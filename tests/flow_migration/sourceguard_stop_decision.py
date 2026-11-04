"""Finite stop-rule model, with conformance against native in-memory models."""
from __future__ import annotations
from dataclasses import dataclass, replace

@dataclass(frozen=True)
class Candidate:
    action_id: str
    target: str
    cost: float
    utility: float
    generated: bool = False

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
    status: str = 'not_run'
    selected: str = ''
    search_order: tuple[str, ...] = ()
CASES = (Case('declared_search_first', 1, False, ('critical',), candidates=(Candidate('generated-twin', 'critical', 0.3, 0.8, True), Candidate('declared', 'critical', 0.3, 0.8))), Case('critical_cheaper', 0.25, False, ('critical',), candidates=(Candidate('expensive', 'critical', 0.9, 0.8), Candidate('cheap', 'critical', 0.2, 0.1))), Case('critical_value_not_cost', 1, False, ('critical',), candidates=(Candidate('search', 'critical', 0.9, 0.1),)), Case('critical_starved', 0, True, ('critical',), candidates=(Candidate('search', 'critical', 0.2, 0.8),)), Case('sufficient_optional', 1, True, optional=('optional',), candidates=(Candidate('followup', 'optional', 0.2, 0.8),)), Case('optional_unfunded', 0, False, optional=('optional',)))

def expected_StopDecision(case: Case, state: DecisionState, mutation=''):
    targets = case.critical or case.optional
    affordable = sorted((item for item in case.candidates if item.target in targets and item.cost <= case.budget), key=lambda item: (-item.utility, item.action_id))
    if not case.critical and (case.sufficient or not case.optional):
        status, selected = ('stop_sufficient', '')
    elif affordable:
        status, selected = ('continue_search', affordable[0].action_id)
    else:
        status, selected = ('blocked_unresolved_critical' if case.critical else 'stop_sufficient', '')
    order = tuple((row.action_id for row in sorted(case.candidates, key=lambda row: (-row.utility, row.generated, row.action_id))))
    return DecisionState(case, status, selected, order)

def _no_stop_with_critical(state):
    if state.case and state.case.critical and (state.status == 'stop_sufficient'):
        return False
    return True

def _continue_affordable(state):
    if state.case and state.status == 'continue_search':
        targets = state.case.critical or state.case.optional
        if not any((item.action_id == state.selected and item.target in targets and (item.cost <= state.case.budget) for item in state.case.candidates)):
            return False
    return True

def _sufficient_stops(state):
    if state.case and (not state.case.critical) and state.case.sufficient and (state.status != 'stop_sufficient'):
        return False
    return True

def _affordable_critical_continues(state):
    if state.case and state.case.critical and any((item.target in state.case.critical and item.cost <= state.case.budget for item in state.case.candidates)) and (state.status != 'continue_search'):
        return False
    return True

def declared_search_comes_first(state):
    if state.case:
        candidates = {row.action_id: row for row in state.case.candidates}
        for i, left in enumerate(state.search_order):
            for right in state.search_order[i + 1:]:
                a, b = (candidates[left], candidates[right])
                if a.utility == b.utility and a.generated and (not b.generated):
                    return False
    return True
RULES = (declared_search_comes_first, _no_stop_with_critical, _continue_affordable, _sufficient_stops, _affordable_critical_continues)

def assert_native_contract():
    from researchguard.source.schema import BeliefState, Gap, SearchAction
    from researchguard.source.stop_decision import decide_model_search_stop
    observations, violations = ([], [])
    for case in CASES[1:]:
        gaps = [Gap(gap_id, gap_type='permission_gap', blocking=gap_id in case.critical) for gap_id in case.critical + case.optional]
        actions = [SearchAction(item.action_id, action_type='text_search', target_gap_id=item.target, query=item.action_id, cost=item.cost) for item in case.candidates]
        _, actual = decide_model_search_stop(BeliefState(gaps=gaps, actions=actions), remaining_budget=case.budget, evidence_sufficient_for_scope=case.sufficient)
        expected = expected_StopDecision(case, DecisionState())
        observed = (actual.status, actual.selected_search_id)
        wanted = (expected.status, expected.selected)
        if observed != wanted:
            violations.append(f'{case.name}: {observed} != {wanted}')
    from researchguard.source.planner import plan_next_actions
    from researchguard.source.schema import SourceRecord
    model = BeliefState(sources=[SourceRecord('s', title='A dated source')], gaps=[Gap('counter-source-s', gap_type='contradiction', description='Counterevidence candidate observed')])
    actions = plan_next_actions(model, limit=None).selected_actions
    observed = [(row.action_type, row.query) for row in actions]
    wanted = [('report_page_search', 'A dated source')]
    if observed != wanted:
        violations.append(f'counter-source searches: {observed!r} != {wanted!r}')
    from researchguard.source.planner import generate_actions_from_gaps
    twin = generate_actions_from_gaps(model)[0]
    declared = replace(twin, action_id='declared', query='Independent source')
    model = replace(model, actions=[declared], sources=[*model.sources, SourceRecord('t', title='Another source')], gaps=[*model.gaps, replace(model.gaps[0], gap_id='counter-source-t')])
    plan = plan_next_actions(model, limit=None)
    scores = {row.action_id: row.total_score for row in plan.scored_actions}
    ordered = plan.selected_actions[0].action_id == 'declared' and len(set(scores.values())) == 1 and (len(scores) == 2)
    if not ordered:
        violations.append('equally scored generated search displaced a declared search')
    assert not violations, violations
RULE_NAMES = ('declared_search_comes_first', 'no_stop_while_blocking_gap_open', 'continue_only_with_affordable_target', 'sufficient_when_no_blocking_gap_and_declared', 'affordable_critical_action_continues')
