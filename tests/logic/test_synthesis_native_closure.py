from __future__ import annotations

from researchguard.logic import load_model_from_dict, model_fingerprint, synthesize_artifact_plan
from researchguard.logic.execution_depth import build_native_depth_analysis
from researchguard.logic.structure_audit import audit_structure


def _request(model, *, units, body_order):
    return {
        "schema": "researchguard.logic.synthesis-request.v1",
        "request_id": "native-closure-request",
        "target_id": "native-closure-artifact",
        "target_goal": "Preserve native closure",
        "artifact_kind": "report",
        "reader_id": "reader",
        "model_id": model.id,
        "model_fingerprint": model_fingerprint(model),
        "body_unit_order": list(body_order),
        "max_body_units": len(body_order),
        "units": list(units),
        "source_branch_bindings": [],
    }


def _unit(unit_id, claim_id, *, parent=None, predecessors=(), relation="establishes"):
    return {
        "unit_id": unit_id,
        "parent_unit_id": parent,
        "reader_question": f"What follows in {unit_id}?",
        "unit_job": f"Explain {claim_id}.",
        "claim_ids": [claim_id],
        "predecessor_unit_ids": list(predecessors),
        "progression_relation": relation,
        "editorial_prominence": "lead" if relation == "concludes" else "normal",
        "placement": "body",
        "placement_reason": "Required by the reader question.",
        "required": True,
    }


def test_grandchild_native_structure_gap_propagates_to_real_ancestors():
    model = load_model_from_dict(
        {
            "model": {"id": "three-level-structure", "root_claim": "C0"},
            "nodes": {
                "C0": {"type": "Claim", "text": "Root", "importance": 0.9},
                "C1": {"type": "Claim", "text": "Child", "importance": 0.8},
                "C2": {"type": "Claim", "text": "Grandchild", "importance": 0.7},
            },
            "edges": [{"source": "C1", "target": "C0", "type": "supports"}],
        }
    )
    units = [
        _unit("u0", "C0", relation="concludes"),
        _unit("u1", "C1", parent="u0", predecessors=("u0",)),
        _unit("u2", "C2", parent="u1", predecessors=("u1",)),
    ]
    report = audit_structure(model, _request(model, units=units, body_order=("u0", "u1", "u2")))
    rows = {(finding.code, finding.affected_blocks) for finding in report.findings}

    assert ("missing_parent_contribution", ("u1", "u2")) in rows
    assert ("ancestor_nonclosure", ("u1", "u2")) in rows
    assert ("ancestor_nonclosure", ("u0", "u1")) in rows
    assert not any(finding.code == "unrecovered_conclusion_obligation" for finding in report.findings)


def test_synthesis_computes_native_depth_itself():
    model = load_model_from_dict(
        {
            "model": {"id": "in-process-depth", "root_claim": "C0"},
            "nodes": {"C0": {"type": "Claim", "text": "Conclusion", "importance": 0.9}},
        }
    )
    request = _request(model, units=[_unit("u0", "C0", relation="concludes")], body_order=["u0"])
    plan = synthesize_artifact_plan(model, selection_request=request)
    expected = build_native_depth_analysis(model, budget=8, requested_claim_scope_ids=["C0"])

    assert plan.status == "blocked_support_gap"
    assert "native_depth_not_licensed" in plan.open_gaps
    assert all(f"native_depth_gap:{gap}" in plan.open_gaps for gap in expected.unresolved_gaps)
    assert not any("result" in gap for gap in plan.open_gaps)
