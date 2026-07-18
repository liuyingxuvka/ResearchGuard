import pytest

from researchguard.source.loader import load_model
from researchguard.source.schema import (
    BeliefState,
    SchemaError,
    SearchAction,
    SourceRecord,
    SourceGuardPreventedFailure,
    SourceGuardProofCase,
    build_sourceguard_model_contract,
    sourceguard_model_contract_fingerprint,
)


def test_valid_yaml_can_load():
    model = load_model(
        "examples/source/starter_researchguard.source.yaml",
        "examples/source/starter_researchguard.source.contract.json",
    )
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
    contract = build_sourceguard_model_contract(
        model_id="test-source-candidate-boundary",
        purpose="Prevent source candidates from being promoted into evidence without anchors.",
        prevented_failures=[
            SourceGuardPreventedFailure(
                failure_id="failure:test:unqualified-candidate",
                title="Unqualified candidate is promoted",
                block_when="a candidate without a usable anchor is promoted",
                oracle_id="oracle:sourceguard:source-qualification",
                known_good=SourceGuardProofCase(
                    "good:test:qualified", "good.yaml", "pass"
                ),
                known_bad=SourceGuardProofCase(
                    "bad:test:unqualified",
                    "good.yaml",
                    "blocked",
                    "make-all-anchors-unusable",
                    "gaps:test",
                ),
            )
        ],
        gap_ids=[],
        target_unit_ids=[],
        claim_boundary="Candidate admission only; factual evidence requires qualified anchors.",
    )
    model = BeliefState.from_dict(
        {
            "guard_contract": contract.to_dict(),
            "candidate_contract_fingerprint": sourceguard_model_contract_fingerprint(contract),
            "sources": [{"source_id": "s1", "source_type": "web_page", "source_status": "candidate"}],
            "anchors": [],
        }
    )
    assert model.sources[0].source_status == "candidate"
    assert model.anchors == []
