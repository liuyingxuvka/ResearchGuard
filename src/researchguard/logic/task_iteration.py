"""Task-local prediction, observation and candidate decision for an argument model.

This module coordinates existing LogicGuard authorities.  It does not change
evaluation or simulation semantics and it never edits Guard policy.  It never
writes model files: the baseline and the candidate stay as they are, so a
rollback is keeping (or restoring from git) the previous model file.
"""

from __future__ import annotations

import uuid
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from ..iteration import baseline_identity, source_identity, require_prediction_identity, select_terminal, validate_candidate, gap_lineage

from .evaluator import evaluate_model
from .model import LogicModel
from .schema import STATES
from .simulator import simulate_model
from .execution_depth import _build_native_depth_analysis


ARGUMENT_PREDICTION_SCHEMA = "researchguard.logic.argument-prediction.v3"
ARGUMENT_ITERATION_RESULT_SCHEMA = "researchguard.logic.argument-iteration-result.v1"
SUPPORTED_PREDICTION_MODES = frozenset(
    {
        "premise-removal",
        "evidence-weakening",
        "rebuttal-activation",
        "assumption-flip",
        "scope-narrowing",
    }
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")




def _native_depth(model: LogicModel, prediction: "ArgumentPrediction") -> tuple[str, ...]:
    analysis = _build_native_depth_analysis(
        model,
        requested_claim_scope_ids=prediction.coverage_ids or None,
    )
    return tuple(sorted(str(item) for item in analysis.unresolved_gaps))


@dataclass(frozen=True)
class ArgumentPrediction:
    prediction_id: str
    model_id: str
    baseline_identity: str
    root_claim: str
    mode: str
    expected_state: str
    node_id: str | None
    confidence: float | None
    max_size: int
    protected_claim_ids: tuple[str, ...]
    frozen_at: str
    task_id: str = ""
    purpose: str = ""
    coverage_ids: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    iteration: int = 0
    max_iterations: int = 8
    prior_open_gap_ids: tuple[str, ...] = ()
    holdout_claim_ids: tuple[str, ...] = ()
    schema_version: str = ARGUMENT_PREDICTION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != ARGUMENT_PREDICTION_SCHEMA:
            raise ValueError(
                "stale_prediction: re-freeze"
            )
        if not self.prediction_id:
            raise ValueError("prediction_id must not be empty")
        if not self.model_id:
            raise ValueError("model_id must not be empty")
        if not self.baseline_identity.startswith("sha256:"):
            raise ValueError("baseline_identity must be a sha256 digest")
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
        if len(set(self.coverage_ids)) != len(self.coverage_ids):
            raise ValueError("coverage_ids must not contain duplicates")
        if self.iteration < 0 or self.max_iterations < 1:
            raise ValueError("iteration must be non-negative and max_iterations must be positive")
        if len(set(self.prior_open_gap_ids)) != len(self.prior_open_gap_ids):
            raise ValueError("prior_open_gap_ids must not contain duplicates")
        if len(set(self.holdout_claim_ids)) != len(self.holdout_claim_ids):
            raise ValueError("holdout_claim_ids must not contain duplicates")
        if set(self.holdout_claim_ids) & set(self.protected_claim_ids):
            raise ValueError("holdout claims must be distinct from protected claims")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "prediction_id": self.prediction_id,
            "model_id": self.model_id,
            "baseline_identity": self.baseline_identity,
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
            "assumptions": list(self.assumptions),
            "unknowns": list(self.unknowns),
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "prior_open_gap_ids": list(self.prior_open_gap_ids),
            "holdout_claim_ids": list(self.holdout_claim_ids),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ArgumentPrediction":
        return cls(
            schema_version=str(raw.get("schema_version", "")),
            prediction_id=str(raw.get("prediction_id", "")),
            model_id=str(raw.get("model_id", "")),
            baseline_identity=str(raw.get("baseline_identity", "")),
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
            assumptions=tuple(str(item) for item in (raw.get("assumptions") or ())),
            unknowns=tuple(str(item) for item in (raw.get("unknowns") or ())),
            iteration=int(raw.get("iteration", 0)),
            max_iterations=int(raw.get("max_iterations", 8)),
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
class ArgumentIterationResult:
    prediction: ArgumentPrediction
    baseline_observation: ArgumentObservation
    baseline_comparison: ArgumentPredictionComparison
    candidate_observation: ArgumentObservation | None
    candidate_comparison: ArgumentPredictionComparison | None
    protected_claims: tuple[ProtectedClaimRevalidation, ...]
    holdout_claims: tuple[ProtectedClaimRevalidation, ...]
    requested_disposition: str
    effective_disposition: str
    disposition_reason: str
    completed_at: str
    schema_version: str = ARGUMENT_ITERATION_RESULT_SCHEMA
    input_gap_ids: tuple[str, ...] = ()
    resolved_gap_ids: tuple[str, ...] = ()
    persisted_gap_ids: tuple[str, ...] = ()
    introduced_gap_ids: tuple[str, ...] = ()
    open_gap_ids: tuple[str, ...] = ()
    gap_transitions: Mapping[str, str] = None  # type: ignore[assignment]
    next_actions: tuple[str, ...] = ()
    terminal_reason: str = "continue_iteration"
    progressed: bool = False

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
            "requested_disposition": self.requested_disposition,
            "effective_disposition": self.effective_disposition,
            "disposition_reason": self.disposition_reason,
            "completed_at": self.completed_at,
            "input_gap_ids": list(self.input_gap_ids),
            "resolved_gap_ids": list(self.resolved_gap_ids),
            "persisted_gap_ids": list(self.persisted_gap_ids),
            "introduced_gap_ids": list(self.introduced_gap_ids),
            "open_gap_ids": list(self.open_gap_ids),
            "gap_transitions": dict(self.gap_transitions or {}),
            "next_actions": list(self.next_actions),
            "terminal_reason": self.terminal_reason,
            "progressed": self.progressed,
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
    task_id: str = "",
    purpose: str = "",
    coverage_ids: Sequence[str] = (),
    assumptions: Sequence[str] = (),
    unknowns: Sequence[str] = (),
    iteration: int = 0,
    max_iterations: int = 8,
    prior_open_gap_ids: Sequence[str] = (),
    holdout_claim_ids: Sequence[str] = (),
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
    missing_coverage = [item for item in coverage if item not in model.nodes]
    if missing_coverage:
        raise ValueError("coverage nodes are missing from the model: " + ", ".join(missing_coverage))
    return ArgumentPrediction(
        prediction_id=prediction_id or f"prediction-{uuid.uuid4().hex}",
        model_id=model.id,
        baseline_identity=baseline_identity(model.canonical_dict()),
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
        assumptions=tuple(str(item) for item in assumptions),
        unknowns=tuple(str(item) for item in unknowns),
        iteration=iteration,
        max_iterations=max_iterations,
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
        model_digest=baseline_identity(model.canonical_dict()),
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
    require_prediction_identity(prediction.baseline_identity, baseline_identity(model.canonical_dict()))


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
    baseline: LogicModel,
    prediction: ArgumentPrediction,
    *,
    candidate: LogicModel | None = None,
    decision: str = "reject",
) -> ArgumentIterationResult:
    """Observe a prediction and decide on a candidate; never writes model files."""

    if decision not in {"accept", "reject"}:
        raise ValueError("decision must be 'accept' or 'reject'")
    validate_prediction_binding(baseline, prediction)
    baseline_observation = observe_argument_prediction(baseline, prediction)
    baseline_comparison = compare_argument_prediction(prediction, baseline_observation)
    baseline_gaps = tuple(
        sorted(
            set(_argument_open_gaps(baseline, baseline_observation, prediction))
            | set(_native_depth(baseline, prediction))
        )
    )

    def terminal_for(gaps: Sequence[str], *, external: bool = False) -> str:
        return select_terminal(closed=not gaps, iteration=prediction.iteration,
                               max_iterations=prediction.max_iterations,
                               stalled=set(gaps) == set(prediction.prior_open_gap_ids) and prediction.iteration > 0,
                               external=external)


    def make_result(
        *,
        candidate_observation: ArgumentObservation | None,
        candidate_comparison: ArgumentPredictionComparison | None,
        protected: tuple[ProtectedClaimRevalidation, ...],
        holdout: tuple[ProtectedClaimRevalidation, ...],
        effective: str,
        reason: str,
        gaps: Sequence[str],
        terminal: str,
    ) -> ArgumentIterationResult:
        resolved, persisted, introduced, transitions = gap_lineage(baseline_gaps, gaps)
        return ArgumentIterationResult(
            prediction=prediction,
            baseline_observation=baseline_observation,
            baseline_comparison=baseline_comparison,
            candidate_observation=candidate_observation,
            candidate_comparison=candidate_comparison,
            protected_claims=protected,
            holdout_claims=holdout,
            requested_disposition=decision,
            effective_disposition=effective,
            disposition_reason=reason,
            completed_at=utc_now(),
            input_gap_ids=baseline_gaps,
            resolved_gap_ids=resolved,
            persisted_gap_ids=persisted,
            introduced_gap_ids=introduced,
            open_gap_ids=tuple(sorted(gaps)),
            gap_transitions=transitions,
            next_actions=("deepen_logic_model",) if gaps else ("no_model_change_needed",),
            terminal_reason=terminal,
            progressed=bool(resolved),
        )

    if baseline_comparison.matches and not baseline_gaps:
        holdout = revalidate_protected_claims(
            baseline, baseline, prediction.holdout_claim_ids
        )
        return make_result(
            candidate_observation=None,
            candidate_comparison=None,
            protected=(),
            holdout=holdout,
            effective="no_revision_needed",
            reason="baseline prediction and current native depth pass",
            gaps=(),
            terminal="model_closed_for_task",
        )

    if candidate is None:
        gaps = set(baseline_gaps)
        external = not baseline_comparison.matches
        if external:
            gaps.add("candidate-model-required")
        return make_result(
            candidate_observation=None,
            candidate_comparison=None,
            protected=(),
            holdout=(),
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
    gaps = set(_argument_open_gaps(candidate, candidate_observation, prediction)) | set(
        _native_depth(candidate, prediction)
    )
    protected = revalidate_protected_claims(baseline, candidate, prediction.protected_claim_ids)
    holdout = revalidate_protected_claims(baseline, candidate, prediction.holdout_claim_ids)
    if not candidate_comparison.matches:
        gaps.add("candidate-prediction-mismatch")
    if any(not item.passed for item in protected):
        gaps.add("protected-claim-regression")
    if any(not item.passed for item in holdout):
        gaps.add("independent-holdout-regression")

    if decision == "accept" and not gaps:
        return make_result(
            candidate_observation=candidate_observation,
            candidate_comparison=candidate_comparison,
            protected=protected,
            holdout=holdout,
            effective="accepted",
            reason="candidate prediction, native depth, protected claims and holdout claims pass",
            gaps=(),
            terminal="model_closed_for_task",
        )

    reasons: list[str] = []
    if decision == "reject":
        reasons.append("caller requested rejection")
        gaps.add("candidate-rejected")
    if gaps:
        reasons.append("candidate retains current LogicGuard closure gaps")
    ordered_gaps = tuple(sorted(gaps))
    return make_result(
        candidate_observation=candidate_observation,
        candidate_comparison=candidate_comparison,
        protected=protected,
        holdout=holdout,
        effective="rejected" if decision == "reject" else "continue_iteration",
        reason="; ".join(reasons),
        gaps=ordered_gaps,
        terminal=terminal_for(ordered_gaps, external=decision == "reject"),
    )




__all__ = [
    "ARGUMENT_ITERATION_RESULT_SCHEMA",
    "ARGUMENT_PREDICTION_SCHEMA",
    "SUPPORTED_PREDICTION_MODES",
    "ArgumentIterationResult",
    "ArgumentObservation",
    "ArgumentPrediction",
    "ArgumentPredictionComparison",
    "ProtectedClaimRevalidation",
    "compare_argument_prediction",
    "freeze_argument_prediction",
    "observe_argument_prediction",
    "revalidate_protected_claims",
    "run_argument_iteration",
    "validate_prediction_binding",
]
