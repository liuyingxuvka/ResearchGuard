"""Synthesis plan status: ready only when the request is valid, within budget and has no open gap."""
from dataclasses import dataclass
import importlib.util
from pathlib import Path

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

def expected_Synthesize(request, state, mutation=''):
    over = request.body_units > request.max_body_units
    if not request.valid:
        status = 'research_handoff_ready' if mutation == 'invalid_request_ready' else 'blocked_invalid_request'
    elif over:
        status = 'research_handoff_ready' if mutation == 'over_budget_ready' else 'blocked_budget'
    elif request.open_gaps:
        status = 'research_handoff_ready' if mutation == 'ready_with_open_gaps' else 'blocked_support_gap'
    else:
        status = 'research_handoff_ready'
    result = State(request, status)
    return result

def rule(check):

    def invariant(state):
        if state.request is None:
            return True
        problem = check(state, state.request)
        return False if problem else True
    return invariant

def ready_rule(state, request):
    if state.status == 'research_handoff_ready' and (request.open_gaps or not request.valid or request.body_units > request.max_body_units):
        return f'{request.name}: ready although the request is blocked'

def budget_rule(state, request):
    if request.valid and request.body_units > request.max_body_units and (state.status != 'blocked_budget'):
        return f'{request.name}: over budget but {state.status}'

def invalid_rule(state, request):
    if not request.valid and state.status != 'blocked_invalid_request':
        return f'{request.name}: invalid request but {state.status}'
RULES = (rule(ready_rule), rule(budget_rule), rule(invalid_rule))
CASES = (Request('invalid', valid=False), Request('support_gap', open_gaps=1), Request('over_budget', body_units=2, max_body_units=1, open_gaps=1), Request('ready', body_units=2, max_body_units=2))
MUTATIONS = {'ready_with_open_gaps': 'ready_only_without_open_gaps', 'over_budget_ready': 'over_budget_is_blocked_budget', 'invalid_request_ready': 'invalid_request_is_blocked'}

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
    return {'invalid': synthesize_artifact_plan(model, selection_request={}), 'support_gap': synthesize_artifact_plan(model, selection_request=contract._request(model)), 'over_budget': synthesize_artifact_plan(model, selection_request=over), 'ready': ready}

def assert_native_contract():
    observations, violations = ([], [])
    plans = native_plans()
    for request in CASES:
        plan = plans[request.name]
        want = expected_Synthesize(request, State()).status
        actual = State(Request(request.name, request.valid, request.body_units, request.max_body_units, len(plan.open_gaps)), plan.status)
        if plan.status != want:
            violations.append(f'{request.name}: {plan.status} != {want}')
        for invariant in RULES:
            verdict = invariant(actual)
            if not verdict:
                violations.append(f"{request.name}: {invariant.__name__}: {'independent contract rejected the native observation'}")
    assert not violations, violations
RULE_NAMES = ('ready_only_without_open_gaps', 'over_budget_is_blocked_budget', 'invalid_request_is_blocked')
