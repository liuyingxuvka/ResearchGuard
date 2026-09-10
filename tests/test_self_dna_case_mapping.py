from __future__ import annotations

import json
from pathlib import Path

from scripts.build_self_dna_case_mapping import build_mapping, verify_strict_execution, verify_strict_parent_execution


ROOT = Path(__file__).resolve().parents[1]


def _declared_rows() -> list[dict[str, object]]:
    # Use every registered parent/child case; this fixture never replaces the
    # real runner in production.
    from scripts.build_self_dna_case_mapping import _load_model, _declared_cases

    model = _load_model(ROOT)
    ids = [case_id for _owner, _parent, case_id in _declared_cases(ROOT, model)]
    return [{"source_case_id": case_id, "observed_status": "pass"} for case_id in ids]


def test_mapping_registry_reconciles_every_declared_native_case(tmp_path: Path) -> None:
    result = tmp_path / "native-case-results.json"
    result.write_text(json.dumps({"results": _declared_rows()}), encoding="utf-8")
    mapping = build_mapping(ROOT, result)
    assert mapping["status"] == "pass"
    assert len(mapping["nodes"]) == 10
    assert len(mapping["cases"]) == 63
    assert mapping["foreign_case_ids"] == []
    assert mapping["orphan_case_ids"] == []


def test_mapping_registry_blocks_foreign_and_orphan_cases(tmp_path: Path) -> None:
    result = tmp_path / "native-case-results.json"
    rows = _declared_rows()
    rows.pop()
    rows.append({"source_case_id": "foreign:case", "observed_status": "pass"})
    result.write_text(json.dumps({"results": rows}), encoding="utf-8")
    mapping = build_mapping(ROOT, result)
    assert mapping["status"] == "blocked"
    assert mapping["foreign_case_ids"] == ["foreign:case"]
    assert len(mapping["orphan_case_ids"]) == 1


def test_mapping_registry_blocks_duplicate_case_rows(tmp_path: Path) -> None:
    result = tmp_path / "native-case-results.json"
    rows = _declared_rows()
    rows.append(rows[0].copy())
    result.write_text(json.dumps({"results": rows}), encoding="utf-8")
    mapping = build_mapping(ROOT, result)
    assert mapping["status"] == "blocked"
    assert mapping["duplicate_case_ids"] == [rows[0]["source_case_id"]]


def _strict_fixture() -> tuple[dict[str, object], list[tuple[str, str, str]]]:
    from scripts.build_self_dna_case_mapping import _load_model, _declared_cases

    model = _load_model(ROOT)
    declared = _declared_cases(ROOT, model)
    rows = []
    for owner, _parent, case_id in declared:
        rows.append({
            "source_case_id": case_id,
            "owner_id": owner,
            "model_instance_id": f"regression:{owner}:current",
            "model_instance_fingerprint": f"fp-model-{owner}",
            "input_inventory_fingerprint": f"fp-input-{owner}",
            "result_fingerprint": f"fp-result-{case_id}",
            "receipt_id": f"receipt:{case_id}",
            "receipt_fingerprint": f"fp-receipt-{case_id}",
            "runner_fingerprint": f"fp-runner-{owner}",
            "observed_status": "pass",
        })
    children = sorted({owner for owner, _parent, _case in declared if owner != "researchguard_suite"})
    return {
        "status": "pass", "ok": True, "exit_code": 0, "terminal": True,
        "cleanup_confirmed": True, "results": rows,
        "child_receipt_ids": children, "source_revision": "source:current",
    }, declared


def test_strict_execution_accepts_complete_identity_envelope() -> None:
    payload, declared = _strict_fixture()
    result = verify_strict_execution(payload, declared, expected_source_revision="source:current")
    assert result["strict_self_dna_status"] == "pass"
    assert result["gaps"] == []


def test_strict_execution_rejects_status_flip_and_identity_forgery() -> None:
    payload, declared = _strict_fixture()
    row = payload["results"][0]
    row["observed_status"] = "blocked"
    row["expected_observed_status"] = "pass"
    row["owner_id"] = "wrong-owner"
    row["model_instance_fingerprint"] = ""
    payload["status"] = "failed"
    result = verify_strict_execution(payload, declared, expected_source_revision="source:current")
    assert result["strict_self_dna_status"] == "blocked"
    assert "oracle_mismatch:" + declared[0][2] in result["gaps"]
    assert "owner_mismatch:" + declared[0][2] in result["gaps"]
    assert "missing_model_instance_fingerprint:" + declared[0][2] in result["gaps"]
    assert "top_level_status_not_pass" in result["gaps"]


def test_strict_parent_adapter_accepts_native_receipt_shape() -> None:
    children = [{
        "subject_id": "validation-owner:model:child_a",
        "result_status": "pass", "exit_code": 0,
        "receipt_id": "r:child_a", "result_fingerprint": "fp:r:a",
        "proof_artifact_fingerprint": "fp:p:a", "producer_id": "p",
        "producer_version": "0.69.0",
    }]
    parent = {
        "result_status": "pass", "exit_code": 0,
        "receipt_id": "r:parent", "result_fingerprint": "fp:r:p",
        "proof_artifact_fingerprint": "fp:p:p",
        "required_child_receipts": [{"receipt_id": "r:child_a"}],
        "consumed_child_receipts": [{"receipt_id": "r:child_a"}],
    }
    result = verify_strict_parent_execution(parent, children, ["child_a"])
    assert result["strict_self_dna_status"] == "pass"


def test_strict_parent_adapter_rejects_missing_child_and_forged_parent() -> None:
    result = verify_strict_parent_execution(
        {"result_status": "failed", "exit_code": 1}, [], ["child_a"]
    )
    assert result["strict_self_dna_status"] == "blocked"
    assert "child_model_closure_mismatch" in result["gaps"]
    assert "parent_result_status_not_pass" in result["gaps"]
