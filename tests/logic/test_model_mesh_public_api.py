from __future__ import annotations

import researchguard.logic


def test_model_mesh_current_public_api_is_exported() -> None:
    assert {
        "MESH_SCHEMA_VERSION",
        "MESH_SNAPSHOT_SCHEMA",
        "MESH_INDEX_SHARD_SCHEMA",
        "MeshId",
        "MeshRevision",
        "MeshTransactionId",
        "MeshReceiptId",
        "MeshEvaluationId",
        "OverlayCatalogRevision",
        "QualifiedModelRef",
        "ModelRegistryEntry",
        "MeshMembership",
        "CrossModelEdge",
        "ModelMeshDefinition",
        "ModelMeshSnapshot",
        "OverlayCatalogPin",
        "MeshIndexShard",
        "MeshIndexBundle",
        "MeshIndexView",
        "compile_mesh_indexes",
        "OverlayDependencyBinding",
        "MeshEvaluationOverlay",
        "MeshCommitReceipt",
        "MeshInvalidationReceipt",
        "MeshSimulationReceipt",
        "FileModelMeshStore",
        "ModelMeshStore",
        "ModelMeshTransaction",
        "OverlayCatalogSnapshot",
        "OverlayCatalogTransaction",
        "OverlayDependencyShard",
        "compute_overlay_invalidation",
        "MeshMaterializationRequest",
        "MaterializedMesh",
        "materialize_mesh",
        "ModelSccAnalysis",
        "compute_model_sccs",
        "evaluate_materialized_mesh",
        "MeshValidationError",
        "MeshIntegrityError",
    } <= set(researchguard.logic.__all__)


def test_product_runtime_model_mesh_is_not_flowguard_workflow_modelmesh() -> None:
    assert researchguard.logic.ModelMeshSnapshot.__module__ == "researchguard.logic.model_mesh"
    assert "flowguard" not in researchguard.logic.ModelMeshSnapshot.__module__
    assert "does not establish factual truth" in researchguard.logic.MESH_STRUCTURAL_CLAIM_BOUNDARY
