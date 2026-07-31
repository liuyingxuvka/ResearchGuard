"""Task-local prediction, observation, and immutable argument-model revision.

This module coordinates existing LogicGuard authorities.  It does not change
evaluation or simulation semantics and it never edits Guard policy.
"""

from __future__ import annotations

import uuid
import hashlib
import json
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
from .execution_depth import _build_native_depth_analysis


ARGUMENT_PREDICTION_SCHEMA = "researchguard.logic.argument-prediction.v2"
ARGUMENT_ITERATION_RECEIPT_SCHEMA = "researchguard.logic.argument-iteration-receipt.v2"
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
MODEL_TERMINALS = frozenset(
    {
        "continue_iteration",
        "model_closed_for_task",
        "external_input_required",
        "scope_excluded",
        "progress_stalled",
        "iteration_limit",
    }
)
ARGUMENT_ITERATION_CLAIM_BOUNDARY = (
    "This receipt proves one task-local prediction, native LogicGuard observation, "
    "declared protected-claim checks, and immutable revision disposition. It does "
    "not prove factual truth or the completeness of undeclared claims."
)


def _canonical_sha256(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(body.encode('utf-8')).hexdigest()}"


def _native_depth(model: LogicModel, prediction: "ArgumentPrediction") -> tuple[Mapping[str, Any], tuple[str, ...]]:
    receipt = _build_native_depth_analysis(
        model,
        requested_claim_scope_ids=prediction.coverage_ids,
    )
    payload = receipt.to_dict()
    return payload, tuple(sorted(str(item) for item in receipt.unresolved_gaps))


def _gap_lineage(
    prior: Sequence[str], current: Sequence[str]
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    before, after = set(prior), set(current)
    return (
        tuple(sorted(before - after)),
        tuple(sorted(before & after)),
        tuple(sorted(after - before)),
    )


def _receipt_fingerprint(
    prediction: "ArgumentPrediction",
    baseline_digest: str,
    candidate_digest: str | None,
    open_gap_ids: Sequence[str],
    terminal_reason: str,
) -> str:
    return _canonical_sha256(
        {
            "prediction": prediction.to_dict(),
            "baseline_digest": baseline_digest,
            "candidate_digest": candidate_digest,
            "open_gap_ids": sorted(open_gap_ids),
            "terminal_reason": terminal_reason,
        }
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
    task_id: str
    purpose: str
    coverage_ids: tuple[str, ...]
    coverage_fingerprint: str
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    iteration: int
    max_iterations: int
    prior_receipt_fingerprint: str
    prior_open_gap_ids: tuple[str, ...]
    holdout_claim_ids: tuple[str, ...]
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
        if not self.task_id.strip() or not self.purpose.strip():
            raise ValueError("task_id and purpose are required")
        if not self.coverage_ids:
            raise ValueError("task-local argument predictions require coverage_ids")
        if not self.coverage_fingerprint.startswith("sha256:"):
            raise ValueError("coverage_fingerprint is required")
        expected_coverage_fingerprint = _canonical_sha256(
            {
                "task_id": self.task_id,
                "purpose": self.purpose,
                "coverage_ids": sorted(self.coverage_ids),
                "model_id": self.model_id,
            }
        )
        if self.coverage_fingerprint != expected_coverage_fingerprint:
            raise ValueError("coverage_fingerprint does not bind the task coverage")
        if len(set(self.coverage_ids)) != len(self.coverage_ids):
            raise ValueError("coverage_ids must not contain duplicates")
        if self.iteration < 0 or self.max_iterations < 1:
            raise ValueError("iteration must be non-negative and max_iterations must be positive")
        if self.iteration and not self.prior_receipt_fingerprint.startswith("sha256:"):
            raise ValueError("later iterations require prior_receipt_fingerprint")
        if len(set(self.prior_open_gap_ids)) != len(self.prior_open_gap_ids):
            raise ValueError("prior_open_gap_ids must not contain duplicates")
        if not self.holdout_claim_ids:
            raise ValueError("at least one independent holdout_claim_id is required")
        if len(set(self.holdout_claim_ids)) != len(self.holdout_claim_ids):
            raise ValueError("holdout_claim_ids must not contain duplicates")
        if set(self.holdout_claim_ids) & set(self.protected_claim_ids):
            raise ValueError("holdout claims must be distinct from protected claims")

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
            "task_id": self.task_id,
            "purpose": self.purpose,
            "coverage_ids": list(self.coverage_ids),
            "coverage_fingerprint": self.coverage_fingerprint,
            "assumptions": list(self.assumptions),
            "unknowns": list(self.unknowns),
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "prior_receipt_fingerprint": self.prior_receipt_fingerprint,
            "prior_open_gap_ids": list(self.prior_open_gap_ids),
            "holdout_claim_ids": list(self.holdout_claim_ids),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ArgumentPrediction":
        required_task_fields = {
            "task_id",
            "purpose",
            "coverage_ids",
            "coverage_fingerprint",
            "assumptions",
            "unknowns",
            "iteration",
            "max_iterations",
            "prior_receipt_fingerprint",
            "prior_open_gap_ids",
            "holdout_claim_ids",
        }
        missing = sorted(required_task_fields - set(raw))
        if missing:
            raise ValueError(
                "current argument prediction is missing task fields: "
                + ", ".join(missing)
            )
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
            task_id=str(raw.get("task_id", "")),
            purpose=str(raw.get("purpose", "")),
            coverage_ids=tuple(str(item) for item in (raw.get("coverage_ids") or ())),
            coverage_fingerprint=str(raw.get("coverage_fingerprint", "")),
            assumptions=tuple(str(item) for item in (raw.get("assumptions") or ())),
            unknowns=tuple(str(item) for item in (raw.get("unknowns") or ())),
            iteration=int(raw.get("iteration", 0)),
            max_iterations=int(raw.get("max_iterations", 8)),
            prior_receipt_fingerprint=str(raw.get("prior_receipt_fingerprint", "")),
            prior_open_gap_ids=tuple(str(item) for item in (raw.get("prior_open_gap_ids") or ())),
            holdout_claim_ids=tuple(str(item) for item in (raw.get("holdout_claim_ids") or ())),
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
    holdout_claims: tuple[ProtectedClaimRevalidation, ...]
    native_depth_receipt: Mapping[str, Any]
    native_depth_receipt_id: str
    requested_disposition: str
    effective_disposition: str
    disposition_reason: str
    baseline_revision: str
    candidate_revision: str | None
    store_receipt: Mapping[str, Any] | None
    completed_at: str
    schema_version: str = ARGUMENT_ITERATION_RECEIPT_SCHEMA
    claim_boundary: str = ARGUMENT_ITERATION_CLAIM_BOUNDARY
    input_gap_ids: tuple[str, ...] = ()
    resolved_gap_ids: tuple[str, ...] = ()
    persisted_gap_ids: tuple[str, ...] = ()
    introduced_gap_ids: tuple[str, ...] = ()
    open_gap_ids: tuple[str, ...] = ()
    gap_transitions: Mapping[str, str] = None  # type: ignore[assignment]
    next_actions: tuple[str, ...] = ()
    terminal_reason: str = "continue_iteration"
    progressed: bool = False
    receipt_fingerprint: str = ""

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
            "holdout_claims": [item.to_dict() for item in self.holdout_claims],
            "native_depth_receipt": dict(self.native_depth_receipt),
            "native_depth_receipt_id": self.native_depth_receipt_id,
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
            "input_gap_ids": list(self.input_gap_ids),
            "resolved_gap_ids": list(self.resolved_gap_ids),
            "persisted_gap_ids": list(self.persisted_gap_ids),
            "introduced_gap_ids": list(self.introduced_gap_ids),
            "open_gap_ids": list(self.open_gap_ids),
            "gap_transitions": dict(self.gap_transitions or {}),
            "next_actions": list(self.next_actions),
            "terminal_reason": self.terminal_reason,
            "progressed": self.progressed,
            "receipt_fingerprint": self.receipt_fingerprint,
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
    task_id: str,
    purpose: str,
    coverage_ids: Sequence[str],
    assumptions: Sequence[str] = (),
    unknowns: Sequence[str] = (),
    iteration: int,
    max_iterations: int,
    prior_receipt_fingerprint: str = "",
    prior_open_gap_ids: Sequence[str] = (),
    holdout_claim_ids: Sequence[str],
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
    for holdout_id in holdout_claim_ids:
        if holdout_id not in model.nodes or model.nodes[holdout_id].type != "Claim":
            raise ValueError(f"holdout claim is missing or not a Claim: {holdout_id}")
        if holdout_id == claim_id:
            raise ValueError("the perturbed target claim cannot also be a holdout")
    coverage = tuple(str(item) for item in coverage_ids)
    coverage_fingerprint = _canonical_sha256(
        {
            "task_id": task_id,
            "purpose": purpose,
            "coverage_ids": sorted(coverage),
            "model_id": model.id,
        }
    )
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
        task_id=task_id,
        purpose=purpose,
        coverage_ids=coverage,
        coverage_fingerprint=coverage_fingerprint,
        assumptions=tuple(str(item) for item in assumptions),
        unknowns=tuple(str(item) for item in unknowns),
        iteration=iteration,
        max_iterations=max_iterations,
        prior_receipt_fingerprint=prior_receipt_fingerprint,
        prior_open_gap_ids=tuple(str(item) for item in prior_open_gap_ids),
        holdout_claim_ids=tuple(str(item) for item in holdout_claim_ids),
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


def _argument_open_gaps(
    model: LogicModel,
    observation: ArgumentObservation,
    prediction: ArgumentPrediction,
) -> tuple[str, ...]:
    """Derive executable native gaps; prose/self-report never enters this set."""

    gaps: set[str] = set()
    native = observation.native_result
    if native.get("warnings"):
        gaps.update(
            f"native-warning:{index}"
            for index, _ in enumerate(native["warnings"])
        )
    if native.get("cycles"):
        gaps.add("native-argument-cycle")
    root = native.get("root")
    if isinstance(root, Mapping):
        blockers = root.get("blockers", ())
        if isinstance(blockers, list):
            gaps.update(f"native-blocker:{blocker}" for blocker in blockers)
    for coverage_id in prediction.coverage_ids:
        if coverage_id not in model.nodes:
            gaps.add(f"coverage-missing:{coverage_id}")
    return tuple(sorted(gaps))


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
    """Observe a prediction and close only on current native depth evidence."""

    if decision not in {"accept", "reject"}:
        raise ValueError("decision must be 'accept' or 'reject'")
    validate_prediction_binding(baseline, prediction)
    baseline_snapshot = _ensure_baseline_snapshot(store, baseline, prediction, actor)
    baseline_observation = observe_argument_prediction(baseline, prediction)
    baseline_comparison = compare_argument_prediction(prediction, baseline_observation)
    baseline_depth, baseline_depth_gaps = _native_depth(baseline, prediction)
    baseline_gaps = tuple(
        sorted(set(_argument_open_gaps(baseline, baseline_observation, prediction)) | set(baseline_depth_gaps))
    )

    def terminal_for(gaps: Sequence[str], *, external: bool = False) -> str:
        if prediction.iteration >= prediction.max_iterations:
            return "iteration_limit"
        if external:
            return "external_input_required"
        if set(gaps) == set(prediction.prior_open_gap_ids) and prediction.iteration > 0:
            return "progress_stalled"
        return "continue_iteration" if gaps else "model_closed_for_task"

    def make_receipt(
        *,
        candidate_observation: ArgumentObservation | None,
        candidate_comparison: ArgumentPredictionComparison | None,
        protected: tuple[ProtectedClaimRevalidation, ...],
        holdout: tuple[ProtectedClaimRevalidation, ...],
        native_depth: Mapping[str, Any],
        candidate_revision: str | None,
        store_receipt: Mapping[str, Any] | None,
        effective: str,
        reason: str,
        gaps: Sequence[str],
        terminal: str,
    ) -> ArgumentIterationReceipt:
        resolved, persisted, introduced = _gap_lineage(
            prediction.prior_open_gap_ids, gaps
        )
        transitions = {
            **{gap: "resolved" for gap in resolved},
            **{gap: "persisted" for gap in persisted},
            **{gap: "introduced" for gap in introduced},
        }
        candidate_digest = (
            candidate_observation.model_digest if candidate_observation else None
        )
        receipt_fingerprint = _receipt_fingerprint(
            prediction,
            baseline_observation.model_digest,
            candidate_digest,
            gaps,
            terminal,
        )
        return ArgumentIterationReceipt(
            prediction=prediction,
            baseline_observation=baseline_observation,
            baseline_comparison=baseline_comparison,
            candidate_observation=candidate_observation,
            candidate_comparison=candidate_comparison,
            protected_claims=protected,
            holdout_claims=holdout,
            native_depth_receipt=native_depth,
            native_depth_receipt_id=(
                str(native_depth.get("receipt_version", "logic-depth"))
                + ":"
                + str(native_depth.get("model_fingerprint", ""))[:20]
            ),
            requested_disposition=decision,
            effective_disposition=effective,
            disposition_reason=reason,
            baseline_revision=str(baseline_snapshot.revision),
            candidate_revision=candidate_revision,
            store_receipt=store_receipt,
            completed_at=utc_now(),
            input_gap_ids=prediction.prior_open_gap_ids,
            resolved_gap_ids=resolved,
            persisted_gap_ids=persisted,
            introduced_gap_ids=introduced,
            open_gap_ids=tuple(sorted(gaps)),
            gap_transitions=transitions,
            next_actions=("deepen_logic_model",) if gaps else ("no_model_change_needed",),
            terminal_reason=terminal,
            progressed=bool(resolved or introduced or (prediction.iteration == 0 and gaps)),
            receipt_fingerprint=receipt_fingerprint,
        )

    if baseline_comparison.matches and not baseline_gaps:
        holdout = revalidate_protected_claims(
            baseline, baseline, prediction.holdout_claim_ids
        )
        return make_receipt(
            candidate_observation=None,
            candidate_comparison=None,
            protected=(),
            holdout=holdout,
            native_depth=baseline_depth,
            candidate_revision=None,
            store_receipt=None,
            effective="no_revision_needed",
            reason="baseline prediction and current native depth receipt pass",
            gaps=(),
            terminal="model_closed_for_task",
        )

    if candidate is None:
        gaps = set(baseline_gaps)
        external = not baseline_comparison.matches
        if external:
            gaps.add("candidate-model-required")
        return make_receipt(
            candidate_observation=None,
            candidate_comparison=None,
            protected=(),
            holdout=(),
            native_depth=baseline_depth,
            candidate_revision=None,
            store_receipt=None,
            effective="external_input_required" if external else "continue_iteration",
            reason=(
                "a candidate model is required after the frozen prediction mismatch"
                if external
                else "current native LogicGuard depth gaps remain"
            ),
            gaps=tuple(sorted(gaps)),
            terminal=terminal_for(tuple(sorted(gaps)), external=external),
        )

    candidate_observation = observe_argument_prediction(
        candidate, prediction, require_baseline_binding=False
    )
    candidate_comparison = compare_argument_prediction(prediction, candidate_observation)
    candidate_depth, candidate_depth_gaps = _native_depth(candidate, prediction)
    gaps = set(_argument_open_gaps(candidate, candidate_observation, prediction)) | set(candidate_depth_gaps)
    protected = revalidate_protected_claims(baseline, candidate, prediction.protected_claim_ids)
    holdout = revalidate_protected_claims(baseline, candidate, prediction.holdout_claim_ids)
    if not candidate_comparison.matches:
        gaps.add("candidate-prediction-mismatch")
    if any(not item.passed for item in protected):
        gaps.add("protected-claim-regression")
    if any(not item.passed for item in holdout):
        gaps.add("independent-holdout-regression")

    transaction = store.begin(
        baseline.id,
        baseline_snapshot.revision,
        idempotency_key or f"{prediction.prediction_id}:candidate",
        actor,
    )
    transaction.stage(candidate)
    staged_revision = transaction.staged_snapshot.revision
    can_accept = decision == "accept" and not gaps
    if can_accept:
        try:
            committed = transaction.commit()
        except TransactionConflictError as exc:
            conflict_gaps = tuple(sorted(set(gaps) | {"model-store-conflict"}))
            return make_receipt(
                candidate_observation=candidate_observation,
                candidate_comparison=candidate_comparison,
                protected=protected,
                holdout=holdout,
                native_depth=candidate_depth,
                candidate_revision=str(staged_revision),
                store_receipt=exc.receipt.to_dict() if exc.receipt else None,
                effective="conflict",
                reason=str(exc),
                gaps=conflict_gaps,
                terminal=terminal_for(conflict_gaps),
            )
        return make_receipt(
            candidate_observation=candidate_observation,
            candidate_comparison=candidate_comparison,
            protected=protected,
            holdout=holdout,
            native_depth=candidate_depth,
            candidate_revision=str(committed.revision),
            store_receipt=committed.to_dict(),
            effective="accepted",
            reason="candidate prediction, native depth, protected claims, and independent holdout pass",
            gaps=(),
            terminal="model_closed_for_task",
        )

    reasons: list[str] = []
    if decision == "reject":
        reasons.append("caller requested rejection")
        gaps.add("candidate-rejected")
    if gaps:
        reasons.append("candidate retains current LogicGuard closure gaps")
    aborted = transaction.abort("; ".join(reasons))
    ordered_gaps = tuple(sorted(gaps))
    return make_receipt(
        candidate_observation=candidate_observation,
        candidate_comparison=candidate_comparison,
        protected=protected,
        holdout=holdout,
        native_depth=candidate_depth,
        candidate_revision=str(staged_revision),
        store_receipt=aborted.to_dict(),
        effective="rejected" if decision == "reject" else "continue_iteration",
        reason="; ".join(reasons),
        gaps=ordered_gaps,
        terminal=terminal_for(ordered_gaps, external=decision == "reject"),
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
