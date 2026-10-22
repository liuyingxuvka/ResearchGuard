"""Finite stop-rule model, with conformance against native in-memory models."""

from __future__ import annotations

from dataclasses import dataclass, replace

from flowguard import FunctionResult, Invariant, InvariantResult, Scenario, ScenarioExpectation, Workflow

MODEL_ID = "sourceguard_stop_decision"
PARENT = "sourceguard"
COMPONENTS = ["sourceguard"]
IMPLEMENTED_BY = {"StopDecision": "src/researchguard/source/stop_decision.py:decide_model_search_stop"}


@dataclass(frozen=True)
class Candidate:
    action_id: str
    target: str
    cost: float
    utility: float


@dataclass(frozen=True)
class Case:
    name: str
    budget: float
    sufficient: bool
    critical: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    candidates: tuple[Candidate, ...] = ()


@dataclass(frozen=True)
class DecisionState:
    case: Case | None = None
    status: str = "not_run"
    selected: str = ""


CASES = (
    Case("critical_cheaper", .25, False, ("critical",), candidates=(
        Candidate("expensive", "critical", .9, .8), Candidate("cheap", "critical", .2, .1))),
    Case("critical_value_not_cost", 1, False, ("critical",), candidates=(Candidate("search", "critical", .9, .1),)),
    Case("critical_starved", 0, True, ("critical",), candidates=(Candidate("search", "critical", .2, .8),)),
    Case("sufficient_optional", 1, True, optional=("optional",), candidates=(Candidate("followup", "optional", .2, .8),)),
    Case("optional_unfunded", 0, False, optional=("optional",)),
)


class StopDecision:
    name = "StopDecision"
    reads = ()
    writes = ("case", "status", "selected")

    def apply(self, case: Case, state: DecisionState):
        targets = case.critical or case.optional
        affordable = sorted((item for item in case.candidates if item.target in targets and item.cost <= case.budget),
                            key=lambda item: (-item.utility, item.action_id))
        if not case.critical and (case.sufficient or not case.optional):
            status, selected = "stop_sufficient", ""
        elif affordable:
            status, selected = "continue_search", affordable[0].action_id
        else:
            status, selected = ("blocked_unresolved_critical" if case.critical else "stop_sufficient"), ""
        yield FunctionResult(case, DecisionState(case, status, selected), label=case.name)


def _no_stop_with_critical(state, trace):
    if state.case and state.case.critical and state.status == "stop_sufficient":
        return InvariantResult.fail("a blocking gap was hidden by sufficiency")
    return InvariantResult.pass_()


def _continue_affordable(state, trace):
    if state.case and state.status == "continue_search":
        targets = state.case.critical or state.case.optional
        if not any(item.action_id == state.selected and item.target in targets and item.cost <= state.case.budget
                   for item in state.case.candidates):
            return InvariantResult.fail("continue selected no affordable action for the actual frontier")
    return InvariantResult.pass_()


def _sufficient_stops(state, trace):
    if state.case and not state.case.critical and state.case.sufficient and state.status != "stop_sufficient":
        return InvariantResult.fail("declared sufficiency without a blocking gap did not stop")
    return InvariantResult.pass_()


def _affordable_critical_continues(state, trace):
    if state.case and state.case.critical and any(item.target in state.case.critical and item.cost <= state.case.budget
                                               for item in state.case.candidates) and state.status != "continue_search":
        return InvariantResult.fail("an affordable critical action was overlooked")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant("no_stop_while_blocking_gap_open", "A critical gap cannot stop as sufficient.", _no_stop_with_critical),
    Invariant("continue_only_with_affordable_target", "Continuation selects an affordable action for the frontier.", _continue_affordable),
    Invariant("sufficient_when_no_blocking_gap_and_declared", "Declared sufficiency stops without a critical gap.", _sufficient_stops),
    Invariant("affordable_critical_action_continues", "All candidates must be considered without comparing utility to cost.", _affordable_critical_continues),
)
TESTED_BY = {
    "no_stop_while_blocking_gap_open": ["tests/source/test_stop_decision.py:test_blocked_and_permission_gaps_still_prevent_sufficient_stop"],
    "continue_only_with_affordable_target": ["tests/source/test_stop_decision.py:test_model_stop_decision_reads_the_plan_and_the_blocking_gaps"],
    "sufficient_when_no_blocking_gap_and_declared": ["tests/source/test_stop_decision.py:test_blocking_closed_nonblocking_open_and_sufficient_stops"],
    "affordable_critical_action_continues": ["tests/source/test_stop_decision.py:test_cheaper_critical_action_is_found_within_budget"],
}


def build_explorer(step=None, cases=CASES):
    from flowguard.explorer import Explorer
    return Explorer(Workflow((step or StopDecision(),), name="sourceguard_stop"), (DecisionState(),), cases, INVARIANTS)


def scenarios():
    return tuple(Scenario(name=case.name, description=case.name, initial_state=DecisionState(),
                          external_input_sequence=(case,), workflow=Workflow((StopDecision(),), name="sourceguard_stop"),
                          invariants=INVARIANTS, expected=ScenarioExpectation(expected_status="ok", summary=case.name)) for case in CASES)


def broken_variants():
    class Broken(StopDecision):
        def __init__(self, kind):
            self.kind = kind

        def apply(self, case, state):
            for result in super().apply(case, state):
                new = result.new_state
                if self.kind == "unsafe_stop":
                    new = replace(new, status="stop_sufficient")
                elif self.kind == "unaffordable_continue":
                    new = replace(new, status="continue_search", selected="search")
                elif self.kind == "optional_never_stops":
                    new = replace(new, status="continue_search", selected="followup")
                elif self.kind == "top_action_only":
                    top = sorted(case.candidates, key=lambda item: (-item.utility, item.action_id))[0]
                    affordable = top.target in case.critical and top.cost <= case.budget
                    new = replace(new, status="continue_search" if affordable else "blocked_unresolved_critical",
                                  selected=top.action_id if affordable else "")
                elif self.kind == "value_vs_cost" and case.candidates[0].utility <= case.candidates[0].cost:
                    new = replace(new, status="blocked_unresolved_critical", selected="")
                yield replace(result, new_state=new)

    return {kind: build_explorer(Broken(kind), (case,)) for kind, case in (
        ("unsafe_stop", CASES[2]), ("unaffordable_continue", CASES[2]), ("optional_never_stops", CASES[3]),
        ("top_action_only", CASES[0]), ("value_vs_cost", CASES[1]),
    )}


def conformance():
    from flowguard.conformance import ConformanceReport, ConformanceViolation
    from flowguard.replay import ReplayObservation
    from researchguard.source.schema import BeliefState, Gap, SearchAction
    from researchguard.source.stop_decision import decide_model_search_stop
    observations, violations = [], []
    for case in CASES:
        # Public-only permission gaps suppress automatic executable candidates;
        # explicit executable actions still exercise the native scorer and rule.
        gaps = [Gap(gap_id, gap_type="permission_gap", blocking=gap_id in case.critical)
                for gap_id in case.critical + case.optional]
        actions = [SearchAction(item.action_id, action_type="text_search", target_gap_id=item.target,
                                query=item.action_id, cost=item.cost) for item in case.candidates]
        _, actual = decide_model_search_stop(BeliefState(gaps=gaps, actions=actions), remaining_budget=case.budget,
                                            evidence_sufficient_for_scope=case.sufficient)
        expected = next(StopDecision().apply(case, DecisionState())).new_state
        observed = (actual.status, actual.selected_search_id)
        wanted = (expected.status, expected.selected)
        observations.append(ReplayObservation(case.name, wanted, observed))
        if observed != wanted:
            violations.append(ConformanceViolation(step_index=1, message=f"{case.name}: {observed} != {wanted}", rule_name="StopDecision"))
    return ConformanceReport(ok=not violations, violations=tuple(violations), replayed_steps=tuple(observations),
                             summary="Five in-memory frontiers replay the native planner, scorer and stop owner.")
