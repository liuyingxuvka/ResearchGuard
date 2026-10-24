import pytest

from researchguard.source.loader import load_model
from researchguard.source.schema import (
    BeliefState,
    SchemaError,
    SearchAction,
    SourceRecord,
)


def test_valid_yaml_can_load():
    model = load_model("examples/source/starter_researchguard.source.yaml")
    assert len(model.leads) == 1
    assert len(model.gaps) == 1
    assert model.metadata["math_boundary"]


def test_invalid_score_values_are_clamped():
    source = SourceRecord.from_dict({"source_id": "s1", "source_reliability": 3, "source_type": "paper"})
    action = SearchAction.from_dict({"action_id": "a1", "action_type": "text_search", "cost": -2, "permission_risk": 7})
    assert source.source_reliability == 1.0
    assert action.cost == 0.0
    assert action.permission_risk == 1.0


def test_invalid_status_raises():
    with pytest.raises(SchemaError):
        SourceRecord.from_dict({"source_id": "s1", "source_status": "validated_truth"})


def test_model_root_must_be_mapping():
    with pytest.raises(SchemaError):
        BeliefState.from_dict([])


def test_source_candidate_does_not_auto_become_evidence():
    model = BeliefState.from_dict(
        {
            "sources": [{"source_id": "s1", "source_type": "web_page", "source_status": "candidate"}],
            "anchors": [],
        }
    )
    assert model.sources[0].source_status == "candidate"
    assert model.anchors == []


def test_gap_hypothesis_ids_are_optional_strings():
    from researchguard.source.planner import plan_next_actions
    from researchguard.source.schema import BeliefState, Gap, SchemaError, to_plain
    assert Gap.from_dict({'gap_id': 'g'}).hypothesis_ids == []
    assert Gap.from_dict({'gap_id': 'g', 'hypothesis_ids': ['h']}).hypothesis_ids == ['h']
    for bad in ('h', [1], [''], {'h': 1}):
        with pytest.raises(SchemaError):
            Gap.from_dict({'gap_id': 'g', 'hypothesis_ids': bad})
    base = {'sources': [{'source_id': 's'}], 'leads': [{'lead_id': 'l'}],
            'gaps': [{'gap_id': 'g', 'lead_id': 'l', 'blocking': True}],
            'search_actions': [{'action_id': 'a', 'target_gap_id': 'g', 'query': 'q'}]}
    named = {**base, 'gaps': [{**base['gaps'][0], 'hypothesis_ids': ['h']}]}
    def plain(data):
        result = to_plain(plan_next_actions(BeliefState.from_dict(data)))
        for row in result['open_gaps']:
            row.pop('hypothesis_ids')
        return result
    assert plain(base) == plain(named)
    assert BeliefState.from_dict(named).gaps[0].hypothesis_ids == ['h']
