"""Every retained independent rule and original bad version has a direct unit destination."""
import pytest
from .contract_cases import TOPICS, bad_states, cases, expected, module, mutations

RULES = [(topic, name) for topic in TOPICS for name in module(topic).RULE_NAMES]
BAD = [(topic, name, rule) for topic in TOPICS for name, rule in mutations(topic).items()]

@pytest.mark.parametrize('topic', TOPICS)
def test_native_contract(topic):
    module(topic).assert_native_contract()

@pytest.mark.parametrize('topic,name', RULES, ids=[f'{t}:{r}' for t,r in RULES])
def test_independent_rule(topic, name):
    m = module(topic)
    predicate = m.RULES[m.RULE_NAMES.index(name)]
    assert all(predicate(expected(topic, case)) for case in cases(topic)), (topic,name)

@pytest.mark.parametrize('topic,mutation,rule', BAD, ids=[f'{t}:{v}' for t,v,r in BAD])
def test_rejects_original_bad_facts(topic, mutation, rule):
    m = module(topic)
    predicate = m.RULES[m.RULE_NAMES.index(rule)]
    assert any(not predicate(state) for state in bad_states(topic, mutation)), (topic,mutation,rule)
