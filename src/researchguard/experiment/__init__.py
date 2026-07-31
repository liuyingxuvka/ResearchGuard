"""ExperimentGuard: recommendation-only experiment discrimination."""

from .engine import recommend_experiments
from .schema import (
    ExperimentRecommendation,
    ExperimentSpec,
    HypothesisPrediction,
)

__all__ = [
    "ExperimentRecommendation",
    "ExperimentSpec",
    "HypothesisPrediction",
    "recommend_experiments",
]
