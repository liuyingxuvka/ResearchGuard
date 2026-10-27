"""Question status assertions grouped by their independent model aspect."""
import copy
import json
from pathlib import Path
import pytest
import yaml
from researchguard.cli import main
from researchguard.research import check_research_tree, load_research, research_status
from research_tree_support import EVERGIVEN, _rewrite, folder

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

def test_live_hypotheses_follow_every_route(folder):
    def index(data):
        data['hypotheses'] = [{'id': name, 'text': name.title()} for name in ('h', 'out', 'dead', 'other')]

    def logic(data):
        data['nodes']['out'] = {'type': 'Claim', 'text': 'Out'}
        data['nodes']['dead'] = {'type': 'Claim', 'text': 'Dead'}
        data['nodes']['other'] = {'type': 'Claim', 'text': 'Other'}
        data['nodes']['M'] = {'type': 'Premise', 'text': 'A premise the out hypothesis needs', 'missing': True}
        data['edges'].append({'source': 'M', 'target': 'out', 'type': 'supports'})

    def trace(data):
        data['storyline_hypotheses'].append({'hypothesis_id': 'dead', 'claim': 'Dead'})
        data['hypothesis_evidence_links'].append({'link_id': 'l-dead', 'hypothesis_id': 'dead', 'evidence_id': 'a', 'polarity': 'oppose'})

    _rewrite(folder, 'research.yaml', index)
    _rewrite(folder, 'logic.yaml', logic)
    _rewrite(folder, 'trace.yaml', trace)
    status = research_status(load_research(folder))
    rows = {row['id']: row for row in status['hypotheses']}
    assert rows['out']['logic']['state'] == 'OUT'
    assert rows['dead']['trace']['live'] is False
    assert rows['other']['experiment']['status'] == 'eliminated'
    assert status['verdict']['live_hypotheses'] == ['h']
    assert status['verdict']['contested'] is bool(status['disagreements'])
    from researchguard.research import route_disagreements, verdict_for_writers
    tree = load_research(folder)
    accepted_and_excluded = [dict(rows['h'], logic={'state': 'IN'}, trace={'live': False})]
    disagreements = route_disagreements({}, accepted_and_excluded)
    assert disagreements and verdict_for_writers(tree, accepted_and_excluded, disagreements, [])['contested'] is True

def test_evidence_directions_cover_both_routes():
    status = research_status(load_research(EVERGIVEN))
    row = next(item for item in status['evidence'] if item['anchor'] == 'anc-unctad-surge')
    assert {'route': 'logic', 'hypothesis': 'h_demand', 'direction': 'support', 'node': 'E_pretrend'} in row['directions']
    assert {'route': 'trace', 'hypothesis': 'h_suez', 'direction': 'oppose', 'node': None} in row['directions']
    assert row['directions'] == sorted(row['directions'], key=lambda item: (item['route'], item['hypothesis'], item['direction']))
    assert 'logic:E_pretrend' in row['used_by']

def test_writer_surface_keys_are_pinned(tmp_path):
    """The keys LogicWriting reads from status --json; they do not change."""
    source_only = tmp_path / 'source-only'
    source_only.mkdir()
    (source_only / 'source.yaml').write_text(yaml.safe_dump({'sources': [{'source_id': 's'}], 'anchors': [{'anchor_id': 'a', 'source_id': 's', 'text': 'Observed text'}]}))
    (source_only / 'research.yaml').write_text(yaml.safe_dump({'schema': 'researchguard.research.v1', 'question': 'Only sources?',
                                                               'hypotheses': [{'id': 'h', 'text': 'Hypothesis'}], 'models': {'source': 'source.yaml'}}))
    for folder in (EVERGIVEN, source_only):
        tree = load_research(folder)
        status = research_status(tree)
        assert {'question', 'verdict', 'hypotheses', 'models', 'evidence'} <= set(status)
        assert status['question'] == tree.index['question']
        assert [(row['id'], row['text']) for row in status['hypotheses']] == [(row['id'], row['text']) for row in tree.index['hypotheses']]
        assert {route: row['path'] for route, row in status['models'].items()} == {
            route: path for route, path in tree.index['models'].items() if route != 'experiment_observations'}
        assert all(set(row) == {'path', 'status'} for row in status['models'].values())
        assert {row['anchor'] for row in status['evidence']} == {row.anchor_id for row in tree.models['source'].anchors}
        for row in status['evidence']:
            for item in row['directions']:
                assert set(item) == {'route', 'hypothesis', 'direction', 'node'} and item['direction'] in {'support', 'oppose', 'limit'}
        assert set(status['verdict']) == {'search', 'root_claim', 'live_hypotheses', 'contested', 'errors'}
