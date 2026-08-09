"""TraceGuard public API.

TraceGuard v0.6.0 provides one constrained HL-MRF/MAP inference kernel for
evidence-to-trace, competing-storyline, and bounded qualitative-causal
reasoning. It is not calibrated probability or factual causal identification.
"""

from .evaluator import EvaluationResult, evaluate_model
from .blueprint import (
    TRACE_BLUEPRINT_SCHEMA,
    TraceBlueprintGap,
    TraceBlueprintResult,
    TraceHierarchyNode,
    TraceTargetUniverse,
    check_blueprint,
    export_blueprint,
    hierarchy_fingerprint,
    impact_blueprint,
    interface_fingerprint,
    project_hierarchy,
    replay_trace_target_material,
    reverse_trace_output,
    trace_target_purpose_fingerprint,
    trace_target_request_fingerprint,
    trace_target_subject_fingerprint,
)
from .handoff import ConsolidationFinding, TraceHandoff, derive_trace_handoffs, review_trace_consolidation
from .loader import load_model
from .storyline_depth import (
    HypothesisSnapshot,
    PerturbationEffect,
    PerturbationPlanItem,
    StorylineAlternative,
    StorylineDepthReceipt,
    evaluate_storyline_depth,
    select_perturbation_plan,
)

__all__ = [
    "ConsolidationFinding",
    "TRACE_BLUEPRINT_SCHEMA",
    "TraceBlueprintGap",
    "TraceBlueprintResult",
    "TraceHierarchyNode",
    "TraceTargetUniverse",
    "EvaluationResult",
    "TraceHandoff",
    "HypothesisSnapshot",
    "PerturbationEffect",
    "PerturbationPlanItem",
    "StorylineAlternative",
    "StorylineDepthReceipt",
    "derive_trace_handoffs",
    "check_blueprint",
    "export_blueprint",
    "evaluate_model",
    "evaluate_storyline_depth",
    "load_model",
    "hierarchy_fingerprint",
    "impact_blueprint",
    "interface_fingerprint",
    "project_hierarchy",
    "replay_trace_target_material",
    "review_trace_consolidation",
    "select_perturbation_plan",
    "reverse_trace_output",
    "trace_target_purpose_fingerprint",
    "trace_target_request_fingerprint",
    "trace_target_subject_fingerprint",
]
from researchguard import __version__
