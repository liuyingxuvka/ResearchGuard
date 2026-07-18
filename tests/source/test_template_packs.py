from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from researchguard.source.schema import (
    SourceGuardPreventedFailure,
    SourceGuardProofCase,
    build_sourceguard_model_contract,
)
from researchguard.source.template_packs import (
    CLAIM_BOUNDARY,
    EXPECTED_PROFILE_IDS,
    TemplatePackError,
    build_template_instance,
    load_catalog,
    seal_catalog,
    select_template_pack,
    validate_catalog_data,
    validate_native_payload,
    verify_template_instance,
)


FIXTURE = Path(__file__).parent / "fixtures" / "template_packs" / "source_requests.json"


def _profile(catalog: dict, profile_id: str) -> dict:
    return next(item for item in catalog["profiles"] if item["profile_id"] == profile_id)


def _guard_contract(model_id: str, gap_ids: list[str]) -> dict:
    failure = SourceGuardPreventedFailure(
        failure_id=f"failure:{model_id}:unqualified-template-promotion",
        title="Unqualified template candidate is promoted as evidence",
        block_when="a generated discovery skeleton is treated as qualified source support",
        oracle_id="oracle:sourceguard:source-qualification",
        known_good=SourceGuardProofCase(
            case_id=f"good:{model_id}:qualified",
            observation_path="template-pack-known-good-observation.json",
            expected_native_status="pass",
        ),
        known_bad=SourceGuardProofCase(
            case_id=f"bad:{model_id}:unqualified",
            observation_path="template-pack-known-bad-observation.json",
            expected_native_status="blocked",
            mutation_id="make-all-anchors-unusable",
            expected_native_finding="sourceguard_blocked:unqualified-candidate-promotion",
        ),
    )
    return build_sourceguard_model_contract(
        model_id=model_id,
        purpose="Prevent a SourceGuard template skeleton from being promoted as validated evidence.",
        prevented_failures=[failure],
        gap_ids=gap_ids,
        target_unit_ids=[],
        claim_boundary=CLAIM_BOUNDARY,
    ).to_dict()


def test_catalog_inventory_digests_and_native_binding() -> None:
    catalog = load_catalog()
    assert {item["profile_id"] for item in catalog["profiles"]} == EXPECTED_PROFILE_IDS
    assert catalog["base_profile_id"] == "discovery"
    assert catalog["catalog_digest"].startswith("sha256:")
    assert all(item["profile_digest"].startswith("sha256:") for item in catalog["profiles"])
    assert catalog["native_binding"]["schema_owner_id"] == "researchguard.source.schema.BeliefState.from_dict"
    assert catalog["claim_boundary"] == CLAIM_BOUNDARY


@pytest.mark.parametrize("case", json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"])
def test_fixture_selection_cases(case: dict) -> None:
    receipt = select_template_pack(case["request"])
    assert receipt["disposition"] == case["disposition"]
    assert [item["profile_id"] for item in receipt["selected_profiles"]] == case["selected"]
    assert receipt["selection_digest"].startswith("sha256:")
    if case["name"] == "strict-dominance":
        assert receipt["suppressed_by"] == {"citation": "disconfirming"}
    if case["disposition"] in {"no_match", "ambiguous"}:
        bundle = build_template_instance(case["request"])
        assert bundle["model"] is None
        assert bundle["instance_receipt"] is None


def test_composition_has_exact_field_owners_and_native_payload() -> None:
    request = {
        "request_id": "source-composed-instance",
        "intent_tags": ["citation", "lineage"],
        "subject": "battery research",
        "guard_contract": _guard_contract(
            "source-composed-instance",
            ["gap-citation", "gap-lineage"],
        ),
    }
    first = build_template_instance(request)
    second = build_template_instance(request)
    assert first == second
    assert first["selection_receipt"]["disposition"] == "composed"
    owners = first["selection_receipt"]["field_owners"]
    assert len(owners) == 6
    assert set(owners.values()) == {"citation", "lineage"}
    assert first["instance_receipt"]["native_validation"]["ok"] is True
    assert first["model"]["metadata"]["boundary"] == CLAIM_BOUNDARY
    assert verify_template_instance(first)["ok"] is True


def test_authorized_overlap_is_ambiguous_not_silently_merged() -> None:
    catalog = load_catalog()
    citation = _profile(catalog, "citation")
    lineage = _profile(catalog, "lineage")
    lineage["owned_fields"][0] = citation["owned_fields"][0]
    resealed = seal_catalog(catalog)
    validate_catalog_data(resealed)
    receipt = select_template_pack(
        {
            "request_id": "source-overlap",
            "intent_tags": ["citation", "lineage"],
            "subject": "overlap",
        },
        catalog=resealed,
    )
    assert receipt["disposition"] == "ambiguous"
    assert any(item.startswith("field_owner_conflict:") for item in receipt["conflicts"])
    assert not receipt["selected_profiles"]


def test_unsealed_tamper_is_rejected_before_selection() -> None:
    catalog = load_catalog()
    catalog["profiles"][0]["priority"] += 1
    with pytest.raises(TemplatePackError, match="profile digest mismatch"):
        validate_catalog_data(catalog)


def test_invalid_strict_dominance_is_rejected_even_when_resealed() -> None:
    catalog = load_catalog()
    _profile(catalog, "gap")["strict_dominates"] = ["citation"]
    resealed = seal_catalog(catalog)
    with pytest.raises(TemplatePackError, match="strict dominance requires"):
        validate_catalog_data(resealed)


def test_native_cross_reference_failure_is_visible() -> None:
    bundle = build_template_instance(
        {
            "request_id": "source-native-bad",
            "intent_tags": ["gap"],
            "subject": "missing reference",
            "guard_contract": _guard_contract("source-native-bad", ["gap-gap"]),
        }
    )
    broken = deepcopy(bundle["model"])
    broken["actions"][0]["target_gap_id"] = "gap-does-not-exist"
    with pytest.raises(TemplatePackError, match="missing gap"):
        validate_native_payload(broken)


def test_payload_tamper_invalidates_instance_receipt() -> None:
    bundle = build_template_instance(
        {
            "request_id": "source-receipt-tamper",
            "intent_tags": ["multimodal-anchor"],
            "subject": "visual claim",
            "guard_contract": _guard_contract(
                "source-receipt-tamper",
                ["gap-multimodal_anchor"],
            ),
        }
    )
    broken = deepcopy(bundle)
    broken["model"]["metadata"]["purpose"] = "tampered"
    with pytest.raises(TemplatePackError, match="payload digest mismatch"):
        verify_template_instance(broken)


def test_target_authored_guard_contract_is_required_before_candidate_construction() -> None:
    with pytest.raises(TemplatePackError, match="target-authored guard_contract is required"):
        build_template_instance(
            {
                "request_id": "source-missing-purpose-contract",
                "intent_tags": ["gap"],
                "subject": "missing purpose contract",
            }
        )


def test_guard_contract_universe_must_match_selected_template_fragments() -> None:
    with pytest.raises(TemplatePackError, match="gap universe does not match"):
        build_template_instance(
            {
                "request_id": "source-wrong-purpose-universe",
                "intent_tags": ["gap"],
                "subject": "wrong purpose universe",
                "guard_contract": _guard_contract(
                    "source-wrong-purpose-universe",
                    ["gap-not-selected"],
                ),
            }
        )
