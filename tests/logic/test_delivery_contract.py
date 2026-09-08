from __future__ import annotations

from dataclasses import replace

from researchguard.logic import adapt_delivery, load_model_from_dict, model_fingerprint, synthesize_artifact_plan
from researchguard.logic.execution_depth import _build_native_depth_analysis


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
    receipt = _build_native_depth_analysis(model, budget=20)
    plan = synthesize_artifact_plan(model, selection_request=request, native_depth_receipt=receipt)
    assert plan.status == "research_handoff_ready", plan.open_gaps
    return plan


def test_delivery_uses_explicit_body_order_and_preserves_each_placement():
    guidance = adapt_delivery(_ready_plan())

    assert [item.unit_id for item in guidance.suggestions] == ["u0", "u1"]
    assert [item.unit_id for item in guidance.note_suggestions] == ["un"]
    assert [item.unit_id for item in guidance.appendix_suggestions] == ["ua"]
    assert "SENTINEL-C2" in guidance.note_suggestions[0].suggested_text
    assert "SENTINEL-C2" in guidance.appendix_suggestions[0].suggested_text
    assert "SENTINEL-O1" not in guidance.to_markdown()
    assert "## Notes" in guidance.to_markdown()
    assert "## Appendix" in guidance.to_markdown()


def test_delivery_keeps_all_claims_in_a_multi_claim_unit():
    plan = _ready_plan()
    multi = replace(
        plan.units[1],
        claim_ids=("C0", "C2"),
    )
    updated = replace(plan, units=(plan.units[0], multi, *plan.units[2:]))
    guidance = adapt_delivery(updated)
    text = guidance.suggestions[1].suggested_text
    assert "SENTINEL-C0" in text
    assert "SENTINEL-C2" in text
    assert set(guidance.suggestions[1].claim_ids) == {"C0", "C2"}


def test_blocked_plan_cannot_become_writer_material():
    plan = replace(_ready_plan(), status="blocked_support_gap", open_gaps=("native_gap",))
    guidance = adapt_delivery(plan)
    assert guidance.status == "blocked_support_gap"
    assert guidance.suggestions == ()
    assert guidance.note_suggestions == ()
    assert guidance.appendix_suggestions == ()
    assert guidance.open_gaps == ("native_gap",)


def test_delivery_rejects_unknown_or_duplicate_body_order():
    plan = _ready_plan()
    bad = replace(plan, body_unit_order=("u1", "u1"))
    guidance = adapt_delivery(bad)
    assert guidance.status == "blocked_delivery_contract"
    assert guidance.suggestions == ()
    assert any("duplicate_body_unit_order" in gap for gap in guidance.open_gaps)

    bad = replace(plan, body_unit_order=("u1", "ghost"))
    guidance = adapt_delivery(bad)
    assert guidance.status == "blocked_delivery_contract"
    assert any("unknown_body_unit:ghost" in gap for gap in guidance.open_gaps)
