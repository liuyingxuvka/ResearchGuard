from __future__ import annotations

import pytest

from researchguard.logic import adapt_delivery, load_model_from_dict, model_fingerprint, synthesize_artifact_plan


def _request(model, *, goal="Create a report", artifact_kind="report", claims=("C0",), placement="body", max_body_units=2, branches=()):
    units = [{
        "unit_id": "u1",
        "parent_unit_id": None,
        "reader_question": "What is the answer?",
        "unit_job": "State and bound the selected claim.",
        "claim_ids": list(claims),
        "predecessor_unit_ids": [],
        "progression_relation": "concludes",
        "editorial_prominence": "lead",
        "placement": placement,
        "placement_reason": "Required for the requested artifact.",
        "required": True,
    }]
    normalized_branches = []
    for branch in branches:
        value = dict(branch)
        value.setdefault("claim_ids", list(claims))
        value.setdefault("anchor_node_id", "C0")
        normalized_branches.append(value)
    return {
        "schema": "researchguard.logic.synthesis-request.v1",
        "request_id": "req-1", "target_id": "artifact-1", "target_goal": goal,
        "artifact_kind": artifact_kind, "reader_id": "reader-1", "model_id": model.id,
        "model_fingerprint": model_fingerprint(model), "body_unit_order": ["u1"] if placement == "body" else [],
        "max_body_units": max_body_units, "units": units,
        "source_branch_bindings": normalized_branches,
    }


def test_synthesis_requires_goal() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "synthesis_goal", "root_claim": "C0"},
            "nodes": {"C0": {"type": "Claim", "text": "Claim", "importance": 0.9}},
        }
    )

    plan = synthesize_artifact_plan(model, selection_request={})
    assert plan.status == "blocked_invalid_request"
    assert any("target_goal" in gap for gap in plan.open_gaps)


def test_synthesis_prioritizes_importance_and_marks_missing_support() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "synthesis_test", "root_claim": "C0"},
            "nodes": {
                "C0": {"type": "Claim", "text": "Core claim.", "importance": 0.95, "salience": "core"},
                "C1": {"type": "Claim", "text": "Optional claim.", "importance": 0.2, "salience": "optional"},
            },
        }
    )

    plan = synthesize_artifact_plan(model, selection_request=_request(model, goal="Create an executive report"))

    assert plan.units[0].claim_ids == ("C0",)
    assert plan.candidate_dispositions[0].placement == "body"
    assert plan.candidate_dispositions[1].placement == "omit"
    assert plan.status == "blocked_support_gap"


def test_synthesis_assigns_treatment_guidance() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "treatment_test", "root_claim": "C0"},
            "nodes": {
                "C0": {"type": "Claim", "text": "Core claim.", "importance": 0.95, "salience": "core"},
                "W1": {"type": "Warrant", "text": "Important bridge.", "importance": 0.72, "salience": "bridge"},
                "E1": {"type": "Evidence", "text": "Useful evidence.", "importance": 0.62, "salience": "supporting"},
                "K1": {"type": "Context", "text": "Background context.", "importance": 0.42, "salience": "background"},
                "C1": {"type": "Claim", "text": "Optional note.", "importance": 0.2, "salience": "optional"},
            },
        }
    )

    plan = synthesize_artifact_plan(model, selection_request=_request(model, claims=("C0",)))

    dispositions = {item.candidate_id: item.placement for item in plan.candidate_dispositions}
    assert dispositions["C0"] == "body"
    assert dispositions["W1"] == "appendix"
    assert dispositions["E1"] == "appendix"
    assert dispositions["K1"] == "omit"
    assert dispositions["C1"] == "omit"

    assert plan.units[0].research_importance["C0"] == 0.95


def test_delivery_guidance_avoids_internal_labels() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "delivery_test", "root_claim": "C0"},
            "nodes": {
                "C0": {"type": "Claim", "text": "Core claim.", "importance": 0.95, "salience": "core"},
                "L1": {"type": "Limitation", "text": "Limited to validated range.", "importance": 0.9, "salience": "risk"},
            },
        }
    )
    plan = synthesize_artifact_plan(model, selection_request=_request(model, artifact_kind="presentation"))
    guidance = adapt_delivery(plan)
    text = "\n".join(item.suggested_text for item in guidance.suggestions)
    traces = "\n".join(item.trace for item in guidance.suggestions)

    assert guidance.status == "blocked_support_gap"
    assert guidance.suggestions == ()
    assert "missing_handoff" not in text
    assert "core_claim" not in text
    assert "Limited to validated range." not in text
    assert "prominence=lead" not in traces


def test_synthesis_can_preserve_source_branch_candidates() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "branch_synthesis", "root_claim": "C0"},
            "nodes": {
                "C0": {"type": "Claim", "text": "Calibration should avoid measured flow as reference.", "importance": 0.7},
            },
        }
    )
    plan = synthesize_artifact_plan(
        model, selection_request=_request(model, goal="Create a measured flow plausibility briefing", branches=({
            "branch_id": "BR1", "source_id": "paper-a", "claim_ids": ["C0"], "destination_unit_id": "u1",
            "current_native_evidence_ref": "ev-1"
        },)),
        source_branches=[
            {
                "branch_id": "BR1",
                "source_id": "paper-a",
                "topic_focus": "measured flow plausibility",
                "branch_role": "limitation_detail",
                "anchor_node_id": "C3",
                "importance": 0.94,
                "salience": "risk",
                "source_date": "2024",
                "coverage_period": "2021-2023",
            }
        ],
    )

    assert plan.units[0].source_branch_ids == ("BR1",)
    assert plan.candidate_dispositions[0].candidate_id == "source_branch:paper-a:BR1"
    assert plan.candidate_dispositions[0].placement == "body"


def test_temporal_context_does_not_override_importance_but_guides_delivery() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "temporal_synthesis", "root_claim": "C0"},
            "nodes": {
                "C0": {
                    "type": "Claim",
                    "text": "Older but central evidence controls the report.",
                    "importance": 0.95,
                    "salience": "core",
                    "source_id": "old-report",
                    "source_date": "2020",
                    "coverage_period": "2018-2020",
                },
            },
        }
    )
    plan = synthesize_artifact_plan(
        model, selection_request=_request(model),
        source_branches=[
            {
                "branch_id": "BR-new",
                "source_id": "new-report",
                "topic_focus": "recent background",
                "importance": 0.3,
                "source_date": "2025",
                "coverage_period": "2024",
            }
        ],
    )
    guidance = adapt_delivery(plan, profile="report")

    assert plan.units[0].claim_ids == ("C0",)
    assert plan.selected_items[0].temporal_role in {"historical", "source_dated"}
    assert guidance.status == "blocked_support_gap"
    assert guidance.suggestions == ()
