"""
Purpose: Generate, score, and summarize SourceGuard next-search plans from leads and gaps.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source plan <model.yaml> --model-contract <model.contract.json>
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .schema import BeliefState, Gap, PlanResult, SearchAction, validate_model_guard_binding
from .scoring import score_action


def _slug(value: str) -> str:
    return "-".join("".join(ch.lower() if ch.isalnum() else "-" for ch in value).split("-"))[:48] or "action"


def _query_for_gap(gap: Gap, lead_question: str = "", domain_hints: Iterable[str] = ()) -> str:
    parts = [lead_question, gap.description, " ".join(str(item) for item in domain_hints if str(item).strip())]
    base = " ".join(dict.fromkeys(part.strip() for part in parts if part and part.strip())) or gap.gap_type
    if gap.structure_unit_id or gap.structural_role_needed:
        structural_bits = " ".join(
            item
            for item in [
                gap.structure_unit_id,
                gap.contribution_type,
                gap.structural_role_needed,
                gap.downstream_consumer,
            ]
            if item
        )
        base = f"{base} {structural_bits}".strip()
    if gap.gap_type == "missing_execution_evidence":
        return f"{base} implementation operation outcome official record independent report direct observation"
    if gap.gap_type == "one_sided_support":
        return f"{base} criticism failure limitation contradiction independent"
    if gap.gap_type == "missing_visual_anchor":
        return f"{base} image photo visual evidence location"
    if gap.gap_type == "missing_audio_anchor":
        return f"{base} transcript audio quote timestamp"
    if gap.gap_type == "missing_pdf_page":
        return f"{base} PDF page figure table"
    if gap.gap_type == "missing_structural_source_support":
        return f"{base} source evidence supports structural role downstream use"
    if gap.gap_type == "missing_bridge_evidence":
        return f"{base} bridge evidence source supports scope method validation handoff"
    if gap.gap_type == "missing_conclusion_recovery_source":
        return f"{base} conclusion support limitation source recovery evidence"
    if gap.gap_type == "missing_book_page":
        return f"{base} book index page citation"
    if gap.gap_type == "unclear_entity":
        return f"{base} aliases entity organization location"
    return base


def _action(
    gap: Gap,
    action_type: str,
    expected_source_role: str,
    expected_modality: str = "text",
    query: str = "",
    cost: float = 0.3,
    permission_risk: float = 0.0,
    status: str = "proposed",
    notes: str = "",
    parameters: dict | None = None,
) -> SearchAction:
    query_text = query or _query_for_gap(gap)
    return SearchAction(
        action_id=f"generated-{gap.gap_id}-{_slug(action_type)}",
        action_type=action_type,
        query=query_text,
        target_lead_id=gap.lead_id,
        target_gap_id=gap.gap_id,
        expected_source_role=expected_source_role,
        expected_modality=expected_modality,
        source_policy="public_only",
        cost=cost,
        permission_risk=permission_risk,
        status=status,
        parameters=parameters or {},
        notes=notes,
    )


def _policy_allows_internal(belief_state: BeliefState) -> bool:
    policy = str(belief_state.metadata.get("source_policy", "public_only"))
    return policy in {"internal_allowed", "local_allowed", "mixed", "all_allowed"}


def _domain_hints(belief_state: BeliefState) -> list[str]:
    raw = belief_state.metadata.get("domain_hints", [])
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, (list, tuple)):
        return [str(item) for item in raw if str(item).strip()]
    return []


def _actions_for_gap(gap: Gap, belief_state: BeliefState) -> list[SearchAction]:
    lead = belief_state.lead_by_id().get(gap.lead_id)
    query = _query_for_gap(gap, lead.question if lead else "", _domain_hints(belief_state))
    if gap.semantic_state == "closed":
        return []
    if gap.gap_type == "missing_primary_source":
        return [
            _action(gap, "primary_source_search", "primary_source", query=query),
            _action(gap, "source_domain_search", "official_claim", query=f"{query} official source"),
        ]
    if gap.gap_type == "missing_independent_source":
        return [
            _action(gap, "text_search", "independent_report", query=f"{query} independent report"),
            _action(gap, "source_domain_search", "independent_report", query=f"{query} local media regulator"),
        ]
    if gap.gap_type == "missing_date":
        return [
            _action(gap, "exact_phrase_search", "primary_source", query=f"\"{query}\" date"),
            _action(gap, "report_page_search", "primary_source", "pdf_page", query=f"{query} report page date"),
        ]
    if gap.gap_type == "missing_location":
        return [
            _action(gap, "map_location_search", "primary_source", "map", query=f"{query} map address"),
            _action(gap, "image_search", "visual_evidence", "image", query=f"{query} site photo location"),
            _action(gap, "source_domain_search", "independent_report", query=f"{query} local source location"),
        ]
    if gap.gap_type == "missing_execution_evidence":
        return [
            _action(gap, "source_domain_search", "primary_source", query=f"{query} official implementation record"),
            _action(gap, "image_search", "visual_evidence", "image", query=f"{query} direct visual observation"),
            _action(gap, "video_search", "visual_evidence", "video", query=f"{query} recorded operation outcome"),
            _action(gap, "report_page_search", "independent_report", "pdf_page", query=f"{query} independent implementation outcome report"),
        ]
    if gap.gap_type == "weak_signal_only":
        return [
            _action(gap, "primary_source_search", "primary_source", query=query),
            _action(gap, "counterevidence_search", "counter_evidence", query=query),
            _action(gap, "text_search", "independent_report", query=f"{query} independent"),
        ]
    if gap.gap_type == "one_sided_support":
        return [
            _action(gap, "counterevidence_search", "counter_evidence", query=query),
            _action(gap, "text_search", "limiting_evidence", query=f"{query} limitation"),
        ]
    if gap.gap_type == "contradiction":
        return [
            _action(gap, "exact_phrase_search", "primary_source", query=f"\"{query}\"", parameters={"freshness_focused": True}),
            _action(gap, "report_page_search", "independent_report", "pdf_page", query=f"{query} dated report", parameters={"freshness_focused": True}),
        ]
    if gap.gap_type == "permission_gap":
        if _policy_allows_internal(belief_state):
            return [_action(gap, "internal_source_search", "primary_source", "text", query=query, permission_risk=0.6)]
        return [
            _action(
                gap,
                "internal_source_search",
                "primary_source",
                "text",
                query=query,
                permission_risk=1.0,
                status="blocked",
                notes="Permission-gated material is an access gap unless local/internal access is explicitly allowed.",
            )
        ]
    if gap.gap_type == "missing_visual_anchor":
        return [
            _action(gap, "image_search", "visual_evidence", "image", query=query),
            _action(gap, "reverse_image_search", "visual_evidence", "image", query=query),
        ]
    if gap.gap_type == "missing_audio_anchor":
        return [_action(gap, "audio_transcript_search", "audio_evidence", "audio", query=query)]
    if gap.gap_type == "missing_book_page":
        return [_action(gap, "book_index_search", "primary_source", "book_page", query=query)]
    if gap.gap_type == "missing_pdf_page":
        return [_action(gap, "pdf_page_search", "primary_source", "pdf_page", query=query)]
    if gap.gap_type == "unclear_entity":
        return [_action(gap, "entity_expand", "context_only", query=query)]
    if gap.gap_type in {"missing_counterevidence", "missing_baseline"}:
        return [_action(gap, "counterevidence_search", "counter_evidence", query=query)]
    if gap.gap_type == "missing_structural_source_support":
        role = gap.suggested_source_roles[0] if gap.suggested_source_roles else "bridge_evidence"
        return [
            _action(gap, "text_search", role, query=query),
            _action(gap, "source_domain_search", "method_source", query=f"{query} method source"),
        ]
    if gap.gap_type == "missing_bridge_evidence":
        return [
            _action(gap, "text_search", "bridge_evidence", query=query),
            _action(gap, "report_page_search", "validation_evidence", "pdf_page", query=f"{query} report evidence"),
        ]
    if gap.gap_type == "missing_conclusion_recovery_source":
        return [
            _action(gap, "text_search", "limiting_evidence", query=query),
            _action(gap, "source_domain_search", "validation_evidence", query=f"{query} validation conclusion evidence"),
        ]
    return [_action(gap, "text_search", "unknown", query=query)]


def _dedupe(actions: Iterable[SearchAction], existing: Iterable[SearchAction]) -> list[SearchAction]:
    seen: set[tuple[str, str, str, str]] = set()
    output: list[SearchAction] = []
    for action in list(existing) + list(actions):
        key = (
            action.action_type,
            " ".join(action.query.lower().split()),
            action.target_gap_id,
            action.expected_source_role,
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(action)
    return output


def generate_actions_from_gaps(belief_state: BeliefState) -> list[SearchAction]:
    validate_model_guard_binding(belief_state)
    generated: list[SearchAction] = []
    for gap in belief_state.gaps:
        generated.extend(_actions_for_gap(gap, belief_state))
    deduped = _dedupe(generated, belief_state.actions)
    existing_ids = {action.action_id for action in belief_state.actions}
    return [action for action in deduped if action.action_id not in existing_ids]


def generate_actions_from_leads(belief_state: BeliefState) -> list[SearchAction]:
    gap_ids = {gap.gap_id for gap in belief_state.gaps}
    generated: list[SearchAction] = []
    for lead in belief_state.leads:
        if not lead.gaps and lead.status in {"open", "supported_incomplete", "candidate"}:
            gap = Gap(
                gap_id=f"generated-gap-{lead.lead_id}",
                lead_id=lead.lead_id,
                gap_type="unclear_scope",
                description=lead.question,
                importance=lead.importance,
                blocking=False,
            )
            if gap.gap_id not in gap_ids:
                generated.append(_action(gap, "entity_expand", "context_only", query=lead.question))
    return _dedupe(generated, belief_state.actions)


def plan_next_actions(belief_state: BeliefState, limit: int = 5) -> PlanResult:
    validate_model_guard_binding(belief_state)
    generated = generate_actions_from_gaps(belief_state) + generate_actions_from_leads(belief_state)
    state_for_scoring = replace(belief_state, actions=_dedupe(generated, belief_state.actions))
    gap_by_id = belief_state.gap_by_id()
    scored = [
        score_action(action, state_for_scoring)
        for action in state_for_scoring.actions
        if action.status not in {"blocked", "rejected", "completed", "executed"}
        and (
            not action.target_gap_id
            or action.target_gap_id not in gap_by_id
            or (
                gap_by_id[action.target_gap_id].semantic_state != "closed"
            )
        )
    ]
    scored = sorted(scored, key=lambda item: item.total_score, reverse=True)
    by_id = state_for_scoring.action_by_id()
    selected = [by_id[item.action_id] for item in scored[:limit] if item.action_id in by_id]
    open_gaps = [
        gap
        for gap in belief_state.gaps
        if gap.semantic_state not in {"closed", "blocked"}
        and gap.gap_type != "permission_gap"
    ]
    blocked_gaps = [
        gap
        for gap in belief_state.gaps
        if gap.semantic_state == "blocked" or gap.gap_type == "permission_gap"
    ]
    warnings = []
    if any(action.status == "blocked" for action in state_for_scoring.actions):
        warnings.append("Blocked actions remain access gaps and are not evidence.")
    if not selected:
        warnings.append("No selectable actions were available.")
    next_step_summary = "Recommended actions prioritize blocking or high-importance gaps, independent/counter sources, concrete anchors, and lower permission risk."
    return PlanResult(
        ok=True,
        selected_actions=selected,
        scored_actions=scored,
        open_gaps=open_gaps,
        blocked_gaps=blocked_gaps,
        warnings=warnings,
        next_step_summary=next_step_summary,
    )


def frontier_summary(belief_state: BeliefState) -> dict:
    validate_model_guard_binding(belief_state)
    open_gaps = [
        gap
        for gap in belief_state.gaps
        if gap.semantic_state not in {"closed", "blocked"}
    ]
    blocking = [gap for gap in open_gaps if gap.blocking]
    permission = [
        gap
        for gap in belief_state.gaps
        if gap.gap_type == "permission_gap" or gap.semantic_state == "blocked"
    ]
    multimodal = [
        gap
        for gap in open_gaps
        if gap.gap_type in {"missing_visual_anchor", "missing_audio_anchor", "missing_pdf_page", "missing_book_page"}
    ]
    return {
        "lead_count": len(belief_state.leads),
        "source_candidate_count": len(belief_state.sources),
        "anchor_count": len(belief_state.anchors),
        "open_gap_count": len(open_gaps),
        "blocking_gap_count": len(blocking),
        "permission_gap_count": len(permission),
        "multimodal_gap_count": len(multimodal),
        "boundary": "Frontier status ranks what to search next; it is not claim validation.",
    }
