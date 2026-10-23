"""Shared-id checks and read-only native status projections."""
import copy
import json
from pathlib import Path

import pytest
import yaml

from researchguard.cli import main
from researchguard.research import check_research_tree, load_research, research_status


@pytest.fixture
def folder(tmp_path):
    files = {
        'source.yaml': {'sources': [{'source_id': 's', 'lineage_id': 'lineage-s', 'independence_group': 'lineage-s'}], 'anchors': [{'anchor_id': 'a', 'source_id': 's', 'text': 'Observed text'}]},
        'trace.yaml': {'metadata': {'schema_version': 'researchguard.trace.model.v2'},
                       'sources': [{'source_id': 's', 'lineage_id': 'lineage-s', 'independence_group': 'lineage-s'}], 'evidence': [{'evidence_id': 'a', 'source_id': 's', 'raw_text': 'Observed text'}],
                       'storyline_hypotheses': [{'hypothesis_id': 'h', 'claim': 'Hypothesis'}],
                       'hypothesis_evidence_links': [{'link_id': 'l', 'hypothesis_id': 'h', 'evidence_id': 'a', 'polarity': 'support'}]},
        'logic.yaml': {'model': {'id': 'logic', 'root_claim': 'h'}, 'nodes': {
            'h': {'type': 'Claim', 'text': 'Hypothesis'}, 'E': {'type': 'Evidence', 'text': 'Observed text',
                'provenance': [{'origin_kind': 'external_source', 'source_id': 's', 'locator': 'a', 'quote': 'Observed text'}]}},
                      'edges': []},
        'experiment.json': {'hypothesis_predictions': [{'hypothesis_id': name, 'outcomes_by_experiment': {'e': outcome}}
                                                       for name, outcome in [('h', 'up'), ('other', 'down')]], 'candidate_experiment_ids': ['e']},
        'obs.json': {'observations': [{'experiment_id': 'e', 'observed_outcome': 'up', 'evidence_id': 'a', 'source_ref': 's',
                                       'observed_at': '2026-10-23', 'role': 'construction'}]},
        'research.yaml': {'schema': 'researchguard.research.v1', 'question': 'Which hypothesis fits?', 'root_claim': 'h',
                          'hypotheses': [{'id': 'h', 'text': 'Hypothesis'}, {'id': 'other', 'text': 'Alternative'}],
                          'models': {'source': 'source.yaml', 'trace': 'trace.yaml', 'logic': 'logic.yaml',
                                     'experiment': 'experiment.json', 'experiment_observations': ['obs.json']}},
    }
    for name, data in files.items():
        (tmp_path / name).write_text(json.dumps(data) if name.endswith('.json') else yaml.safe_dump(data), encoding='utf-8')
    return tmp_path


def _rewrite(folder, name, mutate):
    path = folder / name
    data = yaml.safe_load(path.read_text())
    mutate(data)
    path.write_text(json.dumps(data) if name.endswith('.json') else yaml.safe_dump(data))


def test_consistent_tree_has_no_errors(folder, capsys):
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    assert main(['status', str(folder)]) == 0
    text = capsys.readouterr().out
    assert '| h |' in text and '| other |' in text and 'trace:h:support' in text and 'logic:E' in text
    assert before == {p.name: p.read_bytes() for p in folder.iterdir()}
    status = research_status(load_research(folder / 'research.yaml'))
    assert status['errors'] == []
    assert status['hypotheses'][0]['experiment']['status'] == 'consistent'
    assert status['hypotheses'][0]['trace']['hypothesis_id'] == 'h'


@pytest.mark.parametrize('file,mutate,error', [
    ('research.yaml', lambda d: d['hypotheses'].pop(0), 'unknown_hypothesis:trace:h'),
    ('source.yaml', lambda d: d['anchors'].clear(), 'dangling_anchor:trace:a'),
    ('logic.yaml', lambda d: d['nodes']['E']['provenance'][0].update(locator='missing'), 'dangling_anchor:logic:E:missing'),
    ('obs.json', lambda d: d['observations'][0].update(evidence_id='missing', source_ref='missing'), 'dangling_source:experiment:missing'),
    ('research.yaml', lambda d: d.update(root_claim='missing'), 'root_claim_missing:missing'),
    ('research.yaml', lambda d: d['models'].update(trace='missing.yaml'), 'model_missing:trace'),
    ('trace.yaml', lambda d: d.update(metadata={}), 'model_invalid:trace:'),
])
def test_dangling_references_and_invalid_native_models_are_errors(folder, capsys, file, mutate, error):
    _rewrite(folder, file, mutate)
    assert main(['status', str(folder), '--json']) == 1
    status = json.loads(capsys.readouterr().out)
    assert any(error in item for item in status['errors']), status


def test_unused_hypothesis_is_only_a_warning(folder, capsys):
    _rewrite(folder, 'research.yaml', lambda d: d['hypotheses'].append({'id': 'unused', 'text': 'Unused'}))
    assert main(['status', str(folder), '--json']) == 0
    assert 'hypothesis_unused:unused' in json.loads(capsys.readouterr().out)['warnings']


def test_missing_index_exits_2(tmp_path, capsys):
    assert main(['status', str(tmp_path), '--json']) == 2
    assert 'research_index_invalid' in capsys.readouterr().out


def test_checker_is_in_memory_and_source_is_optional(folder, capsys):
    tree = load_research(folder)
    index = copy.deepcopy(tree.index)
    index['models'].pop('source')
    models = {key: value for key, value in tree.models.items() if key != 'source'}
    result = check_research_tree(index, models, tree.observations)
    assert result['errors'] == [] and result['info'] == ['source_model_not_listed']
    output = folder / 'status.json'
    assert main(['status', str(folder), '--json', '--output', str(output)]) == 0
    assert capsys.readouterr().out == ''
    assert json.loads(output.read_text())['question'] == index['question']
