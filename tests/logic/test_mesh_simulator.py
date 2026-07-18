from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from researchguard.logic.identity import EdgeId, QualifiedModelRef
from researchguard.logic.mesh_materialization import MeshMaterializationRequest
from researchguard.logic.mesh_overlay_catalog import OverlayCatalogEntry, OverlayCatalogError
from researchguard.logic.mesh_simulator import (
    MeshNodeOverride,
    MeshSimulationDelta,
    MeshSimulationError,
    ModelPinReplacement,
    SimulationMeshView,
    adoption_requirements,
    simulate_mesh,
)
from researchguard.logic.mesh_store import FileModelMeshStore, MeshTransactionConflictError
from researchguard.logic.model_mesh import (
    CrossModelEdge,
    MeshMembership,
    ModelMeshDefinition,
)
from researchguard.logic.schema import STATE_OUT

from .model_mesh_test_support import (
    build_definition,
    commit_model,
    committed_models,
    mesh_provenance,
    model_payload,
    model_ref,
    node_ref,
)


def prepared_store(tmp_path):
    p0, snapshots = committed_models(tmp_path / "p0")
    store = FileModelMeshStore(tmp_path / "mesh", model_store=p0)
    transaction = store.begin(
        "brain-main",
        None,
        "simulation-base",
        "simulation-test",
        expected_overlay_catalog_revision=None,
    )
    transaction.stage(build_definition(snapshots))
    transaction.commit()
    return p0, snapshots, store


def request(root, **overrides):
    values = {
        "roots": (root,),
        "direction": "both",
        "hop_limit": 8,
        "node_limit": 100,
        "edge_limit": 200,
        "model_limit": 10,
        "byte_limit": 1_000_000,
        "profile": "bounded",
    }
    values.update(overrides)
    return MeshMaterializationRequest(**values)


def authority_files(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def delta_for(store, **values):
    snapshot = store.get("brain-main")
    return MeshSimulationDelta(
        base_mesh_id=snapshot.mesh_id,
        base_mesh_revision=snapshot.revision,
        **values,
    )


def test_empty_simulation_is_deterministic_and_never_writes_authority(tmp_path) -> None:
    _p0, snapshots, store = prepared_store(tmp_path)
    before = authority_files(tmp_path)
    delta = delta_for(store, metadata={"purpose": "no-op-isolation-proof"})

    first = simulate_mesh(
        store.open_view("brain-main"),
        delta,
        request(node_ref(snapshots[0], "claim-root")),
        requested_claim_scope=(node_ref(snapshots[0], "claim-root"),),
        depth_budget=1,
    )
    second = simulate_mesh(
        store.open_view("brain-main"),
        MeshSimulationDelta.from_dict(delta.to_dict()),
        request(node_ref(snapshots[0], "claim-root")),
        requested_claim_scope=(node_ref(snapshots[0], "claim-root"),),
        depth_budget=1,
    )

    assert first.overlay.authority == "simulation"
    assert not first.overlay.broad_claim_licensed
    assert first.receipt.authority == "simulation-only"
    assert first.overlay.fingerprint == second.overlay.fingerprint
    assert first.delta.delta_digest == second.delta.delta_digest
    assert authority_files(tmp_path) == before
    with pytest.raises(OverlayCatalogError, match="simulation overlay"):
        OverlayCatalogEntry.from_overlay(first.overlay, registered_at="2026-07-14T12:00:00Z")


def test_evidence_availability_override_is_sparse_and_p0_remains_unchanged(tmp_path) -> None:
    p0, snapshots, store = prepared_store(tmp_path)
    evidence = node_ref(snapshots[0], "evidence-one")
    original_payload = copy.deepcopy(snapshots[0].authoring_payload())
    before = authority_files(tmp_path)
    delta = delta_for(
        store,
        evidence_availability_changes=(
            MeshNodeOverride(evidence, {"missing": True}),
        ),
    )

    result = simulate_mesh(
        store.open_view("brain-main"),
        delta,
        request(evidence),
        requested_claim_scope=(evidence,),
        depth_budget=1,
    )
    results = {item.node_ref: item for item in result.overlay.node_results}

    assert results[evidence].state == STATE_OUT
    assert result.shared_model_count == 1
    assert result.overridden_model_count == 1
    assert result.copied_node_count == 1
    assert p0.get(snapshots[0].model_id, snapshots[0].revision).authoring_payload() == original_payload
    assert authority_files(tmp_path) == before
    assert adoption_requirements(delta) == ("p0_commit_then_mesh_repin",)


def test_virtual_edge_and_membership_change_only_the_simulated_topology(tmp_path) -> None:
    _p0, snapshots, store = prepared_store(tmp_path)
    added_edge = CrossModelEdge(
        id=EdgeId("simulation-b-to-a"),
        source=node_ref(snapshots[1], "evidence-one"),
        target=node_ref(snapshots[0], "claim-root"),
        type="supports",
        provenance=(mesh_provenance("simulation-b-to-a"),),
    )
    added_membership = MeshMembership(
        owner=node_ref(snapshots[1], "claim-root"),
        logical_model=model_ref(snapshots[0]),
        roles=("simulated-shared-claim",),
        provenance=(mesh_provenance("simulated-membership"),),
    )
    delta = delta_for(
        store,
        edge_additions=(added_edge,),
        membership_additions=(added_membership,),
    )
    view = SimulationMeshView(store.open_view("brain-main"), delta)

    assert added_edge in view.outgoing_cross_edges(added_edge.source)
    assert added_membership in view.memberships_for_node(added_membership.owner)
    assert model_ref(snapshots[0]) in view.model_dependencies(model_ref(snapshots[1]))
    canonical = store.get("brain-main")
    assert added_edge not in canonical.cross_model_edges
    assert added_membership not in canonical.memberships
    assert adoption_requirements(delta) == ("ordinary_mesh_catalog_cas",)


def test_pin_replacement_reads_exact_target_revision_without_advancing_base_mesh(tmp_path) -> None:
    p0, snapshots, store = prepared_store(tmp_path)
    changed_payload = model_payload("model-a", claim_text="Simulated replacement claim")
    replacement = commit_model(
        p0,
        "model-a",
        payload=changed_payload,
        expected_revision=snapshots[0].revision,
        idempotency_key="replacement-p0-revision",
    )
    pin = ModelPinReplacement(model_ref(snapshots[0]), model_ref(replacement))
    delta = delta_for(store, pin_replacements=(pin,))
    base_head = store.head("brain-main")
    view = SimulationMeshView(store.open_view("brain-main"), delta)

    assert model_ref(replacement) in {item.model_ref for item in view.snapshot.registry}
    assert model_ref(snapshots[0]) not in {item.model_ref for item in view.snapshot.registry}
    assert view.node(node_ref(replacement, "claim-root"))["text"] == "Simulated replacement claim"
    assert store.head("brain-main") == base_head
    assert store.get("brain-main").registry[0].model_ref == model_ref(snapshots[0])
    assert adoption_requirements(delta) == ("ordinary_mesh_catalog_cas",)


def test_replacement_revision_must_preserve_every_affected_endpoint(tmp_path) -> None:
    p0, snapshots, store = prepared_store(tmp_path)
    broken_payload = model_payload("model-a")
    del broken_payload["nodes"]["evidence-one"]
    broken_payload["edges"] = [
        item
        for item in broken_payload["edges"]
        if item["source"] != "evidence-one" and item["target"] != "evidence-one"
    ]
    broken_payload["blocks"]["block-root"]["member_nodes"].remove("evidence-one")
    broken_payload["blocks"]["block-root"]["input_nodes"].remove("evidence-one")
    replacement = commit_model(
        p0,
        "model-a",
        payload=broken_payload,
        expected_revision=snapshots[0].revision,
        idempotency_key="broken-replacement",
    )
    delta = delta_for(
        store,
        pin_replacements=(
            ModelPinReplacement(model_ref(snapshots[0]), model_ref(replacement)),
        ),
    )
    with pytest.raises(MeshSimulationError, match="simulated node is missing"):
        SimulationMeshView(store.open_view("brain-main"), delta)


def test_delta_digest_tamper_and_wrong_override_type_fail_closed(tmp_path) -> None:
    _p0, snapshots, store = prepared_store(tmp_path)
    delta = delta_for(
        store,
        evidence_availability_changes=(
            MeshNodeOverride(node_ref(snapshots[0], "evidence-one"), {"missing": True}),
        ),
    )
    raw = delta.to_dict()
    raw["metadata"] = {"tampered": True}
    with pytest.raises(MeshSimulationError, match="digest mismatch"):
        MeshSimulationDelta.from_dict(raw)

    wrong_type = delta_for(
        store,
        evidence_availability_changes=(
            MeshNodeOverride(node_ref(snapshots[0], "claim-root"), {"missing": True}),
        ),
    )
    with pytest.raises(MeshSimulationError, match="requires Evidence"):
        SimulationMeshView(store.open_view("brain-main"), wrong_type)


def test_override_cannot_bind_a_replaced_source_revision(tmp_path) -> None:
    p0, snapshots, store = prepared_store(tmp_path)
    replacement = commit_model(
        p0,
        "model-a",
        payload=model_payload("model-a", claim_text="replacement"),
        expected_revision=snapshots[0].revision,
        idempotency_key="source-override-replacement",
    )
    delta = delta_for(
        store,
        pin_replacements=(
            ModelPinReplacement(model_ref(snapshots[0]), model_ref(replacement)),
        ),
        evidence_availability_changes=(
            MeshNodeOverride(node_ref(snapshots[0], "evidence-one"), {"missing": True}),
        ),
    )
    with pytest.raises(MeshSimulationError, match="replacement revision"):
        SimulationMeshView(store.open_view("brain-main"), delta)


def test_combined_topology_and_p0_delta_has_two_explicit_adoption_steps(tmp_path) -> None:
    _p0, snapshots, store = prepared_store(tmp_path)
    delta = delta_for(
        store,
        edge_removals=(EdgeId("cross-evidence-a-to-claim-b"),),
        evidence_availability_changes=(
            MeshNodeOverride(node_ref(snapshots[0], "evidence-one"), {"missing": True}),
        ),
    )
    assert adoption_requirements(delta) == (
        "ordinary_mesh_catalog_cas",
        "p0_commit_then_mesh_repin",
    )


def test_simulated_base_cannot_be_adopted_after_mesh_head_advances(tmp_path) -> None:
    _p0, snapshots, store = prepared_store(tmp_path)
    base = store.get("brain-main")
    base_catalog = store.current_catalog_pin(base.mesh_id, base.revision)
    delta = delta_for(
        store,
        edge_removals=(EdgeId("cross-evidence-a-to-claim-b"),),
    )
    advanced_definition = build_definition(snapshots)
    advanced_definition = ModelMeshDefinition(
        mesh_id=advanced_definition.mesh_id,
        registry=advanced_definition.registry,
        memberships=advanced_definition.memberships,
        cross_model_edges=advanced_definition.cross_model_edges,
        invalidation_baseline=base_catalog,
        provenance=advanced_definition.provenance,
        metadata={"advance": "before-simulation-adoption"},
    )
    winner = store.begin(
        base.mesh_id,
        base.revision,
        "advance-before-adoption",
        "simulation-test",
        expected_overlay_catalog_revision=base_catalog.catalog_revision,
    )
    winner.stage(advanced_definition)
    winner.commit()

    stale_adoption_definition = ModelMeshDefinition(
        mesh_id=advanced_definition.mesh_id,
        registry=advanced_definition.registry,
        memberships=advanced_definition.memberships,
        cross_model_edges=(),
        invalidation_baseline=base_catalog,
        provenance=advanced_definition.provenance,
        metadata={"simulation_delta_digest": delta.delta_digest},
    )
    stale = store.begin(
        base.mesh_id,
        base.revision,
        "stale-simulation-adoption",
        "simulation-test",
        expected_overlay_catalog_revision=base_catalog.catalog_revision,
    )
    stale.stage(stale_adoption_definition)
    with pytest.raises(MeshTransactionConflictError, match="mesh head"):
        stale.commit()
    assert store.head(base.mesh_id) != delta.base_mesh_revision
