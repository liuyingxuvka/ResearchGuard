"""Argument-unit synthesis owned by LogicGuard.

Editorial callers choose units and order. This module checks that request and
hands each selected claim to the native argument-coverage owner; it never
selects a top-N story by itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import copy
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from .citation_matrix import ClaimSourceParagraphMatrix, build_claim_source_paragraph_matrix
from .execution_depth import build_argument_coverage_universe, model_fingerprint
from .evaluator import evaluate_model
from .importance import ImportanceRecord, summarize_importance
from .model import LogicDepthReceipt, LogicModel
from .schema import STATE_IN
from .structure_audit import audit_structure
from .synthesis_contract import SelectionRequest, SYNTHESIS_REQUEST_SCHEMA, validate_selection_request
from .loader import load_model


# ``_build_native_depth_analysis`` is still useful to the native depth owner
# and to narrow in-process tests, but persisted/public depth evidence has a
# separate versioned contract.  Keep both version strings visible here so a
# caller cannot pass an arbitrary mapping that merely happens to contain
# ``status=pass``.
_NATIVE_DEPTH_RECEIPT_VERSIONS = {
    "researchguard.logic.depth.v2",
    "researchguard.logic.depth.v3",
}
_PUBLIC_NATIVE_DEPTH_RECEIPT_VERSION = "researchguard.logic.depth.v3"
_TARGET_PROOF_SCHEMA = "researchguard.logic.target_model_purpose_proof.v1"
_TARGET_PROOF_ROLE = "target_model_instance"
_TARGET_PROOF_SKILL_ID = "logicguard"
_TARGET_PROOF_ORACLE_KINDS = {
    "primary_depth_gap_prefix",
    "primary_diagnostic_code",
}


def _target_proof_receipt_gaps(
    payload: Mapping[str, Any],
    *,
    expected_native_model_fingerprint: str = "",
) -> list[str]:
    """Validate the target-purpose proof carried by a public depth receipt.

    The native owner creates this proof after replaying the frozen target
    contract.  Synthesis cannot replay the target files itself, but it must
    still reject a hand-written proof that only copies the contract labels or
    a claimed model fingerprint.  Check the complete producer shape and all
    cross-field identities here; the target owner remains responsible for the
    actual good/bad case replay.
    """

    gaps: list[str] = []
    proof = payload.get("target_proof_receipt")
    if not isinstance(proof, Mapping):
        return ["native_depth_receipt_target_proof_invalid"]

    if proof.get("schema_version") != _TARGET_PROOF_SCHEMA:
        gaps.append("native_depth_receipt_target_proof_schema_invalid")
    if proof.get("status") != "pass":
        gaps.append("native_depth_receipt_target_proof_not_pass")
    if proof.get("contract_role") != _TARGET_PROOF_ROLE:
        gaps.append("native_depth_receipt_target_proof_role_invalid")
    if proof.get("target_skill_id") != _TARGET_PROOF_SKILL_ID:
        gaps.append("native_depth_receipt_target_proof_skill_mismatch")
    if proof.get("selectable_modes") != []:
        gaps.append("native_depth_receipt_target_proof_selectable_modes_invalid")

    identity_pairs = (
        ("target_contract_id", "contract_id"),
        ("target_contract_fingerprint", "contract_fingerprint"),
        ("target_purpose", "prevented_failure_purpose"),
        ("model_id", "model_id"),
    )
    for receipt_field, proof_field in identity_pairs:
        expected = payload.get(receipt_field)
        actual = proof.get(proof_field)
        if type(expected) is not str or not expected.strip():
            gaps.append(f"native_depth_receipt_target_{receipt_field}_invalid")
        elif actual != expected:
            gaps.append(f"native_depth_receipt_target_proof_{receipt_field}_mismatch")

    for field in (
        "contract_id",
        "contract_fingerprint",
        "model_id",
        "candidate_relative_path",
        "candidate_model_fingerprint",
        "native_model_fingerprint",
        "native_owner_id",
        "native_route_id",
        "prevented_failure_purpose",
        "claim_boundary",
    ):
        value = proof.get(field)
        if type(value) is not str or not value.strip():
            gaps.append(f"native_depth_receipt_target_proof_missing:{field}")

    if (
        expected_native_model_fingerprint
        and proof.get("native_model_fingerprint") != expected_native_model_fingerprint
    ):
        gaps.append("native_depth_receipt_target_proof_native_model_fingerprint_mismatch")

    raw_proofs = proof.get("failure_proofs")
    if not isinstance(raw_proofs, list) or not raw_proofs:
        gaps.append("native_depth_receipt_target_proof_failure_proofs_missing")
        raw_proofs = []
    raw_count = proof.get("proofed_failure_count")
    if type(raw_count) is not int or isinstance(raw_count, bool):
        gaps.append("native_depth_receipt_target_proof_count_invalid")
    elif raw_count != len(raw_proofs):
        gaps.append("native_depth_receipt_target_proof_count_mismatch")

    seen_failure_ids: set[str] = set()
    required_failure_fields = (
        "failure_id",
        "known_good_sha256",
        "known_bad_sha256",
        "known_good_status",
        "known_bad_status",
        "candidate_status",
        "finding_observed_in_bad",
        "finding_absent_from_good_and_candidate",
    )
    for index, row in enumerate(raw_proofs):
        prefix = f"native_depth_receipt_target_proof_failure:{index}"
        if not isinstance(row, Mapping):
            gaps.append(f"{prefix}:not_mapping")
            continue
        failure_id = row.get("failure_id")
        if type(failure_id) is not str or not failure_id.strip():
            gaps.append(f"{prefix}:missing_failure_id")
        elif failure_id in seen_failure_ids:
            gaps.append(f"{prefix}:duplicate_failure_id")
        else:
            seen_failure_ids.add(failure_id)
        for field in required_failure_fields:
            if field not in row:
                gaps.append(f"{prefix}:missing:{field}")
        oracle = row.get("oracle")
        if not isinstance(oracle, Mapping):
            gaps.append(f"{prefix}:oracle_invalid")
        else:
            if oracle.get("kind") not in _TARGET_PROOF_ORACLE_KINDS:
                gaps.append(f"{prefix}:oracle_kind_invalid")
            finding_code = oracle.get("finding_code")
            if type(finding_code) is not str or not finding_code.strip():
                gaps.append(f"{prefix}:oracle_finding_invalid")
        if row.get("known_good_status") != "pass":
            gaps.append(f"{prefix}:known_good_not_pass")
        if row.get("known_bad_status") != "blocked":
            gaps.append(f"{prefix}:known_bad_not_blocked")
        if row.get("candidate_status") != "pass":
            gaps.append(f"{prefix}:candidate_not_pass")
        if row.get("finding_observed_in_bad") is not True:
            gaps.append(f"{prefix}:bad_finding_not_observed")
        if row.get("finding_absent_from_good_and_candidate") is not True:
            gaps.append(f"{prefix}:good_candidate_finding_not_absent")
        for field in ("known_good_sha256", "known_bad_sha256"):
            value = row.get(field)
            if type(value) is not str or not value.strip():
                gaps.append(f"{prefix}:{field}_invalid")

    return list(dict.fromkeys(gaps))


@dataclass(frozen=True)
class SynthesisItem:
    node_id: str
    node_type: str
    salience: str
    importance: float
    text: str
    reason: str
    treatment: str = ""
    source_id: str = ""
    source_ids: tuple[str, ...] = ()
    source_roles: dict[str, str] = field(default_factory=dict)
    paragraph_locator: str = ""
    citation_marker: str = ""
    claim_strength: str = ""
    limitation: str = ""
    branch_id: str = ""
    anchor_node_id: str = ""
    anchor_block_id: str = ""
    branch_role: str = ""
    source_date: str = ""
    coverage_period: str = ""
    temporal_role: str = ""
    temporal_caveat: str = ""
    source_node_ids: tuple[str, ...] = ()
    source_project_id: str = ""
    source_model_fingerprint: str = ""
    native_evidence_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = {"node_id": self.node_id, "node_type": self.node_type, "salience": self.salience,
                "importance": round(self.importance, 4), "text": self.text, "reason": self.reason,
                "treatment": self.treatment, "source_id": self.source_id, "source_ids": list(self.source_ids),
                "source_roles": dict(self.source_roles), "paragraph_locator": self.paragraph_locator,
                "citation_marker": self.citation_marker, "claim_strength": self.claim_strength,
                "limitation": self.limitation, "branch_id": self.branch_id, "anchor_node_id": self.anchor_node_id,
                "anchor_block_id": self.anchor_block_id, "branch_role": self.branch_role,
                "source_date": self.source_date, "coverage_period": self.coverage_period,
                "temporal_role": self.temporal_role, "temporal_caveat": self.temporal_caveat,
                "source_node_ids": list(self.source_node_ids), "source_project_id": self.source_project_id,
                "source_model_fingerprint": self.source_model_fingerprint,
                "native_evidence_ref": self.native_evidence_ref}
        return {key: value for key, value in data.items() if value not in ("", [], (), None)}


@dataclass(frozen=True)
class SynthesisUnit:
    unit_id: str
    parent_unit_id: str | None
    reader_question: str
    unit_job: str
    claim_ids: tuple[str, ...]
    predecessor_unit_ids: tuple[str, ...]
    progression_relation: str
    editorial_prominence: str
    placement: str
    placement_reason: str
    required: bool
    argument_closure: tuple[str, ...] = ()
    role_bindings: dict[str, tuple[str, ...]] = field(default_factory=dict)
    source_branch_ids: tuple[str, ...] = ()
    source_branch_candidate_ids: tuple[str, ...] = ()
    research_importance: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"unit_id": self.unit_id, "parent_unit_id": self.parent_unit_id,
                "reader_question": self.reader_question, "unit_job": self.unit_job,
                "claim_ids": list(self.claim_ids), "predecessor_unit_ids": list(self.predecessor_unit_ids),
                "progression_relation": self.progression_relation, "editorial_prominence": self.editorial_prominence,
                "placement": self.placement, "placement_reason": self.placement_reason, "required": self.required,
                "argument_closure": list(self.argument_closure),
                "role_bindings": {key: list(value) for key, value in self.role_bindings.items()},
                "source_branch_ids": list(self.source_branch_ids),
                "source_branch_candidate_ids": list(self.source_branch_candidate_ids),
                "research_importance": {key: round(value, 4) for key, value in self.research_importance.items()}}


@dataclass(frozen=True)
class CandidateDisposition:
    candidate_id: str
    candidate_kind: str
    placement: str
    reason: str
    selected_unit_ids: tuple[str, ...] = ()
    unit_placements: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"candidate_id": self.candidate_id, "candidate_kind": self.candidate_kind,
                "placement": self.placement, "reason": self.reason,
                "selected_unit_ids": list(self.selected_unit_ids),
                "unit_placements": dict(self.unit_placements)}


@dataclass(frozen=True)
class SynthesisPlan:
    model_id: str
    target_goal: str
    profile: str
    units: tuple[SynthesisUnit, ...]
    body_unit_order: tuple[str, ...]
    candidate_dispositions: tuple[CandidateDisposition, ...]
    open_gaps: tuple[str, ...]
    status: str
    claim_boundary: str
    model_fingerprint: str
    selection_request_fingerprint: str
    request_schema: str = SYNTHESIS_REQUEST_SCHEMA
    selected_items: tuple[SynthesisItem, ...] = ()
    omitted_items: tuple[SynthesisItem, ...] = ()
    missing_additions: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    structure_findings: tuple[dict[str, Any], ...] = ()
    native_evaluation: dict[str, Any] = field(default_factory=dict)
    native_coverage: dict[str, Any] = field(default_factory=dict)
    native_depth_receipt_ref: str = ""
    # Preserve the exact request-side source branch bindings at the public
    # handoff boundary.  The native planner validates these rows; consumers
    # must not reconstruct them from candidate ids or unit text.
    source_branch_bindings: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "researchguard.logic.synthesis-plan.v1", "model_id": self.model_id,
                "target_goal": self.target_goal, "profile": self.profile, "units": [u.to_dict() for u in self.units],
                "body_unit_order": list(self.body_unit_order),
                "candidate_dispositions": [item.to_dict() for item in self.candidate_dispositions],
                "open_gaps": list(self.open_gaps), "status": self.status, "claim_boundary": self.claim_boundary,
                "model_fingerprint": self.model_fingerprint,
                "selection_request_fingerprint": self.selection_request_fingerprint,
                "request_schema": self.request_schema,
                "selected_items": [item.to_dict() for item in self.selected_items],
                "omitted_items": [item.to_dict() for item in self.omitted_items],
                "missing_additions": list(self.missing_additions),
                "notes": list(self.notes),
                "structure_findings": [dict(item) for item in self.structure_findings],
                "native_evaluation": dict(self.native_evaluation),
                "native_coverage": dict(self.native_coverage),
                "native_depth_receipt_ref": self.native_depth_receipt_ref,
                "source_branch_bindings": [dict(item) for item in self.source_branch_bindings]}

    def to_markdown(self) -> str:
        lines = [f"# Synthesis Plan: {self.target_goal}", "", f"- Profile: {self.profile}", f"- Status: {self.status}", "",
                 "## Body Unit Order"]
        lines.extend(f"{index}. {unit_id}" for index, unit_id in enumerate(self.body_unit_order, start=1))
        lines.extend(["", "## Argument Units"])
        if not self.units:
            lines.append("- No units supplied.")
        for unit in self.units:
            lines.append(f"- {unit.unit_id} ({unit.progression_relation}, {unit.editorial_prominence}, placement={unit.placement}): {unit.unit_job}")
            if unit.argument_closure:
                lines.append(f"  - Argument closure: {', '.join(unit.argument_closure)}")
        for item in self.selected_items:
            if item.source_ids or item.citation_marker or item.paragraph_locator:
                lines.append(f"  - Citation plan: {item.citation_marker or 'missing marker'} at {item.paragraph_locator or 'unassigned paragraph'} ({item.node_id})")
        lines.extend(["", "## Open Gaps"])
        lines.extend(f"- {gap}" for gap in self.open_gaps) if self.open_gaps else lines.append("- None identified.")
        return "\n".join(lines) + "\n"


def synthesize_artifact_plan(
    model: LogicModel,
    *,
    selection_request: Mapping[str, Any] | SelectionRequest,
    source_branches: Iterable[Any] = (),
    native_depth_receipt: LogicDepthReceipt | Mapping[str, Any] | str | Path | None = None,
    source_library: Any | None = None,
    native_mesh_overlay: Mapping[str, Any] | str | Path | None = None,
) -> SynthesisPlan:
    """Build a bounded plan from one explicit reader request.

    The request supplies editorial intent; the evaluator and coverage owner
    supply the native state used to license that intent.  This function keeps
    the two layers separate so an internally coherent JSON object cannot
    manufacture a successful argument handoff.
    """
    current_model_fingerprint = model_fingerprint(model)
    request, request_errors = validate_selection_request(
        selection_request,
        expected_model_id=model.id,
        expected_model_fingerprint=current_model_fingerprint,
    )
    raw_request = selection_request.to_dict() if isinstance(selection_request, SelectionRequest) else selection_request
    if not isinstance(raw_request, Mapping):
        raw_request = {}
    target_goal = str(raw_request.get("target_goal", "") or "")
    profile = str(raw_request.get("artifact_kind", "") or "")
    request_fp = request.request_fingerprint if request is not None else ""
    if request is not None:
        target_goal, profile = request.target_goal, request.artifact_kind
    if request_errors:
        return _blocked_plan(
            model,
            target_goal=target_goal,
            profile=profile,
            status="blocked_invalid_request",
            gaps=request_errors,
            request_fingerprint=request_fp,
        )
    assert request is not None

    # Evaluate once and pass the frozen result to the native coverage owner.
    # Calling either owner without the other would allow a stale result to be
    # paired with a current model.
    evaluation = evaluate_model(model)
    claims = tuple(dict.fromkeys(str(claim_id) for unit in request.units for claim_id in unit.get("claim_ids", ())))
    coverage = build_argument_coverage_universe(
        model,
        evaluation,
        requested_claim_scope_ids=claims,
    )
    open_gaps: list[str] = []
    open_gaps.extend(_native_scope_gaps(model, request, evaluation, coverage, native_depth_receipt))
    if native_mesh_overlay is not None:
        open_gaps.extend(
            _mesh_overlay_gaps(
                model,
                claims,
                native_mesh_overlay,
                native_depth_receipt=native_depth_receipt
                if native_depth_receipt is not None
                else request.native_depth_receipt_ref,
            )
        )

    raw_branch_data = [_branch_data(branch) for branch in source_branches]
    branch_items: list[SynthesisItem] = []
    branch_by_key: dict[tuple[str, str], SynthesisItem] = {}
    branch_by_candidate_id: dict[str, tuple[str, str]] = {}
    for index, branch in enumerate(raw_branch_data):
        source_id = str(branch.get("source_id", "") or "")
        branch_id = str(branch.get("branch_id", "") or "")
        key = (source_id, branch_id)
        if not source_id or not branch_id:
            open_gaps.append(f"source_branch[{index}]:missing_source_or_branch_id")
            continue
        candidate = _item_from_branch(branch)
        previous = branch_by_key.get(key)
        if previous is not None:
            if _branch_semantic_payload(previous) != _branch_semantic_payload(candidate):
                open_gaps.append(f"source_branch_duplicate_conflict:{source_id}:{branch_id}")
            # Exact duplicate records are normalised once.  They never create
            # a second candidate disposition.
            continue
        candidate_owner = branch_by_candidate_id.get(candidate.node_id)
        if candidate_owner is not None and candidate_owner != key:
            open_gaps.append(
                f"source_branch_candidate_id_collision:{candidate.node_id}:"
                f"{candidate_owner[0]}:{candidate_owner[1]}:{source_id}:{branch_id}"
            )
            continue
        if candidate.node_id in model.nodes:
            open_gaps.append(f"source_branch_candidate_id_model_collision:{candidate.node_id}")
            continue
        branch_by_key[key] = candidate
        branch_by_candidate_id[candidate.node_id] = key
        branch_items.append(candidate)

    bound_branches: dict[str, list[str]] = {}
    bound_branch_candidates: dict[str, list[str]] = {}
    for index, binding in enumerate(request.source_branch_bindings):
        source_id = str(binding.get("source_id", ""))
        branch_id = str(binding.get("branch_id", ""))
        key = (source_id, branch_id)
        candidate = branch_by_key.get(key)
        if candidate is None:
            open_gaps.append(f"source_branch_binding:unknown_branch:{branch_id}")
            open_gaps.append(f"source_branch_binding:unknown_identity:{source_id}:{branch_id}")
            continue
        binding_gaps = _branch_binding_gaps(binding, candidate, source_library=source_library)
        open_gaps.extend(f"source_branch_binding:{source_id}:{branch_id}:{gap}" for gap in binding_gaps)
        destination = str(binding["destination_unit_id"])
        bound_branches.setdefault(destination, []).append(candidate.branch_id)
        bound_branch_candidates.setdefault(destination, []).append(candidate.node_id)

    branch_items = list(_with_temporal_roles(branch_items))
    records = [
        record
        for record in summarize_importance(model, limit=None).records
        if record.subject_type not in {"Document", "Section", "ArgumentBlock", "Edge"} and record.text
    ]
    matrix = build_claim_source_paragraph_matrix(model)
    node_items = list(_with_temporal_roles([_item_from_record(record, model, matrix) for record in records]))
    candidates = tuple((*branch_items, *node_items))
    item_by_id = {item.node_id: item for item in candidates}
    units: list[SynthesisUnit] = []
    selected_units_by_item: dict[str, list[str]] = {}
    selected_items: list[SynthesisItem] = []
    claim_use = {str(row["claim_id"]): row for row in request.claim_use_dispositions}

    for raw_unit in request.units:
        unit_id = str(raw_unit["unit_id"])
        claim_ids = tuple(str(value) for value in raw_unit.get("claim_ids", ()))
        unit_placement = str(raw_unit.get("placement", ""))
        closure: set[str] = set()
        role_bindings: dict[str, set[str]] = {}
        importance: dict[str, float] = {}
        for claim_id in claim_ids:
            if claim_id not in model.nodes:
                open_gaps.append(f"unit:{unit_id}:unknown_claim:{claim_id}")
                continue
            closure.add(claim_id)
            importance[claim_id] = _importance_value(model, claim_id)
            # An explicit omit is a disposition, not a request for native
            # support.  Keep its identity in the unit and candidate ledger,
            # but do not let intentionally excluded material block the
            # selected body/note/appendix scope.
            if unit_placement == "omit":
                continue
            evaluation_row = evaluation.node_results.get(claim_id)
            use_row = claim_use.get(claim_id)
            use = str(use_row.get("use", "assert")) if use_row else "assert"
            if evaluation_row is None:
                open_gaps.append(f"unit:{unit_id}:native_evaluation_missing:{claim_id}")
            elif evaluation_row.state != STATE_IN and use == "assert":
                open_gaps.append(f"unit:{unit_id}:claim_not_in:{claim_id}:{evaluation_row.state}")
            elif evaluation_row.state != STATE_IN and use != "assert":
                if not use_row or not str(use_row.get("native_allowed_wording", "")).strip() or not str(use_row.get("native_evaluation_ref", "")).strip():
                    open_gaps.append(f"unit:{unit_id}:claim_use_unlicensed:{claim_id}:{use}")
            row = next((item for item in coverage.claim_role_coverage if item.claim_id == claim_id), None)
            if row is None:
                open_gaps.append(f"unit:{unit_id}:support_gap:{claim_id}:coverage_missing")
                continue
            for role, node_ids in row.connected_role_node_ids.items():
                role_bindings.setdefault(role, set()).update(node_ids)
                closure.update(node_ids)
            if row.status != "pass":
                details = [
                    *row.missing_roles,
                    *(f"unresolved:{value}" for value in row.unresolved_disposition_roles),
                    *(f"implicit_shared:{value}" for value in row.implicit_shared_role_node_ids),
                ]
                open_gaps.append(f"unit:{unit_id}:native_claim_role_blocked:{claim_id}:{','.join(details) or 'status'}")
            for role in row.missing_roles:
                open_gaps.append(f"unit:{unit_id}:support_gap:{claim_id}:{role}")
            for role in row.unresolved_disposition_roles:
                open_gaps.append(f"unit:{unit_id}:support_gap:{claim_id}:{role}:unresolved")
            for node_id in row.implicit_shared_role_node_ids:
                open_gaps.append(f"unit:{unit_id}:support_gap:{claim_id}:implicit_shared:{node_id}")
            closure.update(row.applicable_perturbation_node_ids)
        closure = _expand_argument_closure(model, closure)
        branch_ids = tuple(dict.fromkeys(bound_branches.get(unit_id, ())))
        branch_candidate_ids = tuple(dict.fromkeys(bound_branch_candidates.get(unit_id, ())))
        unit = SynthesisUnit(
            unit_id=unit_id,
            parent_unit_id=(str(raw_unit["parent_unit_id"]) if raw_unit.get("parent_unit_id") is not None else None),
            reader_question=str(raw_unit["reader_question"]),
            unit_job=str(raw_unit["unit_job"]),
            claim_ids=claim_ids,
            predecessor_unit_ids=tuple(str(value) for value in raw_unit.get("predecessor_unit_ids", ())),
            progression_relation=str(raw_unit["progression_relation"]),
            editorial_prominence=str(raw_unit["editorial_prominence"]),
            placement=unit_placement,
            placement_reason=str(raw_unit["placement_reason"]),
            required=bool(raw_unit["required"]),
            argument_closure=tuple(sorted(closure)),
            role_bindings={key: tuple(sorted(value)) for key, value in sorted(role_bindings.items())},
            source_branch_ids=branch_ids,
            source_branch_candidate_ids=branch_candidate_ids,
            research_importance=importance,
        )
        units.append(unit)
        unit_item_ids = tuple(dict.fromkeys((*claim_ids, *sorted(closure.difference(claim_ids)), *branch_candidate_ids)))
        for item_id in unit_item_ids:
            selected_units_by_item.setdefault(item_id, []).append(unit_id)
            item = item_by_id.get(item_id)
            if item is not None and unit.placement != "omit":
                selected_items.append(item)

    # Preserve each candidate exactly once.  A candidate selected by several
    # units retains every unit placement while its aggregate display location
    # follows the deterministic body > note > appendix > omit rule.
    placement_rank = {"body": 0, "note": 1, "appendix": 2, "omit": 3}
    omitted_items: list[SynthesisItem] = []
    dispositions: list[CandidateDisposition] = []
    for item in candidates:
        unit_ids = tuple(dict.fromkeys(selected_units_by_item.get(item.node_id, ())))
        if unit_ids:
            unit_placements = {
                unit_id: next(unit.placement for unit in units if unit.unit_id == unit_id)
                for unit_id in unit_ids
            }
            placement = min(unit_placements.values(), key=lambda value: placement_rank.get(value, 99))
            dispositions.append(CandidateDisposition(
                item.node_id,
                item.node_type,
                placement,
                "Selected by explicit reader units; native closure and every unit placement remain visible.",
                unit_ids,
                unit_placements,
            ))
        else:
            omitted = _omitted_item(item)
            omitted_items.append(omitted)
            placement = "appendix" if omitted.treatment == "appendix" else "omit"
            dispositions.append(CandidateDisposition(
                item.node_id,
                item.node_type,
                placement,
                "Not selected by the supplied unit request; retained as a complete machine disposition.",
                (),
                {},
            ))

    structure_report = audit_structure(model, request.to_dict())
    structure_findings = tuple(finding.to_dict() for finding in structure_report.findings)
    open_gaps.extend(
        f"structure:{finding.code}:{','.join(finding.affected_blocks)}"
        for finding in structure_report.findings
        if finding.severity in {"error", "critical"}
    )
    required_body_ids = tuple(unit.unit_id for unit in units if unit.required and unit.placement == "body")
    if len(request.body_unit_order) > request.max_body_units or len(required_body_ids) > request.max_body_units:
        open_gaps.append(
            f"budget:required_body_unit_ids={','.join(required_body_ids)}:count={len(request.body_unit_order)}:max_body_units={request.max_body_units}"
        )
    status = (
        "blocked_budget"
        if len(request.body_unit_order) > request.max_body_units or len(required_body_ids) > request.max_body_units
        else "blocked_support_gap" if open_gaps
        else "research_handoff_ready"
    )
    return SynthesisPlan(
        model_id=model.id,
        target_goal=request.target_goal,
        profile=request.artifact_kind,
        units=tuple(units),
        body_unit_order=request.body_unit_order,
        candidate_dispositions=tuple(dispositions),
        open_gaps=tuple(dict.fromkeys(open_gaps)),
        status=status,
        claim_boundary="This is a LogicGuard argument-unit handoff. It preserves native support gaps and does not license article quality or factual certainty.",
        model_fingerprint=current_model_fingerprint,
        selection_request_fingerprint=request.request_fingerprint,
        selected_items=tuple(_dedupe_items(selected_items)),
        omitted_items=tuple(omitted_items),
        missing_additions=tuple(gap for gap in open_gaps if "support_gap" in gap or "native_" in gap),
        notes=(
            "Editorial unit order, prominence, placement, and budget are caller-owned; LogicGuard validates their argument closure.",
            "Research importance remains attached to claims and is separate from editorial prominence.",
            "A research handoff is not evidence that the resulting article is coherent, factual, or stylistically acceptable.",
        ),
        structure_findings=structure_findings,
        native_evaluation=_evaluation_summary(evaluation),
        native_coverage=coverage.to_dict(),
        native_depth_receipt_ref=request.native_depth_receipt_ref,
        source_branch_bindings=tuple(dict(item) for item in request.source_branch_bindings),
    )


def _evaluation_summary(evaluation: Any) -> dict[str, Any]:
    root = evaluation.root() if hasattr(evaluation, "root") else None
    return {
        "summary": evaluation.summary() if hasattr(evaluation, "summary") else "",
        "root_claim": getattr(evaluation, "root_claim", None),
        "root_state": getattr(root, "state", "") if root is not None else "",
        "root_confidence": getattr(root, "confidence", None) if root is not None else None,
        "iterations": getattr(evaluation, "iterations", 0),
        "converged": bool(getattr(evaluation, "converged", False)),
        "model_revision_id": getattr(evaluation, "model_revision_id", None),
    }


def _dedupe_items(items: Iterable[SynthesisItem]) -> list[SynthesisItem]:
    seen: set[str] = set()
    result: list[SynthesisItem] = []
    for item in items:
        if item.node_id in seen:
            continue
        seen.add(item.node_id)
        result.append(item)
    return result


def _load_artifact(value: Any) -> Mapping[str, Any] | None:
    """Load a JSON/YAML receipt without accepting arbitrary object attributes."""
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, LogicDepthReceipt):
        return value.to_dict()
    if isinstance(value, (str, Path)):
        path = Path(value)
        if not path.exists() or not path.is_file():
            return None
        try:
            text = path.read_text(encoding="utf-8")
            if path.suffix.lower() in {".yaml", ".yml"}:
                import yaml

                loaded = yaml.safe_load(text)
            else:
                loaded = json.loads(text)
        except (OSError, ValueError, TypeError):
            return None
        return dict(loaded) if isinstance(loaded, Mapping) else None
    if hasattr(value, "to_dict"):
        loaded = value.to_dict()
        return dict(loaded) if isinstance(loaded, Mapping) else None
    return None


def _native_scope_gaps(
    model: LogicModel,
    request: SelectionRequest,
    evaluation: Any,
    coverage: Any,
    native_depth_receipt: Any,
) -> list[str]:
    gaps: list[str] = []
    selected_claims = tuple(
        dict.fromkeys(
            str(value)
            for unit in request.units
            if str(unit.get("placement", "")) != "omit"
            for value in unit.get("claim_ids", ())
        )
    )
    use_by_claim = {str(row.get("claim_id", "")): str(row.get("use", "assert")) for row in request.claim_use_dispositions}
    assert_claims = {claim_id for claim_id in selected_claims if use_by_claim.get(claim_id, "assert") == "assert"}
    required_assertion = any(
        str(unit.get("placement", "")) in {"body", "note", "appendix"}
        and bool(assert_claims.intersection(str(value) for value in unit.get("claim_ids", ())))
        for unit in request.units
    )
    if required_assertion:
        reference = native_depth_receipt if native_depth_receipt is not None else request.native_depth_receipt_ref
        if reference in (None, ""):
            gaps.append("native_depth_receipt_missing")
        else:
            payload = _load_artifact(reference)
            if payload is None:
                gaps.append("native_depth_receipt_unresolved")
            else:
                receipt_version = payload.get("receipt_version")
                if receipt_version not in _NATIVE_DEPTH_RECEIPT_VERSIONS:
                    gaps.append("native_depth_receipt_version_invalid")
                elif not isinstance(reference, LogicDepthReceipt) and receipt_version != _PUBLIC_NATIVE_DEPTH_RECEIPT_VERSION:
                    # A persisted or caller-supplied object must come from the
                    # public target-contract-bound owner.  The in-memory v2
                    # object remains available to the native owner itself and
                    # to narrow unit tests, but cannot be smuggled in as a
                    # JSON/path success artifact.
                    gaps.append("native_depth_receipt_not_public")
                if str(payload.get("model_id", "")) != model.id:
                    gaps.append("native_depth_receipt_model_mismatch")
                if str(payload.get("model_fingerprint", "")) != model_fingerprint(model):
                    gaps.append("native_depth_receipt_model_fingerprint_mismatch")
                if str(payload.get("status", "")) != "pass" or payload.get("broad_claim_licensed") is not True:
                    gaps.append("native_depth_receipt_not_licensed")
                if receipt_version == _PUBLIC_NATIVE_DEPTH_RECEIPT_VERSION:
                    for field in ("target_contract_id", "target_contract_fingerprint", "target_purpose", "target_proof_receipt"):
                        value = payload.get(field)
                        if value in (None, "", {}):
                            gaps.append(f"native_depth_receipt_missing:{field}")
                    comparison_model = copy.deepcopy(model)
                    comparison_model.metadata.pop("source_path", None)
                    gaps.extend(
                        _target_proof_receipt_gaps(
                            payload,
                            expected_native_model_fingerprint=model_fingerprint(comparison_model),
                        )
                    )
                if request.request_fingerprint and payload.get("selection_request_fingerprint") not in (None, "", request.request_fingerprint):
                    gaps.append("native_depth_receipt_request_mismatch")
                unresolved = payload.get("unresolved_gaps", ())
                if isinstance(unresolved, (list, tuple)) and unresolved:
                    gaps.extend(f"native_depth_receipt_gap:{value}" for value in unresolved)
                receipt_scope = payload.get("coverage_universe")
                if isinstance(receipt_scope, Mapping):
                    covered = set(receipt_scope.get("important_node_ids", ()))
                    gaps.extend(f"native_depth_receipt_scope_missing:{claim_id}" for claim_id in selected_claims if claim_id not in covered)
                    claim_scope = receipt_scope.get("claim_scope")
                    # The private in-memory v2 helper historically omitted an
                    # explicit requested scope when called without one.  Keep
                    # that narrow diagnostic fixture usable, while requiring
                    # the scope on every persisted/public v3 handoff.
                    if isinstance(claim_scope, Mapping):
                        requested_scope = set(claim_scope.get("requested_node_ids", ()))
                        if receipt_version == _PUBLIC_NATIVE_DEPTH_RECEIPT_VERSION or not isinstance(reference, LogicDepthReceipt):
                            gaps.extend(
                                f"native_depth_receipt_requested_scope_missing:{claim_id}"
                                for claim_id in selected_claims
                                if claim_id not in requested_scope
                            )
                    elif receipt_version == _PUBLIC_NATIVE_DEPTH_RECEIPT_VERSION or not isinstance(reference, LogicDepthReceipt):
                        gaps.append("native_depth_receipt_claim_scope_missing")
                else:
                    gaps.append("native_depth_receipt_coverage_universe_missing")
                receipt_coverage = payload.get("coverage")
                if isinstance(receipt_coverage, Mapping) and receipt_coverage.get("semantic_coverage_passed") is not True:
                    gaps.append("native_depth_receipt_semantic_coverage_incomplete")
                elif not isinstance(receipt_coverage, Mapping):
                    gaps.append("native_depth_receipt_coverage_missing")
                tournament = payload.get("tournament")
                if isinstance(tournament, Mapping):
                    unresolved_competitors = tournament.get("unresolved_competitor_ids", ())
                    if isinstance(unresolved_competitors, (list, tuple)):
                        gaps.extend(
                            f"native_depth_receipt_unresolved_competitor:{item}"
                            for item in unresolved_competitors
                            if str(item)
                        )
                    if str(tournament.get("status", "")) in {"bounded", "unresolved", "blocked"}:
                        gaps.append(f"native_depth_receipt_competition:{tournament.get('status')}")
                else:
                    gaps.append("native_depth_receipt_tournament_missing")
                critical_perturbation = payload.get("critical_perturbation_coverage")
                if isinstance(critical_perturbation, Mapping):
                    for key in ("uncovered_ids", "ineffective_ids"):
                        values = critical_perturbation.get(key, ())
                        if isinstance(values, (list, tuple)):
                            gaps.extend(f"native_depth_receipt_critical_{key}:{item}" for item in values if str(item))
                else:
                    gaps.append("native_depth_receipt_critical_perturbation_coverage_missing")
                perturbation_rows = payload.get("claim_perturbation_coverage", ())
                if isinstance(perturbation_rows, (list, tuple)):
                    by_claim = {str(row.get("claim_id", "")): row for row in perturbation_rows if isinstance(row, Mapping)}
                    for claim_id in selected_claims:
                        row = by_claim.get(claim_id)
                        if row is None:
                            gaps.append(f"native_depth_receipt_claim_perturbation_missing:{claim_id}")
                        elif str(row.get("status", "")) != "pass":
                            gaps.append(f"native_depth_receipt_perturbation_blocked:{claim_id}")
                else:
                    gaps.append("native_depth_receipt_claim_perturbation_coverage_missing")

                expected_inventory_fp = str(model.metadata.get("artifact_inventory_fingerprint", "") or "")
                if expected_inventory_fp and payload.get("artifact_inventory_fingerprint") != expected_inventory_fp:
                    gaps.append("native_depth_receipt_artifact_inventory_fingerprint_mismatch")
                expected_interface_refs = {
                    str(item.parent_receipt_id)
                    for item in getattr(model, "block_interfaces", ())
                    if str(getattr(item, "consumer_status", "")) == "consumed"
                    and str(getattr(item, "parent_receipt_id", ""))
                }
                supplied_interface_refs = {
                    str(item)
                    for item in payload.get("interface_receipt_refs", ())
                    if str(item)
                } if isinstance(payload.get("interface_receipt_refs", ()), (list, tuple)) else set()
                gaps.extend(
                    f"native_depth_receipt_interface_missing:{item}"
                    for item in sorted(expected_interface_refs - supplied_interface_refs)
                )
                gaps.extend(
                    f"native_depth_receipt_interface_foreign:{item}"
                    for item in sorted(supplied_interface_refs - expected_interface_refs)
                )

    for claim_id in selected_claims:
        result = getattr(evaluation, "node_results", {}).get(claim_id)
        if result is None:
            gaps.append(f"native_evaluation_missing:{claim_id}")
        elif getattr(result, "state", "") != STATE_IN:
            use_row = next((row for row in request.claim_use_dispositions if str(row.get("claim_id", "")) == claim_id), None)
            if use_row is None or str(use_row.get("use", "assert")) == "assert":
                gaps.append(f"native_claim_state_not_in:{claim_id}:{getattr(result, 'state', '')}")

    # Only scope-related native findings enter the plan.  Global inventory
    # findings remain in native_coverage for diagnostics and do not get
    # silently presented as proof of the selected claim.
    claim_rows = {row.claim_id: row for row in getattr(coverage, "claim_role_coverage", ())}
    for claim_id in selected_claims:
        row = claim_rows.get(claim_id)
        if row is None:
            gaps.append(f"native_claim_coverage_missing:{claim_id}")
            continue
        if getattr(row, "status", "") != "pass":
            gaps.append(f"native_claim_role_status:{claim_id}:{getattr(row, 'status', '')}")
    claim_scope = getattr(coverage, "claim_scope", None)
    if claim_scope is not None:
        gaps.extend(f"native_claim_scope_missing:{value}" for value in getattr(claim_scope, "missing_node_ids", ()))
    return list(dict.fromkeys(str(value) for value in gaps if str(value)))


def _mesh_overlay_gaps(
    model: LogicModel,
    claims: tuple[str, ...],
    value: Any,
    *,
    native_depth_receipt: Any = None,
) -> list[str]:
    """Validate a revision-bound ModelMesh overlay before using its claims.

    A mesh overlay is a typed, content-addressed object.  Reading a few
    caller-provided fields such as ``covered_claim_ids`` would make an inline
    dictionary an alternate trust root.  We therefore parse the real overlay
    contract when its schema is present and retain the old diagnostic shape
    only as an explicitly blocked, untyped envelope.
    """

    payload = _load_artifact(value)
    if payload is None:
        return ["native_mesh_overlay_unresolved"]

    if "artifact_schema" in payload:
        try:
            from .mesh_overlay import MeshEvaluationOverlay

            overlay = (
                value
                if isinstance(value, MeshEvaluationOverlay)
                else MeshEvaluationOverlay.from_dict(payload)
            )
        except Exception as exc:
            return [f"native_mesh_overlay_invalid:{type(exc).__name__}"]
        return _typed_mesh_overlay_gaps(
            model,
            claims,
            overlay,
            native_depth_receipt=native_depth_receipt,
        )

    # Keep useful diagnostics for a hand-written envelope, but never let it
    # qualify a plan.  This prevents a compatibility-shaped object from
    # becoming a second successful path while making the repair reason clear.
    gaps: list[str] = []
    gaps.append("native_mesh_overlay_untyped")
    if payload.get("model_id") not in (None, "", model.id):
        gaps.append("native_mesh_overlay_model_mismatch")
    if payload.get("model_fingerprint") not in (None, "", model_fingerprint(model)):
        gaps.append("native_mesh_overlay_model_fingerprint_mismatch")
    status = str(payload.get("status", payload.get("completeness", "")) or "")
    if status in {"blocked", "incomplete", "stale", "truncated"}:
        gaps.append(f"native_mesh_overlay_nonclosure:{status}")
    raw_gaps = payload.get("gaps", payload.get("unresolved_references", ()))
    if isinstance(raw_gaps, (list, tuple)):
        gaps.extend(f"native_mesh_overlay_gap:{value}" for value in raw_gaps)
    required_raw = payload.get("required_claim_ids", claims)
    covered_raw = payload.get("covered_claim_ids", ())
    required_claims = (
        {str(value) for value in required_raw if str(value)}
        if isinstance(required_raw, (list, tuple, set))
        else set(claims)
    )
    overlay_claims = (
        {str(value) for value in covered_raw if str(value)}
        if isinstance(covered_raw, (list, tuple, set))
        else set()
    )
    gaps.extend(f"native_mesh_overlay_claim_missing:{value}" for value in sorted(required_claims - overlay_claims))
    return list(dict.fromkeys(gaps))


def _typed_mesh_overlay_gaps(
    model: LogicModel,
    claims: tuple[str, ...],
    overlay: Any,
    *,
    native_depth_receipt: Any = None,
) -> list[str]:
    """Check the current overlay's full closure and target-model binding."""

    gaps: list[str] = []
    if getattr(overlay, "authority", "") != "production":
        gaps.append("native_mesh_overlay_not_production")
    if getattr(overlay, "profile", "") != "broad":
        gaps.append(f"native_mesh_overlay_profile:{getattr(overlay, 'profile', '') or 'missing'}")
    if getattr(overlay, "completeness", "") != "complete":
        gaps.append(f"native_mesh_overlay_nonclosure:{getattr(overlay, 'completeness', '') or 'missing'}")
    if bool(getattr(overlay, "truncated", False)):
        gaps.append("native_mesh_overlay_truncated")
    if getattr(overlay, "broad_claim_licensed", False) is not True:
        gaps.append("native_mesh_overlay_not_licensed")

    unresolved = tuple(getattr(overlay, "unresolved_references", ()) or ())
    gaps.extend(
        f"native_mesh_overlay_unresolved_reference:{index}"
        for index, _ in enumerate(unresolved)
    )
    gaps.extend(
        f"native_mesh_overlay_gap:{item}"
        for item in tuple(getattr(overlay, "gaps", ()) or ())
        if str(item)
    )

    model_refs = tuple(getattr(overlay, "selected_models", ()) or ())
    target_refs = {
        str(getattr(item, "model_id", ""))
        for item in model_refs
        if str(getattr(item, "model_id", ""))
    }
    if model.id not in target_refs:
        gaps.append(f"native_mesh_overlay_model_pin_missing:{model.id}")

    depth_bindings = tuple(getattr(overlay, "depth_bindings", ()) or ())
    if not depth_bindings:
        gaps.append("native_mesh_overlay_depth_bindings_missing")
    target_bindings = [
        item
        for item in depth_bindings
        if str(getattr(getattr(item, "model_ref", None), "model_id", "")) == model.id
    ]
    if not target_bindings:
        gaps.append(f"native_mesh_overlay_target_depth_binding_missing:{model.id}")

    # Every pinned model, including a grandchild reached through a child,
    # owns an exact depth binding.  A parent cannot inherit a child's green
    # label when the child has a stale revision, incomplete scope, or an
    # unresolved gap.
    for binding in depth_bindings:
        model_ref = getattr(binding, "model_ref", None)
        model_label = str(getattr(model_ref, "model_id", "") or "unknown")
        if str(getattr(binding, "status", "")) != "pass":
            gaps.append(f"native_mesh_overlay_depth_status:{model_label}:{getattr(binding, 'status', '')}")
        if getattr(binding, "broad_claim_licensed", False) is not True:
            gaps.append(f"native_mesh_overlay_depth_not_licensed:{model_label}")
        if str(getattr(binding, "scope_relation", "")) not in {"exact", "materialization_superset"}:
            gaps.append(f"native_mesh_overlay_depth_scope:{model_label}:{getattr(binding, 'scope_relation', '')}")
        gaps.extend(
            f"native_mesh_overlay_depth_gap:{model_label}:{item}"
            for item in tuple(getattr(binding, "gaps", ()) or ())
            if str(item)
        )

    # The target model's own model fingerprint must agree with the current
    # candidate.  Child fingerprints are still checked for presence and
    # binding status; their current model bytes are owned by ModelMesh.
    for binding in target_bindings:
        declared_fp = str(getattr(binding, "model_fingerprint", "") or "")
        if declared_fp != model_fingerprint(model):
            gaps.append("native_mesh_overlay_target_model_fingerprint_mismatch")

    requested_refs = tuple(getattr(overlay, "requested_claim_scope", ()) or ())
    requested_ids = {
        str(getattr(item, "node_id", ""))
        for item in requested_refs
        if str(getattr(item, "node_id", ""))
        and str(getattr(item, "model_id", "")) == model.id
    }
    gaps.extend(
        f"native_mesh_overlay_claim_missing:{claim_id}"
        for claim_id in claims
        if claim_id not in requested_ids
    )
    result_rows = tuple(getattr(overlay, "node_results", ()) or ())
    by_node = {
        str(getattr(getattr(item, "node_ref", None), "node_id", "")): item
        for item in result_rows
        if str(getattr(getattr(item, "node_ref", None), "model_id", "")) == model.id
    }
    for claim_id in claims:
        row = by_node.get(claim_id)
        if row is None:
            gaps.append(f"native_mesh_overlay_node_result_missing:{claim_id}")
        elif str(getattr(row, "state", "")) != STATE_IN:
            gaps.append(f"native_mesh_overlay_node_state:{claim_id}:{getattr(row, 'state', '')}")

    # Mesh depth bindings carry the receipt digest after removing generated_at,
    # exactly as the native mesh evaluator computes it.  Compare it whenever a
    # current native receipt is supplied; a stale receipt cannot be paired with
    # an otherwise current overlay.
    if native_depth_receipt not in (None, "") and target_bindings:
        depth_payload = _load_artifact(native_depth_receipt)
        if depth_payload is None:
            gaps.append("native_mesh_overlay_depth_receipt_unresolved")
        else:
            try:
                from .model_store import canonical_plain_digest

                comparable = dict(depth_payload)
                comparable.pop("generated_at", None)
                expected_digest = canonical_plain_digest(comparable)
                if not any(
                    str(getattr(item, "depth_receipt_digest", "")) == expected_digest
                    for item in target_bindings
                ):
                    gaps.append("native_mesh_overlay_depth_receipt_digest_mismatch")
            except Exception as exc:
                gaps.append(f"native_mesh_overlay_depth_receipt_digest_error:{type(exc).__name__}")

    # A real overlay's dependency binding is validated by
    # MeshEvaluationOverlay.from_dict.  Verify the references are actually
    # present in that binding so a hand-mutated object cannot hide a missing
    # model pin or a missing scope key.
    dependency = getattr(overlay, "dependency_binding", None)
    dependency_model_ids = {
        str(getattr(item, "model_id", ""))
        for item in tuple(getattr(dependency, "model_refs", ()) or ())
    }
    if model.id not in dependency_model_ids:
        gaps.append(f"native_mesh_overlay_dependency_model_missing:{model.id}")
    dependency_scope_ids = {
        str(getattr(item, "node_id", ""))
        for item in tuple(getattr(dependency, "requested_claim_scope", ()) or ())
        if str(getattr(item, "model_id", "")) == model.id
    }
    gaps.extend(
        f"native_mesh_overlay_dependency_claim_missing:{claim_id}"
        for claim_id in claims
        if claim_id not in dependency_scope_ids
    )
    return list(dict.fromkeys(str(item) for item in gaps if str(item)))


def _branch_data(branch: Any) -> dict[str, Any]:
    if isinstance(branch, Mapping):
        return dict(branch)
    if hasattr(branch, "to_dict"):
        value = branch.to_dict()
        return dict(value) if isinstance(value, Mapping) else {}
    return {
        key: getattr(branch, key)
        for key in (
            "branch_id", "source_id", "project_id", "topic_focus", "branch_role", "note", "locator",
            "importance", "salience", "anchor_node_id", "anchor_block_id", "source_date", "coverage_period",
            "node_ids", "source_model_fingerprint", "native_evidence_ref", "current_native_evidence_ref",
        )
        if hasattr(branch, key)
    }


def _branch_candidate_id(source_id: str, branch_id: str) -> str:
    return f"source_branch:{source_id}:{branch_id}"


def _branch_semantic_payload(item: SynthesisItem) -> dict[str, Any]:
    data = item.to_dict()
    for key in ("temporal_role", "temporal_caveat"):
        data.pop(key, None)
    return data


def _branch_binding_gaps(binding: Mapping[str, Any], candidate: SynthesisItem, *, source_library: Any | None = None) -> list[str]:
    gaps: list[str] = []
    if str(binding.get("source_id", "")) != candidate.source_id:
        gaps.append("source_id_mismatch")
    if str(binding.get("branch_id", "")) != candidate.branch_id:
        gaps.append("branch_id_mismatch")
    request_anchor = str(binding.get("anchor_node_id", "") or "") or str(binding.get("anchor_block_id", "") or "")
    candidate_anchor = candidate.anchor_node_id or candidate.anchor_block_id
    if bool(candidate.anchor_node_id) == bool(candidate.anchor_block_id):
        gaps.append("candidate_exactly_one_anchor_required")
    if not request_anchor or request_anchor != candidate_anchor:
        gaps.append("anchor_mismatch")
    binding_refs = str(binding.get("current_native_evidence_ref", "") or "")
    candidate_ref = candidate.native_evidence_ref
    if not candidate_ref:
        gaps.append("native_evidence_missing")
    elif binding_refs != candidate_ref:
        gaps.append("native_evidence_mismatch")
    else:
        gaps.extend(_native_evidence_reference_gaps(candidate_ref, candidate))
    branch_project = candidate.source_project_id
    if binding.get("project_id") not in (None, "") and str(binding.get("project_id")) != branch_project:
        gaps.append("project_id_mismatch")
    if binding.get("source_node_ids") not in (None, ""):
        expected = {str(value) for value in binding.get("source_node_ids", ())} if isinstance(binding.get("source_node_ids"), (list, tuple, set)) else set()
        if expected and not expected.issubset(set(candidate.source_node_ids)):
            gaps.append("source_node_scope_mismatch")
    binding_model_fp = str(binding.get("source_model_fingerprint", "") or "")
    if binding_model_fp and candidate.source_model_fingerprint and binding_model_fp != candidate.source_model_fingerprint:
        gaps.append("source_model_fingerprint_mismatch")
    if candidate.anchor_node_id and candidate.source_node_ids and candidate.anchor_node_id not in set(candidate.source_node_ids):
        gaps.append("source_anchor_node_scope_mismatch")
    if candidate.anchor_block_id and candidate.source_node_ids and candidate.anchor_block_id not in set(candidate.source_node_ids):
        gaps.append("source_anchor_block_scope_mismatch")
    if source_library is None and not candidate.source_node_ids:
        gaps.append("source_anchor_unverified")
    if source_library is not None:
        gaps.extend(_source_library_binding_gaps(binding, candidate, source_library))
    return list(dict.fromkeys(gaps))


def _native_evidence_reference_gaps(reference: str, candidate: SynthesisItem) -> list[str]:
    """Require a resolvable, identity-bound branch receipt before admission."""

    path = Path(reference)
    if not path.exists() or not path.is_file():
        return ["native_evidence_unresolved"]
    payload = _load_artifact(path)
    if payload is None:
        return ["native_evidence_unresolved"]

    # Prefer the repository's immutable native-receipt resolver when the
    # source branch carries a signed/current receipt.  Merely matching a few
    # JSON labels is not equivalent to reopening the receipt bytes, producer,
    # and binding identity.
    if "schema_version" in payload and "receipt_id" in payload:
        try:
            from ..native_receipts import NativeReceiptReference, resolve_native_receipt_reference

            receipt = NativeReceiptReference.from_dict(payload)
            gaps = [f"{code}:{detail}" for code, detail in resolve_native_receipt_reference(receipt)]
        except Exception:
            return ["native_evidence_invalid"]
        if receipt.status != "passed":
            gaps.append(f"native_evidence_not_current:{receipt.status}")
        if receipt.native_model_id not in (candidate.source_id, candidate.source_id.rsplit(":", 1)[-1]):
            gaps.append("native_evidence_native_model_mismatch")
        expected_anchor = candidate.anchor_node_id or candidate.anchor_block_id
        if expected_anchor and receipt.expected_target_anchor_id != expected_anchor:
            gaps.append("native_evidence_anchor_mismatch")
        if candidate.source_model_fingerprint and receipt.model_fingerprint != candidate.source_model_fingerprint:
            gaps.append("native_evidence_model_fingerprint_mismatch")
        elif not receipt.model_fingerprint:
            gaps.append("native_evidence_model_fingerprint_missing")
        return list(dict.fromkeys(gaps))

    # Unsigned local native outputs are allowed as a bounded source-library
    # fact only when the file still carries enough immutable identity for the
    # resolver/producer to re-check it.  A status/source/branch trio is a
    # spoofable label and is therefore deliberately rejected.
    identity_missing = [
        key
        for key in ("receipt_id", "source_id", "branch_id", "model_fingerprint")
        if not str(payload.get(key, "") or "").strip()
    ]
    anchor_value = str(
        payload.get("anchor_node_id", "")
        or payload.get("anchor_block_id", "")
        or payload.get("anchor_id", "")
        or ""
    ).strip()
    if not anchor_value:
        identity_missing.append("anchor")
    if not any(str(payload.get(key, "") or "").strip() for key in ("receipt_fingerprint", "content_hash", "fingerprint", "result_fingerprint")):
        identity_missing.append("receipt_fingerprint")
    if identity_missing:
        return [f"native_evidence_identity_incomplete:{','.join(identity_missing)}"]
    gaps: list[str] = []
    if payload.get("source_id") not in (None, "", candidate.source_id):
        gaps.append("native_evidence_source_mismatch")
    if payload.get("branch_id") not in (None, "", candidate.branch_id):
        gaps.append("native_evidence_branch_mismatch")
    status = str(payload.get("status", payload.get("receipt_status", "current")) or "")
    if status not in {"pass", "passed", "current", "ready"}:
        gaps.append(f"native_evidence_not_current:{status or 'missing_status'}")
    expected_anchor = candidate.anchor_node_id or candidate.anchor_block_id
    if anchor_value != expected_anchor:
        gaps.append("native_evidence_anchor_mismatch")
    if candidate.source_model_fingerprint and payload.get("model_fingerprint") != candidate.source_model_fingerprint:
        gaps.append("native_evidence_model_fingerprint_mismatch")
    return gaps


def _source_library_binding_gaps(binding: Mapping[str, Any], candidate: SynthesisItem, library: Any) -> list[str]:
    gaps: list[str] = []
    try:
        branches = library.list_deepening_branches(candidate.source_id, project_id=candidate.source_project_id)
    except Exception as exc:
        return [f"source_library_unresolved:{type(exc).__name__}"]
    current = [item for item in branches if str(getattr(item, "branch_id", "")) == candidate.branch_id]
    if len(current) != 1:
        gaps.append("source_library_branch_identity_unresolved")
    else:
        # The supplied branch object is a transport candidate, not source
        # authority.  Compare its stable fields with the sole native record so
        # a caller cannot reuse a valid ID while swapping topic, anchor, node
        # scope, or project metadata.
        native = current[0]
        if str(getattr(native, "source_id", "")) != candidate.source_id:
            gaps.append("source_library_source_id_mismatch")
        if str(getattr(native, "project_id", "")) != candidate.source_project_id:
            gaps.append("source_library_project_id_mismatch")
        if str(getattr(native, "anchor_node_id", "")) != candidate.anchor_node_id:
            gaps.append("source_library_anchor_node_mismatch")
        if str(getattr(native, "anchor_block_id", "")) != candidate.anchor_block_id:
            gaps.append("source_library_anchor_block_mismatch")
        native_nodes = {
            str(value)
            for value in getattr(native, "node_ids", ())
            if str(value)
        }
        candidate_nodes = set(candidate.source_node_ids)
        if native_nodes != candidate_nodes:
            gaps.append("source_library_node_scope_mismatch")
        if str(getattr(native, "branch_role", "")) != candidate.branch_role:
            gaps.append("source_library_branch_role_mismatch")
    try:
        report = library.audit_deepening_branches(candidate.source_id)
        gaps.extend(f"source_library_audit:{item.code}" for item in report.findings if item.branch_id == candidate.branch_id and item.severity in {"error", "critical"})
    except Exception as exc:
        gaps.append(f"source_library_audit_unresolved:{type(exc).__name__}")
    project_id = candidate.source_project_id
    if project_id:
        try:
            links = library.list_links(project_id)
        except Exception as exc:
            links = ()
            gaps.append(f"source_library_links_unresolved:{type(exc).__name__}")
        claim_ids = {str(value) for value in binding.get("claim_ids", ())} if isinstance(binding.get("claim_ids"), (list, tuple, set)) else set()
        matching = [
            link
            for link in links
            if str(getattr(link, "source_id", "")) == candidate.source_id
            and str(getattr(link, "source_branch_id", "")) == candidate.branch_id
            and str(getattr(link, "project_node_id", "")) in claim_ids
        ]
        if not matching:
            gaps.append("source_library_target_link_missing")
        else:
            expected_anchor = candidate.anchor_node_id or candidate.anchor_block_id
            for link in matching:
                link_anchor = str(getattr(link, "anchor_node_id", "") or "") or str(getattr(link, "anchor_block_id", "") or "")
                if expected_anchor and link_anchor and link_anchor != expected_anchor:
                    gaps.append("source_library_link_anchor_mismatch")
                if not str(getattr(link, "relation", "")).strip():
                    gaps.append("source_library_link_relation_missing")
    try:
        model_path = library.source_model_path(candidate.source_id)
        source_model = load_model(model_path)
        if candidate.anchor_node_id and candidate.anchor_node_id not in source_model.nodes:
            gaps.append("source_anchor_node_missing")
        if candidate.anchor_block_id and candidate.anchor_block_id not in source_model.blocks and candidate.anchor_block_id not in source_model.hierarchy:
            gaps.append("source_anchor_block_missing")
        declared_fp = candidate.source_model_fingerprint
        if declared_fp and declared_fp != model_fingerprint(source_model):
            gaps.append("source_model_fingerprint_mismatch")
        binding_fp = str(binding.get("source_model_fingerprint", "") or "")
        if binding_fp and binding_fp != model_fingerprint(source_model):
            gaps.append("source_binding_model_fingerprint_mismatch")
    except Exception as exc:
        gaps.append(f"source_model_unresolved:{type(exc).__name__}")
    return gaps


def _blocked_plan(model: LogicModel, *, target_goal: str, profile: str, status: str, gaps: Iterable[str], request_fingerprint: str) -> SynthesisPlan:
    return SynthesisPlan(model_id=model.id, target_goal=target_goal, profile=profile, units=(), body_unit_order=(),
        candidate_dispositions=(), open_gaps=tuple(dict.fromkeys(str(gap) for gap in gaps)), status=status,
        claim_boundary="No valid selection request was admitted; no argument handoff is licensed.",
        model_fingerprint=model_fingerprint(model), selection_request_fingerprint=request_fingerprint)


def _importance_value(model: LogicModel, node_id: str) -> float:
    return round(float(next((item.importance for item in summarize_importance(model, limit=None).records if item.subject_id == node_id), 0.0)), 4)


def _expand_argument_closure(model: LogicModel, seeds: set[str]) -> set[str]:
    """Follow native argument dependencies while retaining alternative paths."""
    closure = {node_id for node_id in seeds if node_id in model.nodes}
    frontier = list(closure)
    allowed = {"supports", "depends_on", "refines", "derives", "aggregates", "explains", "attacks", "undercuts", "contradicts", "qualifies", "contextualizes"}
    while frontier:
        target = frontier.pop()
        for edge in model.incoming(target):
            if edge.type not in allowed or edge.source not in model.nodes or edge.source in closure:
                continue
            closure.add(edge.source)
            frontier.append(edge.source)
    return closure


def _item_from_record(record: ImportanceRecord, model: LogicModel, matrix: ClaimSourceParagraphMatrix) -> SynthesisItem:
    metadata: Mapping[str, Any] = model.nodes[record.subject_id].metadata if record.subject_id in model.nodes else {}
    row = matrix.row_for_claim(record.subject_id)
    source_ids = row.source_ids if row else ()
    return SynthesisItem(node_id=record.subject_id, node_type=record.subject_type, salience=record.salience,
        importance=record.importance, text=record.text, reason=record.reason,
        treatment=_treatment_for(record.subject_type, record.salience, record.importance),
        source_id=str(metadata.get("source_id", "") or (source_ids[0] if source_ids else "")), source_ids=source_ids,
        source_roles=row.source_roles if row else {}, paragraph_locator=row.paragraph_locator if row else "",
        citation_marker=row.citation_marker if row else "", claim_strength=row.claim_strength if row else "",
        limitation=row.limitation if row else "", source_date=str(metadata.get("source_date", "")),
        coverage_period=str(metadata.get("coverage_period", "")))


def _item_from_branch(branch: Any) -> SynthesisItem:
    data = _branch_data(branch)
    branch_id, source_id = str(data.get("branch_id", "")), str(data.get("source_id", ""))
    candidate_id = _branch_candidate_id(source_id, branch_id) if source_id and branch_id else branch_id
    topic, role, source_date = str(data.get("topic_focus", "")), str(data.get("branch_role", "")), str(data.get("source_date", ""))
    coverage, note, locator = str(data.get("coverage_period", "")), str(data.get("note", "")), str(data.get("locator", ""))
    try: importance = 0.55 if data.get("importance") in (None, "") else float(data.get("importance"))
    except (TypeError, ValueError): importance = 0.55
    salience = str(data.get("salience", "")) or _salience_for_branch_role(role, importance)
    anchor_node, anchor_block = str(data.get("anchor_node_id", "")), str(data.get("anchor_block_id", ""))
    source_nodes = data.get("node_ids", ())
    source_node_ids = tuple(str(value) for value in source_nodes if str(value)) if isinstance(source_nodes, (list, tuple, set)) else ()
    native_ref = str(data.get("native_evidence_ref", data.get("current_native_evidence_ref", "")) or "")
    return SynthesisItem(node_id=candidate_id or f"source_branch:{source_id}:{topic}", node_type="SourceBranch", salience=salience,
        importance=min(1.0, max(0.0, importance)), text=" | ".join(part for part in (topic, role, note, locator) if part) or branch_id or source_id,
        reason=f"Reusable source-library deepening branch{f' anchored to {anchor_node or anchor_block}' if anchor_node or anchor_block else ''}.",
        treatment=_treatment_for("SourceBranch", salience, importance), source_id=source_id, branch_id=branch_id,
        anchor_node_id=anchor_node, anchor_block_id=anchor_block, branch_role=role, source_date=source_date, coverage_period=coverage,
        source_node_ids=source_node_ids, source_project_id=str(data.get("project_id", "") or ""),
        source_model_fingerprint=str(data.get("source_model_fingerprint", "") or ""), native_evidence_ref=native_ref)


def _object_public_data(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        result = value.to_dict()
        return dict(result) if isinstance(result, Mapping) else {}
    return {key: getattr(value, key) for key in ("branch_id", "source_id", "project_id", "topic_focus", "branch_role", "note", "locator", "importance", "salience", "anchor_node_id", "anchor_block_id", "source_date", "coverage_period", "node_ids", "source_model_fingerprint", "native_evidence_ref", "current_native_evidence_ref") if hasattr(value, key)}


def _with_temporal_roles(items: list[SynthesisItem]) -> list[SynthesisItem]:
    years = [year for year in (_leading_year(item.source_date) for item in items if item.source_date) if year is not None]
    return [_with_temporal_role(item, min_year=min(years, default=None), max_year=max(years, default=None)) for item in items]


def _with_temporal_role(item: SynthesisItem, *, min_year: int | None, max_year: int | None) -> SynthesisItem:
    source_year, coverage_end = _leading_year(item.source_date), _coverage_end_year(item.coverage_period)
    if item.source_date and source_year is not None:
        role = "historical" if min_year is not None and source_year == min_year and min_year != max_year else "recent" if max_year is not None and source_year == max_year and min_year != max_year else "source_dated"
    elif item.coverage_period: role = "covered_period"
    elif item.source_id: role = "unknown_time"
    else: role = ""
    caveat = f"Coverage period: {item.coverage_period}." if item.coverage_period and role != "unknown_time" else ""
    if source_year is not None and coverage_end is not None and source_year > coverage_end:
        role, caveat = "covered_period", f"Published/source date {item.source_date} is later than covered period {item.coverage_period}; do not treat publication date as coverage."
    elif role == "unknown_time": caveat = "Source time is unmarked; avoid treating it as current-state evidence without confirmation."
    return replace(item, temporal_role=role, temporal_caveat=caveat)


def _leading_year(value: str) -> int | None:
    match = re.search(r"(?:19|20)\d{2}", value or "")
    return int(match.group(0)) if match else None


def _coverage_end_year(value: str) -> int | None:
    matches = re.findall(r"(?:19|20)\d{2}", value or "")
    return int(matches[-1]) if matches else None


def _salience_for_branch_role(branch_role: str, importance: float) -> str:
    role = branch_role.lower()
    if any(token in role for token in ("limit", "risk", "scope", "rebut", "attack")): return "risk"
    if any(token in role for token in ("mechanism", "warrant", "bridge", "explain")): return "bridge"
    return "core" if importance >= 0.8 else "supporting"


def _treatment_for(node_type: str, salience: str, importance: float) -> str:
    key = salience.lower()
    if key == "optional" or importance < 0.35: return "omit"
    if key == "background" or importance < 0.5: return "brief"
    if importance >= 0.85 or key in {"core", "risk"}: return "deep"
    if key == "bridge" and importance >= 0.7: return "deep"
    if node_type in {"Limitation", "Qualifier", "Rebuttal", "Undercutter"} and importance >= 0.65: return "deep"
    return "normal" if importance >= 0.6 else "brief"


def _omitted_item(item: SynthesisItem) -> SynthesisItem:
    if item.treatment == "omit": return item
    return replace(item, treatment="appendix" if item.importance >= 0.6 or item.salience.lower() in {"core", "risk", "bridge"} else "omit")


__all__ = ["CandidateDisposition", "SynthesisItem", "SynthesisPlan", "SynthesisUnit", "synthesize_artifact_plan"]
