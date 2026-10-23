"""Strict, current-only ExperimentGuard task and iteration-result schemas."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Literal


EXPERIMENT_SPEC_SCHEMA = "researchguard.experiment.task-spec.v3"
EXPERIMENT_ITERATION_SCHEMA = "researchguard.experiment.iteration-result.v1"


def _unique(values: tuple[str, ...], field: str, *, allow_empty: bool = True) -> None:
    if (not allow_empty and not values) or any(not item.strip() for item in values):
        raise ValueError(f"{field} requires non-empty strings")
    if len(set(values)) != len(values):
        raise ValueError(f"{field} must not contain duplicates")


@dataclass(frozen=True)
class HypothesisPrediction:
    hypothesis_id: str
    outcomes_by_experiment: dict[str, str]

    def __post_init__(self) -> None:
        if not self.hypothesis_id.strip():
            raise ValueError("hypothesis_id is required")
        if any(not str(key).strip() or not str(value).strip() for key, value in self.outcomes_by_experiment.items()):
            raise ValueError("experiment predictions require non-empty ids and outcomes")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentSpec:
    task_id: str
    purpose: str
    coverage_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    iteration: int
    max_iterations: int
    hypothesis_predictions: tuple[HypothesisPrediction, ...]
    candidate_experiment_ids: tuple[str, ...]
    maximum_experiment_count: int | None = None
    prior_open_gap_ids: tuple[str, ...] = ()
    schema_version: str = EXPERIMENT_SPEC_SCHEMA
    cost_by_experiment: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if self.schema_version != EXPERIMENT_SPEC_SCHEMA:
            raise ValueError("ExperimentGuard task spec requires the current schema")
        if not self.task_id.strip() or not self.purpose.strip():
            raise ValueError("task_id and purpose are required")
        _unique(self.coverage_ids, "coverage_ids", allow_empty=False)
        _unique(self.assumptions, "assumptions")
        _unique(self.unknowns, "unknowns")
        _unique(self.candidate_experiment_ids, "candidate_experiment_ids", allow_empty=False)
        _unique(self.prior_open_gap_ids, "prior_open_gap_ids")
        if self.iteration < 0 or self.max_iterations < 1:
            raise ValueError("iteration must be non-negative and max_iterations positive")
        hypothesis_ids = tuple(item.hypothesis_id for item in self.hypothesis_predictions)
        _unique(hypothesis_ids, "hypothesis_predictions", allow_empty=False)
        if len(hypothesis_ids) < 2:
            raise ValueError("at least two hypotheses are required")
        candidates = set(self.candidate_experiment_ids)
        for row in self.hypothesis_predictions:
            if not candidates.issubset(row.outcomes_by_experiment):
                raise ValueError("every hypothesis prediction must cover the candidate universe")
        if self.cost_by_experiment is not None:
            if not isinstance(self.cost_by_experiment, Mapping):
                raise ValueError("cost_by_experiment must be an experiment-id to cost mapping")
            if len(self.candidate_experiment_ids) > 16:
                raise ValueError("cost mode supports at most 16 candidate experiments")
            unknown = set(self.cost_by_experiment) - candidates
            if unknown:
                raise ValueError("cost_by_experiment contains unknown experiment ids: " + ", ".join(sorted(map(str, unknown))))
            for experiment_id, cost in self.cost_by_experiment.items():
                if (isinstance(cost, bool) or not isinstance(cost, (int, float))
                        or cost < 0 or (isinstance(cost, float) and not isfinite(cost))):
                    raise ValueError(f"cost for {experiment_id} must be a finite non-negative number")


    def to_dict(self) -> dict[str, object]:
        result = {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "purpose": self.purpose,
            "coverage_ids": list(self.coverage_ids),
            "assumptions": list(self.assumptions),
            "unknowns": list(self.unknowns),
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "hypothesis_predictions": [item.to_dict() for item in self.hypothesis_predictions],
            "candidate_experiment_ids": list(self.candidate_experiment_ids),
            "maximum_experiment_count": self.maximum_experiment_count,
            "prior_open_gap_ids": list(self.prior_open_gap_ids),
        }
        if self.cost_by_experiment is not None:
            result["cost_by_experiment"] = dict(self.cost_by_experiment)
        return result


@dataclass(frozen=True)
class ExperimentObservation:
    experiment_id: str
    observed_outcome: str
    evidence_id: str
    source_ref: str
    observed_at: str
    role: Literal["construction", "holdout"]
    status: Literal["valid", "invalid", "not_run"] = "valid"

    def __post_init__(self) -> None:
        required = (
            self.experiment_id,
            self.evidence_id,
            self.source_ref,
            self.observed_at,
        )
        if any(not value.strip() for value in required):
            raise ValueError("experiment observation identity fields are required")
        if self.status == "valid" and not self.observed_outcome.strip():
            raise ValueError("valid observations require observed_outcome")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class HypothesisDisposition:
    hypothesis_id: str
    status: Literal["consistent", "eliminated", "underdetermined", "model_miss"]
    matched_experiment_ids: tuple[str, ...] = ()
    contradicted_experiment_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PredictionMatrixRevisionCandidate:
    candidate_id: str
    base_matrix_fingerprint: str
    unexpected_observation_ids: tuple[str, ...]
    required_actions: tuple[str, ...]
    disposition: Literal["not_applied"] = "not_applied"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentRecommendation:
    status: Literal["recommended", "indistinguishable", "blocked_invalid_input"]
    selected_experiment_ids: tuple[str, ...]
    alternative_minimal_sets: tuple[tuple[str, ...], ...]
    unresolved_hypothesis_pairs: tuple[tuple[str, str], ...]
    reason_code: str
    claim_boundary: str = (
        "ExperimentGuard recommends a distinguishing set with minimum declared cost when supplied, then minimum experiment count, "
        "for the caller-declared predictions. It does not execute experiments, "
        "invent probabilities, or decide which hypothesis is true."
    )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentIterationResult:
    task_id: str
    iteration: int
    base_matrix_fingerprint: str
    candidate_matrix_fingerprint: str
    recommendation: ExperimentRecommendation
    observations: tuple[ExperimentObservation, ...]
    hypothesis_dispositions: tuple[HypothesisDisposition, ...]
    input_gap_ids: tuple[str, ...]
    resolved_gap_ids: tuple[str, ...]
    persisted_gap_ids: tuple[str, ...]
    introduced_gap_ids: tuple[str, ...]
    open_hypothesis_pairs: tuple[tuple[str, str], ...]
    next_experiment_ids: tuple[str, ...]
    revision_candidate: PredictionMatrixRevisionCandidate | None
    holdout_evidence_ids: tuple[str, ...]
    terminal_reason: Literal[
        "continue_iteration",
        "model_closed_for_task",
        "external_input_required",
        "progress_stalled",
        "iteration_limit",
    ]
    progressed: bool
    affected_obligation_ids: tuple[str, ...] = ()
    first_unresolved_gap: str = ""
    schema_version: str = EXPERIMENT_ITERATION_SCHEMA

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "iteration": self.iteration,
            "base_matrix_fingerprint": self.base_matrix_fingerprint,
            "candidate_matrix_fingerprint": self.candidate_matrix_fingerprint,
            "recommendation": self.recommendation.to_dict(),
            "observations": [item.to_dict() for item in self.observations],
            "hypothesis_dispositions": [item.to_dict() for item in self.hypothesis_dispositions],
            "input_gap_ids": list(self.input_gap_ids),
            "resolved_gap_ids": list(self.resolved_gap_ids),
            "persisted_gap_ids": list(self.persisted_gap_ids),
            "introduced_gap_ids": list(self.introduced_gap_ids),
            "open_hypothesis_pairs": [list(item) for item in self.open_hypothesis_pairs],
            "next_experiment_ids": list(self.next_experiment_ids),
            "revision_candidate": self.revision_candidate.to_dict() if self.revision_candidate else None,
            "holdout_evidence_ids": list(self.holdout_evidence_ids),
            "terminal_reason": self.terminal_reason,
            "progressed": self.progressed,
            "affected_obligation_ids": list(self.affected_obligation_ids),
            "first_unresolved_gap": self.first_unresolved_gap,
        }


__all__ = [
    "EXPERIMENT_ITERATION_SCHEMA",
    "EXPERIMENT_SPEC_SCHEMA",
    "ExperimentIterationResult",
    "ExperimentObservation",
    "ExperimentRecommendation",
    "ExperimentSpec",
    "HypothesisPrediction",
    "HypothesisDisposition",
    "PredictionMatrixRevisionCandidate",
]
