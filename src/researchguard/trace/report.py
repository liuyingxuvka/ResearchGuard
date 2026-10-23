"""TraceGuard report generator.

Purpose: Render trace summaries with support, diagnostics, gaps, contradictions, and safe wording.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: TraceGuard
Math boundary: Reports explain evaluator output; they do not add LLM inference.
CLI: researchguard trace report <model.yaml> --format markdown
Boundary: Reports must not upgrade candidate or weak-signal traces into confirmed facts.
"""

from __future__ import annotations

from .evaluator import EvaluationResult
from .schema import TraceGuardModel
from .temporal import interval_to_range


def render_markdown(
    result: EvaluationResult, model: TraceGuardModel | None = None, depth: object | None = None,
) -> str:
    if model is not None:
        return _render_research_state(result, model, depth)
    lines: list[str] = ["# TraceGuard Report", ""]
    lines.append(f"Objective score: `{result.objective_score}`")
    lines.append(f"Overall model ok: `{str(result.ok).lower()}`")
    lines.append("")
    for trace in result.traces:
        handoff = next((item for item in result.handoffs if getattr(item, "trace_id", "") == trace.trace_id), None)
        lines.extend(
            [
                f"## {trace.title}",
                "",
                f"- Trace title: {trace.title}",
                f"- Trace type: {trace.trace_type}",
                f"- Validation status: `{trace.validation_status}`",
                f"- Structural support: `{trace.support:.3f}`",
                f"- Current stage: `{trace.current_stage}`",
                f"- Evidence support: {', '.join(trace.evidence_ids) or 'none'}",
                f"- Claim boundary: {trace.claim_boundary}",
                f"- Safe wording: {trace.safe_wording}",
                f"- Unsafe wording avoided: {trace.unsafe_wording_avoided}",
                "",
                "### Report Handoff",
                "",
            ]
        )
        if handoff is None:
            lines.append("- none")
        else:
            lines.extend(
                [
                    f"- Claim id: `{handoff.claim_id}`",
                    f"- Lead id: `{handoff.lead_id}`",
                    f"- Paragraph target: `{handoff.paragraph_target}`",
                    f"- Supporting evidence: {', '.join(handoff.supporting_evidence_ids) or 'none'}",
                    f"- Limiting evidence: {', '.join(handoff.limiting_evidence_ids) or 'none'}",
                    f"- Missing evidence: {'; '.join(handoff.missing_evidence) or 'none'}",
                    f"- Next search task: {handoff.next_search_task or 'none'}",
                ]
            )
        lines.extend(
            [
                "",
                "### Rule Violations",
                "",
            ]
        )
        if trace.rule_results:
            for rule in trace.rule_results:
                lines.append(f"- `{rule.rule_id}` {rule.description} loss={rule.loss:.3f} violation={rule.violation:.3f}")
        else:
            lines.append("- none")
        lines.extend(["", "### Contradictions", ""])
        if trace.contradictions:
            for item in trace.contradictions:
                lines.append(f"- `{item.contradiction_id}` {item.message}")
        else:
            lines.append("- none")
        lines.extend(["", "### Gaps", ""])
        if trace.gaps:
            for gap in trace.gaps:
                lines.append(f"- `{gap.gap_id}` {gap.message} Next: {gap.suggested_next_evidence}")
        else:
            lines.append("- none")
        lines.extend(["", "### Diagnostics", ""])
        if trace.diagnostics:
            for diagnostic in trace.diagnostics:
                lines.append(f"- `{diagnostic.diagnostic_id}` {diagnostic.message} Repair: {diagnostic.repair_hint}")
        else:
            lines.append("- none")
        lines.append("")
    if result.storyline_depth is not None:
        depth = result.storyline_depth
        lines.extend(
            [
                "## Storyline Depth Receipt",
                "",
                f"- Receipt id: `{depth.receipt_id}`",
                f"- Closure status: `{depth.closure_status}`",
                f"- Model fingerprint: `{depth.model_fingerprint}`",
                f"- Candidate universe fingerprint: `{depth.candidate_universe_fingerprint}`",
                f"- Object universe fingerprint: `{depth.object_universe_fingerprint}`",
                f"- Requested / covered scope: `{depth.requested_claim_scope}` / `{depth.covered_claim_scope}`",
                f"- Broad claim licensed: `{str(depth.broad_claim_licensed).lower()}`",
                f"- Eligible / critical / executed: `{depth.coverage_counts['eligible_count']}` / "
                f"`{depth.coverage_counts['critical_count']}` / `{depth.coverage_counts['executed_count']}`",
                f"- Critical uncovered: `{len(depth.critical_uncovered_ids)}`",
                f"- Critical ineffective: `{len(depth.critical_ineffective_ids)}`",
                f"- Critical object uncovered: `{depth.object_coverage_counts['critical_uncovered_count']}`",
                f"- Expected-sensitivity mismatches: `{len(depth.sensitivity_mismatch_ids)}`",
                f"- Predictive holdout status: `{depth.predictive_holdout_status}`",
                f"- Effective perturbations: `{depth.effective_perturbation_count}`",
                f"- Claim boundary: {depth.claim_boundary}",
                "",
                "### Model-Derived Perturbations",
                "",
            ]
        )
        if depth.effects:
            for effect in depth.effects:
                lines.append(
                    f"- `{effect.perturbation.perturbation_id}` kind={effect.perturbation.kind} "
                    f"effective=`{str(effect.effective).lower()}` counts=`{str(effect.counts_toward_depth).lower()}`"
                )
        else:
            lines.append("- none")
        lines.extend(["", "### Unresolved Storyline-Depth Gaps", ""])
        if depth.unresolved_gaps:
            for gap in depth.unresolved_gaps:
                lines.append(
                    f"- `{gap.get('gap_id', 'gap')}` {gap.get('message', '')}"
                )
        else:
            lines.append("- none")
        lines.append("")
    if result.consolidation_findings:
        lines.extend(["## Consolidation And Same-Class Review", ""])
        for finding in result.consolidation_findings:
            lines.append(
                f"- `{finding.finding_type}` {finding.rationale} "
                f"Affected: {', '.join(finding.affected_ids)}. Next: {finding.recommendation}"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_text(
    result: EvaluationResult, model: TraceGuardModel | None = None, depth: object | None = None,
) -> str:
    if model is not None:
        lines = _render_research_state(result, model, depth).splitlines()
        return "\n".join(
            line.lstrip("# ").replace("`", "")
            for line in lines if not line.startswith("| ---")
        ) + "\n"
    blocks = []
    for trace in result.traces:
        blocks.append(
            "\n".join(
                [
                    f"Trace title: {trace.title}",
                    f"Validation status: {trace.validation_status}",
                    f"Structural support: {trace.support:.3f}",
                    f"Current stage: {trace.current_stage}",
                    f"Evidence support: {', '.join(trace.evidence_ids) or 'none'}",
                    f"Contradictions: {len(trace.contradictions)}",
                    f"Gaps: {len(trace.gaps)}",
                    f"Claim boundary: {trace.claim_boundary}",
                    f"Safe wording: {trace.safe_wording}",
                    f"Unsafe wording avoided: {trace.unsafe_wording_avoided}",
                ]
            )
        )
    if result.consolidation_findings:
        blocks.append(
            "Consolidation and same-class review:\n"
            + "\n".join(f"- {item.finding_type}: {item.rationale}" for item in result.consolidation_findings)
        )
    if result.storyline_depth is not None:
        blocks.append(
            "Storyline depth receipt:\n"
            f"- Closure status: {result.storyline_depth.closure_status}\n"
            f"- Requested / covered scope: {result.storyline_depth.requested_claim_scope} / "
            f"{result.storyline_depth.covered_claim_scope}\n"
            f"- Broad claim licensed: {result.storyline_depth.broad_claim_licensed}\n"
            f"- Critical uncovered: {len(result.storyline_depth.critical_uncovered_ids)}\n"
            f"- Critical ineffective: {len(result.storyline_depth.critical_ineffective_ids)}\n"
            f"- Critical object uncovered: {result.storyline_depth.object_coverage_counts['critical_uncovered_count']}\n"
            f"- Predictive holdout status: {result.storyline_depth.predictive_holdout_status}\n"
            f"- Effective perturbations: {result.storyline_depth.effective_perturbation_count}\n"
            f"- Unresolved gaps: {len(result.storyline_depth.unresolved_gaps)}\n"
            f"- Claim boundary: {result.storyline_depth.claim_boundary}"
        )
    return "\n\n".join(blocks) + "\n"


def _cell(value: object) -> str:
    """Keep caller text inside one Markdown table cell without losing its content."""
    return str(value).replace("\n", " ").replace("|", "\\|")


def _render_research_state(
    result: EvaluationResult, model: TraceGuardModel, depth: object | None,
) -> str:
    """Compact reading view; all native blockers remain intact, with no byte slicing."""
    depth = depth if depth is not None else result.storyline_depth
    lines = ["# TraceGuard Report", "", "## Timeline", "",
             "| Date | Event id | Action | Evidence ids |", "| --- | --- | --- | --- |"]

    def event_order(event):
        start = interval_to_range(event.time_interval).start
        return (start is None, start.isoformat() if start else "", event.event_id)

    for event in sorted(model.events, key=event_order):
        interval = event.time_interval
        when = "unknown"
        if interval is not None:
            when = str(interval.start or interval.end or interval.text or "unknown")
            if interval.start and interval.end and interval.start != interval.end:
                when = f"{interval.start}–{interval.end}"
        lines.append("| " + " | ".join(map(_cell, (
            when, event.event_id, event.action, ", ".join(event.evidence_ids) or "none",
        ))) + " |")
    lines.extend(["", "## Hypotheses", "",
                  "| Hypothesis id | Claim | Support | Rank | Live | Causal status | Top opposition factor |",
                  "| --- | --- | --- | --- | --- | --- | --- |"])
    hypotheses = model.hypothesis_by_id()
    for row in result.inference_receipt.hypothesis_projections:
        hypothesis = hypotheses.get(row.hypothesis_id)
        claim = hypothesis.claim if hypothesis is not None else ""
        if hypothesis is None and row.hypothesis_id.startswith("implicit:"):
            trace = model.trace_by_id().get(row.hypothesis_id.removeprefix("implicit:"))
            claim = (trace.claim or trace.title) if trace is not None else ""
        claim = claim if len(claim) <= 80 else claim[:79] + "…"
        lines.append("| " + " | ".join(map(_cell, (
            row.hypothesis_id, claim, f"{row.support:.3f}", row.rank,
            str(row.live).lower(), row.causal_status,
            next(iter(row.top_opposition_factor_ids), "none"),
        ))) + " |")
    lines.extend(["", "## Storyline Depth", ""])
    if depth is None:
        lines.append("Not run.")
    else:
        lines.append(
            f"{depth.closure_status}; scope {depth.requested_claim_scope}/{depth.covered_claim_scope}; "
            f"broad claim licensed={str(depth.broad_claim_licensed).lower()}; "
            f"unresolved={len(depth.unresolved_gaps)}."
        )
        for gap in depth.unresolved_gaps:
            owner = gap.get("hypothesis_id") or gap.get("object_id")
            context = f" ({owner})" if owner else ""
            lines.append(f"- `{gap.get('gap_id', 'gap')}`{context}: {gap.get('message', '')}")
        if not depth.unresolved_gaps:
            lines.append("- none")
    lines.extend(["", f"Objective score: {result.objective_score}; Overall model ok: {str(result.ok).lower()}"])
    for trace in result.traces:
        lines.extend([
            "", f"## {trace.title}", "",
            f"Trace type: {trace.trace_type}; Validation status: {trace.validation_status}; "
            f"Structural support: {trace.support:.3f}; Current stage: {trace.current_stage}",
            f"Evidence support: {', '.join(trace.evidence_ids) or 'none'}",
            f"Claim boundary: {trace.claim_boundary}",
            f"Safe wording: {trace.safe_wording}",
            f"Unsafe wording avoided: {trace.unsafe_wording_avoided}",
            "", "### Report Handoff", "",
        ])
        handoff = next((item for item in result.handoffs if item.trace_id == trace.trace_id), None)
        if handoff is None:
            lines.append("- none")
        else:
            lines.extend([
                f"Claim id: {handoff.claim_id}; Lead id: {handoff.lead_id}; Target: {handoff.paragraph_target}",
                f"Supporting: {', '.join(handoff.supporting_evidence_ids) or 'none'}; "
                f"Limiting: {', '.join(handoff.limiting_evidence_ids) or 'none'}",
                f"Missing: {'; '.join(handoff.missing_evidence) or 'none'}; "
                f"Next search: {handoff.next_search_task or 'none'}",
            ])
        lines.extend(["", "### Rule Violations", ""])
        for rule in trace.rule_results[:3]:
            lines.append(f"- `{rule.rule_id}` loss={rule.loss:.3f} violation={rule.violation:.3f}")
        if not trace.rule_results:
            lines.append("- none")
        for title, items, id_field in (
            ("Contradictions", trace.contradictions, "contradiction_id"),
            ("Gaps", trace.gaps, "gap_id"),
            ("Diagnostics", trace.diagnostics, "diagnostic_id"),
        ):
            lines.extend(["", f"### {title}", ""])
            for item in items:
                extra = getattr(item, "suggested_next_evidence", "") or getattr(item, "repair_hint", "")
                lines.append(f"- `{getattr(item, id_field)}` {item.message}" + (f" Next: {extra}" if extra else ""))
            if not items:
                lines.append("- none")
    if result.consolidation_findings:
        lines.extend(["", "## Consolidation And Same-Class Review", ""])
        for finding in result.consolidation_findings:
            lines.append(
                f"- `{finding.finding_type}` {finding.rationale} "
                f"Affected: {', '.join(finding.affected_ids)}. Next: {finding.recommendation}"
            )
    return "\n".join(lines).strip() + "\n"
