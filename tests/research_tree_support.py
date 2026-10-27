"""Unchanged shared question fixtures for the four native model aspects."""
import json
from pathlib import Path
import pytest
import yaml

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

EVERGIVEN = Path(__file__).resolve().parents[1] / 'examples/research/evergiven'
