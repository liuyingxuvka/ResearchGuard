from __future__ import annotations

from researchguard.logic import audit_structure, build_artifact_map, load_model_from_dict


def _artifact_model():
    return load_model_from_dict(
        {
            "model": {"id": "deck_model", "root_claim": "C1", "artifact_kind": "presentation"},
            "nodes": {
                "D0": {"type": "Document", "text": "Deck", "artifact_kind": "presentation", "order_index": 0},
                "S1": {"type": "Section", "text": "Validation", "artifact_kind": "presentation", "order_index": 1},
                "B1": {"type": "ArgumentBlock", "text": "Slide 1", "locator": "slide 1", "order_index": 1},
                "B2": {"type": "ArgumentBlock", "text": "Slide 2", "locator": "slide 2", "order_index": 2},
                "B3": {"type": "ArgumentBlock", "text": "Slide 3", "locator": "slide 3", "order_index": 3},
                "C1": {"type": "Claim", "text": "Calibration is reliable.", "parent": "B1", "importance": 0.9},
                "C2": {"type": "Claim", "text": "Calibration is reliable.", "parent": "B2", "importance": 0.8},
                "C3": {"type": "Claim", "text": "Runtime is acceptable.", "parent": "B2", "importance": 0.82},
                "L1": {"type": "Limitation", "text": "Only validated in the training envelope.", "parent": "B3", "importance": 0.9},
            },
            "edges": [{"source": "L1", "target": "C1", "type": "qualifies", "weight": 0.7}],
            "hierarchy": {"D0": ["S1"], "S1": ["B1", "B2", "B3"], "B1": ["C1"], "B2": ["C2", "C3"], "B3": ["L1"]},
        }
    )


def test_artifact_map_recovers_ordered_blocks() -> None:
    artifact = build_artifact_map(_artifact_model())

    block_ids = [block["block_id"] for block in artifact.to_dict()["blocks"]]
    assert block_ids[:3] == ["D0", "S1", "B1"]
    assert artifact.artifact_kind == "presentation"


def test_structure_audit_finds_flow_issues() -> None:
    report = audit_structure(_artifact_model())
    codes = {finding.code for finding in report.findings}

    assert "missing_handoff" in codes
    assert "late_limitation" in codes
    assert "overloaded_block" in codes
    assert "duplicate_claim" in codes


def test_structure_audit_flags_material_temporal_boundaries() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "temporal_report", "root_claim": "C1", "artifact_kind": "report"},
            "nodes": {
                "D0": {"type": "Document", "text": "Report", "order_index": 0},
                "B1": {"type": "ArgumentBlock", "text": "Current state", "parent": "D0", "order_index": 1},
                "C1": {
                    "type": "Claim",
                    "text": "The current state is supported.",
                    "parent": "B1",
                    "importance": 0.9,
                    "source_id": "report-a",
                    "source_date": "2024",
                    "coverage_period": "2021-2023",
                    "current_state": True,
                },
                "C2": {
                    "type": "Claim",
                    "text": "The current state lacks dated source context.",
                    "parent": "B1",
                    "importance": 0.8,
                    "source_id": "report-b",
                    "current_state": True,
                },
            },
            "hierarchy": {"D0": ["B1"], "B1": ["C1", "C2"]},
        }
    )

    codes = {finding.code for finding in audit_structure(model).findings}

    assert "source_date_after_coverage" in codes
    assert "undated_current_state_source" in codes
