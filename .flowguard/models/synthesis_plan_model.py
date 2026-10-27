"""Synthesis plan status: ready only when the request is valid, within budget and has no open gap."""
from dataclasses import dataclass
import importlib.util
from pathlib import Path

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer

MODEL_ID = 'synthesis_plan'
PARENT = 'logic-artifact'
COMPONENTS = ['logic-artifact']
IMPLEMENTED_BY = {'Synthesize': 'src/researchguard/logic/synthesis.py:synthesize_artifact_plan'}
TESTED_BY = {
    'ready_only_without_open_gaps': ['tests/logic/test_artifact_synthesis.py:test_ready_argument_plan_uses_native_depth_without_external_state',
                                     'tests/logic/test_artifact_synthesis.py:test_missing_support_stays_blocked_in_the_argument_plan'],
    'over_budget_is_blocked_budget': ['tests/logic/test_synthesis_contract.py:test_parent_predecessor_graph_and_budget_fail_closed'],
    'invalid_request_is_blocked': ['tests/logic/test_artifact_synthesis.py:test_synthesis_requires_goal',
                                   'tests/logic/test_synthesis_contract.py:test_selection_request_is_required_and_old_entry_does_not_fallback'],
}


@dataclass(frozen=True)
class Request:
    """What decides a plan's status: request validity, body units against the budget, and open support gaps."""
    name: str
    valid: bool = True
    body_units: int = 1
    max_body_units: int = 1
    open_gaps: int = 0


@dataclass(frozen=True)
class State:
    request: Request | None = None
    status: str = ''


class Synthesize:
    name = 'Synthesize'
    reads = ('request',)
    writes = ('status', 'request')
    mutation = ''

    def apply(self, request, state):
        over = request.body_units > request.max_body_units
        if not request.valid:
            status = 'research_handoff_ready' if self.mutation == 'invalid_request_ready' else 'blocked_invalid_request'
        elif over:
            status = 'research_handoff_ready' if self.mutation == 'over_budget_ready' else 'blocked_budget'
        elif request.open_gaps:
            status = 'research_handoff_ready' if self.mutation == 'ready_with_open_gaps' else 'blocked_support_gap'
        else:
            status = 'research_handoff_ready'
        result = State(request, status)
        yield FunctionResult(result, result, label=request.name)


def rule(check):
    def invariant(state, trace):
        if state.request is None:
            return InvariantResult.pass_()
        problem = check(state, state.request)
        return InvariantResult.fail(problem) if problem else InvariantResult.pass_()
    return invariant


def ready_rule(state, request):
    if state.status == 'research_handoff_ready' and (request.open_gaps or not request.valid or request.body_units > request.max_body_units):
        return f'{request.name}: ready although the request is blocked'


def budget_rule(state, request):
    if request.valid and request.body_units > request.max_body_units and state.status != 'blocked_budget':
        return f'{request.name}: over budget but {state.status}'


def invalid_rule(state, request):
    if not request.valid and state.status != 'blocked_invalid_request':
        return f'{request.name}: invalid request but {state.status}'


INVARIANTS = (
    Invariant('ready_only_without_open_gaps', 'A plan is ready only for a valid request within budget and without open gaps.', rule(ready_rule)),
    Invariant('over_budget_is_blocked_budget', 'Body units over the budget block the plan as blocked_budget.', rule(budget_rule)),
    Invariant('invalid_request_is_blocked', 'An invalid request is blocked_invalid_request.', rule(invalid_rule)),
)
CASES = (
    Request('invalid', valid=False),
    Request('support_gap', open_gaps=1),
    Request('over_budget', body_units=2, max_body_units=1, open_gaps=1),
    Request('ready', body_units=2, max_body_units=2),
)
MUTATIONS = {
    'ready_with_open_gaps': 'ready_only_without_open_gaps',
    'over_budget_ready': 'over_budget_is_blocked_budget',
    'invalid_request_ready': 'invalid_request_is_blocked',
}


def explorer(step):
    return Explorer(Workflow((step,)), (State(),), CASES, INVARIANTS, progress_steps=0)


def build_explorer():
    return explorer(Synthesize())


def broken_variants():
    result = {}
    for name in MUTATIONS:
        step = Synthesize()
        step.mutation = name
        result[name] = explorer(step)
    return result


def _fixtures(name):
    path = Path(__file__).resolve().parents[2] / 'tests/logic' / f'{name}.py'
    spec = importlib.util.spec_from_file_location(f'_synthesis_fixture_{name}', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def native_plans():
    """The real synthesize_artifact_plan on the request shapes the cases stand for (fixtures shared with the tests)."""
    from researchguard.logic import synthesize_artifact_plan
    contract = _fixtures('test_synthesis_contract')
    model = contract._model()
    over = contract._request(model, max_body_units=1)
    over['units'].append({**over['units'][0], 'unit_id': 'u2', 'claim_ids': ['C0']})
    over['body_unit_order'] = ['u1', 'u2']
    ready = _fixtures('test_artifact_synthesis')._ready_plan()
    return {'invalid': synthesize_artifact_plan(model, selection_request={}),
            'support_gap': synthesize_artifact_plan(model, selection_request=contract._request(model)),
            'over_budget': synthesize_artifact_plan(model, selection_request=over),
            'ready': ready}


def conformance():
    from flowguard.conformance import ConformanceReport, ConformanceViolation
    from flowguard.replay import ReplayObservation
    observations, violations = [], []
    plans = native_plans()
    for request in CASES:
        plan = plans[request.name]
        want = next(iter(Synthesize().apply(request, State()))).new_state.status
        actual = State(Request(request.name, request.valid, request.body_units, request.max_body_units, len(plan.open_gaps)), plan.status)
        observations.append(ReplayObservation('Synthesize', plan.status, actual))
        if plan.status != want:
            violations.append(ConformanceViolation(step_index=1, rule_name='Synthesize', message=f'{request.name}: {plan.status} != {want}'))
        for invariant in INVARIANTS:
            verdict = invariant.check(actual, ())
            if not verdict.ok:
                violations.append(ConformanceViolation(step_index=1, rule_name='Synthesize', message=f'{request.name}: {invariant.name}: {verdict.message}'))
    return ConformanceReport(ok=not violations, violations=tuple(violations), replayed_steps=tuple(observations),
                             summary='Real synthesis plans for an invalid, a support-gap, an over-budget and a ready request.')
