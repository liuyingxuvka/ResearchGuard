"""Task-local search prediction and non-overwriting belief-state iteration.

The coordinator reuses SourceGuard's existing observation update and replanning
path.  It never changes utility weights, qualification thresholds, or Guard
policy, and it never overwrites the baseline model: the candidate is written to
a new file, so a rollback is keeping (or restoring from git) the baseline file.
"""

from __future__ import annotations

import uuid
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


SEARCH_OUTCOME_PREDICTION_SCHEMA = "researchguard.source.search-outcome-prediction.v2"
SEARCH_ITERATION_RESULT_SCHEMA = "researchguard.source.search-iteration-result.v1"
GAP_REDUCTION_LEVELS = frozenset({"none", "partial", "closed"})


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
    task_id: str = ""
    purpose: str = ""
    coverage_ids: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    iteration: int = 0
    max_iterations: int = 8
    prior_open_gap_ids: tuple[str, ...] = ()
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
        if len(set(self.coverage_ids)) != len(self.coverage_ids):
            raise ValueError("coverage_ids must not contain duplicates")
        if self.iteration < 0 or self.max_iterations < 1:
            raise ValueError("iteration must be non-negative and max_iterations must be positive")
        if len(set(self.prior_open_gap_ids)) != len(self.prior_open_gap_ids):
            raise ValueError("prior_open_gap_ids must not contain duplicates")

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
            "task_id": self.task_id,
            "purpose": self.purpose,
            "coverage_ids": list(self.coverage_ids),
            "assumptions": list(self.assumptions),
            "unknowns": list(self.unknowns),
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "prior_open_gap_ids": list(self.prior_open_gap_ids),
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
            task_id=str(raw.get("task_id", "")),
            purpose=str(raw.get("purpose", "")),
            coverage_ids=tuple(str(item) for item in (raw.get("coverage_ids") or ())),
            assumptions=tuple(str(item) for item in (raw.get("assumptions") or ())),
            unknowns=tuple(str(item) for item in (raw.get("unknowns") or ())),
            iteration=int(raw.get("iteration", 0)),
            max_iterations=int(raw.get("max_iterations", 8)),
            prior_open_gap_ids=tuple(str(item) for item in (raw.get("prior_open_gap_ids") or ())),
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
    depth_completed: bool
    scope_status_passed: bool
    status: str
    adequacy_status: str
    passed: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "depth_completed": self.depth_completed,
            "scope_status_passed": self.scope_status_passed,
            "status": self.status,
            "adequacy_status": self.adequacy_status,
            "passed": self.passed,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class SearchIterationResult:
    prediction: SearchOutcomePrediction
    realized_outcome: RealizedSearchOutcome
    prediction_error: SearchPredictionError
    candidate_review: SearchCandidateReview
    native_depth_revalidation: NativeDepthRevalidation
    requested_disposition: str
    effective_disposition: str
    disposition_reason: str
    completed_at: str
    schema_version: str = SEARCH_ITERATION_RESULT_SCHEMA
    input_gap_ids: tuple[str, ...] = ()
    resolved_gap_ids: tuple[str, ...] = ()
    persisted_gap_ids: tuple[str, ...] = ()
    introduced_gap_ids: tuple[str, ...] = ()
    open_gap_ids: tuple[str, ...] = ()
    gap_transitions: Mapping[str, str] | None = None
    next_actions: tuple[str, ...] = ()
    terminal_reason: str = "continue_iteration"
    progressed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "prediction": self.prediction.to_dict(),
            "realized_outcome": self.realized_outcome.to_dict(),
            "prediction_error": self.prediction_error.to_dict(),
            "candidate_review": self.candidate_review.to_dict(),
            "native_depth_revalidation": self.native_depth_revalidation.to_dict(),
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
    task_id: str = "",
    purpose: str = "",
    coverage_ids: Sequence[str] = (),
    assumptions: Sequence[str] = (),
    unknowns: Sequence[str] = (),
    iteration: int = 0,
    max_iterations: int = 8,
    prior_open_gap_ids: Sequence[str] = (),
) -> SearchOutcomePrediction:
    """Freeze expected search outcomes without applying any observation."""

    validate_model_guard_binding(baseline)
    action = _bound_action(baseline, action_id)
    if not action.target_gap_id or action.target_gap_id not in baseline.gap_by_id():
        raise ValueError("selected search action must target an existing gap")
    for gap_id in protected_gap_ids:
        if gap_id not in baseline.gap_by_id():
            raise ValueError(f"protected gap is missing from baseline: {gap_id}")
    coverage = tuple(str(item) for item in coverage_ids)
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
        task_id=task_id,
        purpose=purpose,
        coverage_ids=coverage,
        assumptions=tuple(str(item) for item in assumptions),
        unknowns=tuple(str(item) for item in unknowns),
        iteration=iteration,
        max_iterations=max_iterations,
        prior_open_gap_ids=tuple(str(item) for item in prior_open_gap_ids),
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
    observation: Observation | None,
    receipt: SourceDepthReceipt,
) -> NativeDepthRevalidation:
    """Check that native depth completed and passes the requested claim scope."""

    depth_completed = bool(
        receipt.planning_depth_completed
        and (receipt.observation_depth_completed if observation is not None else True)
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
    reasons: list[str] = []
    if not depth_completed:
        reasons.append("native planning and observation depth did not complete")
    if not scope_passed:
        reasons.append("native depth status does not pass the requested claim scope")
    passed = bool(depth_completed and scope_passed)
    return NativeDepthRevalidation(
        depth_completed=depth_completed,
        scope_status_passed=scope_passed,
        status=receipt.status,
        adequacy_status=receipt.adequacy_status,
        passed=passed,
        reasons=tuple(reasons),
    )


def affected_source_obligations(
    state: BeliefState,
    *,
    changed_source_ids: Sequence[str] = (),
    changed_anchor_ids: Sequence[str] = (),
) -> dict[str, object]:
    """Return the exact SourceGuard obligations that consume changed identities.

    This is an impact projection only.  It deliberately does not mutate a gap,
    rerun search, or broaden an unknown dependency into a run-all decision.
    """

    source_ids = set(changed_source_ids)
    anchor_ids = set(changed_anchor_ids)
    known_sources = state.source_by_id()
    known_anchors = {anchor.anchor_id: anchor for anchor in state.anchors}
    unknown_ids = sorted((source_ids - set(known_sources)) | (anchor_ids - set(known_anchors)))
    for anchor in state.anchors:
        if anchor.source_id in source_ids:
            anchor_ids.add(anchor.anchor_id)
    affected_gap_ids: set[str] = set()
    affected_claim_use_ids: set[str] = set()
    for anchor_id in anchor_ids:
        anchor = known_anchors.get(anchor_id)
        if anchor is not None:
            affected_claim_use_ids.update(anchor.claim_use_ids)
    for gap in state.gaps:
        consumed_ids = {
            *gap.closure_basis.source_ids,
            *gap.closure_basis.anchor_ids,
        }
        if source_ids & consumed_ids or anchor_ids & consumed_ids:
            affected_gap_ids.add(gap.gap_id)
        if gap.qualification.source_id in source_ids or gap.qualification.anchor_id in anchor_ids:
            affected_gap_ids.add(gap.gap_id)
    stop_map = state.metadata.get("stop_decisions_by_gap", {})
    if not isinstance(stop_map, Mapping):
        stop_map = {}
        unknown_ids.append("metadata:stop_decisions_by_gap")
    return {
        "changed_source_ids": sorted(source_ids),
        "changed_anchor_ids": sorted(anchor_ids),
        "affected_gap_ids": sorted(affected_gap_ids),
        "affected_stop_decision_ids": sorted(
            str(stop_map[gap_id]) for gap_id in affected_gap_ids if gap_id in stop_map
        ),
        "affected_claim_use_ids": sorted(affected_claim_use_ids),
        "unaffected_gap_ids": sorted(set(state.gap_by_id()) - affected_gap_ids),
        "unknown_dependency_ids": sorted(set(unknown_ids)),
        "unknown_ownership": bool(unknown_ids),
    }


def run_search_iteration(
    baseline: BeliefState,
    prediction: SearchOutcomePrediction,
    observation: Observation | None,
    *,
    actual_cost: float,
    decision: str = "reject",
    limit: int = 5,
    provider_status: str = "OBSERVATION_SUPPLIED",
) -> tuple[BeliefState, SearchIterationResult]:
    """Create and explicitly accept or reject one cloned candidate successor."""

    if decision not in {"accept", "reject"}:
        raise ValueError("decision must be 'accept' or 'reject'")
    validate_search_prediction_binding(baseline, prediction)
    normalized_provider = str(provider_status).upper()
    if normalized_provider not in {"OBSERVATION_SUPPLIED", "PROVIDER_UNAVAILABLE", "NOT_RUN"}:
        raise ValueError("unsupported provider_status")
    if observation is None and normalized_provider == "OBSERVATION_SUPPLIED":
        raise ValueError("OBSERVATION_SUPPLIED requires an observation")
    if observation is not None and normalized_provider != "OBSERVATION_SUPPLIED":
        raise ValueError("a supplied observation requires OBSERVATION_SUPPLIED")
    if observation is not None and observation.action_id != prediction.action_id:
        raise ValueError(
            "observation action_id must equal the frozen prediction action_id"
        )
    candidate, depth_receipt = apply_observation_and_replan(
        baseline,
        observation,
        provider_status=normalized_provider,
        limit=limit,
    )
    if observation is not None:
        realized = derive_realized_search_outcome(
            baseline,
            candidate,
            observation,
            prediction,
            actual_cost=actual_cost,
            limit=limit,
        )
    else:
        baseline_gap = baseline.gap_by_id()[prediction.target_gap_id]
        candidate_gap = candidate.gap_by_id()[prediction.target_gap_id]
        realized = RealizedSearchOutcome(
            action_id=prediction.action_id,
            target_gap_id=prediction.target_gap_id,
            gap_reduction=_gap_reduction(baseline_gap, candidate_gap),
            independent_lineage_found=False,
            counterevidence_found=False,
            actual_cost=float(actual_cost),
            observation_id="",
            observation_applied=False,
            new_source_ids=(),
            new_lineage_ids=(),
            updated_action_rank=None,
        )
    error = compare_search_outcome(prediction, realized)
    review = review_search_candidate(
        baseline, candidate, prediction.protected_gap_ids
    )
    native_review = revalidate_native_depth_receipt(
        baseline, candidate, observation, depth_receipt
    )
    candidate_gap_map = candidate.gap_by_id()
    coverage_gaps = {
        gap_id
        for gap_id in prediction.coverage_ids
        if gap_id not in candidate_gap_map
        or candidate_gap_map[gap_id].semantic_state != "closed"
    }
    open_gap_ids = sorted(
        {
            gap.gap_id
            for gap in candidate.gaps
            if gap.semantic_state != "closed"
        }
        | set(depth_receipt.unresolved_gap_ids)
        | coverage_gaps
    )
    can_close = decision == "accept" and review.passed and native_review.passed and not open_gap_ids
    if can_close:
        effective = "accepted"
        reason = (
            "native depth passes, weights are unchanged, and protected gaps pass"
        )
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
        if open_gap_ids:
            reasons.append("native SourceGuard gaps remain open")
        reason = "; ".join(reasons)
        if decision == "accept" and review.passed and native_review.passed and open_gap_ids:
            effective = "continue_iteration"
    addressable_action_ids = tuple(
        sorted(
            action.action_id
            for action in candidate.actions
            if action.status == "proposed" and action.target_gap_id in set(open_gap_ids)
        )
    )
    if can_close:
        terminal_reason = "model_closed_for_task"
    elif prediction.iteration >= prediction.max_iterations:
        terminal_reason = "iteration_limit"
    elif set(open_gap_ids) == set(prediction.prior_open_gap_ids) and prediction.iteration > 0:
        terminal_reason = "progress_stalled"
    elif normalized_provider == "PROVIDER_UNAVAILABLE":
        terminal_reason = "provider_access_required"
    elif open_gap_ids and not addressable_action_ids:
        terminal_reason = "finite_action_exhausted"
    elif decision == "reject":
        terminal_reason = "external_input_required"
    else:
        terminal_reason = "continue_iteration"
    before, after = set(prediction.prior_open_gap_ids), set(open_gap_ids)
    resolved_gap_ids = tuple(sorted(before - after))
    persisted_gap_ids = tuple(sorted(before & after))
    introduced_gap_ids = tuple(sorted(after - before))
    gap_transitions = {
        **{gap: "resolved" for gap in resolved_gap_ids},
        **{gap: "persisted" for gap in persisted_gap_ids},
        **{gap: "introduced" for gap in introduced_gap_ids},
    }
    result = SearchIterationResult(
        prediction=prediction,
        realized_outcome=realized,
        prediction_error=error,
        candidate_review=review,
        native_depth_revalidation=native_review,
        requested_disposition=decision,
        effective_disposition=effective,
        disposition_reason=reason,
        completed_at=utc_now(),
        input_gap_ids=prediction.prior_open_gap_ids,
        resolved_gap_ids=resolved_gap_ids,
        persisted_gap_ids=persisted_gap_ids,
        introduced_gap_ids=introduced_gap_ids,
        open_gap_ids=tuple(open_gap_ids),
        gap_transitions=gap_transitions,
        next_actions=(
            addressable_action_ids
            if addressable_action_ids
            else (
                ("request_provider_access",)
                if terminal_reason == "provider_access_required"
                else (("revise_search_space",) if open_gap_ids else ("no_model_change_needed",))
            )
        ),
        terminal_reason=terminal_reason,
        progressed=bool(resolved_gap_ids or introduced_gap_ids or (prediction.iteration == 0 and observation is not None)),
    )
    return candidate, result


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


def _required_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


__all__ = [
    "GAP_REDUCTION_LEVELS",
    "NativeDepthRevalidation",
    "SEARCH_ITERATION_RESULT_SCHEMA",
    "SEARCH_OUTCOME_PREDICTION_SCHEMA",
    "ProtectedGapRevalidation",
    "RealizedSearchOutcome",
    "SearchCandidateReview",
    "SearchIterationResult",
    "SearchOutcomePrediction",
    "SearchPredictionError",
    "compare_search_outcome",
    "derive_realized_search_outcome",
    "freeze_search_outcome_prediction",
    "affected_source_obligations",
    "revalidate_native_depth_receipt",
    "review_search_candidate",
    "run_search_iteration",
    "validate_search_prediction_binding",
]
