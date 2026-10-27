from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml

from researchguard.logic import load_model_from_dict, validate_model
from researchguard.logic.provenance import ProvenanceError, ProvenanceRecord
from researchguard.source import schema
from researchguard.source.cli import main as source_main, starter_model_dict

ROOT = Path(__file__).resolve().parents[1]
FIELDS = tuple(ROOT / "skills/researchguard/references/source" / name for name in ('fields-create.md', 'fields-depth.md', 'fields-examples.md'))


def test_source_field_sheet_has_current_enums_and_valid_starter(tmp_path, capsys) -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in FIELDS)
    for name in ("SOURCE_TYPES", "SOURCE_ROLES", "GAP_TYPES", "SEMANTIC_GAP_STATES", "ACTION_TYPES", "ANCHOR_TYPES", "MODALITIES"):
        assert all(value in text for value in getattr(schema, name)), name
    examples = [yaml.safe_load(value) for value in re.findall(r"```yaml\n(.*?)```", text, re.S)]
    model = next(value for value in examples if "leads" in value and "gaps" in value)
    expected = starter_model_dict()
    expected["metadata"].pop("version")
    assert model == expected
    path = tmp_path / "source.yaml"
    path.write_text(yaml.safe_dump(model, sort_keys=False), encoding="utf-8")
    assert source_main(["validate", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert result["lead_count"] == result["source_count"] == result["anchor_count"] == 1
    assert result["gap_count"] == 2
    assert result["warnings"][0].startswith("starter example rows still present: example-")


def test_gap_default_is_only_for_absence_and_retired_status_stays_rejected() -> None:
    assert schema.Gap.from_dict({"gap_id": "g"}).semantic_state == "discovered"
    for value in (None, False, "", "retired"):
        with pytest.raises(schema.SchemaError):
            schema.Gap.from_dict({"gap_id": "g", "semantic_state": value})
    with pytest.raises(schema.SchemaError, match="gap.status is retired"):
        schema.Gap.from_dict({"gap_id": "g", "status": "open"})
    with pytest.raises(schema.SchemaError, match="complete current closure_basis"):
        schema.Gap.from_dict({"gap_id": "g", "semantic_state": "closed"})


def test_choice_errors_list_sorted_allowed_values() -> None:
    with pytest.raises(schema.SchemaError) as exc:
        schema.require_choice("wrong", {"z", "a"}, "field")
    assert str(exc.value) == "field has invalid value 'wrong'; allowed: a, z"
    with pytest.raises(schema.SchemaError) as exc:
        schema.Gap.from_dict({"gap_id": "g", "suggested_source_roles": ["wrong"]})
    assert str(exc.value).endswith("allowed: " + ", ".join(sorted(schema.SOURCE_ROLES)))


def test_quote_hash_preserves_utf8_and_existing_digest_forms() -> None:
    quote = "  原始引文\n"
    digest = hashlib.sha256(quote.encode("utf-8")).hexdigest()
    record = ProvenanceRecord("external_source", source_id="s", quote=quote)
    assert record.content_hash == "sha256:" + digest
    assert record.to_dict()["quote"] == quote
    assert ProvenanceRecord.from_dict(record.to_dict()) == record
    assert ProvenanceRecord("external_source", digest.upper(), source_id="s", quote=quote).content_hash == record.content_hash
    with pytest.raises(ProvenanceError, match="does not match quote"):
        ProvenanceRecord("external_source", "0" * 64, source_id="s", quote=quote)
    for invalid in ("", 0, False, []):
        with pytest.raises(ProvenanceError, match="quote must be a non-empty string"):
            ProvenanceRecord("external_source", source_id="s", quote=invalid)


def test_provenance_errors_identify_the_evidence_node() -> None:
    for record, message in (
        ({"origin_kind": "external_source", "source_id": "s"}, "content_hash or quote is required"),
        ({"origin_kind": "external_source", "source_id": "s", "content_hash": "bad"}, "content_hash must be a sha256 digest"),
        ({"origin_kind": "external_source", "quote": "text"}, "provenance requires source_id or source_reference"),
    ):
        model = load_model_from_dict({"model": {"id": "m", "root_claim": "C"}, "nodes": {"C": {"type": "Claim"}, "E_dates": {"type": "Evidence", "provenance": [record]}}}, validate=False)
        result = validate_model(model)
        assert not result.ok
        assert any("Evidence node 'E_dates': " + message in error for error in result.errors)
