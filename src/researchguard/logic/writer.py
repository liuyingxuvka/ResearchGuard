"""Model-grounded writing helpers."""

from __future__ import annotations

from .diagnostics import diagnose_model
from .evaluator import evaluate_model
from .hierarchy import build_children_index, hierarchy_roots
from .importance import importance_for_node
from .model import DiagnosticReport, LogicModel
from .citation_matrix import ClaimSourceParagraphMatrix


def model_to_outline(model: LogicModel) -> str:
    children = build_children_index(model)
    roots = hierarchy_roots(model)
    lines = [f"# Outline: {model.title or model.id}", ""]
    for root in roots:
        _append_outline_node(model, children, root, lines, level=1)
    if model.root_claim and model.root_claim in model.nodes:
        root_node = model.nodes[model.root_claim]
        lines.extend(["", "## Root Claim", f"- {model.root_claim}: {root_node.text}"])
    return "\n".join(lines).rstrip() + "\n"


def model_to_section_plan(model: LogicModel) -> str:
    lines = [f"# Section Plan: {model.title or model.id}", ""]
    sections = [node_id for node_id, node in model.nodes.items() if node.type in {"Section", "ArgumentBlock"}]
    if not sections:
        sections = [parent for parent in model.hierarchy if parent != model.root_claim]
    for section_id in sections:
        child_ids = model.children_of(section_id)
        claims = _nodes_of_types(model, child_ids, {"Claim"})
        evidence = _nodes_of_types(model, child_ids, {"Evidence", "Result"})
        warrants = _nodes_of_types(model, child_ids, {"Warrant"})
        assumptions = _nodes_of_types(model, child_ids, {"Assumption"})
        rebuttals = _nodes_of_types(model, child_ids, {"Rebuttal", "Undercutter"})
        limitations = _nodes_of_types(model, child_ids, {"Limitation", "Qualifier"})
        title = model.nodes[section_id].text if section_id in model.nodes else section_id
        lines.extend(
            [
                f"## {section_id}: {title}",
                f"- Section claim: {_format_node_list(model, claims) or 'Define a local claim.'}",
                f"- Required evidence: {_format_node_list(model, evidence) or 'Add evidence/result nodes.'}",
                f"- Required warrant: {_format_node_list(model, warrants) or 'Add an explicit warrant.'}",
                f"- Assumptions to state: {_format_node_list(model, assumptions) or 'None declared.'}",
                f"- Rebuttals to address: {_format_node_list(model, rebuttals) or 'None declared.'}",
                f"- Limitations to include: {_format_node_list(model, limitations) or 'Add scope or boundary conditions.'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


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


def paragraph_blueprint(model: LogicModel, claim_id: str | None = None, citation_matrix: ClaimSourceParagraphMatrix | None = None) -> str:
    claim_id = claim_id or model.root_claim
    if not claim_id or claim_id not in model.nodes:
        return "# Paragraph Blueprint\n\nNo claim selected.\n"
    claim = model.nodes[claim_id]
    incoming = model.incoming(claim_id)
    evidence = [edge.source for edge in incoming if model.nodes[edge.source].type in {"Evidence", "Result"}]
    warrants = [edge.source for edge in incoming if model.nodes[edge.source].type == "Warrant"]
    limitations = [edge.source for edge in incoming if model.nodes[edge.source].type in {"Limitation", "Qualifier"}]
    lines = [
        f"# Paragraph Blueprint: {claim_id}",
        "",
        f"- Topic sentence: {claim.text}",
        f"- Evidence: {_format_node_list(model, evidence) or 'Add evidence before drafting.'}",
        f"- Warrant: {_format_node_list(model, warrants) or 'Explain why the evidence supports the claim.'}",
        f"- Limitation: {_format_node_list(model, limitations) or claim.scope or 'State the applicable boundary.'}",
        "- Transition: Connect this local claim to the next higher-level claim.",
    ]
    if citation_matrix is not None and (row := citation_matrix.row_for_claim(claim_id)) is not None:
        lines.extend(
            [
                f"- Paragraph locator: {row.paragraph_locator or 'Assign a paragraph or section locator.'}",
                f"- Source markers: {row.citation_marker or 'Add source marker before final prose.'}",
                f"- Source roles: {_format_source_roles(row.source_roles)}",
                f"- Claim strength: {row.claim_strength}",
                f"- Citation stale when: {'; '.join(row.stale_when) or 'Not declared.'}",
            ]
        )
    return "\n".join(lines) + "\n"


def paper_structure_generator(model: LogicModel) -> str:
    lines = [
        f"# Paper Structure: {model.title or model.id}",
        "",
        "## Introduction",
        "- Establish the root claim and the problem context.",
        "",
        "## Research Gap",
        "- Use gap claims, definitions, and context nodes to explain what is missing.",
        "",
        "## Method",
        "- Present method nodes and the assumptions required by the argument.",
        "",
        "## Results",
        "- Present evidence/result nodes and their direct claims.",
        "",
        "## Discussion",
        "- State warrants, rebuttal responses, and the scope of supported conclusions.",
        "",
        "## Limitations",
        "- Include limitation, qualifier, and unresolved rebuttal nodes.",
        "",
        "## Conclusion",
        "- Restate only the version of the root claim licensed by the model.",
    ]
    return "\n".join(lines) + "\n"


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


def _append_outline_node(
    model: LogicModel,
    children: dict[str, list[str]],
    node_id: str,
    lines: list[str],
    *,
    level: int,
) -> None:
    prefix = "#" * min(level + 1, 6)
    if node_id in model.nodes:
        node = model.nodes[node_id]
        label = f"{node_id} ({node.type})"
        text = f": {node.text}" if node.text else ""
        importance = importance_for_node(model, node_id)
        if importance.explicit:
            text += f" [{importance.salience}, importance={importance.importance:.2f}]"
    else:
        label = node_id
        text = ""
    lines.append(f"{prefix} {label}{text}")
    for child_id in children.get(node_id, []):
        _append_outline_node(model, children, child_id, lines, level=level + 1)


def _nodes_of_types(model: LogicModel, node_ids: list[str], node_types: set[str]) -> list[str]:
    return [node_id for node_id in node_ids if node_id in model.nodes and model.nodes[node_id].type in node_types]


def _format_node_list(model: LogicModel, node_ids: list[str]) -> str:
    return "; ".join(f"{node_id}: {model.nodes[node_id].text}" for node_id in node_ids if node_id in model.nodes)


def _format_source_roles(roles: dict[str, str]) -> str:
    return "; ".join(f"{source_id}: {role}" for source_id, role in roles.items()) or "Add source roles before final prose."


def _review_lines(findings: list[object]) -> list[str]:
    if not findings:
        return ["- None identified."]
    return [f"- {finding.code}: {finding.explanation}" for finding in findings]
