"""TraceGuard public API.

TraceGuard v0.6.0 provides one constrained HL-MRF/MAP inference kernel for
evidence-to-trace, competing-storyline, and bounded qualitative-causal
reasoning. It is not calibrated probability or factual causal identification.
"""

from .evaluator import EvaluationResult, evaluate_model
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
    "EvaluationResult",
    "TraceHandoff",
    "HypothesisSnapshot",
    "PerturbationEffect",
    "PerturbationPlanItem",
    "StorylineAlternative",
    "StorylineDepthReceipt",
    "derive_trace_handoffs",
    "evaluate_model",
    "evaluate_storyline_depth",
    "load_model",
    "review_trace_consolidation",
    "select_perturbation_plan",
]
from researchguard import __version__
