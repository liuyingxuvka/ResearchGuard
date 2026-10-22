"""Typed, evidence-bound search stop decisions for SourceGuard."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .schema import BeliefState


SearchStopStatus = Literal[
    "continue_search", "stop_sufficient", "blocked_unresolved_critical", "not_run",
]


@dataclass(frozen=True)
class SearchCandidate:
    action_id: str
    target_gap_id: str
    cost: float
    utility: float
    declared: bool = False


@dataclass(frozen=True)
class SearchStopInput:
    """All eligible native candidates and the actual open-gap frontier.

    Utility orders searches; only cost is compared with the remaining budget.
    Neither quantity is a factual probability.
    """

    remaining_budget: float
    evidence_sufficient_for_scope: bool
    unresolved_critical_gap_ids: tuple[str, ...] = ()
    optional_gap_ids: tuple[str, ...] = ()
    candidates: tuple[SearchCandidate, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "affordable_search_ids": sorted(
                item.action_id for item in self.candidates
                if item.cost <= self.remaining_budget
            ),
        }


@dataclass(frozen=True)
class SearchStopDecision:
    status: SearchStopStatus
    reason_code: str
    reason: str
    selected_search_id: str = ""
    unresolved_critical_gap_ids: tuple[str, ...] = ()
    optional_followups: tuple[dict[str, str], ...] = ()
    claim_boundary: str = (
        "This decision governs whether the declared source search should "
        "continue. It does not establish factual truth or calibrated probability."
    )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def decide_search_stop(inputs: SearchStopInput) -> SearchStopDecision:
    """Own the one deterministic rule for stopping or choosing a search."""

    critical = tuple(sorted(set(inputs.unresolved_critical_gap_ids)))
    optional = tuple(sorted(set(inputs.optional_gap_ids) - set(critical)))
    ordered = sorted(inputs.candidates, key=lambda item: (-item.utility, not item.declared, item.action_id))
    followups = tuple({"gap_id": gap_id, "action_id": next(
        (item.action_id for item in ordered if item.target_gap_id == gap_id), ""
    )} for gap_id in optional)

    def result(status, code, reason, selected=""):
        return SearchStopDecision(status, code, reason, selected, critical, followups)

    if (not isfinite(inputs.remaining_budget) or inputs.remaining_budget < 0
            or any(not isfinite(item.cost) or item.cost < 0 or not isfinite(item.utility) for item in ordered)):
        return result("not_run", "invalid_decision_inputs", "Budget and action costs must be finite and non-negative; utility must be finite.")
    if critical:
        targets = [item for item in ordered if item.target_gap_id in critical]
        affordable = [item for item in targets if item.cost <= inputs.remaining_budget]
        if affordable:
            return result("continue_search", "critical_gap_search_affordable",
                          "An executable search targeting an open blocking gap fits the budget.", affordable[0].action_id)
        if not targets:
            return result("blocked_unresolved_critical", "critical_gap_without_search",
                          f"No executable action targets the open blocking gaps: {', '.join(critical)}.")
        return result("blocked_unresolved_critical", "critical_gap_search_over_budget",
                      f"All executable actions targeting blocking gaps {', '.join(critical)} exceed budget {inputs.remaining_budget:g}.")
    if inputs.evidence_sufficient_for_scope or not optional:
        return result("stop_sufficient", "scope_sufficient_no_blocking_gap",
                      "No blocking gap is open; the scope is declared sufficient or no gap remains.")
    affordable = [item for item in ordered if item.target_gap_id in optional and item.cost <= inputs.remaining_budget]
    if affordable:
        return result("continue_search", "optional_gap_search_affordable",
                      "No blocking gap is open; pass --sufficient to stop now.", affordable[0].action_id)
    return result("stop_sufficient", "no_affordable_optional_search",
                  "No blocking gap is open and no executable optional search fits the budget.")


def decide_model_search_stop(
    belief_state: "BeliefState", *, remaining_budget: float,
    evidence_sufficient_for_scope: bool = False,
) -> tuple[SearchStopInput, SearchStopDecision]:
    """Collect every eligible native planned action, then apply the stop rule.

    Open means semantic_state != closed, including blocked and permission gaps.
    The planner's complete scored catalog supplies utility without a top-N cap.
    """

    from .planner import plan_next_actions

    plan = plan_next_actions(belief_state, limit=None)
    scores = {item.action_id: item.total_score for item in plan.scored_actions}
    open_gaps = [gap for gap in belief_state.gaps if gap.semantic_state != "closed"]
    open_ids = {gap.gap_id for gap in open_gaps}
    declared_ids = {action.action_id for action in belief_state.actions}
    inputs = SearchStopInput(
        remaining_budget=float(remaining_budget),
        evidence_sufficient_for_scope=bool(evidence_sufficient_for_scope) or not open_gaps,
        unresolved_critical_gap_ids=tuple(sorted(gap.gap_id for gap in open_gaps if gap.blocking)),
        optional_gap_ids=tuple(sorted(gap.gap_id for gap in open_gaps if not gap.blocking)),
        candidates=tuple(SearchCandidate(action.action_id, action.target_gap_id, action.cost,
                                         scores[action.action_id], action.action_id in declared_ids)
                         for action in plan.selected_actions if action.target_gap_id in open_ids),
    )
    return inputs, decide_search_stop(inputs)


__all__ = ["SearchCandidate", "SearchStopDecision", "SearchStopInput", "SearchStopStatus",
           "decide_model_search_stop", "decide_search_stop"]
