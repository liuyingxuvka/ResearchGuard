from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from researchguard.logic import (
    audit_claim_source_paragraph_matrix,
    build_claim_source_paragraph_matrix,
    load_model_from_dict,
    paragraph_blueprint,
    synthesize_artifact_plan,
)


ROOT = Path(__file__).resolve().parents[2]


def _model_dict() -> dict[str, object]:
    return {
        "model": {"id": "citation_test", "title": "Citation Test", "root_claim": "C1"},
        "nodes": {
            "S1": {"type": "Section", "text": "Findings", "locator": "section 2"},
            "C1": {
                "type": "Claim",
                "text": "The evidence supports a cautious conclusion.",
                "parent": "S1",
                "importance": 0.92,
                "salience": "core",
                "confidence": 0.83,
                "claim_strength": "bounded",
            },
            "E1": {
                "type": "Evidence",
                "text": "Trial A measured a repeatable effect.",
                "source_id": "paper-a",
                "source_role": "measured_result",
                "source_locator": "p. 4",
            },
            "L1": {"type": "Limitation", "text": "Only validated for trial A."},
            "C2": {
                "type": "Claim",
                "text": "The evidence supports a cautious conclusion.",
                "paragraph_locator": "paragraph 4",
                "importance": 0.75,
                "source_id": "paper-b",
                "source_role": "replication_result",
            },
            "C3": {
                "type": "Claim",
                "text": "An important claim still needs evidence.",
                "importance": 0.86,
                "paragraph_locator": "paragraph 5",
            },
        },
        "edges": [
            {"source": "E1", "target": "C1", "type": "supports"},
            {"source": "L1", "target": "C1", "type": "qualifies"},
        ],
        "hierarchy": {"S1": ["C1"]},
    }


def test_claim_source_paragraph_matrix_collects_sources_and_paragraphs() -> None:
    model = load_model_from_dict(_model_dict())

    matrix = build_claim_source_paragraph_matrix(model)
    row = matrix.row_for_claim("C1")

    assert row is not None
    assert row.source_ids == ("paper-a",)
    assert row.source_roles == {"paper-a": "measured_result"}
    assert row.source_locators == {"paper-a": "p. 4"}
    assert row.paragraph_locator == "section 2"
    assert row.citation_marker == "[paper-a]"
    assert row.generated_marker is True
    assert row.claim_strength == "bounded"
    assert "trial A" in row.limitation


def test_matrix_audit_flags_missing_sources_and_duplicate_claims() -> None:
    model = load_model_from_dict(_model_dict())

    findings = audit_claim_source_paragraph_matrix(build_claim_source_paragraph_matrix(model))
    codes = {finding.code for finding in findings}

    assert "important_claim_missing_source" in codes
    assert "duplicate_claim_placement" in codes
    assert "generated_citation_marker_needs_review" in codes


def test_paragraph_blueprint_can_include_citation_matrix() -> None:
    model = load_model_from_dict(_model_dict())
    matrix = build_claim_source_paragraph_matrix(model)

    text = paragraph_blueprint(model, "C1", citation_matrix=matrix)

    assert "Paragraph locator: section 2" in text
    assert "Source markers: [paper-a]" in text
    assert "paper-a: measured_result" in text


def test_synthesis_items_include_citation_matrix_handoff() -> None:
    model = load_model_from_dict(_model_dict())

    plan = synthesize_artifact_plan(model, target_goal="draft the cautious conclusion", profile="report", max_items=1)
    item = plan.selected_items[0]

    assert item.node_id == "C1"
    assert item.source_ids == ("paper-a",)
    assert item.citation_marker == "[paper-a]"
    assert item.paragraph_locator == "section 2"
    assert item.source_roles == {"paper-a": "measured_result"}
    assert "Citation plan: [paper-a] at section 2" in plan.to_markdown()


def test_cli_citation_matrix_and_audit_smoke(tmp_path: Path) -> None:
    model_file = tmp_path / "model.json"
    model_file.write_text(json.dumps(_model_dict()), encoding="utf-8")

    matrix = subprocess.run(
        [sys.executable, "-m", "researchguard", "logic", "citation", "matrix", str(model_file), "--json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert matrix.returncode == 0, matrix.stderr or matrix.stdout
    payload = json.loads(matrix.stdout)
    assert payload["rows"][0]["source_ids"] == ["paper-a"]

    audit = subprocess.run(
        [sys.executable, "-m", "researchguard", "logic", "citation", "audit", str(model_file), "--json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert audit.returncode == 0, audit.stderr or audit.stdout
    findings = json.loads(audit.stdout)["findings"]
    assert any(finding["code"] == "important_claim_missing_source" for finding in findings)


def test_cli_outline_can_attach_citation_handoff(tmp_path: Path) -> None:
    model_file = tmp_path / "model.json"
    model_file.write_text(json.dumps(_model_dict()), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "researchguard", "logic", "outline", str(model_file), "--paragraph", "C1", "--with-citations"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Source markers: [paper-a]" in result.stdout
