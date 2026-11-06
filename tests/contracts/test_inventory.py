"""Static migration coverage and the nine old system route ownership contracts."""
from contextlib import closing
from flowguard.structure import build
import json
from pathlib import Path
import pytest
from .contract_cases import TOPICS, module, mutations
ROOT = Path(__file__).resolve().parents[2]
COVERAGE = json.loads(Path(__file__).with_name('coverage.json').read_text())


@pytest.fixture(scope='module')
def generated_map():
    with closing(build(ROOT)) as graph:
        yield graph


def test_each_original_rule_variant_and_production_binding_has_a_destination(generated_map):
    rows = COVERAGE['models']
    assert len(rows) == len(TOPICS) == 13
    assert sum(len(row['rules']) for row in rows) == 50
    assert sum(len(row['bad_variants']) for row in rows) == 55
    assert sum(len(rule['production_tests']) for row in rows for rule in row['rules']) == 74
    for row in rows:
        contract = module(row['topic'])
        assert [rule['id'] for rule in row['rules']] == list(contract.RULE_NAMES)
        assert {v['id']:v['rule'] for v in row['bad_variants']} == mutations(row['topic'])
        for rule in row['rules']:
            for binding in rule['production_tests']:
                path, _, name = binding.partition(':')
                definitions = {node['qual'].split('.')[-1] for node in generated_map.tests() if node['file'] == path}
                assert name in definitions, binding


@pytest.mark.parametrize('route', COVERAGE['system_routes'], ids=lambda row: row['id'])
def test_system_route_anchors(route, generated_map):
    assert route['source_anchors'], route['id']
    for anchor in route['source_anchors']:
        path, _, name = anchor.partition(':')
        definitions = {node['qual'] for node in generated_map.functions().values() if node['file'] == path}
        assert name in definitions, anchor
