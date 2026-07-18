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


def render_markdown(result: EvaluationResult) -> str:
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


def render_text(result: EvaluationResult) -> str:
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
