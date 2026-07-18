"""Task-local search prediction and non-overwriting belief-state iteration.

The coordinator reuses SourceGuard's existing observation update and replanning
path.  It never changes utility weights, qualification thresholds, or Guard
policy.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .depth import apply_observation_and_replan, model_fingerprint
from .planner import plan_next_actions
from .schema import (
    BeliefState,
    Gap,
    Observation,
    SearchAction,
    SourceDepthReceipt,
    to_plain,
    utc_now,
    validate_model_guard_binding,
)


SEARCH_OUTCOME_PREDICTION_SCHEMA = "researchguard.source.search-outcome-prediction.v1"
SEARCH_ITERATION_RECEIPT_SCHEMA = "researchguard.source.search-iteration-receipt.v1"
SEARCH_ROLLBACK_RECEIPT_SCHEMA = "researchguard.source.search-rollback-receipt.v1"
GAP_REDUCTION_LEVELS = frozenset({"none", "partial", "closed"})
SEARCH_ITERATION_CLAIM_BOUNDARY = (
    "This receipt proves one task-local search-outcome prediction, one supplied "
    "observation update, deterministic error reporting, and the declared candidate "
    "disposition. It does not prove source truth or change SourceGuard policy."
)


@dataclass(frozen=True)
class SearchOutcomePrediction:
    prediction_id: str
    baseline_fingerprint: str
    action_id: str
    target_gap_id: str
    expected_gap_reduction: str
    expected_independent_lineage: bool
    expected_counterevidence: bool
    expected_cost: float
    cost_tolerance: float
    protected_gap_ids: tuple[str, ...]
    frozen_at: str
    schema_version: str = SEARCH_OUTCOME_PREDICTION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != SEARCH_OUTCOME_PREDICTION_SCHEMA:
            raise ValueError(
                f"unsupported search prediction schema {self.schema_version!r}"
            )
        if not self.prediction_id:
            raise ValueError("prediction_id must not be empty")
        if not self.baseline_fingerprint:
            raise ValueError("baseline_fingerprint must not be empty")
        if not self.action_id or not self.target_gap_id:
            raise ValueError("action_id and target_gap_id must not be empty")
        if self.expected_gap_reduction not in GAP_REDUCTION_LEVELS:
            raise ValueError(
                f"unsupported expected gap reduction: {self.expected_gap_reduction}"
            )
        if not 0.0 <= self.expected_cost <= 1.0:
            raise ValueError("expected_cost must be between 0 and 1")
        if not 0.0 <= self.cost_tolerance <= 1.0:
            raise ValueError("cost_tolerance must be between 0 and 1")
        if len(set(self.protected_gap_ids)) != len(self.protected_gap_ids):
            raise ValueError("protected_gap_ids must not contain duplicates")
        if self.target_gap_id in self.protected_gap_ids:
            raise ValueError("target gap cannot also be protected")
        if not self.frozen_at:
            raise ValueError("frozen_at must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "prediction_id": self.prediction_id,
            "baseline_fingerprint": self.baseline_fingerprint,
            "action_id": self.action_id,
            "target_gap_id": self.target_gap_id,
            "expected_gap_reduction": self.expected_gap_reduction,
            "expected_independent_lineage": self.expected_independent_lineage,
            "expected_counterevidence": self.expected_counterevidence,
            "expected_cost": self.expected_cost,
            "cost_tolerance": self.cost_tolerance,
            "protected_gap_ids": list(self.protected_gap_ids),
            "frozen_at": self.frozen_at,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "SearchOutcomePrediction":
        return cls(
            schema_version=str(raw.get("schema_version", "")),
            prediction_id=str(raw.get("prediction_id", "")),
            baseline_fingerprint=str(raw.get("baseline_fingerprint", "")),
            action_id=str(raw.get("action_id", "")),
            target_gap_id=str(raw.get("target_gap_id", "")),
            expected_gap_reduction=str(raw.get("expected_gap_reduction", "")),
            expected_independent_lineage=_required_bool(
                raw.get("expected_independent_lineage"),
                "expected_independent_lineage",
            ),
            expected_counterevidence=_required_bool(
                raw.get("expected_counterevidence"),
                "expected_counterevidence",
            ),
            expected_cost=float(raw.get("expected_cost", -1.0)),
            cost_tolerance=float(raw.get("cost_tolerance", -1.0)),
            protected_gap_ids=tuple(
                str(item) for item in (raw.get("protected_gap_ids") or ())
            ),
            frozen_at=str(raw.get("frozen_at", "")),
        )


@dataclass(frozen=True)
class RealizedSearchOutcome:
    action_id: str
    target_gap_id: str
    gap_reduction: str
    independent_lineage_found: bool
    counterevidence_found: bool
    actual_cost: float
    observation_id: str
    observation_applied: bool
    new_source_ids: tuple[str, ...]
    new_lineage_ids: tuple[str, ...]
    updated_action_rank: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "target_gap_id": self.target_gap_id,
            "gap_reduction": self.gap_reduction,
            "independent_lineage_found": self.independent_lineage_found,
            "counterevidence_found": self.counterevidence_found,
            "actual_cost": self.actual_cost,
            "observation_id": self.observation_id,
            "observation_applied": self.observation_applied,
            "new_source_ids": list(self.new_source_ids),
            "new_lineage_ids": list(self.new_lineage_ids),
            "updated_action_rank": self.updated_action_rank,
        }


@dataclass(frozen=True)
class SearchPredictionError:
    gap_reduction_matches: bool
    lineage_independence_matches: bool
    counterevidence_matches: bool
    cost_error: float
    cost_within_tolerance: bool
    overall_matches: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "gap_reduction_matches": self.gap_reduction_matches,
            "lineage_independence_matches": self.lineage_independence_matches,
            "counterevidence_matches": self.counterevidence_matches,
            "cost_error": self.cost_error,
            "cost_within_tolerance": self.cost_within_tolerance,
            "overall_matches": self.overall_matches,
        }


@dataclass(frozen=True)
class ProtectedGapRevalidation:
    gap_id: str
    status: str
    reason: str

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> dict[str, str]:
        return {"gap_id": self.gap_id, "status": self.status, "reason": self.reason}


@dataclass(frozen=True)
class SearchCandidateReview:
    weights_unchanged: bool
    protected_gaps: tuple[ProtectedGapRevalidation, ...]
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "weights_unchanged": self.weights_unchanged,
            "protected_gaps": [item.to_dict() for item in self.protected_gaps],
            "passed": self.passed,
        }


@dataclass(frozen=True)
class NativeDepthRevalidation:
    receipt_version_current: bool
    baseline_binding_current: bool
    candidate_binding_current: bool
    observation_binding_current: bool
    depth_completed: bool
    scope_status_passed: bool
    status: str
    adequacy_status: str
    passed: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_version_current": self.receipt_version_current,
            "baseline_binding_current": self.baseline_binding_current,
            "candidate_binding_current": self.candidate_binding_current,
            "observation_binding_current": self.observation_binding_current,
            "depth_completed": self.depth_completed,
            "scope_status_passed": self.scope_status_passed,
            "status": self.status,
            "adequacy_status": self.adequacy_status,
            "passed": self.passed,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class SearchIterationReceipt:
    prediction: SearchOutcomePrediction
    realized_outcome: RealizedSearchOutcome
    prediction_error: SearchPredictionError
    candidate_review: SearchCandidateReview
    native_depth_revalidation: NativeDepthRevalidation
    native_depth_receipt: Mapping[str, Any]
    candidate_fingerprint: str
    requested_disposition: str
    effective_disposition: str
    disposition_reason: str
    selected_model_fingerprint: str
    completed_at: str
    schema_version: str = SEARCH_ITERATION_RECEIPT_SCHEMA
    claim_boundary: str = SEARCH_ITERATION_CLAIM_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "prediction": self.prediction.to_dict(),
            "realized_outcome": self.realized_outcome.to_dict(),
            "prediction_error": self.prediction_error.to_dict(),
            "candidate_review": self.candidate_review.to_dict(),
            "native_depth_revalidation": self.native_depth_revalidation.to_dict(),
            "native_depth_receipt": dict(self.native_depth_receipt),
            "candidate_fingerprint": self.candidate_fingerprint,
            "requested_disposition": self.requested_disposition,
            "effective_disposition": self.effective_disposition,
            "disposition_reason": self.disposition_reason,
            "selected_model_fingerprint": self.selected_model_fingerprint,
            "completed_at": self.completed_at,
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class SearchRollbackReceipt:
    accepted_receipt_fingerprint: str
    accepted_candidate_fingerprint: str
    restored_baseline_fingerprint: str
    effective_disposition: str
    completed_at: str
    schema_version: str = SEARCH_ROLLBACK_RECEIPT_SCHEMA
    claim_boundary: str = SEARCH_ITERATION_CLAIM_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "accepted_receipt_fingerprint": self.accepted_receipt_fingerprint,
            "accepted_candidate_fingerprint": self.accepted_candidate_fingerprint,
            "restored_baseline_fingerprint": self.restored_baseline_fingerprint,
            "effective_disposition": self.effective_disposition,
            "completed_at": self.completed_at,
            "claim_boundary": self.claim_boundary,
        }


def freeze_search_outcome_prediction(
    baseline: BeliefState,
    *,
    action_id: str,
    expected_gap_reduction: str,
    expected_independent_lineage: bool,
    expected_counterevidence: bool,
    expected_cost: float,
    cost_tolerance: float = 0.1,
    protected_gap_ids: Sequence[str] = (),
    prediction_id: str | None = None,
) -> SearchOutcomePrediction:
    """Freeze expected search outcomes without applying any observation."""

    validate_model_guard_binding(baseline)
    action = _bound_action(baseline, action_id)
    if not action.target_gap_id or action.target_gap_id not in baseline.gap_by_id():
        raise ValueError("selected search action must target an existing gap")
    for gap_id in protected_gap_ids:
        if gap_id not in baseline.gap_by_id():
            raise ValueError(f"protected gap is missing from baseline: {gap_id}")
    return SearchOutcomePrediction(
        prediction_id=prediction_id or f"prediction-{uuid.uuid4().hex}",
        baseline_fingerprint=model_fingerprint(baseline),
        action_id=action.action_id,
        target_gap_id=action.target_gap_id,
        expected_gap_reduction=expected_gap_reduction,
        expected_independent_lineage=bool(expected_independent_lineage),
        expected_counterevidence=bool(expected_counterevidence),
        expected_cost=float(expected_cost),
        cost_tolerance=float(cost_tolerance),
        protected_gap_ids=tuple(str(item) for item in protected_gap_ids),
        frozen_at=utc_now(),
    )


def validate_search_prediction_binding(
    baseline: BeliefState,
    prediction: SearchOutcomePrediction,
) -> SearchAction:
    validate_model_guard_binding(baseline)
    actual = model_fingerprint(baseline)
    if actual != prediction.baseline_fingerprint:
        raise ValueError(
            "stale search prediction: baseline fingerprint changed "
            f"from {prediction.baseline_fingerprint} to {actual}"
        )
    action = _bound_action(baseline, prediction.action_id)
    if action.target_gap_id != prediction.target_gap_id:
        raise ValueError("prediction target gap no longer matches the selected action")
    return action


def derive_realized_search_outcome(
    baseline: BeliefState,
    candidate: BeliefState,
    observation: Observation,
    prediction: SearchOutcomePrediction,
    *,
    actual_cost: float,
    limit: int = 5,
) -> RealizedSearchOutcome:
    if observation.action_id != prediction.action_id:
        raise ValueError(
            "observation action_id must equal the frozen prediction action_id"
        )
    cost = float(actual_cost)
    if not 0.0 <= cost <= 1.0:
        raise ValueError("actual_cost must be between 0 and 1")
    baseline_gap = baseline.gap_by_id().get(prediction.target_gap_id)
    candidate_gap = candidate.gap_by_id().get(prediction.target_gap_id)
    if baseline_gap is None or candidate_gap is None:
        raise ValueError("target gap must exist in both baseline and candidate")

    baseline_source_ids = {source.source_id for source in baseline.sources}
    baseline_lineages = {
        source.lineage_id for source in baseline.sources if source.lineage_id
    }
    new_sources = [
        source
        for source in observation.observed_sources
        if source.source_id not in baseline_source_ids
    ]
    new_lineages = sorted(
        {
            source.lineage_id
            for source in new_sources
            if source.lineage_id and source.lineage_id not in baseline_lineages
        }
    )
    counterevidence = bool(
        observation.contradictions
        or any(
            source.source_role in {"counter_evidence", "limiting_evidence"}
            for source in new_sources
        )
    )
    after_plan = plan_next_actions(candidate, limit=limit)
    rank_by_id = {
        action.action_id: index + 1
        for index, action in enumerate(after_plan.selected_actions)
    }
    return RealizedSearchOutcome(
        action_id=prediction.action_id,
        target_gap_id=prediction.target_gap_id,
        gap_reduction=_gap_reduction(baseline_gap, candidate_gap),
        independent_lineage_found=bool(new_lineages),
        counterevidence_found=counterevidence,
        actual_cost=cost,
        observation_id=observation.observation_id,
        observation_applied=any(
            item.observation_id == observation.observation_id
            for item in candidate.observations
        ),
        new_source_ids=tuple(sorted(source.source_id for source in new_sources)),
        new_lineage_ids=tuple(new_lineages),
        updated_action_rank=rank_by_id.get(prediction.action_id),
    )


def compare_search_outcome(
    prediction: SearchOutcomePrediction,
    realized: RealizedSearchOutcome,
) -> SearchPredictionError:
    gap_matches = prediction.expected_gap_reduction == realized.gap_reduction
    lineage_matches = (
        prediction.expected_independent_lineage
        == realized.independent_lineage_found
    )
    counter_matches = (
        prediction.expected_counterevidence == realized.counterevidence_found
    )
    cost_error = round(abs(prediction.expected_cost - realized.actual_cost), 6)
    cost_matches = cost_error <= prediction.cost_tolerance
    return SearchPredictionError(
        gap_reduction_matches=gap_matches,
        lineage_independence_matches=lineage_matches,
        counterevidence_matches=counter_matches,
        cost_error=cost_error,
        cost_within_tolerance=cost_matches,
        overall_matches=gap_matches
        and lineage_matches
        and counter_matches
        and cost_matches,
    )


def review_search_candidate(
    baseline: BeliefState,
    candidate: BeliefState,
    protected_gap_ids: Sequence[str],
) -> SearchCandidateReview:
    validate_model_guard_binding(candidate)
    rows: list[ProtectedGapRevalidation] = []
    before = baseline.gap_by_id()
    after = candidate.gap_by_id()
    for gap_id in protected_gap_ids:
        if gap_id not in before or gap_id not in after:
            rows.append(
                ProtectedGapRevalidation(
                    gap_id=gap_id,
                    status="fail",
                    reason="protected gap is missing from baseline or candidate",
                )
            )
            continue
        unchanged = to_plain(before[gap_id]) == to_plain(after[gap_id])
        rows.append(
            ProtectedGapRevalidation(
                gap_id=gap_id,
                status="pass" if unchanged else "fail",
                reason=(
                    "protected gap state is unchanged"
                    if unchanged
                    else "protected gap state changed in candidate"
                ),
            )
        )
    weights_unchanged = baseline.weights == candidate.weights
    return SearchCandidateReview(
        weights_unchanged=weights_unchanged,
        protected_gaps=tuple(rows),
        passed=weights_unchanged and all(item.passed for item in rows),
    )


def revalidate_native_depth_receipt(
    baseline: BeliefState,
    candidate: BeliefState,
    observation: Observation,
    receipt: SourceDepthReceipt,
) -> NativeDepthRevalidation:
    """Fail closed unless native depth covers this exact candidate update."""

    baseline_current = receipt.model_fingerprint == model_fingerprint(baseline)
    candidate_current = (
        receipt.result_model_fingerprint == model_fingerprint(candidate)
    )
    observation_current = bool(
        receipt.provider_status == "OBSERVATION_SUPPLIED"
        and receipt.observation_status == "APPLIED"
        and receipt.observations_used == [observation.observation_id]
    )
    depth_completed = bool(
        receipt.planning_depth_completed and receipt.observation_depth_completed
    )
    requested_scope = baseline.depth_policy.requested_claim_scope
    if requested_scope == "broad":
        scope_passed = bool(
            receipt.requested_claim_scope == "broad"
            and receipt.covered_claim_scope == "broad"
            and receipt.status == "pass"
            and receipt.adequacy_status == "pass"
            and receipt.broad_claim_licensed
        )
    else:
        scope_passed = bool(
            receipt.requested_claim_scope == requested_scope
            and receipt.covered_claim_scope in {"bounded", "broad"}
            and receipt.status in {"bounded", "pass"}
            and receipt.adequacy_status in {"bounded", "pass"}
        )
    version_current = receipt.receipt_version == "researchguard.source.depth.v2"
    reasons: list[str] = []
    if not version_current:
        reasons.append("native depth receipt version is not current")
    if not baseline_current:
        reasons.append("native depth receipt is not bound to the baseline")
    if not candidate_current:
        reasons.append("native depth receipt is not bound to the candidate")
    if not observation_current:
        reasons.append("native depth receipt is not bound to the supplied observation")
    if not depth_completed:
        reasons.append("native planning and observation depth did not complete")
    if not scope_passed:
        reasons.append("native depth status does not pass the requested claim scope")
    passed = bool(
        version_current
        and baseline_current
        and candidate_current
        and observation_current
        and depth_completed
        and scope_passed
    )
    return NativeDepthRevalidation(
        receipt_version_current=version_current,
        baseline_binding_current=baseline_current,
        candidate_binding_current=candidate_current,
        observation_binding_current=observation_current,
        depth_completed=depth_completed,
        scope_status_passed=scope_passed,
        status=receipt.status,
        adequacy_status=receipt.adequacy_status,
        passed=passed,
        reasons=tuple(reasons),
    )


def run_search_iteration(
    baseline: BeliefState,
    prediction: SearchOutcomePrediction,
    observation: Observation,
    *,
    actual_cost: float,
    decision: str = "reject",
    limit: int = 5,
) -> tuple[BeliefState, SearchIterationReceipt]:
    """Create and explicitly accept or reject one cloned candidate successor."""

    if decision not in {"accept", "reject"}:
        raise ValueError("decision must be 'accept' or 'reject'")
    validate_search_prediction_binding(baseline, prediction)
    if observation.action_id != prediction.action_id:
        raise ValueError(
            "observation action_id must equal the frozen prediction action_id"
        )
    candidate, depth_receipt = apply_observation_and_replan(
        baseline,
        observation,
        provider_status="OBSERVATION_SUPPLIED",
        limit=limit,
    )
    realized = derive_realized_search_outcome(
        baseline,
        candidate,
        observation,
        prediction,
        actual_cost=actual_cost,
        limit=limit,
    )
    error = compare_search_outcome(prediction, realized)
    review = review_search_candidate(
        baseline, candidate, prediction.protected_gap_ids
    )
    native_review = revalidate_native_depth_receipt(
        baseline, candidate, observation, depth_receipt
    )
    candidate_fingerprint = model_fingerprint(candidate)
    if decision == "accept" and review.passed and native_review.passed:
        effective = "accepted"
        reason = (
            "candidate bindings and native depth receipt are current, weights are "
            "unchanged, and protected gaps pass"
        )
        selected_fingerprint = candidate_fingerprint
    else:
        effective = "rejected"
        reasons: list[str] = []
        if decision == "reject":
            reasons.append("caller requested rejection")
        if not review.weights_unchanged:
            reasons.append("candidate changed the global weight vector")
        if any(not item.passed for item in review.protected_gaps):
            reasons.append("one or more protected gaps changed")
        if not native_review.passed:
            reasons.extend(native_review.reasons)
        reason = "; ".join(reasons)
        selected_fingerprint = prediction.baseline_fingerprint
    receipt = SearchIterationReceipt(
        prediction=prediction,
        realized_outcome=realized,
        prediction_error=error,
        candidate_review=review,
        native_depth_revalidation=native_review,
        native_depth_receipt=to_plain(depth_receipt),
        candidate_fingerprint=candidate_fingerprint,
        requested_disposition=decision,
        effective_disposition=effective,
        disposition_reason=reason,
        selected_model_fingerprint=selected_fingerprint,
        completed_at=utc_now(),
    )
    return candidate, receipt


def rollback_search_iteration(
    baseline: BeliefState,
    accepted_receipt: Mapping[str, Any],
) -> tuple[BeliefState, SearchRollbackReceipt]:
    """Return a new baseline-equivalent projection after verifying acceptance."""

    validate_model_guard_binding(baseline)
    if accepted_receipt.get("schema_version") != SEARCH_ITERATION_RECEIPT_SCHEMA:
        raise ValueError("rollback requires a current search iteration receipt")
    if accepted_receipt.get("effective_disposition") != "accepted":
        raise ValueError("rollback requires an accepted search iteration receipt")
    prediction = accepted_receipt.get("prediction")
    if not isinstance(prediction, Mapping):
        raise ValueError("accepted receipt is missing its frozen prediction")
    baseline_fingerprint = model_fingerprint(baseline)
    if prediction.get("baseline_fingerprint") != baseline_fingerprint:
        raise ValueError("accepted receipt is not bound to the supplied baseline")
    candidate_fingerprint = str(accepted_receipt.get("candidate_fingerprint", ""))
    if not candidate_fingerprint:
        raise ValueError("accepted receipt is missing candidate fingerprint")
    restored = deepcopy(baseline)
    receipt = SearchRollbackReceipt(
        accepted_receipt_fingerprint=_mapping_fingerprint(accepted_receipt),
        accepted_candidate_fingerprint=candidate_fingerprint,
        restored_baseline_fingerprint=model_fingerprint(restored),
        effective_disposition="rolled_back",
        completed_at=utc_now(),
    )
    return restored, receipt


def _bound_action(baseline: BeliefState, action_id: str) -> SearchAction:
    action = baseline.action_by_id().get(action_id)
    if action is None:
        raise ValueError(f"selected search action is missing from baseline: {action_id}")
    return action


def _gap_reduction(before: Gap, after: Gap) -> str:
    if after.semantic_state == "closed":
        return "closed"
    if to_plain(before) != to_plain(after):
        return "partial"
    return "none"


def _mapping_fingerprint(value: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _required_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


__all__ = [
    "GAP_REDUCTION_LEVELS",
    "NativeDepthRevalidation",
    "SEARCH_ITERATION_CLAIM_BOUNDARY",
    "SEARCH_ITERATION_RECEIPT_SCHEMA",
    "SEARCH_OUTCOME_PREDICTION_SCHEMA",
    "SEARCH_ROLLBACK_RECEIPT_SCHEMA",
    "ProtectedGapRevalidation",
    "RealizedSearchOutcome",
    "SearchCandidateReview",
    "SearchIterationReceipt",
    "SearchOutcomePrediction",
    "SearchPredictionError",
    "SearchRollbackReceipt",
    "compare_search_outcome",
    "derive_realized_search_outcome",
    "freeze_search_outcome_prediction",
    "revalidate_native_depth_receipt",
    "review_search_candidate",
    "rollback_search_iteration",
    "run_search_iteration",
    "validate_search_prediction_binding",
]
