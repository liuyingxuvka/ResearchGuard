"""
Purpose: Load, validate, serialize, and write SourceGuard YAML belief-state models.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source validate <model.yaml>
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .schema import BeliefState, to_plain, to_plain_without_defaults

def load_model(path: str | Path) -> BeliefState:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if data is None:
        data = {}
    return BeliefState.from_dict(data)

def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(to_plain_without_defaults(data), sort_keys=False, allow_unicode=True)


def write_yaml(path: str | Path, data: Any) -> None:
    Path(path).write_text(dump_yaml(data), encoding="utf-8")


def model_to_dict(belief_state: BeliefState) -> dict[str, Any]:
    return to_plain(belief_state)


def validate_model(path: str | Path) -> dict[str, Any]:
    belief_state = load_model(path)
    example_ids = sorted({
        getattr(row, id_field)
        for collection, id_field in (
            (belief_state.leads, "lead_id"), (belief_state.sources, "source_id"),
            (belief_state.anchors, "anchor_id"), (belief_state.gaps, "gap_id"),
            (belief_state.actions, "action_id"), (belief_state.observations, "observation_id"),
        )
        for row in collection
        if getattr(row, id_field).startswith("example-")
    })
    return {
        "ok": True,
        "path": str(path),
        "warnings": ["starter example rows still present: " + ", ".join(example_ids)] if example_ids else [],
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
