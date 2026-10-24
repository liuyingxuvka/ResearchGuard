from __future__ import annotations

from pathlib import Path

import pytest

from researchguard.logic import load_model, load_model_from_dict, validate_model


ROOT = Path(__file__).resolve().parents[2]


def test_all_examples_validate() -> None:
    for path in (ROOT / "examples" / "logic").glob("*.yaml"):
        model = load_model(path)
        result = validate_model(model)
        assert result.ok, f"{path.name}: {result.errors}"


def test_validation_rejects_unknown_edge_target() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "bad", "root_claim": "C0"},
            "nodes": {"C0": {"type": "Claim", "text": "Root"}},
            "edges": [{"source": "E1", "target": "C0", "type": "supports"}],
        },
        validate=False,
    )
    result = validate_model(model)
    assert not result.ok
    assert any("source" in item for item in result.errors)


@pytest.mark.parametrize("metadata, fragment", [(1, "not iterable"), ([["one"]], "length 1")])
def test_malformed_provenance_metadata_names_the_evidence_node(metadata, fragment) -> None:
    model = load_model_from_dict({"model": {"id": "m", "root_claim": "C"}, "nodes": {"C": {"type": "Claim"}, "E_dates": {"type": "Evidence", "provenance": [{"origin_kind": "external_source", "source_id": "s", "quote": "text", "metadata": metadata}]}}}, validate=False)
    result = validate_model(model)
    assert not result.ok
    assert any("Evidence node 'E_dates': " in error and fragment in error for error in result.errors)


@pytest.mark.parametrize("owner", ["node", "block"])
def test_scalar_provenance_names_its_loader_owner(owner) -> None:
    from researchguard.logic.loader import ModelLoadError

    raw = {"model": {"id": "m", "root_claim": "C"}, "nodes": {"C": {"type": "Claim"}}}
    if owner == "node":
        raw["nodes"]["E_dates"] = {"type": "Evidence", "provenance": 1}
        label = "Evidence node 'E_dates'"
    else:
        raw["blocks"] = {"B_dates": {"provenance": 1}}
        label = "Argument block 'B_dates'"
    with pytest.raises(ModelLoadError) as exc:
        load_model_from_dict(raw, validate=False)
    assert label in str(exc.value)
    assert "not iterable" in str(exc.value)


def test_retired_block_interfaces_are_load_errors():
    from researchguard.logic.loader import ModelLoadError
    raw = {"model": {"id": "plain", "root_claim": "C"}, "nodes": {"C": {"type": "Claim", "text": "A plain claim"}}}
    model = load_model_from_dict({**raw, "block_interfaces": []})
    assert "block_interfaces" not in model.to_dict()
    with pytest.raises(ModelLoadError, match="block_interfaces.*retired"):
        load_model_from_dict({**raw, "block_interfaces": [{}]})


def test_retired_separation_key_names_the_current_input():
    from researchguard.logic.provenance import ProvenanceError, ProvenanceRecord
    with pytest.raises(ProvenanceError, match="separation_receipt_id.*separation_reason"):
        ProvenanceRecord(origin_kind="external_source", quote="declared quotation",
                         metadata={"separation_receipt_id": "old-review"})
