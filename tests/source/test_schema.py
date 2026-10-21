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
