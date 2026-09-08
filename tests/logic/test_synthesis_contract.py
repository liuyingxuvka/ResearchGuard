from __future__ import annotations

from dataclasses import replace

from researchguard.logic import load_model_from_dict, model_fingerprint, synthesize_artifact_plan
from researchguard.logic.synthesis_contract import validate_selection_request


def _model():
    return load_model_from_dict({
        "model": {"id": "contract-model", "root_claim": "C0"},
        "nodes": {
            "C0": {"type": "Claim", "text": "The selected conclusion.", "importance": 0.9},
            "E0": {"type": "Evidence", "text": "Measured evidence.", "importance": 0.8},
        },
        "edges": [{"source": "E0", "target": "C0", "type": "supports"}],
    })


def _request(model, **overrides):
    request = {
        "schema": "researchguard.logic.synthesis-request.v1", "request_id": "req-1", "target_id": "artifact-1",
        "target_goal": "Answer the reader", "artifact_kind": "report", "reader_id": "reader-1",
        "model_id": model.id, "model_fingerprint": model_fingerprint(model), "body_unit_order": ["u1"],
        "max_body_units": 1, "units": [{"unit_id": "u1", "parent_unit_id": None, "reader_question": "What is the conclusion?",
        "unit_job": "State the bounded conclusion.", "claim_ids": ["C0"], "predecessor_unit_ids": [],
        "progression_relation": "concludes", "editorial_prominence": "lead", "placement": "body",
        "placement_reason": "Required by the reader question.", "required": True}], "source_branch_bindings": [],
    }
    request.update(overrides)
    return request


def test_selection_request_is_required_and_old_entry_does_not_fallback():
    model = _model()
    plan = synthesize_artifact_plan(model, selection_request={})
    assert plan.status == "blocked_invalid_request"
    assert "invalid_schema" in plan.open_gaps


def test_selection_request_preserves_unit_order_and_native_role_gap():
    model = _model()
    plan = synthesize_artifact_plan(model, selection_request=_request(model))
    payload = plan.to_dict()
    assert payload["body_unit_order"] == ["u1"]
    assert payload["units"][0]["research_importance"]["C0"] == 0.9
    assert any("support_gap:C0" in gap for gap in payload["open_gaps"])
    assert payload["status"] == "blocked_support_gap"


def test_body_budget_and_required_omit_are_visible():
    model = _model()
    request = _request(model, max_body_units=0)
    request["units"][0]["placement"] = "omit"
    request["units"][0]["required"] = True
    request["body_unit_order"] = []
    plan = synthesize_artifact_plan(model, selection_request=request)
    assert plan.status == "blocked_invalid_request"
    assert "required_unit_omitted" in plan.open_gaps


def test_unknown_source_branch_is_a_bounded_gap_instead_of_runtime_error():
    model = _model()
    request = _request(model, source_branch_bindings=[{
        "branch_id": "branch:missing",
        "source_id": "source:one",
        "current_native_evidence_ref": "receipt:one",
        "destination_unit_id": "u1",
        "anchor_node_id": "C0",
        "claim_ids": ["C0"],
    }])
    plan = synthesize_artifact_plan(model, selection_request=request)
    assert plan.status == "blocked_support_gap"
    assert "source_branch_binding:unknown_branch:branch:missing" in plan.open_gaps


def test_dataclass_transport_cannot_bypass_strict_mapping_validation():
    model = _model()
    normalized, errors = validate_selection_request(
        _request(model),
        expected_model_id=model.id,
        expected_model_fingerprint=model_fingerprint(model),
    )
    assert normalized is not None and not errors
    forged = replace(normalized, max_body_units=True, request_fingerprint="forged")
    _, forged_errors = validate_selection_request(
        forged,
        expected_model_id=model.id,
        expected_model_fingerprint=model_fingerprint(model),
    )
    assert "max_body_units_bool_forbidden" in forged_errors
    assert forged_errors


def test_parent_predecessor_graph_and_budget_fail_closed():
    model = _model()
    for field, value, expected in (
        ("parent_unit_id", "ghost", "unknown_parent"),
        ("predecessor_unit_ids", "ghost", "predecessor_unit_ids_not_list"),
    ):
        request = _request(model)
        request["units"][0][field] = value
        plan = synthesize_artifact_plan(model, selection_request=request)
        assert plan.status == "blocked_invalid_request"
        assert any(expected in gap for gap in plan.open_gaps)

    request = _request(model, max_body_units=1)
    request["units"].append({**request["units"][0], "unit_id": "u2", "claim_ids": ["C0"]})
    request["body_unit_order"] = ["u1", "u2"]
    plan = synthesize_artifact_plan(model, selection_request=request)
    assert plan.status == "blocked_budget"
    assert "u1,u2" in "".join(plan.open_gaps)


def test_source_branch_identity_anchor_and_receipt_are_independent_gates():
    model = _model()
    request = _request(
        model,
        source_branch_bindings=[
            {
                "branch_id": "BR1",
                "source_id": "source-a",
                "current_native_evidence_ref": "native:correct",
                "destination_unit_id": "u1",
                "anchor_node_id": "C0",
                "claim_ids": ["C0"],
            }
        ],
    )
    branches = [
        {
            "branch_id": "BR1",
            "source_id": "source-a",
            "anchor_node_id": "OTHER",
            "node_ids": ["OTHER"],
            "native_evidence_ref": "native:wrong",
            "topic_focus": "one branch",
        }
    ]
    plan = synthesize_artifact_plan(model, selection_request=request, source_branches=branches)
    assert plan.status == "blocked_support_gap"
    assert any("anchor_mismatch" in gap for gap in plan.open_gaps)
    assert any("native_evidence_mismatch" in gap for gap in plan.open_gaps)
    assert len([row for row in plan.candidate_dispositions if row.candidate_kind == "SourceBranch"]) == 1


def test_structure_audit_is_consumed_and_root_cannot_be_recovered_in_appendix():
    model = _model()
    request = _request(model)
    request["units"][0]["placement"] = "appendix"
    request["units"][0]["required"] = False
    request["body_unit_order"] = []
    plan = synthesize_artifact_plan(model, selection_request=request)
    assert plan.status == "blocked_support_gap"
    assert plan.structure_findings
    assert any(item["code"] == "unrecovered_conclusion_obligation" for item in plan.structure_findings)
    assert any(gap.startswith("structure:unrecovered_conclusion_obligation") for gap in plan.open_gaps)
