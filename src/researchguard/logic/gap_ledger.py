"""Gap-ledger routing for LogicGuard diagnostics and simulations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .diagnostics import diagnose_model
from .evaluator import evaluate_model
from .importance import importance_for_node
from .model import DiagnosticFinding, DiagnosticReport, EvaluationResult, LogicModel
from .schema import STATE_IN
from .simulator import simulate_fragility


SOURCE_LIBRARY_SEARCH = "researchguard.logic.source-library:search"
SOURCE_LIBRARY_INTAKE = "researchguard.logic.source-library:intake"
ARGUMENT_REPAIR = "logicguard:argument-repair"
SIMULATION_ROUTE = "logicguard:simulation"
STRUCTURED_ARTIFACT_AUDIT = "researchguard.logic.structured-artifact:audit"
ARTIFACT_SYNTHESIS_MISSING = "researchguard.logic.artifact-synthesis:missing-addition"


@dataclass(frozen=True)
class GapItem:
    id: str
    gap_type: str
    severity: str
    affected_nodes: tuple[str, ...]
    explanation: str
    suggested_action: str
    recommended_route: str
    source_query: str = ""
    importance: float = 0.0
    salience: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "gap_type": self.gap_type,
            "severity": self.severity,
            "affected_nodes": list(self.affected_nodes),
            "explanation": self.explanation,
            "suggested_action": self.suggested_action,
            "recommended_route": self.recommended_route,
            "source_query": self.source_query,
            "importance": round(self.importance, 4),
            "salience": self.salience,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class GapLedger:
    model_id: str
    root_claim: str | None
    items: tuple[GapItem, ...]

    def route_summary(self) -> dict[str, int]:
        summary: dict[str, int] = {}
        for item in self.items:
            summary[item.recommended_route] = summary.get(item.recommended_route, 0) + 1
        return dict(sorted(summary.items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "root_claim": self.root_claim,
            "items": [item.to_dict() for item in self.items],
            "route_summary": self.route_summary(),
        }


def build_gap_ledger(
    model: LogicModel,
    *,
    result: EvaluationResult | None = None,
    diagnostics: DiagnosticReport | None = None,
    include_simulation: bool = True,
    max_simulation_items: int = 5,
) -> GapLedger:
    """Build a routeable missing-work ledger from existing LogicGuard evidence."""

    result = result or evaluate_model(model)
    diagnostics = diagnostics or diagnose_model(model, result)
    items: list[GapItem] = []

    for index, finding in enumerate(diagnostics.findings, start=1):
        items.append(_item_from_finding(model, finding, index))

    items.extend(_confidence_gaps(model, result, start_index=len(items) + 1))
    if include_simulation:
        items.extend(_fragility_gaps(model, start_index=len(items) + 1, limit=max_simulation_items))

    return GapLedger(
        model_id=model.id,
        root_claim=model.root_claim,
        items=tuple(sorted(_dedupe(items), key=_sort_key)),
    )


def _item_from_finding(model: LogicModel, finding: DiagnosticFinding, index: int) -> GapItem:
    gap_type, route = _classify_finding(finding.code)
    importance, salience = _importance_context(model, finding.affected_nodes)
    source_query = _source_query(model, finding.affected_nodes, finding.code) if route.startswith("researchguard.logic.source-library") else ""
    return GapItem(
        id=f"diagnostic-{index}-{finding.code}",
        gap_type=gap_type,
        severity=finding.severity,
        affected_nodes=tuple(finding.affected_nodes),
        explanation=finding.explanation,
        suggested_action=_route_action(route, finding.suggested_repair),
        recommended_route=route,
        source_query=source_query,
        importance=importance,
        salience=salience,
        provenance={"kind": "diagnostic", "code": finding.code, "evidence": finding.evidence},
    )


def _confidence_gaps(model: LogicModel, result: EvaluationResult, *, start_index: int) -> list[GapItem]:
    items: list[GapItem] = []
    offset = 0
    for node_id, evaluation in result.node_results.items():
        if node_id not in model.nodes:
            continue
        record = importance_for_node(model, node_id)
        if record.importance < 0.75:
            continue
        if evaluation.state == STATE_IN and evaluation.confidence >= 0.55:
            continue
        node = model.nodes[node_id]
        route = SOURCE_LIBRARY_SEARCH if node.type == "Claim" else ARGUMENT_REPAIR
        items.append(
            GapItem(
                id=f"confidence-{start_index + offset}-{node_id}",
                gap_type="confidence_gap",
                severity="warning" if evaluation.state == STATE_IN else "error",
                affected_nodes=(node_id,),
                explanation=f"Important node is {evaluation.state} with confidence {evaluation.confidence:.2f}.",
                suggested_action=_route_action(route, "Add support, narrow the claim, or make the uncertainty explicit."),
                recommended_route=route,
                source_query=_source_query(model, (node_id,), "confidence_gap") if route == SOURCE_LIBRARY_SEARCH else "",
                importance=record.importance,
                salience=record.salience,
                provenance={"kind": "evaluation", "state": evaluation.state, "confidence": evaluation.confidence},
            )
        )
        offset += 1
    return items


def _fragility_gaps(model: LogicModel, *, start_index: int, limit: int) -> list[GapItem]:
    simulation = simulate_fragility(model, root_claim=model.root_claim)
    items: list[GapItem] = []
    for offset, impact in enumerate(simulation.impacts[:limit]):
        if float(impact.get("impact_score") or 0.0) <= 0:
            continue
        node_id = str(impact.get("node_id") or "")
        if not node_id or node_id not in model.nodes:
            continue
        record = importance_for_node(model, node_id)
        node = model.nodes[node_id]
        route = SOURCE_LIBRARY_SEARCH if node.type in {"Claim", "Evidence", "Result"} else SIMULATION_ROUTE
        items.append(
            GapItem(
                id=f"fragility-{start_index + offset}-{node_id}",
                gap_type="fragility_gap",
                severity="info",
                affected_nodes=(node_id,),
                explanation=f"Perturbing {node_id} moves the root to {impact.get('result_state')}.",
                suggested_action=_route_action(route, "Add independent support or report the fragility explicitly."),
                recommended_route=route,
                source_query=_source_query(model, (node_id,), "fragility_gap") if route == SOURCE_LIBRARY_SEARCH else "",
                importance=record.importance,
                salience=record.salience,
                provenance={"kind": "simulation", "mode": "fragility", "impact": dict(impact)},
            )
        )
    return items


def _classify_finding(code: str) -> tuple[str, str]:
    if code in {"missing_warrant", "method_result_conclusion_mismatch"}:
        return "warrant_gap", ARGUMENT_REPAIR
    if code in {"unsupported_claim", "missing_baseline", "context_as_evidence_error"}:
        return "evidence_gap", SOURCE_LIBRARY_SEARCH
    if code in {"scope_mismatch", "missing_boundary_condition", "premature_generalization", "overclaiming"}:
        return "scope_gap", SOURCE_LIBRARY_SEARCH
    if code in {"unanswered_rebuttal", "undercut_warrant"}:
        return "rebuttal_gap", SOURCE_LIBRARY_SEARCH
    if code in {"hidden_assumption"}:
        return "assumption_gap", ARGUMENT_REPAIR
    if code in {"fragile_conclusion"}:
        return "fragility_gap", SIMULATION_ROUTE
    if code in {"circular_reasoning", "contradiction"}:
        return "argument_structure_gap", ARGUMENT_REPAIR
    if code in {"definition_drift", "weak_analogy"}:
        return "artifact_or_argument_gap", STRUCTURED_ARTIFACT_AUDIT
    return "logic_gap", ARTIFACT_SYNTHESIS_MISSING


def _importance_context(model: LogicModel, node_ids: list[str] | tuple[str, ...]) -> tuple[float, str]:
    records = [importance_for_node(model, node_id) for node_id in node_ids if node_id in model.nodes]
    if not records:
        return 0.0, ""
    chosen = max(records, key=lambda record: record.importance)
    return chosen.importance, chosen.salience


def _source_query(model: LogicModel, node_ids: list[str] | tuple[str, ...], code: str) -> str:
    parts = [code.replace("_", " ")]
    for node_id in node_ids:
        node = model.nodes.get(node_id)
        if not node or not node.text:
            continue
        parts.append(node.text)
    return " ".join(parts)[:400]


def _route_action(route: str, argument_repair_action: str) -> str:
    if route == SOURCE_LIBRARY_SEARCH:
        return (
            "Search existing source-library nodes first; if no suitable source exists, find candidate material, "
            "intake and model it, link it to the project claim, then re-evaluate."
        )
    if route == ARGUMENT_REPAIR:
        return argument_repair_action
    if route == SIMULATION_ROUTE:
        return "Run fragility or combination simulation, then add independent support or report the fragile dependency."
    if route == STRUCTURED_ARTIFACT_AUDIT:
        return "Run structured-artifact audit to place the missing bridge, limitation, or definition at the right block."
    if route == ARTIFACT_SYNTHESIS_MISSING:
        return "Keep this as a missing addition in synthesis until real support is supplied."
    raise ValueError(f"unsupported LogicGuard gap route: {route}")


def _dedupe(items: list[GapItem]) -> list[GapItem]:
    seen: set[tuple[str, tuple[str, ...], str]] = set()
    deduped: list[GapItem] = []
    for item in items:
        key = (item.gap_type, item.affected_nodes, item.recommended_route)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _sort_key(item: GapItem) -> tuple[int, float, str]:
    severity_rank = {"critical": 0, "error": 1, "warning": 2, "info": 3}
    return (severity_rank.get(item.severity, 4), -item.importance, item.id)
