"""Finite shared lifecycle boundaries replayed against the actual kernel."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
EXPECTED = {'stale': True, 'same_path': True, 'same_content': True, 'stalled': 'progress_stalled', 'limit': 'iteration_limit'}

@dataclass(frozen=True)
class State:
    case: str = ''
    outcome: object = None

def expected_Check(case, state, mutation=''):
    value = EXPECTED[case]
    if case == mutation:
        value = False if isinstance(value, bool) else 'continue_iteration'
    return State(case, value)

def rule(cases):

    def check(state):
        if state.case in cases and state.outcome != EXPECTED[state.case]:
            return False
        return True
    return check
RULES = (rule(('stale',)), rule(('same_path', 'same_content')), rule(('stalled',)), rule(('limit',)))

def assert_native_contract():
    from researchguard.iteration import baseline_identity, require_prediction_identity, validate_candidate, select_terminal
    observed = {}
    try:
        require_prediction_identity(baseline_identity({'x': 1}), baseline_identity({'x': 2}))
    except ValueError as exc:
        observed['stale'] = str(exc).startswith('stale_prediction: re-freeze')
    with TemporaryDirectory() as directory:
        current, candidate = (Path(directory) / 'current', Path(directory) / 'candidate')
        current.write_text('untouched')
        for case, path, plain in (('same_path', current, {'x': 2}), ('same_content', candidate, {'x': 1})):
            try:
                validate_candidate(current, path, {'x': 1}, plain)
            except ValueError:
                observed[case] = current.read_text() == 'untouched' and (not candidate.exists())
    observed['stalled'] = select_terminal(stalled=True)
    observed['limit'] = select_terminal(iteration=1, max_iterations=1)
    violations = tuple((f'{case}: {observed.get(case)!r}' for case in EXPECTED if observed.get(case) != EXPECTED[case]))
    assert not violations, violations
RULE_NAMES = ('stale_prediction_is_refused', 'candidate_never_overwrites_current', 'no_progress_is_stalled', 'limit_stops_iteration')
