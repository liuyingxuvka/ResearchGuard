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


def test_dump_omits_defaults_and_round_trips():
    from pathlib import Path
    from researchguard.source.loader import dump_yaml
    from researchguard.source.schema import to_plain, to_plain_without_defaults
    import yaml

    path = Path("examples/research/evergiven/source.yaml")
    model = load_model(path)
    rendered = dump_yaml(model)
    full = yaml.safe_dump(to_plain(model), sort_keys=False, allow_unicode=True)
    assert BeliefState.from_dict(yaml.safe_load(rendered)) == model
    assert len(rendered) < len(full)
    assert to_plain_without_defaults({"explicit": False, "zero": 0, "empty": []}) == {
        "explicit": False,
        "zero": 0,
        "empty": [],
    }
    assert to_plain(SourceRecord(source_id="s"))["source_status"] == "candidate"


def test_retired_writing_fields_warn(tmp_path):
    import yaml
    from researchguard.source.loader import validate_model, write_yaml, load_model
    retired = ('parent_goal', 'unit_job', 'contribution_type', 'downstream_consumer',
               'structural_role_needed', 'allowed_wording', 'unsafe_wording',
               'can_support_structural_use', 'cannot_support_structural_use')
    path = tmp_path / 'source.yaml'
    data = {'gaps': [{'gap_id': 'g', 'structure_unit_id': 'unit', **dict.fromkeys(retired, 'old')}],
            'sources': [{'source_id': 's', 'cannot_support_structural_use': 'No causal conclusion'}]}
    path.write_text(yaml.safe_dump(data))
    assert validate_model(path)['warnings'] == ['retired_field:' + name for name in sorted(retired)]
    model = load_model(path)
    assert model.gaps[0].structure_unit_id == 'unit'
    assert model.sources[0].cannot_support_structural_use == 'No causal conclusion'
    write_yaml(path, model)
    rewritten = yaml.safe_load(path.read_text())
    assert not set(rewritten['gaps'][0]) & set(retired)
    assert rewritten['sources'][0]['cannot_support_structural_use'] == 'No causal conclusion'
