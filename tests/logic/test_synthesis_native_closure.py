from __future__ import annotations

from researchguard.logic import load_model_from_dict, model_fingerprint, synthesize_artifact_plan
from researchguard.logic.execution_depth import _build_native_depth_analysis
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


def test_public_or_persisted_depth_mapping_cannot_use_private_v2_shape_as_proof():
    model = load_model_from_dict(
        {
            "model": {"id": "native-depth-contract", "root_claim": "C0"},
            "nodes": {"C0": {"type": "Claim", "text": "Conclusion", "importance": 0.9}},
        }
    )
    request = _request(model, units=[_unit("u0", "C0", relation="concludes")], body_order=["u0"])
    private_receipt = _build_native_depth_analysis(model, budget=8)
    persisted = private_receipt.to_dict()

    plan = synthesize_artifact_plan(model, selection_request=request, native_depth_receipt=persisted)

    assert plan.status == "blocked_support_gap"
    assert "native_depth_receipt_not_public" in plan.open_gaps


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


def test_private_receipt_object_remains_usable_for_existing_narrow_native_fixture():
    model = load_model_from_dict(
        {
            "model": {"id": "narrow-native-fixture", "root_claim": "C0"},
            "nodes": {"C0": {"type": "Claim", "text": "Conclusion", "importance": 0.9}},
        }
    )
    request = _request(model, units=[_unit("u0", "C0", relation="concludes")], body_order=["u0"])
    receipt = _build_native_depth_analysis(model, budget=8)
    plan = synthesize_artifact_plan(model, selection_request=request, native_depth_receipt=receipt)

    # The object is still consumed by the native owner in narrow in-process
    # tests; persisted/path handoffs use the public-v3 gate above.
    assert "native_depth_receipt_not_public" not in plan.open_gaps


def test_public_depth_receipt_rejects_forged_target_proof_shape():
    model = load_model_from_dict(
        {
            "model": {"id": "forged-target-proof", "root_claim": "C0"},
            "nodes": {"C0": {"type": "Claim", "text": "Conclusion", "importance": 0.9}},
        }
    )
    request = _request(model, units=[_unit("u0", "C0", relation="concludes")], body_order=["u0"])
    payload = _build_native_depth_analysis(model, budget=8).to_dict()
    payload.update(
        {
            "receipt_version": "researchguard.logic.depth.v3",
            "target_contract_id": "contract:forged",
            "target_contract_fingerprint": "fingerprint:forged",
            "target_purpose": "forged purpose",
            "target_proof_receipt": {
                "schema_version": "researchguard.logic.target_model_purpose_proof.v1",
                "status": "pass",
                "contract_role": "target_model_instance",
                "target_skill_id": "logicguard",
                "contract_id": "contract:forged",
                "contract_fingerprint": "fingerprint:forged",
                "model_id": model.id,
                "candidate_relative_path": "models/current.json",
                "candidate_model_fingerprint": payload["model_fingerprint"],
                "native_model_fingerprint": payload["model_fingerprint"],
                "native_owner_id": "forged-owner",
                "native_route_id": "forged-route",
                "prevented_failure_purpose": "forged purpose",
                "claim_boundary": "forged boundary",
                "selectable_modes": [],
                "failure_proofs": [],
                "proofed_failure_count": 0,
            },
        }
    )

    plan = synthesize_artifact_plan(model, selection_request=request, native_depth_receipt=payload)

    assert plan.status == "blocked_support_gap"
    assert "native_depth_receipt_target_proof_failure_proofs_missing" in plan.open_gaps
    assert "native_depth_receipt_target_proof_count_invalid" not in plan.open_gaps


def test_public_depth_receipt_rejects_inconsistent_target_failure_proof():
    model = load_model_from_dict(
        {
            "model": {"id": "inconsistent-target-proof", "root_claim": "C0"},
            "nodes": {"C0": {"type": "Claim", "text": "Conclusion", "importance": 0.9}},
        }
    )
    request = _request(model, units=[_unit("u0", "C0", relation="concludes")], body_order=["u0"])
    payload = _build_native_depth_analysis(model, budget=8).to_dict()
    payload.update(
        {
            "receipt_version": "researchguard.logic.depth.v3",
            "target_contract_id": "contract:current",
            "target_contract_fingerprint": "fingerprint:current",
            "target_purpose": "current purpose",
            "target_proof_receipt": {
                "schema_version": "researchguard.logic.target_model_purpose_proof.v1",
                "status": "pass",
                "contract_role": "target_model_instance",
                "target_skill_id": "logicguard",
                "contract_id": "contract:other",
                "contract_fingerprint": "fingerprint:other",
                "model_id": model.id,
                "candidate_relative_path": "models/current.json",
                "candidate_model_fingerprint": payload["model_fingerprint"],
                "native_model_fingerprint": "different-model",
                "native_owner_id": "owner",
                "native_route_id": "route",
                "prevented_failure_purpose": "other purpose",
                "claim_boundary": "bounded",
                "selectable_modes": [],
                "failure_proofs": [
                    {
                        "failure_id": "failure:one",
                        "oracle": {
                            "kind": "primary_depth_gap_prefix",
                            "finding_code": "missing_role",
                        },
                        "known_good_sha256": "good",
                        "known_bad_sha256": "bad",
                        "known_good_status": "pass",
                        "known_bad_status": "blocked",
                        "candidate_status": "pass",
                        "finding_observed_in_bad": True,
                        "finding_absent_from_good_and_candidate": True,
                    }
                ],
                "proofed_failure_count": 1,
            },
        }
    )

    plan = synthesize_artifact_plan(model, selection_request=request, native_depth_receipt=payload)

    assert "native_depth_receipt_target_proof_target_contract_id_mismatch" in plan.open_gaps
    assert "native_depth_receipt_target_proof_native_model_fingerprint_mismatch" in plan.open_gaps
    assert "native_depth_receipt_target_proof_target_purpose_mismatch" in plan.open_gaps
