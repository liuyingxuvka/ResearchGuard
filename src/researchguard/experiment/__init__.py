"""ExperimentGuard: recommendation-only experiment discrimination."""

from __future__ import annotations

from importlib import import_module

_PUBLIC_API = {
    'researchguard.experiment.blueprint': (
        'check_blueprint',
        'child_output_payload_fingerprint',
        'child_output_result_fingerprint',
        'export_blueprint',
        'impact_blueprint',
        'replay_experiment_target_material',
        'reverse_trace_experiment',
        'target_purpose_fingerprint',
        'target_request_fingerprint',
    ),
    'researchguard.experiment.engine': (
        'observe_experiments',
        'recommend_experiments',
    ),
    'researchguard.experiment.schema': (
        'ExperimentConstraint',
        'ExperimentChildOutputBinding',
        'ExperimentDesignBlock',
        'ExperimentIterationReceipt',
        'ExperimentInputBinding',
        'ExperimentNativeCaseEvidence',
        'ExperimentObservation',
        'ExperimentPort',
        'ExperimentRecommendation',
        'ExperimentSpec',
        'ExperimentTargetUniverse',
        'HypothesisDisposition',
        'HypothesisPrediction',
        'PredictionMatrixRevisionCandidate',
        'ProcedureStep',
    ),
}

_LAZY_EXPORTS = {name: module for module, names in _PUBLIC_API.items() for name in names}

__all__ = [
    'ExperimentConstraint',
    'ExperimentChildOutputBinding',
    'ExperimentDesignBlock',
    'ExperimentIterationReceipt',
    'ExperimentInputBinding',
    'ExperimentNativeCaseEvidence',
    'ExperimentObservation',
    'ExperimentPort',
    'ExperimentRecommendation',
    'ExperimentSpec',
    'ExperimentTargetUniverse',
    'HypothesisDisposition',
    'HypothesisPrediction',
    'PredictionMatrixRevisionCandidate',
    'ProcedureStep',
    'check_blueprint',
    'child_output_payload_fingerprint',
    'child_output_result_fingerprint',
    'export_blueprint',
    'impact_blueprint',
    'replay_experiment_target_material',
    'observe_experiments',
    'recommend_experiments',
    'reverse_trace_experiment',
    'target_purpose_fingerprint',
    'target_request_fingerprint',
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
