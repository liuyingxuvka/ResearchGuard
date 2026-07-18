"""
Purpose: Load, validate, serialize, and write SourceGuard YAML belief-state models.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source validate <model.yaml> --model-contract <model.contract.json>
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .guard_contract import load_target_contract, prove_target_model_contract
from .schema import (
    BeliefState,
    SchemaError,
    sourceguard_model_contract_fingerprint,
    to_plain,
)


def load_model(path: str | Path, model_contract_path: str | Path) -> BeliefState:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if data is None:
        data = {}
    belief_state = BeliefState.from_dict(data)
    external_contract = load_target_contract(model_contract_path)
    if belief_state.guard_contract is None:
        raise SchemaError("candidate is missing its target contract snapshot")
    if external_contract.to_dict() != belief_state.guard_contract.to_dict():
        raise SchemaError("explicit model contract does not match the candidate snapshot")
    if belief_state.candidate_contract_fingerprint != sourceguard_model_contract_fingerprint(
        external_contract
    ):
        raise SchemaError("explicit model contract fingerprint does not match the candidate")
    prove_target_model_contract(belief_state, model_contract_path)
    return belief_state


def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(to_plain(data), sort_keys=False, allow_unicode=True)


def write_yaml(path: str | Path, data: Any) -> None:
    Path(path).write_text(dump_yaml(data), encoding="utf-8")


def model_to_dict(belief_state: BeliefState) -> dict[str, Any]:
    return to_plain(belief_state)


def validate_model(path: str | Path, model_contract_path: str | Path) -> dict[str, Any]:
    belief_state = load_model(path, model_contract_path)
    return {
        "ok": True,
        "path": str(path),
        "model_contract_path": str(model_contract_path),
        "lead_count": len(belief_state.leads),
        "source_count": len(belief_state.sources),
        "anchor_count": len(belief_state.anchors),
        "gap_count": len(belief_state.gaps),
        "action_count": len(belief_state.actions),
        "boundary": belief_state.metadata.get(
            "math_boundary",
            "Expected utility ranks search value, not factual truth or calibrated probability.",
        ),
    }
