"""TraceGuard public API.

TraceGuard v0.6.0 provides one constrained HL-MRF/MAP inference kernel for
evidence-to-trace, competing-storyline, and bounded qualitative-causal
reasoning. It is not calibrated probability or factual causal identification."""

from __future__ import annotations

from researchguard._exports import lazy_exports

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


__getattr__, __dir__ = lazy_exports(_PUBLIC_API, globals())
