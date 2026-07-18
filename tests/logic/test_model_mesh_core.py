from __future__ import annotations

import copy

import pytest

from researchguard.logic.identity import (
    EdgeId,
    IdentityError,
    MeshId,
    MeshRevision,
    QualifiedModelRef,
    QualifiedNodeRef,
)
from researchguard.logic.mesh_index import (
    EVIDENCE_BY_KEY_SHARD,
    EVIDENCE_BY_NODE_SHARD,
    MESH_SHARD_KINDS,
    MeshIndexBundle,
    MeshIndexShard,
    MeshIndexView,
)
from researchguard.logic.mesh_receipts import MeshCommitReceipt, MeshReceiptError
from researchguard.logic.model_mesh import (
    CrossModelEdge,
    MeshIntegrityError,
    MeshMembership,
    MeshValidationError,
    ModelMeshDefinition,
    ModelMeshSnapshot,
    ModelRegistryEntry,
    OverlayCatalogPin,
    detect_model_head_drift,
    validate_definition_against_store,
)
from researchguard.logic.provenance import ProvenanceRecord, content_hash_for
from researchguard.logic.schema import (
    MESH_INDEX_SHARD_SCHEMA,
    MESH_SCHEMA_VERSION,
    MESH_SNAPSHOT_SCHEMA,
)

from .model_mesh_test_support import (
    FIXED_ACTOR,
    build_definition,
    commit_model,
    committed_models,
    compile_snapshot,
    mesh_provenance,
    model_payload,
    model_ref,
    node_ref,
    registry_entry,
)


def test_mesh_identities_and_qualified_model_refs_are_exact_and_revision_pinned() -> None:
    ref = QualifiedModelRef.from_dict({"model_id": "model-a", "revision": "revision-a"})
    assert ref.to_dict() == {"model_id": "model-a", "revision": "revision-a"}
    assert MeshId("brain-main").value == "brain-main"
    with pytest.raises(IdentityError, match="revision"):
        QualifiedModelRef.from_dict({"model_id": "model-a"})


def test_definition_validates_exact_p0_pins_and_explicit_cross_model_endpoints(tmp_path) -> None:
    store, snapshots = committed_models(tmp_path / "models")
    definition = build_definition(snapshots)
    resolved = validate_definition_against_store(definition, store)
    assert set(resolved) == {model_ref(snapshot) for snapshot in snapshots}

    missing = CrossModelEdge(
        id=EdgeId("cross-missing"),
        source=node_ref(snapshots[0], "missing-node"),
        target=node_ref(snapshots[1], "claim-root"),
        type="supports",
        provenance=(mesh_provenance("missing"),),
    )
    invalid = build_definition(snapshots, cross_edges=(missing,))
    with pytest.raises(MeshValidationError, match="does not exist"):
        validate_definition_against_store(invalid, store)

    same_model = CrossModelEdge(
        id=EdgeId("cross-is-actually-local"),
        source=node_ref(snapshots[0], "evidence-one"),
        target=node_ref(snapshots[0], "claim-root"),
        type="supports",
        provenance=(mesh_provenance("local"),),
    )
    invalid = build_definition(snapshots, cross_edges=(same_model,))
    with pytest.raises(MeshValidationError, match="P0 local edge"):
        validate_definition_against_store(invalid, store)


def test_cross_edges_require_non_ai_provenance_and_reject_duplicate_relations(tmp_path) -> None:
    _store, snapshots = committed_models(tmp_path / "models")
    ai = ProvenanceRecord(
        origin_kind="ai_generated",
        source_id="ai-output",
        content_hash=content_hash_for("suggestion"),
    )
    with pytest.raises(MeshValidationError, match="non-AI-only"):
        CrossModelEdge(
            id=EdgeId("ai-similarity"),
            source=node_ref(snapshots[0], "claim-root"),
            target=node_ref(snapshots[1], "claim-root"),
            type="contextualizes",
            provenance=(ai,),
        )

    first = CrossModelEdge(
        id=EdgeId("explicit-one"),
        source=node_ref(snapshots[0], "claim-root"),
        target=node_ref(snapshots[1], "claim-root"),
        type="contextualizes",
        provenance=(mesh_provenance("explicit"),),
    )
    duplicate = CrossModelEdge(
        id=EdgeId("explicit-two"),
        source=first.source,
        target=first.target,
        type=first.type,
        provenance=(mesh_provenance("explicit-again"),),
    )
    with pytest.raises(MeshValidationError, match="duplicate cross-model relation"):
        build_definition(snapshots, cross_edges=(first, duplicate))


def test_one_physical_node_can_join_many_logical_models_without_copied_authority(tmp_path) -> None:
    _store, snapshots = committed_models(
        tmp_path / "models", ("model-a", "model-b", "model-c")
    )
    owner = node_ref(snapshots[0], "claim-root")
    memberships = tuple(
        MeshMembership(
            owner=owner,
            logical_model=model_ref(snapshot),
            roles=("shared-claim",),
            role_metadata={"scope": str(snapshot.model_id)},
            provenance=(mesh_provenance(f"membership-{snapshot.model_id}"),),
        )
        for snapshot in snapshots[1:]
    )
    definition = build_definition(snapshots, memberships=memberships, cross_edges=())
    serialized = [item.to_dict() for item in definition.memberships]
    assert {item.logical_model for item in definition.memberships} == {
        model_ref(snapshots[1]),
        model_ref(snapshots[2]),
    }
    assert all("text" not in item["role_metadata"] for item in serialized)
    with pytest.raises(MeshValidationError, match="cannot redefine"):
        MeshMembership(
            owner=owner,
            logical_model=model_ref(snapshots[1]),
            role_metadata={"text": "copied authority"},
            provenance=(mesh_provenance("forbidden"),),
        )


def test_snapshot_and_all_exact_index_shards_are_deterministic_and_round_trip(tmp_path) -> None:
    _store, snapshots = committed_models(tmp_path / "models")
    definition = build_definition(snapshots)
    first, first_indexes = compile_snapshot(definition, snapshots)
    second, second_indexes = compile_snapshot(definition, snapshots)

    assert first.revision == second.revision
    assert first.content_digest == second.content_digest
    assert first.to_dict() == second.to_dict()
    assert ModelMeshSnapshot.from_dict(first.to_dict()) == first
    assert tuple(item.kind for item in first_indexes.shards) == tuple(sorted(MESH_SHARD_KINDS))
    assert all(item.partitions[0].partition == "all" for item in first.shard_sets)
    assert [item.digest for item in first_indexes.shards] == [
        item.digest for item in second_indexes.shards
    ]

    view = MeshIndexView(first, first_indexes)
    assert view.outgoing_edge_ids(node_ref(snapshots[0], "evidence-one")) == (
        EdgeId("cross-evidence-a-to-claim-b"),
    )
    assert view.members_of_model(model_ref(snapshots[1])) == (
        node_ref(snapshots[0], "claim-root"),
    )


def test_evidence_indexes_deduplicate_exact_source_content_and_group_across_models(tmp_path) -> None:
    _store, snapshots = committed_models(
        tmp_path / "models", duplicate_evidence=True
    )
    _mesh, indexes = compile_snapshot(build_definition(snapshots), snapshots)
    by_node = indexes.by_kind(EVIDENCE_BY_NODE_SHARD)
    by_key = indexes.by_kind(EVIDENCE_BY_KEY_SHARD)
    assert len(by_node.records) == 2
    assert len(by_key.records) == 1
    assert len(by_key.records[0]["node_refs"]) == 2


def test_corrupt_or_noncurrent_shard_and_snapshot_authority_fails_visibly(tmp_path) -> None:
    _store, snapshots = committed_models(tmp_path / "models")
    mesh, indexes = compile_snapshot(build_definition(snapshots), snapshots)
    raw = indexes.shards[0].to_dict()
    raw["digest"] = "sha256:" + "0" * 64
    with pytest.raises(MeshIntegrityError, match="digest mismatch"):
        MeshIndexShard.from_dict(raw)

    raw = mesh.to_dict()
    raw["artifact_schema"] = "researchguard.logic.retired-model-mesh-snapshot.v0"
    with pytest.raises(Exception, match="unsupported"):
        ModelMeshSnapshot.from_dict(raw)

    missing = list(indexes.shards[1:])
    with pytest.raises(MeshIntegrityError, match="every exact shard kind"):
        MeshIndexBundle(indexes.content_basis_digest, tuple(missing))


def test_mesh_commit_receipt_is_content_addressed_strict_and_round_trips(tmp_path) -> None:
    _store, snapshots = committed_models(tmp_path / "models")
    mesh, indexes = compile_snapshot(build_definition(snapshots), snapshots)
    child_pin = OverlayCatalogPin(
        mesh_id=mesh.mesh_id,
        mesh_revision=mesh.revision,
        catalog_revision="catalog-genesis-a",
        catalog_content_digest="sha256:" + "a" * 64,
    )
    receipt = MeshCommitReceipt.create(
        transaction_id="mesh-tx-a",
        mesh_id=mesh.mesh_id,
        revision=mesh.revision,
        parent_revision=None,
        content_digest=mesh.content_digest,
        registry_digest=mesh.registry_digest,
        shard_digests=tuple((item.kind, item.digest) for item in indexes.shards),
        model_pins=tuple(item.model_ref for item in mesh.registry),
        parent_catalog_baseline=None,
        child_catalog_pin=child_pin,
        invalidation_receipt_id=None,
        idempotency_key="first-mesh",
        actor=FIXED_ACTOR,
        committed_at="2026-07-14T12:00:00Z",
        package_version="0.17.4",
        tool_fingerprint="sha256:" + "b" * 64,
    )
    assert MeshCommitReceipt.from_dict(receipt.to_dict()) == receipt
    tampered = copy.deepcopy(receipt.to_dict())
    tampered["actor"] = "different-actor"
    with pytest.raises(MeshReceiptError, match="ID mismatch"):
        MeshCommitReceipt.from_dict(tampered)


def test_external_p0_head_drift_is_reported_without_repinning_mesh(tmp_path) -> None:
    store, snapshots = committed_models(tmp_path / "models")
    mesh, _indexes = compile_snapshot(build_definition(snapshots), snapshots)
    old_ref = model_ref(snapshots[0])
    updated = commit_model(
        store,
        str(snapshots[0].model_id),
        payload=model_payload(str(snapshots[0].model_id), claim_text="new head"),
        expected_revision=snapshots[0].revision,
        idempotency_key="advance-model-a",
    )
    drift = detect_model_head_drift(mesh, store)
    assert len(drift) == 1
    assert drift[0].registered == old_ref
    assert drift[0].current_head == updated.revision
    assert mesh.registry[0].model_ref == old_ref


def test_current_mesh_schema_is_explicit_and_distinct_from_artifact_schemas() -> None:
    assert MESH_SCHEMA_VERSION == "researchguard.logic.model-mesh.v1"
    assert MESH_SNAPSHOT_SCHEMA != MESH_SCHEMA_VERSION
    assert MESH_INDEX_SHARD_SCHEMA != MESH_SNAPSHOT_SCHEMA
