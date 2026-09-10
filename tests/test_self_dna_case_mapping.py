from __future__ import annotations

import json
import hashlib
from pathlib import Path

from scripts.build_self_dna_case_mapping import (
    _declared_cases,
    _load_model,
    _strict_native_contracts,
    build_mapping,
    verify_strict_execution,
    verify_strict_parent_execution,
)


ROOT = Path(__file__).resolve().parents[1]


def _declared_rows() -> list[dict[str, object]]:
    # Use every registered parent/child case; this fixture never replaces the
    # real runner in production.
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


def _native_fixture(tmp_path: Path) -> tuple[
    dict[str, object],
    list[tuple[str, str, str]],
    dict[str, Path],
]:
    """Create producer-shaped current native envelopes for every owner.

    The rows are built through FlowGuard's typed protocol and each raw result
    is written before its byte fingerprint is recorded.  This keeps the test
    focused on the adapter's contract rather than on the old caller-owned
    receipt test doubles.
    """

    from flowguard.native_case_protocol import (
        NATIVE_CASE_RESULT_SCHEMA,
        NativeModelCaseResult,
        fingerprint_payload,
    )

    model = _load_model(ROOT)
    declared = _declared_cases(ROOT, model)
    contracts = _strict_native_contracts(ROOT, model, declared)
    paths: dict[str, Path] = {}
    for owner, owner_contracts in contracts.items():
        owner_dir = tmp_path / owner
        owner_dir.mkdir(parents=True)
        rows = []
        for index, contract in enumerate(owner_contracts):
            raw = owner_dir / f"raw-{index}.json"
            raw.write_text(
                json.dumps(
                    {
                        "owner_id": contract.owner_id,
                        "source_case_id": contract.source_case_id,
                        "case_kind": contract.case_kind,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            raw_fingerprint = "sha256:" + hashlib.sha256(raw.read_bytes()).hexdigest()
            observed_status = (
                contract.expected_observed_status or contract.expected_status
            )
            rows.append(
                NativeModelCaseResult(
                    owner_id=contract.owner_id,
                    source_case_id=contract.source_case_id,
                    outcome=contract.expected_status,
                    observed_status=observed_status,
                    observed_finding_codes=contract.expected_finding_codes,
                    executed_dimensions=contract.covered_dimensions,
                    oracle_results=tuple(
                        {
                            "dimension": dimension,
                            "oracle_member_id": contract.oracle_member_ids[0],
                            "status": observed_status,
                            "ok": contract.expected_status == "pass",
                        }
                        for dimension in contract.covered_dimensions
                    ),
                    result_artifact_fingerprint=raw_fingerprint,
                    input_fingerprint=fingerprint_payload(
                        {"owner": owner, "case": contract.source_case_id, "kind": "input"}
                    ),
                    model_fingerprint=fingerprint_payload(
                        {"owner": owner, "case": contract.source_case_id, "kind": "model"}
                    ),
                    code_fingerprint=fingerprint_payload(
                        {"owner": owner, "case": contract.source_case_id, "kind": "code"}
                    ),
                    test_fingerprint=fingerprint_payload(
                        {"owner": owner, "case": contract.source_case_id, "kind": "test"}
                    ),
                    oracle_fingerprint=fingerprint_payload(
                        {"owner": owner, "case": contract.source_case_id, "kind": "oracle"}
                    ),
                    toolchain_fingerprint=fingerprint_payload(
                        {"owner": owner, "case": contract.source_case_id, "kind": "toolchain"}
                    ),
                    environment_fingerprint=fingerprint_payload(
                        {"owner": owner, "case": contract.source_case_id, "kind": "environment"}
                    ),
                    raw_artifact_path=raw.name,
                ).to_dict()
            )
        envelope = owner_dir / "native-case-results.json"
        envelope.write_text(
            json.dumps(
                {"schema_version": NATIVE_CASE_RESULT_SCHEMA, "results": rows},
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        paths[owner] = envelope
    children = sorted(
        {owner for owner, _parent, _case in declared if owner != "researchguard_suite"}
    )
    payload: dict[str, object] = {
        "status": "pass",
        "ok": True,
        "exit_code": 0,
        "terminal": True,
        "cleanup_confirmed": True,
        "child_receipt_ids": children,
        "source_revision": "source:current",
    }
    return payload, declared, paths


def test_strict_execution_accepts_current_native_envelopes(tmp_path: Path) -> None:
    payload, declared, paths = _native_fixture(tmp_path)
    result = verify_strict_execution(
        payload,
        declared,
        expected_source_revision="source:current",
        root=ROOT,
        native_result_paths=paths,
    )
    assert result["strict_self_dna_status"] == "pass"
    assert result["gaps"] == []
    assert result["verified_native_case_count"] == 63
    assert all(item["ok"] for item in result["native_verification"].values())


def test_strict_execution_rejects_tampered_raw_artifact_and_status_flip(
    tmp_path: Path,
) -> None:
    payload, declared, paths = _native_fixture(tmp_path)
    owner = "researchguard_suite"
    envelope = paths[owner]
    raw_path = envelope.parent / "raw-0.json"
    raw_path.write_text(raw_path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    payload["status"] = "failed"
    result = verify_strict_execution(
        payload,
        declared,
        expected_source_revision="source:current",
        root=ROOT,
        native_result_paths=paths,
    )
    assert result["strict_self_dna_status"] == "blocked"
    assert "top_level_status_not_pass" in result["gaps"]
    assert any(
        gap.startswith("native:researchguard_suite:")
        and "raw_artifact_fingerprint_mismatch" in gap
        for gap in result["gaps"]
    )


def test_strict_execution_rejects_legacy_self_hash_rows() -> None:
    model = _load_model(ROOT)
    declared = _declared_cases(ROOT, model)
    payload = {
        "status": "pass",
        "ok": True,
        "exit_code": 0,
        "terminal": True,
        "cleanup_confirmed": True,
        "source_revision": "source:current",
        "child_receipt_ids": list(model.CHILD_MODEL_IDS),
        "results": [{
            "owner_id": "model:researchguard_suite",
            "source_case_id": declared[0][2],
            "model_instance_fingerprint": "sha256:" + "0" * 64,
            "receipt_fingerprint": "sha256:" + "1" * 64,
            "observed_status": "pass",
        }],
    }
    result = verify_strict_execution(
        payload,
        declared,
        expected_source_revision="source:current",
        root=ROOT,
    )
    assert result["strict_self_dna_status"] == "blocked"
    assert "native_result_schema_invalid:inline:0" in result["gaps"]
    assert "native_raw_artifact_root_missing" in result["gaps"]


def test_strict_parent_adapter_requires_official_current_receipt_store() -> None:
    from flowguard.native_case_protocol import fingerprint_payload

    children = [{
        "model_id": "child_a",
        "receipt_id": "receipt:fake-child",
        "receipt_fingerprint": fingerprint_payload({"receipt": "fake-child"}),
    }]
    parent = {
        "status": "pass",
        "execution_receipt_id": "receipt:fake-parent",
        "execution_receipt_fingerprint": fingerprint_payload({"receipt": "fake-parent"}),
    }
    result = verify_strict_parent_execution(parent, children, ["child_a"])
    assert result["strict_self_dna_status"] == "blocked"
    assert "official_current_receipt_store_required" in result["gaps"]


def test_strict_parent_adapter_rejects_missing_child_and_forged_parent() -> None:
    result = verify_strict_parent_execution(
        {"result_status": "failed", "exit_code": 1}, [], ["child_a"]
    )
    assert result["strict_self_dna_status"] == "blocked"
    assert "child_model_closure_mismatch" in result["gaps"]
    assert "parent_result_status_not_pass" in result["gaps"]
