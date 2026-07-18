"""
Purpose: Render SourceGuard belief states and plans as text, Markdown, or JSON reports.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source report <model.yaml> --model-contract <model.contract.json> --format markdown
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims.
"""

from __future__ import annotations

import json
from typing import Any

from .planner import plan_next_actions
from .schema import BeliefState, PlanResult, to_plain


MATH_BOUNDARY = (
    "SourceGuard is a POMDP-inspired approximate planner. Expected utility ranks search-action value, "
    "not factual truth, source validity, evidence authenticity, or final claim confidence."
)


def _plan(value: PlanResult | BeliefState) -> tuple[BeliefState | None, PlanResult]:
    if isinstance(value, BeliefState):
        return value, plan_next_actions(value)
    return None, value


def render_markdown(value: PlanResult | BeliefState) -> str:
    belief_state, plan = _plan(value)
    lines = [
        "# SourceGuard Summary",
        "",
        "## Math Boundary",
        MATH_BOUNDARY,
        "",
        "## Current Leads",
    ]
    if belief_state:
        for lead in belief_state.leads:
            lines.append(f"- `{lead.lead_id}`: {lead.question} (status: {lead.status}, importance: {lead.importance:.2f})")
    else:
        lines.append("- Plan-only report.")
    lines.extend(["", "## Open Gaps"])
    for gap in plan.open_gaps:
        structural = ""
        if gap.structure_unit_id or gap.structural_role_needed:
            structural = (
                f" [structure: {gap.structure_unit_id or 'unspecified'}; "
                f"role: {gap.structural_role_needed or gap.contribution_type or 'unspecified'}; "
                f"consumer: {gap.downstream_consumer or 'unspecified'}]"
            )
        lines.append(
            f"- `{gap.gap_id}`: {gap.gap_type} - {gap.description}{structural} "
            f"(semantic state: {gap.semantic_state}; review required: {str(gap.review_required).lower()})"
        )
    lines.extend(["", "## Semantic Gap Lifecycle"])
    if belief_state and belief_state.gaps:
        for gap in belief_state.gaps:
            basis = "qualified closure basis recorded" if gap.closure_basis.is_complete() else "no qualified closure basis"
            lines.append(
                f"- `{gap.gap_id}`: `{gap.semantic_state}`; {basis}."
            )
    else:
        lines.append("- No model-backed lifecycle rows are available in this plan-only report.")
    lines.extend(["", "## Recommended Search Actions"])
    selected_ids = {action.action_id for action in plan.selected_actions}
    for scored in plan.scored_actions:
        if scored.action_id not in selected_ids:
            continue
        action = next((item for item in plan.selected_actions if item.action_id == scored.action_id), None)
        if action:
            lines.append(f"- `{action.action_id}` ({action.action_type}) score={scored.total_score:.3f}: {action.query}")
    lines.extend(["", "## Why These Actions"])
    for scored in plan.scored_actions[: len(plan.selected_actions)]:
        lines.append(f"- `{scored.action_id}`: " + " ".join(scored.reasons[:4]))
    lines.extend(["", "## Multimodal Anchor Needs"])
    anchor_needs = [
        gap
        for gap in plan.open_gaps
        if gap.gap_type in {"missing_visual_anchor", "missing_audio_anchor", "missing_pdf_page", "missing_book_page", "missing_execution_evidence", "missing_location"}
        or any(modality in {"image", "video", "audio", "pdf_page", "book_page", "map"} for modality in gap.suggested_modalities)
    ]
    for gap in anchor_needs:
        needed = ", ".join(gap.suggested_modalities) or gap.gap_type
        lines.append(f"- `{gap.gap_id}` needs locator-aware {needed} source discovery; extraction is not assumed.")
    if not anchor_needs:
        lines.append("- No explicit multimodal anchor gap is open.")
    lines.extend(["", "## Blocked / Permission-Gated Items"])
    if plan.blocked_gaps:
        for gap in plan.blocked_gaps:
            lines.append(f"- `{gap.gap_id}`: {gap.description or gap.gap_type}")
    else:
        lines.append("- None recorded.")
    lines.extend(["", "## Handoff Readiness"])
    if belief_state and belief_state.anchors:
        lines.append("- TraceGuard seed can include candidate sources and locator-bearing anchors, but no validated events.")
    else:
        lines.append("- Not ready for trace reconstruction; source candidates or anchors are still thin.")
    lines.append("- LogicGuard handoff remains candidate material until preserved and modeled downstream.")
    lines.extend(["", "## Unsafe Wording To Avoid"])
    lines.append("- Avoid saying a candidate source proves a claim.")
    lines.append("- Avoid saying SourceGuard validated a trace, event, image, video, audio, or final conclusion.")
    lines.append("- Avoid treating utility score as factual confidence.")
    return "\n".join(lines) + "\n"


def render_text(value: PlanResult | BeliefState) -> str:
    belief_state, plan = _plan(value)
    parts = [
        "SourceGuard Summary",
        MATH_BOUNDARY,
        f"Open gaps: {len(plan.open_gaps)}",
        f"Blocked gaps: {len(plan.blocked_gaps)}",
        "Recommended actions:",
    ]
    for action in plan.selected_actions:
        score = next((item.total_score for item in plan.scored_actions if item.action_id == action.action_id), 0.0)
        parts.append(f"- {action.action_id} ({action.action_type}) score={score:.3f}: {action.query}")
    if belief_state:
        parts.append(f"Candidate sources: {len(belief_state.sources)}")
        parts.append(f"Evidence anchors: {len(belief_state.anchors)}")
        semantic_counts: dict[str, int] = {}
        for gap in belief_state.gaps:
            semantic_counts[gap.semantic_state] = semantic_counts.get(gap.semantic_state, 0) + 1
        parts.append(f"Semantic gap states: {semantic_counts}")
    parts.append("Boundary: candidate material requires downstream TraceGuard/LogicGuard review.")
    return "\n".join(parts) + "\n"


def render_json(value: Any) -> str:
    return json.dumps(to_plain(value), ensure_ascii=False, indent=2)
