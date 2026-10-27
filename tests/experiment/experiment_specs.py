from __future__ import annotations
import json
import pytest
from researchguard.experiment import (
    ExperimentObservation,
    ExperimentSpec,
    HypothesisPrediction,
    observe_experiments,
    recommend_experiments,
)


def _spec(**overrides) -> ExperimentSpec:
    values = {
        "task_id": "experiment-task-1",
        "purpose": "distinguish the two declared mechanisms",
        "coverage_ids": ("h1", "h2", "e1", "e2"),
        "assumptions": (),
        "unknowns": (),
        "iteration": 0,
        "max_iterations": 4,
        "hypothesis_predictions": (
            HypothesisPrediction("h1", {"e1": "up", "e2": "hot"}),
            HypothesisPrediction("h2", {"e1": "down", "e2": "cold"}),
        ),
        "candidate_experiment_ids": ("e2", "e1"),
    }
    values.update(overrides)
    return ExperimentSpec(**values)


def _observation(
    experiment_id: str,
    outcome: str,
    *,
    role: str,
    suffix: str,
    status: str = "valid",
) -> ExperimentObservation:
    return ExperimentObservation(
        experiment_id=experiment_id,
        observed_outcome=outcome,
        evidence_id=f"evidence:{suffix}",
        source_ref=f"source:{suffix}",
        observed_at="2026-07-31T12:00:00+00:00",
        role=role,
        status=status,
    )


def _evergiven_spec(**overrides) -> ExperimentSpec:
    """Declared trial matrix from the packet, not independently verified facts."""
    values = {
        "hypothesis_predictions": (
            HypothesisPrediction("h_suez", {
                "e_transpacific": "ae_rise_much_larger", "e_reversion": "reverts_by_may",
                "e_yantian_timing": "no_jump"}),
            HypothesisPrediction("h_demand", {
                "e_transpacific": "similar_rise", "e_reversion": "keeps_rising",
                "e_yantian_timing": "no_jump"}),
            HypothesisPrediction("h_yantian", {
                "e_transpacific": "similar_rise", "e_reversion": "keeps_rising",
                "e_yantian_timing": "jump_in_june"}),
        ),
        "candidate_experiment_ids": ("e_transpacific", "e_reversion", "e_yantian_timing"),
        "coverage_ids": ("h_suez", "h_demand", "h_yantian", "e_transpacific", "e_reversion", "e_yantian_timing"),
    }
    values.update(overrides)
    return _spec(**values)


