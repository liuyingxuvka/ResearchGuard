"""Model-grounded claim and review suggestions."""

from __future__ import annotations

from .diagnostics import diagnose_model
from .evaluator import evaluate_model
from .model import DiagnosticReport, LogicModel


def claim_strength_adjustment(model: LogicModel, report: DiagnosticReport | None = None) -> str:
    report = report or diagnose_model(model, evaluate_model(model))
    suggestions: list[str] = []
    for finding in report.findings:
        if finding.rewrite_suggestion:
            suggestions.append(f"- {finding.code} ({', '.join(finding.affected_nodes)}): {finding.rewrite_suggestion}")
    if not suggestions:
        for node_id, node in model.nodes.items():
            if node.type == "Claim":
                suggestions.append(f"- {node_id}: {node.text}")
    return "# Claim Strength Adjustments\n\n" + "\n".join(suggestions) + "\n"


def review_report_generator(model: LogicModel, report: DiagnosticReport | None = None) -> str:
    report = report or diagnose_model(model, evaluate_model(model))
    major = [finding for finding in report.findings if finding.severity in {"critical", "error"}]
    minor = [finding for finding in report.findings if finding.severity in {"warning", "info"}]
    lines = ["# Logic Review Report", "", "## Major Logical Issues"]
    lines.extend(_review_lines(major))
    lines.extend(["", "## Minor Logical Issues"])
    lines.extend(_review_lines(minor))
    lines.extend(["", "## Recommended Revisions"])
    if report.findings:
        lines.extend(f"- {finding.suggested_repair}" for finding in report.findings[:8])
    else:
        lines.append("- No structural revisions required by the current model.")
    return "\n".join(lines).rstrip() + "\n"


def _review_lines(findings: list[object]) -> list[str]:
    if not findings:
        return ["- None identified."]
    return [f"- {finding.code}: {finding.explanation}" for finding in findings]
