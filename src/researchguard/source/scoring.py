"""
Purpose: Score SourceGuard search actions under a POMDP-style approximate source discovery model.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source plan <model.yaml> --model-contract <model.contract.json>
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims.
"""

from __future__ import annotations

from .schema import (
    BeliefState,
    Gap,
    ScoredAction,
    SearchAction,
    clamp01,
    validate_model_guard_binding,
)


def default_weights() -> dict[str, float]:
    return {
        "w_gap": 0.24,
        "w_info": 0.14,
        "w_counter": 0.13,
        "w_newlead": 0.09,
        "w_independent": 0.11,
        "w_multimodal": 0.10,
        "w_freshness": 0.07,
        "w_authority": 0.08,
        "w_cost": 0.12,
        "w_redundancy": 0.12,
        "w_permission": 0.18,
    }


def _weights(belief_state: BeliefState) -> dict[str, float]:
    weights = default_weights()
    weights.update({key: float(value) for key, value in belief_state.weights.items()})
    return weights


def _target_gap(action: SearchAction, belief_state: BeliefState) -> Gap | None:
    return belief_state.gap_by_id().get(action.target_gap_id)


def _target_lead_importance(action: SearchAction, belief_state: BeliefState) -> float:
    lead = belief_state.lead_by_id().get(action.target_lead_id)
    if lead:
        return lead.importance
    gap = _target_gap(action, belief_state)
    if gap:
        lead = belief_state.lead_by_id().get(gap.lead_id)
        if lead:
            return lead.importance
    return 0.5


def _reason(reasons: list[str], condition: bool, text: str) -> None:
    if condition:
        reasons.append(text)


def normalize_cost(value: float) -> float:
    return clamp01(value, 0.3)


def estimate_gap_closure(action: SearchAction, gap: Gap | None, belief_state: BeliefState) -> tuple[float, list[str]]:
    reasons: list[str] = []
    if gap is None:
        return 0.1, ["No target gap was declared, so gap-closure value is conservative."]
    score = 0.2 + (0.35 * gap.importance)
    if gap.blocking:
        score += 0.2
        reasons.append("The target gap is blocking, so closing it would unblock the lead frontier.")
    if gap.gap_type in {
        "missing_primary_source",
        "missing_execution_evidence",
        "weak_signal_only",
        "missing_independent_source",
    } and action.action_type in {
        "primary_source_search",
        "source_domain_search",
        "government_record",
        "text_search",
        "counterevidence_search",
    }:
        score += 0.15
        reasons.append(f"{action.action_type} directly matches the {gap.gap_type} gap.")
    if gap.gap_type == "missing_execution_evidence" and action.action_type in {
        "source_domain_search",
        "image_search",
        "video_search",
        "report_page_search",
        "map_location_search",
    }:
        score += 0.18
        reasons.append("Execution evidence needs concrete deployment, location, media, or official-record search.")
    if gap.gap_type in {"missing_pdf_page", "missing_book_page", "missing_visual_anchor", "missing_audio_anchor"}:
        if action.expected_modality in gap.suggested_modalities or action.expected_modality != "unknown":
            score += 0.12
            reasons.append("The action targets the modality needed by the gap.")
    return clamp01(score, 0.0), reasons or ["The action targets an open gap and may reduce uncertainty."]


def estimate_information_gain(action: SearchAction, belief_state: BeliefState) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.2
    if action.action_type in {
        "entity_expand",
        "citation_backward",
        "citation_forward",
        "followup_from_anchor",
        "map_location_search",
    }:
        score += 0.35
        reasons.append(f"{action.action_type} can expose new entities, citations, or leads.")
    if action.query:
        score += 0.1
        reasons.append("The action has a concrete query rather than an underspecified search instruction.")
    score += 0.2 * _target_lead_importance(action, belief_state)
    if len(belief_state.sources) < 3:
        score += 0.15
        reasons.append("The belief state has few sources, so additional observations can change the frontier.")
    return clamp01(score, 0.0), reasons or ["Information gain is conservative because the action is broad or underspecified."]


def estimate_counterevidence_value(action: SearchAction, belief_state: BeliefState) -> tuple[float, list[str]]:
    reasons: list[str] = []
    if action.action_type != "counterevidence_search" and action.expected_source_role not in {
        "counter_evidence",
        "limiting_evidence",
    }:
        return 0.1, ["The action is not primarily searching for counter or limiting evidence."]
    gap = _target_gap(action, belief_state)
    score = 0.4
    if gap and gap.gap_type in {"one_sided_support", "weak_signal_only", "missing_counterevidence", "contradiction"}:
        score += 0.45
        reasons.append(f"Counter/limiting search is valuable because the target gap is {gap.gap_type}.")
    if any(source.source_role in {"official_claim", "hypothesis_source"} for source in belief_state.sources):
        score += 0.1
        reasons.append("Existing sources include one-sided official or hypothesis material.")
    return clamp01(score, 0.0), reasons or ["Counterevidence search helps avoid one-sided support."]


def estimate_new_lead_value(action: SearchAction, belief_state: BeliefState) -> tuple[float, list[str]]:
    if action.action_type in {"entity_expand", "citation_forward", "citation_backward", "followup_from_anchor"}:
        return 0.7, [f"{action.action_type} is likely to create or refine leads."]
    if action.action_type in {"image_search", "video_search", "map_location_search"}:
        return 0.45, ["Multimodal or location searches can open new follow-up leads."]
    return 0.15, ["The action is focused on an existing gap rather than lead expansion."]


def estimate_source_independence_value(action: SearchAction, belief_state: BeliefState) -> tuple[float, list[str]]:
    if action.expected_source_role in {"independent_report", "counter_evidence", "limiting_evidence"}:
        return 0.75, ["The expected source role is independent, counter, or limiting material."]
    if action.action_type in {"source_domain_search", "government_record", "procurement_record"}:
        return 0.55, ["Domain-specific or official-record search can diversify the source cluster."]
    roles = {source.source_role for source in belief_state.sources}
    if action.expected_source_role and action.expected_source_role not in roles:
        return 0.45, ["The expected source role is not yet represented in known source candidates."]
    return 0.2, ["The action may duplicate the existing source-role cluster."]


def estimate_multimodal_anchor_value(action: SearchAction, belief_state: BeliefState) -> tuple[float, list[str]]:
    gap = _target_gap(action, belief_state)
    modality = action.expected_modality
    if gap and (
        (gap.gap_type == "missing_visual_anchor" and modality in {"image", "video"})
        or (gap.gap_type == "missing_audio_anchor" and modality == "audio")
        or (gap.gap_type == "missing_pdf_page" and modality == "pdf_page")
        or (gap.gap_type == "missing_book_page" and modality == "book_page")
    ):
        return 0.9, ["The action targets the exact multimodal anchor type required by the gap."]
    if modality in {"image", "video", "audio", "pdf_page", "book_page", "map"}:
        return 0.45, ["The action may create a locator-based multimodal anchor, but extraction is not assumed."]
    return 0.05, ["The action is text-oriented and does not specifically request a multimodal anchor."]


def estimate_freshness_value(action: SearchAction, belief_state: BeliefState) -> tuple[float, list[str]]:
    gap = _target_gap(action, belief_state)
    if gap and gap.gap_type in {"stale_source", "missing_date", "contradiction"}:
        return 0.75, ["The target gap needs date or freshness resolution."]
    if action.parameters.get("freshness_focused"):
        return 0.7, ["The action explicitly asks for freshness-sensitive material."]
    if action.action_type in {"exact_phrase_search", "report_page_search", "pdf_page_search"}:
        return 0.45, ["Precise document searches can improve date and version grounding."]
    return 0.2, ["Freshness is not the main value of this action."]


def estimate_source_authority_value(action: SearchAction, belief_state: BeliefState) -> tuple[float, list[str]]:
    if action.expected_source_role == "primary_source":
        return 0.75, ["The action expects a primary source, which is useful for source discovery."]
    if action.action_type in {"primary_source_search", "source_domain_search", "report_page_search", "pdf_page_search"}:
        return 0.6, ["The action searches near primary or report-like material."]
    if action.expected_source_role in {"official_claim", "expert_analysis"}:
        return 0.45, ["The action expects an official or expert source candidate."]
    return 0.2, ["The action has limited source-authority value."]


def estimate_redundancy_penalty(action: SearchAction, belief_state: BeliefState) -> tuple[float, list[str]]:
    penalty = 0.0
    reasons: list[str] = []
    normalized_query = " ".join(action.query.lower().split())
    for existing in belief_state.actions:
        if existing.action_id == action.action_id:
            continue
        same_query = normalized_query and normalized_query == " ".join(existing.query.lower().split())
        same_gap = action.target_gap_id and action.target_gap_id == existing.target_gap_id
        same_role = action.expected_source_role == existing.expected_source_role
        same_type = action.action_type == existing.action_type
        if same_query and same_gap and same_role and same_type:
            penalty = max(penalty, 0.8)
        elif same_query or (same_gap and same_type and same_role):
            penalty = max(penalty, 0.45)
    if penalty:
        reasons.append("The action overlaps an existing action by query, gap, type, or expected source role.")
    role_sources = [source for source in belief_state.sources if source.source_role == action.expected_source_role]
    if action.expected_source_role != "unknown" and len(role_sources) >= 3:
        penalty = max(penalty, 0.35)
        reasons.append("The belief state already has several candidate sources in the expected role.")
    return clamp01(penalty, 0.0), reasons or ["No strong duplicate action pattern was detected."]


def score_action(action: SearchAction, belief_state: BeliefState) -> ScoredAction:
    gap = _target_gap(action, belief_state)
    gap_value, gap_reasons = estimate_gap_closure(action, gap, belief_state)
    info_value, info_reasons = estimate_information_gain(action, belief_state)
    counter_value, counter_reasons = estimate_counterevidence_value(action, belief_state)
    new_lead_value, new_lead_reasons = estimate_new_lead_value(action, belief_state)
    independent_value, independent_reasons = estimate_source_independence_value(action, belief_state)
    multimodal_value, multimodal_reasons = estimate_multimodal_anchor_value(action, belief_state)
    freshness_value, freshness_reasons = estimate_freshness_value(action, belief_state)
    authority_value, authority_reasons = estimate_source_authority_value(action, belief_state)
    search_cost = normalize_cost(action.cost)
    redundancy_penalty, redundancy_reasons = estimate_redundancy_penalty(action, belief_state)
    permission_risk = clamp01(action.permission_risk, 0.0)
    weights = _weights(belief_state)
    total = (
        weights["w_gap"] * gap_value
        + weights["w_info"] * info_value
        + weights["w_counter"] * counter_value
        + weights["w_newlead"] * new_lead_value
        + weights["w_independent"] * independent_value
        + weights["w_multimodal"] * multimodal_value
        + weights["w_freshness"] * freshness_value
        + weights["w_authority"] * authority_value
        - weights["w_cost"] * search_cost
        - weights["w_redundancy"] * redundancy_penalty
        - weights["w_permission"] * permission_risk
    )
    reasons = (
        gap_reasons
        + info_reasons
        + counter_reasons
        + new_lead_reasons
        + independent_reasons
        + multimodal_reasons
        + freshness_reasons
        + authority_reasons
        + redundancy_reasons
    )
    if permission_risk >= 0.6:
        reasons.append("Permission risk is high, so the utility is reduced and should be treated as an access concern.")
    return ScoredAction(
        action_id=action.action_id,
        total_score=clamp01(total, 0.0),
        gap_closure_value=gap_value,
        information_gain=info_value,
        counterevidence_value=counter_value,
        new_lead_value=new_lead_value,
        source_independence_value=independent_value,
        multimodal_anchor_value=multimodal_value,
        freshness_value=freshness_value,
        source_authority_value=authority_value,
        search_cost=search_cost,
        redundancy_penalty=redundancy_penalty,
        permission_risk=permission_risk,
        reasons=reasons,
    )


def score_actions(belief_state: BeliefState) -> list[ScoredAction]:
    validate_model_guard_binding(belief_state)
    scored = [score_action(action, belief_state) for action in belief_state.actions if action.status not in {"blocked", "rejected", "completed"}]
    return sorted(scored, key=lambda item: item.total_score, reverse=True)
