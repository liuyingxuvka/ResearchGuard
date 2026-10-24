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


def test_shipped_evergiven_tree_has_consistent_shared_ids(capsys):
    folder = Path(__file__).resolve().parents[1] / 'examples/research/evergiven'
    assert main(['status', str(folder), '--json']) == 0
    status = json.loads(capsys.readouterr().out)
    assert status['errors'] == []
    assert {row['id'] for row in status['hypotheses']} == {'h_suez', 'h_demand', 'h_yantian'}
    assert any(row['anchor'] == 'anc-transpacific' for row in status['evidence'])
    assert status['warnings'] == ['hypothesis_not_in_logic:h_yantian']


def test_one_observation_reaches_trace_and_logic_by_sync(tmp_path, capsys):
    import shutil
    from researchguard.source.loader import load_model, write_yaml
    from researchguard.source.schema import Observation, EvidenceAnchor
    from researchguard.source.update import apply_observation
    original = Path(__file__).resolve().parents[1] / 'examples/research/evergiven'
    folder = tmp_path / 'research'
    shutil.copytree(original, folder)
    source_path = folder / 'source.yaml'
    source = apply_observation(load_model(source_path), Observation(
        observation_id='obs-extra', observed_anchors=[EvidenceAnchor(
            anchor_id='anc-extra', source_id='src-wci-transpacific',
            text='An additional recorded observation for the same public-data example.',
            locator='Extra illustrative row', usable_for_claim=True)]))
    write_yaml(source_path, source)
    trace_path = folder / 'trace-next.yaml'
    assert main(['source', 'export-traceguard', str(source_path), '--into', str(folder / 'trace.yaml'), '--output', str(trace_path)]) == 0
    trace = yaml.safe_load(trace_path.read_text())
    trace['hypothesis_evidence_links'].append({'link_id': 'l-extra', 'hypothesis_id': 'h_demand',
        'evidence_id': 'anc-extra', 'polarity': 'support', 'declared_relevance': .5,
        'rationale': 'Illustrates an explicit human/AI linking judgment after sync.'})
    trace_path.write_text(yaml.safe_dump(trace))
    bundle, logic = folder / 'bundle.yaml', folder / 'logic-next.yaml'
    assert main(['trace', 'export-logicguard', str(trace_path), '--output', str(bundle)]) == 0
    assert main(['logic', 'import-handoff', str(bundle), '--into', str(folder / 'logic.yaml'), '--output', str(logic)]) == 0
    raw_logic = yaml.safe_load(logic.read_text())
    assert raw_logic['nodes']['anc-extra']['provenance'][0]['source_id'] == 'src-wci-transpacific'
    index_path = folder / 'research.yaml'
    index = yaml.safe_load(index_path.read_text())
    index['models'].update(trace=trace_path.name, logic=logic.name)
    index_path.write_text(yaml.safe_dump(index))
    capsys.readouterr()
    assert main(['status', str(folder), '--json']) == 0
    status = json.loads(capsys.readouterr().out)
    extra = next(row for row in status['evidence'] if row['anchor'] == 'anc-extra')
    assert 'trace:h_demand:support' in extra['used_by'] and 'logic:anc-extra' in extra['used_by']


@pytest.mark.parametrize('route,field,code', [
    ('trace', 'raw_text', 'copy_drift:trace:a:raw_text'),
    ('trace_source', 'title', 'copy_drift:trace:s:title'),
    ('trace_source', 'url', 'copy_drift:trace:s:url'),
    ('trace_source', 'source_date', 'copy_drift:trace:s:source_date'),
    ('trace_source', 'lineage_id', 'copy_drift:trace:s:lineage_id'),
    ('logic', 'quote', 'copy_drift:logic:E:quote'),
    ('logic', 'content_hash', 'copy_drift:logic:E:content_hash'),
    ('logic', 'source_reference', 'copy_drift:logic:E:source_reference'),
    ('logic', 'source_date', 'copy_drift:logic:E:source_date'),
])
def test_copy_drift_is_an_error_for_each_copied_field(folder, route, field, code):
    def drift(data):
        if route == 'trace':
            row = data['evidence'][0]
        elif route == 'trace_source':
            row = data['sources'][0]
        else:
            row = data['nodes']['E']['provenance'][0]
            if field == 'content_hash':
                row.pop('quote')
        row[field] = 'sha256:' + '0' * 64 if field == 'content_hash' else '2026-10-24' if field == 'source_date' else 'Different copied value'
    _rewrite(folder, 'logic.yaml' if route == 'logic' else 'trace.yaml', drift)
    tree = load_research(folder)
    assert code in check_research_tree(tree.index, tree.models, tree.observations)['errors']


def test_library_anchored_evidence_gets_one_answer(folder):
    from researchguard.logic.source_library import SourceLibrary
    from researchguard.logic.validator import source_model_provenance_problems
    from researchguard.source.schema import to_plain
    paper = folder / 'paper.txt'
    paper.write_text('Observed text')
    library = SourceLibrary(folder / 'library')
    imported = library.import_source(paper, title='Paper')
    library.create_source_model(imported.source.source_id, evidence='Observed text')
    node = sorted(library.source_node_ids(imported.source.source_id))[0]
    _rewrite(folder, 'source.yaml', lambda d: d.update(sources=[{'source_id': imported.source.source_id}], anchors=[]))
    _rewrite(folder, 'logic.yaml', lambda d: d['nodes']['E']['provenance'][0].update(source_id=imported.source.source_id, locator=node))
    _rewrite(folder, 'research.yaml', lambda d: d.update(library='library', models={'source': 'source.yaml', 'logic': 'logic.yaml'}))
    tree = load_research(folder)
    expected = source_model_provenance_problems(tree.models['logic'], to_plain(tree.models['source']), source_library=tree.library)
    assert expected == []
    assert check_research_tree(tree.index, tree.models, source_library=tree.library)['errors'] == []
    without = check_research_tree(tree.index, tree.models)
    assert any(item.startswith('dangling_anchor:logic:E:') for item in without['errors'])
    assert without['errors'] == source_model_provenance_problems(tree.models['logic'], to_plain(tree.models['source']))


def test_opposite_anchor_directions_are_a_disagreement(folder):
    from researchguard.research import route_disagreements
    _rewrite(folder, 'logic.yaml', lambda d: d['edges'].append({'source': 'E', 'target': 'h', 'type': 'attacks'}))
    tree = load_research(folder)
    rows = route_disagreements(tree.models, [])
    assert rows == [{'hypothesis': 'h', 'kind': 'anchor', 'detail': 'a'}]


def test_ruled_out_and_accepted_is_a_disagreement():
    from researchguard.research import route_disagreements
    rows = route_disagreements({}, [{'id': 'h', 'logic': {'state': 'IN'}, 'trace': {'live': False}, 'experiment': {'status': 'consistent'}}])
    assert rows and rows[0]['hypothesis'] == 'h' and rows[0]['kind'] == 'status'
    assert route_disagreements({}, [{'id': 'h', 'logic': {'state': 'UNDECIDED'}, 'experiment': {'status': 'consistent'}}]) == []


def test_ablation_nobody_uses_is_named(folder):
    from researchguard.research import apply_ablations
    tree = load_research(folder)
    index = copy.deepcopy(tree.index)
    index['ablations'] = [{'id': 'unused', 'remove_anchors': ['a'], 'hypothesis': 'h', 'expect': 'weaken'}]
    rows, errors, warnings = apply_ablations(index, tree.models, {})
    assert not errors and rows[0]['caught_by'] == []
    assert warnings == ['ablation_not_caught:unused']
    index['ablations'].append(dict(index['ablations'][0]))
    assert 'duplicate_ablation:unused' in apply_ablations(index, tree.models, {})[1]
    index['ablations'] = [{'id': 'bad', 'remove_anchors': ['missing'], 'hypothesis': 'h', 'expect': 'weaken'}]
    assert 'unknown_anchor:ablation:bad:missing' in apply_ablations(index, tree.models, {})[1]


def test_verdict_matches_each_route_and_page_is_readable():
    from researchguard.logic.minimal_sets import license_model_claim
    from researchguard.research import render_status_markdown
    from researchguard.source.stop_decision import decide_model_search_stop
    original = Path(__file__).resolve().parents[1] / 'examples/research/evergiven'
    tree = load_research(original)
    status = research_status(tree)
    verdict = status['verdict']
    assert set(verdict) == {'search', 'root_claim', 'live_hypotheses', 'contested', 'errors'}
    assert verdict['root_claim']['wording_license'] == license_model_claim(tree.models['logic'], 'h_suez').wording_license == 'withhold'
    assert verdict['search'] == decide_model_search_stop(tree.models['source'], remaining_budget=3)[1].status == 'continue_search'
    assert verdict['live_hypotheses'] == ['h_demand', 'h_yantian']
    assert verdict['contested'] is False and verdict['errors'] == 0
    assert status['disagreements'] == []
    assert status['ablations'] and all(row['caught_by'] for row in status['ablations'])
    page = render_status_markdown(status)
    assert len(page.encode()) <= 3000
    assert '{' not in page
    assert page.split('## ', 1)[1].startswith('Verdict')
    lines = page.splitlines()
    for index, line in enumerate(lines):
        if line.startswith('|---'):
            assert line.count('|') == lines[index - 1].count('|')


def test_candidate_view_lists_only_changes(folder, capsys):
    from researchguard.research import compare_research_status
    status = research_status(load_research(folder))
    assert compare_research_status(status, copy.deepcopy(status))['changes'] == []
    candidate = copy.deepcopy(status)
    candidate['hypotheses'][0]['logic']['state'] = 'OUT'
    changes = compare_research_status(status, candidate)['changes']
    assert len(changes) == 1 and changes[0]['kind'] == 'hypothesis' and changes[0]['id'] == 'h'
    assert main(['status', str(folder), '--candidate', str(folder)]) == 0
    assert capsys.readouterr().out == '## Current and candidate\n\nno changes\n'
