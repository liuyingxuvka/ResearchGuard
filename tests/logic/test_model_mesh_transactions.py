from __future__ import annotations

import json

import pytest

from researchguard.logic.mesh_store import (
    FileModelMeshStore,
    MeshIdempotencyConflictError,
    MeshStoreCorruptionError,
    MeshTransactionConflictError,
    OverlayCatalogConflictError,
)
from researchguard.logic.model_mesh import ModelMeshDefinition

from .model_mesh_test_support import (
    build_definition,
    build_overlay,
    committed_models,
)


def create_mesh_store(tmp_path):
    p0, snapshots = committed_models(tmp_path / "p0")
    return p0, snapshots, FileModelMeshStore(tmp_path / "mesh", model_store=p0)


def commit_first(store, snapshots, *, key="mesh-first"):
    transaction = store.begin(
        "brain-main",
        None,
        key,
        "mesh-test",
        expected_overlay_catalog_revision=None,
    )
    transaction.stage(build_definition(snapshots))
    return transaction.commit()


def definition_with_baseline(definition, pin, *, purpose="updated"):
    return ModelMeshDefinition(
        mesh_id=definition.mesh_id,
        registry=definition.registry,
        memberships=definition.memberships,
        cross_model_edges=definition.cross_model_edges,
        invalidation_baseline=pin,
        provenance=definition.provenance,
        metadata={"purpose": purpose},
    )


def test_first_commit_publishes_one_mesh_revision_and_exact_catalog_genesis(tmp_path) -> None:
    _p0, snapshots, store = create_mesh_store(tmp_path)
    receipt = commit_first(store, snapshots)

    assert store.head("brain-main") == receipt.revision
    assert store.list_revisions("brain-main") == (receipt.revision,)
    mesh = store.get("brain-main")
    catalog = store.get_catalog(mesh.mesh_id, mesh.revision)
    assert catalog.pin == receipt.child_catalog_pin
    assert catalog.entries == ()
    assert len(catalog.dependency_shard_sets) == 2


def test_identical_mesh_idempotent_retry_resolves_before_advanced_head_cas(tmp_path) -> None:
    _p0, snapshots, store = create_mesh_store(tmp_path)
    first = commit_first(store, snapshots, key="same-mesh-operation")
    retry = store.begin(
        "brain-main",
        None,
        "same-mesh-operation",
        "mesh-test",
        expected_overlay_catalog_revision=None,
    )
    retry.stage(build_definition(snapshots))

    assert retry.commit() == first
    assert store.list_revisions("brain-main") == (first.revision,)


def test_stale_mesh_writer_loses_with_immutable_conflict_receipt(tmp_path) -> None:
    _p0, snapshots, store = create_mesh_store(tmp_path)
    first = store.begin(
        "brain-main", None, "writer-one", "one", expected_overlay_catalog_revision=None
    )
    second = store.begin(
        "brain-main", None, "writer-two", "two", expected_overlay_catalog_revision=None
    )
    original = build_definition(snapshots)
    first.stage(original)
    second.stage(
        ModelMeshDefinition(
            mesh_id=original.mesh_id,
            registry=original.registry,
            memberships=original.memberships,
            cross_model_edges=original.cross_model_edges,
            provenance=original.provenance,
            metadata={"writer": "two"},
        )
    )
    winner = first.commit()
    with pytest.raises(MeshTransactionConflictError) as caught:
        second.commit()
    assert caught.value.expected is None
    assert caught.value.actual == winner.revision
    assert store.head("brain-main") == winner.revision


def test_idempotency_key_cannot_be_rebound_to_different_mesh_content(tmp_path) -> None:
    _p0, snapshots, store = create_mesh_store(tmp_path)
    first = commit_first(store, snapshots, key="stable-key")
    changed = build_definition(snapshots)
    changed = ModelMeshDefinition(
        mesh_id=changed.mesh_id,
        registry=changed.registry,
        memberships=changed.memberships,
        cross_model_edges=changed.cross_model_edges,
        provenance=changed.provenance,
        metadata={"changed": True},
    )
    retry = store.begin(
        "brain-main", None, "stable-key", "mesh-test", expected_overlay_catalog_revision=None
    )
    retry.stage(changed)
    with pytest.raises(MeshIdempotencyConflictError, match="different mesh content"):
        retry.commit()
    assert store.head("brain-main") == first.revision


def test_mesh_update_pins_parent_catalog_and_creates_invalidation_bound_child_genesis(
    tmp_path,
) -> None:
    _p0, snapshots, store = create_mesh_store(tmp_path)
    first = commit_first(store, snapshots)
    parent_mesh = store.get("brain-main")
    parent_pin = store.current_catalog_pin(parent_mesh.mesh_id, parent_mesh.revision)
    original = build_definition(snapshots)
    updated = definition_with_baseline(original, parent_pin)
    transaction = store.begin(
        "brain-main",
        first.revision,
        "mesh-update",
        "mesh-test",
        expected_overlay_catalog_revision=parent_pin.catalog_revision,
    )
    transaction.stage(updated)
    receipt = transaction.commit()
    child_catalog = store.get_catalog("brain-main", receipt.revision)

    assert receipt.parent_catalog_baseline == parent_pin
    assert receipt.invalidation_receipt_id is not None
    assert child_catalog.invalidation_receipt_id == str(receipt.invalidation_receipt_id)
    assert child_catalog.invalidation_receipt_digest is not None
    assert child_catalog.entries == ()
    assert store.get("brain-main", first.revision) == parent_mesh


def test_stale_parent_catalog_cas_blocks_mesh_update(tmp_path) -> None:
    _p0, snapshots, store = create_mesh_store(tmp_path)
    first = commit_first(store, snapshots)
    mesh = store.get("brain-main")
    old_pin = store.current_catalog_pin(mesh.mesh_id, mesh.revision)
    overlay = build_overlay(mesh)
    catalog_tx = store.begin_catalog(
        mesh.mesh_id,
        mesh.revision,
        old_pin.catalog_revision,
        "register-overlay",
        "mesh-test",
    )
    catalog_tx.stage(overlay)
    catalog_tx.commit()

    staged = definition_with_baseline(build_definition(snapshots), old_pin)
    transaction = store.begin(
        mesh.mesh_id,
        first.revision,
        "stale-parent-catalog",
        "mesh-test",
        expected_overlay_catalog_revision=old_pin.catalog_revision,
    )
    transaction.stage(staged)
    with pytest.raises(OverlayCatalogConflictError):
        transaction.commit()
    assert store.head(mesh.mesh_id) == first.revision


def test_catalog_registration_has_independent_cas_and_never_changes_mesh_manifest(tmp_path) -> None:
    _p0, snapshots, store = create_mesh_store(tmp_path)
    commit_first(store, snapshots)
    mesh = store.get("brain-main")
    pin = store.current_catalog_pin(mesh.mesh_id, mesh.revision)
    overlay = build_overlay(mesh)
    mesh_manifest = (store.root / "mesh-manifest.json").read_bytes()

    transaction = store.begin_catalog(
        mesh.mesh_id,
        mesh.revision,
        pin.catalog_revision,
        "overlay-one",
        "mesh-test",
    )
    transaction.stage(overlay)
    receipt = transaction.commit()

    assert store.get_overlay(mesh.mesh_id, mesh.revision, overlay.evaluation_id) == overlay
    assert store.current_catalog_pin(mesh.mesh_id, mesh.revision).catalog_revision == receipt.catalog_revision
    assert (store.root / "mesh-manifest.json").read_bytes() == mesh_manifest

    stale = store.begin_catalog(
        mesh.mesh_id,
        mesh.revision,
        pin.catalog_revision,
        "overlay-stale",
        "mesh-test",
    )
    stale.stage(build_overlay(mesh))
    with pytest.raises(OverlayCatalogConflictError):
        stale.commit()


def test_abort_is_terminal_and_does_not_publish_mesh_head(tmp_path) -> None:
    _p0, snapshots, store = create_mesh_store(tmp_path)
    transaction = store.begin(
        "brain-main", None, "abort-me", "mesh-test", expected_overlay_catalog_revision=None
    )
    transaction.stage(build_definition(snapshots))
    receipt = transaction.abort("operator cancelled")
    assert receipt.status == "aborted"
    assert store.head("brain-main") is None
    assert transaction.abort("operator cancelled") == receipt


def test_mesh_reads_are_immutable_and_lazy_model_reads_are_counted_once(tmp_path) -> None:
    _p0, snapshots, store = create_mesh_store(tmp_path)
    commit_first(store, snapshots)
    view = store.open_view("brain-main")
    ref = view.snapshot.registry[0].model_ref
    node_ref = next(
        membership.owner
        for membership in view.snapshot.memberships
        if membership.owner.model_id == ref.model_id
    )
    assert view.model_read_count == 0
    view.node(node_ref)
    view.node(node_ref)
    assert view.model_read_count == 1
    with pytest.raises(TypeError):
        view.snapshot.metadata["mutated"] = True  # type: ignore[index]


def test_current_schema_index_repair_rebuilds_missing_exact_shard_with_receipt(tmp_path) -> None:
    _p0, snapshots, store = create_mesh_store(tmp_path)
    receipt = commit_first(store, snapshots)
    shard_files = list((store.root / "m").glob("**/s/**/*.json"))
    assert shard_files
    missing_kind = json.loads(shard_files[0].read_text(encoding="utf-8"))["kind"]
    shard_files[0].unlink()
    with pytest.raises(MeshStoreCorruptionError, match="shard is missing"):
        store.get("brain-main")
    repair = store.repair_indexes(
        "brain-main", receipt.revision, actor="mesh-test"
    )
    assert dict(repair.before_shard_digests)[missing_kind] == "missing"
    assert shard_files[0].exists()
    assert store.get("brain-main").revision == receipt.revision


def test_missing_current_mesh_manifest_is_visible_failure_not_layout_search(tmp_path) -> None:
    p0, snapshots, store = create_mesh_store(tmp_path)
    commit_first(store, snapshots)
    (store.root / "mesh-manifest.json").unlink()
    with pytest.raises(MeshStoreCorruptionError, match="no fallback layout"):
        FileModelMeshStore(store.root, model_store=p0)
