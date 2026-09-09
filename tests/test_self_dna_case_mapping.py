from __future__ import annotations

import json
from pathlib import Path

from scripts.build_self_dna_case_mapping import build_mapping


ROOT = Path(__file__).resolve().parents[1]


def _declared_rows() -> list[dict[str, object]]:
    # The registered suite exposes eight cases; these rows model the native
    # envelope shape without replacing the real runner in production.
    from scripts.build_self_dna_case_mapping import _load_model

    model = _load_model(ROOT)
    ids = (model.KNOWN_GOOD_CASE_ID, f"boundary:{model.MODEL_ID}", *model.KNOWN_BAD_CASE_IDS)
    return [{"source_case_id": case_id, "observed_status": "pass"} for case_id in ids]


def test_mapping_registry_reconciles_every_declared_native_case(tmp_path: Path) -> None:
    result = tmp_path / "native-case-results.json"
    result.write_text(json.dumps({"results": _declared_rows()}), encoding="utf-8")
    mapping = build_mapping(ROOT, result)
    assert mapping["status"] == "pass"
    assert len(mapping["nodes"]) == 10
    assert len(mapping["cases"]) == 8
    assert mapping["foreign_case_ids"] == []
    assert mapping["orphan_case_ids"] == []


def test_mapping_registry_blocks_foreign_and_orphan_cases(tmp_path: Path) -> None:
    result = tmp_path / "native-case-results.json"
    rows = _declared_rows()
    rows.pop()
    rows.append({"source_case_id": "foreign:case", "observed_status": "pass"})
    result.write_text(json.dumps({"results": rows}), encoding="utf-8")
    mapping = build_mapping(ROOT, result)
    assert mapping["status"] == "blocked"
    assert mapping["foreign_case_ids"] == ["foreign:case"]
    assert len(mapping["orphan_case_ids"]) == 1


def test_mapping_registry_blocks_duplicate_case_rows(tmp_path: Path) -> None:
    result = tmp_path / "native-case-results.json"
    rows = _declared_rows()
    rows.append(rows[0].copy())
    result.write_text(json.dumps({"results": rows}), encoding="utf-8")
    mapping = build_mapping(ROOT, result)
    assert mapping["status"] == "blocked"
    assert mapping["duplicate_case_ids"] == [rows[0]["source_case_id"]]
