from __future__ import annotations

from pathlib import Path

import pytest
import researchguard.logic.mesh_evaluator as mesh_evaluator_module

from researchguard.logic.file_model_store import FileModelStore
from researchguard.logic.identity import EdgeId, ModelId, ModelRevision, QualifiedModelRef
from researchguard.logic.mesh_evaluator import (
    build_cross_model_contribution_ledger,
    evaluate_materialized_mesh,
)
from researchguard.logic.mesh_materialization import MeshMaterializationRequest, materialize_mesh
from researchguard.logic.mesh_scc import ModelDependencyGraph, compute_model_sccs
from researchguard.logic.mesh_store import FileModelMeshStore
from researchguard.logic.model_mesh import CrossModelEdge
from researchguard.logic.schema import SCHEMA_VERSION, STATE_IN, STATE_UNDECIDED

from .model_mesh_test_support import (
    build_definition,
    commit_model,
    committed_models,
    mesh_provenance,
    model_payload,
    model_ref,
    node_ref,
)


def open_mesh_store(root: Path, p0, definition):
    store = FileModelMeshStore(root, model_store=p0)
    transaction = store.begin(
        definition.mesh_id,
        None,
        "first-mesh",
        "evaluator-test",
        expected_overlay_catalog_revision=None,
    )
    transaction.stage(definition)
    transaction.commit()
    return store


def materialize(store, roots, *, profile="bounded", hop_limit=12):
    view = store.open_view("brain-main")
    result = materialize_mesh(
        view,
        MeshMaterializationRequest(
            roots=tuple(roots),
            direction="both",
            hop_limit=hop_limit,
            node_limit=1_000,
            edge_limit=2_000,
            model_limit=100,
            byte_limit=10_000_000,
            profile=profile,
        ),
    )
    return view, result


def claim_only_payload(model_id: str) -> dict:
    return {
        "model": {
            "id": model_id,
            "title": model_id,
            "root_claim": "claim-root",
            "schema_version": SCHEMA_VERSION,
        },
        "nodes": {"claim-root": {"type": "Claim", "text": f"Claim {model_id}"}},
        "edges": [],
        "acceptance": {},
        "hierarchy": {},
        "blocks": {
            "block-root": {
                "id": "block-root",
                "title": model_id,
                "root_claim": "claim-root",
                "member_nodes": ["claim-root"],
                "output_claims": ["claim-root"],
            }
        },
    }


def cross_edge(source, target, edge_id, edge_type="supports"):
    return CrossModelEdge(
        id=EdgeId(edge_id),
        source=source,
        target=target,
        type=edge_type,
        provenance=(mesh_provenance(edge_id),),
    )


def test_iterative_scc_handles_deep_cycle_without_recursion() -> None:
    nodes = tuple(
        QualifiedModelRef(ModelId(f"model-{index:04d}"), ModelRevision("revision-a"))
        for index in range(1_200)
    )
    edges = tuple((nodes[index], nodes[(index + 1) % len(nodes)]) for index in range(len(nodes)))
    analysis = compute_model_sccs(ModelDependencyGraph(nodes, edges))
    assert len(analysis.sccs) == 1
    assert analysis.sccs[0].cyclic
    assert analysis.sccs[0].status == "ungrounded-cycle"
    assert len(analysis.sccs[0].members) == 1_200


def test_cross_model_evaluation_keeps_p0_models_separate_and_uses_qualified_results(
    tmp_path,
) -> None:
    p0, snapshots = committed_models(tmp_path / "p0")
    store = open_mesh_store(tmp_path / "mesh", p0, build_definition(snapshots))
    view, materialized = materialize(store, (node_ref(snapshots[0], "evidence-one"),))
    overlay = evaluate_materialized_mesh(
        view,
        materialized,
        requested_claim_scope=(node_ref(snapshots[1], "claim-root"),),
        profile="bounded",
        depth_budget=2,
    )
    results = {item.node_ref: item for item in overlay.node_results}
    assert results[node_ref(snapshots[1], "claim-root")].state == STATE_IN
    assert len({item.node_ref.model_id for item in overlay.node_results}) == 2
    assert all(item.model_ref.revision for item in overlay.depth_bindings)
    assert overlay.profile == "bounded"
    assert not overlay.broad_claim_licensed
    assert "does not establish factual truth" in overlay.claim_boundary


def test_mesh_evaluation_uses_internal_native_depth_without_public_contract_bypass(
    tmp_path, monkeypatch
) -> None:
    calls: list[str] = []
    native_depth = mesh_evaluator_module._build_native_depth_analysis

    def recording_native_depth(model, **kwargs):
        calls.append(model.id)
        return native_depth(model, **kwargs)

    monkeypatch.setattr(
        mesh_evaluator_module,
        "_build_native_depth_analysis",
        recording_native_depth,
    )
    p0, snapshots = committed_models(tmp_path / "p0")
    store = open_mesh_store(tmp_path / "mesh", p0, build_definition(snapshots))
    view, materialized = materialize(store, (node_ref(snapshots[0], "evidence-one"),))

    overlay = evaluate_materialized_mesh(
        view,
        materialized,
        requested_claim_scope=(node_ref(snapshots[1], "claim-root"),),
        profile="bounded",
        depth_budget=2,
    )

    assert calls == [str(item.model_id) for item in overlay.selected_models]
    assert all(binding.depth_receipt_digest for binding in overlay.depth_bindings)


@pytest.mark.parametrize(
    ("duplicate_mode", "expected_contributions"),
    [
        ("exact", 1),
        ("same_group", 1),
        ("independent", 2),
    ],
)
def test_contribution_ledger_deduplicates_across_models_by_source_content_or_group(
    tmp_path, duplicate_mode, expected_contributions
) -> None:
    p0 = FileModelStore(tmp_path / "p0")
    payload_a = model_payload("model-a")
    payload_b = model_payload("model-b")
    if duplicate_mode == "exact":
        payload_b["nodes"]["evidence-one"]["text"] = payload_a["nodes"]["evidence-one"]["text"]
        payload_b["nodes"]["evidence-one"]["provenance"] = [
            dict(payload_a["nodes"]["evidence-one"]["provenance"][0])
        ]
    elif duplicate_mode == "same_group":
        payload_a["nodes"]["evidence-one"]["provenance"][0]["independence_group"] = "shared-group"
        payload_b["nodes"]["evidence-one"]["provenance"][0]["independence_group"] = "shared-group"
    snapshots = (
        commit_model(p0, "model-a", payload=payload_a),
        commit_model(p0, "model-b", payload=payload_b),
        commit_model(p0, "model-c", payload=model_payload("model-c")),
    )
    edges = (
        cross_edge(
            node_ref(snapshots[0], "evidence-one"),
            node_ref(snapshots[2], "claim-root"),
            "edge-a-c",
        ),
        cross_edge(
            node_ref(snapshots[1], "evidence-one"),
            node_ref(snapshots[2], "claim-root"),
            "edge-b-c",
        ),
    )
    definition = build_definition(snapshots, memberships=(), cross_edges=edges)
    store = open_mesh_store(tmp_path / "mesh", p0, definition)
    _view, materialized = materialize(
        store,
        (
            node_ref(snapshots[0], "evidence-one"),
            node_ref(snapshots[1], "evidence-one"),
        ),
    )
    ledger = build_cross_model_contribution_ledger(materialized)
    assert len(ledger) == expected_contributions
    if expected_contributions == 1:
        assert len(ledger[0].arrivals) == 2
        assert ledger[0].duplicate_arrival_count == 1


def test_pure_cross_model_support_cycle_cannot_mint_acceptance(tmp_path) -> None:
    p0 = FileModelStore(tmp_path / "p0")
    snapshots = (
        commit_model(p0, "model-a", payload=claim_only_payload("model-a")),
        commit_model(p0, "model-b", payload=claim_only_payload("model-b")),
    )
    edges = (
        cross_edge(
            node_ref(snapshots[0], "claim-root"),
            node_ref(snapshots[1], "claim-root"),
            "cycle-a-b",
        ),
        cross_edge(
            node_ref(snapshots[1], "claim-root"),
            node_ref(snapshots[0], "claim-root"),
            "cycle-b-a",
        ),
    )
    store = open_mesh_store(
        tmp_path / "mesh",
        p0,
        build_definition(snapshots, memberships=(), cross_edges=edges),
    )
    view, materialized = materialize(
        store,
        tuple(node_ref(item, "claim-root") for item in snapshots),
    )
    overlay = evaluate_materialized_mesh(
        view,
        materialized,
        requested_claim_scope=(node_ref(snapshots[0], "claim-root"),),
        profile="bounded",
        depth_budget=1,
    )
    assert all(item.state == STATE_UNDECIDED for item in overlay.node_results)
    assert any(item["status"] == "ungrounded-cycle" for item in overlay.model_sccs)
    assert any(item.startswith("ungrounded_support_cycle:") for item in overlay.gaps)
    assert overlay.contribution_ledger == ()


def test_mixed_support_attack_scc_is_deterministic_and_does_not_file_order_pass(tmp_path) -> None:
    p0 = FileModelStore(tmp_path / "p0")
    snapshots = (
        commit_model(p0, "model-a", payload=claim_only_payload("model-a")),
        commit_model(p0, "model-b", payload=claim_only_payload("model-b")),
    )
    edges = (
        cross_edge(
            node_ref(snapshots[0], "claim-root"),
            node_ref(snapshots[1], "claim-root"),
            "support-a-b",
            "supports",
        ),
        cross_edge(
            node_ref(snapshots[1], "claim-root"),
            node_ref(snapshots[0], "claim-root"),
            "attack-b-a",
            "attacks",
        ),
    )
    store = open_mesh_store(
        tmp_path / "mesh",
        p0,
        build_definition(snapshots, memberships=(), cross_edges=edges),
    )
    view, materialized = materialize(
        store, tuple(node_ref(item, "claim-root") for item in reversed(snapshots))
    )
    first = evaluate_materialized_mesh(
        view,
        materialized,
        requested_claim_scope=(node_ref(snapshots[0], "claim-root"),),
        profile="bounded",
        depth_budget=1,
    )
    second = evaluate_materialized_mesh(
        store.open_view("brain-main"),
        materialized,
        requested_claim_scope=(node_ref(snapshots[0], "claim-root"),),
        profile="bounded",
        depth_budget=1,
    )
    assert first.fingerprint == second.fingerprint
    assert not first.broad_claim_licensed


def test_partial_or_bounded_universe_never_broad_passes(tmp_path) -> None:
    p0, snapshots = committed_models(tmp_path / "p0")
    store = open_mesh_store(tmp_path / "mesh", p0, build_definition(snapshots))
    view, partial = materialize(
        store, (node_ref(snapshots[0], "evidence-one"),), hop_limit=0
    )
    overlay = evaluate_materialized_mesh(
        view,
        partial,
        requested_claim_scope=(node_ref(snapshots[0], "evidence-one"),),
        profile="broad",
        depth_budget=1,
    )
    assert overlay.completeness == "partial"
    assert overlay.truncated
    assert not overlay.broad_claim_licensed
    assert "materialization:hop_limit" in overlay.gaps


def test_complete_broad_universe_still_requires_every_native_depth_gate(tmp_path) -> None:
    p0, snapshots = committed_models(tmp_path / "p0")
    store = open_mesh_store(tmp_path / "mesh", p0, build_definition(snapshots))
    view, complete = materialize(
        store,
        (node_ref(snapshots[0], "evidence-one"),),
        profile="broad",
    )
    overlay = evaluate_materialized_mesh(
        view,
        complete,
        requested_claim_scope=(node_ref(snapshots[1], "claim-root"),),
        profile="broad",
        depth_budget=2,
    )
    assert complete.complete
    assert overlay.completeness == "complete"
    assert not overlay.broad_claim_licensed
    assert any(item.startswith("depth:") for item in overlay.gaps)


def test_production_overlay_can_be_catalog_registered_only_after_exact_evaluation(
    tmp_path,
) -> None:
    p0, snapshots = committed_models(tmp_path / "p0")
    store = open_mesh_store(tmp_path / "mesh", p0, build_definition(snapshots))
    view, materialized = materialize(store, (node_ref(snapshots[0], "evidence-one"),))
    overlay = evaluate_materialized_mesh(
        view,
        materialized,
        requested_claim_scope=(node_ref(snapshots[1], "claim-root"),),
        profile="bounded",
        depth_budget=1,
    )
    transaction = store.begin_catalog(
        materialized.mesh_id,
        materialized.mesh_revision,
        store.catalog_head(materialized.mesh_id, materialized.mesh_revision),
        "evaluated-overlay",
        "evaluator-test",
    )
    transaction.stage(overlay)
    transaction.commit()
    current = overlay.currentness(
        store.get("brain-main"),
        catalog_snapshot=store.get_catalog("brain-main", materialized.mesh_revision),
    )
    assert current.current
    assert not current.broad_current
