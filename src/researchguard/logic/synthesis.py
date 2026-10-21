"""Argument-unit synthesis owned by LogicGuard.

Editorial callers choose units and order. This module checks that request and
hands each selected claim to the native argument-coverage owner; it never
selects a top-N story by itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import re
from typing import Any, Iterable, Mapping

from .citation_matrix import ClaimSourceParagraphMatrix, build_claim_source_paragraph_matrix
from .execution_depth import _build_native_depth_analysis, build_argument_coverage_universe, model_fingerprint
from .evaluator import evaluate_model
from .importance import ImportanceRecord, summarize_importance
from .model import LogicModel
from .schema import STATE_IN
from .structure_audit import audit_structure
from .synthesis_contract import SelectionRequest, SYNTHESIS_REQUEST_SCHEMA, validate_selection_request
from .loader import load_model


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
    source_library: Any | None = None,
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
    open_gaps.extend(_native_scope_gaps(model, request, evaluation, coverage))

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




def _native_scope_gaps(
    model: LogicModel,
    request: SelectionRequest,
    evaluation: Any,
    coverage: Any,
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
        # Depth is always computed here, on the current model; no external
        # depth result is accepted.
        depth = _build_native_depth_analysis(
            model,
            budget=max(6, len(model.nodes)),
            requested_claim_scope_ids=selected_claims,
            result=evaluation,
        ).to_dict()
        if depth.get("status") != "pass" or depth.get("broad_claim_licensed") is not True:
            gaps.append("native_depth_not_licensed")
        gaps.extend(f"native_depth_gap:{value}" for value in depth.get("unresolved_gaps", ()))
        covered = set((depth.get("coverage_universe") or {}).get("important_node_ids", ()))
        gaps.extend(f"native_depth_scope_missing:{claim_id}" for claim_id in selected_claims if claim_id not in covered)
        if (depth.get("coverage") or {}).get("semantic_coverage_passed") is not True:
            gaps.append("native_depth_semantic_coverage_incomplete")
        tournament = depth.get("tournament") or {}
        gaps.extend(
            f"native_depth_unresolved_competitor:{item}"
            for item in tournament.get("unresolved_competitor_ids", ())
            if str(item)
        )
        if str(tournament.get("status", "")) in {"bounded", "unresolved", "blocked"}:
            gaps.append(f"native_depth_competition:{tournament.get('status')}")
        critical = depth.get("critical_perturbation_coverage") or {}
        for key in ("uncovered_ids", "ineffective_ids"):
            gaps.extend(f"native_depth_critical_{key}:{item}" for item in critical.get(key, ()) if str(item))
        by_claim = {
            str(row.get("claim_id", "")): row
            for row in depth.get("claim_perturbation_coverage", ())
            if isinstance(row, Mapping)
        }
        for claim_id in selected_claims:
            row = by_claim.get(claim_id)
            if row is None:
                gaps.append(f"native_depth_claim_perturbation_missing:{claim_id}")
            elif str(row.get("status", "")) != "pass":
                gaps.append(f"native_depth_perturbation_blocked:{claim_id}")

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
