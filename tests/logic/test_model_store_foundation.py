from __future__ import annotations

import json

import pytest

from researchguard.logic.evaluation_overlay import evaluate_snapshot
from researchguard.logic.file_model_store import FileModelStore
from researchguard.logic.identity import (
    IdentityError,
    ModelId,
    ModelRevision,
    NodeId,
    QualifiedNodeRef,
    decode_path_segment,
    encode_path_segment,
)
from researchguard.logic.model_store import (
    ModelSnapshot,
    StoreCorruptionError,
    StoreSchemaError,
    TombstonedModelError,
)
from researchguard.logic.provenance import (
    OriginKind,
    ProvenanceError,
    ProvenanceRecord,
    content_hash_for,
    normalize_duplicate_independence,
    validate_evidence_provenance,
)
from researchguard.logic.receipts import utc_now
from researchguard.logic.schema import MANIFEST_SCHEMA, SCHEMA_VERSION
from researchguard.logic.store_validation import DurableValidationError, validate_snapshot


def valid_model_payload(model_id: str = "model-alpha", *, text: str = "Conclusion") -> dict:
    source_hash = content_hash_for("observed source")
    return {
        "model": {
            "id": model_id,
            "title": "Alpha",
            "root_claim": "claim-root",
            "schema_version": SCHEMA_VERSION,
        },
        "nodes": {
            "claim-root": {"type": "Claim", "text": text},
            "evidence-one": {
                "type": "Evidence",
                "text": "Observed result",
                "state": "IN",
                "provenance": [
                    {
                        "origin_kind": "test_result",
                        "source_id": "test-suite-alpha",
                        "content_hash": source_hash,
                        "observed_at": "2026-07-14T12:00:00Z",
                    }
                ],
            },
            "warrant-one": {"type": "Warrant", "text": "Result licenses claim"},
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
            "block-alpha": {
                "id": "block-alpha",
                "title": "Alpha card",
                "root_claim": "claim-root",
                "member_nodes": ["claim-root", "evidence-one", "warrant-one"],
                "input_nodes": ["evidence-one"],
                "internal_nodes": ["warrant-one"],
                "output_claims": ["claim-root"],
                "acceptance_conditions": {},
            }
        },
    }


def snapshot_for(payload: dict, parent: ModelRevision | None = None) -> ModelSnapshot:
    return ModelSnapshot.create(
        payload,
        parent_revision=parent,
        created_at="2026-07-14T12:00:00Z",
        created_by="test-actor",
    )


def test_identity_and_qualified_reference_round_trip_is_exact() -> None:
    model_id = ModelId("Model:Alpha-01")
    revision = ModelRevision("rev-a1")
    reference = QualifiedNodeRef(model_id, revision, NodeId("Claim.Root"))

    assert QualifiedNodeRef.from_dict(reference.to_dict()) == reference
    encoded = encode_path_segment(model_id)
    assert decode_path_segment(encoded) == str(model_id)


@pytest.mark.parametrize(
    "unsafe",
    ["../escape", "folder/node", "folder\\node", "C:\\absolute", "has\ncontrol", "two..dots"],
)
def test_unsafe_identity_is_rejected(unsafe: str) -> None:
    with pytest.raises(IdentityError):
        ModelId(unsafe)


def test_floating_qualified_reference_is_rejected() -> None:
    with pytest.raises(IdentityError, match="revision"):
        QualifiedNodeRef.from_dict({"model_id": "model-alpha", "node_id": "claim-root"})


def test_typed_provenance_blocks_ai_only_evidence_and_normalizes_duplicates() -> None:
    digest = content_hash_for("same source")
    ai = ProvenanceRecord(
        origin_kind=OriginKind.AI_GENERATED,
        source_id="model-output",
        content_hash=digest,
    )
    with pytest.raises(ProvenanceError, match="non-ai_generated"):
        validate_evidence_provenance("evidence-ai", [ai])

    first = ProvenanceRecord(
        origin_kind="external_source",
        source_id="source-alpha",
        content_hash=digest,
        independence_group="ind-first",
    )
    second = ProvenanceRecord(
        origin_kind="external_source",
        source_id="source-alpha",
        content_hash=digest,
        independence_group="ind-second",
    )
    normalized = normalize_duplicate_independence([first, second])
    assert normalized[0].independence_group == normalized[1].independence_group
    assert validate_evidence_provenance("evidence-ok", [first]) == (first,)


def test_snapshot_normalizes_duplicate_source_independence_across_nodes() -> None:
    payload = valid_model_payload()
    duplicate = dict(payload["nodes"]["evidence-one"])
    duplicate["text"] = "Same source reused"
    duplicate["provenance"] = [dict(duplicate["provenance"][0])]
    payload["nodes"]["evidence-one"]["provenance"][0][
        "independence_group"
    ] = "ind-first-declaration"
    duplicate["provenance"][0]["independence_group"] = "ind-second-declaration"
    payload["nodes"]["evidence-two"] = duplicate
    payload["blocks"]["block-alpha"]["member_nodes"].append("evidence-two")

    snapshot = snapshot_for(payload)
    first_group = snapshot.model_payload["nodes"]["evidence-one"]["provenance"][0][
        "independence_group"
    ]
    second_group = snapshot.model_payload["nodes"]["evidence-two"]["provenance"][0][
        "independence_group"
    ]
    assert first_group == second_group == "ind-first-declaration"
    validate_snapshot(snapshot)


def test_snapshot_is_stable_immutable_and_excludes_evaluated_state() -> None:
    payload = valid_model_payload()
    first = snapshot_for(payload)
    second = snapshot_for(valid_model_payload())

    assert first.revision == second.revision
    assert first.content_digest == second.content_digest
    assert "state" not in first.model_payload["nodes"]["evidence-one"]
    with pytest.raises(TypeError):
        first.model_payload["model"]["title"] = "mutated"  # type: ignore[index]

    detached = first.authoring_payload()
    detached["model"]["title"] = "mutated"
    assert first.model_payload["model"]["title"] == "Alpha"

    child = snapshot_for(valid_model_payload(), first.revision)
    changed = snapshot_for(valid_model_payload(text="Changed"))
    assert child.revision != first.revision
    assert changed.revision != first.revision


def test_detached_model_receives_revision_binding_without_self_fingerprinting() -> None:
    snapshot = snapshot_for(valid_model_payload())
    model = snapshot.to_model()
    assert model.metadata["model_revision_id"] == str(snapshot.revision)
    assert model.metadata["model_content_digest"] == snapshot.content_digest

    recomposed = ModelSnapshot.create(
        model,
        parent_revision=None,
        created_at=utc_now(),
        created_by="test-actor",
    )
    assert recomposed.revision == snapshot.revision


def test_durable_validation_rejects_ai_evidence_and_conflicting_block_projection() -> None:
    payload = valid_model_payload()
    payload["nodes"]["evidence-one"]["provenance"] = [
        {
            "origin_kind": "ai_generated",
            "source_id": "model-output",
            "content_hash": content_hash_for("generated"),
        }
    ]
    with pytest.raises(DurableValidationError, match="evidence-one"):
        validate_snapshot(snapshot_for(payload))

    payload = valid_model_payload()
    payload["nodes"]["block-alpha"] = {
        "type": "ArgumentBlock",
        "text": "Different card title",
    }
    with pytest.raises(DurableValidationError, match="title conflicts"):
        validate_snapshot(snapshot_for(payload))


def test_retired_alias_manifest_is_rejected_and_tombstone_retains_exact_history(tmp_path) -> None:
    store = FileModelStore(tmp_path / "store")
    transaction = store.begin("model-alpha", None, "create-alpha", "test-actor")
    transaction.stage(valid_model_payload())
    commit = transaction.commit()

    tombstone = store.tombstone(
        "model-alpha", actor="test-actor", reason="retired intentionally"
    )
    with pytest.raises(TombstonedModelError, match="retired intentionally"):
        store.get("model-alpha")
    historical = store.get("model-alpha", commit.revision)
    assert historical.revision == commit.revision
    assert tombstone.action == "tombstone"

    retired_root = tmp_path / "retired-store"
    FileModelStore(retired_root)
    manifest_path = retired_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["aliases"] = {
        "model-retired": {"target": "model-alpha", "receipt_id": "receipt-retired"}
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(StoreCorruptionError, match="aliases are retired"):
        FileModelStore(retired_root)


def test_non_current_manifest_schema_fails_visibly(tmp_path) -> None:
    root = tmp_path / "store"
    FileModelStore(root)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["artifact_schema"] == MANIFEST_SCHEMA
    manifest["artifact_schema"] = "researchguard.logic.old-manifest.v0"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(StoreSchemaError) as caught:
        FileModelStore(root)
    message = str(caught.value)
    assert str(manifest_path) in message
    assert "researchguard.logic.old-manifest.v0" in message
    assert MANIFEST_SCHEMA in message
    assert "explicit import/upgrade" in message


def test_missing_manifest_in_non_empty_store_is_not_silently_recreated(tmp_path) -> None:
    root = tmp_path / "store"
    store = FileModelStore(root)
    transaction = store.begin("model-alpha", None, "create-alpha", "test-actor")
    transaction.stage(valid_model_payload())
    transaction.commit()
    (root / "manifest.json").unlink()

    with pytest.raises(StoreCorruptionError, match="refusing to create replacement authority"):
        FileModelStore(root)
    assert not (root / "manifest.json").exists()


def test_non_current_authorized_snapshot_schema_names_exact_artifact_path(tmp_path) -> None:
    root = tmp_path / "store"
    store = FileModelStore(root)
    transaction = store.begin("model-alpha", None, "create-alpha", "test-actor")
    transaction.stage(valid_model_payload())
    transaction.commit()
    revision_path = next((root / "models").glob("*/revisions/*.json"))
    snapshot_raw = json.loads(revision_path.read_text(encoding="utf-8"))
    snapshot_raw["artifact_schema"] = "researchguard.logic.old-snapshot.v0"
    revision_path.write_text(json.dumps(snapshot_raw), encoding="utf-8")

    with pytest.raises(StoreSchemaError) as caught:
        store.get("model-alpha")
    assert str(revision_path) in str(caught.value)
    assert "researchguard.logic.old-snapshot.v0" in str(caught.value)


def test_file_store_round_trips_revision_bound_evaluation_overlay(tmp_path) -> None:
    store = FileModelStore(tmp_path / "store")
    transaction = store.begin("model-alpha", None, "create-alpha", "test-actor")
    transaction.stage(valid_model_payload())
    commit = transaction.commit()
    snapshot = store.get("model-alpha")
    overlay = evaluate_snapshot(
        snapshot,
        requested_claim_scope=("claim-root",),
        authoritative_universe=tuple(snapshot.model_payload["nodes"]),
    )

    store.put_evaluation(overlay, expected_model_digest=snapshot.content_digest)
    loaded = store.get_evaluation(
        "model-alpha", commit.revision, overlay.evaluation_id
    )
    assert loaded == overlay

    update = store.begin("model-alpha", commit.revision, "update-alpha", "test-actor")
    update.stage(valid_model_payload(text="Changed conclusion"))
    update.commit()
    assert not loaded.currentness(store.get("model-alpha")).binding_current
