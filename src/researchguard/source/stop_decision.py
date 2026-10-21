"""Typed, evidence-bound search stop decisions for SourceGuard."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .schema import BeliefState


SearchStopStatus = Literal[
    "continue_search",
    "stop_sufficient",
    "blocked_unresolved_critical",
    "not_run",
]


@dataclass(frozen=True)
class SearchStopInput:
    """Declared inputs for one search-stop decision.

    Values are comparative planning quantities supplied by the caller. They are
    not probabilities and SourceGuard does not calibrate them as probabilities.
    """

    marginal_information_value: float
    next_search_cost: float
    remaining_budget: float
    evidence_sufficient_for_scope: bool
    unresolved_critical_gap_ids: tuple[str, ...] = ()
    candidate_search_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchStopDecision:
    status: SearchStopStatus
    reason_code: str
    reason: str
    selected_search_id: str = ""
    unresolved_critical_gap_ids: tuple[str, ...] = ()
    claim_boundary: str = (
        "This decision governs whether the declared source search should "
        "continue. It does not establish factual truth or calibrated "
        "probability."
    )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def decide_search_stop(inputs: SearchStopInput) -> SearchStopDecision:
    """Return one deterministic, typed stop/continue decision."""

    numeric = (
        inputs.marginal_information_value,
        inputs.next_search_cost,
        inputs.remaining_budget,
    )
    if any(value < 0 for value in numeric):
        raise ValueError("search-stop quantities must be non-negative")

    critical = tuple(sorted(set(inputs.unresolved_critical_gap_ids)))
    candidates = tuple(sorted(set(inputs.candidate_search_ids)))
    affordable = (
        bool(candidates)
        and inputs.remaining_budget >= inputs.next_search_cost
    )
    worthwhile = (
        inputs.marginal_information_value > inputs.next_search_cost
    )

    if critical:
        if affordable and worthwhile:
            return SearchStopDecision(
                status="continue_search",
                reason_code="critical_gap_search_worthwhile",
                reason=(
                    "At least one declared critical gap remains and the next "
                    "declared search has positive comparative value within "
                    "budget."
                ),
                selected_search_id=candidates[0],
                unresolved_critical_gap_ids=critical,
            )
        return SearchStopDecision(
            status="blocked_unresolved_critical",
            reason_code="critical_gap_without_justified_search",
            reason=(
                "A critical gap remains, but no affordable search with "
                "positive declared comparative value is available."
            ),
            unresolved_critical_gap_ids=critical,
        )

    if inputs.evidence_sufficient_for_scope and not worthwhile:
        return SearchStopDecision(
            status="stop_sufficient",
            reason_code="scope_sufficient_marginal_value_exhausted",
            reason=(
                "The declared scope is sufficiently supported and the next "
                "search does not exceed its declared cost."
            ),
        )

    if affordable and worthwhile:
        return SearchStopDecision(
            status="continue_search",
            reason_code="additional_search_worthwhile",
            reason=(
                "The next declared search has positive comparative value and "
                "fits the remaining budget."
            ),
            selected_search_id=candidates[0],
        )

    return SearchStopDecision(
        status="not_run",
        reason_code="decision_inputs_incomplete",
        reason=(
            "The evidence is not declared sufficient, and no justified "
            "candidate search is currently available."
        ),
    )


def decide_model_search_stop(
    belief_state: "BeliefState",
    *,
    remaining_budget: float,
    evidence_sufficient_for_scope: bool = False,
) -> tuple[SearchStopInput, SearchStopDecision]:
    """Read the stop-decision inputs from a SourceGuard model, then decide.

    The next search is the top action of ``plan_next_actions``: its utility
    score is the marginal value and its declared ``cost`` is the cost.  Open
    blocking gaps are the critical gaps; a model without open gaps is
    sufficient.  The budget and any sufficiency declaration come from the caller.
    """

    from .planner import plan_next_actions

    plan = plan_next_actions(belief_state, limit=1)
    top = plan.selected_actions[0] if plan.selected_actions else None
    score = next(
        (item.total_score for item in plan.scored_actions if top is not None and item.action_id == top.action_id),
        0.0,
    )
    inputs = SearchStopInput(
        marginal_information_value=float(score),
        next_search_cost=float(top.cost) if top is not None else 0.0,
        remaining_budget=float(remaining_budget),
        evidence_sufficient_for_scope=bool(evidence_sufficient_for_scope) or not plan.open_gaps,
        unresolved_critical_gap_ids=tuple(gap.gap_id for gap in plan.open_gaps if gap.blocking),
        candidate_search_ids=(top.action_id,) if top is not None else (),
    )
    return inputs, decide_search_stop(inputs)


__all__ = [
    "SearchStopDecision",
    "SearchStopInput",
    "SearchStopStatus",
    "decide_model_search_stop",
    "decide_search_stop",
]
