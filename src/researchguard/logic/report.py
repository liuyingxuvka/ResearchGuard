"""Markdown report generation."""

from __future__ import annotations

from .diagnostics import diagnose_model
from .evaluator import evaluate_model
from .execution_depth import _build_native_depth_analysis
from .model import DiagnosticReport, EvaluationResult, LogicModel, SimulationResult
from .simulator import dependency_trace, search_counterexamples, simulate_fragility
from .writer import claim_strength_adjustment


def generate_markdown_report(
    model: LogicModel,
    result: EvaluationResult | None = None,
    diagnostics: DiagnosticReport | None = None,
    fragility: SimulationResult | None = None,
    counterexample: SimulationResult | None = None,
) -> str:
    result = result or evaluate_model(model)
    diagnostics = diagnostics or diagnose_model(model, result)
    fragility = fragility or simulate_fragility(model, root_claim=model.root_claim)
    counterexample = counterexample or search_counterexamples(model, root_claim=model.root_claim)
    depth_receipt = _build_native_depth_analysis(model)
    root = result.root()

    lines = [
        f"# LogicGuard Report: {model.title or model.id}",
        "",
        "## Executive Summary",
    ]
    if root:
        lines.append(
            f"Root claim `{root.node_id}` is `{root.state}` with structural confidence `{root.confidence:.2f}`."
        )
        if root.explanation:
            lines.append(f"Reason: {root.explanation}")
    else:
        lines.append("No root claim is defined.")
    if diagnostics.findings:
        lines.append(f"LogicGuard found {len(diagnostics.findings)} structural issue(s).")
    else:
        lines.append("No structural logic findings were detected.")

    lines.extend(["", "## Root Claim Status"])
    if root:
        root_node = model.nodes[root.node_id]
        lines.extend(
            [
                f"- Claim: {root_node.text}",
                f"- State: {root.state}",
                f"- Confidence: {root.confidence:.2f}",
                f"- Explanation: {root.explanation}",
                f"- Blockers: {', '.join(root.blockers) or 'None'}",
            ]
        )
    else:
        lines.append("- No root claim.")

    lines.extend(["", "## Support Structure"])
    support_rows = [row for row in dependency_trace(model, root_claim=model.root_claim) if row.get("edge_type") in {"supports", "depends_on", "refines", "derives", "aggregates"}]
    lines.extend(_path_lines(support_rows) or ["- No declared support paths."])

    lines.extend(["", "## Attack / Rebuttal Structure"])
    attack_rows = [row for row in dependency_trace(model, root_claim=model.root_claim) if row.get("edge_type") in {"attacks", "undercuts", "contradicts"}]
    lines.extend(_path_lines(attack_rows) or ["- No declared attack or rebuttal paths."])

    lines.extend(["", "## Missing Warrants"])
    lines.extend(_finding_lines(diagnostics, "missing_warrant"))

    lines.extend(["", "## Hidden Assumptions"])
    lines.extend(_finding_lines(diagnostics, "hidden_assumption"))

    lines.extend(["", "## Scope and Qualifier Issues"])
    scope_codes = {"scope_mismatch", "missing_boundary_condition", "premature_generalization"}
    lines.extend(_finding_lines(diagnostics, scope_codes))

    lines.extend(["", "## Fragility Analysis"])
    if fragility.impacts:
        for item in fragility.impacts[:8]:
            lines.append(
                f"- `{item['node_id']}` ({item['node_type']}): impact={item['impact_score']}, "
                f"root -> {item['result_state']} at confidence {item['result_confidence']}"
            )
    else:
        lines.append("- No fragility impacts found.")

    lines.extend(["", "## Counterexample Traces"])
    if counterexample.impacts:
        for item in counterexample.impacts[:5]:
            nodes = ", ".join(item.get("minimal_conditions", []))
            lines.append(f"- If `{nodes}` is perturbed: {item.get('explanation')}")
    else:
        lines.append("- No single-node counterexample found.")

    lines.extend(["", "## Suggested Repairs"])
    if diagnostics.findings:
        for finding in diagnostics.findings[:10]:
            lines.append(f"- {finding.code}: {finding.suggested_repair}")
    else:
        lines.append("- Keep claims tied to declared evidence, warrants, assumptions, and scope.")

    lines.extend(["", "## Native Execution Depth"])
    universe = depth_receipt.coverage_universe
    lines.extend(
        [
            f"- Receipt status: `{depth_receipt.status}`",
            f"- Depth profile: `{depth_receipt.profile}`",
            f"- Model fingerprint: `{depth_receipt.model_fingerprint}`",
            f"- Coverage-universe fingerprint: `{universe.universe_fingerprint if universe else 'NOT_RUN'}`",
            f"- Important coverage: {depth_receipt.coverage.covered_count}/{depth_receipt.coverage.required_count}",
            f"- Role-complete important cards: {sum(row.status == 'pass' for row in universe.role_coverage) if universe else 0}/{len(universe.role_coverage) if universe else 0}",
            f"- Disconnected important nodes: {', '.join(universe.unresolved_disconnected_node_ids) if universe and universe.unresolved_disconnected_node_ids else 'None'}",
            f"- Claim scope coverage: {len(universe.claim_scope.covered_node_ids) if universe else 0}/{len(universe.claim_scope.requested_node_ids) if universe else 0}",
            f"- Unresolved competitors: {', '.join(depth_receipt.tournament.unresolved_competitor_ids) or 'None'}",
            f"- Effective perturbations: {sum(item.effective for item in depth_receipt.perturbation_effectiveness)}",
            f"- Effective critical perturbations: {depth_receipt.critical_perturbation_coverage.get('effective_count', 0)}/{depth_receipt.critical_perturbation_coverage.get('eligible_count', 0)}",
            f"- Untested high-impact nodes: {', '.join(depth_receipt.untested_high_impact_node_ids) or 'None'}",
            f"- Broad structural claim licensed: {depth_receipt.broad_claim_licensed}",
            f"- Boundary: {depth_receipt.claim_boundary}",
        ]
    )

    lines.extend(["", "## Suggested Rewrite"])
    rewrites = claim_strength_adjustment(model, diagnostics).splitlines()[2:]
    lines.extend(rewrites or ["- No rewrite needed."])

    return "\n".join(lines).rstrip() + "\n"


def _path_lines(rows: list[dict[str, object]]) -> list[str]:
    lines: list[str] = []
    for row in rows[:12]:
        path = " -> ".join(row.get("path", []))
        edge_type = row.get("edge_type", "")
        lines.append(f"- {edge_type}: {path}")
    return lines


def _finding_lines(report: DiagnosticReport, code: str | set[str]) -> list[str]:
    codes = {code} if isinstance(code, str) else code
    items = [finding for finding in report.findings if finding.code in codes]
    if not items:
        return ["- None detected."]
    return [f"- {finding.code} ({', '.join(finding.affected_nodes)}): {finding.explanation}" for finding in items]
