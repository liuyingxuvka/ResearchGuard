"""ExperimentGuard: recommendation-only experiment discrimination."""

from __future__ import annotations

from researchguard._exports import lazy_exports

_PUBLIC_API = {
    'researchguard.experiment.engine': (
        'observe_experiments',
        'recommend_experiments',
    ),
    'researchguard.experiment.schema': (
        'ExperimentIterationResult',
        'ExperimentObservation',
        'ExperimentRecommendation',
        'ExperimentSpec',
        'HypothesisDisposition',
        'HypothesisPrediction',
        'PredictionMatrixRevisionCandidate',
    ),
}


__all__ = [
    'ExperimentIterationResult',
    'ExperimentObservation',
    'ExperimentRecommendation',
    'ExperimentSpec',
    'HypothesisDisposition',
    'HypothesisPrediction',
    'PredictionMatrixRevisionCandidate',
    'observe_experiments',
    'recommend_experiments',
]


__getattr__, __dir__ = lazy_exports(_PUBLIC_API, globals())
