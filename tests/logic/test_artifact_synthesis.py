from __future__ import annotations

import pytest

from researchguard.logic import load_model_from_dict, model_fingerprint, synthesize_artifact_plan


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


def test_missing_support_stays_blocked_in_the_argument_plan() -> None:
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
    assert plan.status == "blocked_support_gap"
    assert plan.open_gaps


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


def test_temporal_context_does_not_override_argument_importance() -> None:
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

    assert plan.units[0].claim_ids == ("C0",)
    assert plan.selected_items[0].temporal_role in {"historical", "source_dated"}
    assert plan.status == "blocked_support_gap"
    assert plan.open_gaps


def _model():
    nodes = {}
    edges = []
    for claim_id, importance, role_importance in (("C0", 1.0, 0.7), ("C2", 0.8, 0.7), ("O1", 0.2, 0.2)):
        nodes[claim_id] = {"type": "Claim", "text": f"SENTINEL-{claim_id}", "importance": importance}
        for prefix, node_type, edge_type in (
            ("E", "Evidence", "supports"),
            ("W", "Warrant", "supports"),
            ("A", "Assumption", "depends_on"),
            ("L", "Limitation", "qualifies"),
            ("R", "Rebuttal", "attacks"),
        ):
            node_id = f"{prefix}{claim_id}"
            nodes[node_id] = {"type": node_type, "text": f"{node_type}-{claim_id}", "importance": role_importance}
            edges.append({"source": node_id, "target": claim_id, "type": edge_type})
    edges.append({"source": "C2", "target": "C0", "type": "supports"})
    connected = [node_id for node_id in nodes if node_id != "O1" and not node_id.endswith("O1")]
    return load_model_from_dict(
        {
            "model": {
                "id": "delivery-contract",
                "root_claim": "C0",
                "target_units": [{"unit_id": "unit:delivery", "node_ids": connected}],
                "model_cards": [{"card_id": "card:delivery", "node_ids": connected}],
                "role_dispositions": {"competition": "not_applicable"},
            },
            "nodes": nodes,
            "edges": edges,
        }
    )


def _unit(unit_id, claim_ids, placement, *, required=False, predecessors=(), relation="background"):
    return {
        "unit_id": unit_id,
        "parent_unit_id": None,
        "reader_question": "What follows?",
        "unit_job": "Explain the bounded point.",
        "claim_ids": list(claim_ids),
        "predecessor_unit_ids": list(predecessors),
        "progression_relation": relation,
        "editorial_prominence": "lead",
        "placement": placement,
        "placement_reason": "Required by the selected composition.",
        "required": required,
    }


def _ready_plan():
    model = _model()
    request = {
        "schema": "researchguard.logic.synthesis-request.v1",
        "request_id": "delivery-request",
        "target_id": "delivery-artifact",
        "target_goal": "Preserve delivery structure",
        "artifact_kind": "report",
        "reader_id": "reader",
        "model_id": model.id,
        "model_fingerprint": model_fingerprint(model),
        "body_unit_order": ["u0", "u1"],
        "max_body_units": 2,
        "units": [
            _unit("u0", ["C2"], "body", required=True, relation="establishes"),
            _unit("u1", ["C0"], "body", required=True, predecessors=("u0",), relation="concludes"),
            _unit("un", ["C2"], "note"),
            _unit("ua", ["C2"], "appendix"),
            _unit("uo", ["O1"], "omit"),
        ],
        "source_branch_bindings": [],
    }
    plan = synthesize_artifact_plan(model, selection_request=request)
    assert plan.status == "research_handoff_ready", plan.open_gaps
    return plan


def test_ready_argument_plan_uses_native_depth_without_external_state():
    plan = _ready_plan()
    assert plan.status == "research_handoff_ready"
    assert not plan.open_gaps
