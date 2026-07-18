from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from researchguard.logic.mesh_evaluator import evaluate_materialized_mesh
from researchguard.logic.mesh_materialization import MeshMaterializationRequest, materialize_mesh
from researchguard.logic.mesh_receipts import MeshScaleReceipt
from researchguard.logic.model_store import canonical_digest

from .model_mesh_scale_support import (
    PeakRssSampler,
    build_scale_store,
    environment_evidence,
    load_scale_recipe,
    scale_owner_input_digest,
    scale_recipe_digest,
    write_receipt,
)
from .model_mesh_test_support import model_ref, node_ref


RECIPE_PATH = Path(__file__).parent / "fixtures" / "model_mesh_scale" / "profile-v1.json"
REPO_ROOT = Path(__file__).resolve().parents[2]
RECEIPT_PATH = Path(".local/verification/model-mesh-scale-receipt.json")


def test_reference_model_mesh_scale_owner(tmp_path) -> None:
    recipe = load_scale_recipe(RECIPE_PATH)
    owner_input_digest = scale_owner_input_digest(REPO_ROOT)
    if RECEIPT_PATH.is_file():
        try:
            current = MeshScaleReceipt.from_dict(
                json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
            )
        except Exception:
            current = None
        if (
            current is not None
            and current.overall_passed
            and current.fixture.get("profile_id") == recipe["profile_id"]
            and current.fixture.get("owner_input_digest") == owner_input_digest
            and current.environment.get("python_executable") == sys.executable
            and current.environment.get("mesh_schema")
            == __import__("researchguard.logic.schema", fromlist=["MESH_SCHEMA_VERSION"]).MESH_SCHEMA_VERSION
        ):
            assert current.fixture["qualified_node_count"] == int(
                recipe["expected_qualified_nodes"]
            )
            assert current.fixture["combined_edge_count"] == int(
                recipe["expected_combined_edges"]
            )
            return
    _p0, snapshots, store, commit_receipt = build_scale_store(tmp_path, recipe)
    mesh = store.get("brain-scale-reference")
    expected_nodes = int(recipe["expected_qualified_nodes"])
    expected_edges = int(recipe["expected_combined_edges"])
    actual_nodes = sum(len(snapshot.model_payload["nodes"]) for snapshot in snapshots)
    actual_local_edges = sum(len(snapshot.model_payload["edges"]) for snapshot in snapshots)
    actual_edges = actual_local_edges + len(mesh.cross_model_edges)
    assert len(mesh.registry) == int(recipe["model_count"])
    assert actual_nodes == expected_nodes
    assert actual_edges == expected_edges

    cold_start = time.perf_counter()
    cold_view = store.open_view("brain-scale-reference", mesh.revision)
    membership_result = cold_view.memberships_for_node(node_ref(snapshots[0], "claim-root"))
    cold_seconds = time.perf_counter() - cold_start
    assert membership_result
    assert cold_view.model_read_count == 0

    capped_request = MeshMaterializationRequest(
        roots=(node_ref(snapshots[0], "evidence-000"),),
        direction="both",
        hop_limit=250,
        node_limit=int(recipe["capped_materialization_nodes"]),
        edge_limit=2_000,
        model_limit=int(recipe["model_count"]),
        byte_limit=64 * 1024 * 1024,
        profile="bounded",
    )
    capped_start = time.perf_counter()
    capped = materialize_mesh(store.open_view("brain-scale-reference"), capped_request)
    capped_seconds = time.perf_counter() - capped_start
    assert capped.budgets.nodes == int(recipe["capped_materialization_nodes"])
    assert "node_limit" in capped.truncation_reasons
    assert capped.model_read_count < int(recipe["model_count"])

    full_roots = tuple(node_ref(snapshot, "evidence-000") for snapshot in snapshots)
    full_request = MeshMaterializationRequest(
        roots=full_roots,
        direction="both",
        hop_limit=2,
        node_limit=expected_nodes,
        edge_limit=expected_edges,
        model_limit=int(recipe["model_count"]),
        byte_limit=256 * 1024 * 1024,
        profile="bounded",
    )
    full_view = store.open_view("brain-scale-reference")
    full_materialization_start = time.perf_counter()
    full = materialize_mesh(full_view, full_request)
    full_materialization_seconds = time.perf_counter() - full_materialization_start
    assert full.complete
    assert full.budgets.nodes == expected_nodes
    assert full.budgets.edges == expected_edges
    assert full.model_read_count == int(recipe["model_count"])

    with PeakRssSampler() as memory:
        evaluation_start = time.perf_counter()
        overlay = evaluate_materialized_mesh(
            full_view,
            full,
            requested_claim_scope=tuple(
                node_ref(snapshot, "claim-root") for snapshot in snapshots
            ),
            profile="bounded",
            max_scc_iterations=5,
            depth_budget=1,
        )
        evaluation_seconds = time.perf_counter() - evaluation_start
    assert len(overlay.selected_models) == int(recipe["model_count"])
    assert len(overlay.node_results) == expected_nodes
    assert overlay.model_sccs
    assert not overlay.broad_claim_licensed

    mib = 1024 * 1024
    additional_peak_mib = memory.additional_peak_bytes / mib
    thresholds = recipe["thresholds"]
    threshold_results = (
        {
            "name": "cold_open_and_membership_lookup_seconds",
            "limit": float(thresholds["cold_open_and_membership_lookup_seconds"]),
            "observed": cold_seconds,
            "unit": "seconds",
            "passed": cold_seconds
            <= float(thresholds["cold_open_and_membership_lookup_seconds"]),
        },
        {
            "name": "capped_materialization_seconds",
            "limit": float(thresholds["capped_materialization_seconds"]),
            "observed": capped_seconds,
            "unit": "seconds",
            "passed": capped_seconds
            <= float(thresholds["capped_materialization_seconds"]),
        },
        {
            "name": "scc_and_full_evaluation_seconds",
            "limit": float(thresholds["scc_and_full_evaluation_seconds"]),
            "observed": evaluation_seconds,
            "unit": "seconds",
            "passed": evaluation_seconds
            <= float(thresholds["scc_and_full_evaluation_seconds"]),
        },
        {
            "name": "additional_peak_memory_mib",
            "limit": float(thresholds["additional_peak_memory_mib"]),
            "observed": additional_peak_mib,
            "unit": "MiB",
            "passed": additional_peak_mib
            <= float(thresholds["additional_peak_memory_mib"]),
        },
    )
    receipt = MeshScaleReceipt.create(
        environment=environment_evidence(),
        fixture={
            "profile_id": recipe["profile_id"],
            "owner_input_digest": owner_input_digest,
            "recipe_digest": scale_recipe_digest(recipe),
            "mesh_id": str(mesh.mesh_id),
            "mesh_revision": str(mesh.revision),
            "mesh_content_digest": mesh.content_digest,
            "commit_receipt_id": str(commit_receipt.receipt_id),
            "model_count": len(mesh.registry),
            "qualified_node_count": actual_nodes,
            "local_edge_count": actual_local_edges,
            "cross_edge_count": len(mesh.cross_model_edges),
            "combined_edge_count": actual_edges,
            "membership_count": len(mesh.memberships),
            "authoritative_universe_fingerprint": full.authoritative_universe_fingerprint,
            "evaluation_fingerprint": overlay.fingerprint,
            "fixture_digest": canonical_digest(
                {
                    "recipe": recipe,
                    "mesh_content_digest": mesh.content_digest,
                    "model_content_digests": [item.content_digest for item in mesh.registry],
                }
            ),
        },
        io_counts={
            "cold_membership_lookup_model_reads": cold_view.model_read_count,
            "capped_materialization_model_reads": capped.model_read_count,
            "capped_materialization_nodes": capped.budgets.nodes,
            "full_materialization_model_reads": full.model_read_count,
            "full_materialization_nodes": full.budgets.nodes,
        },
        timing={
            "cold_open_and_membership_lookup_seconds": cold_seconds,
            "capped_materialization_seconds": capped_seconds,
            "full_materialization_seconds": full_materialization_seconds,
            "scc_and_full_evaluation_seconds": evaluation_seconds,
        },
        memory={
            "baseline_process_rss_bytes": memory.baseline,
            "peak_process_rss_bytes": memory.peak,
            "additional_peak_process_rss_bytes": memory.additional_peak_bytes,
            "additional_peak_process_rss_mib": additional_peak_mib,
            "sampling_interval_seconds": memory.interval_seconds,
        },
        thresholds=threshold_results,
        overall_passed=all(item["passed"] for item in threshold_results),
        claim_boundary=(
            "This receipt measures the declared local reference profile and structural "
            "LogicGuard execution; it does not establish factual truth or performance "
            "on undeclared hardware, fixtures, or workloads."
        ),
    )
    write_receipt(RECEIPT_PATH, receipt.to_dict())
    reloaded = MeshScaleReceipt.from_dict(json.loads(RECEIPT_PATH.read_text(encoding="utf-8")))
    assert reloaded == receipt
    assert receipt.overall_passed, receipt.to_dict()
