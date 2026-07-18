from __future__ import annotations

import pytest

from researchguard.logic import adapt_delivery, load_model_from_dict, synthesize_artifact_plan


def test_synthesis_requires_goal() -> None:
    model = load_model_from_dict(
        {
            "model": {"id": "synthesis_goal", "root_claim": "C0"},
            "nodes": {"C0": {"type": "Claim", "text": "Claim", "importance": 0.9}},
        }
    )

    with pytest.raises(ValueError, match="target_goal"):
        synthesize_artifact_plan(model, target_goal="")


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

    plan = synthesize_artifact_plan(model, target_goal="Create an executive report", max_items=1)

    assert plan.selected_items[0].node_id == "C0"
    assert plan.selected_items[0].treatment == "deep"
    assert plan.omitted_items[0].node_id == "C1"
    assert plan.omitted_items[0].treatment == "omit"
    assert any("evidence" in addition.lower() for addition in plan.missing_additions)


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

    plan = synthesize_artifact_plan(model, target_goal="Create a report", max_items=3)

    treatments = {item.node_id: item.treatment for item in (*plan.selected_items, *plan.omitted_items)}
    assert treatments["C0"] == "deep"
    assert treatments["W1"] == "deep"
    assert treatments["E1"] == "normal"
    assert treatments["K1"] == "omit"
    assert treatments["C1"] == "omit"

    tight_plan = synthesize_artifact_plan(model, target_goal="Create a very short report", max_items=1)
    tight_treatments = {item.node_id: item.treatment for item in tight_plan.omitted_items}
    assert tight_treatments["W1"] == "appendix"


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
    plan = synthesize_artifact_plan(model, target_goal="Create a presentation", profile="presentation")
    guidance = adapt_delivery(plan)
    text = "\n".join(item.suggested_text for item in guidance.suggestions)
    traces = "\n".join(item.trace for item in guidance.suggestions)

    assert "missing_handoff" not in text
    assert "core_claim" not in text
    assert "Limited to validated range." in text
    assert "treatment=deep" in traces


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
        model,
        target_goal="Create a measured flow plausibility briefing",
        max_items=1,
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

    assert plan.selected_items[0].node_type == "SourceBranch"
    assert plan.selected_items[0].branch_id == "BR1"
    assert plan.selected_items[0].anchor_node_id == "C3"
    assert plan.selected_items[0].temporal_role == "covered_period"
    assert "covered period" in plan.selected_items[0].temporal_caveat.lower()


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
        model,
        target_goal="Create a report",
        max_items=1,
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

    assert plan.selected_items[0].node_id == "C0"
    assert plan.selected_items[0].temporal_role == "historical"
    assert "2018-2020" in guidance.suggestions[0].suggested_text
