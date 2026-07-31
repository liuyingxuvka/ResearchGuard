"""ExperimentGuard: recommendation-only experiment discrimination."""

from .engine import observe_experiments, recommend_experiments
from .schema import (
    ExperimentIterationReceipt,
    ExperimentObservation,
    ExperimentRecommendation,
    ExperimentSpec,
    HypothesisDisposition,
    HypothesisPrediction,
    PredictionMatrixRevisionCandidate,
)

__all__ = [
    "ExperimentRecommendation",
    "ExperimentIterationReceipt",
    "ExperimentObservation",
    "ExperimentSpec",
    "HypothesisDisposition",
    "HypothesisPrediction",
    "PredictionMatrixRevisionCandidate",
    "observe_experiments",
    "recommend_experiments",
]
