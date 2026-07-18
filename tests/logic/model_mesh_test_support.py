from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

from researchguard.logic.file_model_store import FileModelStore
from researchguard.logic.identity import EdgeId, ModelId, QualifiedModelRef, QualifiedNodeRef
from researchguard.logic.mesh_index import MeshIndexBundle, compile_mesh_indexes
from researchguard.logic.mesh_overlay import (
    MeshDependencyKey,
    MeshEvaluationOverlay,
    MeshNodeResult,
    OverlayDependencyBinding,
)
from researchguard.logic.model_mesh import (
    CrossModelEdge,
    MeshMembership,
    ModelMeshDefinition,
    ModelMeshSnapshot,
    ModelRegistryEntry,
)
from researchguard.logic.model_store import ModelSnapshot
from researchguard.logic.model_store import canonical_digest
from researchguard.logic.provenance import ProvenanceRecord, content_hash_for
from researchguard.logic.schema import SCHEMA_VERSION


FIXED_TIME = "2026-07-14T12:00:00Z"
FIXED_ACTOR = "model-mesh-test"


def model_payload(
    model_id: str,
    *,
    claim_text: str | None = None,
    evidence_source: str | None = None,
    evidence_content: str | None = None,
) -> dict:
    source_id = evidence_source or f"source-{model_id}"
    content = evidence_content or f"observed-{model_id}"
    return {
        "model": {
            "id": model_id,
            "title": f"Model {model_id}",
            "root_claim": "claim-root",
            "schema_version": SCHEMA_VERSION,
        },
        "nodes": {
            "claim-root": {
                "type": "Claim",
                "text": claim_text or f"Conclusion for {model_id}",
            },
            "evidence-one": {
                "type": "Evidence",
                "text": content,
                "provenance": [
                    {
                        "origin_kind": "test_result",
                        "source_id": source_id,
                        "content_hash": content_hash_for(content),
                        "observed_at": FIXED_TIME,
                    }
                ],
            },
            "warrant-one": {
                "type": "Warrant",
                "text": f"Evidence licenses {model_id}",
            },
        },
        "edges": [
            {
                "id": "edge-evidence-root",
                "source": "evidence-one",
                "target": "claim-root",
                "type": "supports",
            },
            {
                "id": "edge-warrant-root",
                "source": "warrant-one",
                "target": "claim-root",
                "type": "supports",
            },
        ],
        "acceptance": {},
        "hierarchy": {},
        "blocks": {
            "block-root": {
                "id": "block-root",
                "title": f"Card {model_id}",
                "root_claim": "claim-root",
                "member_nodes": ["claim-root", "evidence-one", "warrant-one"],
                "input_nodes": ["evidence-one"],
                "internal_nodes": ["warrant-one"],
                "output_claims": ["claim-root"],
            }
        },
    }


def commit_model(
    store: FileModelStore,
    model_id: str,
    *,
    payload: dict | None = None,
    expected_revision=None,
    idempotency_key: str | None = None,
) -> ModelSnapshot:
    transaction = store.begin(
        model_id,
        expected_revision,
        idempotency_key or f"commit-{model_id}-{expected_revision or 'first'}",
        FIXED_ACTOR,
    )
    transaction.stage(payload or model_payload(model_id))
    transaction.commit()
    return store.get(model_id)


def committed_models(
    root: Path,
    model_ids: Iterable[str] = ("model-a", "model-b"),
    *,
    duplicate_evidence: bool = False,
) -> tuple[FileModelStore, tuple[ModelSnapshot, ...]]:
    store = FileModelStore(root)
    snapshots = []
    for model_id in model_ids:
        payload = model_payload(
            model_id,
            evidence_source="shared-source" if duplicate_evidence else None,
            evidence_content="same observation" if duplicate_evidence else None,
        )
        snapshots.append(commit_model(store, model_id, payload=payload))
    return store, tuple(snapshots)


def model_ref(snapshot: ModelSnapshot) -> QualifiedModelRef:
    return QualifiedModelRef(snapshot.model_id, snapshot.revision)


def node_ref(snapshot: ModelSnapshot, node_id: str) -> QualifiedNodeRef:
    return QualifiedNodeRef(snapshot.model_id, snapshot.revision, node_id)


def registry_entry(snapshot: ModelSnapshot) -> ModelRegistryEntry:
    return ModelRegistryEntry(
        model_ref=model_ref(snapshot),
        content_digest=snapshot.content_digest,
        snapshot_artifact_schema=snapshot.artifact_schema,
        store_schema_version=snapshot.store_schema_version,
    )


def mesh_provenance(label: str = "mesh-declaration") -> ProvenanceRecord:
    return ProvenanceRecord(
        origin_kind="human_observation",
        source_id="model-mesh-test-contract",
        content_hash=content_hash_for(label),
        observed_at=FIXED_TIME,
        actor=FIXED_ACTOR,
    )


def build_definition(
    snapshots: Iterable[ModelSnapshot],
    *,
    mesh_id: str = "brain-main",
    memberships: Iterable[MeshMembership] | None = None,
    cross_edges: Iterable[CrossModelEdge] | None = None,
) -> ModelMeshDefinition:
    models = tuple(snapshots)
    if len(models) < 2 and (memberships is None or cross_edges is None):
        raise ValueError("the default mesh recipe requires at least two snapshots")
    if memberships is None:
        memberships = (
            MeshMembership(
                owner=node_ref(models[0], "claim-root"),
                logical_model=model_ref(models[1]),
                roles=("shared-claim",),
                role_metadata={"scope": "cross-model"},
                provenance=(mesh_provenance("membership"),),
            ),
        )
    if cross_edges is None:
        cross_edges = (
            CrossModelEdge(
                id=EdgeId("cross-evidence-a-to-claim-b"),
                source=node_ref(models[0], "evidence-one"),
                target=node_ref(models[1], "claim-root"),
                type="supports",
                explanation="Explicit cross-model test relation",
                provenance=(mesh_provenance("cross-edge"),),
            ),
        )
    return ModelMeshDefinition(
        mesh_id=mesh_id,
        registry=tuple(registry_entry(snapshot) for snapshot in models),
        memberships=tuple(memberships),
        cross_model_edges=tuple(cross_edges),
        provenance=(mesh_provenance("mesh"),),
        metadata={"purpose": "test"},
    )


def compile_snapshot(
    definition: ModelMeshDefinition,
    snapshots: Iterable[ModelSnapshot],
    *,
    parent_revision=None,
) -> tuple[ModelMeshSnapshot, MeshIndexBundle]:
    snapshot_map: Mapping[QualifiedModelRef, ModelSnapshot] = {
        model_ref(snapshot): snapshot for snapshot in snapshots
    }
    indexes = compile_mesh_indexes(definition, model_snapshots=snapshot_map)
    mesh_snapshot = ModelMeshSnapshot.create(
        definition,
        parent_revision=parent_revision,
        shard_sets=indexes.shard_sets,
        created_at=FIXED_TIME,
        created_by=FIXED_ACTOR,
    )
    return mesh_snapshot, indexes


def build_overlay(
    mesh_snapshot: ModelMeshSnapshot,
    *,
    authority: str = "production",
    profile: str = "bounded",
    selected_index: int = 0,
) -> MeshEvaluationOverlay:
    selected = mesh_snapshot.registry[selected_index]
    claim_ref = QualifiedNodeRef(
        selected.model_ref.model_id,
        selected.model_ref.revision,
        "claim-root",
    )
    dependency_keys = (
        MeshDependencyKey.create(
            "model_pin",
            {
                "model_ref": selected.model_ref.to_dict(),
                "content_digest": selected.content_digest,
            },
        ),
        MeshDependencyKey.create("scope", {"node_ref": claim_ref.to_dict()}),
        MeshDependencyKey.create("profile", {"profile": profile}),
    )
    materialization_fingerprint = canonical_digest(
        {
            "mesh_revision": str(mesh_snapshot.revision),
            "roots": [claim_ref.to_dict()],
            "profile": profile,
        }
    )
    binding = OverlayDependencyBinding.create(
        mesh_id=mesh_snapshot.mesh_id,
        mesh_revision=mesh_snapshot.revision,
        mesh_content_digest=mesh_snapshot.content_digest,
        materialization_fingerprint=materialization_fingerprint,
        model_refs=(selected.model_ref,),
        node_refs=(claim_ref,),
        membership_keys=(),
        edge_ids=(),
        contribution_keys=(),
        independence_groups=(),
        evaluator_fingerprint="sha256:" + "e" * 64,
        simulator_fingerprint="sha256:" + "f" * 64,
        requested_claim_scope=(claim_ref,),
        profile=profile,
        dependency_keys=dependency_keys,
    )
    return MeshEvaluationOverlay(
        mesh_id=mesh_snapshot.mesh_id,
        mesh_revision=mesh_snapshot.revision,
        mesh_content_digest=mesh_snapshot.content_digest,
        materialization_fingerprint=materialization_fingerprint,
        authoritative_universe_fingerprint=canonical_digest(
            {"selected_models": [selected.model_ref.to_dict()]}
        ),
        requested_claim_scope=(claim_ref,),
        selected_models=(selected.model_ref,),
        profile=profile,
        completeness="complete",
        truncated=False,
        node_results=(MeshNodeResult(claim_ref, "IN", 1.0),),
        block_results=(),
        model_sccs=(),
        cycles=(),
        contribution_ledger=(),
        depth_bindings=(),
        unresolved_references=(),
        gaps=(),
        warnings=(),
        dependency_binding=binding,
        evaluator_fingerprint=binding.evaluator_fingerprint,
        simulator_fingerprint=binding.simulator_fingerprint,
        package_version="0.17.4",
        authority=authority,
        broad_claim_licensed=False,
    )
