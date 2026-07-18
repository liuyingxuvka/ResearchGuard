from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from researchguard.trace.template_packs import (
    CLAIM_BOUNDARY,
    EXPECTED_PROFILE_IDS,
    TemplatePackError,
    build_template_instance,
    derive_cli_example,
    load_catalog,
    seal_catalog,
    select_template_pack,
    validate_catalog_data,
    validate_native_payload,
    verify_template_instance,
)


FIXTURE = Path(__file__).parent / "fixtures" / "template_packs" / "trace_requests.json"


def _profile(catalog: dict, profile_id: str) -> dict:
    return next(item for item in catalog["profiles"] if item["profile_id"] == profile_id)


def test_catalog_inventory_digests_native_binding_and_commands() -> None:
    catalog = load_catalog()
    assert {item["profile_id"] for item in catalog["profiles"]} == EXPECTED_PROFILE_IDS
    assert catalog["base_profile_id"] == "purpose"
    assert catalog["catalog_digest"].startswith("sha256:")
    assert all(item["profile_digest"].startswith("sha256:") for item in catalog["profiles"])
    assert catalog["native_binding"]["reference_validator_id"] == "researchguard.trace.validation.validate_references"
    assert catalog["claim_boundary"] == CLAIM_BOUNDARY
    for profile in catalog["profiles"]:
        example = derive_cli_example(profile["native_binding"]["command_id"])
        assert example.startswith("researchguard trace ")


@pytest.mark.parametrize("case", json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"])
def test_fixture_selection_cases(case: dict) -> None:
    receipt = select_template_pack(case["request"])
    assert receipt["disposition"] == case["disposition"]
    assert [item["profile_id"] for item in receipt["selected_profiles"]] == case["selected"]
    if case["name"] == "strict-dominance":
        assert receipt["suppressed_by"] == {"incident": "causal"}
    if case["disposition"] in {"no_match", "ambiguous"}:
        bundle = build_template_instance(case["request"])
        assert bundle["model"] is None
        assert bundle["instance_receipt"] is None


def test_composition_is_deterministic_native_and_non_factual() -> None:
    request = {
        "request_id": "trace-composed-instance",
        "intent_tags": ["research-lineage", "technology-progression"],
        "subject": "battery research",
    }
    first = build_template_instance(request)
    second = build_template_instance(request)
    assert first == second
    assert first["selection_receipt"]["disposition"] == "composed"
    owners = first["selection_receipt"]["field_owners"]
    assert len(owners) == 8
    assert set(owners.values()) == {"research-lineage", "technology-progression"}
    assert all(
        {
            "validation_status",
            "confidence",
            "allowed_wording",
            "unsafe_wording",
        }.isdisjoint(item)
        for item in first["model"]["traces"]
    )
    assert all(item["usable_as_trace_evidence"] is False for item in first["model"]["evidence"])
    assert first["instance_receipt"]["native_validation"]["ok"] is True
    assert verify_template_instance(first)["ok"] is True


def test_authorized_field_overlap_blocks_composition() -> None:
    catalog = load_catalog()
    lineage = _profile(catalog, "research-lineage")
    progression = _profile(catalog, "technology-progression")
    progression["owned_fields"][0] = lineage["owned_fields"][0]
    resealed = seal_catalog(catalog)
    validate_catalog_data(resealed)
    receipt = select_template_pack(
        {
            "request_id": "trace-overlap",
            "intent_tags": ["research-lineage", "technology-progression"],
            "subject": "overlap",
        },
        catalog=resealed,
    )
    assert receipt["disposition"] == "ambiguous"
    assert any(item.startswith("field_owner_conflict:") for item in receipt["conflicts"])


def test_unsealed_tamper_is_rejected() -> None:
    catalog = load_catalog()
    catalog["profiles"][0]["priority"] += 1
    with pytest.raises(TemplatePackError, match="profile digest mismatch"):
        validate_catalog_data(catalog)


def test_unknown_command_binding_is_rejected_without_fallback() -> None:
    catalog = load_catalog()
    _profile(catalog, "purpose")["native_binding"]["command_id"] = "invented-command"
    resealed = seal_catalog(catalog)
    with pytest.raises(TemplatePackError, match="does not declare command"):
        validate_catalog_data(resealed)


def test_native_reference_failure_is_visible() -> None:
    bundle = build_template_instance(
        {
            "request_id": "trace-native-bad",
            "intent_tags": ["incident"],
            "subject": "outage",
        }
    )
    broken = deepcopy(bundle["model"])
    broken["events"][0]["evidence_ids"] = ["ev_missing"]
    with pytest.raises(TemplatePackError, match="missing evidence"):
        validate_native_payload(broken)


def test_generated_validation_overclaim_is_rejected() -> None:
    bundle = build_template_instance(
        {
            "request_id": "trace-overclaim",
            "intent_tags": ["case-library"],
            "subject": "case",
        }
    )
    broken = deepcopy(bundle["model"])
    broken["traces"][0]["validation_status"] = "validated"
    with pytest.raises(TemplatePackError, match="inference outputs are forbidden"):
        validate_native_payload(broken)


def test_payload_tamper_invalidates_instance_receipt() -> None:
    bundle = build_template_instance(
        {
            "request_id": "trace-receipt-tamper",
            "intent_tags": ["counterfactual"],
            "subject": "intervention",
        }
    )
    broken = deepcopy(bundle)
    broken["model"]["metadata"]["purpose"] = "tampered"
    with pytest.raises(TemplatePackError, match="payload digest mismatch"):
        verify_template_instance(broken)


@pytest.mark.parametrize(
    ("intent_tags", "required_counts"),
    [
        (
            ["incident", "causal"],
            {
                "storyline_hypotheses": 1,
                "hypothesis_evidence_links": 1,
                "causal_candidates": 1,
                "causal_scopes": 1,
            },
        ),
        (
            ["competing-storyline"],
            {
                "storyline_hypotheses": 2,
                "hypothesis_relations": 1,
            },
        ),
        (
            ["counterfactual"],
            {
                "scenario_perturbations": 1,
                "expected_sensitivities": 1,
            },
        ),
    ],
)
def test_schema_v2_profiles_emit_real_typed_skeletons(
    intent_tags: list[str],
    required_counts: dict[str, int],
) -> None:
    bundle = build_template_instance(
        {
            "request_id": "typed-" + "-".join(intent_tags),
            "intent_tags": intent_tags,
            "subject": "typed case",
        }
    )
    assert bundle["model"]["metadata"]["schema_version"] == "researchguard.trace.model.v2"
    for root, count in required_counts.items():
        assert len(bundle["model"][root]) == count
    assert bundle["instance_receipt"]["native_validation"]["inference_engine_id"] == "osqp.direct.v1"
