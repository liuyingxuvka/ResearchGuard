from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from researchguard.logic import (
    GuardModelContractError,
    bind_target_candidate,
    build_logic_depth_receipt,
    freeze_target_contract,
    load_model,
    verify_target_contract,
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _model(model_id: str = "current-model") -> dict:
    return {
        "model": {
            "id": model_id,
            "root_claim": "C0",
            "target_units": [
                {
                    "unit_id": "unit:central-argument",
                    "node_ids": ["C0", "E1", "W1", "A1", "L1", "R1"],
                }
            ],
            "model_cards": [
                {
                    "card_id": "card:central-argument",
                    "node_ids": ["C0", "E1", "W1", "A1", "L1", "R1"],
                    "importance": 1.0,
                }
            ],
            "role_dispositions": {"competition": "not_applicable"},
        },
        "nodes": {
            "C0": {"type": "Claim", "text": "Bounded conclusion", "importance": 1.0},
            "E1": {"type": "Evidence", "provided": True, "confidence": 0.9, "importance": 0.8},
            "W1": {"type": "Warrant", "confidence": 0.8, "importance": 0.8},
            "A1": {"type": "Assumption", "confidence": 0.8, "importance": 0.7},
            "L1": {"type": "Limitation", "confidence": 0.8, "importance": 0.7},
            "R1": {"type": "Rebuttal", "active": False, "confidence": 0.8, "importance": 0.7},
        },
        "edges": [
            {"source": "E1", "target": "C0", "type": "supports"},
            {"source": "W1", "target": "C0", "type": "supports"},
            {"source": "A1", "target": "C0", "type": "depends_on"},
            {"source": "L1", "target": "C0", "type": "qualifies"},
            {"source": "R1", "target": "C0", "type": "attacks"},
        ],
    }


def _bad_missing(model: dict, node_id: str) -> dict:
    value = deepcopy(model)
    value["nodes"].pop(node_id)
    value["edges"] = [
        row
        for row in value["edges"]
        if row["source"] != node_id and row["target"] != node_id
    ]
    for collection in ("target_units", "model_cards"):
        for row in value["model"][collection]:
            row["node_ids"] = [item for item in row["node_ids"] if item != node_id]
    return value


def _declaration(*, failures: list[dict], candidate: str = "models/current.json") -> dict:
    return {
        "schema_version": "researchguard.logic.target_model_purpose_declaration.v1",
        "contract_role": "target_model_instance",
        "contract_id": "contract:current-model:purpose",
        "model_id": "current-model",
        "target_skill_id": "logicguard",
        "native_owner_id": "researchguard.logic.execution_depth",
        "native_route_id": "route:logicguard-authoritative-depth",
        "declared_by": "ai",
        "prevented_failure_purpose": "Prevent this model from licensing a conclusion with a missing declared support role.",
        "claim_boundary": "This proof covers only the current model and its declared support-role failures.",
        "candidate_relative_path": candidate,
        "selectable_modes": [],
        "prevented_failure_classes": failures,
    }


def _failure(failure_id: str, code: str, good: str, bad: str) -> dict:
    return {
        "failure_id": failure_id,
        "title": f"Block {failure_id}",
        "block_when": f"the current model exposes {code}",
        "oracle": {"kind": "primary_depth_gap_prefix", "finding_code": code},
        "known_good_relative_path": good,
        "known_bad_relative_path": bad,
    }


def _prepare(tmp_path: Path, *, multiple: bool = False, bad_actually_blocks: bool = True) -> tuple[Path, Path]:
    good = _model()
    _write(tmp_path / ".logicguard/cases/good.json", good)
    support_bad = _bad_missing(good, "E1") if bad_actually_blocks else good
    _write(tmp_path / ".logicguard/cases/bad-support.json", support_bad)
    failures = [
        _failure(
            "failure:current:missing-support",
            "missing_role:card:central-argument:support",
            ".logicguard/cases/good.json",
            ".logicguard/cases/bad-support.json",
        )
    ]
    if multiple:
        _write(tmp_path / ".logicguard/cases/bad-warrant.json", _bad_missing(good, "W1"))
        failures.append(
            _failure(
                "failure:current:missing-warrant",
                "missing_role:card:central-argument:warrant",
                ".logicguard/cases/good.json",
                ".logicguard/cases/bad-warrant.json",
            )
        )
    declaration = tmp_path / ".logicguard/purpose-declaration.json"
    contract = tmp_path / ".logicguard/guard-purpose-contract.json"
    _write(declaration, _declaration(failures=failures))
    freeze_target_contract(
        target_root=tmp_path,
        declaration_path=declaration,
        output_path=contract,
    )
    _write(tmp_path / "models/current.json", good)
    bind_target_candidate(target_root=tmp_path, contract_path=contract)
    return contract, tmp_path / "models/current.json"


@pytest.mark.parametrize("multiple", [False, True])
def test_dynamic_contract_exhausts_one_or_many_current_failures(
    tmp_path: Path, multiple: bool
) -> None:
    contract, candidate = _prepare(tmp_path, multiple=multiple)
    proof = verify_target_contract(target_root=tmp_path, contract_path=contract)
    assert proof["status"] == "pass"
    assert proof["proofed_failure_count"] == (2 if multiple else 1)
    assert proof["selectable_modes"] == []

    receipt = build_logic_depth_receipt(
        load_model(candidate),
        target_root=tmp_path,
        guard_contract=contract,
        budget=8,
    )
    assert receipt.receipt_version == "researchguard.logic.depth.v3"
    assert receipt.target_contract_fingerprint == proof["contract_fingerprint"]
    assert receipt.target_proof_receipt["proofed_failure_count"] == proof["proofed_failure_count"]


def test_bad_case_that_does_not_block_keeps_target_closed(tmp_path: Path) -> None:
    contract, _candidate = _prepare(tmp_path, bad_actually_blocks=False)
    with pytest.raises(GuardModelContractError, match="known-bad-did-not-block"):
        verify_target_contract(target_root=tmp_path, contract_path=contract)


def test_purpose_change_stales_candidate_binding(tmp_path: Path) -> None:
    contract, _candidate = _prepare(tmp_path)
    value = json.loads(contract.read_text(encoding="utf-8"))
    value["prevented_failure_purpose"] = "Changed target purpose"
    unsigned = dict(value)
    unsigned.pop("contract_fingerprint")
    value["contract_fingerprint"] = hashlib.sha256(
        (json.dumps(unsigned, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    ).hexdigest().upper()
    _write(contract, value)
    with pytest.raises(GuardModelContractError, match="candidate-contract-fingerprint-stale"):
        verify_target_contract(target_root=tmp_path, contract_path=contract)


def test_case_content_change_stales_frozen_contract(tmp_path: Path) -> None:
    contract, _candidate = _prepare(tmp_path)
    good_path = tmp_path / ".logicguard/cases/good.json"
    good = json.loads(good_path.read_text(encoding="utf-8"))
    good["nodes"]["E1"]["text"] = "Changed after freeze"
    _write(good_path, good)
    with pytest.raises(GuardModelContractError, match="target-proof-case-stale"):
        verify_target_contract(target_root=tmp_path, contract_path=contract)


def test_candidate_content_change_stales_bound_model_and_receipt(tmp_path: Path) -> None:
    contract, candidate = _prepare(tmp_path)
    proof = verify_target_contract(target_root=tmp_path, contract_path=contract)
    value = json.loads(candidate.read_text(encoding="utf-8"))
    value["nodes"]["E1"]["text"] = "Changed after binding"
    _write(candidate, value)
    with pytest.raises(GuardModelContractError, match="candidate-contract-fingerprint-stale"):
        verify_target_contract(target_root=tmp_path, contract_path=contract)
    assert proof["candidate_model_fingerprint"] != ""


def test_foreign_target_identity_is_rejected(tmp_path: Path) -> None:
    contract, _candidate = _prepare(tmp_path)
    with pytest.raises(GuardModelContractError, match="foreign-target-identity"):
        verify_target_contract(
            target_root=tmp_path,
            contract_path=contract,
            expected_target_skill_id="sourceguard",
        )


def test_freeze_rejects_candidate_that_already_exists(tmp_path: Path) -> None:
    _write(tmp_path / ".logicguard/cases/good.json", _model())
    _write(tmp_path / ".logicguard/cases/bad.json", _bad_missing(_model(), "E1"))
    _write(tmp_path / "models/current.json", _model())
    declaration = _declaration(
        failures=[
            _failure(
                "failure:current:missing-support",
                "missing_role:card:central-argument:support",
                ".logicguard/cases/good.json",
                ".logicguard/cases/bad.json",
            )
        ]
    )
    _write(tmp_path / ".logicguard/declaration.json", declaration)
    with pytest.raises(GuardModelContractError, match="purpose-not-frozen-before-candidate"):
        freeze_target_contract(
            target_root=tmp_path,
            declaration_path=".logicguard/declaration.json",
            output_path=".logicguard/guard-purpose-contract.json",
        )


def test_target_paths_cannot_escape_and_baseline_cannot_substitute(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.json"
    _write(outside, _model())
    _write(tmp_path / ".logicguard/cases/bad.json", _bad_missing(_model(), "E1"))
    declaration = _declaration(
        failures=[
            _failure(
                "failure:current:missing-support",
                "missing_role:card:central-argument:support",
                f"../{outside.name}",
                ".logicguard/cases/bad.json",
            )
        ]
    )
    _write(tmp_path / ".logicguard/declaration.json", declaration)
    with pytest.raises(GuardModelContractError, match="target-path-escape"):
        freeze_target_contract(
            target_root=tmp_path,
            declaration_path=".logicguard/declaration.json",
            output_path=".logicguard/guard-purpose-contract.json",
        )

    _write(
        tmp_path / "baseline-contract.json",
        {
            "schema_version": "researchguard.logic.guard_baseline_contract.v1",
            "contract_role": "family_baseline_regression",
        },
    )
    with pytest.raises(GuardModelContractError, match="wrong-contract-role"):
        verify_target_contract(
            target_root=tmp_path, contract_path="baseline-contract.json"
        )


def test_public_depth_requires_explicit_target_authority(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        build_logic_depth_receipt(load_model_from_data(_model()))


def load_model_from_data(value: dict):
    from researchguard.logic import load_model_from_dict

    return load_model_from_dict(value)
