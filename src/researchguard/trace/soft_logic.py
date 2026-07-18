"""Read-only relaxed-logic operators used in documentation and unit oracles.

Purpose: Provide transparent relaxed logic operators, implication violations, and weighted losses.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: TraceGuard
Math boundary: These operators do not score models. Canonical inference lives in researchguard.trace.inference.
CLI: researchguard trace evaluate <model.yaml>
Boundary: Soft truth is structural support, not factual certainty.
"""

from __future__ import annotations

from .schema import clamp01


def soft_not(value: float) -> float:
    return 1.0 - clamp01(value)


def soft_and(*values: float) -> float:
    if not values:
        return 1.0
    clamped = [clamp01(value) for value in values]
    return clamp01(sum(clamped) - len(clamped) + 1.0)


def soft_or(*values: float) -> float:
    return clamp01(sum(clamp01(value) for value in values))


def implication_violation(body: float, head: float) -> float:
    return max(0.0, clamp01(body) - clamp01(head))


def weighted_loss(violation: float, weight: float, *, squared: bool = False) -> float:
    v = max(0.0, float(violation))
    return float(weight) * (v * v if squared else v)
