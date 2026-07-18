"""Local transactional implementation of the LogicGuard ModelStore protocol."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from .identity import (
    EvaluationId,
    ModelId,
    ModelRevision,
    ReceiptId,
    TransactionId,
)
from .model_store import (
    EvaluationNotFoundError,
    IdempotencyConflictError,
    ModelNotFoundError,
    ModelSnapshot,
    RecoveryRequiredError,
    RevisionNotFoundError,
    StoreCorruptionError,
    StoreSchemaError,
    TombstonedModelError,
    TransactionConflictError,
    WriterLockHeldError,
    canonical_json_bytes,
)
from .receipts import (
    AbortReceipt,
    CommitReceipt,
    ConflictReceipt,
    LifecycleReceipt,
    RecoveryReceipt,
    receipt_from_dict,
    utc_now,
)
from .schema import (
    EVALUATION_OVERLAY_SCHEMA,
    JOURNAL_SCHEMA,
    MANIFEST_SCHEMA,
    RECEIPT_SCHEMA,
    SCHEMA_VERSION,
)
from .store_transaction import ModelTransaction
from .store_validation import validate_snapshot


FaultHook = Callable[[str], None]


def _storage_segment(identity: Any) -> str:
    """Return a short fixed-width, content-addressed path projection.

    The authoritative identity remains in the manifest/artifact and is checked
    on read.  Fixed-width projection keeps deeply nested Windows temp/store
    roots below legacy MAX_PATH without weakening identity validation.
    """

    digest = hashlib.sha256(str(identity).encode("utf-8")).digest()
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"h-{encoded}"


class TestInjectedStoreFault(RuntimeError):
    """Exception intended only for deterministic crash-boundary tests."""

    __test__ = False


class FileModelStore:
    """One-writer, immutable-revision local filesystem store.

    The only supported layout is rooted at ``manifest.json``.  The constructor
    never searches parent directories or alternate legacy layouts.
    """

    _COMMIT_FAULT_POINTS = (
        "after_lock",
        "after_journal",
        "after_revision",
        "after_receipt",
        "after_manifest",
        "after_terminal_journal",
    )

    def __init__(
        self,
        root: str | Path,
        *,
        _test_fault_hook: FaultHook | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self._test_fault_hook = _test_fault_hook
        self._manifest_path = self.root / "manifest.json"
        self._models_dir = self.root / "models"
        self._evaluations_dir = self.root / "evaluations"
        self._journals_dir = self.root / "journals"
        self._receipts_dir = self.root / "receipts"
        self._locks_dir = self.root / "locks"
        self._writer_lock_path = self._locks_dir / "writer.lock"
        self._ensure_layout()
        # Opening a store is a schema check, never a compatibility scan.
        self._load_manifest()

    @property
    def commit_fault_points(self) -> tuple[str, ...]:
        return self._COMMIT_FAULT_POINTS

    def head(self, model_id: ModelId | str) -> ModelRevision | None:
        identity = ModelId.parse(model_id)
        manifest = self._load_manifest()
        self._raise_if_tombstoned(manifest, identity)
        entry = manifest["models"].get(str(identity))
        if not entry:
            return None
        head = entry.get("head")
        return ModelRevision.parse(head) if head else None

    def get(
        self,
        model_id: ModelId | str,
        revision: ModelRevision | str | None = None,
    ) -> ModelSnapshot:
        identity = ModelId.parse(model_id)
        manifest = self._load_manifest()
        entry = manifest["models"].get(str(identity))
        if not entry:
            raise ModelNotFoundError(f"model not found: {identity}")
        if revision is None:
            self._raise_if_tombstoned(manifest, identity)
            requested = entry.get("head")
            if not requested:
                raise ModelNotFoundError(f"model {identity} has no current head")
        else:
            requested = str(ModelRevision.parse(revision))
        authorized = tuple(entry.get("revisions") or ())
        if requested not in authorized:
            raise RevisionNotFoundError(
                f"revision {requested!r} is not manifest-authorized for model {identity}"
            )
        snapshot = self._read_snapshot(identity, ModelRevision.parse(requested))
        if revision is None:
            self._verify_head_binding(manifest, identity, snapshot)
        return snapshot

    def list_models(self) -> tuple[ModelId, ...]:
        manifest = self._load_manifest()
        tombstones = manifest["tombstones"]
        return tuple(
            ModelId(model_id)
            for model_id in sorted(manifest["models"])
            if model_id not in tombstones
        )

    def list_revisions(self, model_id: ModelId | str) -> tuple[ModelRevision, ...]:
        identity = ModelId.parse(model_id)
        manifest = self._load_manifest()
        entry = manifest["models"].get(str(identity))
        if not entry:
            raise ModelNotFoundError(f"model not found: {identity}")
        return tuple(ModelRevision.parse(item) for item in entry.get("revisions") or ())

    def begin(
        self,
        model_id: ModelId | str,
        expected_revision: ModelRevision | str | None,
        idempotency_key: str,
        actor: str,
    ) -> ModelTransaction:
        return ModelTransaction(
            store=self,
            model_id=model_id,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            actor=actor,
        )

    def _commit_transaction(
        self, transaction: ModelTransaction, snapshot: ModelSnapshot
    ) -> CommitReceipt:
        validate_snapshot(snapshot)
        with self._writer_lock(transaction.transaction_id):
            self._fault("after_lock")
            manifest = self._load_manifest()

            # Idempotency is checked before CAS.  A successful retry therefore
            # remains stable even though its original commit advanced the head.
            previous = manifest["idempotency"].get(transaction.idempotency_key)
            if previous:
                return self._resolve_idempotent_retry(
                    previous=previous,
                    transaction=transaction,
                    snapshot=snapshot,
                )

            prepared = self._find_prepared_idempotency(transaction.idempotency_key)
            if prepared is not None:
                raise RecoveryRequiredError(
                    f"idempotency key {transaction.idempotency_key!r} has incomplete journal "
                    f"{prepared}; run recover() before retrying"
                )

            self._raise_if_tombstoned(manifest, transaction.model_id)
            model_entry = manifest["models"].get(str(transaction.model_id)) or {}
            actual_head = (
                ModelRevision.parse(model_entry["head"])
                if model_entry.get("head")
                else None
            )
            if transaction.expected_revision != actual_head:
                conflict_receipt = ConflictReceipt.create(
                    transaction_id=transaction.transaction_id,
                    model_id=transaction.model_id,
                    conflict_kind="compare_and_swap",
                    expected_revision=transaction.expected_revision,
                    actual_revision=actual_head,
                    reason="declared expected head differs from manifest-authorized head",
                )
                self._write_immutable_json(
                    self._receipt_path("conflicts", conflict_receipt.receipt_id),
                    conflict_receipt.to_dict(),
                )
                raise TransactionConflictError(
                    model_id=transaction.model_id,
                    expected=transaction.expected_revision,
                    actual=actual_head,
                    receipt=conflict_receipt,
                )

            receipt = CommitReceipt.create(
                transaction_id=transaction.transaction_id,
                model_id=transaction.model_id,
                revision=snapshot.revision,
                parent_revision=snapshot.parent_revision,
                content_digest=snapshot.content_digest,
                idempotency_key=transaction.idempotency_key,
                actor=transaction.actor,
            )
            journal = self._prepared_journal(transaction, snapshot, receipt)
            journal_path = self._journal_path(transaction.transaction_id)
            self._write_immutable_json(journal_path, journal)
            self._fault("after_journal")

            revision_path = self._revision_path(snapshot.model_id, snapshot.revision)
            self._write_immutable_json(revision_path, snapshot.to_dict())
            self._fault("after_revision")

            receipt_path = self._receipt_path("commits", receipt.receipt_id)
            self._write_immutable_json(receipt_path, receipt.to_dict())
            self._fault("after_receipt")

            next_manifest = json.loads(canonical_json_bytes(manifest).decode("utf-8"))
            next_entry = dict(next_manifest["models"].get(str(snapshot.model_id)) or {})
            revisions = list(next_entry.get("revisions") or [])
            if str(snapshot.revision) not in revisions:
                revisions.append(str(snapshot.revision))
            next_entry.update(
                {
                    "head": str(snapshot.revision),
                    "revisions": revisions,
                    "head_receipt_id": str(receipt.receipt_id),
                }
            )
            next_manifest["models"][str(snapshot.model_id)] = next_entry
            next_manifest["idempotency"][transaction.idempotency_key] = {
                "model_id": str(snapshot.model_id),
                "revision": str(snapshot.revision),
                "parent_revision": (
                    str(snapshot.parent_revision) if snapshot.parent_revision else None
                ),
                "content_digest": snapshot.content_digest,
                "receipt_id": str(receipt.receipt_id),
                "transaction_id": str(transaction.transaction_id),
            }
            next_manifest["generation"] = int(manifest["generation"]) + 1
            self._atomic_write_json(self._manifest_path, next_manifest)
            self._fault("after_manifest")

            terminal_journal = dict(journal)
            terminal_journal.update(
                {
                    "status": "committed",
                    "terminal_at": utc_now(),
                    "terminal_receipt_id": str(receipt.receipt_id),
                }
            )
            self._atomic_write_json(journal_path, terminal_journal)
            self._fault("after_terminal_journal")
            return receipt

    def _abort_transaction(
        self, transaction: ModelTransaction, reason: str
    ) -> AbortReceipt:
        receipt = AbortReceipt.create(
            transaction_id=transaction.transaction_id,
            model_id=transaction.model_id,
            actor=transaction.actor,
            reason=reason,
            staged_content_digest=(
                transaction.staged_snapshot.content_digest
                if transaction.staged_snapshot is not None
                else None
            ),
        )
        with self._writer_lock(transaction.transaction_id):
            self._write_immutable_json(
                self._receipt_path("aborts", receipt.receipt_id), receipt.to_dict()
            )
        return receipt

    def put_evaluation(self, overlay: Any, expected_model_digest: str) -> Any:
        if not hasattr(overlay, "to_dict"):
            raise TypeError("evaluation overlay must provide to_dict()")
        raw = overlay.to_dict()
        self._require_schema(
            raw,
            key="artifact_schema",
            expected=EVALUATION_OVERLAY_SCHEMA,
            path=Path("<evaluation-overlay>"),
        )
        self._require_schema(
            raw,
            key="store_schema_version",
            expected=SCHEMA_VERSION,
            path=Path("<evaluation-overlay>"),
        )
        model_id = ModelId.parse(raw.get("model_id", ""))
        revision = ModelRevision.parse(raw.get("revision", ""))
        evaluation_id = EvaluationId.parse(raw.get("evaluation_id", ""))
        snapshot = self.get(model_id, revision)
        if snapshot.content_digest != expected_model_digest:
            raise TransactionConflictError(
                model_id=model_id,
                expected=revision,
                actual=revision,
                message=(
                    f"evaluation expected digest {expected_model_digest}, "
                    f"but revision {revision} has {snapshot.content_digest}"
                ),
            )
        if raw.get("content_digest") != snapshot.content_digest:
            raise StoreCorruptionError("evaluation overlay content_digest does not match snapshot")
        path = self._evaluation_path(model_id, revision, evaluation_id)
        lock_id = TransactionId(f"txn-eval-{uuid.uuid4().hex}")
        with self._writer_lock(lock_id):
            self._write_immutable_json(path, raw)
        return overlay

    def get_evaluation(
        self,
        model_id: ModelId | str,
        revision: ModelRevision | str,
        evaluation_id: EvaluationId | str,
    ) -> Any:
        identity = ModelId.parse(model_id)
        revision_id = ModelRevision.parse(revision)
        evaluation_identity = EvaluationId.parse(evaluation_id)
        # Exact historical revision must still be manifest-authorized.
        self.get(identity, revision_id)
        path = self._evaluation_path(identity, revision_id, evaluation_identity)
        if not path.exists():
            raise EvaluationNotFoundError(
                f"evaluation {evaluation_identity} not found for {identity}@{revision_id}"
            )
        raw = self._read_json(path)
        self._require_schema(
            raw,
            key="artifact_schema",
            expected=EVALUATION_OVERLAY_SCHEMA,
            path=path,
        )
        self._require_schema(
            raw,
            key="store_schema_version",
            expected=SCHEMA_VERSION,
            path=path,
        )
        try:
            from .evaluation_overlay import EvaluationOverlay

            return EvaluationOverlay.from_dict(raw)
        except (ImportError, AttributeError):
            # The protocol remains usable during isolated P0 integration.  The
            # package-level overlay owner supplies the typed decoder.
            return raw

    def tombstone(
        self,
        model_id: ModelId | str,
        *,
        actor: str,
        reason: str,
    ) -> LifecycleReceipt:
        identity = ModelId.parse(model_id)
        if not reason.strip():
            raise ValueError("tombstone requires a reason")
        transaction_id = TransactionId(f"txn-tombstone-{uuid.uuid4().hex}")
        with self._writer_lock(transaction_id):
            manifest = self._load_manifest()
            if str(identity) not in manifest["models"]:
                raise ModelNotFoundError(f"model not found: {identity}")
            if str(identity) in manifest["tombstones"]:
                entry = manifest["tombstones"][str(identity)]
                raise TombstonedModelError(
                    identity,
                    reason=str(entry.get("reason", "")),
                    receipt_id=ReceiptId.parse(entry.get("receipt_id", "")),
                )
            receipt = LifecycleReceipt.create(
                transaction_id=transaction_id,
                action="tombstone",
                subject_model_id=identity,
                actor=actor,
                reason=reason,
            )
            self._write_immutable_json(
                self._receipt_path("lifecycle", receipt.receipt_id), receipt.to_dict()
            )
            next_manifest = json.loads(canonical_json_bytes(manifest).decode("utf-8"))
            next_manifest["tombstones"][str(identity)] = {
                "reason": reason,
                "actor": actor,
                "receipt_id": str(receipt.receipt_id),
                "recorded_at": receipt.recorded_at,
            }
            next_manifest["generation"] = int(manifest["generation"]) + 1
            self._atomic_write_json(self._manifest_path, next_manifest)
            return receipt

    def recover(self) -> tuple[RecoveryReceipt, ...]:
        recovery_transaction = TransactionId(f"txn-recovery-{uuid.uuid4().hex}")
        stale_evidence = self._prepare_explicit_recovery_lock()
        receipts: list[RecoveryReceipt] = []
        with self._writer_lock(recovery_transaction):
            if stale_evidence is not None:
                stale_receipt = RecoveryReceipt.create(
                    transaction_id=recovery_transaction,
                    action="remove_stale_lock",
                    reason="explicit recovery removed a non-live writer lock",
                    evidence=stale_evidence,
                )
                self._write_recovery_receipt(stale_receipt)
                receipts.append(stale_receipt)

            manifest = self._load_manifest()
            for journal_path in sorted(self._journals_dir.glob("*.json")):
                journal = self._read_json(journal_path)
                self._require_schema(
                    journal,
                    key="artifact_schema",
                    expected=JOURNAL_SCHEMA,
                    path=journal_path,
                )
                self._require_schema(
                    journal,
                    key="store_schema_version",
                    expected=SCHEMA_VERSION,
                    path=journal_path,
                )
                if journal.get("status") != "prepared":
                    continue
                receipt = self._recover_prepared_journal(manifest, journal_path, journal)
                receipts.append(receipt)
                # A finalized manifest is unchanged; an aborted orphan also does
                # not modify it.  Re-read to guard against accidental divergence.
                manifest = self._load_manifest()
        return tuple(receipts)

    def _recover_prepared_journal(
        self,
        manifest: Mapping[str, Any],
        journal_path: Path,
        journal: Mapping[str, Any],
    ) -> RecoveryReceipt:
        transaction_id = TransactionId.parse(journal.get("transaction_id", ""))
        model_id = ModelId.parse(journal.get("model_id", ""))
        revision = ModelRevision.parse(journal.get("revision", ""))
        receipt_id = ReceiptId.parse(journal.get("commit_receipt_id", ""))
        idempotency_key = str(journal.get("idempotency_key", ""))
        model_entry = manifest["models"].get(str(model_id)) or {}
        binding = manifest["idempotency"].get(idempotency_key)
        manifest_names_revision = model_entry.get("head") == str(revision)
        binding_matches = bool(
            binding
            and binding.get("model_id") == str(model_id)
            and binding.get("revision") == str(revision)
            and binding.get("receipt_id") == str(receipt_id)
            and binding.get("content_digest") == journal.get("content_digest")
        )
        if manifest_names_revision or binding:
            if not (manifest_names_revision and binding_matches):
                raise StoreCorruptionError(
                    f"prepared journal {journal_path} conflicts with manifest authority"
                )
            snapshot = self._read_snapshot(model_id, revision)
            commit_receipt = self._read_commit_receipt(receipt_id)
            self._verify_commit_binding(snapshot, commit_receipt, binding)
            recovery = RecoveryReceipt.create(
                transaction_id=transaction_id,
                action="finalize_committed_journal",
                reason="manifest, immutable revision, idempotency binding, and commit receipt agree",
                model_id=model_id,
                revision=revision,
                journal_status_before="prepared",
                journal_status_after="committed",
                evidence={"commit_receipt_id": str(receipt_id)},
            )
            terminal_status = "committed"
        else:
            # Revision and/or receipt files may exist, but without manifest
            # publication they are retained non-authoritative orphan evidence.
            recovery = RecoveryReceipt.create(
                transaction_id=transaction_id,
                action="abort_orphan",
                reason="manifest never authorized the prepared revision",
                model_id=model_id,
                revision=revision,
                journal_status_before="prepared",
                journal_status_after="aborted",
                evidence={
                    "revision_exists": self._revision_path(model_id, revision).exists(),
                    "commit_receipt_exists": self._receipt_path("commits", receipt_id).exists(),
                },
            )
            terminal_status = "aborted"
        self._write_recovery_receipt(recovery)
        terminal = dict(journal)
        terminal.update(
            {
                "status": terminal_status,
                "terminal_at": recovery.recovered_at,
                "recovery_receipt_id": str(recovery.receipt_id),
            }
        )
        self._atomic_write_json(journal_path, terminal)
        return recovery

    def _resolve_idempotent_retry(
        self,
        *,
        previous: Mapping[str, Any],
        transaction: ModelTransaction,
        snapshot: ModelSnapshot,
    ) -> CommitReceipt:
        expected_binding = {
            "model_id": str(snapshot.model_id),
            "revision": str(snapshot.revision),
            "parent_revision": (
                str(snapshot.parent_revision) if snapshot.parent_revision else None
            ),
            "content_digest": snapshot.content_digest,
        }
        mismatches = {
            key: (previous.get(key), value)
            for key, value in expected_binding.items()
            if previous.get(key) != value
        }
        if mismatches:
            conflict_receipt = ConflictReceipt.create(
                transaction_id=transaction.transaction_id,
                model_id=transaction.model_id,
                conflict_kind="idempotency",
                expected_revision=transaction.expected_revision,
                actual_revision=(
                    ModelRevision.parse(previous["revision"])
                    if previous.get("revision")
                    else None
                ),
                reason="idempotency key is already bound to different canonical content",
                details={
                    key: {"existing": existing, "attempted": attempted}
                    for key, (existing, attempted) in mismatches.items()
                },
            )
            self._write_immutable_json(
                self._receipt_path("conflicts", conflict_receipt.receipt_id),
                conflict_receipt.to_dict(),
            )
            raise IdempotencyConflictError(
                f"idempotency key {transaction.idempotency_key!r} is already bound to "
                f"different model content: {mismatches}",
                receipt=conflict_receipt,
            )
        receipt = self._read_commit_receipt(ReceiptId.parse(previous.get("receipt_id", "")))
        if receipt.idempotency_key != transaction.idempotency_key:
            raise StoreCorruptionError("idempotency manifest binding disagrees with receipt")
        return receipt

    def _verify_head_binding(
        self,
        manifest: Mapping[str, Any],
        model_id: ModelId,
        snapshot: ModelSnapshot,
    ) -> None:
        entry = manifest["models"].get(str(model_id)) or {}
        receipt_id = ReceiptId.parse(entry.get("head_receipt_id", ""))
        receipt = self._read_commit_receipt(receipt_id)
        binding = manifest["idempotency"].get(receipt.idempotency_key)
        if not binding:
            raise StoreCorruptionError(f"head receipt {receipt_id} has no idempotency binding")
        self._verify_commit_binding(snapshot, receipt, binding)

    @staticmethod
    def _verify_commit_binding(
        snapshot: ModelSnapshot,
        receipt: CommitReceipt,
        binding: Mapping[str, Any],
    ) -> None:
        expected = {
            "model_id": str(snapshot.model_id),
            "revision": str(snapshot.revision),
            "parent_revision": (
                str(snapshot.parent_revision) if snapshot.parent_revision else None
            ),
            "content_digest": snapshot.content_digest,
            "receipt_id": str(receipt.receipt_id),
        }
        if any(binding.get(key) != value for key, value in expected.items()):
            raise StoreCorruptionError("manifest idempotency binding disagrees with snapshot/receipt")
        if (
            receipt.model_id != snapshot.model_id
            or receipt.revision != snapshot.revision
            or receipt.parent_revision != snapshot.parent_revision
            or receipt.content_digest != snapshot.content_digest
        ):
            raise StoreCorruptionError("commit receipt disagrees with immutable snapshot")

    def _prepared_journal(
        self,
        transaction: ModelTransaction,
        snapshot: ModelSnapshot,
        receipt: CommitReceipt,
    ) -> dict[str, Any]:
        return {
            "artifact_schema": JOURNAL_SCHEMA,
            "store_schema_version": SCHEMA_VERSION,
            "status": "prepared",
            "transaction_id": str(transaction.transaction_id),
            "model_id": str(snapshot.model_id),
            "expected_revision": (
                str(transaction.expected_revision) if transaction.expected_revision else None
            ),
            "revision": str(snapshot.revision),
            "content_digest": snapshot.content_digest,
            "idempotency_key": transaction.idempotency_key,
            "actor": transaction.actor,
            "prepared_at": utc_now(),
            "revision_path": str(
                self._revision_path(snapshot.model_id, snapshot.revision).relative_to(self.root)
            ).replace("\\", "/"),
            "commit_receipt_id": str(receipt.receipt_id),
        }

    def _ensure_layout(self) -> None:
        root_was_nonempty = self.root.exists() and any(self.root.iterdir())
        if not self._manifest_path.exists() and root_was_nonempty:
            raise StoreCorruptionError(
                f"current manifest authority is missing from non-empty store root: "
                f"{self._manifest_path}; refusing to create replacement authority"
            )
        for path in (
            self.root,
            self._models_dir,
            self._evaluations_dir,
            self._journals_dir,
            self._receipts_dir / "commits",
            self._receipts_dir / "aborts",
            self._receipts_dir / "conflicts",
            self._receipts_dir / "recovery",
            self._receipts_dir / "lifecycle",
            self._locks_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        empty_manifest = {
            "artifact_schema": MANIFEST_SCHEMA,
            "store_schema_version": SCHEMA_VERSION,
            "generation": 0,
            "models": {},
            "tombstones": {},
            "idempotency": {},
        }
        if not self._manifest_path.exists():
            self._write_immutable_json(self._manifest_path, empty_manifest)

    def _load_manifest(self) -> dict[str, Any]:
        try:
            manifest = self._read_json(self._manifest_path)
        except FileNotFoundError as exc:
            raise StoreCorruptionError(
                f"current manifest authority is missing: {self._manifest_path}"
            ) from exc
        self._require_schema(
            manifest,
            key="artifact_schema",
            expected=MANIFEST_SCHEMA,
            path=self._manifest_path,
        )
        self._require_schema(
            manifest,
            key="store_schema_version",
            expected=SCHEMA_VERSION,
            path=self._manifest_path,
        )
        if "aliases" in manifest:
            raise StoreCorruptionError(
                "manifest aliases are retired; migrate directly before opening the store"
            )
        for key in ("models", "tombstones", "idempotency"):
            if not isinstance(manifest.get(key), dict):
                raise StoreCorruptionError(f"manifest {self._manifest_path} field {key} is not a mapping")
        if not isinstance(manifest.get("generation"), int):
            raise StoreCorruptionError(f"manifest {self._manifest_path} generation is not an integer")
        return manifest

    def _read_snapshot(self, model_id: ModelId, revision: ModelRevision) -> ModelSnapshot:
        path = self._revision_path(model_id, revision)
        try:
            raw = self._read_json(path)
            snapshot = ModelSnapshot.from_dict(raw)
            validate_snapshot(snapshot)
        except FileNotFoundError as exc:
            raise StoreCorruptionError(
                f"manifest-authorized snapshot is missing: {path}"
            ) from exc
        except StoreSchemaError as exc:
            raise StoreSchemaError(f"artifact {path}: {exc}") from exc
        except (ValueError, StoreCorruptionError) as exc:
            raise StoreCorruptionError(f"invalid snapshot {path}: {exc}") from exc
        if snapshot.model_id != model_id or snapshot.revision != revision:
            raise StoreCorruptionError(f"snapshot path identity disagrees with payload: {path}")
        return snapshot

    def _read_commit_receipt(self, receipt_id: ReceiptId) -> CommitReceipt:
        path = self._receipt_path("commits", receipt_id)
        try:
            raw = self._read_json(path)
            self._require_schema(
                raw, key="artifact_schema", expected=RECEIPT_SCHEMA, path=path
            )
            receipt = receipt_from_dict(raw)
        except FileNotFoundError as exc:
            raise StoreCorruptionError(
                f"manifest-authorized commit receipt is missing: {path}"
            ) from exc
        except StoreSchemaError:
            raise
        except ValueError as exc:
            raise StoreCorruptionError(f"invalid commit receipt {path}: {exc}") from exc
        if not isinstance(receipt, CommitReceipt):
            raise StoreCorruptionError(f"receipt {path} is not a commit receipt")
        if receipt.receipt_id != receipt_id:
            raise StoreCorruptionError(f"receipt path identity disagrees with payload: {path}")
        return receipt

    def _raise_if_tombstoned(
        self, manifest: Mapping[str, Any], model_id: ModelId
    ) -> None:
        entry = manifest["tombstones"].get(str(model_id))
        if entry:
            raise TombstonedModelError(
                model_id,
                reason=str(entry.get("reason", "")),
                receipt_id=ReceiptId.parse(entry.get("receipt_id", "")),
            )

    def _find_prepared_idempotency(self, key: str) -> TransactionId | None:
        for path in sorted(self._journals_dir.glob("*.json")):
            raw = self._read_json(path)
            self._require_schema(raw, key="artifact_schema", expected=JOURNAL_SCHEMA, path=path)
            if raw.get("status") == "prepared" and raw.get("idempotency_key") == key:
                return TransactionId.parse(raw.get("transaction_id", ""))
        return None

    def _revision_path(self, model_id: ModelId, revision: ModelRevision) -> Path:
        return (
            self._models_dir
            / _storage_segment(model_id)
            / "revisions"
            / f"{_storage_segment(revision)}.json"
        )

    def _evaluation_path(
        self, model_id: ModelId, revision: ModelRevision, evaluation_id: EvaluationId
    ) -> Path:
        return (
            self._evaluations_dir
            / _storage_segment(model_id)
            / _storage_segment(revision)
            / f"{_storage_segment(evaluation_id)}.json"
        )

    def _journal_path(self, transaction_id: TransactionId) -> Path:
        return self._journals_dir / f"{_storage_segment(transaction_id)}.json"

    def _receipt_path(self, category: str, receipt_id: ReceiptId) -> Path:
        return self._receipts_dir / category / f"{_storage_segment(receipt_id)}.json"

    def _write_recovery_receipt(self, receipt: RecoveryReceipt) -> None:
        self._write_immutable_json(
            self._receipt_path("recovery", receipt.receipt_id), receipt.to_dict()
        )

    def _fault(self, point: str) -> None:
        if self._test_fault_hook is not None:
            self._test_fault_hook(point)

    @contextmanager
    def _writer_lock(self, transaction_id: TransactionId) -> Iterator[None]:
        metadata = {
            "artifact_schema": JOURNAL_SCHEMA,
            "store_schema_version": SCHEMA_VERSION,
            "lock_type": "writer",
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
            except StoreCorruptionError as exc:
                # Atomic exclusive creation precedes the small metadata write;
                # a competing writer may observe that narrow window.  Presence
                # is sufficient to fail closed as held, never to steal/delete.
                raise WriterLockHeldError(
                    f"writer lock exists at {self._writer_lock_path} but owner metadata "
                    "is not yet readable; publication refused"
                ) from exc
            if self._lock_owner_is_live(owner):
                raise WriterLockHeldError(
                    f"live writer lock owned by pid={owner.get('pid')} "
                    f"host={owner.get('host')} transaction={owner.get('transaction_id')}"
                )
            raise RecoveryRequiredError(
                f"stale or unverifiable writer lock at {self._writer_lock_path}; "
                "run explicit recover()"
            )
        try:
            yield
        finally:
            # This process is still alive, so normal exceptions (including test
            # fault injection) release their lock.  A real process crash leaves
            # the lock for explicit stale-owner recovery.
            try:
                current = self._read_lock_owner()
            except (FileNotFoundError, StoreCorruptionError):
                current = {}
            if current.get("transaction_id") == str(transaction_id):
                self._writer_lock_path.unlink(missing_ok=True)
                self._fsync_directory(self._locks_dir)

    def _prepare_explicit_recovery_lock(self) -> dict[str, Any] | None:
        if not self._writer_lock_path.exists():
            return None
        owner = self._read_lock_owner()
        if self._lock_owner_is_live(owner):
            raise WriterLockHeldError(
                f"explicit recovery refused live writer lock pid={owner.get('pid')} "
                f"host={owner.get('host')} transaction={owner.get('transaction_id')}"
            )
        # Remove only the exact stale lock observed.  Exclusive acquisition in
        # the caller detects any racer that creates a new live lock afterwards.
        self._writer_lock_path.unlink()
        self._fsync_directory(self._locks_dir)
        return dict(owner)

    def _read_lock_owner(self) -> dict[str, Any]:
        try:
            owner = self._read_json(self._writer_lock_path)
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise StoreCorruptionError(
                f"writer lock {self._writer_lock_path} is unreadable; explicit manual review required"
            ) from exc
        return owner

    @staticmethod
    def _lock_owner_is_live(owner: Mapping[str, Any]) -> bool:
        if owner.get("host") != socket.gethostname():
            # A lock from another host cannot be proven dead by this process.
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
        raw: Mapping[str, Any], *, key: str, expected: str, path: Path
    ) -> None:
        found = raw.get(key)
        if found != expected:
            raise StoreSchemaError(
                f"artifact {path} declares {key}={found!r}; expected {expected!r}; "
                "normal runtime has no compatibility reader—use explicit import/upgrade"
            )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise StoreCorruptionError(f"cannot read JSON artifact {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise StoreCorruptionError(f"JSON artifact {path} must contain an object")
        return raw

    def _write_immutable_json(self, path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = self._read_json(path)
            if canonical_json_bytes(existing) != canonical_json_bytes(value):
                raise StoreCorruptionError(
                    f"immutable artifact already exists with different content: {path}"
                )
            return
        try:
            self._write_exclusive_json(path, value)
        except FileExistsError:
            existing = self._read_json(path)
            if canonical_json_bytes(existing) != canonical_json_bytes(value):
                raise StoreCorruptionError(
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
            # Windows commonly refuses directory fsync; file fsync + atomic
            # replace remain the supported local durability primitive there.
            pass
        finally:
            os.close(descriptor)


__all__ = ["FileModelStore", "TestInjectedStoreFault"]
