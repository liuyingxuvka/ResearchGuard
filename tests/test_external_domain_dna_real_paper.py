from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import importlib
import importlib.resources
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
from typing import Mapping
import zipfile

import pytest

import researchguard.domain_dna as domain_dna_module
from researchguard.domain_dna import (
    ExternalDomainDnaError,
    MEMBER_BEHAVIOR_IDS,
    MEMBER_IDS,
    MEMBER_NATIVE_ROUTES,
    _OUTPUT_VALIDATORS,
    _compute_portable_native_context,
    _expected_claim_boundary,
    _portable_native_context,
    build_external_domain_parent_function_block,
    export_external_domain_dna,
    external_domain_dna_impact,
    external_domain_dna_reverse,
    project_external_domain_dna,
    qualify_external_domain_dna,
)
from external_scope_authority_fixtures import signed_scope_authority
from test_portable_composition_bundle import _build_temporary_wheel


REPOSITORY = Path(__file__).resolve().parents[1]
PAPER_FIXTURE_ROOT_ENV = "RESEARCHGUARD_EXTERNAL_DNA_PAPER_ROOT"
_PAPER_FIXTURE_ROOT_RAW = os.environ.get(PAPER_FIXTURE_ROOT_ENV, "").strip()
PAPER_ROOT = (
    Path(_PAPER_FIXTURE_ROOT_RAW).expanduser().resolve()
    if _PAPER_FIXTURE_ROOT_RAW
    else REPOSITORY / ".external-paper-fixture-not-configured"
)
MODEL_ROOT = REPOSITORY / "models" / "external_domain_dna"
CANONICAL_SPEC_PATH = MODEL_ROOT / "attention-is-all-you-need-v7.json"
NATIVE_COMPOSITION_PATH = MODEL_ROOT / "canonical-native-composition.json"
TRUST_ROOTS_PATH = MODEL_ROOT / "canonical-native-trust-roots.json"
SCOPE_AUTHORITY_PATH = MODEL_ROOT / "attention-is-all-you-need-v7.authority.json"
SCOPE_AUTHORITY_TRUST_ROOTS_PATH = (
    MODEL_ROOT / "canonical-scope-authority-trust-roots.json"
)


@pytest.fixture(autouse=True)
def _bounded_native_replay_cache() -> None:
    _compute_portable_native_context.cache_clear()
    yield
    _compute_portable_native_context.cache_clear()


def _spec() -> dict[str, object]:
    return json.loads(CANONICAL_SPEC_PATH.read_text(encoding="utf-8"))


def _native_bundle() -> bytes:
    return NATIVE_COMPOSITION_PATH.read_bytes()


def _trust_roots() -> tuple[str, ...]:
    return tuple(json.loads(TRUST_ROOTS_PATH.read_text(encoding="utf-8")))


def _scope_authority() -> dict[str, object]:
    return json.loads(SCOPE_AUTHORITY_PATH.read_text(encoding="utf-8"))


def _scope_authority_trust_roots() -> tuple[str, ...]:
    return tuple(
        json.loads(SCOPE_AUTHORITY_TRUST_ROOTS_PATH.read_text(encoding="utf-8"))
    )


def _artifact_hashes(spec: dict[str, object]) -> tuple[str, ...]:
    target = spec["target"]
    assert isinstance(target, dict)
    return tuple(str(item["sha256"]) for item in target["artifacts"])


def _digest(value: object) -> str:
    body = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _rebind_external(raw: dict[str, object]) -> bytes:
    core = {
        key: value
        for key, value in raw.items()
        if key not in {"dna_id", "dna_fingerprint"}
    }
    fingerprint = _digest(core)
    raw["dna_fingerprint"] = fingerprint
    raw["dna_id"] = "external-domain-dna:" + fingerprint[7:]
    return json.dumps(
        raw, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _rebind_portable(raw: dict[str, object]) -> bytes:
    core = {
        key: value
        for key, value in raw.items()
        if key not in {"bundle_id", "bundle_fingerprint"}
    }
    fingerprint = _digest(core)
    raw["bundle_fingerprint"] = fingerprint
    raw["bundle_id"] = "portable-composition:" + fingerprint[7:]
    return json.dumps(
        raw, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _export_paper() -> bytes:
    _require_paper_root()
    return export_external_domain_dna(
        _spec(),
        native_composition_bundle=_native_bundle(),
        scope_authority_record=_scope_authority(),
        material_root=PAPER_ROOT,
    )


def _require_paper_root() -> Path:
    if not _PAPER_FIXTURE_ROOT_RAW:
        pytest.skip(
            f"set {PAPER_FIXTURE_ROOT_ENV} to the frozen external paper fixture root"
        )
    if not PAPER_ROOT.is_dir():
        pytest.skip(
            f"{PAPER_FIXTURE_ROOT_ENV} does not name an available directory"
        )
    return PAPER_ROOT


def _refresh_models(spec: dict[str, object], material_root: Path) -> None:
    """Re-derive one generic target through the four native-owner projections."""

    if not material_root.is_dir():
        pytest.skip("external DNA fixture root is unavailable")

    target = spec["target"]
    structures = spec["structure_nodes"]
    models = spec["member_models"]
    assert isinstance(target, dict) and isinstance(structures, list) and isinstance(models, dict)
    native_contexts, _qualified = _portable_native_context(_native_bundle())
    outputs: dict[str, object] = {}
    context: dict[str, object] = {
        "target": target,
        "structure_nodes": structures,
        "material_root": material_root,
        "member_outputs": outputs,
    }
    prior_owned: list[str] = []
    external_inputs = [
        str(target["target_id"]),
        *(str(item["artifact_id"]) for item in target["artifacts"]),
        *(str(item["node_id"]) for item in structures),
    ]
    for member_id in MEMBER_IDS:
        model = models[member_id]
        assert isinstance(model, dict)
        module_name, function_name = MEMBER_NATIVE_ROUTES[member_id][
            "external_transition"
        ].split(":", 1)
        evaluator = getattr(importlib.import_module(module_name), function_name)
        result = evaluator(
            model,
            {**context, "native_member_replay": native_contexts[member_id]},
        )
        model["output"] = result["output"]
        for field, value in result["transition_contract"].items():
            model[field] = value
        owned = sorted(set(_OUTPUT_VALIDATORS[member_id](model["output"])))
        model["owned_object_ids"] = owned
        inputs = external_inputs if member_id == "sourceguard" else prior_owned
        model["bindings"] = [
            {
                "binding_id": f"binding:{member_id}:input:{index}",
                "object_id": object_id,
                "direction": "input_to_model",
                "role": "declared_prerequisite",
            }
            for index, object_id in enumerate(sorted(set(inputs)), start=1)
        ] + [
            {
                "binding_id": f"binding:{member_id}:output:{index}",
                "object_id": object_id,
                "direction": "model_to_output",
                "role": "member_owned_output",
            }
            for index, object_id in enumerate(owned, start=1)
        ]
        scope = target["model_scope"]
        model["scope_binding"] = {
            "scope_id": scope["scope_id"],
            "declared_complete_object_ids": owned,
            "declared_input_object_ids": sorted(set(inputs)),
            "expansion_frontier_ids": list(scope["expansion_frontier_ids"]),
            "completion_status": "complete_within_declared_scope",
        }
        oracle = model["oracle_binding"]
        oracle["protected_failure"] = model["protected_failure"]
        for evidence in model["evidence_bindings"]:
            if evidence["role"] == "model":
                evidence["subject_id"] = model["model_id"]
            elif evidence["role"] == "material":
                evidence["subject_id"] = target["target_id"]
            elif evidence["role"] == "test":
                evidence["subject_id"] = (
                    f"test:{member_id}:external-object-known-good"
                )
            elif evidence["role"] == "oracle":
                evidence["subject_id"] = (
                    f"oracle:{member_id}:external-object-transition"
                )
            elif evidence["role"] == "native_receipt":
                evidence["subject_id"] = model["native_binding"][
                    "native_receipt_ids"
                ][0]
        outputs[member_id] = model["output"]
        prior_owned = owned
    all_owned = {
        object_id
        for member_id in MEMBER_IDS
        for object_id in models[member_id]["owned_object_ids"]
    }
    anchor_ids = {
        str(item["anchor_id"])
        for item in models["sourceguard"]["input"]["extraction_requests"]
    }
    for node in structures:
        node["bound_object_ids"] = [
            anchor_id
            for anchor_id in anchor_ids
            if any(
                request["anchor_id"] == anchor_id
                and request["structure_node_id"] == node["node_id"]
                for request in models["sourceguard"]["input"]["extraction_requests"]
            )
        ]
    structures[0]["bound_object_ids"] = sorted(
        set(structures[0]["bound_object_ids"]) | (all_owned - anchor_ids)
    )
    spec["dependency_edges"] = [
        {
            "edge_id": f"dependency:{left}:{right}",
            "from_id": models[left]["model_id"],
            "to_id": models[right]["model_id"],
            "relation": "member_native_handoff",
        }
        for left, right in zip(MEMBER_IDS, MEMBER_IDS[1:])
    ]
    spec["parent_function_block"] = build_external_domain_parent_function_block(spec)


def test_bounded_paper_dna_is_native_bound_complete_for_scope_and_queryable() -> None:
    spec = _spec()
    assert len(spec["target"]["artifacts"]) == 25
    assert spec["target"]["model_scope"]["scope_kind"] == "bounded_research_question"
    assert spec["target"]["model_scope"]["whole_target_semantics_claimed"] is False
    assert spec["target"]["model_scope"]["expansion_frontier_ids"]
    bundle = _export_paper()
    qualified = qualify_external_domain_dna(
        bundle,
        trusted_artifact_sha256=_artifact_hashes(spec),
        trusted_producer_descriptor_fingerprints=_trust_roots(),
        trusted_scope_authority_producer_descriptor_fingerprints=(
            _scope_authority_trust_roots()
        ),
        material_root=PAPER_ROOT,
    )
    assert qualified["status"] == "dna_qualified"
    assert qualified["native_composition_status"] == "handoff_qualified"
    assert qualified["member_producer_authenticity"] == "licensed"
    assert qualified["whole_target_semantics_status"] == "not_claimed"
    assert qualified["recursive_deepening_available"] is True
    assert qualified["model_scope"]["completion_status"] == "complete_within_declared_scope"
    assert {item["member_id"] for item in qualified["member_summaries"]} == set(MEMBER_IDS)

    compact = project_external_domain_dna(
        bundle,
        trusted_artifact_sha256=_artifact_hashes(spec),
        trusted_producer_descriptor_fingerprints=_trust_roots(),
        trusted_scope_authority_producer_descriptor_fingerprints=(
            _scope_authority_trust_roots()
        ),
        material_root=PAPER_ROOT,
    )
    compact_bytes = json.dumps(compact, ensure_ascii=False).encode("utf-8")
    assert len(compact_bytes) < 16_384
    assert len(compact_bytes) * 10 < len(bundle)
    logic = project_external_domain_dna(
        bundle,
        trusted_artifact_sha256=_artifact_hashes(spec),
        trusted_producer_descriptor_fingerprints=_trust_roots(),
        trusted_scope_authority_producer_descriptor_fingerprints=(
            _scope_authority_trust_roots()
        ),
        material_root=PAPER_ROOT,
        query_kind="behavior",
        object_id=MEMBER_BEHAVIOR_IDS["logicguard"],
    )
    assert logic["query_status"] == "found"
    assert "41.8" in json.dumps(logic["detail"], ensure_ascii=False)
    scope_id = spec["target"]["model_scope"]["scope_id"]
    scope = project_external_domain_dna(
        bundle, query_kind="scope", object_id=scope_id
    )
    assert scope["query_status"] == "found"
    assert scope["detail"]["whole_target_semantics_claimed"] is False

    impact = external_domain_dna_impact(bundle, [spec["target"]["target_id"]])
    assert impact["status"] == "impact_complete"
    assert {
        spec["member_models"][member_id]["model_id"] for member_id in MEMBER_IDS
    }.issubset(set(impact["affected_object_ids"]))
    reverse = external_domain_dna_reverse(
        bundle, "hypothesis:reported-score-is-41.8"
    )
    assert reverse["status"] == "reverse_complete"
    assert "artifact:results-tex" in reverse["upstream_object_ids"]
    assert any(item.startswith("test:") for item in reverse["upstream_object_ids"])
    assert any(item.startswith("oracle:") for item in reverse["upstream_object_ids"])
    assert any(item.startswith("evidence:") for item in reverse["upstream_object_ids"])
    assert MEMBER_NATIVE_ROUTES["experimentguard"]["blueprint_checker"] in reverse[
        "upstream_object_ids"
    ]


def _fully_qualify_paper(bundle: bytes) -> dict[str, object]:
    return qualify_external_domain_dna(
        bundle,
        trusted_artifact_sha256=_artifact_hashes(_spec()),
        trusted_producer_descriptor_fingerprints=_trust_roots(),
        trusted_scope_authority_producer_descriptor_fingerprints=(
            _scope_authority_trust_roots()
        ),
        material_root=PAPER_ROOT,
    )


def test_scope_authority_is_explicit_external_trust_not_bundle_self_trust() -> None:
    bundle = _export_paper()
    untrusted = qualify_external_domain_dna(
        bundle,
        trusted_artifact_sha256=_artifact_hashes(_spec()),
        trusted_producer_descriptor_fingerprints=_trust_roots(),
        material_root=PAPER_ROOT,
    )
    assert untrusted["status"] == "dna_self_consistent"
    assert untrusted["validation_states"]["scope_authority_licensed"] is False
    assert untrusted["validation_states"]["scope_obligation_coverage"] is True
    assert untrusted["first_gap"]["code"] == "scope-authority-trust-not-licensed"

    record = _scope_authority()
    explicitly_trusted = qualify_external_domain_dna(
        bundle,
        trusted_artifact_sha256=_artifact_hashes(_spec()),
        trusted_producer_descriptor_fingerprints=_trust_roots(),
        trusted_scope_authority_fingerprints=[record["authority_fingerprint"]],
        material_root=PAPER_ROOT,
    )
    assert explicitly_trusted["status"] == "dna_qualified"
    assert explicitly_trusted["validation_states"] == {
        "material_inventory_verified": True,
        "member_native_replay_verified": True,
        "candidate_internal_consistency": True,
        "scope_authority_licensed": True,
        "scope_obligation_coverage": True,
        "dna_qualified": True,
    }


def test_synchronized_four_member_shrink_is_candidate_only_and_queries_expose_missing() -> None:
    spec = _spec()
    models = spec["member_models"]
    source = models["sourceguard"]
    source["input"]["extraction_requests"] = [
        source["input"]["extraction_requests"][0]
    ]
    models["traceguard"]["input"]["event_specs"] = [
        models["traceguard"]["input"]["event_specs"][0]
    ]
    models["logicguard"]["input"]["claim_specs"] = [
        models["logicguard"]["input"]["claim_specs"][0]
    ]
    models["experimentguard"]["input"]["hypothesis_ids_by_value"] = {
        "41.8": "hypothesis:reported-score-is-41.8"
    }
    _refresh_models(spec, PAPER_ROOT)
    bundle = export_external_domain_dna(
        spec,
        native_composition_bundle=_native_bundle(),
        scope_authority_record=_scope_authority(),
        material_root=PAPER_ROOT,
    )
    qualified = _fully_qualify_paper(bundle)
    assert qualified["status"] == "candidate_model"
    assert qualified["validation_states"]["candidate_internal_consistency"] is True
    assert qualified["validation_states"]["member_native_replay_verified"] is True
    assert qualified["validation_states"]["scope_authority_licensed"] is True
    assert qualified["validation_states"]["scope_obligation_coverage"] is False
    assert qualified["validation_states"]["dna_qualified"] is False
    assert qualified["first_gap"]["code"] == "authority-required-but-missing"

    impact = external_domain_dna_impact(bundle, [spec["target"]["target_id"]])
    assert "anchor:results-table-enfr-bleu-41.8" in impact[
        "authority_required_but_missing"
    ]
    reverse = external_domain_dna_reverse(
        bundle, "anchor:results-table-enfr-bleu-41.8"
    )
    assert reverse["status"] == "reverse_incomplete"
    assert reverse["first_gap"]["code"] == "authority-required-but-missing"


@pytest.mark.parametrize(
    "mutation",
    ("real-line-rebind", "duplicate-occurrence", "unconstrained-logic", "kind-and-role"),
)
def test_semantically_coherent_rebindings_cannot_rewrite_scope_authority(
    mutation: str,
) -> None:
    spec = _spec()
    models = spec["member_models"]
    requests = models["sourceguard"]["input"]["extraction_requests"]
    if mutation == "real-line-rebind":
        table = requests[1]
        prose = requests[2]
        table["selector"] = deepcopy(prose["selector"])
        table["selector"]["occurrence_id"] = (
            "occurrence:attention-v7:table-rebound-to-real-prose-line"
        )
        table["expected_value"] = prose["expected_value"]
        next(
            row
            for row in spec["structure_nodes"]
            if row["node_id"] == "structure:results-table"
        )["locator"] = prose["selector"]["locator"]
    elif mutation == "duplicate-occurrence":
        requests[1]["selector"]["occurrence_id"] = requests[2]["selector"][
            "occurrence_id"
        ]
    elif mutation == "unconstrained-logic":
        models["logicguard"]["input"]["scope_limits"] = [
            "No boundary limits this conclusion."
        ]
    else:
        spec["target"]["kind"] = "test-workflow"
        source_role = spec["target"]["source_authorities"][0]
        source_role["role"] = "primary_workflow_material"
        models["sourceguard"]["input"]["source_roles"] = [deepcopy(source_role)]
    _refresh_models(spec, PAPER_ROOT)
    bundle = export_external_domain_dna(
        spec,
        native_composition_bundle=_native_bundle(),
        scope_authority_record=_scope_authority(),
        material_root=PAPER_ROOT,
    )
    qualified = _fully_qualify_paper(bundle)
    assert qualified["status"] == "candidate_model"
    assert qualified["validation_states"]["candidate_internal_consistency"] is True
    assert qualified["validation_states"]["scope_obligation_coverage"] is False
    assert qualified["validation_states"]["dna_qualified"] is False


def test_zero_scope_structures_and_coherent_structure_deletion_are_blocked() -> None:
    zero = _spec()
    zero["target"]["model_scope"]["included_structure_node_ids"] = []
    with pytest.raises(ExternalDomainDnaError):
        export_external_domain_dna(
            zero,
            native_composition_bundle=_native_bundle(),
            scope_authority_record=_scope_authority(),
            material_root=PAPER_ROOT,
        )

    reduced = _spec()
    models = reduced["member_models"]
    reduced["structure_nodes"] = reduced["structure_nodes"][:2]
    reduced["target"]["model_scope"]["included_structure_node_ids"] = [
        "structure:abstract"
    ]
    root = reduced["structure_nodes"][0]
    root["artifact_ids"] = sorted(
        set(root["artifact_ids"]) | {"artifact:results-tex"}
    )
    models["sourceguard"]["input"]["extraction_requests"] = [
        models["sourceguard"]["input"]["extraction_requests"][0]
    ]
    models["traceguard"]["input"]["event_specs"] = [
        models["traceguard"]["input"]["event_specs"][0]
    ]
    models["logicguard"]["input"]["claim_specs"] = [
        models["logicguard"]["input"]["claim_specs"][0]
    ]
    models["experimentguard"]["input"]["hypothesis_ids_by_value"] = {
        "41.8": "hypothesis:reported-score-is-41.8"
    }
    reduced_source_role = reduced["target"]["source_authorities"][0]
    reduced_source_role["coverage_ids"] = sorted(
        {
            reduced["target"]["target_id"],
            *(item["artifact_id"] for item in reduced["target"]["artifacts"]),
            *(item["node_id"] for item in reduced["structure_nodes"]),
        }
    )
    models["sourceguard"]["input"]["source_roles"] = [
        deepcopy(reduced_source_role)
    ]
    _refresh_models(reduced, PAPER_ROOT)
    bundle = export_external_domain_dna(
        reduced,
        native_composition_bundle=_native_bundle(),
        scope_authority_record=_scope_authority(),
        material_root=PAPER_ROOT,
    )
    qualified = _fully_qualify_paper(bundle)
    assert qualified["status"] == "candidate_model"
    assert qualified["validation_states"]["scope_obligation_coverage"] is False


def test_coherent_denominator_reductions_and_semantic_rebindings_are_blocked() -> None:
    if not PAPER_ROOT.is_dir():
        pytest.skip("frozen Attention v7 target is unavailable")

    missing_binding = _spec()
    source = missing_binding["member_models"]["sourceguard"]
    source["bindings"] = [
        item
        for item in source["bindings"]
        if item["object_id"] != "artifact:paper-pdf"
    ]
    source["scope_binding"]["declared_input_object_ids"] = [
        item
        for item in source["scope_binding"]["declared_input_object_ids"]
        if item != "artifact:paper-pdf"
    ]
    missing_binding["parent_function_block"] = build_external_domain_parent_function_block(
        missing_binding
    )
    with pytest.raises(ExternalDomainDnaError):
        export_external_domain_dna(
            missing_binding,
            native_composition_bundle=_native_bundle(),
            material_root=PAPER_ROOT,
        )

    missing_material = _spec()
    removed = missing_material["target"]["artifacts"].pop()
    removed_id = removed["artifact_id"]
    missing_material["target"]["source_authorities"][0]["coverage_ids"].remove(removed_id)
    for node in missing_material["structure_nodes"]:
        if removed_id in node["artifact_ids"]:
            node["artifact_ids"].remove(removed_id)
    source = missing_material["member_models"]["sourceguard"]
    source["input"]["source_roles"] = deepcopy(
        missing_material["target"]["source_authorities"]
    )
    source["output"]["source_roles"] = deepcopy(
        missing_material["target"]["source_authorities"]
    )
    source["bindings"] = [item for item in source["bindings"] if item["object_id"] != removed_id]
    source["scope_binding"]["declared_input_object_ids"].remove(removed_id)
    missing_material["parent_function_block"] = build_external_domain_parent_function_block(
        missing_material
    )
    with pytest.raises(ExternalDomainDnaError, match="closed directory tree"):
        export_external_domain_dna(
            missing_material,
            native_composition_bundle=_native_bundle(),
            material_root=PAPER_ROOT,
        )

    two_materials = deepcopy(missing_material)
    while len(two_materials["target"]["artifacts"]) > 2:
        victim = two_materials["target"]["artifacts"].pop()
        victim_id = victim["artifact_id"]
        if victim_id in two_materials["target"]["source_authorities"][0]["coverage_ids"]:
            two_materials["target"]["source_authorities"][0]["coverage_ids"].remove(victim_id)
        for node in two_materials["structure_nodes"]:
            if victim_id in node["artifact_ids"]:
                node["artifact_ids"].remove(victim_id)
        source = two_materials["member_models"]["sourceguard"]
        source["bindings"] = [item for item in source["bindings"] if item["object_id"] != victim_id]
        if victim_id in source["scope_binding"]["declared_input_object_ids"]:
            source["scope_binding"]["declared_input_object_ids"].remove(victim_id)
    source["input"]["source_roles"] = deepcopy(
        two_materials["target"]["source_authorities"]
    )
    source["output"]["source_roles"] = deepcopy(
        two_materials["target"]["source_authorities"]
    )
    two_materials["parent_function_block"] = build_external_domain_parent_function_block(
        two_materials
    )
    with pytest.raises(ExternalDomainDnaError):
        export_external_domain_dna(
            two_materials,
            native_composition_bundle=_native_bundle(),
            material_root=PAPER_ROOT,
        )

    table_rebound = _spec()
    request = table_rebound["member_models"]["sourceguard"]["input"][
        "extraction_requests"
    ][1]
    request["structure_node_id"] = "structure:results-prose"
    request["expected_structure_kind"] = "paragraph"
    with pytest.raises(ExternalDomainDnaError, match="structure role"):
        export_external_domain_dna(
            table_rebound,
            native_composition_bundle=_native_bundle(),
            material_root=PAPER_ROOT,
        )

    for mutation in ("source-role", "logic-scope", "trace-event", "logic-claim", "parent", "top"):
        attacked = _spec()
        if mutation == "source-role":
            attacked["target"]["source_authorities"][0]["role"] = "secondary_commentary"
            attacked["member_models"]["sourceguard"]["input"]["source_roles"] = deepcopy(
                attacked["target"]["source_authorities"]
            )
            attacked["member_models"]["sourceguard"]["output"]["source_roles"] = deepcopy(
                attacked["target"]["source_authorities"]
            )
        elif mutation == "logic-scope":
            attacked["member_models"]["logicguard"]["input"]["scope_limits"] = []
            attacked["member_models"]["logicguard"]["output"]["scope_limits"] = []
        elif mutation == "trace-event":
            attacked["member_models"]["traceguard"]["output"]["ordered_events"].pop()
        elif mutation == "logic-claim":
            attacked["member_models"]["logicguard"]["output"]["claims"].pop()
        elif mutation == "parent":
            attacked["parent_function_block"]["child_input_mappings"].pop()
        else:
            attacked["claim_boundary"] += " This is the complete semantic DNA of the paper."
        with pytest.raises(ExternalDomainDnaError):
            export_external_domain_dna(
                attacked,
                native_composition_bundle=_native_bundle(),
                material_root=PAPER_ROOT,
            )


def test_target_native_chain_consumes_every_declared_upstream_semantic() -> None:
    """Role, storyline and argument meaning cannot be inert handoff decoration."""

    _require_paper_root()
    spec = _spec()
    target = spec["target"]
    structures = spec["structure_nodes"]
    models = spec["member_models"]
    native_contexts, _qualified = _portable_native_context(_native_bundle())
    outputs: dict[str, object] = {}
    base_context: dict[str, object] = {
        "target": target,
        "structure_nodes": structures,
        "material_root": PAPER_ROOT,
        "member_outputs": outputs,
    }
    results: dict[str, Mapping[str, object]] = {}
    for member_id in MEMBER_IDS:
        module_name, function_name = MEMBER_NATIVE_ROUTES[member_id][
            "external_transition"
        ].split(":", 1)
        evaluator = getattr(importlib.import_module(module_name), function_name)
        result = evaluator(
            models[member_id],
            {**base_context, "native_member_replay": native_contexts[member_id]},
        )
        results[member_id] = result
        outputs[member_id] = result["output"]
        declared_inputs = {
            str(item["object_id"])
            for item in models[member_id]["bindings"]
            if item["direction"] == "input_to_model"
        }
        assert set(result["native_result"]["consumed_upstream_object_ids"]) == declared_inputs

    trace_evaluator = getattr(
        importlib.import_module("researchguard.trace.owner_attestation"),
        "evaluate_external_object_transition",
    )
    role_attack = deepcopy(outputs)
    role_attack["sourceguard"]["source_roles"][0]["role"] = "foreign_source_role"
    with pytest.raises(ValueError, match="roles differ"):
        trace_evaluator(
            models["traceguard"],
            {
                **base_context,
                "member_outputs": role_attack,
                "native_member_replay": native_contexts["traceguard"],
            },
        )

    logic_evaluator = getattr(
        importlib.import_module("researchguard.logic.owner_attestation"),
        "evaluate_external_object_transition",
    )
    storyline_attack = deepcopy(outputs)
    storyline_attack["traceguard"]["storylines"][0]["status"] = "consistent"
    with pytest.raises(ValueError, match="storyline status"):
        logic_evaluator(
            models["logicguard"],
            {
                **base_context,
                "member_outputs": storyline_attack,
                "native_member_replay": native_contexts["logicguard"],
            },
        )

    experiment_evaluator = getattr(
        importlib.import_module("researchguard.experiment.owner_attestation"),
        "evaluate_external_object_transition",
    )
    relation_attack = deepcopy(outputs)
    relation_attack["logicguard"]["argument_edges"][0]["relation"] = (
        "asserts_unlicensed_truth"
    )
    with pytest.raises(ValueError, match="argument edge is invalid"):
        experiment_evaluator(
            models["experimentguard"],
            {
                **base_context,
                "member_outputs": relation_attack,
                "native_member_replay": native_contexts["experimentguard"],
            },
        )

    foreign_source = _spec()
    foreign_source["member_models"]["sourceguard"]["input"][
        "extraction_requests"
    ][0]["source_id"] = "source:foreign-target-authority"
    with pytest.raises(ExternalDomainDnaError, match="outside target source authorities"):
        domain_dna_module._validate_spec(foreign_source)


@pytest.mark.parametrize(
    "mutation",
    ("test-id", "oracle-producer", "material-subject", "receipt-subject"),
)
def test_target_native_binding_identities_reject_fakes(mutation: str) -> None:
    attacked = _spec()
    model = attacked["member_models"]["logicguard"]
    if mutation == "test-id":
        model["test_bindings"][0]["test_id"] = "test:logicguard:forged-good"
        model["oracle_binding"]["good_case_id"] = "test:logicguard:forged-good"
    elif mutation == "oracle-producer":
        model["oracle_binding"]["checker_entrypoint"] = (
            "researchguard.logic.owner_attestation:forged_transition"
        )
    elif mutation == "material-subject":
        next(
            item for item in model["evidence_bindings"] if item["role"] == "material"
        )["subject_id"] = "paper:forged-target"
    else:
        next(
            item
            for item in model["evidence_bindings"]
            if item["role"] == "native_receipt"
        )["subject_id"] = "receipt:logicguard:forged"
    with pytest.raises(ExternalDomainDnaError):
        domain_dna_module._validate_spec(attacked)


def test_capability_fixture_and_target_native_replay_are_separate_evidence() -> None:
    bundle = _export_paper()
    raw = json.loads(bundle)
    models = raw["member_models"]
    for member_id in MEMBER_IDS:
        evidence = raw["native_member_evidence"][member_id]
        assert evidence["target_native_replay_status"] == (
            "passed_good_and_rejected_bad"
        )
        assert evidence["capability_fixture_replay_fingerprint"].startswith("sha256:")
        assert evidence["target_native_good_case_fingerprint"].startswith("sha256:")
        assert evidence["target_native_bad_case_fingerprint"].startswith("sha256:")
        assert evidence["target_native_oracle_fingerprint"].startswith("sha256:")
        assert evidence["capability_fixture_replay_fingerprint"] != evidence[
            "target_native_good_case_fingerprint"
        ]
        assert set(evidence["consumed_upstream_object_ids"]) == {
            str(item["object_id"])
            for item in models[member_id]["bindings"]
            if item["direction"] == "input_to_model"
        }
    self_consistent = qualify_external_domain_dna(bundle)
    assert self_consistent["capability_fixture_replay_status"] == "passed"
    assert self_consistent["target_native_replay_status"] == (
        "passed_good_and_rejected_bad"
    )
    assert self_consistent["validation_states"]["dna_qualified"] is False


def test_embedded_native_payload_and_manifest_attacks_remain_blocked_after_rebinding() -> None:
    bundle = _export_paper()
    for attack in ("payload", "manifest"):
        raw = json.loads(bundle)
        native = base64.b64decode(raw["native_composition"]["bundle_b64"])
        native_raw = json.loads(native)
        envelope = native_raw["portable_member_envelopes"][0]
        if attack == "payload":
            envelope["opaque_payload_b64"] = None
        else:
            manifest = envelope["behavior_manifest"]
            manifest["domain_behavior_cases"].pop()
            core = {
                key: value
                for key, value in manifest.items()
                if key not in {"manifest_id", "manifest_fingerprint"}
            }
            manifest["manifest_fingerprint"] = _digest(core)
            manifest["manifest_id"] = (
                f"member-behavior-manifest:{envelope['member_id']}:"
                + manifest["manifest_fingerprint"][7:]
            )
            envelope_core = {
                key: value
                for key, value in envelope.items()
                if key not in {"envelope_fingerprint", "opaque_payload_b64"}
            }
            envelope["envelope_fingerprint"] = _digest(envelope_core)
        rebound_native = _rebind_portable(native_raw)
        native_fingerprint = json.loads(rebound_native)["bundle_fingerprint"]
        raw["native_composition"]["bundle_b64"] = base64.b64encode(
            rebound_native
        ).decode("ascii")
        raw["native_composition"]["bundle_fingerprint"] = native_fingerprint
        rejected = qualify_external_domain_dna(_rebind_external(raw))
        assert rejected["status"] == "dna_blocked"
        assert rejected["first_gap"]["code"] == "external-domain-dna-invalid"


def test_native_replay_cache_has_exact_identity_and_never_caches_material_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = _native_bundle()
    _portable_native_context(native)
    first = _compute_portable_native_context.cache_info()
    assert (first.hits, first.misses, first.currsize, first.maxsize) == (0, 1, 1, 8)
    _portable_native_context(native)
    second = _compute_portable_native_context.cache_info()
    assert second.hits == 1 and second.misses == 1

    _portable_native_context(
        native,
        trusted_producer_descriptor_fingerprints=tuple(reversed(_trust_roots())),
    )
    trusted_once = _compute_portable_native_context.cache_info()
    assert trusted_once.misses == 2
    _portable_native_context(
        native,
        trusted_producer_descriptor_fingerprints=_trust_roots(),
    )
    normalized_order = _compute_portable_native_context.cache_info()
    assert normalized_order.hits == 2 and normalized_order.misses == 2

    changed = json.loads(native)
    changed["claim_boundary"] += " Cache identity probe only."
    changed_native = _rebind_portable(changed)
    _portable_native_context(changed_native)
    changed_identity = _compute_portable_native_context.cache_info()
    assert changed_identity.misses == 3
    assert changed_identity.currsize <= changed_identity.maxsize == 8

    if not PAPER_ROOT.is_dir():
        return
    material_calls = 0
    original_verify = domain_dna_module._verify_target_materials

    def counted_verify(target: object, root: Path):
        nonlocal material_calls
        material_calls += 1
        return original_verify(target, root)  # type: ignore[arg-type]

    monkeypatch.setattr(domain_dna_module, "_verify_target_materials", counted_verify)
    spec = _spec()
    bundle = export_external_domain_dna(
        spec,
        native_composition_bundle=native,
        material_root=PAPER_ROOT,
    )
    for _ in range(2):
        qualify_external_domain_dna(bundle, material_root=PAPER_ROOT)
    assert material_calls == 3


def test_generic_nonpaper_consistent_workflow_uses_the_same_native_path(tmp_path: Path) -> None:
    spec = _spec()
    target = spec["target"]
    workflow = {"transitions": {"ready_to_done": "done"}}
    body = json.dumps(
        workflow, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    material = tmp_path / "workflow.json"
    material.write_bytes(body)
    target.update(
        {
            "target_id": "workflow:synthetic-state-check",
            "title": "Synthetic state-check workflow",
            "kind": "test-workflow",
            "version": "fixture:v1",
            "official_url": "https://example.invalid/state-check/v1",
            "artifacts": [
                {
                    "artifact_id": "artifact:workflow-json",
                    "role": "modeled-workflow-definition",
                    "official_url": "https://example.invalid/state-check/v1/workflow.json",
                    "relative_path": "workflow.json",
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "byte_length": len(body),
                    "embedded": False,
                    "disposition": "modeled",
                }
            ],
        }
    )
    scope = target["model_scope"]
    scope.update(
        {
            "scope_id": "scope:workflow:reported-state-consistency",
            "purpose": "Check whether declared workflow state observations are consistent.",
            "included_question_ids": ["question:workflow-state-consistency"],
            "included_structure_node_ids": ["structure:workflow-transition"],
            "excluded_semantic_region_ids": ["semantic-region:workflow:outside-state-check"],
            "expansion_frontier_ids": ["frontier:workflow:recursive-behavior-inventory"],
        }
    )
    spec["structure_nodes"] = [
        {
            "node_id": "structure:workflow-root",
            "parent_id": None,
            "kind": "workflow",
            "label": "Synthetic workflow",
            "locator": "workflow.json",
            "semantic_role": "workflow_definition_root",
            "member_ids": list(MEMBER_IDS),
            "artifact_ids": [],
            "bound_object_ids": [],
        },
        {
            "node_id": "structure:workflow-transition",
            "parent_id": "structure:workflow-root",
            "kind": "state-transition",
            "label": "ready to done transition",
            "locator": "workflow.json#/transitions/ready_to_done",
            "semantic_role": "declared_state_transition",
            "member_ids": list(MEMBER_IDS),
            "artifact_ids": ["artifact:workflow-json"],
            "bound_object_ids": ["anchor:workflow:ready-to-done"],
        },
    ]
    source_id = "source:workflow:synthetic-state-check"
    coverage = sorted(
        {
            target["target_id"],
            *(item["artifact_id"] for item in target["artifacts"]),
            *(item["node_id"] for item in spec["structure_nodes"]),
        }
    )
    authority = {
        "source_id": source_id,
        "role": "primary_workflow_material",
        "coverage_ids": coverage,
    }
    target["source_authorities"] = [authority]
    models = spec["member_models"]
    source_input = models["sourceguard"]["input"]
    source_input["target_id"] = target["target_id"]
    source_input["source_roles"] = [authority]
    selected_body = json.dumps(
        "done", ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    source_input["extraction_requests"] = [
        {
            "anchor_id": "anchor:workflow:ready-to-done",
            "claim_id": "claim:workflow:declared-state",
            "source_id": source_id,
            "role": "declared_transition_target_state",
            "artifact_id": "artifact:workflow-json",
            "selector": {
                "selector_kind": "json_pointer",
                "occurrence_id": "occurrence:workflow:ready-to-done",
                "locator": "workflow.json#/transitions/ready_to_done",
                "fingerprint": "sha256:" + hashlib.sha256(selected_body).hexdigest(),
                "parameters": {"pointer": "/transitions/ready_to_done"},
            },
            "expected_value": "done",
            "structure_node_id": "structure:workflow-transition",
            "expected_structure_kind": "state-transition",
        }
    ]
    models["traceguard"]["input"]["event_specs"] = [
        {
            "event_id": "event:workflow:ready-to-done",
            "anchor_id": "anchor:workflow:ready-to-done",
            "stage": "declared-transition",
        }
    ]
    models["traceguard"]["input"]["storyline_id"] = "storyline:workflow:state-check"
    models["logicguard"]["input"]["claim_specs"] = [
        {
            "event_id": "event:workflow:ready-to-done",
            "claim_id": "claim:workflow:ready-to-done",
            "edge_id": "edge:workflow:transition-supports-summary",
        }
    ]
    models["logicguard"]["input"]["summary_claim_id"] = (
        "claim:workflow:declared-state-consistent"
    )
    models["logicguard"]["input"]["scope_limits"] = [
        "The model checks the declared transition target, not runtime execution."
    ]
    models["experimentguard"]["input"]["hypothesis_ids_by_value"] = {
        "done": "hypothesis:workflow-state-is-done"
    }
    models["experimentguard"]["input"]["comparison_experiment_id"] = (
        "experiment:workflow:compare-declared-state"
    )
    models["experimentguard"]["input"]["resolution_experiment_id"] = (
        "experiment:workflow:runtime-check"
    )
    for member_id in MEMBER_IDS:
        models[member_id]["model_id"] = f"model:{member_id}:synthetic-state-check"
        models[member_id]["scope_binding"]["scope_id"] = scope["scope_id"]
        models[member_id]["scope_binding"]["expansion_frontier_ids"] = list(
            scope["expansion_frontier_ids"]
        )
    spec["claim_boundary"] = _expected_claim_boundary(
        target["target_id"], scope["scope_id"]
    )
    source_outputs = [source_id, "anchor:workflow:ready-to-done"]
    trace_outputs = [
        "event:workflow:ready-to-done",
        "storyline:workflow:state-check",
    ]
    logic_outputs = [
        "claim:workflow:ready-to-done",
        "claim:workflow:declared-state-consistent",
        "edge:workflow:transition-supports-summary",
    ]
    experiment_outputs = [
        "hypothesis:workflow-state-is-done",
        "experiment:workflow:compare-declared-state",
        "experiment:workflow:runtime-check",
    ]
    external_inputs = sorted(
        {
            target["target_id"],
            "artifact:workflow-json",
            "structure:workflow-root",
            "structure:workflow-transition",
        }
    )
    authority_material = {
        "authority_id": "scope-authority:workflow:state-check:v1",
        "authority_revision": "1",
        "provenance": {
            "origin_kind": "test_fixture",
            "origin_id": "fixture:workflow:state-check:v1",
            "issued_at": "2026-08-05T00:00:00Z",
            "request_fingerprint": _digest(
                {"target": target["target_id"], "scope": scope["scope_id"]}
            ),
        },
        "target": {
            key: deepcopy(target[key])
            for key in (
                "target_id",
                "title",
                "kind",
                "version",
                "official_url",
                "material_inventory_policy",
                "source_authorities",
                "artifacts",
            )
        },
        "scope": {
            **{
                key: deepcopy(scope[key])
                for key in (
                    "scope_id",
                    "purpose",
                    "scope_kind",
                    "completion_status",
                    "whole_target_semantics_claimed",
                    "included_question_ids",
                    "included_structure_node_ids",
                    "excluded_semantic_region_ids",
                    "expansion_frontier_ids",
                )
            },
            "structure_obligations": [
                {
                    "node_id": "structure:workflow-root",
                    "parent_id": None,
                    "kind": "workflow",
                    "semantic_role": "workflow_definition_root",
                    "locator": "workflow.json",
                    "required_member_ids": list(MEMBER_IDS),
                    "required_artifact_ids": [],
                    "required_bound_object_ids": sorted(
                        set(source_outputs + trace_outputs + logic_outputs + experiment_outputs)
                        - {"anchor:workflow:ready-to-done"}
                    ),
                },
                {
                    "node_id": "structure:workflow-transition",
                    "parent_id": "structure:workflow-root",
                    "kind": "state-transition",
                    "semantic_role": "declared_state_transition",
                    "locator": "workflow.json#/transitions/ready_to_done",
                    "required_member_ids": list(MEMBER_IDS),
                    "required_artifact_ids": ["artifact:workflow-json"],
                    "required_bound_object_ids": ["anchor:workflow:ready-to-done"],
                },
            ],
            "anchor_obligations": deepcopy(source_input["extraction_requests"]),
            "member_obligations": [
                {
                    "member_id": "sourceguard",
                    "required_input_object_ids": external_inputs,
                    "required_output_object_ids": source_outputs,
                    "required_output_kinds": [
                        {"kind": "source_role", "object_ids": [source_id]},
                        {"kind": "claim_anchor", "object_ids": ["anchor:workflow:ready-to-done"]},
                        {"kind": "gap", "object_ids": []},
                    ],
                },
                {
                    "member_id": "traceguard",
                    "required_input_object_ids": source_outputs,
                    "required_output_object_ids": trace_outputs,
                    "required_output_kinds": [
                        {"kind": "ordered_event", "object_ids": ["event:workflow:ready-to-done"]},
                        {"kind": "storyline", "object_ids": ["storyline:workflow:state-check"]},
                        {"kind": "gap", "object_ids": []},
                    ],
                },
                {
                    "member_id": "logicguard",
                    "required_input_object_ids": trace_outputs,
                    "required_output_object_ids": logic_outputs,
                    "required_output_kinds": [
                        {"kind": "claim", "object_ids": logic_outputs[:2]},
                        {"kind": "argument_edge", "object_ids": [logic_outputs[2]]},
                        {"kind": "gap", "object_ids": []},
                    ],
                },
                {
                    "member_id": "experimentguard",
                    "required_input_object_ids": logic_outputs,
                    "required_output_object_ids": experiment_outputs,
                    "required_output_kinds": [
                        {"kind": "hypothesis", "object_ids": [experiment_outputs[0]]},
                        {"kind": "experiment", "object_ids": experiment_outputs[1:]},
                        {"kind": "gap", "object_ids": []},
                    ],
                },
            ],
            "cross_member_handoffs": [
                {
                    "object_id": object_id,
                    "producer_member_id": member_id,
                    "consumer_member_ids": (
                        [MEMBER_IDS[index + 1]] if index + 1 < len(MEMBER_IDS) else []
                    ),
                }
                for index, (member_id, outputs) in enumerate(
                    zip(
                        MEMBER_IDS,
                        (source_outputs, trace_outputs, logic_outputs, experiment_outputs),
                    )
                )
                for object_id in outputs
            ],
            "scope_limits": deepcopy(models["logicguard"]["input"]["scope_limits"]),
        },
    }
    scope_authority = signed_scope_authority(authority_material)
    spec["scope_authority_binding"] = {
        "authority_id": authority_material["authority_id"],
        "authority_fingerprint": scope_authority["authority_fingerprint"],
        "producer_descriptor_fingerprint": scope_authority[
            "producer_descriptor_fingerprint"
        ],
    }
    _refresh_models(spec, tmp_path)
    bundle = export_external_domain_dna(
        spec,
        native_composition_bundle=_native_bundle(),
        scope_authority_record=scope_authority,
        material_root=tmp_path,
    )
    qualified = qualify_external_domain_dna(
        bundle,
        trusted_artifact_sha256=_artifact_hashes(spec),
        trusted_producer_descriptor_fingerprints=_trust_roots(),
        trusted_scope_authority_producer_descriptor_fingerprints=[
            scope_authority["producer_descriptor_fingerprint"]
        ],
        material_root=tmp_path,
    )
    assert qualified["status"] == "dna_qualified"
    assert {item["gap_count"] for item in qualified["member_summaries"]} == {0}
    assert qualified["target_id"] == "workflow:synthetic-state-check"
    assert source_input["extraction_requests"][0]["selector"]["selector_kind"] == "json_pointer"
    assert "line_number" not in source_input["extraction_requests"][0]


def test_wheel_packaging_and_zero_bespoke_domain_evaluator_residuals(
    tmp_path: Path,
) -> None:
    bundle = _export_paper()
    bundle_path = tmp_path / "domain-dna.json"
    bundle_path.write_bytes(bundle)

    for member_id in MEMBER_IDS:
        assert not (REPOSITORY / "src" / "researchguard" / member_id.removesuffix("guard") / "domain_dna.py").exists()
    forbidden_imports = {
        f"researchguard.{member_id.removesuffix('guard')}.domain_dna"
        for member_id in MEMBER_IDS
    }
    python_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (REPOSITORY / "src").rglob("*.py")
    )
    assert all(item not in python_text for item in forbidden_imports)

    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = _build_temporary_wheel(REPOSITORY, wheelhouse)
    installed_site = tmp_path / "installed-site"
    fresh_home = tmp_path / "fresh-home"
    fresh_home.mkdir()
    installed_site.mkdir()
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(installed_site)
    child = textwrap.dedent(
        """
        import json, os, sys
        from pathlib import Path
        installed, repository, paper, bundle = map(Path, sys.argv[1:5])
        sys.path.insert(0, str(installed))
        def audit(event, args):
            if event != 'open' or not args:
                return
            try: candidate = Path(os.fspath(args[0])).resolve()
            except (OSError, TypeError, ValueError): return
            if candidate == repository or repository in candidate.parents:
                raise RuntimeError(f'repository read: {candidate}')
            if candidate == paper or paper in candidate.parents:
                raise RuntimeError(f'target material read: {candidate}')
            if 'researchguard-external-domain-dna-compiler-' in candidate.as_posix().lower():
                raise RuntimeError(f'compiler temporary material read: {candidate}')
        sys.addaudithook(audit)
        from researchguard.domain_dna import project_external_domain_dna
        result = project_external_domain_dna(
            bundle.read_bytes(),
            trusted_artifact_sha256=sys.argv[5].split(','),
            trusted_producer_descriptor_fingerprints=sys.argv[6].split(','),
        )
        assert not (installed / 'researchguard' / 'resources' / 'external_domain_dna').exists()
        print(json.dumps(result, sort_keys=True))
        """
    )
    environment = os.environ.copy()
    environment.update({"HOME": str(fresh_home), "USERPROFILE": str(fresh_home), "PYTHONDONTWRITEBYTECODE": "1"})
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            child,
            str(installed_site),
            str(REPOSITORY),
            str(PAPER_ROOT),
            str(bundle_path),
            ",".join(_artifact_hashes(_spec())),
            ",".join(_trust_roots()),
        ],
        cwd=fresh_home,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    independent = json.loads(completed.stdout)
    assert independent["status"] == "dna_self_consistent"
    assert independent["member_producer_authenticity"] == "licensed"
    assert independent["anchor_material_replay_status"] == "not_run"
    assert len(completed.stdout.encode()) < 16_384
    assert len(completed.stdout.encode()) * 10 < len(bundle)
