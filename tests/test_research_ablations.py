"""Question status assertions grouped by their independent model aspect."""
import copy
import json
from pathlib import Path
import pytest
import yaml
from researchguard.cli import main
from researchguard.research import check_research_tree, load_research, research_status
from research_tree_support import folder

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

def test_trace_ablation_agrees_with_trace_depth():
    from researchguard.trace.evaluator import evaluate_model
    folder = Path(__file__).resolve().parents[1] / 'examples/research/evergiven'
    tree = load_research(folder)
    status = research_status(tree)
    trace = tree.models['trace']
    mismatched = set(evaluate_model(trace, include_storyline_depth=True).storyline_depth.sensitivity_mismatch_ids)
    rows = {row['id']: row for row in status['ablations']}
    declared = [item for item in trace.expected_sensitivities if item.perturbation_id in rows]
    assert declared
    for item in declared:
        assert ('trace' in rows[item.perturbation_id]['caught_by']) == (item.sensitivity_id not in mismatched)
    # abl_no_unctad: the h_demand snapshot score falls by 0.0435, below trace's declared 0.05, so neither view counts trace.
    assert rows['abl_no_unctad']['caught_by'] == ['logic'] and 'sens_no_unctad' in mismatched
    # The question-level row has threshold 0, so the same check counts any decrease.
    assert rows['question_without_unctad']['caught_by'] == ['logic', 'trace']

def test_ablation_rows_name_side_effects():
    from researchguard.research import render_status_markdown
    folder = Path(__file__).resolve().parents[1] / 'examples/research/evergiven'
    status = research_status(load_research(folder))
    rows = {row['id']: row for row in status['ablations']}
    for name in ('abl_no_unctad', 'question_without_unctad'):
        assert {'hypothesis': 'h_suez', 'route': 'trace', 'field': 'live', 'before': False, 'after': True} in rows[name]['effects']
    assert '; effects: h_suez trace live false → true' in render_status_markdown(status)
