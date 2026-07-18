from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from researchguard.logic.evaluation_overlay import (
    EvaluationOverlay,
    EvaluationOverlayError,
    evaluate_snapshot,
    fingerprint_authoritative_universe,
    fingerprint_evaluator,
)
from researchguard.logic.loader import load_model_from_dict
from researchguard.logic.model import NodeEvaluation
from researchguard.logic.model_store import ModelSnapshot
from researchguard.logic.schema import EVALUATION_OVERLAY_SCHEMA


def _model(*, model_id: str = "overlay-model", evidence_state: str = "IN"):
    return load_model_from_dict(
        {
            "model": {
                "id": model_id,
                "title": "Overlay test",
                "root_claim": "claim-root",
            },
            "nodes": {
                "evidence-1": {
                    "type": "Evidence",
                    "text": "Observed result",
                    "state": evidence_state,
                    "confidence": 0.9,
                },
                "claim-root": {
                    "type": "Claim",
                    "text": "Root claim",
                },
            },
            "edges": [
                {
                    "source": "evidence-1",
                    "target": "claim-root",
                    "type": "supports",
                }
            ],
        },
        validate=False,
    )


def _snapshot(*, model_id: str = "overlay-model", evidence_state: str = "IN"):
    return ModelSnapshot.create(
        _model(model_id=model_id, evidence_state=evidence_state),
        parent_revision=None,
        created_at="2026-07-14T12:00:00Z",
        created_by="test",
    )


def _evaluate(snapshot=None, **kwargs):
    snapshot = snapshot or _snapshot()
    return evaluate_snapshot(
        snapshot,
        requested_claim_scope=("claim-root",),
        authoritative_universe=("claim-root", "evidence-1"),
        **kwargs,
    )


def _currentness(overlay, snapshot=None, **kwargs):
    snapshot = snapshot or _snapshot()
    return overlay.currentness(
        snapshot,
        expected_evaluator_fingerprint=fingerprint_evaluator(),
        requested_claim_scope=("claim-root",),
        authoritative_universe=("claim-root", "evidence-1"),
        profile="broad",
        **kwargs,
    )


def test_evaluate_snapshot_creates_frozen_revision_bound_overlay_without_mutation():
    snapshot = _snapshot()
    before = snapshot.to_dict()

    overlay = _evaluate(snapshot)

    assert snapshot.to_dict() == before
    assert "state" not in snapshot.model_payload["nodes"]["claim-root"]
    assert str(overlay.model_id) == "overlay-model"
    assert overlay.revision == snapshot.revision
    assert overlay.content_digest == snapshot.content_digest
    assert overlay.artifact_schema == EVALUATION_OVERLAY_SCHEMA
    assert overlay.node_results["claim-root"].state == "IN"
    assert overlay.complete
    assert not overlay.truncated
    assert "factual truth" in overlay.claim_boundary
    with pytest.raises(FrozenInstanceError):
        overlay.profile = "bounded"
    with pytest.raises(TypeError):
        overlay.node_results["claim-root"] = overlay.node_results["claim-root"]


def test_overlay_round_trip_and_fingerprint_are_deterministic_and_tamper_evident():
    overlay = _evaluate()
    payload = overlay.to_dict()

    restored = EvaluationOverlay.from_dict(payload)

    assert restored == overlay
    assert restored.to_dict() == payload
    assert restored.fingerprint() == overlay.fingerprint()
    assert str(restored.evaluation_id) == payload["evaluation_id"]

    tampered = dict(payload)
    tampered["content_digest"] = "sha256:" + ("0" * 64)
    with pytest.raises(EvaluationOverlayError, match="evaluation_id|fingerprint"):
        EvaluationOverlay.from_dict(tampered)


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ({"model_id": "different-model"}, "model_id_mismatch"),
        ({"revision": "rev-" + ("1" * 64)}, "revision_mismatch"),
        ({"content_digest": "sha256:" + ("2" * 64)}, "content_digest_mismatch"),
        ({"evaluator_fingerprint": "sha256:" + ("3" * 64)}, "evaluator_fingerprint_mismatch"),
        ({"requested_claim_scope": ("evidence-1",)}, "requested_claim_scope_mismatch"),
        (
            {"authoritative_universe_fingerprint": "sha256:" + ("4" * 64)},
            "authoritative_universe_mismatch",
        ),
    ],
)
def test_binding_mismatches_fail_currentness_and_broad_currentness(mutation, expected_code):
    overlay = replace(_evaluate(), **mutation)

    report = _currentness(overlay)

    assert not report.binding_current
    assert not report.current
    assert not report.broad_current
    assert expected_code in {item.code for item in report.diagnostics}


def test_changed_snapshot_revision_and_content_stale_prior_overlay():
    first = _snapshot()
    overlay = _evaluate(first)
    changed_model = _model()
    changed_model.nodes["evidence-1"].text = "A changed canonical observation"
    second = ModelSnapshot.create(
        changed_model,
        parent_revision=first.revision,
        created_at="2026-07-14T13:00:00Z",
        created_by="test",
    )

    report = _currentness(overlay, second)

    assert not report.current
    codes = {item.code for item in report.diagnostics}
    assert {"revision_mismatch", "content_digest_mismatch"} <= codes


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ({"completeness": "partial"}, "incomplete_overlay"),
        ({"truncated": True}, "truncated_overlay"),
        ({"node_results": {}}, "requested_claim_results_missing"),
        ({"profile": "bounded"}, "profile_mismatch"),
    ],
)
def test_partial_truncated_missing_or_bounded_overlay_never_broad_passes(
    mutation, expected_code
):
    overlay = replace(_evaluate(), **mutation)

    report = _currentness(overlay)

    assert not report.broad_current
    assert expected_code in {item.code for item in report.diagnostics}


def test_scope_and_universe_are_canonical_and_their_expected_fingerprint_is_checked():
    snapshot = _snapshot()
    overlay = evaluate_snapshot(
        snapshot,
        requested_claim_scope=("claim-root", "claim-root"),
        authoritative_universe=("evidence-1", "claim-root", "evidence-1"),
    )

    assert overlay.requested_claim_scope == ("claim-root",)
    assert overlay.authoritative_universe_fingerprint == fingerprint_authoritative_universe(
        ("claim-root", "evidence-1")
    )
    assert overlay.is_broad_current(
        snapshot,
        expected_evaluator_fingerprint=fingerprint_evaluator(),
        requested_claim_scope=("claim-root",),
        authoritative_universe=("claim-root", "evidence-1"),
        profile="broad",
    )

    with pytest.raises(EvaluationOverlayError, match="does not match its universe"):
        evaluate_snapshot(
            snapshot,
            authoritative_universe=("claim-root",),
            authoritative_universe_fingerprint="sha256:" + ("0" * 64),
        )


def test_non_converged_native_evaluation_is_recorded_as_truncated():
    snapshot = _snapshot()
    overlay = evaluate_snapshot(
        snapshot,
        requested_claim_scope=("claim-root",),
        authoritative_universe=("claim-root", "evidence-1"),
        max_iterations=0,
    )

    assert overlay.truncated
    assert not _currentness(overlay, snapshot).broad_current


def test_constructor_freezes_native_node_evaluation_values():
    overlay = replace(
        _evaluate(),
        node_results={
            "claim-root": NodeEvaluation(
                node_id="claim-root",
                state="IN",
                confidence=0.75,
            )
        },
    )

    assert overlay.node_results["claim-root"].confidence == 0.75
