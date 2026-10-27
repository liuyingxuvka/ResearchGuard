from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import pytest
from researchguard.trace.inference.osqp_backend import solve_problem
from researchguard.trace.inference.policy import DEFAULT_POLICY
from researchguard.trace.inference.types import (
    CompiledProblem,
    HardConstraint,
    HingeFactor,
    LatentAtom,
    LinearExpression,
    ObservedAtom,
    SolverError,
)
from researchguard.trace.evaluator import evaluate_model
from researchguard.trace.schema import SchemaError, TraceGuardModel
from researchguard.trace.loader import load_model


EVERGIVEN = Path(__file__).parent / "fixtures" / "evergiven"


def _storyline_projections(model):
    return {row.hypothesis_id: row for row in evaluate_model(model).inference.hypothesis_projections}


def test_live_hypotheses_lie_within_the_margin_of_the_best() -> None:
    from researchguard.trace.inference.policy import InferencePolicy

    margin = InferencePolicy().alternative_live_margin
    for name in ("tr_v2b", "tr_v1"):
        rows = list(_storyline_projections(load_model(EVERGIVEN / f"{name}.yaml")).values())
        best = max(row.support for row in rows)
        for row in rows:
            assert row.live == (best - row.support <= margin)
        ordered = sorted(rows, key=lambda row: row.rank)
        assert [row.hypothesis_id for row in ordered] == [row.hypothesis_id for row in sorted(rows, key=lambda row: (-row.support, row.hypothesis_id))]


def test_better_supported_alternative_ranks_first() -> None:
    rows = _storyline_projections(load_model(EVERGIVEN / "tr_v2b.yaml"))
    assert rows["h_demand"].rank == 1


def test_causal_declaration_never_raises_storyline_support() -> None:
    for name in ("tr_v1", "tr_varB"):
        model = load_model(EVERGIVEN / f"{name}.yaml")
        plain = load_model(EVERGIVEN / "tr_varA.yaml") if name == "tr_v1" else replace(model, causal_candidates=())
        actual = _storyline_projections(model)
        expected = _storyline_projections(plain)
        assert actual.keys() == expected.keys()
        for hypothesis_id, row in actual.items():
            assert abs(row.support - expected[hypothesis_id].support) <= 0.001
            if row.causal_support is not None:
                assert row.causal_support <= row.support + 0.000001


def test_opposition_lowers_support() -> None:
    opposed = _storyline_projections(load_model(EVERGIVEN / "tr_v2b.yaml"))
    unopposed = _storyline_projections(load_model(EVERGIVEN / "tr_v2c_nooppose.yaml"))
    assert opposed["h_suez"].support <= unopposed["h_suez"].support - 0.01


