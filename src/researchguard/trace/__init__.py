"""TraceGuard public API.

TraceGuard v0.6.0 provides one constrained HL-MRF/MAP inference kernel for
evidence-to-trace, competing-storyline, and bounded qualitative-causal
reasoning. It is not calibrated probability or factual causal identification."""

from __future__ import annotations

from importlib import import_module

_PUBLIC_API = {
    'researchguard.trace.evaluator': (
        'EvaluationResult',
        'evaluate_model',
    ),
    'researchguard.trace.handoff': (
        'ConsolidationFinding',
        'TraceHandoff',
        'derive_trace_handoffs',
        'review_trace_consolidation',
    ),
    'researchguard.trace.loader': (
        'load_model',
    ),
    'researchguard.trace.export_logicguard': (
        'LOGICGUARD_HANDOFF_EXPORT_VERSION',
        'LOGICGUARD_HANDOFF_SCHEMA',
        'logicguard_bundle',
        'render_logicguard_yaml',
        'validate_logicguard_bundle',
    ),
    'researchguard.trace.storyline_depth': (
        'HypothesisSnapshot',
        'PerturbationEffect',
        'PerturbationPlanItem',
        'StorylineAlternative',
        'StorylineDepthResult',
        'evaluate_storyline_depth',
        'select_perturbation_plan',
    ),
    'researchguard': (
        '__version__',
    ),
}

_LAZY_EXPORTS = {name: module for module, names in _PUBLIC_API.items() for name in names}

__all__ = [
    'ConsolidationFinding',
    'LOGICGUARD_HANDOFF_EXPORT_VERSION',
    'LOGICGUARD_HANDOFF_SCHEMA',
    'EvaluationResult',
    'TraceHandoff',
    'HypothesisSnapshot',
    'PerturbationEffect',
    'PerturbationPlanItem',
    'StorylineAlternative',
    'StorylineDepthResult',
    'derive_trace_handoffs',
    'logicguard_bundle',
    'render_logicguard_yaml',
    'validate_logicguard_bundle',
    'evaluate_model',
    'evaluate_storyline_depth',
    'load_model',
    'review_trace_consolidation',
    'select_perturbation_plan',
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
