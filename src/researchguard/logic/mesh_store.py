"""Transactional current-schema filesystem store for product-runtime ModelMesh."""

from __future__ import annotations

import base64
import hashlib
import importlib.metadata
import json
import os
import socket
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping, Protocol

from .identity import (
    EdgeId,
    MeshEvaluationId,
    MeshId,
    MeshReceiptId,
    MeshRevision,
    MeshTransactionId,
    OverlayCatalogRevision,
    QualifiedModelRef,
    QualifiedNodeRef,
)
from .mesh_index import MeshIndexBundle, MeshIndexShard, MeshIndexView, compile_mesh_indexes
from .mesh_invalidation import compute_overlay_invalidation
from .mesh_overlay import MeshEvaluationOverlay
from .mesh_overlay_catalog import (
    OverlayCatalogEntry,
    OverlayCatalogError,
    OverlayCatalogSnapshot,
    OverlayCatalogTransaction,
    OverlayDependencyShard,
    OverlayDependencyShardBundle,
    create_catalog_snapshot,
)
from .mesh_receipts import (
    MeshAbortReceipt,
    MeshCommitReceipt,
    MeshConflictReceipt,
    MeshIndexRepairReceipt,
    MeshInvalidationReceipt,
    MeshRecoveryReceipt,
    OverlayCatalogCommitReceipt,
)
from .mesh_transaction import ModelMeshTransaction
from .model_mesh import (
    CrossModelEdge,
    MeshIntegrityError,
    MeshMembership,
    MeshNotFoundError,
    MeshRevisionNotFoundError,
    ModelHeadDrift,
    ModelMeshDefinition,
    ModelMeshSnapshot,
    ModelRegistryEntry,
    OverlayCatalogPin,
    detect_model_head_drift,
    qualified_model_key,
    qualified_node_key,
    validate_definition_against_store,
)
from .model_store import canonical_digest, canonical_json_bytes
from .receipts import utc_now
from .schema import (
    MESH_JOURNAL_SCHEMA,
    MESH_MANIFEST_SCHEMA,
    MESH_OVERLAY_CATALOG_MANIFEST_SCHEMA,
    MESH_SCHEMA_VERSION,
)


FaultHook = Callable[[str], None]


def _storage_segment(identity: Any) -> str:
    # A 96-bit fixed-width projection keeps the deepest catalog paths below
    # legacy Windows MAX_PATH even under long pytest/user roots.  The complete
    # identity remains inside every artifact and is checked on read, so this is
    # a path projection rather than a second identity authority.
    digest = hashlib.sha256(str(identity).encode("utf-8")).digest()[:12]
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"h-{encoded}"


def _package_version() -> str:
    try:
        return importlib.metadata.version("logicguard")
    except importlib.metadata.PackageNotFoundError:
        return "0+local"


MESH_STORE_TOOL_FINGERPRINT = canonical_digest(
    {
        "component": "researchguard.logic.file-model-mesh-store",
        "mesh_schema_version": MESH_SCHEMA_VERSION,
        "package_version": _package_version(),
        "publication_protocol": "mesh-catalog-shared-writer-lock-v1",
    }
)


class MeshStoreError(RuntimeError):
    """Base error for filesystem ModelMesh authority."""


class MeshStoreSchemaError(MeshStoreError):
    """A durable artifact does not use the sole current schema."""


class MeshStoreCorruptionError(MeshStoreError):
    """A manifest-authorized artifact is missing, unreadable, or inconsistent."""


class MeshWriterLockHeldError(MeshStoreError):
    """The shared mesh/catalog writer lock has a live or unverifiable owner."""


class MeshRecoveryRequiredError(MeshStoreError):
    """A prepared operation requires explicit deterministic recovery."""


class MeshTransactionConflictError(MeshStoreError):
    def __init__(self, *, receipt: MeshConflictReceipt) -> None:
        super().__init__(receipt.reason)
        self.receipt = receipt
        self.expected = receipt.expected_revision
        self.actual = receipt.actual_revision


class MeshIdempotencyConflictError(MeshStoreError):
    def __init__(self, *, receipt: MeshConflictReceipt) -> None:
        super().__init__(receipt.reason)
        self.receipt = receipt


class OverlayCatalogConflictError(MeshStoreError):
    def __init__(self, *, receipt: MeshConflictReceipt) -> None:
        super().__init__(receipt.reason)
        self.receipt = receipt
        self.expected = receipt.expected_catalog_revision
        self.actual = receipt.actual_catalog_revision


class TestInjectedMeshStoreFault(RuntimeError):
    """Exception intended only for deterministic publication-boundary tests."""

    __test__ = False


class ModelMeshStore(Protocol):
    def head(self, mesh_id: MeshId | str) -> MeshRevision | None: ...

    def get(
        self, mesh_id: MeshId | str, revision: MeshRevision | str | None = None
    ) -> ModelMeshSnapshot: ...

    def list_meshes(self) -> tuple[MeshId, ...]: ...

    def list_revisions(self, mesh_id: MeshId | str) -> tuple[MeshRevision, ...]: ...

    def begin(
        self,
        mesh_id: MeshId | str,
        expected_revision: MeshRevision | str | None,
        idempotency_key: str,
        actor: str,
        *,
        expected_overlay_catalog_revision: OverlayCatalogRevision | str | None,
    ) -> ModelMeshTransaction: ...


class MeshRevisionView:
    """Digest-verified lazy read view over one exact mesh revision."""

    def __init__(
        self,
        store: "FileModelMeshStore",
        snapshot: ModelMeshSnapshot,
        indexes: MeshIndexBundle,
    ) -> None:
        self._store = store
        self.snapshot = snapshot
        self.indexes = indexes
        self.index = MeshIndexView(snapshot, indexes)
        self._registry = {item.model_ref: item for item in snapshot.registry}
        self._models: dict[QualifiedModelRef, Any] = {}
        self._model_read_count = 0
        self._memberships_by_owner: dict[QualifiedNodeRef, list[MeshMembership]] = {}
        self._memberships_by_model: dict[QualifiedModelRef, list[MeshMembership]] = {}
        self._edges_by_id = {item.id: item for item in snapshot.cross_model_edges}
        self._out_edges: dict[QualifiedNodeRef, list[CrossModelEdge]] = {}
        self._in_edges: dict[QualifiedNodeRef, list[CrossModelEdge]] = {}
        for membership in snapshot.memberships:
            self._memberships_by_owner.setdefault(membership.owner, []).append(membership)
            self._memberships_by_model.setdefault(membership.logical_model, []).append(
                membership
            )
        for edge in snapshot.cross_model_edges:
            self._out_edges.setdefault(edge.source, []).append(edge)
            self._in_edges.setdefault(edge.target, []).append(edge)

    @property
    def model_read_count(self) -> int:
        return self._model_read_count

    def registry_entry(self, ref: QualifiedModelRef) -> ModelRegistryEntry:
        try:
            return self._registry[ref]
        except KeyError as exc:
            raise MeshIntegrityError(f"model ref is not registered in mesh: {ref}") from exc

    def model_snapshot(self, ref: QualifiedModelRef):
        entry = self.registry_entry(ref)
        if ref not in self._models:
            snapshot = self.exact_model_snapshot(ref)
            if snapshot.content_digest != entry.content_digest:
                raise MeshIntegrityError(f"P0 content digest drift for pinned model {ref}")
            self._models[ref] = snapshot
            self._model_read_count += 1
        return self._models[ref]

    def exact_model_snapshot(self, ref: QualifiedModelRef):
        """Load one exact P0 revision without floating-head resolution.

        This deliberately does not require the revision to be present in the
        current mesh registry.  Sparse simulation uses it to inspect a
        proposed replacement pin while preserving exact P0 identity.  Normal
        mesh reads should continue through :meth:`model_snapshot`, which also
        enforces the current registry digest.
        """

        identity = (
            ref if isinstance(ref, QualifiedModelRef) else QualifiedModelRef.from_dict(ref)
        )
        return self._store.model_store.get(identity.model_id, identity.revision)

    def node(self, ref: QualifiedNodeRef) -> Mapping[str, Any]:
        model_ref = QualifiedModelRef(ref.model_id, ref.revision)
        snapshot = self.model_snapshot(model_ref)
        try:
            return snapshot.model_payload["nodes"][str(ref.node_id)]
        except KeyError as exc:
            raise MeshIntegrityError(f"node is absent from pinned P0 model: {ref}") from exc

    def memberships_for_node(self, ref: QualifiedNodeRef) -> tuple[MeshMembership, ...]:
        return tuple(
            sorted(
                self._memberships_by_owner.get(ref, ()),
                key=lambda item: qualified_model_key(item.logical_model),
            )
        )

    def members_of_model(self, ref: QualifiedModelRef) -> tuple[MeshMembership, ...]:
        return tuple(
            sorted(
                self._memberships_by_model.get(ref, ()),
                key=lambda item: qualified_node_key(item.owner),
            )
        )

    def outgoing_cross_edges(self, ref: QualifiedNodeRef) -> tuple[CrossModelEdge, ...]:
        return tuple(sorted(self._out_edges.get(ref, ()), key=lambda item: str(item.id)))

    def incoming_cross_edges(self, ref: QualifiedNodeRef) -> tuple[CrossModelEdge, ...]:
        return tuple(sorted(self._in_edges.get(ref, ()), key=lambda item: str(item.id)))

    def cross_edge(self, edge_id: EdgeId | str) -> CrossModelEdge:
        identity = EdgeId.parse(edge_id)
        try:
            return self._edges_by_id[identity]
        except KeyError as exc:
            raise MeshIntegrityError(f"cross edge is not in mesh: {identity}") from exc

    def model_dependencies(self, ref: QualifiedModelRef) -> tuple[QualifiedModelRef, ...]:
        return self.index.model_dependencies(ref)

    def evidence_contributions(self) -> tuple[Mapping[str, Any], ...]:
        from .mesh_index import EVIDENCE_BY_KEY_SHARD

        return self.indexes.by_kind(EVIDENCE_BY_KEY_SHARD).records


class FileModelMeshStore:
    """One-writer immutable-revision mesh and overlay-catalog store.

    Normal runtime recognizes one layout rooted at ``mesh-manifest.json``.  It
    never searches for an alternate manifest, old schema, alias, or cache.
    """

    _MESH_COMMIT_FAULT_POINTS = (
        "after_lock",
        "after_journal",
        "after_shards",
        "after_snapshot",
        "after_invalidation_receipt",
        "after_commit_receipt",
        "after_child_catalog_snapshot",
        "after_catalog_manifest",
        "after_mesh_manifest",
        "after_terminal_journal",
    )
    _CATALOG_COMMIT_FAULT_POINTS = (
        "catalog_after_lock",
        "catalog_after_journal",
        "catalog_after_overlay",
        "catalog_after_shards",
        "catalog_after_snapshot",
        "catalog_after_receipt",
        "catalog_after_manifest",
        "catalog_after_terminal_journal",
    )

    def __init__(
        self,
        root: str | Path,
        *,
        model_store,
        _test_fault_hook: FaultHook | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.model_store = model_store
        self._test_fault_hook = _test_fault_hook
        self._manifest_path = self.root / "mesh-manifest.json"
        self._meshes_dir = self.root / "m"
        self._catalogs_dir = self.root / "c"
        self._journals_dir = self.root / "j"
        self._receipts_dir = self.root / "r"
        self._locks_dir = self.root / "locks"
        self._writer_lock_path = self._locks_dir / "writer.lock"
        preexisting_nonempty = self.root.exists() and any(self.root.iterdir())
        if not self._manifest_path.exists() and preexisting_nonempty:
            raise MeshStoreCorruptionError(
                f"mesh store {self.root} is non-empty but current authority "
                f"{self._manifest_path} is missing; no fallback layout is allowed"
            )
        self._ensure_layout()
        if not self._manifest_path.exists():
            self._atomic_write_json(self._manifest_path, self._initial_manifest())
        self._load_manifest()

    @property
    def mesh_commit_fault_points(self) -> tuple[str, ...]:
        return self._MESH_COMMIT_FAULT_POINTS

    @property
    def catalog_commit_fault_points(self) -> tuple[str, ...]:
        return self._CATALOG_COMMIT_FAULT_POINTS

    def head(self, mesh_id: MeshId | str) -> MeshRevision | None:
        identity = MeshId.parse(mesh_id)
        entry = self._load_manifest()["meshes"].get(str(identity))
        if not entry or not entry.get("head"):
            return None
        return MeshRevision.parse(entry["head"])

    def get(
        self,
        mesh_id: MeshId | str,
        revision: MeshRevision | str | None = None,
    ) -> ModelMeshSnapshot:
        identity = MeshId.parse(mesh_id)
        manifest = self._load_manifest()
        entry = manifest["meshes"].get(str(identity))
        if not entry:
            raise MeshNotFoundError(f"mesh not found: {identity}")
        requested = str(MeshRevision.parse(revision)) if revision is not None else entry.get("head")
        if not requested:
            raise MeshNotFoundError(f"mesh has no current head: {identity}")
        if requested not in tuple(entry.get("revisions") or ()):
            raise MeshRevisionNotFoundError(
                f"mesh revision {requested!r} is not manifest-authorized for {identity}"
            )
        snapshot = self._read_mesh_snapshot(identity, MeshRevision.parse(requested))
        if revision is None and str(snapshot.revision) != entry.get("head"):
            raise MeshStoreCorruptionError("mesh head does not bind loaded snapshot")
        self._read_mesh_indexes(snapshot)
        return snapshot

    def list_meshes(self) -> tuple[MeshId, ...]:
        return tuple(MeshId(item) for item in sorted(self._load_manifest()["meshes"]))

    def list_revisions(self, mesh_id: MeshId | str) -> tuple[MeshRevision, ...]:
        identity = MeshId.parse(mesh_id)
        entry = self._load_manifest()["meshes"].get(str(identity))
        if not entry:
            raise MeshNotFoundError(f"mesh not found: {identity}")
        return tuple(MeshRevision.parse(item) for item in entry.get("revisions") or ())

    def begin(
        self,
        mesh_id: MeshId | str,
        expected_revision: MeshRevision | str | None,
        idempotency_key: str,
        actor: str,
        *,
        expected_overlay_catalog_revision: OverlayCatalogRevision | str | None,
    ) -> ModelMeshTransaction:
        return ModelMeshTransaction(
            store=self,
            mesh_id=mesh_id,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            actor=actor,
            expected_overlay_catalog_revision=expected_overlay_catalog_revision,
        )

    def open_view(
        self, mesh_id: MeshId | str, revision: MeshRevision | str | None = None
    ) -> MeshRevisionView:
        snapshot = self.get(mesh_id, revision)
        return MeshRevisionView(self, snapshot, self._read_mesh_indexes(snapshot))

    def head_drift(
        self, mesh_id: MeshId | str, revision: MeshRevision | str | None = None
    ) -> tuple[ModelHeadDrift, ...]:
        return detect_model_head_drift(self.get(mesh_id, revision), self.model_store)

    def catalog_head(
        self, mesh_id: MeshId | str, mesh_revision: MeshRevision | str
    ) -> OverlayCatalogRevision:
        snapshot = self.get(mesh_id, mesh_revision)
        manifest = self._load_catalog_manifest(snapshot.mesh_id, snapshot.revision)
        return OverlayCatalogRevision.parse(manifest["head"])

    def get_catalog(
        self,
        mesh_id: MeshId | str,
        mesh_revision: MeshRevision | str,
        catalog_revision: OverlayCatalogRevision | str | None = None,
    ) -> OverlayCatalogSnapshot:
        mesh_snapshot = self.get(mesh_id, mesh_revision)
        manifest = self._load_catalog_manifest(mesh_snapshot.mesh_id, mesh_snapshot.revision)
        requested = (
            str(OverlayCatalogRevision.parse(catalog_revision))
            if catalog_revision is not None
            else manifest["head"]
        )
        if requested not in tuple(manifest.get("revisions") or ()):
            raise OverlayCatalogError(
                f"catalog revision {requested!r} is not manifest-authorized"
            )
        snapshot = self._read_catalog_snapshot(
            mesh_snapshot.mesh_id,
            mesh_snapshot.revision,
            OverlayCatalogRevision.parse(requested),
        )
        self._read_catalog_shards(snapshot)
        return snapshot

    def current_catalog_pin(
        self, mesh_id: MeshId | str, mesh_revision: MeshRevision | str
    ) -> OverlayCatalogPin:
        return self.get_catalog(mesh_id, mesh_revision).pin

    def begin_catalog(
        self,
        mesh_id: MeshId | str,
        mesh_revision: MeshRevision | str,
        expected_catalog_revision: OverlayCatalogRevision | str,
        idempotency_key: str,
        actor: str,
    ) -> OverlayCatalogTransaction:
        return OverlayCatalogTransaction(
            store=self,
            mesh_id=mesh_id,
            mesh_revision=mesh_revision,
            expected_catalog_revision=expected_catalog_revision,
            idempotency_key=idempotency_key,
            actor=actor,
        )

    def get_overlay(
        self,
        mesh_id: MeshId | str,
        mesh_revision: MeshRevision | str,
        overlay_id: MeshEvaluationId | str,
    ) -> MeshEvaluationOverlay:
        catalog = self.get_catalog(mesh_id, mesh_revision)
        identity = MeshEvaluationId.parse(overlay_id)
        entry = next((item for item in catalog.entries if item.overlay_id == identity), None)
        if entry is None:
            raise OverlayCatalogError(f"overlay is not catalog-authorized: {identity}")
        path = self._overlay_path(catalog.mesh_id, catalog.mesh_revision, identity)
        overlay = MeshEvaluationOverlay.from_dict(self._read_json(path))
        if overlay.fingerprint != entry.overlay_digest:
            raise MeshStoreCorruptionError(f"overlay digest differs from catalog entry: {path}")
        return overlay

    def catalog_dependents(
        self,
        catalog_pin: OverlayCatalogPin,
        dependency_digests: Iterable[str],
    ) -> tuple[MeshEvaluationId, ...]:
        catalog = self.get_catalog(
            catalog_pin.mesh_id,
            catalog_pin.mesh_revision,
            catalog_pin.catalog_revision,
        )
        if catalog.content_digest != catalog_pin.catalog_content_digest:
            raise MeshStoreCorruptionError("catalog pin digest mismatch")
        return catalog.dependents(dependency_digests)

    def get_invalidation_receipt(
        self, receipt_id: MeshReceiptId | str
    ) -> MeshInvalidationReceipt:
        identity = MeshReceiptId.parse(receipt_id)
        path = self._receipt_path("mesh-invalidations", identity)
        try:
            return MeshInvalidationReceipt.from_dict(self._read_json(path))
        except FileNotFoundError as exc:
            raise MeshStoreCorruptionError(
                f"declared mesh invalidation receipt is missing: {path}"
            ) from exc

    def _commit_mesh_transaction(
        self, transaction: ModelMeshTransaction, definition: ModelMeshDefinition
    ) -> MeshCommitReceipt:
        snapshots = validate_definition_against_store(definition, self.model_store)
        indexes = compile_mesh_indexes(definition, model_snapshots=snapshots)
        committed_at = utc_now()
        mesh_snapshot = ModelMeshSnapshot.create(
            definition,
            parent_revision=transaction.expected_revision,
            shard_sets=indexes.shard_sets,
            created_at=committed_at,
            created_by=transaction.actor,
        )
        with self._writer_lock(transaction.transaction_id):
            self._fault("after_lock")
            manifest = self._load_manifest()
            previous = manifest["idempotency"].get(transaction.idempotency_key)
            if previous:
                return self._resolve_mesh_idempotent_retry(
                    previous, transaction, mesh_snapshot
                )
            self._raise_if_prepared_journal()
            entry = manifest["meshes"].get(str(transaction.mesh_id)) or {}
            actual_head = MeshRevision.parse(entry["head"]) if entry.get("head") else None
            if actual_head != transaction.expected_revision:
                receipt = MeshConflictReceipt.create(
                    transaction_id=transaction.transaction_id,
                    mesh_id=transaction.mesh_id,
                    conflict_kind="mesh_compare_and_swap",
                    expected_revision=transaction.expected_revision,
                    actual_revision=actual_head,
                    expected_catalog_revision=transaction.expected_overlay_catalog_revision,
                    actual_catalog_revision=None,
                    reason="declared mesh head differs from manifest-authorized head",
                )
                self._write_conflict(receipt)
                raise MeshTransactionConflictError(receipt=receipt)

            parent_snapshot = None
            parent_indexes = None
            parent_catalog = None
            if transaction.expected_revision is not None:
                parent_snapshot = self._read_mesh_snapshot(
                    transaction.mesh_id, transaction.expected_revision
                )
                parent_indexes = self._read_mesh_indexes(parent_snapshot)
                parent_catalog_manifest = self._load_catalog_manifest(
                    transaction.mesh_id, transaction.expected_revision
                )
                actual_catalog_revision = OverlayCatalogRevision.parse(
                    parent_catalog_manifest["head"]
                )
                if actual_catalog_revision != transaction.expected_overlay_catalog_revision:
                    receipt = MeshConflictReceipt.create(
                        transaction_id=transaction.transaction_id,
                        mesh_id=transaction.mesh_id,
                        conflict_kind="catalog_compare_and_swap",
                        expected_revision=transaction.expected_revision,
                        actual_revision=actual_head,
                        expected_catalog_revision=transaction.expected_overlay_catalog_revision,
                        actual_catalog_revision=actual_catalog_revision,
                        reason="declared parent catalog head differs from current catalog authority",
                    )
                    self._write_conflict(receipt)
                    raise OverlayCatalogConflictError(receipt=receipt)
                parent_catalog = self._read_catalog_snapshot(
                    transaction.mesh_id,
                    transaction.expected_revision,
                    actual_catalog_revision,
                )
                self._read_catalog_shards(parent_catalog)
                if definition.invalidation_baseline != parent_catalog.pin:
                    receipt = MeshConflictReceipt.create(
                        transaction_id=transaction.transaction_id,
                        mesh_id=transaction.mesh_id,
                        conflict_kind="catalog_pin_digest",
                        expected_revision=transaction.expected_revision,
                        actual_revision=actual_head,
                        expected_catalog_revision=transaction.expected_overlay_catalog_revision,
                        actual_catalog_revision=actual_catalog_revision,
                        reason="staged invalidation baseline is not the exact parent catalog pin",
                    )
                    self._write_conflict(receipt)
                    raise OverlayCatalogConflictError(receipt=receipt)

            snapshots = validate_definition_against_store(definition, self.model_store)
            indexes = compile_mesh_indexes(definition, model_snapshots=snapshots)
            mesh_snapshot = ModelMeshSnapshot.create(
                definition,
                parent_revision=transaction.expected_revision,
                shard_sets=indexes.shard_sets,
                created_at=committed_at,
                created_by=transaction.actor,
            )
            invalidation_receipt: MeshInvalidationReceipt | None = None
            if parent_snapshot is not None and parent_indexes is not None and parent_catalog is not None:
                invalidation_receipt = compute_overlay_invalidation(
                    parent_snapshot=parent_snapshot,
                    parent_indexes=parent_indexes,
                    child_snapshot=mesh_snapshot,
                    child_indexes=indexes,
                    catalog_snapshot=parent_catalog,
                    tool_fingerprint=MESH_STORE_TOOL_FINGERPRINT,
                    created_at=committed_at,
                )
            invalidation_digest = (
                canonical_digest(invalidation_receipt.to_dict())
                if invalidation_receipt is not None
                else None
            )
            child_catalog, child_catalog_shards = create_catalog_snapshot(
                mesh_id=mesh_snapshot.mesh_id,
                mesh_revision=mesh_snapshot.revision,
                parent_revision=None,
                entries=(),
                dependency_bindings=(),
                invalidation_receipt_id=(
                    str(invalidation_receipt.receipt_id)
                    if invalidation_receipt is not None
                    else None
                ),
                invalidation_receipt_digest=invalidation_digest,
                created_at=committed_at,
                created_by=transaction.actor,
            )
            commit_receipt = MeshCommitReceipt.create(
                transaction_id=transaction.transaction_id,
                mesh_id=mesh_snapshot.mesh_id,
                revision=mesh_snapshot.revision,
                parent_revision=mesh_snapshot.parent_revision,
                content_digest=mesh_snapshot.content_digest,
                registry_digest=mesh_snapshot.registry_digest,
                shard_digests=tuple(
                    (item.kind, item.digest) for item in indexes.shards
                ),
                model_pins=tuple(item.model_ref for item in mesh_snapshot.registry),
                parent_catalog_baseline=definition.invalidation_baseline,
                child_catalog_pin=child_catalog.pin,
                invalidation_receipt_id=(
                    invalidation_receipt.receipt_id
                    if invalidation_receipt is not None
                    else None
                ),
                idempotency_key=transaction.idempotency_key,
                actor=transaction.actor,
                committed_at=committed_at,
                package_version=_package_version(),
                tool_fingerprint=MESH_STORE_TOOL_FINGERPRINT,
            )
            next_manifest = self._next_mesh_manifest(
                manifest, transaction, mesh_snapshot, commit_receipt
            )
            child_catalog_manifest = self._initial_catalog_manifest(
                child_catalog, idempotency={}
            )
            required_paths = [
                *(str(self._mesh_shard_path(mesh_snapshot, item.kind)) for item in indexes.shards),
                str(self._mesh_snapshot_path(mesh_snapshot.mesh_id, mesh_snapshot.revision)),
                str(self._receipt_path("mesh-commits", commit_receipt.receipt_id)),
                *(str(self._catalog_shard_path(child_catalog, item.kind)) for item in child_catalog_shards.shards),
                str(self._catalog_snapshot_path(child_catalog.mesh_id, child_catalog.mesh_revision, child_catalog.revision)),
                str(self._catalog_manifest_path(child_catalog.mesh_id, child_catalog.mesh_revision)),
            ]
            if invalidation_receipt is not None:
                required_paths.append(
                    str(self._receipt_path("mesh-invalidations", invalidation_receipt.receipt_id))
                )
            journal = {
                "artifact_schema": MESH_JOURNAL_SCHEMA,
                "mesh_schema_version": MESH_SCHEMA_VERSION,
                "operation": "mesh-commit",
                "status": "prepared",
                "transaction_id": str(transaction.transaction_id),
                "idempotency_key": transaction.idempotency_key,
                "mesh_id": str(transaction.mesh_id),
                "expected_revision": (
                    str(transaction.expected_revision) if transaction.expected_revision else None
                ),
                "target_revision": str(mesh_snapshot.revision),
                "target_receipt_id": str(commit_receipt.receipt_id),
                "required_paths": required_paths,
                "next_manifest": next_manifest,
                "prepared_at": committed_at,
            }
            journal_path = self._journal_path(transaction.transaction_id)
            self._write_immutable_json(journal_path, journal)
            self._fault("after_journal")

            for shard in indexes.shards:
                self._write_immutable_json(
                    self._mesh_shard_path(mesh_snapshot, shard.kind), shard.to_dict()
                )
            self._fault("after_shards")
            self._write_immutable_json(
                self._mesh_snapshot_path(mesh_snapshot.mesh_id, mesh_snapshot.revision),
                mesh_snapshot.to_dict(),
            )
            self._fault("after_snapshot")
            if invalidation_receipt is not None:
                self._write_immutable_json(
                    self._receipt_path(
                        "mesh-invalidations", invalidation_receipt.receipt_id
                    ),
                    invalidation_receipt.to_dict(),
                )
            self._fault("after_invalidation_receipt")
            self._write_immutable_json(
                self._receipt_path("mesh-commits", commit_receipt.receipt_id),
                commit_receipt.to_dict(),
            )
            self._fault("after_commit_receipt")
            for shard in child_catalog_shards.shards:
                self._write_immutable_json(
                    self._catalog_shard_path(child_catalog, shard.kind), shard.to_dict()
                )
            self._write_immutable_json(
                self._catalog_snapshot_path(
                    child_catalog.mesh_id,
                    child_catalog.mesh_revision,
                    child_catalog.revision,
                ),
                child_catalog.to_dict(),
            )
            self._fault("after_child_catalog_snapshot")
            self._atomic_write_json(
                self._catalog_manifest_path(
                    child_catalog.mesh_id, child_catalog.mesh_revision
                ),
                child_catalog_manifest,
            )
            self._fault("after_catalog_manifest")
            self._atomic_write_json(self._manifest_path, next_manifest)
            self._fault("after_mesh_manifest")
            self._terminalize_journal(
                journal_path, journal, "committed", commit_receipt.receipt_id
            )
            self._fault("after_terminal_journal")
            return commit_receipt

    def _abort_mesh_transaction(
        self, transaction: ModelMeshTransaction, reason: str
    ) -> MeshAbortReceipt:
        staged_digest = (
            canonical_digest(transaction.staged_definition.canonical_dict())
            if transaction.staged_definition is not None
            else None
        )
        receipt = MeshAbortReceipt.create(
            transaction_id=transaction.transaction_id,
            mesh_id=transaction.mesh_id,
            actor=transaction.actor,
            reason=reason,
            staged_content_digest=staged_digest,
        )
        with self._writer_lock(transaction.transaction_id):
            self._write_immutable_json(
                self._receipt_path("mesh-aborts", receipt.receipt_id), receipt.to_dict()
            )
        return receipt

    def _commit_catalog_transaction(
        self,
        transaction: OverlayCatalogTransaction,
        overlay: MeshEvaluationOverlay,
    ) -> OverlayCatalogCommitReceipt:
        committed_at = utc_now()
        with self._writer_lock(transaction.transaction_id):
            self._fault("catalog_after_lock")
            mesh_snapshot = self.get(transaction.mesh_id, transaction.mesh_revision)
            if self.head(transaction.mesh_id) != transaction.mesh_revision:
                receipt = MeshConflictReceipt.create(
                    transaction_id=transaction.transaction_id,
                    mesh_id=transaction.mesh_id,
                    conflict_kind="catalog_mesh_head",
                    expected_revision=transaction.mesh_revision,
                    actual_revision=self.head(transaction.mesh_id),
                    expected_catalog_revision=transaction.expected_catalog_revision,
                    actual_catalog_revision=None,
                    reason="production catalog registration requires the exact current mesh head",
                )
                self._write_conflict(receipt)
                raise MeshTransactionConflictError(receipt=receipt)
            if (
                overlay.mesh_content_digest != mesh_snapshot.content_digest
                or overlay.dependency_binding.mesh_content_digest
                != mesh_snapshot.content_digest
            ):
                raise OverlayCatalogError("overlay content binding differs from mesh snapshot")
            manifest = self._load_catalog_manifest(
                transaction.mesh_id, transaction.mesh_revision
            )
            previous = manifest["idempotency"].get(transaction.idempotency_key)
            if previous:
                return self._resolve_catalog_idempotent_retry(
                    previous, transaction, overlay
                )
            self._raise_if_prepared_journal()
            actual = OverlayCatalogRevision.parse(manifest["head"])
            if actual != transaction.expected_catalog_revision:
                receipt = MeshConflictReceipt.create(
                    transaction_id=transaction.transaction_id,
                    mesh_id=transaction.mesh_id,
                    conflict_kind="catalog_compare_and_swap",
                    expected_revision=transaction.mesh_revision,
                    actual_revision=transaction.mesh_revision,
                    expected_catalog_revision=transaction.expected_catalog_revision,
                    actual_catalog_revision=actual,
                    reason="declared catalog head differs from manifest-authorized head",
                )
                self._write_conflict(receipt)
                raise OverlayCatalogConflictError(receipt=receipt)
            parent = self._read_catalog_snapshot(
                transaction.mesh_id, transaction.mesh_revision, actual
            )
            self._read_catalog_shards(parent)
            existing = next(
                (item for item in parent.entries if item.overlay_id == overlay.evaluation_id),
                None,
            )
            if existing is not None:
                receipt = MeshConflictReceipt.create(
                    transaction_id=transaction.transaction_id,
                    mesh_id=transaction.mesh_id,
                    conflict_kind="catalog_duplicate_overlay",
                    expected_revision=transaction.mesh_revision,
                    actual_revision=transaction.mesh_revision,
                    expected_catalog_revision=transaction.expected_catalog_revision,
                    actual_catalog_revision=actual,
                    reason="overlay is already registered under another idempotency owner",
                )
                self._write_conflict(receipt)
                raise MeshIdempotencyConflictError(receipt=receipt)
            entry = OverlayCatalogEntry.from_overlay(
                overlay, registered_at=committed_at
            )
            catalog, shards = create_catalog_snapshot(
                mesh_id=parent.mesh_id,
                mesh_revision=parent.mesh_revision,
                parent_revision=parent.revision,
                entries=(*parent.entries, entry),
                dependency_bindings=(*parent.dependency_bindings, overlay.dependency_binding),
                invalidation_receipt_id=parent.invalidation_receipt_id,
                invalidation_receipt_digest=parent.invalidation_receipt_digest,
                created_at=committed_at,
                created_by=transaction.actor,
            )
            receipt = OverlayCatalogCommitReceipt.create(
                transaction_id=transaction.transaction_id,
                mesh_id=catalog.mesh_id,
                mesh_revision=catalog.mesh_revision,
                catalog_revision=catalog.revision,
                parent_catalog_revision=catalog.parent_revision,
                content_digest=catalog.content_digest,
                dependency_shard_digests=tuple(
                    (item.kind, item.digest) for item in shards.shards
                ),
                overlay_ids=tuple(item.overlay_id for item in catalog.entries),
                idempotency_key=transaction.idempotency_key,
                actor=transaction.actor,
                committed_at=committed_at,
            )
            next_manifest = json.loads(canonical_json_bytes(manifest).decode("utf-8"))
            revisions = list(next_manifest.get("revisions") or ())
            revisions.append(str(catalog.revision))
            next_manifest.update(
                {
                    "head": str(catalog.revision),
                    "revisions": revisions,
                    "head_receipt_id": str(receipt.receipt_id),
                    "generation": int(manifest["generation"]) + 1,
                }
            )
            next_manifest["idempotency"][transaction.idempotency_key] = {
                "overlay_id": str(overlay.evaluation_id),
                "overlay_digest": overlay.fingerprint,
                "catalog_revision": str(catalog.revision),
                "receipt_id": str(receipt.receipt_id),
                "transaction_id": str(transaction.transaction_id),
            }
            required_paths = [
                str(self._overlay_path(catalog.mesh_id, catalog.mesh_revision, overlay.evaluation_id)),
                *(str(self._catalog_shard_path(catalog, item.kind)) for item in shards.shards),
                str(self._catalog_snapshot_path(catalog.mesh_id, catalog.mesh_revision, catalog.revision)),
                str(self._receipt_path("catalog-commits", receipt.receipt_id)),
            ]
            journal = {
                "artifact_schema": MESH_JOURNAL_SCHEMA,
                "mesh_schema_version": MESH_SCHEMA_VERSION,
                "operation": "catalog-commit",
                "status": "prepared",
                "transaction_id": str(transaction.transaction_id),
                "idempotency_key": transaction.idempotency_key,
                "mesh_id": str(transaction.mesh_id),
                "mesh_revision": str(transaction.mesh_revision),
                "expected_catalog_revision": str(transaction.expected_catalog_revision),
                "target_catalog_revision": str(catalog.revision),
                "target_receipt_id": str(receipt.receipt_id),
                "required_paths": required_paths,
                "catalog_manifest_path": str(
                    self._catalog_manifest_path(catalog.mesh_id, catalog.mesh_revision)
                ),
                "next_manifest": next_manifest,
                "prepared_at": committed_at,
            }
            journal_path = self._journal_path(transaction.transaction_id)
            self._write_immutable_json(journal_path, journal)
            self._fault("catalog_after_journal")
            self._write_immutable_json(
                self._overlay_path(catalog.mesh_id, catalog.mesh_revision, overlay.evaluation_id),
                overlay.to_dict(),
            )
            self._fault("catalog_after_overlay")
            for shard in shards.shards:
                self._write_immutable_json(
                    self._catalog_shard_path(catalog, shard.kind), shard.to_dict()
                )
            self._fault("catalog_after_shards")
            self._write_immutable_json(
                self._catalog_snapshot_path(catalog.mesh_id, catalog.mesh_revision, catalog.revision),
                catalog.to_dict(),
            )
            self._fault("catalog_after_snapshot")
            self._write_immutable_json(
                self._receipt_path("catalog-commits", receipt.receipt_id), receipt.to_dict()
            )
            self._fault("catalog_after_receipt")
            self._atomic_write_json(
                self._catalog_manifest_path(catalog.mesh_id, catalog.mesh_revision),
                next_manifest,
            )
            self._fault("catalog_after_manifest")
            self._terminalize_journal(journal_path, journal, "committed", receipt.receipt_id)
            self._fault("catalog_after_terminal_journal")
            return receipt

    def _abort_catalog_transaction(
        self, transaction: OverlayCatalogTransaction, reason: str
    ) -> MeshAbortReceipt:
        receipt = MeshAbortReceipt.create(
            transaction_id=transaction.transaction_id,
            mesh_id=transaction.mesh_id,
            actor=transaction.actor,
            reason=reason,
            staged_content_digest=(
                transaction.staged_overlay.fingerprint
                if transaction.staged_overlay is not None
                else None
            ),
        )
        with self._writer_lock(transaction.transaction_id):
            self._write_immutable_json(
                self._receipt_path("catalog-aborts", receipt.receipt_id), receipt.to_dict()
            )
        return receipt

    def repair_indexes(
        self,
        mesh_id: MeshId | str,
        revision: MeshRevision | str,
        *,
        actor: str,
    ) -> MeshIndexRepairReceipt:
        identity = MeshId.parse(mesh_id)
        requested = MeshRevision.parse(revision)
        entry = self._load_manifest()["meshes"].get(str(identity))
        if not entry or str(requested) not in tuple(entry.get("revisions") or ()):
            raise MeshRevisionNotFoundError(
                f"mesh revision {requested!r} is not manifest-authorized for repair"
            )
        snapshot = self._read_mesh_snapshot(identity, requested)
        definition = ModelMeshDefinition(
            mesh_id=snapshot.mesh_id,
            registry=snapshot.registry,
            memberships=snapshot.memberships,
            cross_model_edges=snapshot.cross_model_edges,
            invalidation_baseline=snapshot.invalidation_baseline,
            provenance=snapshot.provenance,
            metadata=snapshot.metadata,
        )
        model_snapshots = validate_definition_against_store(definition, self.model_store)
        rebuilt = compile_mesh_indexes(definition, model_snapshots=model_snapshots)
        expected = {
            item.kind: item.partitions[0].digest for item in snapshot.shard_sets
        }
        actual = {item.kind: item.digest for item in rebuilt.shards}
        if expected != actual:
            raise MeshStoreCorruptionError(
                "current-schema index repair cannot change snapshot-bound shard digests"
            )
        transaction_id = MeshTransactionId(f"mesh-repair-{uuid.uuid4().hex}")
        before = []
        with self._writer_lock(transaction_id):
            for shard in rebuilt.shards:
                path = self._mesh_shard_path(snapshot, shard.kind)
                if path.exists():
                    try:
                        before.append((shard.kind, MeshIndexShard.from_dict(self._read_json(path)).digest))
                    except Exception:
                        before.append((shard.kind, "corrupt"))
                else:
                    before.append((shard.kind, "missing"))
                self._atomic_write_json(path, shard.to_dict())
            receipt = MeshIndexRepairReceipt.create(
                mesh_id=snapshot.mesh_id,
                mesh_revision=snapshot.revision,
                before_shard_digests=tuple(before),
                after_shard_digests=tuple(actual.items()),
                actor=actor,
            )
            self._write_immutable_json(
                self._receipt_path("mesh-index-repairs", receipt.receipt_id),
                receipt.to_dict(),
            )
            self._read_mesh_indexes(snapshot)
            return receipt

    def recover(self) -> tuple[MeshRecoveryReceipt, ...]:
        stale_lock = self._prepare_explicit_recovery_lock()
        recovery_tx = MeshTransactionId(f"mesh-recovery-{uuid.uuid4().hex}")
        receipts: list[MeshRecoveryReceipt] = []
        with self._writer_lock(recovery_tx):
            if stale_lock is not None:
                receipt = MeshRecoveryReceipt.create(
                    action="remove_stale_lock",
                    mesh_id=stale_lock.get("mesh_id") or "mesh-recovery-scope",
                    transaction_id=stale_lock.get("transaction_id"),
                    revision=None,
                    reason="explicit recovery removed a non-live shared writer lock",
                )
                self._write_recovery_receipt(receipt)
                receipts.append(receipt)
            for journal_path, journal in self._prepared_journals():
                operation = journal.get("operation")
                required = tuple(Path(item) for item in journal.get("required_paths") or ())
                complete = bool(required) and all(path.exists() for path in required)
                action = "preserve_old_authority"
                reason = "prepared operation lacked a complete immutable artifact set"
                if complete and operation == "mesh-commit":
                    manifest = self._load_manifest()
                    mesh_id = MeshId.parse(journal["mesh_id"])
                    expected = journal.get("expected_revision")
                    actual = (manifest["meshes"].get(str(mesh_id)) or {}).get("head")
                    target = journal["target_revision"]
                    if actual in {expected, target}:
                        self._atomic_write_json(
                            self._manifest_path, journal["next_manifest"]
                        )
                        action = "complete_mesh_publication"
                        reason = "all immutable mesh and child catalog authority was complete"
                elif complete and operation == "catalog-commit":
                    manifest_path = Path(journal["catalog_manifest_path"])
                    current = self._read_json(manifest_path)
                    expected = journal.get("expected_catalog_revision")
                    target = journal.get("target_catalog_revision")
                    if current.get("head") in {expected, target}:
                        self._atomic_write_json(manifest_path, journal["next_manifest"])
                        action = "complete_catalog_publication"
                        reason = "all immutable overlay catalog authority was complete"
                if action == "preserve_old_authority":
                    removed = self._remove_unpublished_artifacts(required)
                    reason = (
                        "prepared operation lacked a complete immutable artifact set; "
                        f"explicit recovery removed {removed} unmanifested artifact(s)"
                    )
                mesh_revision = journal.get("target_revision") or journal.get("mesh_revision")
                receipt = MeshRecoveryReceipt.create(
                    action=action,
                    mesh_id=journal.get("mesh_id") or "mesh-recovery-scope",
                    transaction_id=journal.get("transaction_id"),
                    revision=mesh_revision,
                    reason=reason,
                )
                self._write_recovery_receipt(receipt)
                terminal = dict(journal)
                terminal.update(
                    {
                        "status": "recovered",
                        "terminal_at": utc_now(),
                        "terminal_receipt_id": str(receipt.receipt_id),
                    }
                )
                self._atomic_write_json(journal_path, terminal)
                receipts.append(receipt)
        return tuple(receipts)

    def _remove_unpublished_artifacts(self, paths: Iterable[Path]) -> int:
        """Remove only exact journal-declared files that never became authority."""

        removed = 0
        root = self.root.resolve()
        for path in paths:
            resolved = path.resolve()
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise MeshStoreCorruptionError(
                    f"recovery journal names a path outside the mesh store: {resolved}"
                ) from exc
            if resolved.exists() and resolved.is_file():
                resolved.unlink()
                self._fsync_directory(resolved.parent)
                removed += 1
        return removed

    def _resolve_mesh_idempotent_retry(
        self,
        previous: Mapping[str, Any],
        transaction: ModelMeshTransaction,
        snapshot: ModelMeshSnapshot,
    ) -> MeshCommitReceipt:
        if (
            previous.get("mesh_id") != str(transaction.mesh_id)
            or previous.get("content_digest") != snapshot.content_digest
            or previous.get("parent_revision")
            != (str(snapshot.parent_revision) if snapshot.parent_revision else None)
        ):
            receipt = MeshConflictReceipt.create(
                transaction_id=transaction.transaction_id,
                mesh_id=transaction.mesh_id,
                conflict_kind="mesh_idempotency",
                expected_revision=transaction.expected_revision,
                actual_revision=self.head(transaction.mesh_id),
                expected_catalog_revision=transaction.expected_overlay_catalog_revision,
                actual_catalog_revision=None,
                reason="idempotency key is already bound to different mesh content",
            )
            self._write_conflict(receipt)
            raise MeshIdempotencyConflictError(receipt=receipt)
        raw = self._read_json(
            self._receipt_path("mesh-commits", MeshReceiptId.parse(previous["receipt_id"]))
        )
        return MeshCommitReceipt.from_dict(raw)

    def _resolve_catalog_idempotent_retry(
        self,
        previous: Mapping[str, Any],
        transaction: OverlayCatalogTransaction,
        overlay: MeshEvaluationOverlay,
    ) -> OverlayCatalogCommitReceipt:
        if (
            previous.get("overlay_id") != str(overlay.evaluation_id)
            or previous.get("overlay_digest") != overlay.fingerprint
        ):
            receipt = MeshConflictReceipt.create(
                transaction_id=transaction.transaction_id,
                mesh_id=transaction.mesh_id,
                conflict_kind="catalog_idempotency",
                expected_revision=transaction.mesh_revision,
                actual_revision=transaction.mesh_revision,
                expected_catalog_revision=transaction.expected_catalog_revision,
                actual_catalog_revision=self.catalog_head(
                    transaction.mesh_id, transaction.mesh_revision
                ),
                reason="idempotency key is already bound to a different overlay",
            )
            self._write_conflict(receipt)
            raise MeshIdempotencyConflictError(receipt=receipt)
        raw = self._read_json(
            self._receipt_path("catalog-commits", MeshReceiptId.parse(previous["receipt_id"]))
        )
        return OverlayCatalogCommitReceipt.from_dict(raw)

    def _next_mesh_manifest(
        self,
        manifest: Mapping[str, Any],
        transaction: ModelMeshTransaction,
        snapshot: ModelMeshSnapshot,
        receipt: MeshCommitReceipt,
    ) -> dict[str, Any]:
        result = json.loads(canonical_json_bytes(manifest).decode("utf-8"))
        entry = dict(result["meshes"].get(str(snapshot.mesh_id)) or {})
        revisions = list(entry.get("revisions") or ())
        revisions.append(str(snapshot.revision))
        entry.update(
            {
                "head": str(snapshot.revision),
                "revisions": revisions,
                "head_receipt_id": str(receipt.receipt_id),
            }
        )
        result["meshes"][str(snapshot.mesh_id)] = entry
        result["idempotency"][transaction.idempotency_key] = {
            "mesh_id": str(snapshot.mesh_id),
            "revision": str(snapshot.revision),
            "parent_revision": (
                str(snapshot.parent_revision) if snapshot.parent_revision else None
            ),
            "content_digest": snapshot.content_digest,
            "receipt_id": str(receipt.receipt_id),
            "transaction_id": str(transaction.transaction_id),
        }
        result["generation"] = int(manifest["generation"]) + 1
        return result

    def _read_mesh_snapshot(
        self, mesh_id: MeshId, revision: MeshRevision
    ) -> ModelMeshSnapshot:
        path = self._mesh_snapshot_path(mesh_id, revision)
        try:
            snapshot = ModelMeshSnapshot.from_dict(self._read_json(path))
        except FileNotFoundError as exc:
            raise MeshStoreCorruptionError(
                f"manifest-authorized mesh snapshot is missing: {path}"
            ) from exc
        if snapshot.mesh_id != mesh_id or snapshot.revision != revision:
            raise MeshStoreCorruptionError(f"mesh snapshot identity mismatch: {path}")
        return snapshot

    def _read_mesh_indexes(self, snapshot: ModelMeshSnapshot) -> MeshIndexBundle:
        shards = []
        for shard_set in snapshot.shard_sets:
            if len(shard_set.partitions) != 1 or shard_set.partitions[0].partition != "all":
                raise MeshStoreCorruptionError("unsupported or incomplete mesh shard partition")
            path = self._mesh_shard_path(snapshot, shard_set.kind)
            try:
                shard = MeshIndexShard.from_dict(self._read_json(path))
            except FileNotFoundError as exc:
                raise MeshStoreCorruptionError(
                    f"manifest-authorized mesh shard is missing: {path}"
                ) from exc
            shards.append(shard)
        if not shards:
            raise MeshStoreCorruptionError("mesh snapshot binds no index authority")
        bundle = MeshIndexBundle(shards[0].content_basis_digest, tuple(shards))
        bundle.validate_snapshot_binding(snapshot)
        return bundle

    def _read_catalog_snapshot(
        self,
        mesh_id: MeshId,
        mesh_revision: MeshRevision,
        catalog_revision: OverlayCatalogRevision,
    ) -> OverlayCatalogSnapshot:
        path = self._catalog_snapshot_path(mesh_id, mesh_revision, catalog_revision)
        try:
            snapshot = OverlayCatalogSnapshot.from_dict(self._read_json(path))
        except FileNotFoundError as exc:
            raise MeshStoreCorruptionError(
                f"catalog-authorized snapshot is missing: {path}"
            ) from exc
        if (
            snapshot.mesh_id != mesh_id
            or snapshot.mesh_revision != mesh_revision
            or snapshot.revision != catalog_revision
        ):
            raise MeshStoreCorruptionError(f"catalog snapshot identity mismatch: {path}")
        return snapshot

    def _read_catalog_shards(
        self, snapshot: OverlayCatalogSnapshot
    ) -> OverlayDependencyShardBundle:
        shards = []
        for shard_set in snapshot.dependency_shard_sets:
            if len(shard_set.partitions) != 1 or shard_set.partitions[0].partition != "all":
                raise MeshStoreCorruptionError("unsupported catalog dependency partition")
            path = self._catalog_shard_path(snapshot, shard_set.kind)
            try:
                shard = OverlayDependencyShard.from_dict(self._read_json(path))
            except FileNotFoundError as exc:
                raise MeshStoreCorruptionError(
                    f"catalog-authorized dependency shard is missing: {path}"
                ) from exc
            if shard.digest != shard_set.partitions[0].digest:
                raise MeshStoreCorruptionError(f"catalog shard ref mismatch: {path}")
            shards.append(shard)
        if not shards:
            raise MeshStoreCorruptionError("catalog snapshot binds no dependency authority")
        return OverlayDependencyShardBundle(shards[0].content_basis_digest, tuple(shards))

    def _initial_manifest(self) -> dict[str, Any]:
        return {
            "artifact_schema": MESH_MANIFEST_SCHEMA,
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "generation": 0,
            "meshes": {},
            "idempotency": {},
        }

    def _initial_catalog_manifest(
        self,
        snapshot: OverlayCatalogSnapshot,
        *,
        idempotency: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "artifact_schema": MESH_OVERLAY_CATALOG_MANIFEST_SCHEMA,
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "mesh_id": str(snapshot.mesh_id),
            "mesh_revision": str(snapshot.mesh_revision),
            "generation": 0,
            "head": str(snapshot.revision),
            "revisions": [str(snapshot.revision)],
            "head_receipt_id": None,
            "idempotency": dict(idempotency),
        }

    def _load_manifest(self) -> dict[str, Any]:
        raw = self._read_json(self._manifest_path)
        self._require_schema(raw, "artifact_schema", MESH_MANIFEST_SCHEMA, self._manifest_path)
        self._require_schema(raw, "mesh_schema_version", MESH_SCHEMA_VERSION, self._manifest_path)
        for field in ("generation", "meshes", "idempotency"):
            if field not in raw:
                raise MeshStoreCorruptionError(
                    f"current mesh manifest is missing required field {field!r}: {self._manifest_path}"
                )
        if not isinstance(raw["meshes"], dict) or not isinstance(raw["idempotency"], dict):
            raise MeshStoreCorruptionError("mesh manifest authority maps must be objects")
        return raw

    def _load_catalog_manifest(
        self, mesh_id: MeshId, mesh_revision: MeshRevision
    ) -> dict[str, Any]:
        path = self._catalog_manifest_path(mesh_id, mesh_revision)
        try:
            raw = self._read_json(path)
        except FileNotFoundError as exc:
            raise MeshStoreCorruptionError(
                f"exact catalog manifest is missing for mesh revision: {path}"
            ) from exc
        self._require_schema(
            raw, "artifact_schema", MESH_OVERLAY_CATALOG_MANIFEST_SCHEMA, path
        )
        self._require_schema(raw, "mesh_schema_version", MESH_SCHEMA_VERSION, path)
        if raw.get("mesh_id") != str(mesh_id) or raw.get("mesh_revision") != str(
            mesh_revision
        ):
            raise MeshStoreCorruptionError(f"catalog manifest identity mismatch: {path}")
        for field in ("generation", "head", "revisions", "idempotency"):
            if field not in raw:
                raise MeshStoreCorruptionError(
                    f"catalog manifest is missing required field {field!r}: {path}"
                )
        return raw

    def _ensure_layout(self) -> None:
        for path in (
            self.root,
            self._meshes_dir,
            self._catalogs_dir,
            self._journals_dir,
            self._receipts_dir,
            self._locks_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _mesh_snapshot_path(self, mesh_id: MeshId, revision: MeshRevision) -> Path:
        return (
            self._meshes_dir
            / _storage_segment(mesh_id)
            / "v"
            / f"{_storage_segment(revision)}.json"
        )

    def _mesh_shard_path(self, snapshot: ModelMeshSnapshot, kind: str) -> Path:
        return (
            self._meshes_dir
            / _storage_segment(snapshot.mesh_id)
            / "s"
            / _storage_segment(snapshot.revision)
            / f"{_storage_segment(kind)}.json"
        )

    def _catalog_root(self, mesh_id: MeshId, mesh_revision: MeshRevision) -> Path:
        return (
            self._catalogs_dir
            / _storage_segment(mesh_id)
            / _storage_segment(mesh_revision)
        )

    def _catalog_manifest_path(self, mesh_id: MeshId, mesh_revision: MeshRevision) -> Path:
        return self._catalog_root(mesh_id, mesh_revision) / "manifest.json"

    def _catalog_snapshot_path(
        self,
        mesh_id: MeshId,
        mesh_revision: MeshRevision,
        catalog_revision: OverlayCatalogRevision,
    ) -> Path:
        return (
            self._catalog_root(mesh_id, mesh_revision)
            / "v"
            / f"{_storage_segment(catalog_revision)}.json"
        )

    def _catalog_shard_path(
        self, snapshot: OverlayCatalogSnapshot, kind: str
    ) -> Path:
        return (
            self._catalog_root(snapshot.mesh_id, snapshot.mesh_revision)
            / "d"
            / _storage_segment(snapshot.revision)
            / f"{_storage_segment(kind)}.json"
        )

    def _overlay_path(
        self,
        mesh_id: MeshId,
        mesh_revision: MeshRevision,
        overlay_id: MeshEvaluationId,
    ) -> Path:
        return (
            self._catalog_root(mesh_id, mesh_revision)
            / "o"
            / f"{_storage_segment(overlay_id)}.json"
        )

    def _journal_path(self, transaction_id: MeshTransactionId) -> Path:
        return self._journals_dir / f"{_storage_segment(transaction_id)}.json"

    def _receipt_path(self, category: str, receipt_id: MeshReceiptId) -> Path:
        return self._receipts_dir / category / f"{_storage_segment(receipt_id)}.json"

    def _write_conflict(self, receipt: MeshConflictReceipt) -> None:
        self._write_immutable_json(
            self._receipt_path("conflicts", receipt.receipt_id), receipt.to_dict()
        )

    def _write_recovery_receipt(self, receipt: MeshRecoveryReceipt) -> None:
        self._write_immutable_json(
            self._receipt_path("recovery", receipt.receipt_id), receipt.to_dict()
        )

    def _terminalize_journal(
        self,
        path: Path,
        journal: Mapping[str, Any],
        status: str,
        receipt_id: MeshReceiptId,
    ) -> None:
        terminal = dict(journal)
        terminal.update(
            {
                "status": status,
                "terminal_at": utc_now(),
                "terminal_receipt_id": str(receipt_id),
            }
        )
        self._atomic_write_json(path, terminal)

    def _prepared_journals(self) -> tuple[tuple[Path, dict[str, Any]], ...]:
        result = []
        for path in sorted(self._journals_dir.glob("*.json")):
            raw = self._read_json(path)
            self._require_schema(raw, "artifact_schema", MESH_JOURNAL_SCHEMA, path)
            self._require_schema(raw, "mesh_schema_version", MESH_SCHEMA_VERSION, path)
            if raw.get("status") == "prepared":
                result.append((path, raw))
        return tuple(result)

    def _raise_if_prepared_journal(self) -> None:
        prepared = self._prepared_journals()
        if prepared:
            raise MeshRecoveryRequiredError(
                f"prepared mesh/catalog journal requires explicit recover(): {prepared[0][0]}"
            )

    def _fault(self, point: str) -> None:
        if self._test_fault_hook is not None:
            self._test_fault_hook(point)

    @contextmanager
    def _writer_lock(self, transaction_id: MeshTransactionId) -> Iterator[None]:
        metadata = {
            "artifact_schema": MESH_JOURNAL_SCHEMA,
            "mesh_schema_version": MESH_SCHEMA_VERSION,
            "lock_type": "mesh-catalog-shared-writer",
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "transaction_id": str(transaction_id),
            "created_at": utc_now(),
        }
        try:
            self._write_exclusive_json(self._writer_lock_path, metadata)
        except FileExistsError:
            try:
                owner = self._read_lock_owner()
            except MeshStoreCorruptionError as exc:
                raise MeshWriterLockHeldError(
                    f"shared writer lock exists but metadata is not yet readable: {self._writer_lock_path}"
                ) from exc
            if self._lock_owner_is_live(owner):
                raise MeshWriterLockHeldError(
                    f"live shared writer lock pid={owner.get('pid')} host={owner.get('host')} "
                    f"transaction={owner.get('transaction_id')}"
                )
            raise MeshRecoveryRequiredError(
                f"stale or unverifiable shared writer lock at {self._writer_lock_path}; run recover()"
            )
        try:
            yield
        finally:
            try:
                current = self._read_lock_owner()
            except (FileNotFoundError, MeshStoreCorruptionError):
                current = {}
            if current.get("transaction_id") == str(transaction_id):
                self._writer_lock_path.unlink(missing_ok=True)
                self._fsync_directory(self._locks_dir)

    def _prepare_explicit_recovery_lock(self) -> dict[str, Any] | None:
        if not self._writer_lock_path.exists():
            return None
        owner = self._read_lock_owner()
        if self._lock_owner_is_live(owner):
            raise MeshWriterLockHeldError(
                f"explicit recovery refused live shared writer lock pid={owner.get('pid')}"
            )
        self._writer_lock_path.unlink()
        self._fsync_directory(self._locks_dir)
        return dict(owner)

    def _read_lock_owner(self) -> dict[str, Any]:
        try:
            return self._read_json(self._writer_lock_path)
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise MeshStoreCorruptionError(
                f"shared writer lock is unreadable: {self._writer_lock_path}"
            ) from exc

    @staticmethod
    def _lock_owner_is_live(owner: Mapping[str, Any]) -> bool:
        if owner.get("host") != socket.gethostname():
            return True
        try:
            pid = int(owner.get("pid"))
        except (TypeError, ValueError):
            return False
        if pid <= 0:
            return False
        if pid == os.getpid():
            return True
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    @staticmethod
    def _require_schema(
        raw: Mapping[str, Any], key: str, expected: str, path: Path
    ) -> None:
        found = raw.get(key)
        if found != expected:
            raise MeshStoreSchemaError(
                f"artifact {path} declares {key}={found!r}; expected {expected!r}; "
                "normal runtime has no compatibility reader or fallback"
            )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise MeshStoreCorruptionError(f"cannot read JSON artifact {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise MeshStoreCorruptionError(f"JSON artifact must contain an object: {path}")
        return raw

    def _write_immutable_json(self, path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = self._read_json(path)
            if canonical_json_bytes(existing) != canonical_json_bytes(value):
                raise MeshStoreCorruptionError(
                    f"immutable artifact already exists with different content: {path}"
                )
            return
        try:
            self._write_exclusive_json(path, value)
        except FileExistsError:
            existing = self._read_json(path)
            if canonical_json_bytes(existing) != canonical_json_bytes(value):
                raise MeshStoreCorruptionError(
                    f"immutable artifact raced with different content: {path}"
                )

    def _write_exclusive_json(self, path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = canonical_json_bytes(value) + b"\n"
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        self._fsync_directory(path.parent)

    def _atomic_write_json(self, path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
        payload = canonical_json_bytes(value) + b"\n"
        try:
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            self._fsync_directory(path.parent)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        try:
            descriptor = os.open(path, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        except OSError:
            pass
        finally:
            os.close(descriptor)


__all__ = [
    "FileModelMeshStore",
    "MESH_STORE_TOOL_FINGERPRINT",
    "MeshIdempotencyConflictError",
    "MeshRecoveryRequiredError",
    "MeshRevisionView",
    "MeshStoreCorruptionError",
    "MeshStoreError",
    "MeshStoreSchemaError",
    "MeshTransactionConflictError",
    "MeshWriterLockHeldError",
    "ModelMeshStore",
    "OverlayCatalogConflictError",
    "TestInjectedMeshStoreFault",
]
