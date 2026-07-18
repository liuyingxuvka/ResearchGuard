"""Task-local prediction, observation, and immutable argument-model revision.

This module coordinates existing LogicGuard authorities.  It does not change
evaluation or simulation semantics and it never edits Guard policy.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .evaluator import evaluate_model
from .model import LogicModel
from .model_store import (
    ModelSnapshot,
    ModelStore,
    TransactionConflictError,
    canonical_digest,
    canonical_model_payload,
)
from .receipts import utc_now
from .schema import STATES
from .simulator import simulate_model


ARGUMENT_PREDICTION_SCHEMA = "researchguard.logic.argument-prediction.v1"
ARGUMENT_ITERATION_RECEIPT_SCHEMA = "researchguard.logic.argument-iteration-receipt.v1"
ARGUMENT_ROLLBACK_RECEIPT_SCHEMA = "researchguard.logic.argument-rollback-receipt.v1"
SUPPORTED_PREDICTION_MODES = frozenset(
    {
        "premise-removal",
        "evidence-weakening",
        "rebuttal-activation",
        "assumption-flip",
        "scope-narrowing",
    }
)
ARGUMENT_ITERATION_CLAIM_BOUNDARY = (
    "This receipt proves one task-local prediction, native LogicGuard observation, "
    "declared protected-claim checks, and immutable revision disposition. It does "
    "not prove factual truth or the completeness of undeclared claims."
)


@dataclass(frozen=True)
class ArgumentPrediction:
    prediction_id: str
    model_id: str
    baseline_digest: str
    root_claim: str
    mode: str
    expected_state: str
    node_id: str | None
    confidence: float | None
    max_size: int
    protected_claim_ids: tuple[str, ...]
    frozen_at: str
    schema_version: str = ARGUMENT_PREDICTION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != ARGUMENT_PREDICTION_SCHEMA:
            raise ValueError(
                f"unsupported argument prediction schema {self.schema_version!r}"
            )
        if not self.prediction_id:
            raise ValueError("prediction_id must not be empty")
        if not self.model_id:
            raise ValueError("model_id must not be empty")
        if not self.baseline_digest.startswith("sha256:"):
            raise ValueError("baseline_digest must be a sha256 digest")
        if self.mode not in SUPPORTED_PREDICTION_MODES:
            raise ValueError(f"unsupported prediction mode: {self.mode}")
        if self.expected_state not in STATES:
            raise ValueError(f"unsupported expected claim state: {self.expected_state}")
        if not self.root_claim:
            raise ValueError("root_claim must not be empty")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.max_size < 1:
            raise ValueError("max_size must be positive")
        if len(set(self.protected_claim_ids)) != len(self.protected_claim_ids):
            raise ValueError("protected_claim_ids must not contain duplicates")
        if not self.frozen_at:
            raise ValueError("frozen_at must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "prediction_id": self.prediction_id,
            "model_id": self.model_id,
            "baseline_digest": self.baseline_digest,
            "root_claim": self.root_claim,
            "mode": self.mode,
            "expected_state": self.expected_state,
            "node_id": self.node_id,
            "confidence": self.confidence,
            "max_size": self.max_size,
            "protected_claim_ids": list(self.protected_claim_ids),
            "frozen_at": self.frozen_at,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ArgumentPrediction":
        return cls(
            schema_version=str(raw.get("schema_version", "")),
            prediction_id=str(raw.get("prediction_id", "")),
            model_id=str(raw.get("model_id", "")),
            baseline_digest=str(raw.get("baseline_digest", "")),
            root_claim=str(raw.get("root_claim", "")),
            mode=str(raw.get("mode", "")),
            expected_state=str(raw.get("expected_state", "")),
            node_id=str(raw["node_id"]) if raw.get("node_id") else None,
            confidence=(
                float(raw["confidence"]) if raw.get("confidence") is not None else None
            ),
            max_size=int(raw.get("max_size", 2)),
            protected_claim_ids=tuple(
                str(item) for item in (raw.get("protected_claim_ids") or ())
            ),
            frozen_at=str(raw.get("frozen_at", "")),
        )


@dataclass(frozen=True)
class ArgumentObservation:
    model_digest: str
    observed_state: str | None
    observed_confidence: float | None
    native_result: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_digest": self.model_digest,
            "observed_state": self.observed_state,
            "observed_confidence": self.observed_confidence,
            "native_result": dict(self.native_result),
        }


@dataclass(frozen=True)
class ArgumentPredictionComparison:
    expected_state: str
    observed_state: str | None
    matches: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_state": self.expected_state,
            "observed_state": self.observed_state,
            "matches": self.matches,
        }


@dataclass(frozen=True)
class ProtectedClaimRevalidation:
    claim_id: str
    baseline_state: str | None
    candidate_state: str | None
    status: str
    reason: str

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "baseline_state": self.baseline_state,
            "candidate_state": self.candidate_state,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ArgumentIterationReceipt:
    prediction: ArgumentPrediction
    baseline_observation: ArgumentObservation
    baseline_comparison: ArgumentPredictionComparison
    candidate_observation: ArgumentObservation | None
    candidate_comparison: ArgumentPredictionComparison | None
    protected_claims: tuple[ProtectedClaimRevalidation, ...]
    requested_disposition: str
    effective_disposition: str
    disposition_reason: str
    baseline_revision: str
    candidate_revision: str | None
    store_receipt: Mapping[str, Any] | None
    completed_at: str
    schema_version: str = ARGUMENT_ITERATION_RECEIPT_SCHEMA
    claim_boundary: str = ARGUMENT_ITERATION_CLAIM_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "prediction": self.prediction.to_dict(),
            "baseline_observation": self.baseline_observation.to_dict(),
            "baseline_comparison": self.baseline_comparison.to_dict(),
            "candidate_observation": (
                self.candidate_observation.to_dict()
                if self.candidate_observation is not None
                else None
            ),
            "candidate_comparison": (
                self.candidate_comparison.to_dict()
                if self.candidate_comparison is not None
                else None
            ),
            "protected_claims": [item.to_dict() for item in self.protected_claims],
            "requested_disposition": self.requested_disposition,
            "effective_disposition": self.effective_disposition,
            "disposition_reason": self.disposition_reason,
            "baseline_revision": self.baseline_revision,
            "candidate_revision": self.candidate_revision,
            "store_receipt": (
                dict(self.store_receipt) if self.store_receipt is not None else None
            ),
            "completed_at": self.completed_at,
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class ArgumentRollbackReceipt:
    model_id: str
    rollback_source_revision: str
    prior_head_revision: str
    compensating_revision: str
    store_receipt: Mapping[str, Any]
    completed_at: str
    schema_version: str = ARGUMENT_ROLLBACK_RECEIPT_SCHEMA
    claim_boundary: str = ARGUMENT_ITERATION_CLAIM_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "rollback_source_revision": self.rollback_source_revision,
            "prior_head_revision": self.prior_head_revision,
            "compensating_revision": self.compensating_revision,
            "store_receipt": dict(self.store_receipt),
            "completed_at": self.completed_at,
            "claim_boundary": self.claim_boundary,
        }


def freeze_argument_prediction(
    model: LogicModel,
    *,
    expected_state: str,
    mode: str,
    root_claim: str | None = None,
    node_id: str | None = None,
    confidence: float | None = None,
    max_size: int = 2,
    protected_claim_ids: Sequence[str] = (),
    prediction_id: str | None = None,
) -> ArgumentPrediction:
    """Freeze an expectation without running the native simulator."""

    claim_id = root_claim or model.root_claim
    if not claim_id or claim_id not in model.nodes:
        raise ValueError("prediction root claim is missing from the model")
    if model.nodes[claim_id].type != "Claim":
        raise ValueError(f"prediction root {claim_id!r} is not a Claim")
    if mode not in SUPPORTED_PREDICTION_MODES:
        raise ValueError(f"unsupported prediction mode: {mode}")
    target_id = node_id or (claim_id if mode == "scope-narrowing" else None)
    if not target_id or target_id not in model.nodes:
        raise ValueError("prediction perturbation target is missing from the model")
    for protected_id in protected_claim_ids:
        if protected_id not in model.nodes:
            raise ValueError(f"protected claim is missing from baseline: {protected_id}")
        if model.nodes[protected_id].type != "Claim":
            raise ValueError(f"protected node {protected_id!r} is not a Claim")
        if protected_id == claim_id:
            raise ValueError("the perturbed target claim cannot also be protected")
    return ArgumentPrediction(
        prediction_id=prediction_id or f"prediction-{uuid.uuid4().hex}",
        model_id=model.id,
        baseline_digest=_model_digest(model),
        root_claim=claim_id,
        mode=mode,
        expected_state=expected_state,
        node_id=target_id,
        confidence=confidence,
        max_size=max_size,
        protected_claim_ids=tuple(str(item) for item in protected_claim_ids),
        frozen_at=utc_now(),
    )


def observe_argument_prediction(
    model: LogicModel,
    prediction: ArgumentPrediction,
    *,
    require_baseline_binding: bool = True,
) -> ArgumentObservation:
    """Run the frozen perturbation through the existing native simulator."""

    if require_baseline_binding:
        validate_prediction_binding(model, prediction)
    elif model.id != prediction.model_id:
        raise ValueError(
            f"candidate model id {model.id!r} does not match prediction model "
            f"{prediction.model_id!r}"
        )
    result = simulate_model(
        model,
        root_claim=prediction.root_claim,
        mode=prediction.mode,
        node_id=prediction.node_id,
        confidence=prediction.confidence,
        max_size=prediction.max_size,
    )
    return ArgumentObservation(
        model_digest=_model_digest(model),
        observed_state=result.result_state,
        observed_confidence=result.result_confidence,
        native_result=result.to_dict(),
    )


def compare_argument_prediction(
    prediction: ArgumentPrediction,
    observation: ArgumentObservation,
) -> ArgumentPredictionComparison:
    return ArgumentPredictionComparison(
        expected_state=prediction.expected_state,
        observed_state=observation.observed_state,
        matches=observation.observed_state == prediction.expected_state,
    )


def validate_prediction_binding(
    model: LogicModel, prediction: ArgumentPrediction
) -> None:
    if model.id != prediction.model_id:
        raise ValueError(
            f"prediction model id {prediction.model_id!r} does not match "
            f"baseline {model.id!r}"
        )
    actual_digest = _model_digest(model)
    if actual_digest != prediction.baseline_digest:
        raise ValueError(
            "stale argument prediction: baseline digest changed "
            f"from {prediction.baseline_digest} to {actual_digest}"
        )
    if prediction.root_claim not in model.nodes:
        raise ValueError("prediction root claim is missing from baseline")
    if not prediction.node_id or prediction.node_id not in model.nodes:
        raise ValueError("prediction perturbation target is missing from baseline")


def revalidate_protected_claims(
    baseline: LogicModel,
    candidate: LogicModel,
    claim_ids: Sequence[str],
) -> tuple[ProtectedClaimRevalidation, ...]:
    baseline_result = evaluate_model(baseline)
    candidate_result = evaluate_model(candidate)
    rows: list[ProtectedClaimRevalidation] = []
    for claim_id in claim_ids:
        if claim_id not in baseline.nodes or baseline.nodes[claim_id].type != "Claim":
            rows.append(
                ProtectedClaimRevalidation(
                    claim_id=claim_id,
                    baseline_state=None,
                    candidate_state=None,
                    status="fail",
                    reason="protected claim is missing or not a Claim in baseline",
                )
            )
            continue
        if claim_id not in candidate.nodes or candidate.nodes[claim_id].type != "Claim":
            rows.append(
                ProtectedClaimRevalidation(
                    claim_id=claim_id,
                    baseline_state=baseline_result.node_results[claim_id].state,
                    candidate_state=None,
                    status="fail",
                    reason="protected claim is missing or not a Claim in candidate",
                )
            )
            continue
        baseline_state = baseline_result.node_results[claim_id].state
        candidate_state = candidate_result.node_results[claim_id].state
        rows.append(
            ProtectedClaimRevalidation(
                claim_id=claim_id,
                baseline_state=baseline_state,
                candidate_state=candidate_state,
                status="pass" if baseline_state == candidate_state else "fail",
                reason=(
                    "native claim status is unchanged"
                    if baseline_state == candidate_state
                    else "native claim status changed in candidate"
                ),
            )
        )
    return tuple(rows)


def run_argument_iteration(
    store: ModelStore,
    baseline: LogicModel,
    prediction: ArgumentPrediction,
    *,
    candidate: LogicModel | None = None,
    decision: str = "reject",
    actor: str = "logicguard-task-iteration",
    idempotency_key: str | None = None,
) -> ArgumentIterationReceipt:
    """Observe a prediction and explicitly accept or reject a candidate revision."""

    if decision not in {"accept", "reject"}:
        raise ValueError("decision must be 'accept' or 'reject'")
    validate_prediction_binding(baseline, prediction)
    baseline_snapshot = _ensure_baseline_snapshot(store, baseline, prediction, actor)
    baseline_observation = observe_argument_prediction(baseline, prediction)
    baseline_comparison = compare_argument_prediction(prediction, baseline_observation)

    if baseline_comparison.matches:
        return ArgumentIterationReceipt(
            prediction=prediction,
            baseline_observation=baseline_observation,
            baseline_comparison=baseline_comparison,
            candidate_observation=None,
            candidate_comparison=None,
            protected_claims=(),
            requested_disposition=decision,
            effective_disposition="no_revision_needed",
            disposition_reason="baseline native observation matches the frozen prediction",
            baseline_revision=str(baseline_snapshot.revision),
            candidate_revision=None,
            store_receipt=None,
            completed_at=utc_now(),
        )
    if candidate is None:
        raise ValueError("a candidate model is required after a baseline prediction mismatch")

    candidate_observation = observe_argument_prediction(
        candidate, prediction, require_baseline_binding=False
    )
    candidate_comparison = compare_argument_prediction(prediction, candidate_observation)
    protected = revalidate_protected_claims(
        baseline, candidate, prediction.protected_claim_ids
    )
    protected_ok = all(item.passed for item in protected)
    transaction = store.begin(
        baseline.id,
        baseline_snapshot.revision,
        idempotency_key or f"{prediction.prediction_id}:candidate",
        actor,
    )
    transaction.stage(candidate)
    staged_revision = transaction.staged_snapshot.revision
    can_accept = candidate_comparison.matches and protected_ok
    if decision == "accept" and can_accept:
        try:
            store_receipt = transaction.commit()
        except TransactionConflictError as exc:
            return ArgumentIterationReceipt(
                prediction=prediction,
                baseline_observation=baseline_observation,
                baseline_comparison=baseline_comparison,
                candidate_observation=candidate_observation,
                candidate_comparison=candidate_comparison,
                protected_claims=protected,
                requested_disposition=decision,
                effective_disposition="conflict",
                disposition_reason=str(exc),
                baseline_revision=str(baseline_snapshot.revision),
                candidate_revision=str(staged_revision),
                store_receipt=(
                    exc.receipt.to_dict() if exc.receipt is not None else None
                ),
                completed_at=utc_now(),
            )
        return ArgumentIterationReceipt(
            prediction=prediction,
            baseline_observation=baseline_observation,
            baseline_comparison=baseline_comparison,
            candidate_observation=candidate_observation,
            candidate_comparison=candidate_comparison,
            protected_claims=protected,
            requested_disposition=decision,
            effective_disposition="accepted",
            disposition_reason="candidate repairs the prediction and preserves protected claims",
            baseline_revision=str(baseline_snapshot.revision),
            candidate_revision=str(store_receipt.revision),
            store_receipt=store_receipt.to_dict(),
            completed_at=utc_now(),
        )

    reasons: list[str] = []
    if decision == "reject":
        reasons.append("caller requested rejection")
    if not candidate_comparison.matches:
        reasons.append("candidate does not produce the frozen expected status")
    if not protected_ok:
        reasons.append("one or more protected claims changed")
    abort_receipt = transaction.abort("; ".join(reasons))
    return ArgumentIterationReceipt(
        prediction=prediction,
        baseline_observation=baseline_observation,
        baseline_comparison=baseline_comparison,
        candidate_observation=candidate_observation,
        candidate_comparison=candidate_comparison,
        protected_claims=protected,
        requested_disposition=decision,
        effective_disposition="rejected",
        disposition_reason="; ".join(reasons),
        baseline_revision=str(baseline_snapshot.revision),
        candidate_revision=str(staged_revision),
        store_receipt=abort_receipt.to_dict(),
        completed_at=utc_now(),
    )


def rollback_argument_revision(
    store: ModelStore,
    *,
    model_id: str,
    source_revision: str,
    actor: str = "logicguard-task-iteration",
    idempotency_key: str | None = None,
) -> ArgumentRollbackReceipt:
    """Append a compensating revision whose payload equals a historical revision."""

    prior_head = store.head(model_id)
    if prior_head is None:
        raise ValueError(f"cannot roll back model without a current head: {model_id}")
    historical = store.get(model_id, source_revision)
    transaction = store.begin(
        model_id,
        prior_head,
        idempotency_key
        or f"rollback:{source_revision}:{uuid.uuid4().hex}",
        actor,
    )
    transaction.stage(historical.authoring_payload())
    commit_receipt = transaction.commit()
    return ArgumentRollbackReceipt(
        model_id=model_id,
        rollback_source_revision=str(historical.revision),
        prior_head_revision=str(prior_head),
        compensating_revision=str(commit_receipt.revision),
        store_receipt=commit_receipt.to_dict(),
        completed_at=utc_now(),
    )


def _ensure_baseline_snapshot(
    store: ModelStore,
    baseline: LogicModel,
    prediction: ArgumentPrediction,
    actor: str,
) -> ModelSnapshot:
    head = store.head(baseline.id)
    if head is None:
        transaction = store.begin(
            baseline.id,
            None,
            f"{prediction.prediction_id}:baseline",
            actor,
        )
        transaction.stage(baseline)
        receipt = transaction.commit()
        return store.get(baseline.id, receipt.revision)
    snapshot = store.get(baseline.id)
    if snapshot.content_digest != prediction.baseline_digest:
        raise ValueError(
            "stored model head does not match the prediction-bound baseline: "
            f"{snapshot.content_digest} != {prediction.baseline_digest}"
        )
    return snapshot


def _model_digest(model: LogicModel) -> str:
    return canonical_digest(canonical_model_payload(model))


__all__ = [
    "ARGUMENT_ITERATION_CLAIM_BOUNDARY",
    "ARGUMENT_ITERATION_RECEIPT_SCHEMA",
    "ARGUMENT_PREDICTION_SCHEMA",
    "ARGUMENT_ROLLBACK_RECEIPT_SCHEMA",
    "SUPPORTED_PREDICTION_MODES",
    "ArgumentIterationReceipt",
    "ArgumentObservation",
    "ArgumentPrediction",
    "ArgumentPredictionComparison",
    "ArgumentRollbackReceipt",
    "ProtectedClaimRevalidation",
    "compare_argument_prediction",
    "freeze_argument_prediction",
    "observe_argument_prediction",
    "revalidate_protected_claims",
    "rollback_argument_revision",
    "run_argument_iteration",
    "validate_prediction_binding",
]
