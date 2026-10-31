"""Question status assertions grouped by their independent model aspect."""
import copy
import json
from pathlib import Path
import pytest
import yaml
from researchguard.cli import main
from researchguard.research import check_research_tree, load_research, research_status
from research_tree_support import _rewrite, folder

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

def test_status_names_a_non_index_error(folder, capsys, monkeypatch):
    def fail(tree):
        raise TypeError('probe')

    monkeypatch.setattr('researchguard.research.research_status', fail)
    assert main(['status', str(folder)]) == 2
    errors = json.loads(capsys.readouterr().out)['errors']
    assert errors == [f'research_status_failed: {folder / "research.yaml"}: TypeError: probe (research.yaml was read; this is a ResearchGuard defect)']
    assert 'create research.yaml first' not in errors[0]

def _add_unanchored_evidence(candidate, hypothesis):
    def add_reference(data):
        data['nodes']['E_lloyds'] = {'type': 'Evidence',
            'text': "Lloyd's List: the blockage alone doubled Asia-Europe spot rates in April 2021.",
            'confidence': 0.85, 'scope': 'Asia-Europe spot rates, 2021',
            'provenance': [{'origin_kind': 'external_source', 'source_reference': "Lloyd's List, April 2021",
                            'quote': 'The Suez blockage alone doubled Asia-Europe spot rates in April 2021.'}]}
        data['edges'].append({'source': 'E_lloyds', 'target': hypothesis, 'type': 'supports', 'weight': 0.9})

    _rewrite(candidate, 'logic.yaml', add_reference)

@pytest.fixture
def unanchored_folder(tmp_path):
    import shutil
    from research_tree_support import EVERGIVEN
    candidate = tmp_path / 'unanchored'
    shutil.copytree(EVERGIVEN, candidate)
    _add_unanchored_evidence(candidate, 'h_suez')
    return candidate

def test_unanchored_logic_evidence_is_an_error_with_a_source_model(unanchored_folder, capsys):
    from research_tree_support import EVERGIVEN
    error = 'evidence_not_in_source:logic:E_lloyds (its provenance names no source_id; add the anchor with researchguard source add-anchor, then run researchguard sync <folder>)'
    assert main(['status', str(unanchored_folder), '--json']) == 1
    assert json.loads(capsys.readouterr().out)['errors'] == [error]
    assert main(['status', str(EVERGIVEN), '--candidate', str(unanchored_folder)]) == 1
    assert f'- errors added: {error}' in capsys.readouterr().out

def test_unanchored_logic_evidence_is_listed_without_a_source_model(folder, capsys):
    _add_unanchored_evidence(folder, 'h')
    _rewrite(folder, 'research.yaml', lambda data: data['models'].pop('source'))
    assert main(['status', str(folder), '--json']) == 0
    status = json.loads(capsys.readouterr().out)
    assert status['errors'] == []
    assert 'evidence_unanchored:logic:E_lloyds' in status['info']

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
    import hashlib
    external = folder.parent / 'external-library'
    library.root.rename(external)
    _rewrite(folder, 'research.yaml', lambda d: d.update(library='../external-library'))
    status = research_status(load_research(folder))
    digests = {row['path']: row['sha256'] for row in status['input_digests']}
    expected_library = ['../external-library/index/sources.json',
                        '../external-library/source_models/' + library.source_model_path(imported.source.source_id).name]
    assert sorted(digests) == sorted(['research.yaml', 'source.yaml', 'logic.yaml', *expected_library])
    assert all(digest == hashlib.sha256((folder / path).read_bytes()).hexdigest() for path, digest in digests.items())


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

def test_gap_hypotheses_are_checked_and_grouped(tmp_path, capsys):
    import shutil
    original = Path(__file__).resolve().parents[1] / 'examples/research/evergiven'
    status = research_status(load_research(original))
    gap = next(row for row in status['open_gaps'] if row.get('id') == 'gap-alt-yantian')
    search = next(row for row in status['next'] if row.get('id') == 'act-yantian')
    assert gap['hypotheses'] == ['h_yantian'] and search['hypotheses'] == ['h_yantian']
    folder = tmp_path / 'research'
    shutil.copytree(original, folder)

    def dangle(data):
        next(row for row in data['gaps'] if row['gap_id'] == 'gap-alt-yantian')['hypothesis_ids'] = ['h_missing']
    _rewrite(folder, 'source.yaml', dangle)
    assert main(['status', str(folder), '--json']) == 1
    assert 'unknown_hypothesis:source:gap-alt-yantian:h_missing' in json.loads(capsys.readouterr().out)['errors']

def test_missing_index_names_the_template(tmp_path, capsys):
    assert main(['status', str(tmp_path)]) == 2
    assert 'Start a question' in capsys.readouterr().out


def test_status_reports_input_digests(tmp_path):
    import hashlib
    import shutil
    from research_tree_support import EVERGIVEN
    folder = tmp_path / 'research'
    shutil.copytree(EVERGIVEN, folder)
    status = research_status(load_research(folder))
    paths = ['exp-obs1.json', 'experiment.json', 'logic.yaml', 'research.yaml', 'source.yaml', 'trace.yaml']
    assert status['input_digests'] == [{'path': path, 'sha256': hashlib.sha256((folder / path).read_bytes()).hexdigest()} for path in paths]
    original = {row['path']: row['sha256'] for row in status['input_digests']}
    source = folder / 'source.yaml'
    source.write_bytes(source.read_bytes() + b'\n')
    changed = {row['path']: row['sha256'] for row in research_status(load_research(folder))['input_digests']}
    assert [key for key in paths if original[key] != changed[key]] == ['source.yaml']
