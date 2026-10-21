"""ExperimentGuard: recommendation-only experiment discrimination."""

from __future__ import annotations

from importlib import import_module

_PUBLIC_API = {
    'researchguard.experiment.engine': (
        'observe_experiments',
        'recommend_experiments',
    ),
    'researchguard.experiment.schema': (
        'ExperimentIterationReceipt',
        'ExperimentObservation',
        'ExperimentRecommendation',
        'ExperimentSpec',
        'HypothesisDisposition',
        'HypothesisPrediction',
        'PredictionMatrixRevisionCandidate',
    ),
}

_LAZY_EXPORTS = {name: module for module, names in _PUBLIC_API.items() for name in names}

__all__ = [
    'ExperimentIterationReceipt',
    'ExperimentObservation',
    'ExperimentRecommendation',
    'ExperimentSpec',
    'HypothesisDisposition',
    'HypothesisPrediction',
    'PredictionMatrixRevisionCandidate',
    'observe_experiments',
    'recommend_experiments',
]


def __getattr__(name: str):
    try:
        module_name = _LAZY_EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    attribute = name
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(_LAZY_EXPORTS))
