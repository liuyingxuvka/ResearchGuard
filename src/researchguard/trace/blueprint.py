"""TraceGuard-owned deterministic investigation blueprint.

This module projects the current native TraceGuard model and one already
produced canonical inference receipt.  It never solves, rescales, retries, or
selects an alternate inference path.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from typing import Iterable, Literal, Mapping

from ..native_receipts import (
    NativeReceiptExpectation,
    NativeReceiptReference,
    native_receipt_expectation,
    resolve_expected_native_receipts,
)
from ..target_authority import (
    ExpectedTargetAnchor,
    NativeTargetMaterialReplay,
    TargetAuthorityItem,
    TargetPurposeAuthority,
    content_addressed_request_id,
    _issue_replayed_target_authority,
    read_target_material_bytes,
    verify_registered_target_authority,
)

from .inference.engine import verify_inference_receipt
from .inference.projection import project_canonical_receipt_identity
from .inference.types import InferenceReceipt
from .purpose_contract import GuardPurposeContractError, require_current_guard_purpose_binding
from .schema import (
    SCHEMA_ID,
    SchemaError,
    TraceGuardModel,
    TraceInterfaceBinding,
    TraceInterfaceReceiptRef,
    semantic_object_fingerprint,
    trace_interface_endpoint_fingerprint,
    trace_interface_model_fingerprint,
    trace_interface_payload_fingerprint,
    trace_model_fingerprint,
)
from .validation import validate_references


TRACE_BLUEPRINT_SCHEMA = "researchguard.trace.investigation-blueprint.v1"
TRACE_TARGET_AUTHORITY_OWNER = "researchguard.trace.target-purpose"
TRACE_TARGET_AUTHORITY_TOOL = "researchguard.trace.native-inventory"
TRACE_TARGET_ADAPTER_ID = "researchguard.trace.target-material-adapter"
TRACE_TARGET_ADAPTER_VERSION = "2"
TRACE_TARGET_MATERIAL_SCHEMA = "researchguard.trace.target-material.v1"


def _digest(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _content_fingerprint(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_trace_interface_receipt_material(
    model: TraceGuardModel, binding: TraceInterfaceBinding
) -> TraceInterfaceReceiptRef:
    """Build interface material; immutable receipt admission is external."""

    value = TraceInterfaceReceiptRef(
        receipt_id=f"trace-interface:{binding.binding_id}",
        producer_kind=binding.producer_kind,
        producer_id=binding.producer_id,
        result_fingerprint=trace_interface_payload_fingerprint(model, binding),
        model_fingerprint=trace_interface_model_fingerprint(model),
        task_id=str(model.metadata.get("model_instance_id") or "traceguard-investigation"),
        status="current",
        receipt_fingerprint="sha256:" + "0" * 64,
    )
    return replace(value, receipt_fingerprint=value.expected_fingerprint)


@dataclass(frozen=True)
class TraceTargetUniverse:
    universe_id: str
    required_source_ids: tuple[str, ...]
    required_evidence_ids: tuple[str, ...]
    required_entity_ids: tuple[str, ...]
    required_entity_resolution_ids: tuple[str, ...]
    required_location_ids: tuple[str, ...]
    required_event_ids: tuple[str, ...]
    required_trace_ids: tuple[str, ...]
    required_stage_ids: tuple[str, ...]
    required_hypothesis_ids: tuple[str, ...]
    required_hypothesis_evidence_link_ids: tuple[str, ...]
    required_hypothesis_relation_ids: tuple[str, ...]
    required_causal_boundary_ids: tuple[str, ...]
    required_causal_candidate_ids: tuple[str, ...]
    required_causal_mechanism_ids: tuple[str, ...]
    required_confounder_review_ids: tuple[str, ...]
    required_causal_scope_ids: tuple[str, ...]
    required_evidence_ablation_ids: tuple[str, ...]
    required_scenario_perturbation_ids: tuple[str, ...]
    required_sensitivity_ids: tuple[str, ...]
    required_interface_binding_ids: tuple[str, ...]
    required_bounded_claim_ids: tuple[str, ...]
    required_handoff_ids: tuple[str, ...]
    known_good_case_ids: tuple[str, ...]
    known_bad_case_ids: tuple[str, ...]
    native_receipt_refs: tuple[NativeReceiptReference, ...] = ()
    target_authority: TargetPurposeAuthority | None = None

    def __post_init__(self) -> None:
        if not self.universe_id.strip():
            raise ValueError("trace target universe requires universe_id")
        for name in (
            "required_source_ids",
            "required_evidence_ids",
            "required_entity_ids",
            "required_entity_resolution_ids",
            "required_location_ids",
            "required_event_ids",
            "required_trace_ids",
            "required_stage_ids",
            "required_hypothesis_ids",
            "required_hypothesis_evidence_link_ids",
            "required_hypothesis_relation_ids",
            "required_causal_boundary_ids",
            "required_causal_candidate_ids",
            "required_causal_mechanism_ids",
            "required_confounder_review_ids",
            "required_causal_scope_ids",
            "required_evidence_ablation_ids",
            "required_scenario_perturbation_ids",
            "required_sensitivity_ids",
            "required_interface_binding_ids",
            "required_bounded_claim_ids",
            "required_handoff_ids",
            "known_good_case_ids",
            "known_bad_case_ids",
        ):
            values = getattr(self, name)
            if len(values) != len(set(values)) or any(not item.strip() for item in values):
                raise ValueError(f"{name} must contain unique non-empty ids")
        receipt_ids = tuple(item.receipt_id for item in self.native_receipt_refs)
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("trace target native receipt ids must be unique")

    @property
    def fingerprint(self) -> str:
        material = {
            key: list(value) if isinstance(value, tuple) else value
            for key, value in asdict(self).items()
            if key not in {"target_authority", "native_receipt_refs"}
        }
        material["native_receipt_refs"] = []
        material["target_authority"] = self.target_authority.to_dict() if self.target_authority else None
        return _digest(material)

    def to_dict(self) -> dict[str, object]:
        payload = {
            key: list(value) if isinstance(value, tuple) else value
            for key, value in asdict(self).items()
            if key not in {"target_authority", "native_receipt_refs"}
        }
        payload["native_receipt_refs"] = [
            item.to_dict() for item in self.native_receipt_refs
        ]
        payload["target_authority"] = self.target_authority.to_dict() if self.target_authority else None
        return payload | {"universe_fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "TraceTargetUniverse":
        keys = (
            "required_source_ids",
            "required_evidence_ids",
            "required_entity_ids",
            "required_entity_resolution_ids",
            "required_location_ids",
            "required_event_ids",
            "required_trace_ids",
            "required_stage_ids",
            "required_hypothesis_ids",
            "required_hypothesis_evidence_link_ids",
            "required_hypothesis_relation_ids",
            "required_causal_boundary_ids",
            "required_causal_candidate_ids",
            "required_causal_mechanism_ids",
            "required_confounder_review_ids",
            "required_causal_scope_ids",
            "required_evidence_ablation_ids",
            "required_scenario_perturbation_ids",
            "required_sensitivity_ids",
            "required_interface_binding_ids",
            "required_bounded_claim_ids",
            "required_handoff_ids",
            "known_good_case_ids",
            "known_bad_case_ids",
        )
        allowed = {"universe_id", "target_authority", "native_receipt_refs", "universe_fingerprint", *keys}
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ValueError(f"trace target universe contains unknown fields: {unknown!r}")
        for key in keys:
            if not isinstance(raw.get(key), list):
                raise ValueError(f"trace target universe {key} must be a list")
        result = cls(
            universe_id=str(raw.get("universe_id", "")),
            target_authority=(
                TargetPurposeAuthority.from_dict(raw["target_authority"])
                if isinstance(raw.get("target_authority"), Mapping)
                else None
            ),
            native_receipt_refs=tuple(
                NativeReceiptReference.from_dict(item)
                for item in raw.get("native_receipt_refs", [])
                if isinstance(item, Mapping)
            ),
            **{key: tuple(str(item) for item in raw.get(key, [])) for key in keys},
        )
        supplied = str(raw.get("universe_fingerprint", ""))
        if supplied and supplied != result.fingerprint:
            raise ValueError("trace target universe fingerprint mismatch")
        return result


@dataclass(frozen=True)
class TraceHierarchyNode:
    projection_id: str
    kind: str
    native_id: str
    parent_projection_id: str
    cross_link_parent_ids: tuple[str, ...] = ()
    disposition: str = "contained"
    depth: int = -1

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class TraceBlueprintGap:
    code: str
    object_id: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class TraceBlueprintResult:
    status: Literal["complete", "incomplete", "stale", "failed"]
    model_fingerprint: str
    universe_fingerprint: str
    canonical_receipt_id: str
    canonical_problem_fingerprint: str
    hierarchy_fingerprint: str
    interface_fingerprint: str
    blueprint_fingerprint: str
    deepest_proven_layer: str
    first_unresolved_gap: str
    live_alternative_ids: tuple[str, ...]
    causal_boundaries: tuple[dict[str, object], ...]
    hierarchy: tuple[TraceHierarchyNode, ...]
    interface_receipt_refs: tuple[dict[str, object], ...]
    gaps: tuple[TraceBlueprintGap, ...]
    layer_statuses: tuple[dict[str, object], ...]
    claim_boundary: str = (
        "TraceGuard projects source-backed temporal and storyline structure plus only the canonical "
        "receipt's bounded qualitative causal status. It does not license formal causal identification, "
        "do-calculus, calibrated treatment effects, factual proof, or missing source content."
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": TRACE_BLUEPRINT_SCHEMA,
            "status": self.status,
            "model_fingerprint": self.model_fingerprint,
            "universe_fingerprint": self.universe_fingerprint,
            "canonical_receipt_id": self.canonical_receipt_id,
            "canonical_problem_fingerprint": self.canonical_problem_fingerprint,
            "hierarchy_fingerprint": self.hierarchy_fingerprint,
            "interface_fingerprint": self.interface_fingerprint,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "deepest_proven_layer": self.deepest_proven_layer,
            "first_unresolved_gap": self.first_unresolved_gap,
            "live_alternative_ids": list(self.live_alternative_ids),
            "causal_boundaries": list(self.causal_boundaries),
            "hierarchy": [item.to_dict() for item in self.hierarchy],
            "interface_receipt_refs": list(self.interface_receipt_refs),
            "gaps": [item.to_dict() for item in self.gaps],
            "layer_statuses": list(self.layer_statuses),
            "claim_boundary": self.claim_boundary,
        }


def _owner_node(
    projection_id: str,
    kind: str,
    native_id: str,
    parent_ids: Iterable[str],
    *,
    root_id: str,
) -> TraceHierarchyNode:
    parents = tuple(sorted(set(parent_ids)))
    if parents:
        return TraceHierarchyNode(
            projection_id,
            kind,
            native_id,
            parents[0],
            parents[1:],
        )
    return TraceHierarchyNode(
        projection_id,
        kind,
        native_id,
        root_id,
        (),
        "unresolved-orphan",
    )


def entity_resolution_id(left_id: str, relation: str, right_id: str) -> str:
    return f"entity-resolution:{left_id}:{relation}:{right_id}"


def _assign_hierarchy_depths(nodes: Iterable[TraceHierarchyNode]) -> tuple[TraceHierarchyNode, ...]:
    by_id = {item.projection_id: item for item in nodes}
    memo: dict[str, int] = {}

    def resolve(projection_id: str, stack: set[str]) -> int:
        if projection_id in memo:
            return memo[projection_id]
        item = by_id.get(projection_id)
        if item is None or projection_id in stack:
            return -1
        if not item.parent_projection_id:
            memo[projection_id] = 0
            return 0
        parent_depth = resolve(item.parent_projection_id, {*stack, projection_id})
        memo[projection_id] = parent_depth + 1 if parent_depth >= 0 else -1
        return memo[projection_id]

    return tuple(
        sorted(
            (replace(item, depth=resolve(item.projection_id, set())) for item in by_id.values()),
            key=lambda item: item.projection_id,
        )
    )


def project_hierarchy(model: TraceGuardModel) -> tuple[TraceHierarchyNode, ...]:
    root_native_id = str(model.metadata.get("model_instance_id") or "traceguard-investigation")
    root_id = f"investigation:{root_native_id}"
    nodes: list[TraceHierarchyNode] = [
        TraceHierarchyNode(root_id, "investigation", root_native_id, "")
    ]
    for hypothesis in sorted(model.storyline_hypotheses, key=lambda item: item.hypothesis_id):
        hypothesis_projection = f"hypothesis:{hypothesis.hypothesis_id}"
        nodes.append(
            TraceHierarchyNode(
                hypothesis_projection,
                "storyline_hypothesis",
                hypothesis.hypothesis_id,
                root_id,
            )
        )
        boundary_projection = f"causal-boundary:{hypothesis.hypothesis_id}"
        nodes.append(
            TraceHierarchyNode(
                boundary_projection,
                "causal_boundary",
                boundary_projection,
                hypothesis_projection,
            )
        )
        for claim_id in sorted(hypothesis.bounded_claim_ids):
            nodes.append(
                TraceHierarchyNode(
                    f"bounded-claim:{claim_id}",
                    "bounded_claim",
                    claim_id,
                    hypothesis_projection,
                )
            )
        for handoff_id in sorted(hypothesis.handoff_ids):
            nodes.append(
                TraceHierarchyNode(
                    f"handoff:{handoff_id}",
                    "handoff",
                    handoff_id,
                    hypothesis_projection,
                )
            )
    for candidate in sorted(model.causal_candidates, key=lambda item: item.causal_id):
        nodes.append(
            TraceHierarchyNode(
                f"causal-candidate:{candidate.causal_id}",
                "causal_candidate",
                candidate.causal_id,
                f"causal-boundary:{candidate.hypothesis_id}",
            )
        )
    candidate_parents_by_mechanism: dict[str, list[str]] = {}
    candidate_parents_by_confounder: dict[str, list[str]] = {}
    candidate_parents_by_scope: dict[str, list[str]] = {}
    for candidate in model.causal_candidates:
        for mechanism_id in candidate.mechanism_ids:
            candidate_parents_by_mechanism.setdefault(mechanism_id, []).append(f"causal-candidate:{candidate.causal_id}")
        for confounder_id in candidate.confounder_ids:
            candidate_parents_by_confounder.setdefault(confounder_id, []).append(f"causal-candidate:{candidate.causal_id}")
        if candidate.scope_id:
            candidate_parents_by_scope.setdefault(candidate.scope_id, []).append(f"causal-candidate:{candidate.causal_id}")
    for mechanism in sorted(model.causal_mechanisms, key=lambda item: item.mechanism_id):
        nodes.append(
            _owner_node(
                f"causal-mechanism:{mechanism.mechanism_id}",
                "causal_mechanism",
                mechanism.mechanism_id,
                candidate_parents_by_mechanism.get(mechanism.mechanism_id, (f"causal-boundary:{mechanism.hypothesis_id}",)),
                root_id=root_id,
            )
        )
    for confounder in sorted(model.confounder_reviews, key=lambda item: item.confounder_id):
        nodes.append(
            _owner_node(
                f"confounder:{confounder.confounder_id}",
                "confounder",
                confounder.confounder_id,
                candidate_parents_by_confounder.get(confounder.confounder_id, (f"causal-boundary:{confounder.hypothesis_id}",)),
                root_id=root_id,
            )
        )
    for scope in sorted(model.causal_scopes, key=lambda item: item.scope_id):
        nodes.append(
            _owner_node(
                f"causal-scope:{scope.scope_id}",
                "causal_scope",
                scope.scope_id,
                candidate_parents_by_scope.get(scope.scope_id, ()),
                root_id=root_id,
            )
        )
    hypothesis_parents: dict[str, list[str]] = {}
    for hypothesis in model.storyline_hypotheses:
        for trace_id in hypothesis.trace_ids:
            hypothesis_parents.setdefault(trace_id, []).append(
                f"hypothesis:{hypothesis.hypothesis_id}"
            )
    for trace in sorted(model.traces, key=lambda item: item.trace_id):
        trace_projection = f"trace:{trace.trace_id}"
        nodes.append(
            _owner_node(
                trace_projection,
                "trace",
                trace.trace_id,
                hypothesis_parents.get(trace.trace_id, ()),
                root_id=root_id,
            )
        )
        nodes.append(
            TraceHierarchyNode(
                f"stage:{trace.trace_id}:{trace.current_stage}",
                "sequence_stage",
                trace.current_stage,
                trace_projection,
            )
        )
    trace_parents: dict[str, list[str]] = {}
    for trace in model.traces:
        for event_id in trace.event_ids:
            trace_parents.setdefault(event_id, []).append(
                f"stage:{trace.trace_id}:{trace.current_stage}"
            )
    for event in sorted(model.events, key=lambda item: item.event_id):
        nodes.append(
            _owner_node(
                f"event:{event.event_id}",
                "event",
                event.event_id,
                trace_parents.get(event.event_id, ()),
                root_id=root_id,
            )
        )
    event_parents: dict[str, list[str]] = {}
    for event in model.events:
        for evidence_id in event.evidence_ids:
            event_parents.setdefault(evidence_id, []).append(f"event:{event.event_id}")
    for evidence in sorted(model.evidence, key=lambda item: item.evidence_id):
        nodes.append(
            _owner_node(
                f"evidence:{evidence.evidence_id}",
                "evidence_fact",
                evidence.evidence_id,
                event_parents.get(evidence.evidence_id, ()),
                root_id=root_id,
            )
        )
    entity_parents: dict[str, list[str]] = {}
    for entity in model.entities:
        if entity.evidence_id:
            entity_parents.setdefault(entity.mention_id, []).append(
                f"evidence:{entity.evidence_id}"
            )
    for event in model.events:
        for entity_id in event.actor_ids + event.object_ids + event.technology_ids:
            entity_parents.setdefault(entity_id, []).append(f"event:{event.event_id}")
    for entity in sorted(model.entities, key=lambda item: item.mention_id):
        nodes.append(
            _owner_node(
                f"entity:{entity.mention_id}",
                "entity",
                entity.mention_id,
                entity_parents.get(entity.mention_id, ()),
                root_id=root_id,
            )
        )
    for resolution in sorted(model.entity_resolutions, key=lambda item: (item.left_id, item.relation, item.right_id)):
        resolution_native_id = entity_resolution_id(resolution.left_id, resolution.relation, resolution.right_id)
        nodes.append(
            _owner_node(
                resolution_native_id,
                "entity_resolution",
                resolution_native_id,
                (f"entity:{resolution.left_id}", f"entity:{resolution.right_id}"),
                root_id=root_id,
            )
        )
    location_parents: dict[str, list[str]] = {}
    for event in model.events:
        for location_id in event.location_ids:
            location_parents.setdefault(location_id, []).append(f"event:{event.event_id}")
    for trace in model.traces:
        for location_id in trace.location_ids:
            location_parents.setdefault(location_id, []).append(f"trace:{trace.trace_id}")
    for location in sorted(model.locations, key=lambda item: item.location_id):
        nodes.append(
            _owner_node(
                f"location:{location.location_id}",
                "location",
                location.location_id,
                location_parents.get(location.location_id, ()),
                root_id=root_id,
            )
        )
    evidence_parents: dict[str, list[str]] = {}
    for evidence in model.evidence:
        evidence_parents.setdefault(evidence.source_id, []).append(
            f"evidence:{evidence.evidence_id}"
        )
    for source in sorted(model.sources, key=lambda item: item.source_id):
        nodes.append(
            _owner_node(
                f"source:{source.source_id}",
                "source",
                source.source_id,
                evidence_parents.get(source.source_id, ()),
                root_id=root_id,
            )
        )
    for link in sorted(model.hypothesis_evidence_links, key=lambda item: item.link_id):
        nodes.append(
            _owner_node(
                f"hypothesis-evidence-link:{link.link_id}",
                "hypothesis_evidence_link",
                link.link_id,
                (f"hypothesis:{link.hypothesis_id}", f"evidence:{link.evidence_id}"),
                root_id=root_id,
            )
        )
    for relation in sorted(model.hypothesis_relations, key=lambda item: item.relation_id):
        nodes.append(
            _owner_node(
                f"hypothesis-relation:{relation.relation_id}",
                "hypothesis_relation",
                relation.relation_id,
                (f"hypothesis:{relation.left_hypothesis_id}", f"hypothesis:{relation.right_hypothesis_id}"),
                root_id=root_id,
            )
        )
    for item in sorted(model.evidence_ablations, key=lambda row: row.ablation_id):
        parents = ([f"hypothesis:{item.hypothesis_id}"] if item.hypothesis_id else []) + ([f"trace:{item.trace_id}"] if item.trace_id else [])
        nodes.append(_owner_node(f"evidence-ablation:{item.ablation_id}", "evidence_ablation", item.ablation_id, parents, root_id=root_id))
    for item in sorted(model.scenario_perturbations, key=lambda row: row.perturbation_id):
        parents = ([f"hypothesis:{item.hypothesis_id}"] if item.hypothesis_id else []) + ([f"trace:{item.trace_id}"] if item.trace_id else [])
        nodes.append(_owner_node(f"scenario-perturbation:{item.perturbation_id}", "scenario_perturbation", item.perturbation_id, parents, root_id=root_id))
    for item in sorted(model.expected_sensitivities, key=lambda row: row.sensitivity_id):
        nodes.append(
            _owner_node(
                f"sensitivity:{item.sensitivity_id}",
                "expected_sensitivity",
                item.sensitivity_id,
                (f"scenario-perturbation:{item.perturbation_id}",),
                root_id=root_id,
            )
        )
    return _assign_hierarchy_depths(nodes)


def _native_objects(model: TraceGuardModel) -> dict[str, dict[str, object]]:
    return {
        "source": {item.source_id: item for item in model.sources},
        "evidence_fact": {item.evidence_id: item for item in model.evidence},
        "event": {item.event_id: item for item in model.events},
        "trace": {item.trace_id: item for item in model.traces},
        "hypothesis": {
            item.hypothesis_id: item for item in model.storyline_hypotheses
        },
    }


def _required_interfaces(model: TraceGuardModel) -> set[tuple[str, str, str, str]]:
    required = {
        ("source", item.source_id, "evidence_fact", item.evidence_id)
        for item in model.evidence
    }
    required.update(
        ("evidence_fact", evidence_id, "event", event.event_id)
        for event in model.events
        for evidence_id in event.evidence_ids
    )
    required.update(
        ("event", event_id, "trace", trace.trace_id)
        for trace in model.traces
        for event_id in trace.event_ids
    )
    required.update(
        ("trace", trace_id, "hypothesis", hypothesis.hypothesis_id)
        for hypothesis in model.storyline_hypotheses
        for trace_id in hypothesis.trace_ids
    )
    required.update(
        ("hypothesis", hypothesis.hypothesis_id, "bounded_claim", claim_id)
        for hypothesis in model.storyline_hypotheses
        for claim_id in hypothesis.bounded_claim_ids
    )
    required.update(
        ("hypothesis", hypothesis.hypothesis_id, "handoff", handoff_id)
        for hypothesis in model.storyline_hypotheses
        for handoff_id in hypothesis.handoff_ids
    )
    return required


def hierarchy_fingerprint(model: TraceGuardModel) -> str:
    return _digest([item.to_dict() for item in project_hierarchy(model)])


def _hierarchy_gaps(hierarchy: tuple[TraceHierarchyNode, ...]) -> list[TraceBlueprintGap]:
    gaps: list[TraceBlueprintGap] = []
    by_id = {item.projection_id: item for item in hierarchy}
    if len(by_id) != len(hierarchy):
        gaps.append(TraceBlueprintGap("duplicate-hierarchy-projection", "hierarchy", "projection ids must be unique"))
    roots = [item for item in hierarchy if not item.parent_projection_id]
    if len(roots) != 1 or roots[0].kind != "investigation" or roots[0].depth != 0:
        gaps.append(TraceBlueprintGap("invalid-hierarchy-root", "hierarchy", f"roots={[item.projection_id for item in roots]}"))
    for item in hierarchy:
        if not item.parent_projection_id:
            continue
        parent = by_id.get(item.parent_projection_id)
        if parent is None:
            gaps.append(TraceBlueprintGap("missing-hierarchy-parent", item.projection_id, item.parent_projection_id))
        elif item.depth != parent.depth + 1:
            gaps.append(TraceBlueprintGap("hierarchy-depth-jump", item.projection_id, f"{parent.depth}->{item.depth}"))
        for cross_link in item.cross_link_parent_ids:
            if cross_link not in by_id:
                gaps.append(TraceBlueprintGap("foreign-hierarchy-cross-link", item.projection_id, cross_link))
            if cross_link == item.parent_projection_id:
                gaps.append(TraceBlueprintGap("duplicate-hierarchy-cross-link", item.projection_id, cross_link))
        if item.depth < 0:
            gaps.append(TraceBlueprintGap("hierarchy-cycle-or-unreachable", item.projection_id, item.parent_projection_id))
    return gaps


def interface_fingerprint(model: TraceGuardModel) -> str:
    return _digest(
        [
            asdict(item)
            for item in sorted(model.interface_bindings, key=lambda item: item.binding_id)
        ]
    )


def _identity_gaps(model: TraceGuardModel) -> list[TraceBlueprintGap]:
    gaps: list[TraceBlueprintGap] = []
    for source in model.sources:
        missing = [
            name
            for name in (
                "object_fingerprint",
                "source_revision",
                "content_fingerprint",
                "locator",
                "provider_id",
                "provider_revision",
                "retrieval_request_fingerprint",
            )
            if not getattr(source, name)
        ]
        if missing:
            gaps.append(TraceBlueprintGap("incomplete-source-identity", source.source_id, ",".join(missing)))
        elif source.object_fingerprint != semantic_object_fingerprint(source):
            gaps.append(TraceBlueprintGap("stale-object-fingerprint", source.source_id, "source semantic content changed"))
    for evidence in model.evidence:
        missing = [
            name
            for name in (
                "object_fingerprint",
                "source_revision",
                "content_fingerprint",
                "locator",
                "normalizer_id",
                "normalizer_revision",
                "normalizer_fingerprint",
                "extractor_id",
                "extractor_revision",
                "extractor_fingerprint",
            )
            if not getattr(evidence, name)
        ]
        if missing:
            gaps.append(TraceBlueprintGap("incomplete-evidence-identity", evidence.evidence_id, ",".join(missing)))
        else:
            semantic_text = evidence.normalized_summary or evidence.raw_text
            if evidence.content_fingerprint != _content_fingerprint(semantic_text):
                gaps.append(TraceBlueprintGap("stale-evidence-content", evidence.evidence_id, "content fingerprint changed"))
            if evidence.object_fingerprint != semantic_object_fingerprint(evidence):
                gaps.append(TraceBlueprintGap("stale-object-fingerprint", evidence.evidence_id, "evidence semantic content changed"))
    for kind, rows, required_fields in (
        ("event", model.events, ("object_fingerprint", "extractor_id", "extractor_revision", "extractor_fingerprint")),
        ("trace", model.traces, ("object_fingerprint", "normalizer_id", "normalizer_revision", "normalizer_fingerprint")),
        ("hypothesis", model.storyline_hypotheses, ("object_fingerprint", "normalizer_id", "normalizer_revision", "normalizer_fingerprint")),
    ):
        for item in rows:
            item_id = str(getattr(item, f"{kind}_id"))
            missing = [name for name in required_fields if not getattr(item, name)]
            if missing:
                gaps.append(TraceBlueprintGap(f"incomplete-{kind}-identity", item_id, ",".join(missing)))
            elif item.object_fingerprint != semantic_object_fingerprint(item):
                gaps.append(TraceBlueprintGap("stale-object-fingerprint", item_id, f"{kind} semantic content changed"))
    return gaps


def _interface_gaps(
    model: TraceGuardModel,
    receipt: InferenceReceipt,
) -> tuple[list[TraceBlueprintGap], tuple[dict[str, object], ...]]:
    gaps: list[TraceBlueprintGap] = []
    native = _native_objects(model)
    required = _required_interfaces(model)
    by_key: dict[tuple[str, str, str, str], list[TraceInterfaceBinding]] = {}
    for binding in model.interface_bindings:
        key = (
            binding.producer_kind,
            binding.producer_id,
            binding.consumer_kind,
            binding.consumer_id,
        )
        by_key.setdefault(key, []).append(binding)
        if key not in required:
            gaps.append(
                TraceBlueprintGap(
                    "unexpected-interface",
                    binding.binding_id,
                    f"{binding.producer_id}->{binding.consumer_id}",
                )
            )
        expected_producer = trace_interface_endpoint_fingerprint(
            model, binding.producer_kind, binding.producer_id
        )
        if not expected_producer or binding.producer_object_fingerprint != expected_producer:
            gaps.append(
                TraceBlueprintGap(
                    "stale-interface-producer",
                    binding.binding_id,
                    binding.producer_id,
                )
            )
        expected_consumer = trace_interface_endpoint_fingerprint(
            model, binding.consumer_kind, binding.consumer_id
        )
        if not expected_consumer or binding.consumer_object_fingerprint != expected_consumer:
            gaps.append(
                TraceBlueprintGap(
                    "stale-interface-consumer",
                    binding.binding_id,
                    binding.consumer_id,
                )
            )
        expected_payload = trace_interface_payload_fingerprint(model, binding)
        expected_model = trace_interface_model_fingerprint(model)
        expected_task = str(model.metadata.get("model_instance_id") or "traceguard-investigation")
        if len(binding.receipt_refs) != 1:
            gaps.append(
                TraceBlueprintGap(
                    "missing-interface-native-receipt" if not binding.receipt_refs else "duplicate-interface-native-receipt",
                    binding.binding_id,
                    f"count={len(binding.receipt_refs)}",
                )
            )
        for native_receipt in binding.receipt_refs:
            receipt_checks = (
                (native_receipt.producer_kind == binding.producer_kind, "interface-receipt-producer-kind-mismatch", native_receipt.producer_kind),
                (native_receipt.producer_id == binding.producer_id, "interface-receipt-producer-mismatch", native_receipt.producer_id),
                (native_receipt.result_fingerprint == expected_payload, "interface-receipt-result-stale", native_receipt.result_fingerprint),
                (native_receipt.model_fingerprint == expected_model, "interface-receipt-model-stale", native_receipt.model_fingerprint),
                (native_receipt.task_id == expected_task, "interface-receipt-task-mismatch", native_receipt.task_id),
                (native_receipt.status == "current", "interface-receipt-not-current", native_receipt.status),
                (native_receipt.receipt_fingerprint == native_receipt.expected_fingerprint, "interface-receipt-fingerprint-mismatch", native_receipt.receipt_id),
            )
            for ok, code, detail in receipt_checks:
                if not ok:
                    gaps.append(TraceBlueprintGap(code, binding.binding_id, detail))
    for key in sorted(required):
        matches = by_key.get(key, [])
        if len(matches) != 1:
            gaps.append(
                TraceBlueprintGap(
                    "missing-interface" if not matches else "duplicate-interface",
                    f"{key[1]}->{key[3]}",
                    f"{key[0]}->{key[2]}",
                )
            )
        elif matches[0].disposition != "consumed":
            gaps.append(
                TraceBlueprintGap(
                    "required-interface-not-consumed",
                    matches[0].binding_id,
                    matches[0].disposition,
                )
            )
    source_consumers = {binding.producer_id for binding in model.interface_bindings if (binding.producer_kind, binding.producer_id, binding.consumer_kind, binding.consumer_id) in required and binding.producer_kind == "source" and binding.consumer_kind == "evidence_fact" and binding.disposition == "consumed"}
    evidence_consumers = {binding.producer_id for binding in model.interface_bindings if (binding.producer_kind, binding.producer_id, binding.consumer_kind, binding.consumer_id) in required and binding.producer_kind == "evidence_fact" and binding.consumer_kind == "event" and binding.disposition == "consumed"}
    event_consumers = {binding.producer_id for binding in model.interface_bindings if (binding.producer_kind, binding.producer_id, binding.consumer_kind, binding.consumer_id) in required and binding.producer_kind == "event" and binding.consumer_kind == "trace" and binding.disposition == "consumed"}
    trace_consumers = {binding.producer_id for binding in model.interface_bindings if (binding.producer_kind, binding.producer_id, binding.consumer_kind, binding.consumer_id) in required and binding.producer_kind == "trace" and binding.consumer_kind == "hypothesis" and binding.disposition == "consumed"}
    def output_gap(kind: str, object_id: str, consumed: bool, disposition: str) -> None:
        if disposition and disposition not in {"terminal", "excluded", "unresolved"}:
            gaps.append(TraceBlueprintGap("invalid-output-disposition", object_id, disposition))
        elif disposition == "unresolved":
            gaps.append(TraceBlueprintGap(f"unresolved-{kind}-output", object_id, disposition))
        elif not consumed and not disposition:
            gaps.append(TraceBlueprintGap(f"unconsumed-{kind}-output", object_id, "no typed/native consumer or explicit disposition"))

    for source in model.sources:
        output_gap("source", source.source_id, source.source_id in source_consumers, source.unconsumed_output_disposition)
    for evidence in model.evidence:
        if evidence.evidence_id not in evidence_consumers and not evidence.unconsumed_output_disposition:
            gaps.append(TraceBlueprintGap("unconsumed-evidence-output", evidence.evidence_id, "no event consumer or disposition"))
    for event in model.events:
        if not event.evidence_ids and not event.unresolved_input_disposition:
            gaps.append(TraceBlueprintGap("missing-evidence-input", event.event_id, "no evidence fact or unresolved disposition"))
        if event.event_id not in event_consumers and not event.unconsumed_output_disposition:
            gaps.append(TraceBlueprintGap("unconsumed-event-output", event.event_id, "no trace consumer or disposition"))
    for trace in model.traces:
        if not trace.event_ids and not trace.unresolved_input_disposition:
            gaps.append(TraceBlueprintGap("missing-event-input", trace.trace_id, "no event or unresolved disposition"))
        if trace.trace_id not in trace_consumers and not trace.unconsumed_output_disposition:
            gaps.append(TraceBlueprintGap("unconsumed-trace-output", trace.trace_id, "no hypothesis consumer or disposition"))
    for hypothesis in model.storyline_hypotheses:
        if not hypothesis.trace_ids and not hypothesis.unresolved_input_disposition:
            gaps.append(TraceBlueprintGap("missing-trace-input", hypothesis.hypothesis_id, "no trace or unresolved disposition"))
        if not hypothesis.bounded_claim_ids and not hypothesis.handoff_ids and not hypothesis.unconsumed_output_disposition:
            gaps.append(TraceBlueprintGap("unconsumed-hypothesis-output", hypothesis.hypothesis_id, "no bounded claim, handoff, or disposition"))
    used_entities = {
        value for event in model.events for value in event.actor_ids + event.object_ids + event.technology_ids
    } | {value for trace in model.traces for value in trace.entity_ids}
    used_locations = {value for event in model.events for value in event.location_ids} | {
        value for trace in model.traces for value in trace.location_ids
    } | {value for scope in model.causal_scopes for value in scope.location_ids}
    for entity in model.entities:
        output_gap("entity", entity.mention_id, entity.mention_id in used_entities, entity.unconsumed_output_disposition)
    for resolution in model.entity_resolutions:
        object_id = entity_resolution_id(resolution.left_id, resolution.relation, resolution.right_id)
        output_gap(
            "entity-resolution",
            object_id,
            bool({resolution.left_id, resolution.right_id} & used_entities),
            resolution.unconsumed_output_disposition,
        )
    for location in model.locations:
        output_gap("location", location.location_id, location.location_id in used_locations, location.unconsumed_output_disposition)
    for link in model.hypothesis_evidence_links:
        output_gap("hypothesis-evidence-link", link.link_id, True, link.unconsumed_output_disposition)
    for relation in model.hypothesis_relations:
        output_gap("hypothesis-relation", relation.relation_id, True, relation.unconsumed_output_disposition)
    used_mechanisms = {value for item in model.causal_candidates for value in item.mechanism_ids} | {
        value for item in model.storyline_hypotheses for value in item.mechanism_ids
    }
    used_confounders = {value for item in model.causal_candidates for value in item.confounder_ids} | {
        value for item in model.storyline_hypotheses for value in item.confounder_ids
    }
    used_scopes = {item.scope_id for item in model.causal_candidates if item.scope_id}
    for item in model.causal_mechanisms:
        output_gap("causal-mechanism", item.mechanism_id, item.mechanism_id in used_mechanisms, item.unconsumed_output_disposition)
    for item in model.confounder_reviews:
        output_gap("confounder", item.confounder_id, item.confounder_id in used_confounders, item.unconsumed_output_disposition)
    for item in model.causal_scopes:
        output_gap("causal-scope", item.scope_id, item.scope_id in used_scopes, item.unconsumed_output_disposition)
    for item in model.causal_candidates:
        output_gap("causal-candidate", item.causal_id, bool(item.hypothesis_id), item.unconsumed_output_disposition)
    for item in model.evidence_ablations:
        output_gap("evidence-ablation", item.ablation_id, bool(item.hypothesis_id or item.trace_id), item.unconsumed_output_disposition)
    for item in model.scenario_perturbations:
        output_gap("scenario-perturbation", item.perturbation_id, bool(item.hypothesis_id or item.trace_id), item.unconsumed_output_disposition)
    perturbation_ids = {item.perturbation_id for item in model.scenario_perturbations}
    for item in model.expected_sensitivities:
        output_gap("sensitivity", item.sensitivity_id, item.perturbation_id in perturbation_ids, item.unconsumed_output_disposition)
    refs = tuple(
        {
            "binding_id": binding.binding_id,
            "canonical_receipt_id": receipt.receipt_id,
            "native_receipt_refs": [
                item.to_dict()
                for item in sorted(binding.receipt_refs, key=lambda row: row.receipt_id)
            ],
        }
        for binding in sorted(model.interface_bindings, key=lambda item: item.binding_id)
    )
    return gaps, refs


def _trace_actual_objects(model: TraceGuardModel) -> dict[str, set[str]]:
    return {
        "source": {item.source_id for item in model.sources},
        "evidence": {item.evidence_id for item in model.evidence},
        "entity": {item.mention_id for item in model.entities},
        "entity-resolution": {
            entity_resolution_id(item.left_id, item.relation, item.right_id)
            for item in model.entity_resolutions
        },
        "location": {item.location_id for item in model.locations},
        "event": {item.event_id for item in model.events},
        "trace": {item.trace_id for item in model.traces},
        "stage": {f"stage:{item.trace_id}:{item.current_stage}" for item in model.traces},
        "hypothesis": {item.hypothesis_id for item in model.storyline_hypotheses},
        "hypothesis-evidence-link": {item.link_id for item in model.hypothesis_evidence_links},
        "hypothesis-relation": {item.relation_id for item in model.hypothesis_relations},
        "causal-boundary": {
            f"causal-boundary:{item.hypothesis_id}" for item in model.storyline_hypotheses
        },
        "causal-candidate": {item.causal_id for item in model.causal_candidates},
        "causal-mechanism": {item.mechanism_id for item in model.causal_mechanisms},
        "confounder-review": {item.confounder_id for item in model.confounder_reviews},
        "causal-scope": {item.scope_id for item in model.causal_scopes},
        "evidence-ablation": {item.ablation_id for item in model.evidence_ablations},
        "scenario-perturbation": {item.perturbation_id for item in model.scenario_perturbations},
        "sensitivity": {item.sensitivity_id for item in model.expected_sensitivities},
        "interface-binding": {item.binding_id for item in model.interface_bindings},
        "bounded-claim": {value for item in model.storyline_hypotheses for value in item.bounded_claim_ids},
        "handoff": {value for item in model.storyline_hypotheses for value in item.handoff_ids},
    }


def _trace_required_objects(universe: TraceTargetUniverse) -> dict[str, set[str]]:
    return {
        "source": set(universe.required_source_ids),
        "evidence": set(universe.required_evidence_ids),
        "entity": set(universe.required_entity_ids),
        "entity-resolution": set(universe.required_entity_resolution_ids),
        "location": set(universe.required_location_ids),
        "event": set(universe.required_event_ids),
        "trace": set(universe.required_trace_ids),
        "stage": set(universe.required_stage_ids),
        "hypothesis": set(universe.required_hypothesis_ids),
        "hypothesis-evidence-link": set(universe.required_hypothesis_evidence_link_ids),
        "hypothesis-relation": set(universe.required_hypothesis_relation_ids),
        "causal-boundary": set(universe.required_causal_boundary_ids),
        "causal-candidate": set(universe.required_causal_candidate_ids),
        "causal-mechanism": set(universe.required_causal_mechanism_ids),
        "confounder-review": set(universe.required_confounder_review_ids),
        "causal-scope": set(universe.required_causal_scope_ids),
        "evidence-ablation": set(universe.required_evidence_ablation_ids),
        "scenario-perturbation": set(universe.required_scenario_perturbation_ids),
        "sensitivity": set(universe.required_sensitivity_ids),
        "interface-binding": set(universe.required_interface_binding_ids),
        "bounded-claim": set(universe.required_bounded_claim_ids),
        "handoff": set(universe.required_handoff_ids),
    }


def _trace_native_target_subject(model: TraceGuardModel) -> dict[str, object]:
    return {
        "model_instance_id": str(model.metadata.get("model_instance_id", "")),
        "schema_id": SCHEMA_ID,
        "interface_model_fingerprint": trace_interface_model_fingerprint(model),
        "native_objects": {
            kind: sorted(values)
            for kind, values in sorted(_trace_actual_objects(model).items())
        },
    }


def trace_target_subject_fingerprint(model: TraceGuardModel) -> str:
    """Fingerprint only the native model subject, excluding target cases."""

    return _digest(_trace_native_target_subject(model))


def _trace_declared_failure_ids(model: TraceGuardModel) -> tuple[str, ...]:
    binding = model.metadata.get("guard_purpose_contract")
    if not isinstance(binding, Mapping):
        return ()
    values = binding.get("selected_failure_ids")
    if not isinstance(values, list):
        return ()
    return tuple(sorted(str(value) for value in values if str(value).strip()))


def _trace_target_denominator_fingerprint(
    model: TraceGuardModel,
    universe: TraceTargetUniverse,
    failure_class_ids: Iterable[str],
) -> str:
    return _digest(
        {
            "native_subject": _trace_native_target_subject(model),
            "known_good_case_ids": sorted(universe.known_good_case_ids),
            "known_bad_case_ids": sorted(universe.known_bad_case_ids),
            "failure_class_ids": sorted(str(value) for value in failure_class_ids),
        }
    )


def trace_target_purpose_fingerprint(model: TraceGuardModel) -> str:
    return _digest(
        {
            "model_instance_id": str(model.metadata.get("model_instance_id", "")),
            "purpose": str(model.metadata.get("purpose", "")),
            "bounded_claim_ids": sorted(
                value
                for item in model.storyline_hypotheses
                for value in item.bounded_claim_ids
            ),
            "handoff_ids": sorted(
                value for item in model.storyline_hypotheses for value in item.handoff_ids
            ),
        }
    )


def trace_target_request_fingerprint(model: TraceGuardModel) -> str:
    return trace_target_purpose_fingerprint(model)


def _noncurrent_trace_replay(
    model: TraceGuardModel,
    locator: str,
    status: Literal["unverified", "failed"],
    detail: str,
) -> NativeTargetMaterialReplay:
    marker = _digest({"locator": locator, "status": status})
    target_id = str(
        model.metadata.get("model_instance_id") or "traceguard-investigation"
    )
    request_fingerprint = trace_target_request_fingerprint(model)
    target_fingerprint = trace_target_subject_fingerprint(model)
    return NativeTargetMaterialReplay(
        adapter_id=TRACE_TARGET_ADAPTER_ID,
        adapter_version=TRACE_TARGET_ADAPTER_VERSION,
        request_id=content_addressed_request_id(request_fingerprint),
        request_fingerprint=request_fingerprint,
        input_id=locator or "unreplayable:trace-target-material",
        input_fingerprint=marker,
        target_id=target_id,
        target_revision=target_fingerprint,
        target_fingerprint=target_fingerprint,
        purpose_fingerprint=trace_target_purpose_fingerprint(model),
        material_locator=locator or "unreplayable:trace-target-material",
        material_media_type="application/json",
        material_fingerprint=marker,
        items=(),
        status=status,
        detail=detail,
    )


def replay_trace_target_material(
    model: TraceGuardModel, locator: str
) -> NativeTargetMaterialReplay:
    """TraceGuard-owned closed parser for stable-object target material."""

    body, material_fingerprint, gap = read_target_material_bytes(locator)
    if body is None:
        return _noncurrent_trace_replay(model, locator, "unverified", gap)
    try:
        raw = json.loads(body.decode("utf-8"))
        if not isinstance(raw, Mapping) or set(raw) != {
            "schema_version", "request_contract", "target_id", "target_revision",
            "native_subject", "known_good_case_ids", "known_bad_case_ids",
            "failure_class_ids",
        }:
            raise ValueError("trace target material has an unknown or missing root field")
        if raw.get("schema_version") != TRACE_TARGET_MATERIAL_SCHEMA:
            raise ValueError("trace target material schema is not current")
        request = raw.get("request_contract")
        subject = raw.get("native_subject")
        if not isinstance(request, Mapping) or set(request) != {
            "request_id", "model_instance_id", "purpose", "bounded_claim_ids",
            "handoff_ids",
        }:
            raise ValueError("trace request contract is not exact-current")
        if not isinstance(subject, Mapping) or set(subject) != {
            "model_instance_id", "schema_id", "interface_model_fingerprint",
            "native_objects",
        }:
            raise ValueError("trace native subject is not exact-current")
        native_objects = subject.get("native_objects")
        expected_kinds = set(_trace_actual_objects(model))
        if not isinstance(native_objects, Mapping) or set(native_objects) != expected_kinds:
            raise ValueError("trace native object kinds do not match the current adapter schema")
        items: list[TargetAuthorityItem] = []
        for kind in sorted(expected_kinds):
            values = native_objects[kind]
            if not isinstance(values, list) or any(not str(value).strip() for value in values):
                raise ValueError(f"trace native object kind {kind} must contain ids")
            if len(values) != len(set(str(value) for value in values)):
                raise ValueError(f"trace native object kind {kind} contains duplicate ids")
            items.extend(
                TargetAuthorityItem(kind, str(object_id), "required")
                for object_id in values
            )
        for key, kind in (
            ("known_good_case_ids", "known-good-case"),
            ("known_bad_case_ids", "known-bad-case"),
            ("failure_class_ids", "failure-class"),
        ):
            values = raw[key]
            if not isinstance(values, list) or any(not str(value).strip() for value in values):
                raise ValueError(f"trace {key} must contain ids")
            items.extend(
                TargetAuthorityItem(kind, str(object_id), "required")
                for object_id in values
            )
        request_material = {
            "model_instance_id": str(request["model_instance_id"]),
            "purpose": str(request["purpose"]),
            "bounded_claim_ids": [str(value) for value in request["bounded_claim_ids"]],
            "handoff_ids": [str(value) for value in request["handoff_ids"]],
        }
        request_fingerprint = _digest(request_material)
        target_fingerprint = _digest(
            {
                "native_subject": dict(subject),
                "known_good_case_ids": sorted(str(value) for value in raw["known_good_case_ids"]),
                "known_bad_case_ids": sorted(str(value) for value in raw["known_bad_case_ids"]),
                "failure_class_ids": sorted(str(value) for value in raw["failure_class_ids"]),
            }
        )
        return NativeTargetMaterialReplay(
            adapter_id=TRACE_TARGET_ADAPTER_ID,
            adapter_version=TRACE_TARGET_ADAPTER_VERSION,
            request_id=str(request["request_id"]),
            request_fingerprint=request_fingerprint,
            input_id=locator,
            input_fingerprint=material_fingerprint,
            target_id=str(raw["target_id"]),
            target_revision=str(raw["target_revision"]),
            target_fingerprint=target_fingerprint,
            purpose_fingerprint=_digest(request_material),
            material_locator=locator,
            material_media_type="application/json",
            material_fingerprint=material_fingerprint,
            items=tuple(items),
            status="current",
        )
    except Exception as exc:
        return _noncurrent_trace_replay(model, locator, "failed", str(exc))


def _bind_trace_target_authority(
    model: TraceGuardModel,
    universe: TraceTargetUniverse,
    *,
    expected_target_anchor: ExpectedTargetAnchor,
) -> TraceTargetUniverse:
    replay = replay_trace_target_material(model, expected_target_anchor.material_locator)
    authority = _issue_replayed_target_authority(
        member_id="traceguard",
        owner_id=TRACE_TARGET_AUTHORITY_OWNER,
        tool_id=TRACE_TARGET_AUTHORITY_TOOL,
        tool_revision="1",
        expected_target_anchor=expected_target_anchor,
        replay=replay,
    )
    return replace(universe, target_authority=authority)


def _universe_gaps(model: TraceGuardModel, universe: TraceTargetUniverse) -> list[TraceBlueprintGap]:
    actual = _trace_actual_objects(model)
    required = _trace_required_objects(universe)
    gaps = [
        TraceBlueprintGap(f"omitted-universe-{kind}", object_id, "required by independent universe")
        for kind in required
        for object_id in sorted(required[kind] - actual[kind])
    ]
    gaps.extend(
        TraceBlueprintGap(f"undeclared-universe-{kind}", object_id, "current native model object is absent from independent universe")
        for kind in required
        for object_id in sorted(actual[kind] - required[kind])
    )
    if not universe.known_good_case_ids:
        gaps.append(TraceBlueprintGap("missing-known-good", universe.universe_id, "native good case required"))
    if not universe.known_bad_case_ids:
        gaps.append(TraceBlueprintGap("missing-known-bad", universe.universe_id, "native bad case required"))
    authority = universe.target_authority
    if authority is None:
        gaps.append(
            TraceBlueprintGap(
                "missing-target-purpose-authority",
                universe.universe_id,
                "independent TraceGuard native inventory authority required",
            )
        )
    else:
        subject = _trace_target_denominator_fingerprint(
            model,
            universe,
            _trace_declared_failure_ids(model),
        )
        target_id = str(model.metadata.get("model_instance_id") or "traceguard-investigation")
        checks = (
            (authority.member_id == "traceguard", "target-authority-member-mismatch", authority.member_id),
            (authority.owner_id == TRACE_TARGET_AUTHORITY_OWNER, "target-authority-owner-mismatch", authority.owner_id),
            (authority.tool_id == TRACE_TARGET_AUTHORITY_TOOL, "target-authority-tool-mismatch", authority.tool_id),
            (authority.target_id == target_id, "target-authority-target-mismatch", authority.target_id),
            (authority.target_revision == authority.target_fingerprint, "target-authority-revision-mismatch", authority.target_revision),
            (authority.request_fingerprint == trace_target_request_fingerprint(model), "target-authority-request-stale", authority.request_fingerprint),
            (authority.target_fingerprint == subject, "target-authority-target-stale", authority.target_fingerprint),
            (authority.purpose_fingerprint == trace_target_purpose_fingerprint(model), "target-authority-purpose-stale", authority.purpose_fingerprint),
            (authority.status == "current", "target-authority-not-current", authority.status),
            (authority.authority_fingerprint == authority.expected_fingerprint, "target-authority-fingerprint-mismatch", authority.authority_id),
        )
        for ok, code, detail in checks:
            if not ok:
                gaps.append(TraceBlueprintGap(code, universe.universe_id, detail))
        for kind, current_objects in actual.items():
            authoritative = authority.ids(kind)
            declared_objects = required[kind]
            for object_id in sorted(authoritative - declared_objects):
                gaps.append(TraceBlueprintGap(f"target-authority-omitted-{kind}", object_id, "missing from member denominator"))
            for object_id in sorted(declared_objects - authoritative):
                gaps.append(TraceBlueprintGap(f"target-authority-foreign-{kind}", object_id, "not owned by target authority"))
            for object_id in sorted(authoritative - current_objects):
                gaps.append(TraceBlueprintGap(f"target-authority-missing-{kind}", object_id, "missing from current native model"))
            for object_id in sorted(current_objects - authoritative):
                gaps.append(TraceBlueprintGap(f"target-authority-unowned-{kind}", object_id, "current native model object is absent from target authority"))
        for kind, member_ids in (
            ("known-good-case", set(universe.known_good_case_ids)),
            ("known-bad-case", set(universe.known_bad_case_ids)),
        ):
            authoritative = authority.ids(kind)
            for object_id in sorted(authoritative - member_ids):
                gaps.append(TraceBlueprintGap(f"target-authority-omitted-{kind}", object_id, "missing from member case denominator"))
            for object_id in sorted(member_ids - authoritative):
                gaps.append(TraceBlueprintGap(f"target-authority-foreign-{kind}", object_id, "not owned by target authority"))
        declared_failure_ids = set(_trace_declared_failure_ids(model))
        authoritative_failure_ids = authority.ids("failure-class")
        if not authoritative_failure_ids:
            gaps.append(TraceBlueprintGap("missing-target-failure-class", universe.universe_id, "native owner declared no protected failure class"))
        for object_id in sorted(authoritative_failure_ids - declared_failure_ids):
            gaps.append(TraceBlueprintGap("target-authority-omitted-failure-class", object_id, "missing from member purpose denominator"))
        for object_id in sorted(declared_failure_ids - authoritative_failure_ids):
            gaps.append(TraceBlueprintGap("target-authority-foreign-failure-class", object_id, "not owned by target authority"))
        for item in authority.unresolved_items:
            gaps.append(TraceBlueprintGap("target-authority-unresolved", item.object_id, item.reason))
        replay = replay_trace_target_material(
            model,
            authority.expected_target_anchor.material_locator
            if authority.native_attestation is not None
            else "",
        )
        for code, detail in verify_registered_target_authority(authority, replay):
            gaps.append(TraceBlueprintGap(code, universe.universe_id, detail))
    return gaps


def _causal_boundaries(model: TraceGuardModel, receipt: InferenceReceipt) -> tuple[dict[str, object], ...]:
    projections = {item.hypothesis_id: item for item in receipt.hypothesis_projections}
    candidates = {item.hypothesis_id: item for item in model.causal_candidates}
    return tuple(
        {
            "boundary_id": f"causal-boundary:{hypothesis.hypothesis_id}",
            "hypothesis_id": hypothesis.hypothesis_id,
            "native_causal_status": projections.get(hypothesis.hypothesis_id).causal_status if projections.get(hypothesis.hypothesis_id) else "not_run",
            "bounded_non_causal": hypothesis.bounded_non_causal,
            "causal_candidate_id": candidates.get(hypothesis.hypothesis_id).causal_id if candidates.get(hypothesis.hypothesis_id) else "",
            "mechanism_ids": sorted(hypothesis.mechanism_ids),
            "confounder_ids": sorted(hypothesis.confounder_ids),
            "alternative_ids": sorted(hypothesis.alternative_to),
            "claim_boundary": projections.get(hypothesis.hypothesis_id).claim_boundary if projections.get(hypothesis.hypothesis_id) else "No canonical hypothesis projection is current.",
            "formal_causal_identification_licensed": False,
        }
        for hypothesis in sorted(model.storyline_hypotheses, key=lambda item: item.hypothesis_id)
    )


def _trace_native_receipt_expectations(
    model: TraceGuardModel,
    receipt: InferenceReceipt,
    universe: TraceTargetUniverse,
) -> tuple[NativeReceiptExpectation, ...]:
    authority = universe.target_authority
    if authority is None:
        return ()
    anchor = authority.expected_target_anchor
    task_id = str(model.metadata.get("model_instance_id") or "traceguard-investigation")
    result: list[NativeReceiptExpectation] = []
    for binding in model.interface_bindings:
        for native in binding.receipt_refs:
            result.append(
                native_receipt_expectation(
                    receipt_id=native.receipt_id,
                    member_id="traceguard",
                    native_owner_id="traceguard.interface",
                    checker_id="researchguard.trace.interface",
                    checker_version="1",
                    checker_entrypoint="researchguard.trace.blueprint:check_blueprint",
                    task_id=task_id,
                    expected_target_anchor_id=anchor.anchor_id,
                    expected_target_anchor_fingerprint=anchor.anchor_fingerprint,
                    native_model_id=binding.producer_id,
                    model_fingerprint=native.model_fingerprint,
                    request_fingerprint=_digest(
                        {
                            "binding_id": binding.binding_id,
                            "producer_kind": binding.producer_kind,
                            "consumer_kind": binding.consumer_kind,
                            "payload_schema_id": binding.payload_schema_id,
                            "expected_target_anchor_id": anchor.anchor_id,
                        }
                    ),
                    input_fingerprint=_digest(
                        {"result_fingerprint": native.result_fingerprint}
                    ),
                    result_fingerprint=_digest(native.to_dict()),
                )
            )
    result.append(
        native_receipt_expectation(
            receipt_id=receipt.receipt_id,
            member_id="traceguard",
            native_owner_id="traceguard.canonical-inference",
            checker_id="researchguard.trace.canonical-inference",
            checker_version="1",
            checker_entrypoint="researchguard.trace.blueprint:check_blueprint",
            task_id=task_id,
            expected_target_anchor_id=anchor.anchor_id,
            expected_target_anchor_fingerprint=anchor.anchor_fingerprint,
            native_model_id=task_id,
            model_fingerprint=f"sha256:{receipt.model_fingerprint}",
            request_fingerprint=_digest(
                {
                    "schema_id": receipt.schema_id,
                    "policy_id": receipt.policy_id,
                    "solver_id": receipt.solver_id,
                    "expected_target_anchor_id": anchor.anchor_id,
                }
            ),
            input_fingerprint=_digest(
                {"problem_fingerprint": receipt.problem_fingerprint}
            ),
            result_fingerprint=_digest(receipt.to_dict()),
        )
    )
    purpose = model.metadata.get("guard_purpose_contract", {})
    result.append(
        native_receipt_expectation(
            receipt_id=f"trace-purpose:{universe.universe_id}",
            member_id="traceguard",
            native_owner_id="traceguard.native-purpose",
            checker_id="researchguard.trace.native-purpose",
            checker_version="1",
            checker_entrypoint="researchguard.trace.blueprint:check_blueprint",
            task_id=task_id,
            expected_target_anchor_id=anchor.anchor_id,
            expected_target_anchor_fingerprint=anchor.anchor_fingerprint,
            native_model_id=task_id,
            model_fingerprint=f"sha256:{trace_model_fingerprint(model)}",
            request_fingerprint=_digest(
                {
                    "universe_id": universe.universe_id,
                    "expected_target_anchor_id": anchor.anchor_id,
                }
            ),
            input_fingerprint=_digest(purpose),
            result_fingerprint=_digest(
                {
                    "known_good_case_ids": list(universe.known_good_case_ids),
                    "known_bad_case_ids": list(universe.known_bad_case_ids),
                    "selected_failure_ids": sorted(
                        purpose.get("selected_failure_ids", [])
                        if isinstance(purpose, Mapping)
                        else []
                    ),
                }
            ),
        )
    )
    return tuple(result)


def check_blueprint(
    model: TraceGuardModel,
    receipt: InferenceReceipt,
    universe: TraceTargetUniverse,
    *,
    candidate_path: str | None = None,
) -> TraceBlueprintResult:
    gaps: list[TraceBlueprintGap] = []
    try:
        validate_references(model)
    except SchemaError as exc:
        gaps.append(TraceBlueprintGap("invalid-native-reference", str(model.metadata.get("model_instance_id", "")), str(exc)))
    receipt_failed = False
    try:
        verify_inference_receipt(receipt)
    except Exception as exc:
        gaps.append(TraceBlueprintGap("invalid-canonical-receipt", receipt.receipt_id, str(exc)))
        receipt_failed = True
    current_model_fingerprint = trace_model_fingerprint(model)
    receipt_stale = receipt.model_fingerprint != current_model_fingerprint
    if receipt_stale:
        gaps.append(TraceBlueprintGap("stale-canonical-receipt", receipt.receipt_id, "model fingerprint mismatch"))
    if receipt.schema_id != SCHEMA_ID or receipt.solver_status.lower() not in {"solved", "solved inaccurate"}:
        gaps.append(TraceBlueprintGap("canonical-solver-not-current", receipt.receipt_id, receipt.solver_status))
        receipt_failed = True
    hierarchy = project_hierarchy(model)
    orphan_nodes = [item for item in hierarchy if item.disposition == "unresolved-orphan"]
    gaps.extend(
        TraceBlueprintGap("unresolved-hierarchy-owner", item.native_id, item.kind)
        for item in orphan_nodes
    )
    projection_hierarchy_gaps = _hierarchy_gaps(hierarchy)
    gaps.extend(projection_hierarchy_gaps)
    gaps.extend(_identity_gaps(model))
    interface_gaps, interface_refs = _interface_gaps(model, receipt)
    gaps.extend(interface_gaps)
    gaps.extend(_universe_gaps(model, universe))
    purpose_binding: Mapping[str, object] | None = None
    if candidate_path is None:
        gaps.append(TraceBlueprintGap("native-purpose-replay-not-run", universe.universe_id, "candidate_path is required for current purpose replay"))
    else:
        try:
            purpose_binding = require_current_guard_purpose_binding(
                model.to_dict(), candidate_path=candidate_path
            )
        except (GuardPurposeContractError, OSError, ValueError) as exc:
            gaps.append(TraceBlueprintGap("native-purpose-replay-failed", universe.universe_id, str(exc)))
    if purpose_binding is not None:
        if set(purpose_binding.get("known_good_case_ids", [])) != set(universe.known_good_case_ids):
            gaps.append(TraceBlueprintGap("native-good-case-denominator-mismatch", universe.universe_id, "purpose binding and universe differ"))
        if set(purpose_binding.get("known_bad_case_ids", [])) != set(universe.known_bad_case_ids):
            gaps.append(TraceBlueprintGap("native-bad-case-denominator-mismatch", universe.universe_id, "purpose binding and universe differ"))
        authority = universe.target_authority
        selected_failure_ids = set(purpose_binding.get("selected_failure_ids", []))
        authoritative_failure_ids = authority.ids("failure-class") if authority else set()
        if selected_failure_ids != authoritative_failure_ids:
            gaps.append(
                TraceBlueprintGap(
                    "native-failure-class-denominator-mismatch",
                    universe.universe_id,
                    "purpose binding and target authority differ",
                )
            )
    gaps.extend(
        TraceBlueprintGap(code, detail.split(":", 1)[0], detail)
        for code, detail in resolve_expected_native_receipts(
            universe.native_receipt_refs,
            _trace_native_receipt_expectations(model, receipt, universe),
        )
    )
    hierarchy_fp = _digest([item.to_dict() for item in hierarchy])
    interface_fp = interface_fingerprint(model)
    causal = _causal_boundaries(model, receipt)
    live_alternatives = tuple(
        sorted(
            item.hypothesis_id
            for item in receipt.hypothesis_projections
            if item.live
        )
    )
    hierarchy_codes = {"invalid-native-reference", "unresolved-hierarchy-owner", *(item.code for item in projection_hierarchy_gaps)}
    interface_codes = {
        "missing-interface", "duplicate-interface", "unexpected-interface",
        "stale-interface-producer", "stale-interface-consumer",
        "missing-interface-native-receipt", "duplicate-interface-native-receipt",
        "interface-receipt-producer-kind-mismatch", "interface-receipt-producer-mismatch",
        "interface-receipt-result-stale", "interface-receipt-model-stale",
        "interface-receipt-task-mismatch", "interface-receipt-not-current",
        "interface-receipt-fingerprint-mismatch",
        "required-interface-not-consumed", "unconsumed-evidence-output",
        "unconsumed-event-output", "unconsumed-trace-output", "unconsumed-hypothesis-output",
        "missing-evidence-input", "missing-event-input", "missing-trace-input",
        "invalid-output-disposition",
        *(item.code for item in interface_gaps if item.code.startswith("unconsumed-") or item.code.startswith("unresolved-")),
    }
    receipt_codes = {
        "invalid-canonical-receipt", "stale-canonical-receipt", "canonical-solver-not-current",
        "native-purpose-replay-not-run", "native-purpose-replay-failed",
        "native-good-case-denominator-mismatch", "native-bad-case-denominator-mismatch",
        "native-failure-class-denominator-mismatch",
    }
    hierarchy_gaps = [item for item in gaps if item.code in hierarchy_codes]
    identity_gaps = [item for item in gaps if item.code.startswith("incomplete-") or item.code in {"stale-object-fingerprint", "stale-evidence-content"}]
    interface_layer_gaps = [item for item in gaps if item.code in interface_codes]
    universe_gaps = [
        item
        for item in gaps
        if item.code.startswith("omitted-universe")
        or item.code.startswith("undeclared-universe")
        or item.code.startswith("missing-known")
        or item.code.startswith("target-authority-")
        or item.code in {"missing-target-purpose-authority", "missing-target-failure-class"}
    ]
    receipt_gaps = [
        item
        for item in gaps
        if item.code in receipt_codes or item.code.startswith("native-receipt-")
    ]
    categorized = {*hierarchy_gaps, *identity_gaps, *interface_layer_gaps, *universe_gaps, *receipt_gaps}
    residual_gaps = [item for item in gaps if item not in categorized]
    layer_definitions = (
        ("deterministic-hierarchy", hierarchy_gaps),
        ("semantic-identities", identity_gaps),
        ("typed-interfaces", interface_layer_gaps),
        ("independent-universe", universe_gaps),
        ("canonical-receipt-bound-blueprint", [*receipt_gaps, *residual_gaps]),
    )
    layer_statuses: list[dict[str, object]] = []
    deepest = "native-objects"
    first = ""
    prior_passed = True
    for layer_id, layer_gaps in layer_definitions:
        if not prior_passed:
            layer_statuses.append({"layer_id": layer_id, "status": "not_run", "gap_ids": []})
            continue
        if layer_gaps:
            gap_ids = [f"{item.code}:{item.object_id}" for item in layer_gaps]
            layer_statuses.append({"layer_id": layer_id, "status": "failed", "gap_ids": gap_ids})
            first = gap_ids[0]
            prior_passed = False
        else:
            layer_statuses.append({"layer_id": layer_id, "status": "passed", "gap_ids": []})
            deepest = layer_id
    if receipt_failed:
        status: Literal["complete", "incomplete", "stale", "failed"] = "failed"
    elif receipt_stale:
        status = "stale"
    else:
        status = "complete" if not gaps else "incomplete"
    payload = {
        "model_fingerprint": current_model_fingerprint,
        "universe": universe.to_dict(),
        "receipt": project_canonical_receipt_identity(receipt),
        "hierarchy": [item.to_dict() for item in hierarchy],
        "interfaces": [asdict(item) for item in sorted(model.interface_bindings, key=lambda item: item.binding_id)],
        "gaps": [item.to_dict() for item in gaps],
        "causal_boundaries": list(causal),
    }
    return TraceBlueprintResult(
        status=status,
        model_fingerprint="sha256:" + current_model_fingerprint,
        universe_fingerprint=universe.fingerprint,
        canonical_receipt_id=receipt.receipt_id,
        canonical_problem_fingerprint=receipt.problem_fingerprint,
        hierarchy_fingerprint=hierarchy_fp,
        interface_fingerprint=interface_fp,
        blueprint_fingerprint=_digest(payload),
        deepest_proven_layer=deepest,
        first_unresolved_gap=first,
        live_alternative_ids=live_alternatives,
        causal_boundaries=causal,
        hierarchy=hierarchy,
        interface_receipt_refs=interface_refs,
        gaps=tuple(gaps),
        layer_statuses=tuple(layer_statuses),
    )


def impact_blueprint(
    model: TraceGuardModel,
    receipt: InferenceReceipt,
    changed_ids: Iterable[str],
    universe: TraceTargetUniverse | None = None,
    *,
    candidate_path: str | None = None,
) -> dict[str, object]:
    changed = set(changed_ids)
    qualification = (
        check_blueprint(
            model, receipt, universe, candidate_path=candidate_path
        )
        if universe is not None
        else None
    )
    authority = universe.target_authority if universe is not None else None
    if qualification is None or qualification.status != "complete":
        return {
            "query_status": "blocked",
            "qualification_status": (
                qualification.status if qualification is not None else "not_run"
            ),
            "qualification_model_fingerprint": (
                qualification.model_fingerprint if qualification is not None else ""
            ),
            "qualification_gaps": (
                [item.to_dict() for item in qualification.gaps]
                if qualification is not None
                else [
                    TraceBlueprintGap(
                        "missing-target-universe",
                        str(model.metadata.get("model_instance_id", "traceguard")),
                        "impact requires one current TraceGuard blueprint qualification",
                    ).to_dict()
                ]
            ),
            "target_authority_status": authority.status if authority else "not_run",
            "target_material_status": (
                authority.native_attestation.status
                if authority and authority.native_attestation
                else "not_run"
            ),
            "model_fingerprint": "sha256:" + trace_model_fingerprint(model),
            "canonical_receipt_id": receipt.receipt_id,
            "changed_ids": sorted(changed),
            "affected_source_ids": [],
            "affected_evidence_ids": [],
            "affected_entity_ids": [],
            "affected_entity_resolution_ids": [],
            "affected_location_ids": [],
            "affected_event_ids": [],
            "affected_trace_ids": [],
            "affected_hypothesis_ids": [],
            "affected_causal_candidate_ids": [],
            "affected_causal_mechanism_ids": [],
            "affected_confounder_ids": [],
            "affected_causal_scope_ids": [],
            "affected_hypothesis_evidence_link_ids": [],
            "affected_hypothesis_relation_ids": [],
            "affected_interface_binding_ids": [],
            "affected_evidence_ablation_ids": [],
            "affected_scenario_perturbation_ids": [],
            "affected_perturbation_ids": [],
            "affected_sensitivity_ids": [],
            "affected_depth_receipt_ids": [],
            "affected_holdout_ids": [],
            "affected_narrative_fragment_ids": [],
            "affected_handoff_ids": [],
            "canonical_receipt_stale": False,
            "live_alternative_ids": [],
            "unknown_dependency_ids": [],
            "unknown_ownership": False,
            "partial_result_suppressed": True,
        }

    def tokens(*values: object) -> set[str]:
        return {str(value) for value in values if value not in (None, "")}

    def object_tokens(value: object) -> set[str]:
        collected: set[str] = set()

        def visit(item: object) -> None:
            if isinstance(item, Mapping):
                for child in item.values():
                    visit(child)
            elif isinstance(item, (list, tuple, set)):
                for child in item:
                    visit(child)
            elif item not in (None, ""):
                collected.add(str(item))

        visit(asdict(value) if hasattr(value, "__dataclass_fields__") else value)
        return collected

    source_tokens = {
        item.source_id: tokens(
            item.source_id,
            item.object_fingerprint,
            item.source_revision,
            item.content_fingerprint,
            item.url,
            item.locator,
            item.provider_id,
            item.provider_revision,
            item.retrieval_request_fingerprint,
            item.lineage_id,
        )
        for item in model.sources
    }
    evidence_tokens = {
        item.evidence_id: tokens(
            item.evidence_id,
            item.object_fingerprint,
            item.source_revision,
            item.content_fingerprint,
            item.locator,
            item.normalizer_id,
            item.normalizer_revision,
            item.normalizer_fingerprint,
            item.extractor_id,
            item.extractor_revision,
            item.extractor_fingerprint,
        )
        for item in model.evidence
    }
    event_tokens = {
        item.event_id: tokens(
            item.event_id,
            item.object_fingerprint,
            item.extractor_id,
            item.extractor_revision,
            item.extractor_fingerprint,
        )
        for item in model.events
    }
    trace_tokens = {
        item.trace_id: tokens(
            item.trace_id,
            item.object_fingerprint,
            item.normalizer_id,
            item.normalizer_revision,
            item.normalizer_fingerprint,
        )
        for item in model.traces
    }
    hypothesis_tokens = {
        item.hypothesis_id: tokens(
            item.hypothesis_id,
            item.object_fingerprint,
            item.normalizer_id,
            item.normalizer_revision,
            item.normalizer_fingerprint,
            *item.bounded_claim_ids,
            *item.handoff_ids,
            f"causal-boundary:{item.hypothesis_id}",
        )
        for item in model.storyline_hypotheses
    }
    entity_tokens = {item.mention_id: object_tokens(item) for item in model.entities}
    resolution_tokens = {
        entity_resolution_id(item.left_id, item.relation, item.right_id): object_tokens(item)
        | {entity_resolution_id(item.left_id, item.relation, item.right_id)}
        for item in model.entity_resolutions
    }
    location_tokens = {item.location_id: object_tokens(item) for item in model.locations}
    link_tokens = {item.link_id: object_tokens(item) for item in model.hypothesis_evidence_links}
    relation_tokens = {item.relation_id: object_tokens(item) for item in model.hypothesis_relations}
    mechanism_tokens = {item.mechanism_id: object_tokens(item) for item in model.causal_mechanisms}
    confounder_tokens = {item.confounder_id: object_tokens(item) for item in model.confounder_reviews}
    scope_tokens = {item.scope_id: object_tokens(item) for item in model.causal_scopes}
    causal_tokens = {item.causal_id: object_tokens(item) for item in model.causal_candidates}
    ablation_tokens = {item.ablation_id: object_tokens(item) for item in model.evidence_ablations}
    perturbation_tokens = {item.perturbation_id: object_tokens(item) for item in model.scenario_perturbations}
    sensitivity_tokens = {item.sensitivity_id: object_tokens(item) for item in model.expected_sensitivities}
    affected_sources = {item for item, values in source_tokens.items() if changed & values}
    affected_evidence = {item for item, values in evidence_tokens.items() if changed & values}
    affected_entities = {item for item, values in entity_tokens.items() if changed & values}
    affected_resolutions = {item for item, values in resolution_tokens.items() if changed & values}
    affected_locations = {item for item, values in location_tokens.items() if changed & values}
    affected_events = {item for item, values in event_tokens.items() if changed & values}
    affected_traces = {item for item, values in trace_tokens.items() if changed & values}
    affected_hypotheses = {
        item for item, values in hypothesis_tokens.items() if changed & values
    }
    affected_links = {item for item, values in link_tokens.items() if changed & values}
    affected_relations = {item for item, values in relation_tokens.items() if changed & values}
    affected_mechanisms = {item for item, values in mechanism_tokens.items() if changed & values}
    affected_confounders = {item for item, values in confounder_tokens.items() if changed & values}
    affected_scopes = {item for item, values in scope_tokens.items() if changed & values}
    affected_causal = {item for item, values in causal_tokens.items() if changed & values}
    affected_ablations = {item for item, values in ablation_tokens.items() if changed & values}
    affected_scenario_perturbations = {item for item, values in perturbation_tokens.items() if changed & values}
    affected_perturbations = affected_ablations | affected_scenario_perturbations
    affected_sensitivities = {item for item, values in sensitivity_tokens.items() if changed & values}
    affected_bindings = {
        item.binding_id
        for item in model.interface_bindings
        if changed
        & tokens(
            item.binding_id,
            item.producer_object_fingerprint,
            item.consumer_object_fingerprint,
            item.payload_schema_id,
            *(
                value
                for receipt_ref in item.receipt_refs
                for value in object_tokens(receipt_ref.to_dict())
            ),
        )
    }
    for resolution in model.entity_resolutions:
        resolution_id = entity_resolution_id(resolution.left_id, resolution.relation, resolution.right_id)
        if resolution_id in affected_resolutions or changed & tokens(resolution.left_id, resolution.right_id):
            affected_resolutions.add(resolution_id)
            affected_entities.update((resolution.left_id, resolution.right_id))
    for link in model.hypothesis_evidence_links:
        if link.link_id in affected_links:
            affected_evidence.add(link.evidence_id)
            affected_hypotheses.add(link.hypothesis_id)
    for relation in model.hypothesis_relations:
        if relation.relation_id in affected_relations:
            affected_hypotheses.update(
                (relation.left_hypothesis_id, relation.right_hypothesis_id)
            )
    for binding in model.interface_bindings:
        if binding.binding_id not in affected_bindings:
            continue
        endpoint_sets = {
            "source": affected_sources,
            "evidence_fact": affected_evidence,
            "event": affected_events,
            "trace": affected_traces,
            "hypothesis": affected_hypotheses,
        }
        if binding.producer_kind in endpoint_sets:
            endpoint_sets[binding.producer_kind].add(binding.producer_id)
        if binding.consumer_kind in endpoint_sets:
            endpoint_sets[binding.consumer_kind].add(binding.consumer_id)
        elif binding.consumer_kind in {"bounded_claim", "handoff"}:
            affected_hypotheses.update(
                item.hypothesis_id
                for item in model.storyline_hypotheses
                if binding.consumer_id
                in (
                    item.bounded_claim_ids
                    if binding.consumer_kind == "bounded_claim"
                    else item.handoff_ids
                )
            )
    for evidence in model.evidence:
        if evidence.source_id in affected_sources:
            affected_evidence.add(evidence.evidence_id)
    for event in model.events:
        if (
            affected_evidence & set(event.evidence_ids)
            or affected_entities & set(event.actor_ids + event.object_ids + event.technology_ids)
            or affected_locations & set(event.location_ids)
        ):
            affected_events.add(event.event_id)
    for trace in model.traces:
        if (
            affected_events & set(trace.event_ids)
            or affected_entities & set(trace.entity_ids)
            or affected_locations & set(trace.location_ids)
        ):
            affected_traces.add(trace.trace_id)
    for hypothesis in model.storyline_hypotheses:
        if affected_traces & set(hypothesis.trace_ids) or affected_events & set(hypothesis.event_ids) or affected_evidence & set(hypothesis.evidence_ids + hypothesis.contradicting_evidence_ids):
            affected_hypotheses.add(hypothesis.hypothesis_id)
    for relation in model.hypothesis_relations:
        if relation.relation in {"alternative", "competes_with"} and affected_hypotheses & {
            relation.left_hypothesis_id,
            relation.right_hypothesis_id,
        }:
            affected_relations.add(relation.relation_id)
            affected_hypotheses.update(
                (relation.left_hypothesis_id, relation.right_hypothesis_id)
            )
    for mechanism in model.causal_mechanisms:
        if mechanism.hypothesis_id in affected_hypotheses or affected_evidence & set(mechanism.evidence_ids):
            affected_mechanisms.add(mechanism.mechanism_id)
    for confounder in model.confounder_reviews:
        if confounder.hypothesis_id in affected_hypotheses or affected_evidence & set(confounder.evidence_ids):
            affected_confounders.add(confounder.confounder_id)
    for scope in model.causal_scopes:
        if affected_locations & set(scope.location_ids):
            affected_scopes.add(scope.scope_id)
    for candidate in model.causal_candidates:
        if (
            candidate.hypothesis_id in affected_hypotheses
            or affected_events & set(candidate.cause_event_ids + candidate.effect_event_ids)
            or affected_mechanisms & set(candidate.mechanism_ids)
            or affected_confounders & set(candidate.confounder_ids)
            or candidate.scope_id in affected_scopes
        ):
            affected_causal.add(candidate.causal_id)
    affected_hypotheses.update(
        item.hypothesis_id for item in model.causal_candidates if item.causal_id in affected_causal
    )
    for item in model.evidence_ablations:
        if (
            item.hypothesis_id in affected_hypotheses
            or item.trace_id in affected_traces
            or affected_evidence & set(item.remove_evidence_ids)
            or affected_events & set(item.remove_event_ids)
        ):
            affected_ablations.add(item.ablation_id)
            affected_perturbations.add(item.ablation_id)
    for item in model.scenario_perturbations:
        if (
            item.hypothesis_id in affected_hypotheses
            or item.trace_id in affected_traces
            or affected_evidence & set(item.remove_evidence_ids + item.add_evidence_ids)
            or affected_events & set(item.remove_event_ids + item.add_event_ids)
        ):
            affected_scenario_perturbations.add(item.perturbation_id)
            affected_perturbations.add(item.perturbation_id)
    for sensitivity in model.expected_sensitivities:
        if sensitivity.perturbation_id in affected_perturbations:
            affected_sensitivities.add(sensitivity.sensitivity_id)
    endpoint_affected = affected_sources | affected_evidence | affected_events | affected_traces | affected_hypotheses
    affected_bindings.update(
        item.binding_id
        for item in model.interface_bindings
        if item.producer_id in endpoint_affected or item.consumer_id in endpoint_affected
    )
    affected_claims = {
        claim_id for item in model.storyline_hypotheses if item.hypothesis_id in affected_hypotheses for claim_id in item.bounded_claim_ids
    }
    affected_handoffs = {
        handoff_id for item in model.storyline_hypotheses if item.hypothesis_id in affected_hypotheses for handoff_id in item.handoff_ids
    }
    known = set().union(
        *source_tokens.values(),
        *evidence_tokens.values(),
        *entity_tokens.values(),
        *resolution_tokens.values(),
        *location_tokens.values(),
        *event_tokens.values(),
        *trace_tokens.values(),
        *hypothesis_tokens.values(),
        *link_tokens.values(),
        *relation_tokens.values(),
        *mechanism_tokens.values(),
        *confounder_tokens.values(),
        *scope_tokens.values(),
        *causal_tokens.values(),
        *ablation_tokens.values(),
        *perturbation_tokens.values(),
        *sensitivity_tokens.values(),
        (
            value
            for item in model.interface_bindings
            for value in tokens(
                item.binding_id,
                item.producer_object_fingerprint,
                item.consumer_object_fingerprint,
                item.payload_schema_id,
                *(
                    value
                    for receipt_ref in item.receipt_refs
                    for value in object_tokens(receipt_ref.to_dict())
                ),
            )
        ),
    )
    receipt_tokens = object_tokens(receipt.to_dict())
    known.update(receipt_tokens)
    if changed & receipt_tokens:
        affected_traces.update(item.trace_id for item in model.traces)
        affected_hypotheses.update(item.hypothesis_id for item in model.storyline_hypotheses)
    if universe is not None:
        universe_tokens = object_tokens(universe.to_dict())
        known.update(universe_tokens)
        if changed & {
            universe.universe_id,
            universe.fingerprint,
            *universe.known_good_case_ids,
            *universe.known_bad_case_ids,
        }:
            affected_sources.update(item.source_id for item in model.sources)
            affected_evidence.update(item.evidence_id for item in model.evidence)
            affected_entities.update(item.mention_id for item in model.entities)
            affected_locations.update(item.location_id for item in model.locations)
            affected_events.update(item.event_id for item in model.events)
            affected_traces.update(item.trace_id for item in model.traces)
            affected_hypotheses.update(item.hypothesis_id for item in model.storyline_hypotheses)
    if affected_hypotheses:
        affected_claims.update(
            claim_id
            for item in model.storyline_hypotheses
            if item.hypothesis_id in affected_hypotheses
            for claim_id in item.bounded_claim_ids
        )
        affected_handoffs.update(
            handoff_id
            for item in model.storyline_hypotheses
            if item.hypothesis_id in affected_hypotheses
            for handoff_id in item.handoff_ids
        )
        affected_bindings.update(
            item.binding_id
            for item in model.interface_bindings
            if item.producer_id in affected_hypotheses or item.consumer_id in affected_hypotheses | affected_claims | affected_handoffs
        )
    unknown = sorted(changed - known)
    any_affected = bool(
        endpoint_affected
        or affected_entities
        or affected_locations
        or affected_causal
        or affected_bindings
        or affected_perturbations
    )
    result = {
        "query_status": "complete",
        "qualification_status": qualification.status,
        "qualification_model_fingerprint": qualification.model_fingerprint,
        "qualification_gaps": [],
        "target_authority_status": authority.status if authority else "not_run",
        "target_material_status": (
            authority.native_attestation.status
            if authority and authority.native_attestation
            else "not_run"
        ),
        "model_fingerprint": "sha256:" + trace_model_fingerprint(model),
        "canonical_receipt_id": receipt.receipt_id,
        "changed_ids": sorted(changed),
        "affected_source_ids": sorted(affected_sources),
        "affected_evidence_ids": sorted(affected_evidence),
        "affected_entity_ids": sorted(affected_entities),
        "affected_entity_resolution_ids": sorted(affected_resolutions),
        "affected_location_ids": sorted(affected_locations),
        "affected_event_ids": sorted(affected_events),
        "affected_trace_ids": sorted(affected_traces),
        "affected_hypothesis_ids": sorted(affected_hypotheses),
        "affected_causal_candidate_ids": sorted(affected_causal),
        "affected_causal_mechanism_ids": sorted(affected_mechanisms),
        "affected_confounder_ids": sorted(affected_confounders),
        "affected_causal_scope_ids": sorted(affected_scopes),
        "affected_hypothesis_evidence_link_ids": sorted(affected_links),
        "affected_hypothesis_relation_ids": sorted(affected_relations),
        "affected_interface_binding_ids": sorted(affected_bindings),
        "affected_evidence_ablation_ids": sorted(affected_ablations),
        "affected_scenario_perturbation_ids": sorted(affected_scenario_perturbations),
        "affected_perturbation_ids": sorted(affected_perturbations),
        "affected_sensitivity_ids": sorted(affected_sensitivities),
        "affected_depth_receipt_ids": [f"storyline-depth:{model.metadata.get('model_instance_id', 'model')}"] if any_affected else [],
        "affected_holdout_ids": [f"holdout:{item}" for item in sorted(affected_hypotheses)],
        "affected_narrative_fragment_ids": sorted(affected_claims),
        "affected_handoff_ids": sorted(affected_handoffs),
        "canonical_receipt_stale": any_affected,
        "live_alternative_ids": sorted(item.hypothesis_id for item in receipt.hypothesis_projections if item.live),
        "unknown_dependency_ids": unknown,
        "unknown_ownership": bool(unknown),
    }
    if unknown:
        for key in tuple(result):
            if key.startswith("affected_"):
                result[key] = []
        result["canonical_receipt_stale"] = False
        result["partial_result_suppressed"] = True
    else:
        result["partial_result_suppressed"] = False
    return result


def reverse_trace_output(
    model: TraceGuardModel,
    receipt: InferenceReceipt,
    output_id: str,
    universe: TraceTargetUniverse | None = None,
    *,
    candidate_path: str | None = None,
) -> dict[str, object]:
    qualification = (
        check_blueprint(
            model,
            receipt,
            universe,
            candidate_path=candidate_path,
        )
        if universe is not None
        else None
    )
    authority = universe.target_authority if universe is not None else None
    target_material_status = (
        authority.native_attestation.status
        if authority and authority.native_attestation
        else "not_run"
    )
    if qualification is None or qualification.status != "complete":
        trace_gaps = (
            [item.to_dict() for item in qualification.gaps]
            if qualification is not None
            else [
                TraceBlueprintGap(
                    "missing-target-universe",
                    output_id,
                    "reverse trace requires one current TraceGuard blueprint qualification",
                ).to_dict()
            ]
        )
        return {
            "query_status": "blocked",
            "qualification_status": (
                qualification.status if qualification is not None else "not_run"
            ),
            "qualification_model_fingerprint": (
                qualification.model_fingerprint if qualification is not None else ""
            ),
            "trace_status": "incomplete",
            "trace_gaps": trace_gaps,
            "blueprint_status": (
                qualification.status if qualification is not None else "incomplete"
            ),
            "target_authority_status": authority.status if authority else "not_run",
            "target_material_status": target_material_status,
            "output_id": "",
            "output_kind": "",
            "hypothesis_id": "",
            "trace_ids": [],
            "event_ids": [],
            "entities": [],
            "locations": [],
            "entity_resolutions": [],
            "evidence": [],
            "sources": [],
            "canonical_receipt": {},
            "canonical_receipt_contributions": [],
            "interface_bindings": [],
            "hypothesis_evidence_links": [],
            "hypothesis_relations": [],
            "alternatives": [],
            "confounders": [],
            "causal_candidates": [],
            "causal_mechanisms": [],
            "causal_scopes": [],
            "evidence_ablations": [],
            "scenario_perturbations": [],
            "expected_sensitivities": [],
            "hierarchy_nodes": [],
            "causal_boundary": {},
            "limitations": [],
            "native_causal_status": "not_run",
            "claim_boundary": (
                qualification.claim_boundary
                if qualification is not None
                else (
                    "TraceGuard projects source-backed temporal and storyline structure plus only the canonical "
                    "receipt's bounded qualitative causal status. It does not license formal causal identification, "
                    "do-calculus, calibrated treatment effects, factual proof, or missing source content."
                )
            ),
            "formal_causal_identification_licensed": False,
            "universe_fingerprint": "",
            "terminal_capability_boundary": "",
            "partial_result_suppressed": True,
        }
    hypotheses = [
        item
        for item in model.storyline_hypotheses
        if output_id in item.bounded_claim_ids or output_id in item.handoff_ids
    ]
    if len(hypotheses) != 1:
        raise ValueError(f"output {output_id!r} must resolve to exactly one hypothesis")
    hypothesis = hypotheses[0]
    trace_ids = set(hypothesis.trace_ids)
    traces = [item for item in model.traces if item.trace_id in trace_ids]
    event_ids = set(hypothesis.event_ids)
    event_ids.update(value for item in traces for value in item.event_ids)
    events = [item for item in model.events if item.event_id in event_ids]
    evidence_ids = set(hypothesis.evidence_ids + hypothesis.contradicting_evidence_ids)
    evidence_ids.update(value for item in events for value in item.evidence_ids)
    evidence = [item for item in model.evidence if item.evidence_id in evidence_ids]
    source_ids = {item.source_id for item in evidence}
    source_rows = [item for item in model.sources if item.source_id in source_ids]
    entity_ids = {
        value
        for event in events
        for value in event.actor_ids + event.object_ids + event.technology_ids
    }
    entity_ids.update(value for trace in traces for value in trace.entity_ids)
    location_ids = {value for event in events for value in event.location_ids}
    location_ids.update(value for trace in traces for value in trace.location_ids)
    contribution_rows = [
        item.to_dict()
        for item in receipt.contributions
        if set(item.affected_object_ids) & ({hypothesis.hypothesis_id} | trace_ids | event_ids)
        or set(item.evidence_ids) & evidence_ids
    ]
    projection = next(
        (item for item in receipt.hypothesis_projections if item.hypothesis_id == hypothesis.hypothesis_id),
        None,
    )
    alternatives = [
        {
            "hypothesis_id": item.hypothesis_id,
            "claim": item.claim,
            "role": item.role,
            "live": next((row.live for row in receipt.hypothesis_projections if row.hypothesis_id == item.hypothesis_id), False),
            "out_of_scope_reason": item.alternative_out_of_scope_reason or "",
        }
        for item in model.storyline_hypotheses
        if item.hypothesis_id in set(hypothesis.alternative_to)
    ]
    confounders = [asdict(item) for item in model.confounder_reviews if item.hypothesis_id == hypothesis.hypothesis_id]
    causal_candidates = [
        asdict(item)
        for item in model.causal_candidates
        if item.hypothesis_id == hypothesis.hypothesis_id
    ]
    mechanism_ids = {
        value for item in model.causal_candidates if item.hypothesis_id == hypothesis.hypothesis_id for value in item.mechanism_ids
    } | set(hypothesis.mechanism_ids)
    scope_ids = {
        item.scope_id
        for item in model.causal_candidates
        if item.hypothesis_id == hypothesis.hypothesis_id and item.scope_id
    }
    causal_boundary = next(
        (
            item
            for item in _causal_boundaries(model, receipt)
            if item["hypothesis_id"] == hypothesis.hypothesis_id
        ),
        {
            "boundary_id": f"causal-boundary:{hypothesis.hypothesis_id}",
            "native_causal_status": "not_run",
            "formal_causal_identification_licensed": False,
        },
    )
    relevant_interface_ids = {
        item.binding_id
        for item in model.interface_bindings
        if item.producer_id in source_ids | evidence_ids | event_ids | trace_ids | {hypothesis.hypothesis_id}
        or item.consumer_id in evidence_ids | event_ids | trace_ids | {hypothesis.hypothesis_id, output_id}
    }
    relevant_perturbation_ids = {
        item.perturbation_id
        for item in model.scenario_perturbations
        if item.hypothesis_id == hypothesis.hypothesis_id or item.trace_id in trace_ids
    }
    hierarchy = project_hierarchy(model)
    relevant_native_ids = source_ids | evidence_ids | event_ids | trace_ids | entity_ids | location_ids | {
        hypothesis.hypothesis_id,
        output_id,
        *mechanism_ids,
        *(item.confounder_id for item in model.confounder_reviews if item.hypothesis_id == hypothesis.hypothesis_id),
        *(item.causal_id for item in model.causal_candidates if item.hypothesis_id == hypothesis.hypothesis_id),
    }
    return {
        "query_status": "complete",
        "qualification_status": qualification.status,
        "qualification_model_fingerprint": qualification.model_fingerprint,
        "trace_status": "complete",
        "trace_gaps": [],
        "blueprint_status": qualification.status,
        "target_authority_status": authority.status if authority else "not_run",
        "target_material_status": target_material_status,
        "output_id": output_id,
        "output_kind": "handoff" if output_id in hypothesis.handoff_ids else "bounded_claim",
        "hypothesis_id": hypothesis.hypothesis_id,
        "trace_ids": sorted(trace_ids),
        "event_ids": sorted(event_ids),
        "entities": [
            asdict(item)
            for item in sorted(model.entities, key=lambda item: item.mention_id)
            if item.mention_id in entity_ids
        ],
        "locations": [
            asdict(item)
            for item in sorted(model.locations, key=lambda item: item.location_id)
            if item.location_id in location_ids
        ],
        "entity_resolutions": [
            {**asdict(item), "resolution_id": entity_resolution_id(item.left_id, item.relation, item.right_id)}
            for item in model.entity_resolutions
            if {item.left_id, item.right_id} & entity_ids
        ],
        "evidence": [
            {
                "evidence_id": item.evidence_id,
                "source_id": item.source_id,
                "locator": item.locator,
                "content_fingerprint": item.content_fingerprint,
                "normalizer_fingerprint": item.normalizer_fingerprint,
                "extractor_fingerprint": item.extractor_fingerprint,
                "normalizer_id": item.normalizer_id,
                "normalizer_revision": item.normalizer_revision,
                "extractor_id": item.extractor_id,
                "extractor_revision": item.extractor_revision,
                "limits": list(item.limits),
                "warnings": list(item.warnings),
            }
            for item in sorted(evidence, key=lambda item: item.evidence_id)
        ],
        "sources": [
            {
                "source_id": item.source_id,
                "source_revision": item.source_revision,
                "content_fingerprint": item.content_fingerprint,
                "url": item.url,
                "retrieval_locator": item.locator,
                "provider_id": item.provider_id,
                "provider_revision": item.provider_revision,
                "retrieval_request_fingerprint": item.retrieval_request_fingerprint,
                "fetched_at": item.fetched_at,
                "lineage_id": item.lineage_id,
                "independence_group": item.independence_group,
            }
            for item in sorted(source_rows, key=lambda item: item.source_id)
        ],
        "canonical_receipt": project_canonical_receipt_identity(receipt),
        "canonical_receipt_contributions": contribution_rows,
        "interface_bindings": [
            asdict(item)
            for item in sorted(model.interface_bindings, key=lambda item: item.binding_id)
            if item.binding_id in relevant_interface_ids
        ],
        "hypothesis_evidence_links": [
            asdict(item)
            for item in model.hypothesis_evidence_links
            if item.hypothesis_id == hypothesis.hypothesis_id or item.evidence_id in evidence_ids
        ],
        "hypothesis_relations": [
            asdict(item)
            for item in model.hypothesis_relations
            if hypothesis.hypothesis_id in {item.left_hypothesis_id, item.right_hypothesis_id}
        ],
        "alternatives": alternatives,
        "confounders": confounders,
        "causal_candidates": causal_candidates,
        "causal_mechanisms": [
            asdict(item)
            for item in model.causal_mechanisms
            if item.mechanism_id in mechanism_ids
        ],
        "causal_scopes": [
            asdict(item) for item in model.causal_scopes if item.scope_id in scope_ids
        ],
        "evidence_ablations": [
            asdict(item)
            for item in model.evidence_ablations
            if item.hypothesis_id == hypothesis.hypothesis_id or item.trace_id in trace_ids
        ],
        "scenario_perturbations": [
            asdict(item)
            for item in model.scenario_perturbations
            if item.perturbation_id in relevant_perturbation_ids
        ],
        "expected_sensitivities": [
            asdict(item)
            for item in model.expected_sensitivities
            if item.perturbation_id in relevant_perturbation_ids
        ],
        "hierarchy_nodes": [
            item.to_dict()
            for item in hierarchy
            if item.native_id in relevant_native_ids
        ],
        "causal_boundary": causal_boundary,
        "limitations": sorted({value for item in evidence for value in (*item.limits, *item.warnings)}),
        "native_causal_status": projection.causal_status if projection else "not_run",
        "claim_boundary": projection.claim_boundary if projection else "No canonical hypothesis projection is current.",
        "formal_causal_identification_licensed": False,
        "universe_fingerprint": universe.fingerprint if universe else "",
        "terminal_capability_boundary": (
            "TraceGuard can reconstruct the declared source-to-storyline and bounded causal-review chain; "
            "it cannot recover unread source bytes or license formal causal identification."
        ),
        "partial_result_suppressed": False,
    }


def export_blueprint(
    model: TraceGuardModel,
    receipt: InferenceReceipt,
    universe: TraceTargetUniverse,
    *,
    candidate_path: str | None = None,
) -> dict[str, object]:
    return {
        "schema_version": TRACE_BLUEPRINT_SCHEMA,
        "model": model.to_dict(),
        "target_universe": universe.to_dict(),
        "canonical_receipt": receipt.to_dict(),
        "check": check_blueprint(model, receipt, universe, candidate_path=candidate_path).to_dict(),
    }


__all__ = [
    "TRACE_BLUEPRINT_SCHEMA",
    "TraceBlueprintGap",
    "TraceBlueprintResult",
    "TraceHierarchyNode",
    "TraceTargetUniverse",
    "check_blueprint",
    "export_blueprint",
    "hierarchy_fingerprint",
    "impact_blueprint",
    "interface_fingerprint",
    "replay_trace_target_material",
    "project_hierarchy",
    "reverse_trace_output",
    "trace_target_purpose_fingerprint",
    "trace_target_request_fingerprint",
    "trace_target_subject_fingerprint",
]
