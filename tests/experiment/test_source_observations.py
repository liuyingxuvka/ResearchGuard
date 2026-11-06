"""Real root entry: captured literals constrain labels; interpretations stay declared."""
import json

import pytest
import yaml

from researchguard.cli import main


def _folder(tmp_path, quote='The reading is 6.0.', labels=('6.0', '9.0'), table=None):
    project = tmp_path / 'research'
    project.mkdir()
    source = {'sources': [{'source_id': 's', 'title': 'Meter trial'}],
              'anchors': [{'anchor_id': 'a', 'source_id': 's', 'text': quote}]}
    logic = {'model': {'id': 'logic', 'root_claim': 'h'}, 'nodes': {
        'h': {'type': 'Claim', 'text': 'The recorded result applies to this trial.'},
        'E': {'type': 'Evidence', 'text': quote, 'provenance': [
            {'origin_kind': 'external_source', 'source_id': 's', 'locator': 'a', 'quote': quote}]}},
        'edges': [{'source': 'E', 'target': 'h', 'type': 'supports'}]}
    index = {'schema': 'researchguard.research.v1', 'question': 'Which recorded result fits this trial?',
             'root_claim': 'h', 'hypotheses': [{'id': 'h', 'text': 'Recorded result'}, {'id': 'other', 'text': 'Other result'}],
             'models': {'source': 'source.yaml', 'logic': 'logic.yaml', 'experiment': 'experiment.json',
                        'experiment_observations': ['obs.json']},
             'search': {'budget': 3, 'scope_sufficient': False}}
    for name, value in [('source.yaml', source), ('logic.yaml', logic), ('research.yaml', index)]:
        (project / name).write_text(yaml.safe_dump(value), encoding='utf-8')
    spec = {'hypothesis_predictions': [{'hypothesis_id': name, 'outcomes_by_experiment': {'e': outcome}}
                                      for name, outcome in zip(('h', 'other'), labels)], 'candidate_experiment_ids': ['e']}
    (project / 'experiment.json').write_text(json.dumps(spec), encoding='utf-8')
    _outcome(project, labels[0])
    original = tmp_path / ('original.csv' if table is not None else 'original.txt')
    original.write_text(table if table is not None else quote, encoding='utf-8')
    assert main(['source', 'capture', 's', '--project', str(project), '--file', str(original)]) == 0
    return project


def _outcome(project, label):
    row = {'experiment_id': 'e', 'observed_outcome': label, 'evidence_id': 'a', 'source_ref': 's',
           'observed_at': '2026-11-06', 'role': 'construction'}
    (project / 'obs.json').write_text(json.dumps({'observations': [row]}), encoding='utf-8')


def _status(project, capsys):
    capsys.readouterr()
    code = main(['status', str(project), '--json'])
    return code, json.loads(capsys.readouterr().out)


@pytest.mark.parametrize('table,quote,labels', [
    (None, 'The reading is 6.0.', ('6.0', '9.0')),
    ('trial,value\nsample,6.0\n', 'sample: 6.0', ('6.0', '9.0')),
    ('trial,status\nsample,open\n', 'sample: open', ('open', 'closed')),
    (None, 'open', ('open', 'closed')),
])
def test_stop_sufficient_same_green_capture_does_not_license_a_changed_literal(tmp_path, capsys, table, quote, labels):
    project = _folder(tmp_path, quote, labels, table)
    code, original = _status(project, capsys)
    assert code == 0, original['errors']
    assert original['verdict']['search'] == 'stop_sufficient'
    assert original['verdict']['root_claim']['wording_license'] == 'assert'
    assert original['experiment_observation_checks'][0]['colour'] == 'green'
    assert original['source_readings'][0]['colour'] == 'green'
    _outcome(project, labels[1])
    code, changed = _status(project, capsys)
    assert changed['source_readings'] == original['source_readings']
    assert changed['verdict']['search'] == 'stop_sufficient'
    assert changed['verdict']['root_claim']['wording_license'] == 'assert'
    assert code == 1
    assert 'experiment_outcome_disagrees:e:a' in changed['errors']
    assert changed['experiment_observation_checks'][0]['colour'] == 'red'


@pytest.mark.parametrize('quote,labels,reason', [
    ('The reading rose to 6.0.', ('rose', 'fell'), 'caller-declared'),
    ('A is 6.0 and B is 9.0.', ('6.0', '9.0'), 'caller-declared'),
    ('The reading is 6.0.', ('6', '6.0'), 'multiple labels'),
])
def test_unread_or_ambiguous_mapping_remains_caller_declared(tmp_path, capsys, quote, labels, reason):
    project = _folder(tmp_path, quote, labels)
    code, report = _status(project, capsys)
    assert code == 0, report['errors']
    row = report['experiment_observation_checks'][0]
    assert row['colour'] == 'grey' and row['basis'] == 'caller_declared'
    assert reason in row['reason']
    assert report['verdict']['search'] == 'stop_sufficient'


def test_standalone_declared_selector_keeps_its_use_and_names_observation_boundary(tmp_path, capsys):
    project = _folder(tmp_path, 'The reading rose to 6.0.', ('rose', 'fell'))
    capsys.readouterr()
    assert main(['experiment', 'observe', str(project / 'experiment.json'), str(project / 'obs.json')]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['terminal_reason'] == 'model_closed_for_task'
    assert result['observation_basis'] == 'caller_declared'
    assert 'does not independently measure' in result['claim_boundary']


def test_capture_change_still_blocks_root_without_claiming_observation_verification(tmp_path, capsys):
    project = _folder(tmp_path)
    original = project / 'captures/s.txt'
    original.write_text('Changed original', encoding='utf-8')
    code, report = _status(project, capsys)
    assert code == 1 and 'capture_changed:s' in report['errors']
    assert report['source_readings'][0]['colour'] == 'red'
    assert report['experiment_observation_checks'][0]['colour'] == 'grey'


def test_root_and_focused_text_keep_the_declared_observation_boundary(tmp_path, capsys):
    project = _folder(tmp_path, 'The reading rose to 6.0.', ('rose', 'fell'))
    for extra in ([], ['--hypothesis', 'h']):
        capsys.readouterr()
        assert main(['status', str(project), *extra]) == 0
        text = capsys.readouterr().out
        assert 'Experiment observation basis' in text
        assert 'caller_declared' in text and 'no unique captured literal' in text
