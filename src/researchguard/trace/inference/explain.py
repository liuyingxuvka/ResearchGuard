"""Factor-level explanations derived from the solved canonical objective."""

from __future__ import annotations

from .policy import InferencePolicy
from .types import CompiledProblem, FactorContribution, InferenceSolution


def explain_solution(
    problem: CompiledProblem,
    solution: InferenceSolution,
    policy: InferencePolicy,
) -> tuple[FactorContribution, ...]:
    if solution.problem_fingerprint != problem.problem_fingerprint:
        raise ValueError("solution/problem fingerprint mismatch")
    contributions = [
        FactorContribution(
            factor_id=factor.factor_id,
            family=factor.family,
            direction=factor.direction,
            violation=factor.violation(solution.atom_values),
            loss=factor.loss(solution.atom_values),
            affected_object_ids=factor.affected_object_ids,
            evidence_ids=factor.evidence_ids,
            explanation=(
                f"{factor.description} Solved hinge violation="
                f"{factor.violation(solution.atom_values):.6f}, "
                f"weighted loss={factor.loss(solution.atom_values):.6f}."
            ),
        )
        for factor in problem.factors
    ]
    return tuple(
        sorted(
            contributions,
            key=lambda item: (
                -item.loss,
                item.factor_id,
            ),
        )
    )
