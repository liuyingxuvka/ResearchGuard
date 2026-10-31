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

    original = Path(__file__).resolve().parents[1] / "examples/research/evergiven"
    tree = load_research(original)
    status = research_status(tree)
    verdict = status["verdict"]
    assert set(verdict) == {"search", "root_claim", "live_hypotheses", "contested", "errors"}
    assert (
        verdict["root_claim"]["wording_license"]
        == license_model_claim(tree.models["logic"], "h_suez").wording_license
        == "withhold"
    )
    assert (
        verdict["search"]
        == decide_model_search_stop(tree.models["source"], remaining_budget=3)[1].status
        == "continue_search"
    )
    assert verdict["live_hypotheses"] == ["h_demand", "h_yantian"]
    assert verdict["contested"] is False and verdict["errors"] == 0
    assert status["disagreements"] == []
    assert status["ablations"] and all(row["caught_by"] for row in status["ablations"])
    page = render_status_markdown(status)
    headings = [line for line in page.splitlines() if line.startswith("## ")]
    assert len(headings) == len(set(headings))
    hypothesis_table = page.split("## Hypotheses", 1)[1].split("\n## ", 1)[0]
    shown = [
        line.split("|")[1].strip()
        for line in hypothesis_table.splitlines()
        if line.startswith("| h")
    ]
    assert sorted(shown) == sorted(row["id"] for row in status["hypotheses"])
    assert "{" not in page
    assert page.split("## ", 1)[1].startswith("Verdict")
    lines = page.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("|---"):
            assert line.count("|") == lines[index - 1].count("|")

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

def test_reference_only_evidence_has_no_direction(tmp_path):
    import shutil
    candidate = tmp_path / 'reference-only'
    shutil.copytree(EVERGIVEN, candidate)

    def add_reference(data):
        data['nodes']['E_lloyds'] = {
            'type': 'Evidence', 'text': "Lloyd's List: the blockage alone doubled Asia-Europe spot rates in April 2021.",
            'confidence': 0.85, 'scope': 'Asia-Europe spot rates, 2021',
            'provenance': [{'origin_kind': 'external_source', 'source_reference': "Lloyd's List, April 2021",
                            'quote': 'The Suez blockage alone doubled Asia-Europe spot rates in April 2021.'}],
        }
        data['edges'].append({'source': 'E_lloyds', 'target': 'h_suez', 'type': 'supports', 'weight': 0.9})

    _rewrite(candidate, 'logic.yaml', add_reference)
    status = research_status(load_research(candidate))
    assert not any(direction['node'] == 'E_lloyds' for row in status['evidence'] for direction in row['directions'])

def test_summary_number_not_in_quote_warns(tmp_path):
    import shutil
    candidate = tmp_path / 'C2'
    shutil.copytree(EVERGIVEN, candidate)
    baseline = research_status(load_research(EVERGIVEN))
    path = candidate / 'logic.yaml'
    path.write_text(path.read_text().replace('~7,000 (mid', '~3,500 (mid'))
    warning = 'summary_number_not_in_quote:E_series'
    c2 = research_status(load_research(candidate))
    assert c2['warnings'].count(warning) == 1
    assert not any(item.startswith('summary_number_not_in_quote:') for item in baseline['warnings'])
    assert c2['verdict'] == baseline['verdict'] and c2['errors'] == [] and set(c2) == set(baseline)

    source_path = candidate / 'source.yaml'
    source = yaml.safe_load(source_path.read_text())
    matched = next(row for row in source['anchors'] if (row['source_id'], row['anchor_id']) == ('src-drewry-wci', 'anc-wci-series'))
    unrelated = next(row for row in source['anchors'] if row is not matched)
    unrelated['normalized_summary'] = (unrelated.get('normalized_summary') or '') + ' 3,500'
    source_path.write_text(yaml.safe_dump(source, sort_keys=False))
    assert research_status(load_research(candidate))['warnings'].count(warning) == 1
    matched['normalized_summary'] = (matched.get('normalized_summary') or '') + ' 3,500'
    source_path.write_text(yaml.safe_dump(source, sort_keys=False))
    anchor_supported = research_status(load_research(candidate))
    assert warning not in anchor_supported['warnings'] and anchor_supported['errors'] == []

    path.write_text(path.read_text().replace('~3,500 (mid', '~7000 (mid'))
    assert research_status(load_research(candidate))['warnings'].count(warning) == 1
    _rewrite(candidate, 'logic.yaml', lambda data: data['nodes']['E_series'].update(text='上涨3500元，报价3500USD。'))
    assert research_status(load_research(candidate))['warnings'].count(warning) == 1

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
        assert {'question', 'verdict', 'hypotheses', 'models', 'evidence', 'input_digests'} <= set(status)
        assert status['question'] == tree.index['question']
        assert [(row['id'], row['text']) for row in status['hypotheses']] == [(row['id'], row['text']) for row in tree.index['hypotheses']]
        assert {route: row['path'] for route, row in status['models'].items()} == {
            route: path for route, path in tree.index['models'].items() if route != 'experiment_observations'}
        assert all(set(row) == {'path', 'status'} for row in status['models'].values())
        assert {row['anchor'] for row in status['evidence']} == {row.anchor_id for row in tree.models['source'].anchors}
        for row in status['evidence']:
            assert {'locator', 'summary', 'boundary'} <= set(row)
            anchor = next(a for a in tree.models['source'].anchors if a.anchor_id == row['anchor'])
            source = next(a for a in tree.models['source'].sources if a.source_id == row['source'])
            assert row['locator'] == anchor.locator
            assert row['summary'] == (anchor.normalized_summary or anchor.text[:200])
            assert row['boundary'] == source.cannot_support_structural_use
            for item in row['directions']:
                assert set(item) == {'route', 'hypothesis', 'direction', 'node'} and item['direction'] in {'support', 'oppose', 'limit'}
        assert set(status['verdict']) == {'search', 'root_claim', 'live_hypotheses', 'contested', 'errors'}
