"""One folder sync preserves reasoning, and conflicts preserve all input bytes."""
import json
import shlex
import shutil

import yaml

from researchguard.cli import main
from researchguard.research import compare_research_status, load_research, research_status
from research_tree_support import EVERGIVEN


def _files(folder):
    return {str(path.relative_to(folder)): path.read_bytes() for path in folder.rglob('*') if path.is_file()}


def test_sync_of_the_synced_example_changes_nothing(tmp_path, capsys):
    folder = tmp_path / 'same folder'
    shutil.copytree(EVERGIVEN, folder)
    before = _files(folder)
    assert main(['sync', str(folder)]) == 0
    assert _files(folder) == before
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == 'sync: trace evidence added [] updated []; logic nodes added [] updated []; conflicts []'
    assert shlex.split(lines[1].removeprefix('next: ')) == ['researchguard', 'status', str(folder.resolve())]
    assert lines[2].startswith('note: To compare, pass the unchanged current folder')


def test_sync_after_add_anchor_adds_only_that_anchor(tmp_path, capsys):
    folder = tmp_path / 'added'
    shutil.copytree(EVERGIVEN, folder)
    assert main(['source', 'add-anchor', str(folder / 'source.yaml'), '--source-id', 'src-lloyds',
                 '--anchor-id', 'anc-lloyds', '--quote', 'The Suez blockage alone doubled Asia-Europe spot rates in April 2021.',
                 '--locator', "Lloyd's List, April 2021", '--output', str(folder / 'source.yaml')]) == 0
    capsys.readouterr()
    source, index = (folder / 'source.yaml').read_bytes(), (folder / 'research.yaml').read_bytes()
    assert main(['sync', str(folder)]) == 0
    assert (folder / 'source.yaml').read_bytes() == source
    assert (folder / 'research.yaml').read_bytes() == index
    changes = compare_research_status(research_status(load_research(EVERGIVEN)), research_status(load_research(folder)))['changes']
    assert changes == [{'kind': 'evidence', 'id': 'anc-lloyds', 'change': 'added'}]


def test_sync_conflict_writes_nothing(tmp_path, capsys):
    folder = tmp_path / 'conflict'
    shutil.copytree(EVERGIVEN, folder)
    path = folder / 'trace.yaml'
    trace = yaml.safe_load(path.read_text())
    evidence = trace['evidence'][0]
    evidence['source_id'] = next(row['source_id'] for row in trace['sources'] if row['source_id'] != evidence['source_id'])
    path.write_text(yaml.safe_dump(trace, sort_keys=False))
    before = _files(folder)
    assert main(['sync', str(folder)]) == 1
    assert _files(folder) == before
    assert json.loads(capsys.readouterr().out)['errors'][0].startswith('sync_conflict: ')


def test_sync_rejects_incomplete_outside_and_aliased_paths_before_loading(tmp_path, capsys, monkeypatch):
    def must_not_load(path):
        raise AssertionError('member model loaded before path validation')

    monkeypatch.setattr('researchguard.research.load_source', must_not_load)
    outside = tmp_path / 'outside.yaml'
    outside.write_bytes((EVERGIVEN / 'logic.yaml').read_bytes())
    for case in ('missing', 'outside_logic', 'aliased_source_trace'):
        folder = tmp_path / case
        shutil.copytree(EVERGIVEN, folder)
        index_path = folder / 'research.yaml'
        index = yaml.safe_load(index_path.read_text())
        if case == 'missing':
            index['models'].pop('logic')
        elif case == 'outside_logic':
            index['models']['logic'] = '../outside.yaml'
        else:
            index['models']['trace'] = index['models']['source']
        index_path.write_text(yaml.safe_dump(index, sort_keys=False))
        before, outside_before = _files(folder), outside.read_bytes()
        assert main(['sync', str(folder)]) == 2
        errors = json.loads(capsys.readouterr().out)['errors']
        if case == 'missing':
            assert errors == ['sync_needs_models: research.yaml must list source, trace and logic models']
        else:
            assert errors[0].startswith('sync_invalid_folder: ')
        assert _files(folder) == before and outside.read_bytes() == outside_before
