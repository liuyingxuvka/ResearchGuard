"""Acceptance condition semantics and confidence heuristics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model import Edge, LogicModel, NodeEvaluation
from .schema import (
    ATTACK_EDGE_TYPES,
    STATE_IN,
    STATE_OUT,
    STATE_UNDECIDED,
    SUPPORT_EDGE_TYPES,
    UNDERCUT_EDGE_TYPES,
)


@dataclass
class AcceptanceDecision:
    state: str
    confidence: float
    explanation: str
    blockers: list[str] = field(default_factory=list)


def initial_node_evaluation(node_id: str, model: LogicModel) -> NodeEvaluation:
    node = model.nodes[node_id]
    forced = node.metadata.get("forced_state")
    if forced in {STATE_IN, STATE_OUT, STATE_UNDECIDED}:
        return NodeEvaluation(node_id, forced, _clip(node.confidence), f"Forced state {forced}.")

    confidence = _clip(node.confidence)
    if node.type == "Evidence":
        if node.get_bool("missing", False) or node.get("provided") is False:
            return NodeEvaluation(node_id, STATE_OUT, 0.0, "Evidence is marked missing or not provided.")
        if node.get_bool("disputed", False):
            return NodeEvaluation(node_id, STATE_UNDECIDED, confidence, "Evidence is disputed.")
        return NodeEvaluation(node_id, STATE_IN, confidence, "Evidence is provided.")
    if node.type == "Assumption":
        if node.get_bool("rejected", False):
            return NodeEvaluation(node_id, STATE_OUT, confidence, "Assumption is rejected.")
        if node.get_bool("unsupported", False) or node.get("support") == "unsupported":
            return NodeEvaluation(node_id, STATE_UNDECIDED, confidence, "Assumption is unsupported.")
        return NodeEvaluation(node_id, STATE_IN, confidence, "Assumption is declared or provisionally accepted.")
    if node.type in {"Rebuttal", "Undercutter"}:
        return NodeEvaluation(
            node_id,
            STATE_IN if node.active else STATE_OUT,
            confidence if node.active else 0.0,
            "Rebuttal/undercutter is active." if node.active else "Rebuttal/undercutter is inactive.",
        )
    if node.type == "Context":
        return NodeEvaluation(node_id, STATE_IN, confidence, "Context is available but not evidential by default.")
    if node.type in {"Premise", "Warrant", "Qualifier", "Definition", "Method", "Result", "Limitation"}:
        if node.get_bool("missing", False):
            return NodeEvaluation(node_id, STATE_OUT, 0.0, f"{node.type} is marked missing.")
        return NodeEvaluation(node_id, STATE_IN, confidence, f"{node.type} is provisionally available.")
    return NodeEvaluation(node_id, STATE_UNDECIDED, confidence, "Claim-like node awaits acceptance evaluation.")


def evaluate_acceptance(
    model: LogicModel,
    node_id: str,
    previous: dict[str, NodeEvaluation],
) -> AcceptanceDecision:
    condition = dict(model.acceptance.get(node_id) or {})
    if condition:
        return _evaluate_explicit_condition(model, node_id, previous, condition)
    return _evaluate_graph_condition(model, node_id, previous)


def _evaluate_explicit_condition(
    model: LogicModel,
    node_id: str,
    previous: dict[str, NodeEvaluation],
    condition: dict[str, Any],
) -> AcceptanceDecision:
    blockers: list[str] = []
    confidence_parts: list[float] = []
    decisive_out = False
    undecided = False
    reasons: list[str] = []

    for ref in _as_list(condition.get("all_of")):
        result = previous[ref]
        confidence_parts.append(result.confidence)
        if result.state == STATE_OUT:
            decisive_out = True
            blockers.append(ref)
            reasons.append(f"{ref} is OUT but required by all_of")
        elif result.state != STATE_IN:
            undecided = True
            blockers.append(ref)
            reasons.append(f"{ref} is {result.state} but required by all_of")

    any_refs = _as_list(condition.get("any_of"))
    if any_refs:
        in_refs = [previous[ref] for ref in any_refs if previous[ref].state == STATE_IN]
        if in_refs:
            confidence_parts.append(max(item.confidence for item in in_refs))
            reasons.append("any_of has accepted support")
        elif any(previous[ref].state == STATE_UNDECIDED for ref in any_refs):
            undecided = True
            blockers.extend(any_refs)
            reasons.append("any_of has no accepted support yet")
        else:
            decisive_out = True
            blockers.extend(any_refs)
            reasons.append("any_of candidates are all OUT")

    for ref in _as_list(condition.get("requires")):
        result = previous[ref]
        confidence_parts.append(result.confidence)
        if result.state != STATE_IN:
            undecided = True if result.state == STATE_UNDECIDED else undecided
            decisive_out = True if result.state == STATE_OUT else decisive_out
            blockers.append(ref)
            reasons.append(f"{ref} is required but {result.state}")

    for ref in _as_list(condition.get("requires_not_out")):
        result = previous[ref]
        confidence_parts.append(result.confidence)
        if result.state == STATE_OUT:
            decisive_out = True
            blockers.append(ref)
            reasons.append(f"{ref} must not be OUT")
        elif result.state == STATE_UNDECIDED:
            undecided = True
            blockers.append(ref)
            reasons.append(f"{ref} is unresolved")

    at_least = condition.get("at_least_k")
    if at_least is not None:
        k, refs = _parse_at_least_k(at_least)
        accepted = sorted(
            (previous[ref].confidence for ref in refs if previous[ref].state == STATE_IN),
            reverse=True,
        )
        if len(accepted) >= k:
            confidence_parts.append(sum(accepted[:k]) / k)
            reasons.append(f"at_least_k satisfied with {len(accepted)} accepted nodes")
        elif any(previous[ref].state == STATE_UNDECIDED for ref in refs):
            undecided = True
            blockers.extend(refs)
            reasons.append("at_least_k is unresolved")
        else:
            decisive_out = True
            blockers.extend(refs)
            reasons.append("at_least_k is not satisfied")

    for ref in _as_list(condition.get("none_of")) + _as_list(condition.get("unless")):
        result = previous[ref]
        if result.state == STATE_IN:
            decisive_out = True
            blockers.append(ref)
            reasons.append(f"{ref} is active but forbidden")

    if condition.get("no_undefeated_rebuttal", False):
        undefeated = _undefeated_rebuttals(model, node_id, previous)
        if undefeated:
            undecided = True
            blockers.extend(undefeated)
            reasons.append("active rebuttal or undercutter is not answered")

    if condition.get("scope_match", False):
        mismatches = _scope_mismatches(model, node_id)
        if mismatches:
            undecided = True
            blockers.extend(mismatches)
            reasons.append("support scope does not match claim scope")

    if condition.get("warrant_required", False) and _missing_warrant(model, node_id):
        undecided = True
        blockers.append(node_id)
        reasons.append("direct evidence support lacks a warrant")

    support_confidence = _condition_confidence(confidence_parts, condition)
    threshold = float(condition.get("threshold", 0.0) or 0.0)
    if support_confidence < threshold and not decisive_out:
        undecided = True
        reasons.append(f"support confidence {support_confidence:.2f} is below threshold {threshold:.2f}")

    support_confidence = _apply_attack_penalty(model, node_id, previous, support_confidence)
    if decisive_out:
        return AcceptanceDecision(STATE_OUT, support_confidence, "; ".join(reasons) or "Acceptance condition failed.", blockers)
    if undecided:
        return AcceptanceDecision(
            STATE_UNDECIDED,
            support_confidence,
            "; ".join(reasons) or "Acceptance condition is unresolved.",
            blockers,
        )
    return AcceptanceDecision(
        STATE_IN,
        support_confidence,
        "; ".join(reasons) or "Acceptance condition is satisfied.",
        blockers,
    )


def _evaluate_graph_condition(
    model: LogicModel,
    node_id: str,
    previous: dict[str, NodeEvaluation],
) -> AcceptanceDecision:
    node = model.nodes[node_id]
    incoming = model.incoming(node_id)
    supports = [edge for edge in incoming if edge.type in SUPPORT_EDGE_TYPES]
    attacks = [edge for edge in incoming if edge.type in ATTACK_EDGE_TYPES]
    undercuts = [edge for edge in incoming if edge.type in UNDERCUT_EDGE_TYPES]

    active_undercuts = [edge.source for edge in undercuts if previous[edge.source].state == STATE_IN]
    if active_undercuts and node.type == "Warrant":
        return AcceptanceDecision(
            STATE_UNDECIDED,
            max(0.0, node.confidence * 0.5),
            "Warrant is undercut by active undercutter.",
            active_undercuts,
        )

    active_attacks = [edge.source for edge in attacks if previous[edge.source].state == STATE_IN]
    if active_attacks:
        support_conf = _weighted_confidence(supports, previous)
        return AcceptanceDecision(
            STATE_UNDECIDED,
            max(0.0, support_conf * 0.6),
            "Active attack or contradiction prevents clean acceptance.",
            active_attacks,
        )

    if supports:
        accepted = [edge for edge in supports if previous[edge.source].state == STATE_IN]
        undecided = [edge for edge in supports if previous[edge.source].state == STATE_UNDECIDED]
        if accepted:
            return AcceptanceDecision(
                STATE_IN,
                _weighted_confidence(accepted, previous),
                "Accepted support edge(s) license this node.",
                [],
            )
        if undecided:
            return AcceptanceDecision(
                STATE_UNDECIDED,
                _weighted_confidence(undecided, previous),
                "Support edge(s) remain unresolved.",
                [edge.source for edge in undecided],
            )
        return AcceptanceDecision(STATE_OUT, 0.0, "All supporting nodes are OUT.", [edge.source for edge in supports])

    # Keep base states for non-claim nodes. Claims without support remain unresolved.
    base = previous[node_id]
    return AcceptanceDecision(base.state, base.confidence, base.explanation, list(base.blockers))


def _condition_confidence(parts: list[float], condition: dict[str, Any]) -> float:
    if not parts:
        base = 0.5
    elif "all_of" in condition or "requires" in condition or "requires_not_out" in condition:
        base = min(parts)
    else:
        base = max(parts)
    return _clip(base * float(condition.get("local_quality_factor", 1.0) or 1.0))


def _weighted_confidence(edges: list[Edge], previous: dict[str, NodeEvaluation]) -> float:
    if not edges:
        return 0.5
    total_weight = sum(max(edge.weight, 0.0) for edge in edges)
    if total_weight <= 0:
        return 0.0
    return _clip(sum(previous[edge.source].confidence * edge.weight for edge in edges) / total_weight)


def _apply_attack_penalty(
    model: LogicModel,
    node_id: str,
    previous: dict[str, NodeEvaluation],
    confidence: float,
) -> float:
    attacks = [
        edge
        for edge in model.incoming(node_id)
        if edge.type in ATTACK_EDGE_TYPES and previous[edge.source].state == STATE_IN
    ]
    if not attacks:
        return _clip(confidence)
    penalty = min(0.6, sum(edge.weight for edge in attacks) * 0.25)
    return _clip(confidence * (1.0 - penalty))


def _undefeated_rebuttals(
    model: LogicModel,
    node_id: str,
    previous: dict[str, NodeEvaluation],
) -> list[str]:
    candidates = [
        edge.source
        for edge in model.incoming(node_id)
        if edge.type in {"attacks", "undercuts", "contradicts"} and previous[edge.source].state == STATE_IN
    ]
    undefeated: list[str] = []
    for rebuttal_id in candidates:
        answered = any(
            edge.type in {"attacks", "contradicts", "undercuts"}
            and edge.target == rebuttal_id
            and previous[edge.source].state == STATE_IN
            for edge in model.edges
        )
        if not answered:
            undefeated.append(rebuttal_id)
    return undefeated


def _scope_mismatches(model: LogicModel, node_id: str) -> list[str]:
    target = model.nodes[node_id]
    mismatches: list[str] = []
    for edge in model.incoming(node_id):
        if edge.type not in SUPPORT_EDGE_TYPES:
            continue
        source = model.nodes[edge.source]
        if not scopes_compatible(source.scope, target.scope):
            mismatches.append(edge.source)
    return mismatches


def _missing_warrant(model: LogicModel, node_id: str) -> bool:
    direct_evidence = any(model.nodes[edge.source].type == "Evidence" and edge.type == "supports" for edge in model.incoming(node_id))
    if not direct_evidence:
        return False
    return not any(model.nodes[edge.source].type == "Warrant" and edge.type in SUPPORT_EDGE_TYPES for edge in model.incoming(node_id))


def scopes_compatible(source_scope: str | None, target_scope: str | None) -> bool:
    if not source_scope or not target_scope:
        return True
    source = source_scope.lower()
    target = target_scope.lower()
    if source == target or source in target or target in source:
        return True
    broad_terms = {"general", "all", "always", "universal", "any operating condition", "global"}
    narrow_markers = {"tested", "sample", "specific", "local", "simulated", "dataset", "case study"}
    if any(term in target for term in broad_terms) and any(marker in source for marker in narrow_markers):
        return False
    if "different" in source or "different" in target:
        return False
    return False


def _parse_at_least_k(value: Any) -> tuple[int, list[str]]:
    if isinstance(value, dict):
        return int(value.get("k", 1)), _as_list(value.get("nodes"))
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return int(value[0]), _as_list(value[1])
    return 1, []


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
