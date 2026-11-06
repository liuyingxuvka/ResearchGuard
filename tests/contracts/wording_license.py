"""A wording license cannot outrun native support, blockers or claim state."""
from dataclasses import dataclass, replace
from pathlib import Path

@dataclass(frozen=True)
class State:
    case: str = ''
    license: str = 'withhold'
    support: bool = False
    blocker: bool = False
    claim_state: str = 'UNDECIDED'
CASES = (State('blocked', 'withhold', False, True, 'OUT'), State('unsupported', 'withhold', False, False, 'UNDECIDED'), State('qualified', 'qualify', True, True, 'IN'), State('supported', 'assert', True, False, 'IN'))

def expected_License(case, state, mutation=''):
    result = replace(case, license='assert') if mutation == case.case else case
    return result

def blocked(state):
    if state.case == 'blocked' and state.license != 'withhold':
        return False
    return True

def support(state):
    if state.license == 'assert' and (not state.support or state.blocker):
        return False
    return True

def strength(state):
    if state.case == 'qualified' and state.license == 'assert' or (state.claim_state != 'IN' and state.license != 'withhold'):
        return False
    return True
RULES = (blocked, support, strength)

def assert_native_contract():
    from researchguard.logic.loader import load_model, load_model_from_dict
    from researchguard.logic.minimal_sets import license_model_claim
    root = Path(__file__).resolve().parents[2]
    qualified = load_model_from_dict({'model': {'id': 'qualified', 'root_claim': 'C'}, 'nodes': {'C': {'type': 'Claim', 'text': 'claim', 'confidence': 0.8}, 'E': {'type': 'Evidence', 'text': 'support', 'confidence': 0.9}, 'R': {'type': 'Rebuttal', 'text': 'counter', 'confidence': 0.9, 'active': False}}, 'edges': [{'source': 'E', 'target': 'C', 'type': 'supports', 'weight': 0.9}, {'source': 'R', 'target': 'C', 'type': 'attacks', 'weight': 0.9}], 'acceptance': {'C': {'any_of': ['E'], 'no_undefeated_rebuttal': True}}})
    unsupported = load_model_from_dict({'model': {'id': 'unsupported'}, 'nodes': {'C': {'type': 'Claim', 'text': 'claim'}}, 'edges': []})
    fixtures = ((load_model(root / 'tests/logic/fixtures/evergiven/lg_v1.yaml'), 'C0'), (unsupported, 'C'), (qualified, 'C'), (load_model(root / 'examples/logic/structured_artifact_deck.yaml'), 'C1'))
    observations, violations = ([], [])
    for case, (model, claim) in zip(CASES, fixtures):
        actual = license_model_claim(model, claim)
        if actual.wording_license != case.license:
            violations.append(f'{case.case}: {actual.wording_license} != {case.license}')
    assert not violations, violations
RULE_NAMES = ('blocked_claim_is_withheld', 'assert_needs_support_and_no_blocker', 'license_never_exceeds_state')
