from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from researchguard.software_dna import (
    BCL_CONNECTION_SCHEMA,
    build_researchguard_behavior_commitment_candidate,
    check_software_dna_contract,
    load_canonical_behavior_commitment_ledger,
    qualify_researchguard_behavior_commitment_ledger,
    software_dna_affected_closure,
    software_dna_reverse_trace,
)


def _candidate() -> dict[str, object]:
    result = build_researchguard_behavior_commitment_candidate(".")
    assert result["status"] == "candidate"
    return result


def test_bcl_candidate_preserves_separate_17_model_and_10_native_owner_boundaries() -> None:
    result = _candidate()

    assert result["ready"] is False
    assert result["counts"] == {
        "models": 17,
        "function_blocks": 20,
        "native_owner_count": 10,
        "commitments": 20,
        "source_surfaces": 60,
    }
    assert result["gaps"][0]["code"] == "current_native_evidence_missing"  # type: ignore[index]
    assert result["ledger"]["artifact_type"] == "flowguard_behavior_commitment_ledger"  # type: ignore[index]


def test_bcl_round_trip_requires_the_official_current_envelope(tmp_path: Path) -> None:
    result = _candidate()
    envelope = result["ledger"]
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(envelope), encoding="utf-8")

    ledger = load_canonical_behavior_commitment_ledger(path)
    assert ledger.ledger_id == "researchguard-software-dna-bcl-candidate"
    assert len(ledger.commitments) == 20

    bare = dict(envelope["ledger"])  # type: ignore[index]
    with pytest.raises(ValueError, match="canonical envelope|bare"):
        load_canonical_behavior_commitment_ledger(bare)

    wrong_schema = copy.deepcopy(envelope)
    wrong_schema["schema_version"] = "0.1"
    with pytest.raises(ValueError, match="schema"):
        load_canonical_behavior_commitment_ledger(wrong_schema)

    missing_payload = {key: value for key, value in envelope.items() if key != "ledger"}
    with pytest.raises(ValueError, match="canonical envelope|ledger"):
        load_canonical_behavior_commitment_ledger(missing_payload)


def test_bcl_connection_keeps_current_native_evidence_as_an_explicit_blocker() -> None:
    result = _candidate()
    qualification = qualify_researchguard_behavior_commitment_ledger(".", result["ledger"])

    assert qualification["schema_version"] == BCL_CONNECTION_SCHEMA
    assert qualification["ready"] is False
    codes = {gap["code"] for gap in qualification["gaps"]}
    assert "behavior_commitment_evidence_missing" in codes
    assert qualification["indexes"] == {}


def test_bcl_source_tamper_is_not_hidden_by_a_recomputed_ledger_envelope() -> None:
    result = _candidate()
    envelope = copy.deepcopy(result["ledger"])
    envelope["ledger"]["source_surfaces"][0]["content_fingerprint"] = "sha256:tampered"  # type: ignore[index]

    qualification = qualify_researchguard_behavior_commitment_ledger(".", envelope)
    codes = {gap["code"] for gap in qualification["gaps"]}
    assert "behavior_commitment_source_tampered" in codes


def test_bcl_rejects_foreign_owner_and_foreign_native_evidence_path() -> None:
    result = _candidate()
    envelope = copy.deepcopy(result["ledger"])
    first = envelope["ledger"]["commitments"][0]  # type: ignore[index]
    obligation_id = first["evidence"]["model_obligation_ids"][0]
    first["evidence"]["metadata"]["native_evidence"] = [
        {
            "obligation_id": obligation_id,
            "native_owner_id": "foreign-owner",
            "model_owner_id": first["primary_owner_model_id"],
            "current": True,
            "status": "current_pass",
            "path": "../outside/receipt.json",
            "fingerprint": "sha256:foreign",
        }
    ]

    qualification = qualify_researchguard_behavior_commitment_ledger(".", envelope)
    codes = {gap["code"] for gap in qualification["gaps"]}
    assert "behavior_commitment_evidence_foreign_owner" in codes
    assert "behavior_commitment_evidence_foreign" in codes


def test_bcl_rejects_bare_model_owner_and_duplicate_obligation() -> None:
    result = _candidate()
    envelope = copy.deepcopy(result["ledger"])
    first = envelope["ledger"]["commitments"][0]  # type: ignore[index]
    second = envelope["ledger"]["commitments"][1]  # type: ignore[index]
    first["primary_owner_model_id"] = "logicguard"
    second["evidence"]["model_obligation_ids"] = first["evidence"]["model_obligation_ids"]

    qualification = qualify_researchguard_behavior_commitment_ledger(".", envelope)
    codes = {gap["code"] for gap in qualification["gaps"]}
    assert "behavior_commitment_owner_noncanonical" in codes
    assert "behavior_commitment_duplicate_obligation" in codes


def test_bcl_reverse_and_affected_queries_reject_a_replaced_ledger() -> None:
    base = check_software_dna_contract(".")["indexes"]
    connected = copy.deepcopy(base)
    connected["behavior_commitment_ledger"] = {"status": "ready", "fingerprint": "sha256:current"}

    closure = software_dna_affected_closure(
        connected,
        ["code:src/researchguard/self_dna.py#check"],
        expected_bcl_fingerprint="sha256:replaced",
    )
    trace = software_dna_reverse_trace(
        connected,
        "code:src/researchguard/self_dna.py#check",
        expected_bcl_fingerprint="sha256:replaced",
    )
    assert closure["status"] == "blocked"
    assert closure["gap"]["code"] == "behavior_ledger_replaced"
    assert trace["status"] == "blocked"
    assert trace["gap"]["code"] == "behavior_ledger_replaced"
