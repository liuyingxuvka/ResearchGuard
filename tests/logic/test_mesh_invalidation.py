from __future__ import annotations

import pytest

from researchguard.logic.mesh_invalidation import (
    diff_mesh_dependencies,
    mesh_authority_dependency_keys,
)
from researchguard.logic.mesh_store import FileModelMeshStore, MeshStoreCorruptionError
from researchguard.logic.model_mesh import ModelMeshDefinition

from .model_mesh_test_support import (
    build_definition,
    build_overlay,
    commit_model,
    committed_models,
    compile_snapshot,
    model_payload,
)


def prepared_parent(tmp_path):
    p0, snapshots = committed_models(tmp_path / "p0")
    store = FileModelMeshStore(tmp_path / "mesh", model_store=p0)
    first = store.begin(
        "brain-main",
        None,
        "first-mesh",
        "invalidation-test",
        expected_overlay_catalog_revision=None,
    )
    first.stage(build_definition(snapshots))
    first.commit()
    parent = store.get("brain-main")
    return p0, snapshots, store, parent


def register(store, mesh, overlay, key):
    transaction = store.begin_catalog(
        mesh.mesh_id,
        mesh.revision,
        store.catalog_head(mesh.mesh_id, mesh.revision),
        key,
        "invalidation-test",
    )
    transaction.stage(overlay)
    return transaction.commit()


def update_definition(snapshots, pin, *, metadata=None):
    base = build_definition(snapshots)
    return ModelMeshDefinition(
        mesh_id=base.mesh_id,
        registry=base.registry,
        memberships=base.memberships,
        cross_model_edges=base.cross_model_edges,
        invalidation_baseline=pin,
        provenance=base.provenance,
        metadata=metadata or {"purpose": "updated"},
    )


def commit_update(store, parent, definition, pin, key="mesh-update"):
    transaction = store.begin(
        parent.mesh_id,
        parent.revision,
        key,
        "invalidation-test",
        expected_overlay_catalog_revision=pin.catalog_revision,
    )
    transaction.stage(definition)
    return transaction.commit()


def test_exact_model_pin_change_invalidates_only_overlay_that_declared_that_model(
    tmp_path,
) -> None:
    p0, snapshots, store, parent = prepared_parent(tmp_path)
    overlay_a = build_overlay(parent, selected_index=0)
    overlay_b = build_overlay(parent, selected_index=1)
    register(store, parent, overlay_a, "overlay-a")
    register(store, parent, overlay_b, "overlay-b")
    parent_catalog = store.get_catalog(parent.mesh_id, parent.revision)
    pin = parent_catalog.pin

    updated_a = commit_model(
        p0,
        "model-a",
        payload=model_payload("model-a", claim_text="changed claim"),
        expected_revision=snapshots[0].revision,
        idempotency_key="advance-model-a",
    )
    updated_snapshots = (updated_a, p0.get("model-b"))
    receipt = commit_update(
        store,
        parent,
        update_definition(updated_snapshots, pin),
        pin,
    )
    invalidation = store.get_invalidation_receipt(receipt.invalidation_receipt_id)

    assert invalidation.invalidated_overlay_ids == (overlay_a.evaluation_id,)
    assert {item["overlay_id"] for item in invalidation.unaffected_overlays} == {
        str(overlay_b.evaluation_id)
    }
    child = store.get(parent.mesh_id)
    child_catalog = store.get_catalog(child.mesh_id, child.revision)
    assert child_catalog.invalidation_receipt_id == str(invalidation.receipt_id)
    assert overlay_a.currentness(parent, catalog_snapshot=parent_catalog).current
    assert not overlay_a.currentness(
        child,
        catalog_snapshot=child_catalog,
        invalidated_overlay_ids=invalidation.invalidated_overlay_ids,
    ).current


def test_mesh_metadata_change_does_not_blanket_invalidate_unrelated_overlays(tmp_path) -> None:
    _p0, snapshots, store, parent = prepared_parent(tmp_path)
    overlays = (
        build_overlay(parent, selected_index=0),
        build_overlay(parent, selected_index=1),
    )
    for index, overlay in enumerate(overlays):
        register(store, parent, overlay, f"overlay-{index}")
    catalog = store.get_catalog(parent.mesh_id, parent.revision)
    receipt = commit_update(
        store,
        parent,
        update_definition(snapshots, catalog.pin, metadata={"note": "unrelated"}),
        catalog.pin,
        key="metadata-only",
    )
    invalidation = store.get_invalidation_receipt(receipt.invalidation_receipt_id)
    assert invalidation.invalidated_overlay_ids == ()
    assert {item["overlay_id"] for item in invalidation.unaffected_overlays} == {
        str(item.evaluation_id) for item in overlays
    }


def test_dependency_delta_contains_old_and_new_model_pin_authority(tmp_path) -> None:
    p0, snapshots, _store, parent = prepared_parent(tmp_path)
    updated_a = commit_model(
        p0,
        "model-a",
        payload=model_payload("model-a", claim_text="changed"),
        expected_revision=snapshots[0].revision,
        idempotency_key="change-for-delta",
    )
    child_definition = build_definition((updated_a, p0.get("model-b")))
    child, child_indexes = compile_snapshot(
        child_definition, (updated_a, p0.get("model-b")), parent_revision=parent.revision
    )
    parent_definition = build_definition(snapshots)
    _parent_copy, parent_indexes = compile_snapshot(parent_definition, snapshots)
    delta = diff_mesh_dependencies(parent, parent_indexes, child, child_indexes)
    assert any(item.kind == "model_pin" for item in delta.removed_or_changed)
    assert any(item.kind == "model_pin" for item in delta.added_or_changed)
    assert set(delta.affected_parent_digests).isdisjoint(
        item.identity_digest for item in delta.added_or_changed
    )


def test_missing_declared_invalidation_receipt_fails_without_receipt_scan(tmp_path) -> None:
    _p0, snapshots, store, parent = prepared_parent(tmp_path)
    catalog = store.get_catalog(parent.mesh_id, parent.revision)
    receipt = commit_update(
        store,
        parent,
        update_definition(snapshots, catalog.pin),
        catalog.pin,
    )
    target = next((store.root / "r" / "mesh-invalidations").glob("*.json"))
    target.unlink()
    with pytest.raises(MeshStoreCorruptionError, match="receipt is missing"):
        store.get_invalidation_receipt(receipt.invalidation_receipt_id)


def test_dependency_key_projection_is_deterministic_for_same_exact_mesh(tmp_path) -> None:
    _p0, snapshots, _store, parent = prepared_parent(tmp_path)
    definition = build_definition(snapshots)
    _copy, indexes = compile_snapshot(definition, snapshots)
    first = mesh_authority_dependency_keys(parent, indexes)
    second = mesh_authority_dependency_keys(parent, indexes)
    assert first == second
    assert len({item.identity_digest for item in first}) == len(first)
