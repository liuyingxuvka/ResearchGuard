"""Stable facade over the canonical TraceGuard inference engine.

There is no scoring, status, boundary, causal, or solver authority in this
module. All mathematical outputs originate in ``researchguard.trace.inference``.
"""

from __future__ import annotations

from dataclasses import replace

from .inference.engine import infer_model
from .results import EvaluationResult, TraceEvaluation
from .schema import TraceGuardModel


def evaluate_model(
    model: TraceGuardModel,
    *,
    include_storyline_depth: bool = True,
) -> EvaluationResult:
    """TraceGuardModel x evaluation options -> EvaluationResult."""

    base_result = infer_model(model)
    from .handoff import derive_trace_handoffs, review_trace_consolidation

    result = replace(
        base_result,
        handoffs=derive_trace_handoffs(base_result),
        consolidation_findings=review_trace_consolidation(model, base_result),
    )
    if include_storyline_depth:
        from .storyline_depth import evaluate_storyline_depth

        result = replace(
            result,
            storyline_depth=evaluate_storyline_depth(model, result),
        )
    return result


__all__ = ["EvaluationResult", "TraceEvaluation", "evaluate_model"]
