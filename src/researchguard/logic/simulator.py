"""What-if simulation, counterexample search, and fragility analysis."""

from __future__ import annotations

import copy
from itertools import combinations
from collections import deque
from typing import Any

from .evaluator import evaluate_model
from .model import EvaluationResult, LogicModel, SimulationResult
from .schema import STATE_IN, SUPPORT_EDGE_TYPES


def simulate_model(
    model: LogicModel,
    *,
    root_claim: str | None = None,
    mode: str = "fragility",
    node_id: str | None = None,
    confidence: float | None = None,
    max_size: int = 2,
) -> SimulationResult:
    root_claim = root_claim or model.root_claim
    if mode == "fragility":
        return simulate_fragility(model, root_claim=root_claim)
    if mode == "counterexample":
        return search_counterexamples(model, root_claim=root_claim)
    if mode == "combination-counterexample":
        return search_combination_counterexamples(model, root_claim=root_claim, max_size=max_size)
    if mode == "premise-removal":
        if not node_id:
            node_id = _first_node_of_type(model, "Premise")
        return _single_node_perturbation(model, root_claim, node_id, "premise_removed", forced_state="OUT")
    if mode == "evidence-weakening":
        if not node_id:
            node_id = _first_node_of_type(model, "Evidence")
        return _single_node_perturbation(
            model,
            root_claim,
            node_id,
            "evidence_weakened",
            confidence=0.1 if confidence is None else confidence,
        )
    if mode == "rebuttal-activation":
        if not node_id:
            node_id = _first_node_of_type(model, "Rebuttal")
        return _single_node_perturbation(model, root_claim, node_id, "rebuttal_activated", active=True)
    if mode == "assumption-flip":
        if not node_id:
            node_id = _first_node_of_type(model, "Assumption")
        return _single_node_perturbation(model, root_claim, node_id, "assumption_flipped", forced_state="OUT")
    if mode == "scope-narrowing":
        if not node_id:
            node_id = root_claim
        return _single_node_perturbation(
            model,
            root_claim,
            node_id,
            "scope_narrowed",
            scope="narrow tested conditions",
        )
    if mode == "dependency-trace":
        baseline = evaluate_model(model)
        root = baseline.root()
        return SimulationResult(
            mode="dependency-trace",
            root_claim=root_claim,
            baseline_state=root.state if root else None,
            baseline_confidence=root.confidence if root else None,
            impacts=dependency_trace(model, root_claim=root_claim),
            explanation="Dependency trace follows incoming support, dependency, attack, and undercut paths.",
        )
    if mode == "repair":
        return repair_simulation(model, root_claim=root_claim)
    raise ValueError(f"Unsupported simulation mode: {mode}")


def simulate_fragility(model: LogicModel, *, root_claim: str | None = None) -> SimulationResult:
    root_claim = root_claim or model.root_claim
    baseline = evaluate_model(model)
    root = baseline.node_results.get(root_claim) if root_claim else baseline.root()
    impacts: list[dict[str, Any]] = []
    if not root_claim or root is None:
        return SimulationResult("fragility", root_claim, None, None, explanation="No root claim available.")

    candidates = _dependency_nodes(model, root_claim)
    for candidate in candidates:
        node = model.nodes[candidate]
        variant = copy.deepcopy(model)
        if node.type == "Evidence":
            variant.nodes[candidate].confidence = 0.0
            variant.nodes[candidate].metadata["provided"] = False
        elif node.type in {"Rebuttal", "Undercutter"}:
            variant.nodes[candidate].active = True
        else:
            variant.nodes[candidate].metadata["forced_state"] = "OUT"
            variant.nodes[candidate].confidence = 0.0
        variant_result = evaluate_model(variant)
        variant_root = variant_result.node_results[root_claim]
        state_impact = 1.0 if root.state == STATE_IN and variant_root.state != STATE_IN else 0.0
        confidence_drop = max(0.0, root.confidence - variant_root.confidence)
        impact_score = round(state_impact + confidence_drop, 4)
        impacts.append(
            {
                "node_id": candidate,
                "node_type": node.type,
                "baseline_state": root.state,
                "result_state": variant_root.state,
                "baseline_confidence": round(root.confidence, 4),
                "result_confidence": round(variant_root.confidence, 4),
                "impact_score": impact_score,
                "reason": f"Perturbing {candidate} changes root to {variant_root.state}.",
            }
        )
    impacts.sort(key=lambda item: item["impact_score"], reverse=True)
    return SimulationResult(
        mode="fragility",
        root_claim=root_claim,
        baseline_state=root.state,
        baseline_confidence=root.confidence,
        impacts=impacts,
        explanation="Nodes are ranked by root-state collapse and confidence drop after deterministic perturbation.",
    )


def search_counterexamples(model: LogicModel, *, root_claim: str | None = None) -> SimulationResult:
    root_claim = root_claim or model.root_claim
    baseline = evaluate_model(model)
    root = baseline.node_results.get(root_claim) if root_claim else baseline.root()
    if not root_claim or root is None:
        return SimulationResult("counterexample", root_claim, None, None, explanation="No root claim available.")

    candidates = _dependency_nodes(model, root_claim)
    impacts: list[dict[str, Any]] = []
    for candidate in candidates:
        node = model.nodes[candidate]
        variant = copy.deepcopy(model)
        if node.type == "Evidence":
            variant.nodes[candidate].metadata["provided"] = False
            variant.nodes[candidate].confidence = 0.0
            action = "remove evidence"
        elif node.type in {"Rebuttal", "Undercutter"}:
            variant.nodes[candidate].active = True
            action = "activate rebuttal"
        else:
            variant.nodes[candidate].metadata["forced_state"] = "OUT"
            variant.nodes[candidate].confidence = 0.0
            action = "force node OUT"
        variant_result = evaluate_model(variant)
        variant_root = variant_result.node_results[root_claim]
        if variant_root.state != STATE_IN or variant_root.confidence < root.confidence:
            impacts.append(
                {
                    "minimal_conditions": [candidate],
                    "action": action,
                    "result_state": variant_root.state,
                    "result_confidence": round(variant_root.confidence, 4),
                    "explanation": f"If {candidate} is weakened or rejected, root claim becomes {variant_root.state}.",
                }
            )
        if variant_root.state != STATE_IN:
            break
    chosen = impacts[0] if impacts else {}
    return SimulationResult(
        mode="counterexample",
        root_claim=root_claim,
        baseline_state=root.state,
        baseline_confidence=root.confidence,
        result_state=chosen.get("result_state"),
        result_confidence=chosen.get("result_confidence"),
        perturbation=chosen,
        impacts=impacts,
        explanation="Counterexamples are minimal single-node perturbations found by deterministic search.",
    )


def search_combination_counterexamples(
    model: LogicModel,
    *,
    root_claim: str | None = None,
    max_size: int = 2,
    limit: int = 10,
) -> SimulationResult:
    root_claim = root_claim or model.root_claim
    baseline = evaluate_model(model)
    root = baseline.node_results.get(root_claim) if root_claim else baseline.root()
    if not root_claim or root is None:
        return SimulationResult("combination-counterexample", root_claim, None, None, explanation="No root claim available.")

    candidates = _dependency_nodes(model, root_claim)
    max_size = max(2, min(max_size, len(candidates)))
    impacts: list[dict[str, Any]] = []
    for size in range(2, max_size + 1):
        for combo in combinations(candidates, size):
            variant = copy.deepcopy(model)
            actions = [apply_default_perturbation(variant, node_id) for node_id in combo]
            variant_result = evaluate_model(variant)
            variant_root = variant_result.node_results[root_claim]
            confidence_drop = max(0.0, root.confidence - variant_root.confidence)
            state_impact = 1.0 if root.state == STATE_IN and variant_root.state != STATE_IN else 0.0
            if root.state != variant_root.state and state_impact == 0.0:
                state_impact = 0.5
            if state_impact <= 0.0 and confidence_drop <= 0.0:
                continue
            impacts.append(
                {
                    "minimal_conditions": list(combo),
                    "actions": actions,
                    "result_state": variant_root.state,
                    "result_confidence": round(variant_root.confidence, 4),
                    "impact_score": round(state_impact + confidence_drop, 4),
                    "explanation": f"If {', '.join(combo)} are perturbed together, root claim becomes {variant_root.state}.",
                }
            )
    impacts.sort(key=lambda item: (float(item["impact_score"]), -len(item["minimal_conditions"])), reverse=True)
    impacts = impacts[:limit]
    chosen = impacts[0] if impacts else {}
    return SimulationResult(
        mode="combination-counterexample",
        root_claim=root_claim,
        baseline_state=root.state,
        baseline_confidence=root.confidence,
        result_state=chosen.get("result_state"),
        result_confidence=chosen.get("result_confidence"),
        perturbation=chosen,
        impacts=impacts,
        explanation="Combination counterexamples are bounded multi-node perturbations over dependency paths.",
    )


def dependency_trace(model: LogicModel, *, root_claim: str | None = None) -> list[dict[str, Any]]:
    root_claim = root_claim or model.root_claim
    if not root_claim:
        return []
    rows: list[dict[str, Any]] = []
    queue = deque([(root_claim, [root_claim])])
    seen_paths: set[tuple[str, ...]] = set()
    while queue:
        current, path = queue.popleft()
        for edge in model.incoming(current):
            if edge.source in path:
                rows.append(
                    {
                        "path": [edge.source] + path,
                        "edge_type": edge.type,
                        "status": "cycle",
                        "explanation": "Dependency path loops back on itself.",
                    }
                )
                continue
            new_path = [edge.source] + path
            key = tuple(new_path)
            if key in seen_paths:
                continue
            seen_paths.add(key)
            rows.append(
                {
                    "path": new_path,
                    "edge_type": edge.type,
                    "weight": edge.weight,
                    "explanation": edge.explanation,
                }
            )
            if edge.type in SUPPORT_EDGE_TYPES or edge.type in {"attacks", "undercuts", "contradicts"}:
                queue.append((edge.source, new_path))
    return rows


def repair_simulation(model: LogicModel, *, root_claim: str | None = None) -> SimulationResult:
    root_claim = root_claim or model.root_claim
    baseline = evaluate_model(model)
    root = baseline.node_results.get(root_claim) if root_claim else baseline.root()
    impacts: list[dict[str, Any]] = []
    if not root_claim or root is None:
        return SimulationResult("repair", root_claim, None, None, explanation="No root claim available.")

    missing_warrant_targets = []
    for edge in model.edges:
        if edge.type == "supports" and model.nodes[edge.source].type == "Evidence" and model.nodes[edge.target].type == "Claim":
            has_warrant = any(model.nodes[in_edge.source].type == "Warrant" for in_edge in model.incoming(edge.target))
            if not has_warrant:
                missing_warrant_targets.append(edge.target)
    for target in sorted(set(missing_warrant_targets)):
        impacts.append(
            {
                "repair": "add_warrant",
                "target": target,
                "expected_effect": "May change missing-warrant and unsupported-claim diagnostics into accepted or better-qualified support.",
            }
        )
    for node_id, node in model.nodes.items():
        if node.type == "Claim" and not node.scope:
            impacts.append(
                {
                    "repair": "add_qualifier",
                    "target": node_id,
                    "expected_effect": "Narrows the claim so evidence scope can match the conclusion.",
                }
            )
    for node_id, node in model.nodes.items():
        if node.type in {"Rebuttal", "Undercutter"} and node.active:
            impacts.append(
                {
                    "repair": "respond_to_rebuttal",
                    "target": node_id,
                    "expected_effect": "Moves an unanswered objection into a resolved or explicitly limited branch.",
                }
            )
    return SimulationResult(
        mode="repair",
        root_claim=root_claim,
        baseline_state=root.state,
        baseline_confidence=root.confidence,
        impacts=impacts,
        explanation="Repair simulation lists model-grounded edits; add the proposed nodes/edges and re-evaluate to confirm.",
    )


def _single_node_perturbation(
    model: LogicModel,
    root_claim: str | None,
    node_id: str | None,
    label: str,
    **changes: Any,
) -> SimulationResult:
    baseline = evaluate_model(model)
    root = baseline.node_results.get(root_claim) if root_claim else baseline.root()
    if not root_claim or root is None or not node_id or node_id not in model.nodes:
        return SimulationResult(label, root_claim, None, None, explanation="Required root or target node is missing.")
    variant = copy.deepcopy(model)
    _apply_node_changes(variant, node_id, **changes)
    variant_result = evaluate_model(variant)
    variant_root = variant_result.node_results[root_claim]
    return SimulationResult(
        mode=label,
        root_claim=root_claim,
        baseline_state=root.state,
        baseline_confidence=root.confidence,
        result_state=variant_root.state,
        result_confidence=variant_root.confidence,
        perturbation={"node_id": node_id, **changes},
        explanation=f"After {label} on {node_id}, root claim is {variant_root.state}.",
    )


def apply_default_perturbation(model: LogicModel, node_id: str) -> dict[str, Any]:
    """Apply the deterministic default perturbation for one model node."""

    node = model.nodes[node_id]
    if node.type == "Evidence":
        _apply_node_changes(model, node_id, provided=False, confidence=0.0)
        return {"node_id": node_id, "action": "remove evidence"}
    if node.type in {"Rebuttal", "Undercutter"}:
        _apply_node_changes(model, node_id, active=True)
        return {"node_id": node_id, "action": "activate rebuttal"}
    _apply_node_changes(model, node_id, forced_state="OUT", confidence=0.0)
    return {"node_id": node_id, "action": "force node OUT"}

def _apply_node_changes(model: LogicModel, node_id: str, **changes: Any) -> None:
    node = model.nodes[node_id]
    for key, value in changes.items():
        if key == "forced_state":
            node.metadata["forced_state"] = value
        elif hasattr(node, key):
            setattr(node, key, value)
        else:
            node.metadata[key] = value


def _dependency_nodes(model: LogicModel, root_claim: str) -> list[str]:
    found: list[str] = []
    queue = deque([root_claim])
    seen = {root_claim}
    while queue:
        current = queue.popleft()
        for edge in model.incoming(current):
            if edge.source not in seen:
                seen.add(edge.source)
                found.append(edge.source)
                queue.append(edge.source)
    return found


def _first_node_of_type(model: LogicModel, node_type: str) -> str | None:
    for node_id, node in model.nodes.items():
        if node.type == node_type:
            return node_id
    return None
