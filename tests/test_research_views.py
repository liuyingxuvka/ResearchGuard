"""Question status assertions grouped by their independent model aspect."""
import copy
import json
from pathlib import Path
import pytest
import yaml
from researchguard.cli import main
from researchguard.research import check_research_tree, load_research, research_status
from research_tree_support import EVERGIVEN, _rewrite

def test_hypothesis_view_lists_its_rows(capsys):
    assert main(['status', str(EVERGIVEN), '--hypothesis', 'h_yantian']) == 0
    page = capsys.readouterr().out
    for text in ('not in logic', 'not in trace', 'gap-alt-yantian', 'act-yantian', 'e_yantian_timing'):
        assert text in page
    assert main(['status', str(EVERGIVEN), '--hypothesis', 'h_suez', '--json']) == 0
    view = json.loads(capsys.readouterr().out)
    assert {'anchor': 'anc-unctad-surge', 'route': 'trace'} in view['evidence']['oppose']
    assert [row['id'] for row in view['ablations']] == ['question_without_unctad', 'abl_no_unctad']
    assert main(['status', str(EVERGIVEN), '--hypothesis', 'h_missing']) == 2
    assert 'unknown_hypothesis:h_missing' in capsys.readouterr().out
    assert main(['status', str(EVERGIVEN), '--hypothesis', 'h_suez', '--candidate', str(EVERGIVEN)]) == 2
    status = research_status(load_research(EVERGIVEN))
    from researchguard.research import hypothesis_view
    for row in status['hypotheses']:
        view = hypothesis_view(status, row['id'])
        assert view['open_gaps'] == [gap for gap in status['open_gaps'] if row['id'] in gap.get('hypotheses', ())]
        assert [item for item in view['next'] if item['route'] == 'search'] == [
            item for item in status['next'] if item['route'] == 'search' and row['id'] in item['hypotheses']]
    from researchguard.research import render_status_markdown
    lines = render_status_markdown(status).splitlines()
    at = lines.index('## Disagreements')
    assert lines[at + 1] == '' and lines[at + 2] == '- none'

def test_candidate_view_shows_verdict_changes(tmp_path, capsys):
    import shutil
    from researchguard.research import compare_research_status
    candidate = tmp_path / 'candidate'
    shutil.copytree(EVERGIVEN, candidate)
    removed = {('R_pretrend', 'attacks'), ('h_demand', 'contradicts')}
    _rewrite(candidate, 'logic.yaml', lambda d: d.update(edges=[e for e in d['edges'] if not (e['target'] == 'h_suez' and (e['source'], e['type']) in removed)]))
    changes = compare_research_status(research_status(load_research(EVERGIVEN)), research_status(load_research(candidate)))['changes']
    assert any(row['kind'] == 'verdict' and row['id'] == 'root_claim.reason' for row in changes)
    suez = next(row for row in changes if row['kind'] == 'hypothesis' and row['id'] == 'h_suez')
    assert suez['before'] == {'logic': {'confidence': 0.25}} and suez['after'] == {'logic': {'confidence': 0.4}}
    assert main(['status', str(EVERGIVEN), '--candidate', str(candidate)]) == 0
    page = capsys.readouterr().out
    assert '- h_suez: logic confidence 0.25 → 0.40' in page and '- verdict root_claim.reason: ' in page
    assert '0.332256954214' not in page
