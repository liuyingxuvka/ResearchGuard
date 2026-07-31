"""Typed ExperimentGuard inputs and recommendation results."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class HypothesisPrediction:
    hypothesis_id: str
    outcomes_by_experiment: dict[str, str]


@dataclass(frozen=True)
class ExperimentSpec:
    hypothesis_predictions: tuple[HypothesisPrediction, ...]
    candidate_experiment_ids: tuple[str, ...]
    maximum_experiment_count: int | None = None


@dataclass(frozen=True)
class ExperimentObservation:
    experiment_id: str
    observed_outcome: str
    evidence_id: str
    status: Literal["valid", "invalid", "not_run"] = "valid"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class HypothesisDisposition:
    hypothesis_id: str
    status: Literal["supported", "weakened", "undetermined"]
    matched_experiment_ids: tuple[str, ...] = ()
    contradicted_experiment_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentIterationReceipt:
    recommendation: ExperimentRecommendation
    observations: tuple[ExperimentObservation, ...]
    hypothesis_dispositions: tuple[HypothesisDisposition, ...]
    open_hypothesis_pairs: tuple[tuple[str, str], ...]
    next_experiment_ids: tuple[str, ...]
    terminal_reason: str
    progressed: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "recommendation": self.recommendation.to_dict(),
            "observations": [item.to_dict() for item in self.observations],
            "hypothesis_dispositions": [item.to_dict() for item in self.hypothesis_dispositions],
            "open_hypothesis_pairs": [list(item) for item in self.open_hypothesis_pairs],
            "next_experiment_ids": list(self.next_experiment_ids),
            "terminal_reason": self.terminal_reason,
            "progressed": self.progressed,
        }


@dataclass(frozen=True)
class ExperimentRecommendation:
    status: Literal[
        "recommended",
        "indistinguishable",
        "blocked_invalid_input",
    ]
    selected_experiment_ids: tuple[str, ...]
    alternative_minimal_sets: tuple[tuple[str, ...], ...]
    unresolved_hypothesis_pairs: tuple[tuple[str, str], ...]
    reason_code: str
    claim_boundary: str = (
        "ExperimentGuard recommends a minimum-cardinality distinguishing set "
        "for the caller-declared predictions. It does not execute experiments, "
        "invent probabilities, or decide which hypothesis is true."
    )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


__all__ = [
    "ExperimentIterationReceipt",
    "ExperimentObservation",
    "ExperimentRecommendation",
    "ExperimentSpec",
    "HypothesisPrediction",
    "HypothesisDisposition",
]
