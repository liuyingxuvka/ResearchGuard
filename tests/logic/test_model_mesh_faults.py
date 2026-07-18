from __future__ import annotations

import json
import os
import socket

import pytest

from researchguard.logic.mesh_store import (
    FileModelMeshStore,
    MeshStoreSchemaError,
    MeshWriterLockHeldError,
    TestInjectedMeshStoreFault,
)
from researchguard.logic.schema import MESH_JOURNAL_SCHEMA, MESH_SCHEMA_VERSION

from .model_mesh_test_support import (
    build_definition,
    build_overlay,
    committed_models,
)


MESH_FAULT_POINTS = FileModelMeshStore._MESH_COMMIT_FAULT_POINTS
CATALOG_FAULT_POINTS = FileModelMeshStore._CATALOG_COMMIT_FAULT_POINTS


def injecting(target):
    def hook(point):
        if point == target:
            raise TestInjectedMeshStoreFault(target)

    return hook


def begin_first(store, snapshots, *, key="faulted-first"):
    transaction = store.begin(
        "brain-main",
        None,
        key,
        "fault-test",
        expected_overlay_catalog_revision=None,
    )
    transaction.stage(build_definition(snapshots))
    return transaction


@pytest.mark.parametrize("fault_point", MESH_FAULT_POINTS)
def test_every_mesh_publication_fault_recovers_to_old_or_complete_new_head(
    tmp_path, fault_point
) -> None:
    case = tmp_path / fault_point
    p0, snapshots = committed_models(case / "p0")
    store = FileModelMeshStore(
        case / "mesh", model_store=p0, _test_fault_hook=injecting(fault_point)
    )
    transaction = begin_first(store, snapshots)
    with pytest.raises(TestInjectedMeshStoreFault, match=fault_point):
        transaction.commit()

    before = store.head("brain-main")
    recovery = store.recover()
    reopened = FileModelMeshStore(case / "mesh", model_store=p0)
    after = reopened.head("brain-main")
    assert before is None or before == after
    if after is not None:
        mesh = reopened.get("brain-main")
        assert reopened.get_catalog(mesh.mesh_id, mesh.revision).mesh_revision == mesh.revision
    else:
        assert fault_point not in {
            "after_catalog_manifest",
            "after_mesh_manifest",
            "after_terminal_journal",
        }
    retry = begin_first(reopened, snapshots)
    receipt = retry.commit()
    assert reopened.head("brain-main") == receipt.revision
    assert reopened.get_catalog("brain-main", receipt.revision).pin == receipt.child_catalog_pin
    if fault_point not in {"after_lock", "after_terminal_journal"}:
        assert recovery


@pytest.mark.parametrize("fault_point", CATALOG_FAULT_POINTS)
def test_every_catalog_publication_fault_recovers_without_mutating_mesh_authority(
    tmp_path, fault_point
) -> None:
    case = tmp_path / fault_point
    p0, snapshots = committed_models(case / "p0")
    base = FileModelMeshStore(case / "mesh", model_store=p0)
    begin_first(base, snapshots, key="base").commit()
    mesh = base.get("brain-main")
    pin = base.current_catalog_pin(mesh.mesh_id, mesh.revision)
    mesh_manifest_before = (base.root / "mesh-manifest.json").read_bytes()

    store = FileModelMeshStore(
        case / "mesh", model_store=p0, _test_fault_hook=injecting(fault_point)
    )
    overlay = build_overlay(mesh)
    transaction = store.begin_catalog(
        mesh.mesh_id,
        mesh.revision,
        pin.catalog_revision,
        "faulted-overlay",
        "fault-test",
    )
    transaction.stage(overlay)
    with pytest.raises(TestInjectedMeshStoreFault, match=fault_point):
        transaction.commit()

    recovery = store.recover()
    reopened = FileModelMeshStore(case / "mesh", model_store=p0)
    assert (reopened.root / "mesh-manifest.json").read_bytes() == mesh_manifest_before
    current = reopened.get_catalog(mesh.mesh_id, mesh.revision)
    assert current.revision in {pin.catalog_revision, transaction.expected_catalog_revision} or current.entries

    if not current.entries:
        retry = reopened.begin_catalog(
            mesh.mesh_id,
            mesh.revision,
            current.revision,
            "faulted-overlay",
            "fault-test",
        )
        retry.stage(overlay)
        retry.commit()
    assert reopened.get_overlay(mesh.mesh_id, mesh.revision, overlay.evaluation_id) == overlay
    if fault_point not in {"catalog_after_lock", "catalog_after_terminal_journal"}:
        assert recovery


def test_live_shared_writer_lock_is_never_stolen(tmp_path) -> None:
    p0, snapshots = committed_models(tmp_path / "p0")
    store = FileModelMeshStore(tmp_path / "mesh", model_store=p0)
    lock = store.root / "locks" / "writer.lock"
    lock.write_text(
        json.dumps(
            {
                "artifact_schema": MESH_JOURNAL_SCHEMA,
                "mesh_schema_version": MESH_SCHEMA_VERSION,
                "lock_type": "mesh-catalog-shared-writer",
                "pid": os.getpid(),
                "host": socket.gethostname(),
                "transaction_id": "mesh-tx-live",
                "created_at": "2026-07-14T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    transaction = begin_first(store, snapshots)
    with pytest.raises(MeshWriterLockHeldError, match="live shared writer lock"):
        transaction.commit()
    with pytest.raises(MeshWriterLockHeldError, match="refused live"):
        store.recover()
    assert lock.exists()


def test_explicit_recovery_removes_only_a_proven_dead_lock(tmp_path) -> None:
    p0, _snapshots = committed_models(tmp_path / "p0")
    store = FileModelMeshStore(tmp_path / "mesh", model_store=p0)
    lock = store.root / "locks" / "writer.lock"
    lock.write_text(
        json.dumps(
            {
                "artifact_schema": MESH_JOURNAL_SCHEMA,
                "mesh_schema_version": MESH_SCHEMA_VERSION,
                "lock_type": "mesh-catalog-shared-writer",
                "pid": 2147483647,
                "host": socket.gethostname(),
                "transaction_id": "mesh-tx-dead",
                "created_at": "2026-07-14T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    receipts = store.recover()
    assert not lock.exists()
    assert receipts[0].action == "remove_stale_lock"


def test_noncurrent_mesh_and_catalog_manifests_fail_closed(tmp_path) -> None:
    p0, snapshots = committed_models(tmp_path / "p0")
    store = FileModelMeshStore(tmp_path / "mesh", model_store=p0)
    receipt = begin_first(store, snapshots).commit()
    manifest_path = store.root / "mesh-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_schema"] = "researchguard.logic.retired-mesh-manifest.v0"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(MeshStoreSchemaError, match="no compatibility"):
        FileModelMeshStore(store.root, model_store=p0)

    manifest["artifact_schema"] = "researchguard.logic.model-mesh-manifest.v1"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    reopened = FileModelMeshStore(store.root, model_store=p0)
    catalog_manifest = next((store.root / "c").glob("**/manifest.json"))
    raw = json.loads(catalog_manifest.read_text(encoding="utf-8"))
    raw["artifact_schema"] = "researchguard.logic.retired-catalog-manifest.v0"
    catalog_manifest.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(MeshStoreSchemaError, match="no compatibility"):
        reopened.get_catalog("brain-main", receipt.revision)
