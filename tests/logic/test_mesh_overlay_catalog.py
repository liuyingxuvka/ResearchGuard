from __future__ import annotations

import json

import pytest

from researchguard.logic.mesh_overlay_catalog import (
    CATALOG_DEPENDENCY_FORWARD_SHARD,
    CATALOG_DEPENDENCY_REVERSE_SHARD,
    OverlayCatalogError,
)
from researchguard.logic.mesh_store import (
    FileModelMeshStore,
    MeshIdempotencyConflictError,
    MeshStoreCorruptionError,
)

from .model_mesh_test_support import (
    build_definition,
    build_overlay,
    committed_models,
)


def prepared_store(tmp_path):
    p0, snapshots = committed_models(tmp_path / "p0")
    store = FileModelMeshStore(tmp_path / "mesh", model_store=p0)
    transaction = store.begin(
        "brain-main",
        None,
        "first-mesh",
        "catalog-test",
        expected_overlay_catalog_revision=None,
    )
    transaction.stage(build_definition(snapshots))
    transaction.commit()
    mesh = store.get("brain-main")
    return store, mesh


def register(store, mesh, overlay, *, key="overlay-one", expected=None):
    expected = expected or store.catalog_head(mesh.mesh_id, mesh.revision)
    transaction = store.begin_catalog(
        mesh.mesh_id,
        mesh.revision,
        expected,
        key,
        "catalog-test",
    )
    transaction.stage(overlay)
    return transaction.commit()


def test_catalog_genesis_and_registered_snapshot_bind_both_exact_dependency_shards(
    tmp_path,
) -> None:
    store, mesh = prepared_store(tmp_path)
    genesis = store.get_catalog(mesh.mesh_id, mesh.revision)
    assert genesis.entries == ()
    assert {item.kind for item in genesis.dependency_shard_sets} == {
        CATALOG_DEPENDENCY_FORWARD_SHARD,
        CATALOG_DEPENDENCY_REVERSE_SHARD,
    }

    overlay = build_overlay(mesh)
    register(store, mesh, overlay)
    current = store.get_catalog(mesh.mesh_id, mesh.revision)
    assert current.parent_revision == genesis.revision
    assert current.entries[0].overlay_id == overlay.evaluation_id
    assert current.binding_for(current.entries[0]) == overlay.dependency_binding
    assert store.catalog_dependents(
        current.pin,
        (overlay.dependency_binding.dependency_keys[0].identity_digest,),
    ) == (overlay.evaluation_id,)


def test_catalog_idempotency_resolves_before_cas_and_rejects_rebinding(tmp_path) -> None:
    store, mesh = prepared_store(tmp_path)
    genesis = store.catalog_head(mesh.mesh_id, mesh.revision)
    overlay = build_overlay(mesh)
    first = register(store, mesh, overlay, key="stable-overlay", expected=genesis)
    retry = register(store, mesh, overlay, key="stable-overlay", expected=genesis)
    assert retry == first

    different = build_overlay(mesh, profile="broad")
    transaction = store.begin_catalog(
        mesh.mesh_id,
        mesh.revision,
        genesis,
        "stable-overlay",
        "catalog-test",
    )
    transaction.stage(different)
    with pytest.raises(MeshIdempotencyConflictError, match="different overlay"):
        transaction.commit()


def test_catalog_rejects_simulation_overlay_and_duplicate_registration_owner(tmp_path) -> None:
    store, mesh = prepared_store(tmp_path)
    simulation = build_overlay(mesh, authority="simulation")
    transaction = store.begin_catalog(
        mesh.mesh_id,
        mesh.revision,
        store.catalog_head(mesh.mesh_id, mesh.revision),
        "simulation",
        "catalog-test",
    )
    with pytest.raises(OverlayCatalogError, match="simulation"):
        transaction.stage(simulation)

    overlay = build_overlay(mesh)
    register(store, mesh, overlay, key="first-owner")
    duplicate = store.begin_catalog(
        mesh.mesh_id,
        mesh.revision,
        store.catalog_head(mesh.mesh_id, mesh.revision),
        "second-owner",
        "catalog-test",
    )
    duplicate.stage(overlay)
    with pytest.raises(MeshIdempotencyConflictError, match="already registered"):
        duplicate.commit()


def test_overlay_currentness_requires_exact_catalog_registration_and_consumes_drift_once(
    tmp_path,
) -> None:
    store, mesh = prepared_store(tmp_path)
    overlay = build_overlay(mesh)
    genesis = store.get_catalog(mesh.mesh_id, mesh.revision)
    absent = overlay.currentness(mesh, catalog_snapshot=genesis)
    assert not absent.current
    assert {item.code for item in absent.diagnostics} == {"overlay_unregistered"}

    register(store, mesh, overlay)
    current_catalog = store.get_catalog(mesh.mesh_id, mesh.revision)
    current = overlay.currentness(mesh, catalog_snapshot=current_catalog)
    assert current.current
    assert not current.broad_current

    def one_drift():
        yield {"model": "advanced"}

    stale = overlay.currentness(
        mesh,
        catalog_snapshot=current_catalog,
        head_drift=one_drift(),
    )
    assert not stale.current
    assert "model_head_drift" in {item.code for item in stale.diagnostics}


def test_missing_or_corrupt_dependency_shard_blocks_catalog_without_overlay_scan(tmp_path) -> None:
    store, mesh = prepared_store(tmp_path)
    overlay = build_overlay(mesh)
    register(store, mesh, overlay)
    shards = list((store.root / "c").glob("**/d/**/*.json"))
    assert shards
    for shard in shards:
        raw = json.loads(shard.read_text(encoding="utf-8"))
        raw["digest"] = "sha256:" + "0" * 64
        shard.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(OverlayCatalogError, match="digest mismatch"):
        store.get_catalog(mesh.mesh_id, mesh.revision)
    assert list((store.root / "c").glob("**/o/*.json"))


def test_catalog_snapshot_and_overlay_tampering_is_detected(tmp_path) -> None:
    store, mesh = prepared_store(tmp_path)
    overlay = build_overlay(mesh)
    register(store, mesh, overlay)
    overlay_path = next((store.root / "c").glob("**/o/*.json"))
    raw = json.loads(overlay_path.read_text(encoding="utf-8"))
    raw["warnings"] = ["tampered"]
    overlay_path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(Exception, match="ID does not match|fingerprint"):
        store.get_overlay(mesh.mesh_id, mesh.revision, overlay.evaluation_id)


def test_catalog_history_remains_replayable_after_later_catalog_revision(tmp_path) -> None:
    store, mesh = prepared_store(tmp_path)
    genesis = store.get_catalog(mesh.mesh_id, mesh.revision)
    overlay = build_overlay(mesh)
    receipt = register(store, mesh, overlay)
    current = store.get_catalog(mesh.mesh_id, mesh.revision)
    historical = store.get_catalog(mesh.mesh_id, mesh.revision, genesis.revision)
    assert current.revision == receipt.catalog_revision
    assert historical.entries == ()
    assert historical.revision == genesis.revision
