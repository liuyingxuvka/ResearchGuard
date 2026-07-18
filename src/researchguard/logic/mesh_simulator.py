"""Sparse copy-on-write simulation over one immutable ModelMesh revision."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .identity import (
    EdgeId,
    MeshId,
    MeshRevision,
    ModelId,
    QualifiedModelRef,
    QualifiedNodeRef,
)
from .loader import load_model_from_dict
from .mesh_evaluator import MESH_SIMULATOR_FINGERPRINT, evaluate_materialized_mesh
from .mesh_materialization import MeshMaterializationRequest, materialize_mesh
from .mesh_overlay import MeshEvaluationOverlay
from .mesh_receipts import MeshSimulationReceipt
from .model_mesh import (
    CrossModelEdge,
    MeshMembership,
    ModelRegistryEntry,
    qualified_model_key,
    qualified_node_key,
)
from .model_store import canonical_digest


class MeshSimulationError(RuntimeError):
    """A simulation delta is stale, malformed, or exceeds simulation authority."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return copy.deepcopy(value)


@dataclass(frozen=True, order=True)
class ModelPinReplacement:
    source: QualifiedModelRef
    target: QualifiedModelRef

    def __post_init__(self) -> None:
        if self.source.model_id != self.target.model_id:
            raise MeshSimulationError("pin replacement must preserve physical model_id")
        if self.source == self.target:
            raise MeshSimulationError("pin replacement must advance to a different revision")

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source.to_dict(), "target": self.target.to_dict()}


@dataclass(frozen=True)
class MeshNodeOverride:
    node_ref: QualifiedNodeRef
    changes: Mapping[str, Any]

    def __post_init__(self) -> None:
        changes = dict(self.changes or {})
        if not changes:
            raise MeshSimulationError("node override requires at least one changed field")
        if any(key in {"id", "type"} for key in changes):
            raise MeshSimulationError("simulation override cannot change node identity or type")
        object.__setattr__(self, "changes", _freeze(changes))

    def to_dict(self) -> dict[str, Any]:
        return {"node_ref": self.node_ref.to_dict(), "changes": _thaw(self.changes)}


@dataclass(frozen=True)
class MeshSimulationDelta:
    base_mesh_id: MeshId
    base_mesh_revision: MeshRevision
    pin_replacements: tuple[ModelPinReplacement, ...] = ()
    membership_additions: tuple[MeshMembership, ...] = ()
    membership_removals: tuple[str, ...] = ()
    edge_additions: tuple[CrossModelEdge, ...] = ()
    edge_removals: tuple[EdgeId, ...] = ()
    provenance_overrides: tuple[MeshNodeOverride, ...] = ()
    evidence_availability_changes: tuple[MeshNodeOverride, ...] = ()
    rebuttal_changes: tuple[MeshNodeOverride, ...] = ()
    assumption_changes: tuple[MeshNodeOverride, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    delta_digest: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_mesh_id", MeshId.parse(self.base_mesh_id))
        object.__setattr__(
            self, "base_mesh_revision", MeshRevision.parse(self.base_mesh_revision)
        )
        replacements = tuple(sorted(self.pin_replacements, key=lambda item: qualified_model_key(item.source)))
        if len({item.source.model_id for item in replacements}) != len(replacements):
            raise MeshSimulationError("duplicate pin replacement for one physical model")
        object.__setattr__(self, "pin_replacements", replacements)
        object.__setattr__(
            self,
            "membership_additions",
            tuple(sorted(self.membership_additions, key=lambda item: item.membership_key)),
        )
        object.__setattr__(self, "membership_removals", tuple(sorted(set(self.membership_removals))))
        object.__setattr__(
            self, "edge_additions", tuple(sorted(self.edge_additions, key=lambda item: str(item.id)))
        )
        object.__setattr__(
            self,
            "edge_removals",
            tuple(sorted({EdgeId.parse(item) for item in self.edge_removals}, key=str)),
        )
        for name in (
            "provenance_overrides",
            "evidence_availability_changes",
            "rebuttal_changes",
            "assumption_changes",
        ):
            object.__setattr__(
                self,
                name,
                tuple(sorted(getattr(self, name), key=lambda item: qualified_node_key(item.node_ref))),
            )
        object.__setattr__(self, "metadata", _freeze(dict(self.metadata or {})))
        expected = canonical_digest(self.fingerprint_payload())
        if self.delta_digest and self.delta_digest != expected:
            raise MeshSimulationError(
                f"simulation delta digest mismatch: {self.delta_digest} != {expected}"
            )
        object.__setattr__(self, "delta_digest", expected)

    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "base_mesh_id": str(self.base_mesh_id),
            "base_mesh_revision": str(self.base_mesh_revision),
            "pin_replacements": [item.to_dict() for item in self.pin_replacements],
            "membership_additions": [item.to_dict() for item in self.membership_additions],
            "membership_removals": list(self.membership_removals),
            "edge_additions": [item.to_dict() for item in self.edge_additions],
            "edge_removals": [str(item) for item in self.edge_removals],
            "provenance_overrides": [item.to_dict() for item in self.provenance_overrides],
            "evidence_availability_changes": [
                item.to_dict() for item in self.evidence_availability_changes
            ],
            "rebuttal_changes": [item.to_dict() for item in self.rebuttal_changes],
            "assumption_changes": [item.to_dict() for item in self.assumption_changes],
            "metadata": _thaw(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.fingerprint_payload(), "delta_digest": self.delta_digest}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshSimulationDelta":
        required = (
            "base_mesh_id",
            "base_mesh_revision",
            "pin_replacements",
            "membership_additions",
            "membership_removals",
            "edge_additions",
            "edge_removals",
            "provenance_overrides",
            "evidence_availability_changes",
            "rebuttal_changes",
            "assumption_changes",
            "metadata",
            "delta_digest",
        )
        missing = [key for key in required if key not in raw]
        if missing:
            raise MeshSimulationError(
                "simulation delta is missing current fields: " + ", ".join(missing)
            )

        def parse_replacement(item: Mapping[str, Any]) -> ModelPinReplacement:
            return ModelPinReplacement(
                source=QualifiedModelRef.from_dict(item["source"]),
                target=QualifiedModelRef.from_dict(item["target"]),
            )

        def parse_override(item: Mapping[str, Any]) -> MeshNodeOverride:
            return MeshNodeOverride(
                node_ref=QualifiedNodeRef.from_dict(item["node_ref"]),
                changes=dict(item["changes"]),
            )

        return cls(
            base_mesh_id=MeshId.parse(raw["base_mesh_id"]),
            base_mesh_revision=MeshRevision.parse(raw["base_mesh_revision"]),
            pin_replacements=tuple(
                parse_replacement(item) for item in raw["pin_replacements"]
            ),
            membership_additions=tuple(
                MeshMembership.from_dict(item) for item in raw["membership_additions"]
            ),
            membership_removals=tuple(str(item) for item in raw["membership_removals"]),
            edge_additions=tuple(
                CrossModelEdge.from_dict(item) for item in raw["edge_additions"]
            ),
            edge_removals=tuple(EdgeId.parse(item) for item in raw["edge_removals"]),
            provenance_overrides=tuple(
                parse_override(item) for item in raw["provenance_overrides"]
            ),
            evidence_availability_changes=tuple(
                parse_override(item) for item in raw["evidence_availability_changes"]
            ),
            rebuttal_changes=tuple(
                parse_override(item) for item in raw["rebuttal_changes"]
            ),
            assumption_changes=tuple(
                parse_override(item) for item in raw["assumption_changes"]
            ),
            metadata=dict(raw["metadata"]),
            delta_digest=str(raw["delta_digest"]),
        )


@dataclass(frozen=True)
class _SimulationSnapshotProjection:
    mesh_id: MeshId
    revision: MeshRevision
    content_digest: str
    registry: tuple[ModelRegistryEntry, ...]
    memberships: tuple[MeshMembership, ...]
    cross_model_edges: tuple[CrossModelEdge, ...]


class _VirtualModelSnapshot:
    def __init__(self, base, payload: Mapping[str, Any], virtual_digest: str) -> None:
        self._base = base
        self.model_id = base.model_id
        self.revision = base.revision
        self.content_digest = virtual_digest
        self.artifact_schema = base.artifact_schema
        self.store_schema_version = base.store_schema_version
        self.model_payload = _freeze(dict(payload))

    def to_model(self):
        model = load_model_from_dict(_thaw(self.model_payload), validate=False)
        model.metadata["model_revision_id"] = str(self.revision)
        model.metadata["model_content_digest"] = self.content_digest
        model.metadata["simulation_only"] = True
        return model


def _virtual_snapshot_digest(
    base_digest: str,
    relevant: Mapping[QualifiedNodeRef, Mapping[str, Any]],
) -> str:
    return canonical_digest(
        {
            "base_content_digest": base_digest,
            "overrides": [
                {
                    "node_ref": item.to_dict(),
                    "changes": _thaw(relevant[item]),
                }
                for item in sorted(relevant, key=qualified_node_key)
            ],
        }
    )


def _repin_node(ref: QualifiedNodeRef, replacements: Mapping[QualifiedModelRef, QualifiedModelRef]):
    source = QualifiedModelRef(ref.model_id, ref.revision)
    target = replacements.get(source)
    if target is None:
        return ref
    return QualifiedNodeRef(target.model_id, target.revision, ref.node_id)


def _repin_membership(
    membership: MeshMembership,
    replacements: Mapping[QualifiedModelRef, QualifiedModelRef],
) -> MeshMembership:
    logical = replacements.get(membership.logical_model, membership.logical_model)
    return MeshMembership(
        owner=_repin_node(membership.owner, replacements),
        logical_model=logical,
        roles=membership.roles,
        role_metadata=membership.role_metadata,
        provenance=membership.provenance,
    )


def _repin_edge(
    edge: CrossModelEdge,
    replacements: Mapping[QualifiedModelRef, QualifiedModelRef],
) -> CrossModelEdge:
    return CrossModelEdge(
        id=edge.id,
        source=_repin_node(edge.source, replacements),
        target=_repin_node(edge.target, replacements),
        type=edge.type,
        weight=edge.weight,
        explanation=edge.explanation,
        source_block_id=edge.source_block_id,
        target_block_id=edge.target_block_id,
        source_role=edge.source_role,
        target_role=edge.target_role,
        provenance=edge.provenance,
        metadata=edge.metadata,
    )


class SimulationMeshView:
    """Sparse read-only overlay implementing the MeshRevisionView interface."""

    def __init__(self, base_view, delta: MeshSimulationDelta) -> None:
        if (
            delta.base_mesh_id != base_view.snapshot.mesh_id
            or delta.base_mesh_revision != base_view.snapshot.revision
        ):
            raise MeshSimulationError("simulation delta does not bind base mesh view")
        self.base_view = base_view
        self.delta = delta
        self._overrides: dict[QualifiedNodeRef, dict[str, Any]] = {}
        self._override_categories: dict[QualifiedNodeRef, set[str]] = {}
        for category, values in (
            ("provenance", delta.provenance_overrides),
            ("evidence_availability", delta.evidence_availability_changes),
            ("rebuttal", delta.rebuttal_changes),
            ("assumption", delta.assumption_changes),
        ):
            for item in values:
                target = self._overrides.setdefault(item.node_ref, {})
                for key, value in _thaw(item.changes).items():
                    if key in target and target[key] != value:
                        raise MeshSimulationError(
                            f"conflicting simulation overrides for {item.node_ref}: {key}"
                        )
                    target[key] = value
                self._override_categories.setdefault(item.node_ref, set()).add(category)
        base_registry = {item.model_ref: item for item in base_view.snapshot.registry}
        replacements = {item.source: item.target for item in delta.pin_replacements}
        self._replacement_sources = frozenset(replacements)
        self._replacement_targets = frozenset(replacements.values())
        if any(source not in base_registry for source in replacements):
            raise MeshSimulationError("pin replacement source is not in base registry")
        if any(
            QualifiedModelRef(ref.model_id, ref.revision) in replacements
            for ref in self._overrides
        ):
            raise MeshSimulationError(
                "node overrides must bind the replacement revision, not its retired source pin"
            )
        registry = []
        self._target_snapshots = {}
        for source_ref, entry in base_registry.items():
            target_ref = replacements.get(source_ref, source_ref)
            relevant = {
                ref: changes
                for ref, changes in self._overrides.items()
                if QualifiedModelRef(ref.model_id, ref.revision) == target_ref
            }
            if target_ref == source_ref and not relevant:
                registry.append(entry)
                continue
            if target_ref != source_ref:
                target_snapshot = base_view.exact_model_snapshot(target_ref)
                self._target_snapshots[target_ref] = target_snapshot
            else:
                target_snapshot = base_view.exact_model_snapshot(source_ref)
            registry.append(
                ModelRegistryEntry(
                    model_ref=target_ref,
                    content_digest=(
                        _virtual_snapshot_digest(target_snapshot.content_digest, relevant)
                        if relevant
                        else target_snapshot.content_digest
                    ),
                    snapshot_artifact_schema=target_snapshot.artifact_schema,
                    store_schema_version=target_snapshot.store_schema_version,
                )
            )
        memberships = {
            item.membership_key: _repin_membership(item, replacements)
            for item in base_view.snapshot.memberships
            if item.membership_key not in set(delta.membership_removals)
        }
        for item in delta.membership_additions:
            memberships[item.membership_key] = item
        edges = {
            item.id: _repin_edge(item, replacements)
            for item in base_view.snapshot.cross_model_edges
            if item.id not in set(delta.edge_removals)
        }
        for item in delta.edge_additions:
            edges[item.id] = item
        self.snapshot = _SimulationSnapshotProjection(
            mesh_id=base_view.snapshot.mesh_id,
            revision=base_view.snapshot.revision,
            content_digest=base_view.snapshot.content_digest,
            registry=tuple(sorted(registry, key=lambda item: qualified_model_key(item.model_ref))),
            memberships=tuple(sorted(memberships.values(), key=lambda item: item.membership_key)),
            cross_model_edges=tuple(sorted(edges.values(), key=lambda item: str(item.id))),
        )
        self._registry = {item.model_ref: item for item in self.snapshot.registry}
        self._models = {}
        self._model_read_count = 0
        self._memberships_by_owner = {}
        self._memberships_by_model = {}
        self._out_edges = {}
        self._in_edges = {}
        for membership in self.snapshot.memberships:
            self._memberships_by_owner.setdefault(membership.owner, []).append(membership)
            self._memberships_by_model.setdefault(membership.logical_model, []).append(membership)
        for edge in self.snapshot.cross_model_edges:
            self._out_edges.setdefault(edge.source, []).append(edge)
            self._in_edges.setdefault(edge.target, []).append(edge)
        self._validate_overrides()
        self._validate_virtual_topology()

    @property
    def model_read_count(self) -> int:
        return self._model_read_count

    @property
    def copied_node_count(self) -> int:
        return len(self._overrides)

    def _base_or_target_snapshot(self, ref: QualifiedModelRef):
        if ref in self._target_snapshots:
            return self._target_snapshots[ref]
        return self.base_view.exact_model_snapshot(ref)

    def _validate_overrides(self) -> None:
        for ref, categories in self._override_categories.items():
            model_ref = QualifiedModelRef(ref.model_id, ref.revision)
            if model_ref not in self._registry:
                raise MeshSimulationError(f"override node model is not in virtual registry: {ref}")
            snapshot = self._base_or_target_snapshot(model_ref)
            node = snapshot.model_payload.get("nodes", {}).get(str(ref.node_id))
            if node is None:
                raise MeshSimulationError(f"override node does not exist: {ref}")
            node_type = node.get("type")
            if "evidence_availability" in categories and node_type != "Evidence":
                raise MeshSimulationError("evidence availability change requires Evidence node")
            if "rebuttal" in categories and node_type not in {"Rebuttal", "Undercutter"}:
                raise MeshSimulationError("rebuttal change requires Rebuttal/Undercutter node")
            if "assumption" in categories and node_type != "Assumption":
                raise MeshSimulationError("assumption change requires Assumption node")

    def _validate_virtual_topology(self) -> None:
        registered = set(self._registry)
        for membership in self.snapshot.memberships:
            owner_model = QualifiedModelRef(
                membership.owner.model_id, membership.owner.revision
            )
            changed = (
                membership in self.delta.membership_additions
                or owner_model in self._replacement_targets
                or membership.logical_model in self._replacement_targets
            )
            if not changed:
                continue
            if owner_model not in registered or membership.logical_model not in registered:
                raise MeshSimulationError(
                    "simulated membership endpoints must use virtual registry pins"
                )
            self.node(membership.owner)
        for edge in self.snapshot.cross_model_edges:
            endpoint_models = tuple(
                QualifiedModelRef(endpoint.model_id, endpoint.revision)
                for endpoint in (edge.source, edge.target)
            )
            changed = (
                edge in self.delta.edge_additions
                or any(item in self._replacement_targets for item in endpoint_models)
            )
            if not changed:
                continue
            for endpoint, model_ref in zip((edge.source, edge.target), endpoint_models):
                if model_ref not in registered:
                    raise MeshSimulationError(
                        "simulated cross-edge endpoints must use virtual registry pins"
                    )
                self.node(endpoint)

    def registry_entry(self, ref):
        try:
            return self._registry[ref]
        except KeyError as exc:
            raise MeshSimulationError(f"model is not in simulated registry: {ref}") from exc

    def model_snapshot(self, ref: QualifiedModelRef):
        self.registry_entry(ref)
        if ref not in self._models:
            base = self._base_or_target_snapshot(ref)
            relevant = {
                node_ref: changes
                for node_ref, changes in self._overrides.items()
                if QualifiedModelRef(node_ref.model_id, node_ref.revision) == ref
            }
            if not relevant:
                self._models[ref] = base
            else:
                payload = base.authoring_payload()
                for node_ref, changes in relevant.items():
                    payload["nodes"][str(node_ref.node_id)].update(_thaw(changes))
                self._models[ref] = _VirtualModelSnapshot(
                    base,
                    payload,
                    _virtual_snapshot_digest(base.content_digest, relevant),
                )
            self._model_read_count += 1
        return self._models[ref]

    def node(self, ref: QualifiedNodeRef):
        snapshot = self.model_snapshot(QualifiedModelRef(ref.model_id, ref.revision))
        try:
            return snapshot.model_payload["nodes"][str(ref.node_id)]
        except KeyError as exc:
            raise MeshSimulationError(f"simulated node is missing: {ref}") from exc

    def memberships_for_node(self, ref):
        return tuple(sorted(self._memberships_by_owner.get(ref, ()), key=lambda item: item.membership_key))

    def members_of_model(self, ref):
        return tuple(sorted(self._memberships_by_model.get(ref, ()), key=lambda item: qualified_node_key(item.owner)))

    def outgoing_cross_edges(self, ref):
        return tuple(sorted(self._out_edges.get(ref, ()), key=lambda item: str(item.id)))

    def incoming_cross_edges(self, ref):
        return tuple(sorted(self._in_edges.get(ref, ()), key=lambda item: str(item.id)))

    def model_dependencies(self, ref):
        targets = {
            QualifiedModelRef(edge.target.model_id, edge.target.revision)
            for edge in self.snapshot.cross_model_edges
            if QualifiedModelRef(edge.source.model_id, edge.source.revision) == ref
        }
        targets.update(
            item.logical_model
            for item in self.snapshot.memberships
            if QualifiedModelRef(item.owner.model_id, item.owner.revision) == ref
        )
        targets.discard(ref)
        return tuple(sorted(targets, key=qualified_model_key))


@dataclass(frozen=True)
class MeshSimulationResult:
    delta: MeshSimulationDelta
    materialized: Any
    overlay: MeshEvaluationOverlay
    receipt: MeshSimulationReceipt
    shared_model_count: int
    overridden_model_count: int
    copied_node_count: int


def simulate_mesh(
    base_view,
    delta: MeshSimulationDelta,
    request: MeshMaterializationRequest,
    *,
    requested_claim_scope: Iterable[QualifiedNodeRef],
    profile: str = "bounded",
    depth_budget: int = 6,
) -> MeshSimulationResult:
    view = SimulationMeshView(base_view, delta)
    materialized = materialize_mesh(view, request)
    overlay = evaluate_materialized_mesh(
        view,
        materialized,
        requested_claim_scope=requested_claim_scope,
        profile=profile,
        depth_budget=depth_budget,
        authority="simulation",
    )
    changed_models = {
        item.source.model_id for item in delta.pin_replacements
    }.union(ref.model_id for ref in view._overrides)
    limitations = (
        "simulation-only; no canonical Mesh, Catalog, or P0 authority was changed",
        "mesh-owned changes require ordinary mesh/catalog CAS adoption",
        "P0 content changes require a P0 commit followed by an explicit mesh repin",
    )
    receipt = MeshSimulationReceipt.create(
        mesh_id=delta.base_mesh_id,
        base_mesh_revision=delta.base_mesh_revision,
        delta_digest=delta.delta_digest,
        affected_universe_fingerprint=materialized.authoritative_universe_fingerprint,
        result_fingerprint=overlay.fingerprint,
        tool_fingerprint=MESH_SIMULATOR_FINGERPRINT,
        limitations=limitations,
    )
    return MeshSimulationResult(
        delta=delta,
        materialized=materialized,
        overlay=overlay,
        receipt=receipt,
        shared_model_count=max(len(view.snapshot.registry) - len(changed_models), 0),
        overridden_model_count=len(changed_models),
        copied_node_count=view.copied_node_count,
    )


def adoption_requirements(delta: MeshSimulationDelta) -> tuple[str, ...]:
    requirements = []
    if (
        delta.pin_replacements
        or delta.membership_additions
        or delta.membership_removals
        or delta.edge_additions
        or delta.edge_removals
    ):
        requirements.append("ordinary_mesh_catalog_cas")
    if (
        delta.provenance_overrides
        or delta.evidence_availability_changes
        or delta.rebuttal_changes
        or delta.assumption_changes
    ):
        requirements.append("p0_commit_then_mesh_repin")
    return tuple(requirements)


__all__ = [
    "MeshNodeOverride",
    "MeshSimulationDelta",
    "MeshSimulationError",
    "MeshSimulationResult",
    "ModelPinReplacement",
    "SimulationMeshView",
    "adoption_requirements",
    "simulate_mesh",
]
