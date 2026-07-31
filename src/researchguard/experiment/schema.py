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
    "ExperimentRecommendation",
    "ExperimentSpec",
    "HypothesisPrediction",
]
