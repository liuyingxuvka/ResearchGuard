from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from researchguard.trace.library_depth import (
    NATIVE_OWNER_ID,
    NATIVE_ROUTE_ID,
    OBJECT_RELATIONSHIPS,
    REQUIRED_OBLIGATIONS,
    TARGET_SKILL_ID,
    build_library_scheduled_production_package,
    evaluate_library_execution_package,
)


ROOT = Path(__file__).resolve().parents[2]


def test_case_library_is_an_internal_traceguard_route() -> None:
    route = ROOT / "skills" / "traceguard" / "references" / "routes" / "case-library.md"
    assert route.is_file()
    text = route.read_text(encoding="utf-8")
    assert "researchguard trace library" in text
    assert "traceguard-library" not in text


def _write_production_package(
    target_root: Path,
    package: dict,
    relative: str,
) -> list[str]:
    paths: set[str] = set()
    pairs = (
        ("evidence_ref", "evidence_sha256"),
        ("artifact_ref", "artifact_sha256"),
        ("source_ref", "content_sha256"),
    )

    def visit(node: object) -> None:
        if isinstance(node, dict):
            for ref_field, hash_field in pairs:
                if ref_field in node:
                    ref = str(node[ref_field])
                    paths.add(ref)
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(package)
    for ref in paths:
        path = target_root / ref
        assert path.is_file(), ref
    package_path = target_root / relative
    package_path.parent.mkdir(parents=True, exist_ok=True)
    package_path.write_text(json.dumps(package), encoding="utf-8")
    return [relative, *sorted(paths)]


def _copy_production_library(target_root: Path) -> None:
    shutil.copytree(ROOT / "examples/trace/case_library", target_root / "library")


def _rewrite_bound_hash(package: dict, relative: str, digest: str) -> None:
    pairs = (
        ("evidence_ref", "evidence_sha256"),
        ("artifact_ref", "artifact_sha256"),
        ("source_ref", "content_sha256"),
    )

    def visit(node: object) -> None:
        if isinstance(node, dict):
            for ref_field, hash_field in pairs:
                if node.get(ref_field) == relative:
                    node[hash_field] = digest
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(package)


def _evidence(obligation_id: str) -> dict:
    return {"obligation_id":obligation_id,"status":"complete","evidence_ref":f"evidence/{obligation_id}.json","evidence_sha256":"a"*64,"native_range":{"range_id":f"native:{obligation_id}","source_ref":f"evidence/{obligation_id}.json","content_sha256":"a"*64,"start_anchor":f"{obligation_id}:start","end_anchor":f"{obligation_id}:end"}}


def _object(object_id: str, kind: str) -> dict:
    return {"object_id":object_id,"object_kind":kind,"importance":"important","disposition":"covered","relationship_results":[{"relationship_id":relationship_id,"status":"complete","evidence_ref":f"evidence/{object_id}/{relationship_id}.json","evidence_sha256":"b"*64} for relationship_id in OBJECT_RELATIONSHIPS[kind]]}


def _positive() -> dict:
    ids_and_kinds = [
        ("case:c1", "case"),
        ("direction:d1", "direction"),
        ("source:s1", "source"),
        ("evidence:e1", "evidence"),
        ("event:v1", "event"),
        ("lead:l1", "lead"),
        ("trace:t1", "trace"),
        ("gap:g1", "gap"),
        ("hypothesis:h1", "hypothesis"),
        ("causal-candidate:c1", "causal_candidate"),
        ("perturbation:p1", "perturbation"),
        ("inference-receipt:r1", "inference_receipt"),
    ]
    object_ids = [item[0] for item in ids_and_kinds]
    return {
        "artifact_kind":"traceguard_library_execution_package",
        "target_skill_id":TARGET_SKILL_ID,
        "native_owner_id":NATIVE_OWNER_ID,
        "native_route_id":NATIVE_ROUTE_ID,
        "run_id":"run:traceguard:case-library:positive",
        "evidence_domain":"fixture_calibration",
        "selected_scope":{"library_id":"library:fixture","scope_kind":"case","scope_id":"case:c1","scope_fingerprint":"c"*64},
        "operation_status":"pass",
        "inference_outputs_in_input": [],
        "inference_observations": [
            {
                "record_kind": "inference_observation",
                "authority": "observation_only",
                "receipt_id": "inference-receipt:r1",
                "receipt_ref": "evidence/inference-receipt-r1.json",
                "receipt_sha256": "e" * 64,
            }
        ],
        "native_artifacts":[{"artifact_id":"library:case-package","artifact_ref":"fixtures/case-c1.json","artifact_sha256":"d"*64,"status":"current"}],
        "obligation_results":[_evidence(item) for item in REQUIRED_OBLIGATIONS],
        "object_universe":{"declared_object_ids":list(object_ids),"discovered_object_ids":list(object_ids),"required_object_ids":["case:c1","source:s1","evidence:e1"],"important_object_ids":list(object_ids),"excluded_objects":[],"evaluated_object_ids":list(object_ids),"object_kind_by_id":dict(ids_and_kinds)},
        "object_results":[_object(object_id,kind) for object_id,kind in ids_and_kinds],
        "blockers":[],
        "residual_risk":["Case-library closure is not final factual or causal proof."],
        "claim_boundary":"Covers preservation, linkage, current evaluation handoff, and gap write-back for the selected case only.",
    }


def test_complete_selected_scope_receipt_passes_and_is_bound_to_library_route() -> None:
    receipt=evaluate_library_execution_package(_positive())
    assert receipt["status"]=="pass",receipt["errors"]
    assert receipt["target_skill_id"]==TARGET_SKILL_ID
    assert receipt["native_owner_id"]==NATIVE_OWNER_ID
    assert receipt["receipt_sha256"]
    assert {row["obligation_id"] for row in receipt["native_obligation_evidence"]} == set(REQUIRED_OBLIGATIONS)
    for object_row in receipt["per_object_relationship_coverage"]:
        assert object_row["relationship_ids"] == [
            row["relationship_id"] for row in object_row["relationship_evidence"]
        ]
        assert all(
            row["evidence_ref"] and row["evidence_sha256"]
            for row in object_row["relationship_evidence"]
        )


def test_shallow_missing_important_obligation_and_relationship_both_block() -> None:
    payload=_positive()
    payload["obligation_results"]=[row for row in payload["obligation_results"] if row["obligation_id"]!="evidence_before_event_or_trace"]
    evidence=next(row for row in payload["object_results"] if row["object_id"]=="evidence:e1")
    evidence["relationship_results"]=[row for row in evidence["relationship_results"] if row["relationship_id"]!="event_trace_or_gap_disposition"]
    receipt=evaluate_library_execution_package(payload)
    codes={item["code"] for item in receipt["errors"]}
    assert receipt["status"]=="blocked"
    assert "missing_target_obligation" in codes
    assert "missing_object_relationship" in codes


def test_catalog_only_or_primary_receipt_relabeling_cannot_close_library() -> None:
    payload=_positive()
    payload["object_universe"]["evaluated_object_ids"]=["case:c1"]
    payload["native_owner_id"]="researchguard.trace.storyline-depth"
    receipt=evaluate_library_execution_package(payload)
    codes={item["code"] for item in receipt["errors"]}
    assert "wrong_native_owner" in codes
    assert "object_universe_not_reconciled" in codes


def test_fixture_and_scheduled_production_domains_are_not_aliases() -> None:
    payload=_positive()
    payload["evidence_domain"]="fixture_as_production"
    receipt=evaluate_library_execution_package(payload)
    assert receipt["status"]=="blocked"
    assert "invalid_evidence_domain" in {item["code"] for item in receipt["errors"]}


def _scheduled_identity() -> dict:
    return {
        "scheduler_or_trigger_id":"trigger:traceguard:case-library:nightly",
        "scheduled_execution_id":"execution:traceguard:case-library:2026-07-14",
        "installation_receipt_id":"install:traceguard:case-library:current",
        "installation_receipt_hash":"1"*64,
        "installation_receipt_root_ref":{"path_token":"active_skill_root","relative_path":".skillguard/installation-receipt.json"},
        "installed_runtime_fingerprint":"2"*64,
    }


def test_capability_and_scheduled_production_evidence_are_typed_and_disjoint(tmp_path: Path) -> None:
    capability=_positive()
    capability["evidence_domain"]="capability_validation"
    assert evaluate_library_execution_package(capability)["status"]=="pass"

    relabeled=copy.deepcopy(capability)
    relabeled["evidence_domain"]="scheduled_production"
    blocked=evaluate_library_execution_package(relabeled)
    assert "missing_scheduled_production_identity" in {item["code"] for item in blocked["errors"]}

    production=copy.deepcopy(relabeled)
    production["scheduled_production_identity"]=_scheduled_identity()
    result=evaluate_library_execution_package(production)
    assert result["status"]=="blocked"
    assert "fixture_as_production" in {item["code"] for item in result["errors"]}

    _copy_production_library(tmp_path)
    production=build_library_scheduled_production_package(
        target_root=tmp_path,
        library_relative="library",
        scheduled_production_identity=_scheduled_identity(),
        run_id="run:traceguard:case-library:scheduled-production",
    )
    result=evaluate_library_execution_package(production)
    assert result["status"]=="pass",result["errors"]
    identity = result["scheduled_production_identity"]
    expected = _scheduled_identity()
    assert identity["scheduler_or_trigger_id"] == expected["scheduler_or_trigger_id"]
    assert identity["scheduled_execution_id"] == expected["scheduled_execution_id"]
    assert len(identity["target_root_fingerprint"]) == 64
    assert len(identity["runtime_fingerprint"]) == 64

    fixture_with_production_identity=_positive()
    fixture_with_production_identity["scheduled_production_identity"]=_scheduled_identity()
    blocked=evaluate_library_execution_package(fixture_with_production_identity)
    assert "scheduled_identity_on_nonproduction_evidence" in {item["code"] for item in blocked["errors"]}


def test_stale_artifact_and_overlapping_native_range_fail_closed() -> None:
    payload=copy.deepcopy(_positive())
    payload["native_artifacts"][0]["status"]="stale"
    payload["obligation_results"][1]["native_range"]={**payload["obligation_results"][0]["native_range"],"range_id":"renamed:same-span"}
    receipt=evaluate_library_execution_package(payload)
    codes={item["code"] for item in receipt["errors"]}
    assert "evidence_not_current" in codes
    assert "missing_or_overlapping_range" in codes


def test_native_range_cannot_relabel_an_unrelated_evidence_ref_or_hash() -> None:
    payload=_positive()
    payload["obligation_results"][0]["native_range"]["source_ref"]="evidence/unrelated.json"
    payload["obligation_results"][1]["native_range"]["content_sha256"]="f"*64
    receipt=evaluate_library_execution_package(payload)
    codes={item["code"] for item in receipt["errors"]}
    assert "native_range_evidence_ref_mismatch" in codes
    assert "native_range_content_hash_mismatch" in codes


def test_important_object_inventory_cannot_be_emptied_or_reclassified() -> None:
    payload = _positive()
    payload["object_universe"]["important_object_ids"] = []
    receipt = evaluate_library_execution_package(payload)
    assert receipt["status"] == "blocked"
    assert "empty_important_object_universe" in {item["code"] for item in receipt["errors"]}

    payload = _positive()
    payload["object_results"][0]["importance"] = "ordinary"
    receipt = evaluate_library_execution_package(payload)
    assert receipt["status"] == "blocked"
    assert "object_importance_mismatch" in {item["code"] for item in receipt["errors"]}


def test_important_library_object_cannot_escape_through_exclusion() -> None:
    payload = _positive()
    object_id = "source:s1"
    payload["object_universe"]["evaluated_object_ids"].remove(object_id)
    payload["object_universe"]["excluded_objects"] = [
        {
            "object_id": object_id,
            "status": "current",
            "evidence_ref": "evidence/source-s1-exclusion.json",
            "evidence_sha256": "f" * 64,
            "reason": "The source is proven duplicate and contributes no distinct case evidence.",
            "closed_disposition": "closed_noncontributing",
            "claim_contribution": "none",
        }
    ]
    payload["object_results"] = [row for row in payload["object_results"] if row["object_id"] != object_id]
    receipt = evaluate_library_execution_package(payload)
    codes = {item["code"] for item in receipt["errors"]}
    assert receipt["status"] == "blocked"
    assert "required_object_excluded" in codes
    assert "important_object_excluded" in codes


def test_ordinary_exclusion_requires_and_preserves_a_specific_reason() -> None:
    payload = _positive()
    object_id = "gap:g1"
    payload["object_universe"]["important_object_ids"].remove(object_id)
    payload["object_universe"]["evaluated_object_ids"].remove(object_id)
    payload["object_universe"]["excluded_objects"] = [
        {
            "object_id": object_id,
            "status": "current",
            "evidence_ref": "evidence/gap-g1-exclusion.json",
            "evidence_sha256": "f" * 64,
            "closed_disposition": "closed_not_applicable",
            "claim_contribution": "none",
        }
    ]
    payload["object_results"] = [
        row for row in payload["object_results"] if row["object_id"] != object_id
    ]

    blocked = evaluate_library_execution_package(payload)
    assert "missing_or_generic_exclusion_reason" in {
        item["code"] for item in blocked["errors"]
    }

    reason = "This selected case has no unresolved gap for the bounded operation."
    payload["object_universe"]["excluded_objects"][0]["reason"] = reason
    passed = evaluate_library_execution_package(payload)
    assert passed["status"] == "pass", passed["errors"]
    assert passed["object_universe"]["exclusions"][0] == {
        "object_id": object_id,
        "reason": reason,
        "closed_disposition": "closed_not_applicable",
        "claim_contribution": "none",
        "evidence_ref": "evidence/gap-g1-exclusion.json",
        "evidence_sha256": "f" * 64,
    }


def test_object_kind_relabel_cannot_reduce_required_relationships() -> None:
    payload = _positive()
    trace_row = next(
        row for row in payload["object_results"] if row["object_id"] == "trace:t1"
    )
    trace_row["object_kind"] = "gap"
    trace_row["relationship_results"] = [
        {
            "relationship_id": relationship_id,
            "status": "complete",
            "evidence_ref": f"evidence/trace:t1/{relationship_id}.json",
            "evidence_sha256": "b" * 64,
        }
        for relationship_id in OBJECT_RELATIONSHIPS["gap"]
    ]

    receipt = evaluate_library_execution_package(payload)
    codes = {item["code"] for item in receipt["errors"]}

    assert receipt["status"] == "blocked"
    assert "object_kind_mismatch" in codes
    assert "missing_object_relationship" in codes
