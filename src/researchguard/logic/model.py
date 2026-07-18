"""Data structures for LogicGuard H-WADF models and outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .schema import SCHEMA_VERSION, STATE_UNDECIDED


_TRANSIENT_NODE_KEYS = {
    "forced_state",
    "evaluated_state",
    "evaluation_state",
    "runtime_state",
}


def _serialize_value(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize_value(item) for item in value]
    return value


@dataclass
class Node:
    id: str
    type: str
    text: str = ""
    level: str = ""
    scope: str | None = None
    state: str = STATE_UNDECIDED
    confidence: float = 0.5
    active: bool = False
    impact: str | None = None
    importance: float | None = None
    salience: str | None = None
    role: str | None = None
    importance_reason: str | None = None
    parent: str | None = None
    children: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: list[Any] = field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        return self.metadata.get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes", "y", "active", "declared"}
        return bool(value)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "text": self.text,
            "level": self.level,
            "scope": self.scope,
            "state": self.state,
            "confidence": self.confidence,
            "active": self.active,
            "impact": self.impact,
            "importance": self.importance,
            "salience": self.salience,
            "role": self.role,
            "importance_reason": self.importance_reason,
            "parent": self.parent,
            "children": list(self.children),
            "provenance": [_serialize_value(item) for item in self.provenance],
        }
        data.update(self.metadata)
        return {key: value for key, value in data.items() if value not in (None, "", [], {})}

    def canonical_dict(self) -> dict[str, Any]:
        """Return durable semantic content without transient evaluation output."""

        data = self.to_dict()
        data.pop("state", None)
        for key in _TRANSIENT_NODE_KEYS:
            data.pop(key, None)
        return data


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    type: str
    weight: float = 1.0
    explanation: str = ""
    importance: float | None = None
    salience: str | None = None
    importance_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "type": self.type,
            "weight": self.weight,
            "explanation": self.explanation,
            "importance": self.importance,
            "salience": self.salience,
            "importance_reason": self.importance_reason,
        }
        data.update(self.metadata)
        return {key: value for key, value in data.items() if value not in (None, "", [], {})}

    def canonical_dict(self) -> dict[str, Any]:
        return self.to_dict()


@dataclass
class ArgumentBlock:
    id: str
    title: str = ""
    level: str = ""
    parent: str | None = None
    input_nodes: list[str] = field(default_factory=list)
    internal_nodes: list[str] = field(default_factory=list)
    output_claims: list[str] = field(default_factory=list)
    local_assumptions: list[str] = field(default_factory=list)
    local_rebuttals: list[str] = field(default_factory=list)
    acceptance_conditions: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)
    child_blocks: list[str] = field(default_factory=list)
    root_claim: str | None = None
    member_nodes: list[str] = field(default_factory=list)
    input_classifications: dict[str, str] = field(default_factory=dict)
    output_classifications: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: list[Any] = field(default_factory=list)

    def member_node_ids(self) -> tuple[str, ...]:
        """Return the one complete, stable block membership projection."""

        values = [
            *self.member_nodes,
            *self.input_nodes,
            *self.internal_nodes,
            *self.output_claims,
            *self.local_assumptions,
            *self.local_rebuttals,
        ]
        if self.root_claim:
            values.append(self.root_claim)
        return tuple(dict.fromkeys(str(value) for value in values if value))

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "title": self.title,
            "level": self.level,
            "parent": self.parent,
            "input_nodes": list(self.input_nodes),
            "internal_nodes": list(self.internal_nodes),
            "output_claims": list(self.output_claims),
            "local_assumptions": list(self.local_assumptions),
            "local_rebuttals": list(self.local_rebuttals),
            "acceptance_conditions": self.acceptance_conditions,
            "diagnostics": list(self.diagnostics),
            "child_blocks": list(self.child_blocks),
            "root_claim": self.root_claim,
            "member_nodes": list(self.member_node_ids()),
            "input_classifications": dict(self.input_classifications),
            "output_classifications": dict(self.output_classifications),
            "provenance": [_serialize_value(item) for item in self.provenance],
        }
        data.update(self.metadata)
        return {key: value for key, value in data.items() if value not in (None, "", [], {})}


@dataclass
class LogicModel:
    id: str
    title: str = ""
    root_claim: str | None = None
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    acceptance: dict[str, dict[str, Any]] = field(default_factory=dict)
    hierarchy: dict[str, list[str]] = field(default_factory=dict)
    blocks: dict[str, ArgumentBlock] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION
    _incoming_index: dict[str, list[Edge]] = field(default_factory=dict, init=False, repr=False)
    _outgoing_index: dict[str, list[Edge]] = field(default_factory=dict, init=False, repr=False)
    _edge_index_token: tuple[int, int] | None = field(default=None, init=False, repr=False)

    def node(self, node_id: str) -> Node:
        return self.nodes[node_id]

    def incoming(self, node_id: str, edge_type: str | None = None) -> list[Edge]:
        self._ensure_edge_indexes()
        edges = self._incoming_index.get(node_id, ())
        return [edge for edge in edges if edge_type is None or edge.type == edge_type]

    def outgoing(self, node_id: str, edge_type: str | None = None) -> list[Edge]:
        self._ensure_edge_indexes()
        edges = self._outgoing_index.get(node_id, ())
        return [edge for edge in edges if edge_type is None or edge.type == edge_type]

    def _ensure_edge_indexes(self) -> None:
        token = (id(self.edges), len(self.edges))
        if self._edge_index_token == token:
            return
        incoming: dict[str, list[Edge]] = {}
        outgoing: dict[str, list[Edge]] = {}
        for edge in self.edges:
            incoming.setdefault(edge.target, []).append(edge)
            outgoing.setdefault(edge.source, []).append(edge)
        self._incoming_index = incoming
        self._outgoing_index = outgoing
        self._edge_index_token = token

    def rebuild_edge_indexes(self) -> None:
        self._edge_index_token = None
        self._ensure_edge_indexes()

    def argument_blocks(self) -> dict[str, ArgumentBlock]:
        """Return the canonical executable block registry.

        ``ArgumentBlock`` nodes remain display/document projections only.  They
        never contribute membership or acceptance independently.
        """

        return dict(self.blocks)

    def children_of(self, parent_id: str) -> list[str]:
        if parent_id in self.hierarchy:
            return list(self.hierarchy[parent_id])
        if parent_id in self.nodes:
            return list(self.nodes[parent_id].children)
        return []

    def parent_of(self, child_id: str) -> str | None:
        if child_id in self.nodes and self.nodes[child_id].parent:
            return self.nodes[child_id].parent
        for parent, children in self.hierarchy.items():
            if child_id in children:
                return parent
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": {
                "id": self.id,
                "title": self.title,
                "root_claim": self.root_claim,
                **self.metadata,
                "schema_version": self.schema_version,
            },
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            "edges": [edge.to_dict() for edge in self.edges],
            "acceptance": self.acceptance,
            "hierarchy": self.hierarchy,
            "blocks": {block_id: block.to_dict() for block_id, block in self.blocks.items()},
        }

    def canonical_dict(self) -> dict[str, Any]:
        """Return deterministic durable content, excluding evaluated node state."""

        model_metadata = {
            str(key): _serialize_value(value)
            for key, value in self.metadata.items()
            if key not in {"source_path", "model_revision_id", "model_content_digest"}
            and not str(key).startswith("_")
        }
        return {
            "model": {
                "id": self.id,
                "title": self.title,
                "root_claim": self.root_claim,
                **model_metadata,
                "schema_version": self.schema_version,
            },
            "nodes": {
                node_id: self.nodes[node_id].canonical_dict()
                for node_id in sorted(self.nodes)
            },
            "edges": [
                edge.canonical_dict()
                for edge in sorted(
                    self.edges,
                    key=lambda item: (
                        item.id,
                        item.source,
                        item.target,
                        item.type,
                        item.explanation,
                    ),
                )
            ],
            "acceptance": {
                key: _serialize_value(self.acceptance[key])
                for key in sorted(self.acceptance)
            },
            "hierarchy": {
                key: list(self.hierarchy[key])
                for key in sorted(self.hierarchy)
            },
            "blocks": {
                block_id: self.blocks[block_id].to_dict()
                for block_id in sorted(self.blocks)
            },
        }


@dataclass
class NodeEvaluation:
    node_id: str
    state: str
    confidence: float
    explanation: str = ""
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state,
            "confidence": round(self.confidence, 4),
            "explanation": self.explanation,
            "blockers": list(self.blockers),
        }


@dataclass
class EvaluationTraceStep:
    iteration: int
    node_id: str
    old_state: str
    new_state: str
    old_confidence: float
    new_confidence: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "node_id": self.node_id,
            "old_state": self.old_state,
            "new_state": self.new_state,
            "old_confidence": round(self.old_confidence, 4),
            "new_confidence": round(self.new_confidence, 4),
            "reason": self.reason,
        }


@dataclass
class EvaluationResult:
    model_id: str
    root_claim: str | None
    node_results: dict[str, NodeEvaluation]
    trace: list[EvaluationTraceStep] = field(default_factory=list)
    iterations: int = 0
    converged: bool = False
    cycles: list[list[str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    model_revision_id: str | None = None

    def root(self) -> NodeEvaluation | None:
        if self.root_claim is None:
            return None
        return self.node_results.get(self.root_claim)

    def summary(self) -> str:
        root = self.root()
        if root is None:
            return f"Model {self.model_id}: no root claim"
        return (
            f"Root claim {root.node_id}: {root.state} "
            f"(confidence={root.confidence:.2f}, converged={self.converged})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_revision_id": self.model_revision_id,
            "root_claim": self.root_claim,
            "summary": self.summary(),
            "iterations": self.iterations,
            "converged": self.converged,
            "cycles": self.cycles,
            "warnings": self.warnings,
            "nodes": {node_id: result.to_dict() for node_id, result in self.node_results.items()},
            "trace": [step.to_dict() for step in self.trace],
        }


@dataclass
class DiagnosticFinding:
    code: str
    severity: str
    affected_nodes: list[str]
    explanation: str
    why_it_matters: str
    suggested_repair: str
    rewrite_suggestion: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "affected_nodes": self.affected_nodes,
            "explanation": self.explanation,
            "why_it_matters": self.why_it_matters,
            "suggested_repair": self.suggested_repair,
            "rewrite_suggestion": self.rewrite_suggestion,
            "evidence": self.evidence,
        }


@dataclass
class DiagnosticReport:
    model_id: str
    findings: list[DiagnosticFinding] = field(default_factory=list)

    def by_severity(self) -> dict[str, list[DiagnosticFinding]]:
        grouped: dict[str, list[DiagnosticFinding]] = {}
        for finding in self.findings:
            grouped.setdefault(finding.severity, []).append(finding)
        return grouped

    def to_dict(self) -> dict[str, Any]:
        return {"model_id": self.model_id, "findings": [finding.to_dict() for finding in self.findings]}

    def to_markdown(self) -> str:
        if not self.findings:
            return "No structural logic findings were detected.\n"
        lines = ["# LogicGuard Diagnostics", ""]
        for finding in self.findings:
            nodes = ", ".join(finding.affected_nodes) or "n/a"
            lines.extend(
                [
                    f"## {finding.severity.upper()}: {finding.code}",
                    f"- Affected nodes: {nodes}",
                    f"- Explanation: {finding.explanation}",
                    f"- Why it matters: {finding.why_it_matters}",
                    f"- Suggested repair: {finding.suggested_repair}",
                ]
            )
            if finding.rewrite_suggestion:
                lines.append(f"- Possible rewrite: {finding.rewrite_suggestion}")
            lines.append("")
        return "\n".join(lines)


@dataclass
class SimulationResult:
    mode: str
    root_claim: str | None
    baseline_state: str | None
    baseline_confidence: float | None
    result_state: str | None = None
    result_confidence: float | None = None
    perturbation: dict[str, Any] = field(default_factory=dict)
    impacts: list[dict[str, Any]] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "root_claim": self.root_claim,
            "baseline_state": self.baseline_state,
            "baseline_confidence": self.baseline_confidence,
            "result_state": self.result_state,
            "result_confidence": self.result_confidence,
            "perturbation": self.perturbation,
            "impacts": self.impacts,
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class DepthCoverageItem:
    node_id: str
    node_type: str
    importance: float
    state: str
    confidence: float
    reachable: bool
    evaluated: bool
    coverage_status: str
    response_node_ids: tuple[str, ...] = ()
    downstream_consumers: tuple[str, ...] = ()
    disposition: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "importance": round(self.importance, 4),
            "state": self.state,
            "confidence": round(self.confidence, 4),
            "reachable": self.reachable,
            "evaluated": self.evaluated,
            "coverage_status": self.coverage_status,
            "response_node_ids": list(self.response_node_ids),
            "downstream_consumers": list(self.downstream_consumers),
            "disposition": self.disposition,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class DepthCoverageSummary:
    important_threshold: float
    required_count: int
    covered_count: int
    uncovered_node_ids: tuple[str, ...]
    role_counts: dict[str, int]
    edge_role_counts: dict[str, int]
    semantic_coverage_passed: bool
    items: tuple[DepthCoverageItem, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "important_threshold": self.important_threshold,
            "required_count": self.required_count,
            "covered_count": self.covered_count,
            "coverage_ratio": round(self.covered_count / self.required_count, 4) if self.required_count else 0.0,
            "uncovered_node_ids": list(self.uncovered_node_ids),
            "role_counts": dict(self.role_counts),
            "edge_role_counts": dict(self.edge_role_counts),
            "semantic_coverage_passed": self.semantic_coverage_passed,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True)
class ConclusionCandidate:
    node_id: str
    state: str
    confidence: float
    importance: float
    rank: int
    is_root: bool = False
    unresolved_objection_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state,
            "confidence": round(self.confidence, 4),
            "importance": round(self.importance, 4),
            "rank": self.rank,
            "is_root": self.is_root,
            "unresolved_objection_ids": list(self.unresolved_objection_ids),
        }


@dataclass(frozen=True)
class ConclusionTournament:
    root_claim: str | None
    preferred_conclusion: str | None
    candidates: tuple[ConclusionCandidate, ...]
    unresolved_competitor_ids: tuple[str, ...]
    status: str
    allowed_wording: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_claim": self.root_claim,
            "preferred_conclusion": self.preferred_conclusion,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "unresolved_competitor_ids": list(self.unresolved_competitor_ids),
            "status": self.status,
            "allowed_wording": self.allowed_wording,
        }


@dataclass(frozen=True)
class PerturbationPlanItem:
    node_id: str
    node_type: str
    mutation: str
    importance: float
    uncertainty: float
    centrality: float
    priority: float
    reasons: tuple[str, ...]
    critical: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "mutation": self.mutation,
            "importance": round(self.importance, 4),
            "uncertainty": round(self.uncertainty, 4),
            "centrality": round(self.centrality, 4),
            "priority": round(self.priority, 4),
            "reasons": list(self.reasons),
            "critical": self.critical,
        }


@dataclass(frozen=True)
class PerturbationEffectiveness:
    node_id: str
    mutation: str
    baseline_state: str | None
    result_state: str | None
    baseline_confidence: float | None
    result_confidence: float | None
    state_changed: bool
    confidence_changed: bool
    support_path_changed: bool
    diagnostics_changed: bool
    ranking_changed: bool
    effective: bool
    changed_diagnostic_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "mutation": self.mutation,
            "baseline_state": self.baseline_state,
            "result_state": self.result_state,
            "baseline_confidence": self.baseline_confidence,
            "result_confidence": self.result_confidence,
            "state_changed": self.state_changed,
            "confidence_changed": self.confidence_changed,
            "support_path_changed": self.support_path_changed,
            "diagnostics_changed": self.diagnostics_changed,
            "ranking_changed": self.ranking_changed,
            "effective": self.effective,
            "changed_diagnostic_codes": list(self.changed_diagnostic_codes),
        }


@dataclass(frozen=True)
class ImportancePolicy:
    profile: str
    requested_threshold: float | None
    effective_threshold: float
    threshold_origin: str
    native_broad_threshold: float
    valid_range: tuple[float, float]
    passed: bool
    gaps: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "requested_threshold": self.requested_threshold,
            "effective_threshold": self.effective_threshold,
            "threshold_origin": self.threshold_origin,
            "native_broad_threshold": self.native_broad_threshold,
            "valid_range": list(self.valid_range),
            "passed": self.passed,
            "gaps": list(self.gaps),
        }


@dataclass(frozen=True)
class RoleCoverage:
    card_id: str
    node_ids: tuple[str, ...]
    importance: float
    required_roles: tuple[str, ...]
    covered_roles: tuple[str, ...]
    terminal_dispositions: dict[str, str]
    missing_roles: tuple[str, ...]
    unresolved_disposition_roles: tuple[str, ...]
    status: str
    declared_importance: float | None = None
    member_node_importance: float = 0.0
    structural_importance: float = 0.0
    inventory_origins: tuple[str, ...] = ()
    explicit: bool = False
    excluded: bool = False
    exclusion_reason: str = ""
    exclusion_disposition: str = ""
    exclusion_closed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "node_ids": list(self.node_ids),
            "importance": round(self.importance, 4),
            "required_roles": list(self.required_roles),
            "covered_roles": list(self.covered_roles),
            "terminal_dispositions": dict(self.terminal_dispositions),
            "missing_roles": list(self.missing_roles),
            "unresolved_disposition_roles": list(self.unresolved_disposition_roles),
            "status": self.status,
            "declared_importance": self.declared_importance,
            "member_node_importance": round(self.member_node_importance, 4),
            "structural_importance": round(self.structural_importance, 4),
            "importance_origin": "max(declared,member_node,structural)",
            "inventory_origins": list(self.inventory_origins),
            "explicit": self.explicit,
            "excluded": self.excluded,
            "exclusion_reason": self.exclusion_reason,
            "exclusion_disposition": self.exclusion_disposition,
            "exclusion_closed": self.exclusion_closed,
        }


@dataclass(frozen=True)
class ClaimRoleCoverage:
    claim_id: str
    card_ids: tuple[str, ...]
    importance: float
    required_roles: tuple[str, ...]
    connected_role_node_ids: dict[str, tuple[str, ...]]
    terminal_dispositions: dict[str, str]
    missing_roles: tuple[str, ...]
    unresolved_disposition_roles: tuple[str, ...]
    implicit_shared_role_node_ids: tuple[str, ...]
    applicable_perturbation_node_ids: tuple[str, ...]
    perturbation_disposition: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "card_ids": list(self.card_ids),
            "importance": round(self.importance, 4),
            "required_roles": list(self.required_roles),
            "connected_role_node_ids": {
                role: list(node_ids)
                for role, node_ids in self.connected_role_node_ids.items()
            },
            "terminal_dispositions": dict(self.terminal_dispositions),
            "missing_roles": list(self.missing_roles),
            "unresolved_disposition_roles": list(self.unresolved_disposition_roles),
            "implicit_shared_role_node_ids": list(self.implicit_shared_role_node_ids),
            "applicable_perturbation_node_ids": list(
                self.applicable_perturbation_node_ids
            ),
            "perturbation_disposition": self.perturbation_disposition,
            "status": self.status,
        }


@dataclass(frozen=True)
class ClaimPerturbationCoverage:
    claim_id: str
    applicable_node_ids: tuple[str, ...]
    selected_node_ids: tuple[str, ...]
    executed_node_ids: tuple[str, ...]
    effective_node_ids: tuple[str, ...]
    uncovered_node_ids: tuple[str, ...]
    ineffective_node_ids: tuple[str, ...]
    terminal_disposition: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "applicable_node_ids": list(self.applicable_node_ids),
            "selected_node_ids": list(self.selected_node_ids),
            "executed_node_ids": list(self.executed_node_ids),
            "effective_node_ids": list(self.effective_node_ids),
            "uncovered_node_ids": list(self.uncovered_node_ids),
            "ineffective_node_ids": list(self.ineffective_node_ids),
            "terminal_disposition": self.terminal_disposition,
            "status": self.status,
        }


@dataclass(frozen=True)
class ClaimScopeCoverage:
    requested_node_ids: tuple[str, ...]
    covered_node_ids: tuple[str, ...]
    missing_node_ids: tuple[str, ...]
    coverage_ratio: float
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_node_ids": list(self.requested_node_ids),
            "covered_node_ids": list(self.covered_node_ids),
            "missing_node_ids": list(self.missing_node_ids),
            "coverage_ratio": round(self.coverage_ratio, 4),
            "passed": self.passed,
        }


@dataclass(frozen=True)
class ArgumentCoverageUniverse:
    owner_id: str
    universe_fingerprint: str
    target_unit_ids: tuple[str, ...]
    modeled_target_unit_ids: tuple[str, ...]
    unmodeled_target_unit_ids: tuple[str, ...]
    model_card_ids: tuple[str, ...]
    important_node_ids: tuple[str, ...]
    reachable_node_ids: tuple[str, ...]
    disconnected_important_node_ids: tuple[str, ...]
    terminally_disposed_disconnected_node_ids: tuple[str, ...]
    unresolved_disconnected_node_ids: tuple[str, ...]
    critical_perturbable_node_ids: tuple[str, ...]
    role_coverage: tuple[RoleCoverage, ...]
    claim_role_coverage: tuple[ClaimRoleCoverage, ...]
    importance_policy: ImportancePolicy
    claim_scope: ClaimScopeCoverage
    discovered_model_card_ids: tuple[str, ...] = ()
    declared_model_card_ids: tuple[str, ...] = ()
    excluded_model_card_ids: tuple[str, ...] = ()
    unresolved_excluded_model_card_ids: tuple[str, ...] = ()
    card_reconciliation_passed: bool = False
    findings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "universe_fingerprint": self.universe_fingerprint,
            "target_unit_ids": list(self.target_unit_ids),
            "modeled_target_unit_ids": list(self.modeled_target_unit_ids),
            "unmodeled_target_unit_ids": list(self.unmodeled_target_unit_ids),
            "model_card_ids": list(self.model_card_ids),
            "important_node_ids": list(self.important_node_ids),
            "reachable_node_ids": list(self.reachable_node_ids),
            "disconnected_important_node_ids": list(self.disconnected_important_node_ids),
            "terminally_disposed_disconnected_node_ids": list(
                self.terminally_disposed_disconnected_node_ids
            ),
            "unresolved_disconnected_node_ids": list(self.unresolved_disconnected_node_ids),
            "critical_perturbable_node_ids": list(self.critical_perturbable_node_ids),
            "role_coverage": [item.to_dict() for item in self.role_coverage],
            "claim_role_coverage": [
                item.to_dict() for item in self.claim_role_coverage
            ],
            "importance_policy": self.importance_policy.to_dict(),
            "claim_scope": self.claim_scope.to_dict(),
            "discovered_model_card_ids": list(self.discovered_model_card_ids),
            "declared_model_card_ids": list(self.declared_model_card_ids),
            "excluded_model_card_ids": list(self.excluded_model_card_ids),
            "unresolved_excluded_model_card_ids": list(
                self.unresolved_excluded_model_card_ids
            ),
            "card_reconciliation_passed": self.card_reconciliation_passed,
            "counts": {
                "target_unit_count": len(self.target_unit_ids),
                "modeled_target_unit_count": len(self.modeled_target_unit_ids),
                "unmodeled_target_unit_count": len(self.unmodeled_target_unit_ids),
                "model_card_count": len(self.model_card_ids),
                "important_node_count": len(self.important_node_ids),
                "reachable_node_count": len(self.reachable_node_ids),
                "disconnected_important_count": len(self.disconnected_important_node_ids),
                "unresolved_disconnected_count": len(self.unresolved_disconnected_node_ids),
                "critical_perturbable_count": len(self.critical_perturbable_node_ids),
                "role_complete_card_count": sum(item.status == "pass" for item in self.role_coverage),
                "important_claim_count": len(self.claim_role_coverage),
                "claim_role_complete_count": sum(
                    item.status == "pass" for item in self.claim_role_coverage
                ),
                "excluded_model_card_count": len(self.excluded_model_card_ids),
            },
            "findings": list(self.findings),
        }


@dataclass(frozen=True)
class LogicDepthReceipt:
    receipt_version: str
    model_id: str
    model_fingerprint: str
    generated_at: str
    evaluation: EvaluationResult
    coverage: DepthCoverageSummary
    tournament: ConclusionTournament
    perturbation_plan: tuple[PerturbationPlanItem, ...]
    perturbation_effectiveness: tuple[PerturbationEffectiveness, ...]
    untested_high_impact_node_ids: tuple[str, ...]
    unresolved_gaps: tuple[str, ...]
    status: str
    broad_claim_licensed: bool
    claim_boundary: str
    native_obligation_evidence: tuple[dict[str, Any], ...]
    profile: str = "enforced"
    coverage_universe: ArgumentCoverageUniverse | None = None
    critical_perturbation_coverage: dict[str, Any] = field(default_factory=dict)
    claim_perturbation_coverage: tuple[ClaimPerturbationCoverage, ...] = ()
    requested_claim_scope: str = "complete"
    covered_claim_scope: str = "not_run"
    target_contract_id: str = ""
    target_contract_fingerprint: str = ""
    target_purpose: str = ""
    target_proof_receipt: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_version": self.receipt_version,
            "model_id": self.model_id,
            "model_fingerprint": self.model_fingerprint,
            "generated_at": self.generated_at,
            "evaluation": self.evaluation.to_dict(),
            "coverage": self.coverage.to_dict(),
            "tournament": self.tournament.to_dict(),
            "perturbation_plan": [item.to_dict() for item in self.perturbation_plan],
            "perturbation_effectiveness": [item.to_dict() for item in self.perturbation_effectiveness],
            "effective_perturbation_count": sum(item.effective for item in self.perturbation_effectiveness),
            "untested_high_impact_node_ids": list(self.untested_high_impact_node_ids),
            "unresolved_gaps": list(self.unresolved_gaps),
            "status": self.status,
            "broad_claim_licensed": self.broad_claim_licensed,
            "claim_boundary": self.claim_boundary,
            "native_obligation_evidence": [
                dict(item) for item in self.native_obligation_evidence
            ],
            "profile": self.profile,
            "coverage_universe": self.coverage_universe.to_dict() if self.coverage_universe else None,
            "critical_perturbation_coverage": dict(self.critical_perturbation_coverage),
            "claim_perturbation_coverage": [
                item.to_dict() for item in self.claim_perturbation_coverage
            ],
            "requested_claim_scope": self.requested_claim_scope,
            "covered_claim_scope": self.covered_claim_scope,
            "target_contract_id": self.target_contract_id,
            "target_contract_fingerprint": self.target_contract_fingerprint,
            "target_purpose": self.target_purpose,
            "target_proof_receipt": dict(self.target_proof_receipt),
        }


def freeze_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})
