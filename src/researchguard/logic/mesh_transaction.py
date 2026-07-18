"""Explicit compare-and-swap transaction state for product-runtime ModelMesh."""

from __future__ import annotations

import uuid
from typing import Protocol

from .identity import (
    MeshId,
    MeshRevision,
    MeshTransactionId,
    OverlayCatalogRevision,
)
from .mesh_receipts import MeshAbortReceipt, MeshCommitReceipt
from .model_mesh import ModelMeshDefinition, validate_definition_against_store


class MeshTransactionStateError(RuntimeError):
    """A mesh transaction was used outside its legal state."""


class _MeshTransactionBackend(Protocol):
    @property
    def model_store(self): ...

    def _commit_mesh_transaction(
        self, transaction: "ModelMeshTransaction", definition: ModelMeshDefinition
    ) -> MeshCommitReceipt: ...

    def _abort_mesh_transaction(
        self, transaction: "ModelMeshTransaction", reason: str
    ) -> MeshAbortReceipt: ...


class ModelMeshTransaction:
    """One explicit mesh authoring-to-publication attempt.

    Both the mesh head and the parent overlay-catalog head are captured at
    construction.  Neither value is silently refreshed during commit.
    """

    def __init__(
        self,
        *,
        store: _MeshTransactionBackend,
        mesh_id: MeshId | str,
        expected_revision: MeshRevision | str | None,
        idempotency_key: str,
        actor: str,
        expected_overlay_catalog_revision: OverlayCatalogRevision | str | None,
        transaction_id: MeshTransactionId | str | None = None,
    ) -> None:
        self._store = store
        self.mesh_id = MeshId.parse(mesh_id)
        self.expected_revision = (
            MeshRevision.parse(expected_revision) if expected_revision is not None else None
        )
        self.expected_overlay_catalog_revision = (
            OverlayCatalogRevision.parse(expected_overlay_catalog_revision)
            if expected_overlay_catalog_revision is not None
            else None
        )
        if self.expected_revision is None and self.expected_overlay_catalog_revision is not None:
            raise ValueError("first mesh commit cannot name a parent catalog revision")
        if self.expected_revision is not None and self.expected_overlay_catalog_revision is None:
            raise ValueError("mesh update requires expected_overlay_catalog_revision")
        MeshTransactionId(str(idempotency_key))
        self.idempotency_key = str(idempotency_key)
        self.actor = str(actor).strip()
        if not self.actor:
            raise ValueError("mesh transaction actor must not be empty")
        self.transaction_id = MeshTransactionId.parse(
            transaction_id or f"mesh-tx-{uuid.uuid4().hex}"
        )
        self._definition: ModelMeshDefinition | None = None
        self._terminal_receipt: MeshCommitReceipt | MeshAbortReceipt | None = None
        self._state = "open"

    @property
    def state(self) -> str:
        return self._state

    @property
    def staged_definition(self) -> ModelMeshDefinition | None:
        return self._definition

    @property
    def terminal_receipt(self) -> MeshCommitReceipt | MeshAbortReceipt | None:
        return self._terminal_receipt

    def stage(self, definition: ModelMeshDefinition) -> str:
        if self._state not in {"open", "staged"}:
            raise MeshTransactionStateError(
                f"cannot stage mesh transaction {self.transaction_id} in state {self._state}"
            )
        if definition.mesh_id != self.mesh_id:
            raise ValueError(
                f"transaction mesh {self.mesh_id} does not match staged mesh {definition.mesh_id}"
            )
        baseline = definition.invalidation_baseline
        if self.expected_revision is None:
            if baseline is not None:
                raise ValueError("first mesh definition cannot name invalidation baseline")
        else:
            if baseline is None:
                raise ValueError("mesh update requires exact invalidation baseline catalog pin")
            if (
                baseline.mesh_id != self.mesh_id
                or baseline.mesh_revision != self.expected_revision
                or baseline.catalog_revision != self.expected_overlay_catalog_revision
            ):
                raise ValueError("staged invalidation baseline differs from declared CAS authority")
        validate_definition_against_store(definition, self._store.model_store)
        self._definition = definition
        self._state = "staged"
        from .model_store import canonical_digest

        return canonical_digest(definition.canonical_dict())

    def commit(self) -> MeshCommitReceipt:
        if self._state == "committed" and isinstance(
            self._terminal_receipt, MeshCommitReceipt
        ):
            return self._terminal_receipt
        if self._state != "staged" or self._definition is None:
            raise MeshTransactionStateError(
                f"cannot commit mesh transaction {self.transaction_id} in state {self._state}; "
                "stage a valid definition first"
            )
        receipt = self._store._commit_mesh_transaction(self, self._definition)
        self._terminal_receipt = receipt
        self._state = "committed"
        return receipt

    def abort(self, reason: str) -> MeshAbortReceipt:
        if self._state == "aborted" and isinstance(self._terminal_receipt, MeshAbortReceipt):
            return self._terminal_receipt
        if self._state == "committed":
            raise MeshTransactionStateError("cannot abort committed mesh transaction")
        if not str(reason).strip():
            raise ValueError("mesh abort requires a reason")
        receipt = self._store._abort_mesh_transaction(self, str(reason).strip())
        self._terminal_receipt = receipt
        self._state = "aborted"
        return receipt

    def __enter__(self) -> "ModelMeshTransaction":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if exc is not None and self._state not in {"committed", "aborted"}:
            self.abort(f"context exited with {exc_type.__name__}: {exc}")
        return False


__all__ = ["MeshTransactionStateError", "ModelMeshTransaction"]
