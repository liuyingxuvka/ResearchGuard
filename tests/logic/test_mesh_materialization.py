from __future__ import annotations

import pytest

from researchguard.logic.mesh_materialization import (
    MeshMaterializationError,
    MeshMaterializationRequest,
    materialize_mesh,
)
from researchguard.logic.mesh_store import FileModelMeshStore

from .model_mesh_test_support import (
    build_definition,
    committed_models,
    model_ref,
    node_ref,
)


def prepared_store(tmp_path, model_ids=("model-a", "model-b")):
    p0, snapshots = committed_models(tmp_path / "p0", model_ids)
    store = FileModelMeshStore(tmp_path / "mesh", model_store=p0)
    transaction = store.begin(
        "brain-main",
        None,
        "first-mesh",
        "materialization-test",
        expected_overlay_catalog_revision=None,
    )
    transaction.stage(build_definition(snapshots))
    transaction.commit()
    return store, snapshots


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


def test_repeated_materialization_is_deterministic_and_binds_exact_universe(tmp_path) -> None:
    store, snapshots = prepared_store(tmp_path)
    root = node_ref(snapshots[0], "evidence-one")
    first = materialize_mesh(store.open_view("brain-main"), request(root))
    second = materialize_mesh(store.open_view("brain-main"), request(root))

    assert first.complete
    assert first.to_dict() == second.to_dict()
    assert first.materialization_fingerprint == second.materialization_fingerprint
    assert first.authoritative_universe_fingerprint == second.authoritative_universe_fingerprint
    assert set(first.model_pins) == {model_ref(item) for item in snapshots}
    assert first.frontier == ()


def test_hop_limit_is_visible_frontier_and_never_complete(tmp_path) -> None:
    store, snapshots = prepared_store(tmp_path)
    result = materialize_mesh(
        store.open_view("brain-main"),
        request(node_ref(snapshots[0], "evidence-one"), hop_limit=0),
    )
    assert not result.complete
    assert result.truncation_reasons == ("hop_limit",)
    assert result.frontier
    assert all(item.reason == "hop_limit" for item in result.frontier)
    assert result.budgets.nodes == 1


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"node_limit": 1}, "node_limit"),
        ({"edge_limit": 1}, "edge_limit"),
        ({"model_limit": 1}, "model_limit"),
        ({"byte_limit": 900}, "byte_limit"),
    ],
)
def test_every_budget_is_a_visible_terminal_boundary(tmp_path, overrides, reason) -> None:
    store, snapshots = prepared_store(tmp_path)
    result = materialize_mesh(
        store.open_view("brain-main"),
        request(node_ref(snapshots[0], "evidence-one"), **overrides),
    )
    assert not result.complete
    assert reason in result.truncation_reasons
    assert result.frontier


def test_model_filter_excludes_relation_explicitly_without_loading_filtered_model(tmp_path) -> None:
    store, snapshots = prepared_store(tmp_path)
    only_a = (model_ref(snapshots[0]),)
    result = materialize_mesh(
        store.open_view("brain-main"),
        request(
            node_ref(snapshots[0], "evidence-one"),
            model_filter=only_a,
        ),
    )
    assert result.complete
    assert result.model_pins == only_a
    assert result.model_read_count == 1
    assert any(item.reason == "model_filter" for item in result.excluded_relations)


def test_unrelated_registered_model_snapshot_is_never_read(tmp_path) -> None:
    store, snapshots = prepared_store(
        tmp_path, ("model-a", "model-b", "model-c")
    )
    result = materialize_mesh(
        store.open_view("brain-main"),
        request(node_ref(snapshots[2], "claim-root")),
    )
    assert result.complete
    assert result.model_pins == (model_ref(snapshots[2]),)
    assert result.model_read_count == 1
    assert all(item.ref.model_id == snapshots[2].model_id for item in result.nodes)


def test_edge_kind_filter_is_declared_exclusion_and_broad_profile_forbids_hidden_filter(
    tmp_path,
) -> None:
    store, snapshots = prepared_store(tmp_path)
    result = materialize_mesh(
        store.open_view("brain-main"),
        request(
            node_ref(snapshots[0], "evidence-one"),
            allowed_edge_kinds=("attacks",),
        ),
    )
    assert result.complete
    assert result.budgets.edges == 0
    assert result.excluded_relations
    with pytest.raises(MeshMaterializationError, match="broad materialization cannot hide"):
        request(
            node_ref(snapshots[0], "evidence-one"),
            allowed_edge_kinds=("supports",),
            profile="broad",
        )


def test_incoming_and_outgoing_direction_select_different_declared_universes(tmp_path) -> None:
    store, snapshots = prepared_store(tmp_path)
    root = node_ref(snapshots[0], "evidence-one")
    incoming = materialize_mesh(
        store.open_view("brain-main"), request(root, direction="incoming")
    )
    outgoing = materialize_mesh(
        store.open_view("brain-main"), request(root, direction="outgoing")
    )
    assert incoming.budgets.nodes == 1
    assert outgoing.budgets.nodes > incoming.budgets.nodes
    assert incoming.authoritative_universe_fingerprint != outgoing.authoritative_universe_fingerprint


def test_unregistered_or_budget_excluded_root_fails_instead_of_widening(tmp_path) -> None:
    store, snapshots = prepared_store(tmp_path)
    missing = type(node_ref(snapshots[0], "claim-root"))(
        snapshots[0].model_id,
        snapshots[0].revision,
        "missing-root",
    )
    with pytest.raises(MeshMaterializationError, match="root cannot fit"):
        materialize_mesh(store.open_view("brain-main"), request(missing))
    with pytest.raises(MeshMaterializationError, match="excluded by model_filter"):
        materialize_mesh(
            store.open_view("brain-main"),
            request(
                node_ref(snapshots[0], "claim-root"),
                model_filter=(model_ref(snapshots[1]),),
            ),
        )


def test_broad_request_can_complete_only_when_no_frontier_or_unresolved_reference(tmp_path) -> None:
    store, snapshots = prepared_store(tmp_path)
    broad = materialize_mesh(
        store.open_view("brain-main"),
        request(node_ref(snapshots[0], "evidence-one"), profile="broad"),
    )
    assert broad.request.profile == "broad"
    assert broad.complete
    assert not broad.frontier
    assert not broad.unresolved_references
