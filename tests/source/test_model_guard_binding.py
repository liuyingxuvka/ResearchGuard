from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from researchguard.source.loader import load_model
from researchguard.source.schema import BeliefState, SchemaError


ROOT = Path(__file__).resolve().parents[2]
MODEL_PAIRS = [
    (ROOT / "examples/source/starter_researchguard.source.yaml", ROOT / "examples/source/starter_researchguard.source.contract.json"),
    (ROOT / "examples/source/structural_source_gap.yaml", ROOT / "examples/source/structural_source_gap.contract.json"),
    (ROOT / "examples/source/fuel_cell_project_discovery.yaml", ROOT / "examples/source/fuel_cell_project_discovery.contract.json"),
    (ROOT / "examples/source/multimodal_report_video_discovery.yaml", ROOT / "examples/source/multimodal_report_video_discovery.contract.json"),
    (ROOT / "examples/source/paper_citation_discovery.yaml", ROOT / "examples/source/paper_citation_discovery.contract.json"),
]


def _raw_model() -> dict:
    return yaml.safe_load(MODEL_PAIRS[0][0].read_text(encoding="utf-8"))


def test_every_current_model_uses_an_explicit_task_contract_and_native_proof() -> None:
    declaration_counts = []
    for model_path, contract_path in MODEL_PAIRS:
        model = load_model(model_path, contract_path)
        assert model.guard_contract is not None
        assert model.guard_contract.purpose_frozen is True
        assert model.guard_contract.candidate_construction_sequence > (
            model.guard_contract.purpose_freeze_sequence
        )
        declaration_counts.append(len(model.guard_contract.prevented_failures))
        assert declaration_counts[-1] >= 1
    assert set(declaration_counts) == {1}


def test_model_without_guard_contract_is_rejected_before_execution() -> None:
    raw = _raw_model()
    raw.pop("guard_contract")
    with pytest.raises(SchemaError, match="guard_contract is required"):
        BeliefState.from_dict(raw)


def test_candidate_with_stale_purpose_fingerprint_is_rejected() -> None:
    raw = _raw_model()
    raw["candidate_contract_fingerprint"] = "0" * 64
    with pytest.raises(SchemaError, match="does not match the frozen guard_contract"):
        BeliefState.from_dict(raw)


def test_explicit_contract_must_match_candidate_snapshot(tmp_path: Path) -> None:
    contract = yaml.safe_load(MODEL_PAIRS[0][1].read_text(encoding="utf-8"))
    contract["purpose"] += " changed"
    foreign = tmp_path / "contract.json"
    foreign.write_text(yaml.safe_dump(contract), encoding="utf-8")
    with pytest.raises(SchemaError, match="does not match the candidate snapshot"):
        load_model(MODEL_PAIRS[0][0], foreign)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("purpose_frozen", False, "purpose must be frozen"),
        ("candidate_construction_sequence", 1, "must occur after the frozen purpose"),
    ],
)
def test_candidate_cannot_be_constructed_before_purpose_freeze(
    field: str,
    value: object,
    message: str,
) -> None:
    raw = _raw_model()
    raw["guard_contract"][field] = value
    with pytest.raises(SchemaError, match=message):
        BeliefState.from_dict(raw)


def test_candidate_cannot_shrink_the_declared_gap_universe() -> None:
    raw = _raw_model()
    raw["guard_contract"]["external_universe"]["gap_ids"] = []
    with pytest.raises(SchemaError, match="gap universe does not match"):
        BeliefState.from_dict(raw)


def test_dynamic_task_contract_may_declare_one_failure() -> None:
    raw = _raw_model()
    assert len(raw["guard_contract"]["prevented_failures"]) == 1
    model = BeliefState.from_dict(raw)
    assert [row.failure_id for row in model.guard_contract.prevented_failures] == [
        "failure:starter:unqualified-independent-promotion"
    ]


def test_empty_or_unmapped_task_failure_contract_is_rejected() -> None:
    empty = _raw_model()
    empty["guard_contract"]["prevented_failures"] = []
    with pytest.raises(SchemaError, match="one or more prevented failures"):
        BeliefState.from_dict(empty)

    unmapped = deepcopy(_raw_model())
    unmapped["guard_contract"]["prevented_failures"][0]["oracle_id"] = (
        "oracle:sourceguard:not-real"
    )
    with pytest.raises(SchemaError, match="unsupported native oracle"):
        BeliefState.from_dict(unmapped)
