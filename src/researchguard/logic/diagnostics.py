"""Rule-based LogicGuard diagnostics."""

from __future__ import annotations

from collections import defaultdict
import re

from .acceptance import scopes_compatible
from .evaluator import detect_argument_cycles, evaluate_model
from .model import DiagnosticFinding, DiagnosticReport, EvaluationResult, LogicModel
from .schema import STATE_IN, STATE_UNDECIDED, SUPPORT_EDGE_TYPES


def diagnose_model(model: LogicModel, result: EvaluationResult | None = None) -> DiagnosticReport:
    result = result or evaluate_model(model)
    findings: list[DiagnosticFinding] = []
    findings.extend(_unsupported_claims(model, result))
    findings.extend(_missing_warrants(model))
    findings.extend(_hidden_assumptions(model))
    findings.extend(_overclaiming(model, result))
    findings.extend(_scope_mismatches(model))
    findings.extend(_context_as_evidence(model))
    findings.extend(_unanswered_rebuttals(model, result))
    findings.extend(_undercut_warrants(model, result))
    findings.extend(_circular_reasoning(model, result))
    findings.extend(_contradictions(model, result))
    findings.extend(_causal_overclaims(model))
    findings.extend(_missing_baselines(model))
    findings.extend(_missing_boundary_conditions(model))
    findings.extend(_method_result_conclusion_mismatch(model))
    findings.extend(_fragile_conclusions(model, result))
    findings.extend(_weak_analogies(model))
    findings.extend(_definition_drift(model))
    findings.extend(_premature_generalization(model))
    return DiagnosticReport(model_id=model.id, findings=_dedupe_findings(findings))


def _unsupported_claims(model: LogicModel, result: EvaluationResult) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for node_id, node in model.nodes.items():
        if node.type != "Claim":
            continue
        incoming_supports = [edge for edge in model.incoming(node_id) if edge.type in SUPPORT_EDGE_TYPES]
        has_acceptance = node_id in model.acceptance
        evaluation = result.node_results.get(node_id)
        if not incoming_supports and not has_acceptance:
            findings.append(
                DiagnosticFinding(
                    "unsupported_claim",
                    "error",
                    [node_id],
                    "Claim has no declared support edges and no acceptance condition.",
                    "A conclusion is not structurally licensed unless the model declares why it follows.",
                    "Add premises, evidence, warrants, assumptions, or an explicit acceptance condition.",
                    _weaken_claim_text(node.text),
                )
            )
        elif evaluation and evaluation.state != STATE_IN and "required" in evaluation.explanation.lower():
            findings.append(
                DiagnosticFinding(
                    "unsupported_claim",
                    "warning",
                    [node_id] + evaluation.blockers,
                    f"Claim is {evaluation.state}: {evaluation.explanation}",
                    "A blocked dependency prevents the claim from being accepted in the current model.",
                    "Resolve the blocked dependency, add missing support, or weaken the claim.",
                    _weaken_claim_text(node.text),
                )
            )
    return findings


def _missing_warrants(model: LogicModel) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for edge in model.edges:
        if edge.type != "supports":
            continue
        source = model.nodes[edge.source]
        target = model.nodes[edge.target]
        if source.type != "Evidence" or target.type != "Claim":
            continue
        has_warrant = any(model.nodes[in_edge.source].type == "Warrant" for in_edge in model.incoming(edge.target))
        if not has_warrant:
            findings.append(
                DiagnosticFinding(
                    "missing_warrant",
                    "error",
                    [edge.source, edge.target],
                    "Evidence directly supports a non-trivial claim without a declared warrant.",
                    "The model needs an explicit bridge explaining why the evidence licenses the claim.",
                    "Add a Warrant node connecting the evidence or premise to the claim.",
                    _weaken_claim_text(target.text),
                    {"edge": edge.to_dict()},
                )
            )
    return findings


def _hidden_assumptions(model: LogicModel) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for node_id, node in model.nodes.items():
        if node.type != "Assumption":
            continue
        hidden = node.get_bool("hidden", False) or node.get("status") == "hidden" or node.get("declared") is False
        unsupported = node.get_bool("unsupported", False) or node.get("support") == "unsupported"
        if hidden or unsupported:
            findings.append(
                DiagnosticFinding(
                    "hidden_assumption",
                    "warning",
                    [node_id],
                    "Assumption is hidden, undeclared, or unsupported.",
                    "High-impact hidden assumptions can make a conclusion appear stronger than the model permits.",
                    "State the assumption explicitly and add support, qualification, or a sensitivity check.",
                )
            )
    return findings


def _overclaiming(model: LogicModel, result: EvaluationResult) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for node_id, node in model.nodes.items():
        if node.type != "Claim":
            continue
        evaluation = result.node_results.get(node_id)
        text = node.text.lower()
        strong = _has_any(text, ("prove", "proves", "always", "guarantee", "all ", "definitive", "must ", "causes", "causal"))
        if strong and (not evaluation or evaluation.confidence < 0.75 or evaluation.state != STATE_IN):
            findings.append(
                DiagnosticFinding(
                    "overclaiming",
                    "warning",
                    [node_id],
                    "Claim wording is stronger than the current support structure warrants.",
                    "Overclaiming can turn a structurally plausible argument into an unsupported conclusion.",
                    "Add stronger support and rebuttal handling, or reduce the claim strength.",
                    _weaken_claim_text(node.text),
                    {"state": evaluation.state if evaluation else None, "confidence": evaluation.confidence if evaluation else None},
                )
            )
    return findings


def _scope_mismatches(model: LogicModel) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for edge in model.edges:
        if edge.type not in SUPPORT_EDGE_TYPES:
            continue
        source = model.nodes[edge.source]
        target = model.nodes[edge.target]
        if not scopes_compatible(source.scope, target.scope):
            findings.append(
                DiagnosticFinding(
                    "scope_mismatch",
                    "error",
                    [edge.source, edge.target],
                    f"Support scope {source.scope!r} does not match claim scope {target.scope!r}.",
                    "Evidence only licenses conclusions within compatible boundary conditions.",
                    "Add a qualifier, narrow the claim scope, or add evidence for the broader scope.",
                    _scope_rewrite(target.text, source.scope),
                    {"edge": edge.to_dict()},
                )
            )
    return findings


def _context_as_evidence(model: LogicModel) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for edge in model.edges:
        if edge.type == "supports" and model.nodes[edge.source].type == "Context":
            findings.append(
                DiagnosticFinding(
                    "context_as_evidence_error",
                    "warning",
                    [edge.source, edge.target],
                    "A Context node is used as direct evidence.",
                    "Background can frame a claim, but it does not automatically establish the claim.",
                    "Change the edge to contextualizes or add an Evidence node plus a Warrant.",
                )
            )
    return findings


def _unanswered_rebuttals(model: LogicModel, result: EvaluationResult) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for node_id, node in model.nodes.items():
        if node.type not in {"Rebuttal", "Undercutter"}:
            continue
        evaluation = result.node_results.get(node_id)
        if not evaluation or evaluation.state != STATE_IN:
            continue
        targets = [edge.target for edge in model.outgoing(node_id) if edge.type in {"attacks", "undercuts", "contradicts"}]
        if not targets:
            continue
        answered = any(
            edge.target == node_id
            and edge.type in {"attacks", "undercuts", "contradicts"}
            and result.node_results.get(edge.source)
            and result.node_results[edge.source].state == STATE_IN
            for edge in model.edges
        )
        if not answered:
            findings.append(
                DiagnosticFinding(
                    "unanswered_rebuttal",
                    "error",
                    [node_id] + targets,
                    "An active rebuttal or undercutter is not answered by the argument structure.",
                    "A live objection can block a claim even when supporting evidence exists.",
                    "Add a response, qualifier, limitation, or weaker conclusion that acknowledges the objection.",
                )
            )
    return findings


def _undercut_warrants(model: LogicModel, result: EvaluationResult) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for edge in model.edges:
        if edge.type != "undercuts":
            continue
        source_eval = result.node_results.get(edge.source)
        target = model.nodes.get(edge.target)
        if source_eval and source_eval.state == STATE_IN and target and target.type == "Warrant":
            findings.append(
                DiagnosticFinding(
                    "undercut_warrant",
                    "error",
                    [edge.source, edge.target],
                    "An active undercutter attacks the warrant that bridges support to conclusion.",
                    "Undercuts should make the downstream claim unresolved until the bridge is repaired.",
                    "Defend the warrant, narrow the claim, or add a stronger warrant that survives the undercutter.",
                )
            )
    return findings


def _circular_reasoning(model: LogicModel, result: EvaluationResult) -> list[DiagnosticFinding]:
    cycles = result.cycles or detect_argument_cycles(model)
    return [
        DiagnosticFinding(
            "circular_reasoning",
            "error",
            cycle,
            "Support/dependency path loops back to its own starting claim.",
            "Circular support cannot independently license a conclusion.",
            "Break the cycle by adding an external premise, evidence node, or independent warrant.",
            evidence={"cycle": cycle},
        )
        for cycle in cycles
    ]


def _contradictions(model: LogicModel, result: EvaluationResult) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for edge in model.edges:
        if edge.type == "contradicts":
            source = result.node_results.get(edge.source)
            target = result.node_results.get(edge.target)
            if source and target and source.state == STATE_IN and target.state == STATE_IN:
                findings.append(
                    DiagnosticFinding(
                        "contradiction",
                        "critical",
                        [edge.source, edge.target],
                        "Contradictory nodes are both accepted.",
                        "A model that accepts both sides of a contradiction cannot license a stable conclusion.",
                        "Resolve the contradiction, qualify one side, or mark the conflict as unresolved.",
                    )
                )
    return findings


def _causal_overclaims(model: LogicModel) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for node_id, node in model.nodes.items():
        if node.type != "Claim":
            continue
        if not _has_any(node.text.lower(), ("cause", "causes", "caused", "because", "drives", "leads to")):
            continue
        incoming_evidence = [edge for edge in model.incoming(node_id) if model.nodes[edge.source].type == "Evidence"]
        if not incoming_evidence:
            continue
        has_causal_warrant = any(
            model.nodes[edge.source].type == "Warrant"
            and _has_any(model.nodes[edge.source].text.lower(), ("causal", "mechanism", "intervention", "identification"))
            for edge in model.incoming(node_id)
        )
        evidence_is_correlation = any(
            model.nodes[edge.source].get("evidence_kind") == "correlation"
            or "correlation" in model.nodes[edge.source].text.lower()
            or "associated" in model.nodes[edge.source].text.lower()
            for edge in incoming_evidence
        )
        if evidence_is_correlation and not has_causal_warrant:
            findings.append(
                DiagnosticFinding(
                    "causal_overclaim",
                    "error",
                    [node_id] + [edge.source for edge in incoming_evidence],
                    "A causal claim is supported only by correlation-style evidence.",
                    "Correlation can be consistent with causation but does not by itself license causal wording.",
                    "Add a causal identification warrant or rewrite the claim as association/consistency.",
                    _weaken_claim_text(node.text),
                )
            )
    return findings


def _missing_baselines(model: LogicModel) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    comparative_terms = ("improve", "improves", "better", "higher", "lower", "reduced", "more efficient", "outperform")
    for node_id, node in model.nodes.items():
        if node.type != "Claim" or not _has_any(node.text.lower(), comparative_terms):
            continue
        related_text = " ".join(model.nodes[edge.source].text.lower() for edge in model.incoming(node_id))
        if not _has_any(related_text, ("baseline", "control", "comparison", "same", "reference")):
            findings.append(
                DiagnosticFinding(
                    "missing_baseline",
                    "warning",
                    [node_id],
                    "Comparative claim does not declare a baseline or control comparison.",
                    "A comparison is structurally incomplete without the reference being compared against.",
                    "Add baseline evidence or rewrite the claim as a non-comparative observation.",
                    _scope_rewrite(node.text, node.scope),
                )
            )
    return findings


def _missing_boundary_conditions(model: LogicModel) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for node_id, node in model.nodes.items():
        if node.type != "Claim":
            continue
        has_qualifier = any(model.nodes[edge.source].type in {"Qualifier", "Limitation"} for edge in model.incoming(node_id))
        if not node.scope and not has_qualifier and _has_any(node.text.lower(), ("improve", "causes", "always", "guarantee", "effective")):
            findings.append(
                DiagnosticFinding(
                    "missing_boundary_condition",
                    "warning",
                    [node_id],
                    "Claim lacks scope or qualifying boundary conditions.",
                    "Engineering and scientific claims are usually licensed only under stated operating ranges.",
                    "Add a Qualifier or Limitation node and narrow the claim wording.",
                    _scope_rewrite(node.text, "the tested conditions"),
                )
            )
    return findings


def _method_result_conclusion_mismatch(model: LogicModel) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for edge in model.edges:
        if edge.type != "supports":
            continue
        source = model.nodes[edge.source]
        target = model.nodes[edge.target]
        if source.type in {"Method", "Result"} and target.type == "Claim":
            has_warrant = any(model.nodes[in_edge.source].type == "Warrant" for in_edge in model.incoming(edge.target))
            if not has_warrant:
                findings.append(
                    DiagnosticFinding(
                        "method_result_conclusion_mismatch",
                        "warning",
                        [edge.source, edge.target],
                        "Method/result node is connected to a conclusion without an explicit warrant.",
                        "A result describes what happened; a warrant explains what conclusion it licenses.",
                        "Add a warrant that links the method/result to the conclusion and states its limitations.",
                    )
                )
    return findings


def _fragile_conclusions(model: LogicModel, result: EvaluationResult) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for node_id, node in model.nodes.items():
        if node.type != "Claim":
            continue
        incoming_supports = [edge for edge in model.incoming(node_id) if edge.type in SUPPORT_EDGE_TYPES]
        evaluation = result.node_results.get(node_id)
        if len(incoming_supports) == 1 and evaluation and evaluation.state == STATE_IN:
            findings.append(
                DiagnosticFinding(
                    "fragile_conclusion",
                    "info",
                    [node_id, incoming_supports[0].source],
                    "Claim depends on a single accepted support path.",
                    "Single-path conclusions are sensitive to evidence weakening or premise removal.",
                    "Add independent support, make the claim more local, or report fragility explicitly.",
                    _weaken_claim_text(node.text),
                )
            )
        elif evaluation and evaluation.state == STATE_IN and evaluation.confidence < 0.55:
            findings.append(
                DiagnosticFinding(
                    "fragile_conclusion",
                    "warning",
                    [node_id],
                    "Claim is accepted with low confidence.",
                    "The structure currently licenses the claim, but a small perturbation may collapse it.",
                    "Add stronger support or weaken the conclusion.",
                    _weaken_claim_text(node.text),
                )
            )
    return findings


def _weak_analogies(model: LogicModel) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for node_id, node in model.nodes.items():
        text = node.text.lower()
        if node.get("reasoning_type") == "analogy" or _has_any(text, ("analogous", "similar to", "like ")):
            has_similarity_warrant = any(
                model.nodes[edge.source].type == "Warrant"
                and _has_any(model.nodes[edge.source].text.lower(), ("similarity", "shared mechanism", "relevant similarity"))
                for edge in model.incoming(node_id)
            )
            if not has_similarity_warrant:
                findings.append(
                    DiagnosticFinding(
                        "weak_analogy",
                        "warning",
                        [node_id],
                        "Analogy-style reasoning lacks a warrant for relevant similarity.",
                        "Analogies only support conclusions when the relevant shared structure is explicit.",
                        "Add a similarity warrant or narrow the analogy to an illustrative context.",
                    )
                )
    return findings


def _definition_drift(model: LogicModel) -> list[DiagnosticFinding]:
    by_term: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for node_id, node in model.nodes.items():
        if node.type != "Definition":
            continue
        term = str(node.get("term", "") or node.text.split(":", 1)[0]).strip().lower()
        if term:
            by_term[term].append((node_id, node.text.strip()))
    findings: list[DiagnosticFinding] = []
    for term, entries in by_term.items():
        definitions = {text for _, text in entries}
        if len(entries) > 1 and len(definitions) > 1:
            findings.append(
                DiagnosticFinding(
                    "definition_drift",
                    "warning",
                    [node_id for node_id, _ in entries],
                    f"Term {term!r} has multiple non-identical definitions.",
                    "Definition drift can make later claims appear supported under a changed meaning.",
                    "Consolidate the definition or qualify which definition applies in each section.",
                )
            )
    return findings


def _premature_generalization(model: LogicModel) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    broad_terms = ("all ", "always", "general", "any ", "universally")
    for node_id, node in model.nodes.items():
        if node.type != "Claim" or not _has_any(node.text.lower(), broad_terms):
            continue
        narrow_sources = [
            edge.source
            for edge in model.incoming(node_id)
            if model.nodes[edge.source].scope and not scopes_compatible(model.nodes[edge.source].scope, node.scope or "general")
        ]
        if narrow_sources:
            findings.append(
                DiagnosticFinding(
                    "premature_generalization",
                    "error",
                    [node_id] + narrow_sources,
                    "Local or narrow evidence is used to support a broad/general claim.",
                    "A local result does not automatically license a global conclusion.",
                    "Narrow the conclusion to the tested scope or add broader evidence.",
                    _scope_rewrite(node.text, model.nodes[narrow_sources[0]].scope),
                )
            )
    return findings


def _dedupe_findings(findings: list[DiagnosticFinding]) -> list[DiagnosticFinding]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    result: list[DiagnosticFinding] = []
    for finding in findings:
        key = (finding.code, tuple(finding.affected_nodes))
        if key not in seen:
            seen.add(key)
            result.append(finding)
    severity_order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
    return sorted(result, key=lambda item: (severity_order.get(item.severity, 9), item.code))


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _weaken_claim_text(text: str) -> str:
    if not text:
        return "State a narrower claim tied to the model's declared support."
    replacements = {
        "proves": "suggests",
        "prove": "suggest",
        "causes": "is consistent with",
        "cause": "is consistent with",
        "always": "under the stated conditions",
        "guarantees": "is consistent with",
        "guarantee": "is consistent with",
        "must": "may",
        "significantly improves": "shows potential improvement in",
        "improves": "is consistent with improvement in",
    }
    rewritten = text
    for strong, weak in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        rewritten = re.sub(rf"\b{re.escape(strong)}\b", weak, rewritten, flags=re.IGNORECASE)
    if rewritten == text:
        rewritten = f"The current evidence supports a narrower version of: {text}"
    return rewritten


def _scope_rewrite(text: str, scope: str | None) -> str:
    scope_text = scope or "the stated boundary conditions"
    if not text:
        return f"Limit the claim to {scope_text}."
    return f"{text.rstrip('.')} under {scope_text}."
