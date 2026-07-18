"""Revision-bound cross-model evaluation overlays and currentness checks."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .identity import (
    EdgeId,
    MeshEvaluationId,
    MeshId,
    MeshRevision,
    QualifiedModelRef,
    QualifiedNodeRef,
)
from .model_mesh import ModelMeshSnapshot, qualified_model_key, qualified_node_key
from .model_store import canonical_digest
from .schema import (
    MESH_EVALUATION_OVERLAY_SCHEMA,
    MESH_SCHEMA_VERSION,
    STATE_IN,
    STATES,
)


MESH_STRUCTURAL_CLAIM_BOUNDARY = (
    "This overlay licenses only the declared structural scope over the exact "
    "revision-bound authoritative universe. It does not establish factual truth."
)


class MeshOverlayError(ValueError):
    """A mesh overlay or dependency binding is malformed or tampered."""


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


def _require(raw: Mapping[str, Any], key: str) -> Any:
    if key not in raw:
        raise MeshOverlayError(f"required overlay field is missing: {key}")
    return raw[key]


@dataclass(frozen=True, order=True)
class MeshDependencyKey:
    kind: str
    identity_digest: str
    payload: Mapping[str, Any] = field(compare=False)

    ALLOWED_KINDS = frozenset(
        {
            "edge",
            "evaluator",
            "evidence_identity",
            "independence_group",
            "membership",
            "model_pin",
            "node",
            "profile",
            "scope",
            "simulator",
        }
    )

    def __post_init__(self) -> None:
        if self.kind not in self.ALLOWED_KINDS:
            raise MeshOverlayError(f"unsupported mesh dependency kind: {self.kind!r}")
        object.__setattr__(self, "payload", _freeze(dict(self.payload or {})))
        expected = canonical_digest({"kind": self.kind, "payload": _thaw(self.payload)})
        if self.identity_digest != expected:
            raise MeshOverlayError(
                f"dependency key digest mismatch: found {self.identity_digest}, expected {expected}"
            )

    @classmethod
    def create(cls, kind: str, payload: Mapping[str, Any]) -> "MeshDependencyKey":
        normalized = dict(payload)
        return cls(
            kind=kind,
            identity_digest=canonical_digest({"kind": kind, "payload": normalized}),
            payload=normalized,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "identity_digest": self.identity_digest,
            "payload": _thaw(self.payload),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshDependencyKey":
        return cls(
            kind=str(_require(raw, "kind")),
            identity_digest=str(_require(raw, "identity_digest")),
            payload=dict(_require(raw, "payload")),
        )


@dataclass(frozen=True)
class OverlayDependencyBinding:
    mesh_id: MeshId
    mesh_revision: MeshRevision
    mesh_content_digest: str
    materialization_fingerprint: str
    model_refs: tuple[QualifiedModelRef, ...]
    node_refs: tuple[QualifiedNodeRef, ...]
    membership_keys: tuple[str, ...]
    edge_ids: tuple[EdgeId, ...]
    contribution_keys: tuple[str, ...]
    independence_groups: tuple[str, ...]
    evaluator_fingerprint: str
    simulator_fingerprint: str
    requested_claim_scope: tuple[QualifiedNodeRef, ...]
    profile: str
    dependency_keys: tuple[MeshDependencyKey, ...]
    digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "mesh_id", MeshId.parse(self.mesh_id))
        object.__setattr__(self, "mesh_revision", MeshRevision.parse(self.mesh_revision))
        if not self.mesh_content_digest.startswith("sha256:"):
            raise MeshOverlayError("mesh_content_digest must be sha256")
        if not self.materialization_fingerprint.startswith("sha256:"):
            raise MeshOverlayError("materialization_fingerprint must be sha256")
        object.__setattr__(
            self, "model_refs", tuple(sorted(set(self.model_refs), key=qualified_model_key))
        )
        object.__setattr__(
            self, "node_refs", tuple(sorted(set(self.node_refs), key=qualified_node_key))
        )
        object.__setattr__(self, "membership_keys", tuple(sorted(set(self.membership_keys))))
        object.__setattr__(
            self,
            "edge_ids",
            tuple(sorted({EdgeId.parse(item) for item in self.edge_ids}, key=str)),
        )
        object.__setattr__(self, "contribution_keys", tuple(sorted(set(self.contribution_keys))))
        object.__setattr__(
            self, "independence_groups", tuple(sorted(set(self.independence_groups)))
        )
        object.__setattr__(
            self,
            "requested_claim_scope",
            tuple(sorted(set(self.requested_claim_scope), key=qualified_node_key)),
        )
        object.__setattr__(
            self,
            "dependency_keys",
            tuple(sorted(set(self.dependency_keys), key=lambda item: (item.kind, item.identity_digest))),
        )
        if self.profile not in {"broad", "bounded"}:
            raise MeshOverlayError("overlay dependency profile must be broad or bounded")
        if not self.evaluator_fingerprint or not self.simulator_fingerprint:
            raise MeshOverlayError("dependency binding requires evaluator and simulator fingerprints")
        expected = canonical_digest(self.fingerprint_payload())
        if self.digest != expected:
            raise MeshOverlayError(
                f"overlay dependency digest mismatch: found {self.digest}, expected {expected}"
            )

    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "mesh_id": str(self.mesh_id),
            "mesh_revision": str(self.mesh_revision),
            "mesh_content_digest": self.mesh_content_digest,
            "materialization_fingerprint": self.materialization_fingerprint,
            "model_refs": [item.to_dict() for item in self.model_refs],
            "node_refs": [item.to_dict() for item in self.node_refs],
            "membership_keys": list(self.membership_keys),
            "edge_ids": [str(item) for item in self.edge_ids],
            "contribution_keys": list(self.contribution_keys),
            "independence_groups": list(self.independence_groups),
            "evaluator_fingerprint": self.evaluator_fingerprint,
            "simulator_fingerprint": self.simulator_fingerprint,
            "requested_claim_scope": [item.to_dict() for item in self.requested_claim_scope],
            "profile": self.profile,
            "dependency_keys": [item.to_dict() for item in self.dependency_keys],
        }

    @classmethod
    def create(
        cls,
        *,
        mesh_id: MeshId,
        mesh_revision: MeshRevision,
        mesh_content_digest: str,
        materialization_fingerprint: str,
        model_refs: Iterable[QualifiedModelRef],
        node_refs: Iterable[QualifiedNodeRef],
        membership_keys: Iterable[str],
        edge_ids: Iterable[EdgeId],
        contribution_keys: Iterable[str],
        independence_groups: Iterable[str],
        evaluator_fingerprint: str,
        simulator_fingerprint: str,
        requested_claim_scope: Iterable[QualifiedNodeRef],
        profile: str,
        dependency_keys: Iterable[MeshDependencyKey],
    ) -> "OverlayDependencyBinding":
        payload = {
            "mesh_id": str(mesh_id),
            "mesh_revision": str(mesh_revision),
            "mesh_content_digest": mesh_content_digest,
            "materialization_fingerprint": materialization_fingerprint,
            "model_refs": [item.to_dict() for item in sorted(set(model_refs), key=qualified_model_key)],
            "node_refs": [item.to_dict() for item in sorted(set(node_refs), key=qualified_node_key)],
            "membership_keys": sorted(set(membership_keys)),
            "edge_ids": [str(item) for item in sorted({EdgeId.parse(item) for item in edge_ids}, key=str)],
            "contribution_keys": sorted(set(contribution_keys)),
            "independence_groups": sorted(set(independence_groups)),
            "evaluator_fingerprint": evaluator_fingerprint,
            "simulator_fingerprint": simulator_fingerprint,
            "requested_claim_scope": [
                item.to_dict() for item in sorted(set(requested_claim_scope), key=qualified_node_key)
            ],
            "profile": profile,
            "dependency_keys": [
                item.to_dict()
                for item in sorted(set(dependency_keys), key=lambda value: (value.kind, value.identity_digest))
            ],
        }
        return cls(
            mesh_id=mesh_id,
            mesh_revision=mesh_revision,
            mesh_content_digest=mesh_content_digest,
            materialization_fingerprint=materialization_fingerprint,
            model_refs=tuple(model_refs),
            node_refs=tuple(node_refs),
            membership_keys=tuple(membership_keys),
            edge_ids=tuple(edge_ids),
            contribution_keys=tuple(contribution_keys),
            independence_groups=tuple(independence_groups),
            evaluator_fingerprint=evaluator_fingerprint,
            simulator_fingerprint=simulator_fingerprint,
            requested_claim_scope=tuple(requested_claim_scope),
            profile=profile,
            dependency_keys=tuple(dependency_keys),
            digest=canonical_digest(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        return {**self.fingerprint_payload(), "digest": self.digest}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "OverlayDependencyBinding":
        return cls(
            mesh_id=MeshId.parse(_require(raw, "mesh_id")),
            mesh_revision=MeshRevision.parse(_require(raw, "mesh_revision")),
            mesh_content_digest=str(_require(raw, "mesh_content_digest")),
            materialization_fingerprint=str(_require(raw, "materialization_fingerprint")),
            model_refs=tuple(QualifiedModelRef.from_dict(item) for item in _require(raw, "model_refs")),
            node_refs=tuple(QualifiedNodeRef.from_dict(item) for item in _require(raw, "node_refs")),
            membership_keys=tuple(_require(raw, "membership_keys")),
            edge_ids=tuple(EdgeId.parse(item) for item in _require(raw, "edge_ids")),
            contribution_keys=tuple(_require(raw, "contribution_keys")),
            independence_groups=tuple(_require(raw, "independence_groups")),
            evaluator_fingerprint=str(_require(raw, "evaluator_fingerprint")),
            simulator_fingerprint=str(_require(raw, "simulator_fingerprint")),
            requested_claim_scope=tuple(
                QualifiedNodeRef.from_dict(item) for item in _require(raw, "requested_claim_scope")
            ),
            profile=str(_require(raw, "profile")),
            dependency_keys=tuple(
                MeshDependencyKey.from_dict(item) for item in _require(raw, "dependency_keys")
            ),
            digest=str(_require(raw, "digest")),
        )


@dataclass(frozen=True, order=True)
class MeshNodeResult:
    node_ref: QualifiedNodeRef
    state: str
    confidence: float
    explanation: str = ""
    blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.state not in STATES:
            raise MeshOverlayError(f"unknown LogicGuard state: {self.state!r}")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise MeshOverlayError("node result confidence must be between 0 and 1")
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "blockers", tuple(sorted(set(self.blockers))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_ref": self.node_ref.to_dict(),
            "state": self.state,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "blockers": list(self.blockers),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshNodeResult":
        return cls(
            node_ref=QualifiedNodeRef.from_dict(_require(raw, "node_ref")),
            state=str(_require(raw, "state")),
            confidence=float(_require(raw, "confidence")),
            explanation=str(_require(raw, "explanation")),
            blockers=tuple(_require(raw, "blockers")),
        )


@dataclass(frozen=True, order=True)
class MeshDepthBinding:
    model_ref: QualifiedModelRef
    depth_receipt_digest: str
    model_fingerprint: str
    requested_claim_refs: tuple[QualifiedNodeRef, ...]
    important_node_refs: tuple[QualifiedNodeRef, ...]
    scope_relation: str
    status: str
    broad_claim_licensed: bool
    gaps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.scope_relation not in {"exact", "materialization_superset", "incomplete"}:
            raise MeshOverlayError("invalid mesh depth scope relation")
        object.__setattr__(
            self,
            "requested_claim_refs",
            tuple(sorted(set(self.requested_claim_refs), key=qualified_node_key)),
        )
        object.__setattr__(
            self,
            "important_node_refs",
            tuple(sorted(set(self.important_node_refs), key=qualified_node_key)),
        )
        object.__setattr__(self, "gaps", tuple(sorted(set(self.gaps))))

    @property
    def licenses_mesh_scope(self) -> bool:
        return (
            self.broad_claim_licensed
            and self.status == "pass"
            and self.scope_relation in {"exact", "materialization_superset"}
            and not self.gaps
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_ref": self.model_ref.to_dict(),
            "depth_receipt_digest": self.depth_receipt_digest,
            "model_fingerprint": self.model_fingerprint,
            "requested_claim_refs": [item.to_dict() for item in self.requested_claim_refs],
            "important_node_refs": [item.to_dict() for item in self.important_node_refs],
            "scope_relation": self.scope_relation,
            "status": self.status,
            "broad_claim_licensed": self.broad_claim_licensed,
            "gaps": list(self.gaps),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshDepthBinding":
        return cls(
            model_ref=QualifiedModelRef.from_dict(_require(raw, "model_ref")),
            depth_receipt_digest=str(_require(raw, "depth_receipt_digest")),
            model_fingerprint=str(_require(raw, "model_fingerprint")),
            requested_claim_refs=tuple(
                QualifiedNodeRef.from_dict(item) for item in _require(raw, "requested_claim_refs")
            ),
            important_node_refs=tuple(
                QualifiedNodeRef.from_dict(item) for item in _require(raw, "important_node_refs")
            ),
            scope_relation=str(_require(raw, "scope_relation")),
            status=str(_require(raw, "status")),
            broad_claim_licensed=bool(_require(raw, "broad_claim_licensed")),
            gaps=tuple(_require(raw, "gaps")),
        )


@dataclass(frozen=True, order=True)
class EvidenceContributionRecord:
    target: QualifiedNodeRef
    contribution_key: str
    source_identity: str
    content_hash: str
    independence_group: str
    arrivals: tuple[QualifiedNodeRef, ...]
    duplicate_arrival_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "arrivals", tuple(sorted(set(self.arrivals), key=qualified_node_key))
        )
        if self.duplicate_arrival_count != max(len(self.arrivals) - 1, 0):
            raise MeshOverlayError("duplicate arrival count does not match unique arrivals")

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target.to_dict(),
            "contribution_key": self.contribution_key,
            "source_identity": self.source_identity,
            "content_hash": self.content_hash,
            "independence_group": self.independence_group,
            "arrivals": [item.to_dict() for item in self.arrivals],
            "duplicate_arrival_count": self.duplicate_arrival_count,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "EvidenceContributionRecord":
        return cls(
            target=QualifiedNodeRef.from_dict(_require(raw, "target")),
            contribution_key=str(_require(raw, "contribution_key")),
            source_identity=str(_require(raw, "source_identity")),
            content_hash=str(_require(raw, "content_hash")),
            independence_group=str(_require(raw, "independence_group")),
            arrivals=tuple(QualifiedNodeRef.from_dict(item) for item in _require(raw, "arrivals")),
            duplicate_arrival_count=int(_require(raw, "duplicate_arrival_count")),
        )


@dataclass(frozen=True)
class MeshCurrentnessDiagnostic:
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class MeshOverlayCurrentness:
    binding_current: bool
    catalog_registered: bool
    catalog_current: bool
    dependency_authority_current: bool
    not_invalidated: bool
    current: bool
    broad_current: bool
    diagnostics: tuple[MeshCurrentnessDiagnostic, ...]

    @property
    def ok(self) -> bool:
        return self.current

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_current": self.binding_current,
            "catalog_registered": self.catalog_registered,
            "catalog_current": self.catalog_current,
            "dependency_authority_current": self.dependency_authority_current,
            "not_invalidated": self.not_invalidated,
            "current": self.current,
            "broad_current": self.broad_current,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }


@dataclass(frozen=True)
class MeshEvaluationOverlay:
    mesh_id: MeshId
    mesh_revision: MeshRevision
    mesh_content_digest: str
    materialization_fingerprint: str
    authoritative_universe_fingerprint: str
    requested_claim_scope: tuple[QualifiedNodeRef, ...]
    selected_models: tuple[QualifiedModelRef, ...]
    profile: str
    completeness: str
    truncated: bool
    node_results: tuple[MeshNodeResult, ...]
    block_results: tuple[Mapping[str, Any], ...]
    model_sccs: tuple[Mapping[str, Any], ...]
    cycles: tuple[Mapping[str, Any], ...]
    contribution_ledger: tuple[EvidenceContributionRecord, ...]
    depth_bindings: tuple[MeshDepthBinding, ...]
    unresolved_references: tuple[Mapping[str, Any], ...]
    gaps: tuple[str, ...]
    warnings: tuple[str, ...]
    dependency_binding: OverlayDependencyBinding
    evaluator_fingerprint: str
    simulator_fingerprint: str
    package_version: str
    authority: str
    broad_claim_licensed: bool
    claim_boundary: str = MESH_STRUCTURAL_CLAIM_BOUNDARY
    artifact_schema: str = MESH_EVALUATION_OVERLAY_SCHEMA
    mesh_schema_version: str = MESH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "mesh_id", MeshId.parse(self.mesh_id))
        object.__setattr__(self, "mesh_revision", MeshRevision.parse(self.mesh_revision))
        if self.artifact_schema != MESH_EVALUATION_OVERLAY_SCHEMA:
            raise MeshOverlayError("unsupported mesh evaluation overlay schema")
        if self.mesh_schema_version != MESH_SCHEMA_VERSION:
            raise MeshOverlayError("unsupported mesh schema version")
        if self.profile not in {"broad", "bounded"}:
            raise MeshOverlayError("mesh overlay profile must be broad or bounded")
        if self.completeness not in {"complete", "partial"}:
            raise MeshOverlayError("mesh overlay completeness must be complete or partial")
        if self.authority not in {"production", "simulation"}:
            raise MeshOverlayError("mesh overlay authority must be production or simulation")
        object.__setattr__(
            self,
            "requested_claim_scope",
            tuple(sorted(set(self.requested_claim_scope), key=qualified_node_key)),
        )
        object.__setattr__(
            self, "selected_models", tuple(sorted(set(self.selected_models), key=qualified_model_key))
        )
        object.__setattr__(
            self, "node_results", tuple(sorted(self.node_results, key=lambda item: qualified_node_key(item.node_ref)))
        )
        object.__setattr__(self, "block_results", tuple(_freeze(dict(item)) for item in self.block_results))
        object.__setattr__(self, "model_sccs", tuple(_freeze(dict(item)) for item in self.model_sccs))
        object.__setattr__(self, "cycles", tuple(_freeze(dict(item)) for item in self.cycles))
        object.__setattr__(
            self,
            "contribution_ledger",
            tuple(sorted(self.contribution_ledger, key=lambda item: (qualified_node_key(item.target), item.contribution_key))),
        )
        object.__setattr__(
            self, "depth_bindings", tuple(sorted(self.depth_bindings, key=lambda item: qualified_model_key(item.model_ref)))
        )
        object.__setattr__(
            self,
            "unresolved_references",
            tuple(_freeze(dict(item)) for item in self.unresolved_references),
        )
        object.__setattr__(self, "gaps", tuple(sorted(set(self.gaps))))
        object.__setattr__(self, "warnings", tuple(sorted(set(self.warnings))))
        if self.dependency_binding.mesh_id != self.mesh_id or self.dependency_binding.mesh_revision != self.mesh_revision:
            raise MeshOverlayError("overlay dependency binding names a different mesh revision")
        if self.dependency_binding.mesh_content_digest != self.mesh_content_digest:
            raise MeshOverlayError("overlay dependency binding names a different mesh digest")
        if self.dependency_binding.materialization_fingerprint != self.materialization_fingerprint:
            raise MeshOverlayError("overlay dependency binding names a different materialization")
        if self.broad_claim_licensed and not self._broad_prerequisites():
            raise MeshOverlayError("broad_claim_licensed is inconsistent with overlay boundaries")
        if "does not establish factual truth" not in self.claim_boundary:
            raise MeshOverlayError("mesh claim boundary must distinguish structure from factual truth")

    def _broad_prerequisites(self) -> bool:
        return (
            self.profile == "broad"
            and self.authority == "production"
            and self.completeness == "complete"
            and not self.truncated
            and not self.unresolved_references
            and not self.gaps
            and bool(self.depth_bindings)
            and all(item.licenses_mesh_scope for item in self.depth_bindings)
            and all(
                next((result.state for result in self.node_results if result.node_ref == ref), None)
                == STATE_IN
                for ref in self.requested_claim_scope
            )
        )

    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "artifact_schema": self.artifact_schema,
            "mesh_schema_version": self.mesh_schema_version,
            "mesh_id": str(self.mesh_id),
            "mesh_revision": str(self.mesh_revision),
            "mesh_content_digest": self.mesh_content_digest,
            "materialization_fingerprint": self.materialization_fingerprint,
            "authoritative_universe_fingerprint": self.authoritative_universe_fingerprint,
            "requested_claim_scope": [item.to_dict() for item in self.requested_claim_scope],
            "selected_models": [item.to_dict() for item in self.selected_models],
            "profile": self.profile,
            "completeness": self.completeness,
            "truncated": self.truncated,
            "node_results": [item.to_dict() for item in self.node_results],
            "block_results": [_thaw(item) for item in self.block_results],
            "model_sccs": [_thaw(item) for item in self.model_sccs],
            "cycles": [_thaw(item) for item in self.cycles],
            "contribution_ledger": [item.to_dict() for item in self.contribution_ledger],
            "depth_bindings": [item.to_dict() for item in self.depth_bindings],
            "unresolved_references": [_thaw(item) for item in self.unresolved_references],
            "gaps": list(self.gaps),
            "warnings": list(self.warnings),
            "dependency_binding": self.dependency_binding.to_dict(),
            "evaluator_fingerprint": self.evaluator_fingerprint,
            "simulator_fingerprint": self.simulator_fingerprint,
            "package_version": self.package_version,
            "authority": self.authority,
            "broad_claim_licensed": self.broad_claim_licensed,
            "claim_boundary": self.claim_boundary,
        }

    @property
    def fingerprint(self) -> str:
        return canonical_digest(self.fingerprint_payload())

    @property
    def evaluation_id(self) -> MeshEvaluationId:
        return MeshEvaluationId(f"mesh-eval-{self.fingerprint.split(':', 1)[1]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.fingerprint_payload(),
            "evaluation_id": str(self.evaluation_id),
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MeshEvaluationOverlay":
        overlay = cls(
            artifact_schema=str(_require(raw, "artifact_schema")),
            mesh_schema_version=str(_require(raw, "mesh_schema_version")),
            mesh_id=MeshId.parse(_require(raw, "mesh_id")),
            mesh_revision=MeshRevision.parse(_require(raw, "mesh_revision")),
            mesh_content_digest=str(_require(raw, "mesh_content_digest")),
            materialization_fingerprint=str(_require(raw, "materialization_fingerprint")),
            authoritative_universe_fingerprint=str(_require(raw, "authoritative_universe_fingerprint")),
            requested_claim_scope=tuple(
                QualifiedNodeRef.from_dict(item) for item in _require(raw, "requested_claim_scope")
            ),
            selected_models=tuple(
                QualifiedModelRef.from_dict(item) for item in _require(raw, "selected_models")
            ),
            profile=str(_require(raw, "profile")),
            completeness=str(_require(raw, "completeness")),
            truncated=bool(_require(raw, "truncated")),
            node_results=tuple(MeshNodeResult.from_dict(item) for item in _require(raw, "node_results")),
            block_results=tuple(_require(raw, "block_results")),
            model_sccs=tuple(_require(raw, "model_sccs")),
            cycles=tuple(_require(raw, "cycles")),
            contribution_ledger=tuple(
                EvidenceContributionRecord.from_dict(item)
                for item in _require(raw, "contribution_ledger")
            ),
            depth_bindings=tuple(
                MeshDepthBinding.from_dict(item) for item in _require(raw, "depth_bindings")
            ),
            unresolved_references=tuple(_require(raw, "unresolved_references")),
            gaps=tuple(_require(raw, "gaps")),
            warnings=tuple(_require(raw, "warnings")),
            dependency_binding=OverlayDependencyBinding.from_dict(
                _require(raw, "dependency_binding")
            ),
            evaluator_fingerprint=str(_require(raw, "evaluator_fingerprint")),
            simulator_fingerprint=str(_require(raw, "simulator_fingerprint")),
            package_version=str(_require(raw, "package_version")),
            authority=str(_require(raw, "authority")),
            broad_claim_licensed=bool(_require(raw, "broad_claim_licensed")),
            claim_boundary=str(_require(raw, "claim_boundary")),
        )
        if str(_require(raw, "evaluation_id")) != str(overlay.evaluation_id):
            raise MeshOverlayError("mesh evaluation ID does not match content")
        if str(_require(raw, "fingerprint")) != overlay.fingerprint:
            raise MeshOverlayError("mesh evaluation fingerprint does not match content")
        return overlay

    def currentness(
        self,
        snapshot: ModelMeshSnapshot,
        *,
        catalog_snapshot: Any | None,
        invalidated_overlay_ids: Iterable[MeshEvaluationId | str] = (),
        dependency_authority_current: bool = True,
        head_drift: Iterable[Any] = (),
    ) -> MeshOverlayCurrentness:
        diagnostics: list[MeshCurrentnessDiagnostic] = []
        head_drift_items = tuple(head_drift)
        binding_current = (
            self.mesh_id == snapshot.mesh_id
            and self.mesh_revision == snapshot.revision
            and self.mesh_content_digest == snapshot.content_digest
        )
        if not binding_current:
            diagnostics.append(
                MeshCurrentnessDiagnostic("mesh_binding_mismatch", "overlay is bound to another mesh revision")
            )
        catalog_registered = False
        catalog_current = False
        if catalog_snapshot is None:
            diagnostics.append(
                MeshCurrentnessDiagnostic("catalog_missing", "exact OverlayCatalog authority is required")
            )
        else:
            catalog_current = (
                getattr(catalog_snapshot, "mesh_id", None) == self.mesh_id
                and getattr(catalog_snapshot, "mesh_revision", None) == self.mesh_revision
            )
            entries = getattr(catalog_snapshot, "entries", ())
            catalog_registered = any(
                str(getattr(item, "overlay_id", "")) == str(self.evaluation_id)
                and getattr(item, "overlay_digest", "") == self.fingerprint
                for item in entries
            )
            if not catalog_current:
                diagnostics.append(
                    MeshCurrentnessDiagnostic("catalog_mesh_mismatch", "catalog pins another mesh revision")
                )
            if not catalog_registered:
                diagnostics.append(
                    MeshCurrentnessDiagnostic("overlay_unregistered", "overlay is absent from the exact catalog")
                )
        invalidated = {str(item) for item in invalidated_overlay_ids}
        not_invalidated = str(self.evaluation_id) not in invalidated
        if not not_invalidated:
            diagnostics.append(
                MeshCurrentnessDiagnostic("overlay_invalidated", "overlay dependency closure changed")
            )
        if not dependency_authority_current:
            diagnostics.append(
                MeshCurrentnessDiagnostic("dependency_authority_stale", "dependency shard or receipt is not current")
            )
        if head_drift_items:
            diagnostics.append(
                MeshCurrentnessDiagnostic("model_head_drift", "one or more P0 model heads advanced outside the mesh")
            )
        current = (
            binding_current
            and catalog_registered
            and catalog_current
            and dependency_authority_current
            and not_invalidated
            and not head_drift_items
            and self.authority == "production"
        )
        broad_current = current and self.broad_claim_licensed and self._broad_prerequisites()
        return MeshOverlayCurrentness(
            binding_current=binding_current,
            catalog_registered=catalog_registered,
            catalog_current=catalog_current,
            dependency_authority_current=dependency_authority_current,
            not_invalidated=not_invalidated,
            current=current,
            broad_current=broad_current,
            diagnostics=tuple(diagnostics),
        )


__all__ = [
    "EvidenceContributionRecord",
    "MESH_STRUCTURAL_CLAIM_BOUNDARY",
    "MeshCurrentnessDiagnostic",
    "MeshDependencyKey",
    "MeshDepthBinding",
    "MeshEvaluationOverlay",
    "MeshNodeResult",
    "MeshOverlayCurrentness",
    "MeshOverlayError",
    "OverlayDependencyBinding",
]
