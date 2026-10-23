"""Task-local prediction, observation, and reversible storyline revision.

This module owns lifecycle integrity only.  It never scores a storyline and
never changes TraceGuard's inference policy.  Candidate evaluation is delegated
to the canonical :func:`researchguard.trace.evaluator.evaluate_model` entry point.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from ..gap_lineage import gap_lineage

from .evaluator import evaluate_model
from .storyline_depth import evaluate_storyline_depth
from .inference.types import fingerprint
from .loader import load_model
from .schema import SourceRecord, EvidenceItem, EventCandidate, HypothesisEvidenceLink, TraceGuardModel
from .validation import validate_references


PREDICTION_SCHEMA = "researchguard.trace.task_prediction.v2"
OBSERVATION_SCHEMA = "researchguard.trace.evidence_batch_observation.v2"
COMPARISON_SCHEMA = "researchguard.trace.prediction_observation_comparison.v2"
REVISION_SCHEMA = "researchguard.trace.candidate_storyline_revision.v2"
VALID_TARGET_KINDS = {"storyline", "hypothesis"}
VALID_PREDICTION_KINDS = {"evidence_footprint", "future_event"}
VALID_QUALITY = {"valid", "invalid", "access_gap"}
VALID_DIRECTIONS = {"weaken", "strengthen", "unchanged"}
_OBSERVATION_RECORDS = (
    ("new_sources", "sources", SourceRecord, "source_id"),
    ("new_evidence", "evidence", EvidenceItem, "evidence_id"),
    ("new_events", "events", EventCandidate, "event_id"),
    ("new_links", "hypothesis_evidence_links", HypothesisEvidenceLink, "link_id"),
)


class TaskIterationError(ValueError):
    """Raised when task-local lifecycle evidence is missing or stale."""


def _sha256_file(path: str | Path) -> str:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise TaskIterationError(f"required file does not exist: {resolved}")
    return hashlib.sha256(resolved.read_bytes()).hexdigest()


def _parse_timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TaskIterationError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise TaskIterationError(f"{field} must include a timezone")
    return parsed


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return tuple(result)


def _load_mapping(path: str | Path) -> dict[str, Any]:
    resolved = Path(path)
    if not resolved.is_file():
        raise TaskIterationError(f"required lifecycle artifact does not exist: {resolved}")
    text = resolved.read_text(encoding="utf-8")
    data = json.loads(text) if resolved.suffix.lower() == ".json" else yaml.safe_load(text)
    if not isinstance(data, dict):
        raise TaskIterationError(f"{resolved} must contain one mapping")
    return data


def write_artifact(path: str | Path, payload: Mapping[str, Any]) -> None:
    """Write one immutable-style lifecycle artifact.

    Existing files are never overwritten.  A caller must choose a new path for
    a new prediction, observation comparison, or candidate revision.
    """

    target = Path(path)
    if target.exists():
        raise TaskIterationError(f"refusing to overwrite lifecycle artifact: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


@dataclass(frozen=True)
class PredictionSnapshot:
    schema_version: str
    prediction_id: str
    baseline_model_path: str
    baseline_model_sha256: str
    frozen_at: str
    target_kind: str
    target_id: str
    prediction_kind: str
    expected_evidence_ids: tuple[str, ...]
    expected_event_ids: tuple[str, ...]
    expected_event_order: tuple[str, ...]
    weakens_when: str
    factual_future_prediction_licensed: bool
    task_id: str = ""
    purpose: str = ""
    coverage_ids: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    iteration: int = 0
    max_iterations: int = 8
    prior_open_gap_ids: tuple[str, ...] = ()
    expected_direction: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PredictionSnapshot":
        if data.get("schema_version") != PREDICTION_SCHEMA:
            raise TaskIterationError(f"schema_version must equal {PREDICTION_SCHEMA}")
        target_kind = str(data.get("target_kind", ""))
        prediction_kind = str(data.get("prediction_kind", ""))
        expected_direction = str(data.get("expected_direction", ""))
        if expected_direction and expected_direction not in VALID_DIRECTIONS:
            raise TaskIterationError(f"invalid expected_direction: {expected_direction}")
        if target_kind not in VALID_TARGET_KINDS:
            raise TaskIterationError(f"invalid target_kind: {target_kind}")
        if prediction_kind not in VALID_PREDICTION_KINDS:
            raise TaskIterationError(f"invalid prediction_kind: {prediction_kind}")
        expected_evidence = _ordered_unique(data.get("expected_evidence_ids", []))
        expected_events = _ordered_unique(data.get("expected_event_ids", []))
        expected_order = tuple(str(item) for item in data.get("expected_event_order", []))
        task_id = str(data.get("task_id", "")).strip()
        coverage_ids = _ordered_unique(data.get("coverage_ids", []))
        iteration = int(data.get("iteration", 0))
        max_iterations = int(data.get("max_iterations", 8))
        if iteration < 0 or max_iterations < 1:
            raise TaskIterationError("iteration must be non-negative and max_iterations must be positive")
        if not expected_evidence and not expected_events:
            raise TaskIterationError(
                "prediction requires expected_evidence_ids or expected_event_ids"
            )
        if expected_order and set(expected_order) - set(expected_events):
            raise TaskIterationError(
                "expected_event_order may only contain expected_event_ids"
            )
        if bool(data.get("factual_future_prediction_licensed", False)):
            raise TaskIterationError(
                "task-local prediction snapshots cannot license factual future prediction"
            )
        payload = {
            "schema_version": PREDICTION_SCHEMA,
            "prediction_id": str(data.get("prediction_id", "")),
            "baseline_model_path": str(data.get("baseline_model_path", "")),
            "baseline_model_sha256": str(data.get("baseline_model_sha256", "")),
            "frozen_at": str(data.get("frozen_at", "")),
            "target_kind": target_kind,
            "target_id": str(data.get("target_id", "")),
            "prediction_kind": prediction_kind,
            "expected_evidence_ids": expected_evidence,
            "expected_event_ids": expected_events,
            "expected_event_order": expected_order,
            "weakens_when": str(data.get("weakens_when", "")).strip(),
            "expected_direction": expected_direction,
            "factual_future_prediction_licensed": False,
            "task_id": task_id,
            "purpose": str(data.get("purpose", "")).strip(),
            "coverage_ids": coverage_ids,
            "assumptions": _ordered_unique(data.get("assumptions", [])),
            "unknowns": _ordered_unique(data.get("unknowns", [])),
            "iteration": iteration,
            "max_iterations": max_iterations,
            "prior_open_gap_ids": _ordered_unique(data.get("prior_open_gap_ids", [])),
        }
        if not payload["prediction_id"] or not payload["target_id"]:
            raise TaskIterationError("prediction_id and target_id are required")
        _parse_timestamp(payload["frozen_at"], "frozen_at")
        observed_model_hash = _sha256_file(payload["baseline_model_path"])
        if observed_model_hash != payload["baseline_model_sha256"]:
            raise TaskIterationError("baseline model fingerprint is stale")
        return cls(**payload)


@dataclass(frozen=True)
class EvidenceBatchObservation:
    schema_version: str
    observation_id: str
    observed_at: str
    quality_status: str
    evidence_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    event_order: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    source_refs: tuple[str, ...]
    future_holdout_status: str
    external_input_ids: tuple[str, ...] = ()
    new_sources: tuple[SourceRecord, ...] = ()
    new_evidence: tuple[EvidenceItem, ...] = ()
    new_events: tuple[EventCandidate, ...] = ()
    new_links: tuple[HypothesisEvidenceLink, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EvidenceBatchObservation":
        if data.get("schema_version") != OBSERVATION_SCHEMA:
            raise TaskIterationError(f"schema_version must equal {OBSERVATION_SCHEMA}")
        quality = str(data.get("quality_status", ""))
        if quality not in VALID_QUALITY:
            raise TaskIterationError(f"invalid quality_status: {quality}")
        payload = {
            "schema_version": OBSERVATION_SCHEMA,
            "observation_id": str(data.get("observation_id", "")),
            "observed_at": str(data.get("observed_at", "")),
            "quality_status": quality,
            "evidence_ids": _ordered_unique(data.get("evidence_ids", [])),
            "event_ids": _ordered_unique(data.get("event_ids", [])),
            "event_order": tuple(str(item) for item in data.get("event_order", [])),
            "contradiction_ids": _ordered_unique(data.get("contradiction_ids", [])),
            "source_refs": _ordered_unique(data.get("source_refs", [])),
            "future_holdout_status": str(
                data.get("future_holdout_status", "not_run")
            ),
            "external_input_ids": _ordered_unique(data.get("external_input_ids", [])),
        }
        for field, _, record_type, _ in _OBSERVATION_RECORDS:
            rows = data.get(field, [])
            if not isinstance(rows, (list, tuple)) or any(not isinstance(row, Mapping) for row in rows):
                raise TaskIterationError(f"{field} must be a list of native record mappings")
            payload[field] = tuple(record_type.from_dict(dict(row)) for row in rows)
        if not payload["observation_id"]:
            raise TaskIterationError("observation_id is required")
        _parse_timestamp(payload["observed_at"], "observed_at")
        known_order_ids = set(payload["event_ids"]) | {row.event_id for row in payload["new_events"]}
        if set(payload["event_order"]) - known_order_ids:
            raise TaskIterationError("event_order may only contain event_ids or new_events ids")
        return cls(**payload)


def _require_observed_ids(model: Any, observation: "EvidenceBatchObservation", label: str) -> None:
    """Every evidence, event and source id an observation names must exist in the model."""

    for kind, ids, known in (
        ("evidence", observation.evidence_ids, model.evidence_by_id()),
        ("event", observation.event_ids, model.event_by_id()),
        ("source", observation.source_refs, model.source_by_id()),
    ):
        missing = [item for item in ids if item not in known]
        if missing:
            raise TaskIterationError(
                f"{label} {kind} is missing from the model: " + ", ".join(missing)
            )



def _observed_model(model: TraceGuardModel, observation: EvidenceBatchObservation) -> TraceGuardModel:
    """Append typed records in memory and reuse the native cross-reference binding."""
    updates: dict[str, tuple[Any, ...]] = {}
    for field, attribute, _, id_field in _OBSERVATION_RECORDS:
        rows = getattr(observation, field)
        if not rows:
            continue
        original = getattr(model, attribute)
        seen = {getattr(row, id_field) for row in original}
        for row in rows:
            record_id = getattr(row, id_field)
            if record_id in seen:
                raise TaskIterationError(f"{field} {id_field} conflicts with baseline or observation: {record_id}")
            seen.add(record_id)
        updates[attribute] = (*original, *rows)
    if not updates:
        return model
    augmented = replace(model, **updates)
    merged = TraceGuardModel.from_dict(augmented.to_dict())
    validate_references(merged)
    return merged


def _require_new_records(candidate: TraceGuardModel, observation: EvidenceBatchObservation) -> None:
    for field, attribute, _, id_field in _OBSERVATION_RECORDS:
        candidate_rows = {getattr(row, id_field): row for row in getattr(candidate, attribute)}
        changed = [getattr(row, id_field) for row in getattr(observation, field)
                   if candidate_rows.get(getattr(row, id_field)) != row]
        if changed:
            raise TaskIterationError(f"construction {field} changed in candidate: " + ", ".join(changed))


def _target_support(result: Any, prediction: PredictionSnapshot) -> float:
    if prediction.target_kind == "storyline":
        rows = result.traces
        field = "trace_id"
    else:
        rows = result.inference_receipt.hypothesis_projections
        field = "hypothesis_id"
    row = next((row for row in rows if getattr(row, field) == prediction.target_id), None)
    if row is None:
        raise TaskIterationError(f"prediction target is missing from evaluated model: {prediction.target_id}")
    return float(row.support)


@dataclass(frozen=True)
class StorylineMismatch:
    mismatch_id: str
    mismatch_type: str
    blocking_original_prediction: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def freeze_prediction(
    *,
    model_path: str | Path,
    prediction_id: str,
    frozen_at: str,
    target_kind: str,
    target_id: str,
    prediction_kind: str,
    expected_evidence_ids: Iterable[str] = (),
    expected_event_ids: Iterable[str] = (),
    expected_event_order: Iterable[str] = (),
    weakens_when: str = "",
    expected_direction: str = "",
    task_id: str = "",
    purpose: str = "",
    coverage_ids: Iterable[str] = (),
    assumptions: Iterable[str] = (),
    unknowns: Iterable[str] = (),
    iteration: int = 0,
    max_iterations: int = 8,
    prior_open_gap_ids: Iterable[str] = (),
) -> PredictionSnapshot:
    """Freeze a prediction before a new evidence batch is read."""

    resolved = Path(model_path).resolve()
    model = load_model(resolved)
    known_targets = (
        {item.trace_id for item in model.traces}
        if target_kind == "storyline"
        else {item.hypothesis_id for item in model.storyline_hypotheses}
    )
    if target_id not in known_targets:
        raise TaskIterationError(f"prediction target is missing from the model: {target_id}")
    coverage = list(coverage_ids)
    known_coverage = (
        set(model.evidence_by_id())
        | set(model.event_by_id())
        | set(model.source_by_id())
        | {item.trace_id for item in model.traces}
        | {item.hypothesis_id for item in model.storyline_hypotheses}
    )
    missing_coverage = [item for item in coverage if item not in known_coverage]
    if missing_coverage:
        raise TaskIterationError("coverage ids are missing from the model: " + ", ".join(missing_coverage))
    expected_evidence_ids = list(expected_evidence_ids)
    expected_event_ids = list(expected_event_ids)
    payload = {
        "schema_version": PREDICTION_SCHEMA,
        "prediction_id": prediction_id,
        "baseline_model_path": str(resolved),
        "baseline_model_sha256": _sha256_file(resolved),
        "frozen_at": frozen_at,
        "target_kind": target_kind,
        "target_id": target_id,
        "prediction_kind": prediction_kind,
        "expected_evidence_ids": list(expected_evidence_ids),
        "expected_event_ids": list(expected_event_ids),
        "expected_event_order": list(expected_event_order),
        "weakens_when": weakens_when,
        "expected_direction": expected_direction,
        "factual_future_prediction_licensed": False,
        "task_id": task_id,
        "purpose": purpose,
        "coverage_ids": coverage,
        "assumptions": list(assumptions),
        "unknowns": list(unknowns),
        "iteration": iteration,
        "max_iterations": max_iterations,
        "prior_open_gap_ids": list(prior_open_gap_ids),
    }
    return PredictionSnapshot.from_dict(payload)


def load_prediction(path: str | Path) -> PredictionSnapshot:
    return PredictionSnapshot.from_dict(_load_mapping(path))


def load_observation(path: str | Path) -> EvidenceBatchObservation:
    return EvidenceBatchObservation.from_dict(_load_mapping(path))


def _native_gap_ids(model: Any, depth: Any, coverage_ids: Iterable[str]) -> tuple[str, ...]:
    known = (set(model.evidence_by_id()) | set(model.event_by_id()) | set(model.source_by_id())
             | {item.trace_id for item in model.traces}
             | {item.hypothesis_id for item in model.storyline_hypotheses})
    return tuple(sorted(
        {"native-depth:" + str(item.get("gap_id") or item.get("finding_id") or fingerprint(item)[:20])
         for item in depth.unresolved_gaps}
        | {f"native-critical-uncovered:{item}" for item in depth.critical_uncovered_ids}
        | {f"native-critical-ineffective:{item}" for item in depth.critical_ineffective_ids}
        | {f"coverage-missing:{item}" for item in coverage_ids if item not in known}
    ))


def compare_prediction_observation(
    prediction: PredictionSnapshot,
    observation: EvidenceBatchObservation,
) -> dict[str, Any]:
    """Compare a frozen prediction with a later, append-only native observation."""
    if _parse_timestamp(observation.observed_at, "observed_at") <= _parse_timestamp(prediction.frozen_at, "frozen_at"):
        raise TaskIterationError("observation must be later than the frozen prediction")
    if _sha256_file(prediction.baseline_model_path) != prediction.baseline_model_sha256:
        raise TaskIterationError("baseline model fingerprint is stale")
    model = load_model(prediction.baseline_model_path)
    observed_model = _observed_model(model, observation)
    _require_observed_ids(observed_model, observation, "observed")
    baseline_result = evaluate_model(model)
    baseline_depth = evaluate_storyline_depth(model, baseline_result)
    observed_result = baseline_result if observed_model is model else evaluate_model(observed_model)
    observed_depth = baseline_depth if observed_model is model else evaluate_storyline_depth(observed_model, observed_result)
    baseline_gap_ids = _native_gap_ids(model, baseline_depth, prediction.coverage_ids)
    depth_gap_ids = _native_gap_ids(observed_model, observed_depth, prediction.coverage_ids)
    support_before = _target_support(baseline_result, prediction)
    support_after = _target_support(observed_result, prediction)
    delta = support_after - support_before
    direction = "weaken" if delta < -0.01 else "strengthen" if delta > 0.01 else "unchanged"
    mismatches: list[StorylineMismatch] = []

    def add(kind: str, detail: str) -> None:
        mismatches.append(StorylineMismatch(f"mismatch-{len(mismatches) + 1:03d}", kind, True, detail))

    if observation.quality_status != "valid":
        add("observation_invalid", f"observation quality is {observation.quality_status}")
    observed_evidence_ids = set(observation.evidence_ids) | {row.evidence_id for row in observation.new_evidence}
    observed_event_ids = set(observation.event_ids) | {row.event_id for row in observation.new_events}
    missing_evidence = sorted(set(prediction.expected_evidence_ids) - observed_evidence_ids)
    missing_events = sorted(set(prediction.expected_event_ids) - observed_event_ids)
    if missing_evidence:
        add("expected_evidence_missing", "missing expected evidence ids: " + ", ".join(missing_evidence))
    if missing_events:
        add("expected_event_missing", "missing expected event ids: " + ", ".join(missing_events))
    if prediction.expected_event_order and tuple(item for item in observation.event_order if item in prediction.expected_event_order) != prediction.expected_event_order:
        add("event_order_mismatch", "observed event order does not preserve the frozen expected order")
    if observation.contradiction_ids:
        add("unexpected_contradiction", "observation reports contradictions: " + ", ".join(observation.contradiction_ids))
    if prediction.prediction_kind == "future_event" and observation.future_holdout_status != "pass":
        add("future_holdout_validator_missing", "future-event expectation requires a passing future holdout check")
    if prediction.expected_direction and direction != prediction.expected_direction:
        add("direction_mismatch", f"expected {prediction.expected_direction}, observed {direction}")
    open_gap_ids = tuple(dict.fromkeys((*depth_gap_ids, *(row.mismatch_id for row in mismatches))))
    if observation.external_input_ids:
        terminal_reason = "external_input_required"
    elif not open_gap_ids:
        terminal_reason = "model_closed_for_task"
    elif prediction.iteration >= prediction.max_iterations:
        terminal_reason = "iteration_limit"
    elif set(open_gap_ids) == set(prediction.prior_open_gap_ids) and prediction.iteration > 0:
        terminal_reason = "progress_stalled"
    else:
        terminal_reason = "continue_iteration"
    transitions = gap_lineage(baseline_gap_ids, depth_gap_ids)
    return {
        "schema_version": COMPARISON_SCHEMA,
        "prediction_id": prediction.prediction_id,
        "observation_id": observation.observation_id,
        "baseline_model_path": prediction.baseline_model_path,
        "baseline_model_sha256": prediction.baseline_model_sha256,
        "mismatches": [item.to_dict() for item in mismatches],
        "expected_direction": prediction.expected_direction,
        "observed_direction": direction,
        "support_before": support_before,
        "support_after": support_after,
        "task_id": prediction.task_id,
        "purpose": prediction.purpose,
        "coverage_ids": list(prediction.coverage_ids),
        "open_gap_ids": list(open_gap_ids),
        "open_depth_gap_ids": list(depth_gap_ids),
        "baseline_gap_ids": list(baseline_gap_ids),
        "input_gap_ids": list(baseline_gap_ids),
        **{key: list(value) if isinstance(value, tuple) else value for key, value in transitions._asdict().items()},
        "live_alternative_ids": list(observed_depth.live_alternative_ids),
        "causal_boundaries": list(observed_depth.causal_boundaries),
        "deepest_proven_layer": observed_depth.deepest_proven_layer,
        "first_unresolved_gap": observed_depth.first_unresolved_gap,
        "next_actions": ["address_prediction_mismatches"] if mismatches else ["deepen_trace_evidence"] if depth_gap_ids else ["no_model_change_needed"],
        "terminal_reason": terminal_reason,
        "iteration": prediction.iteration,
        "prior_open_gap_ids": list(prediction.prior_open_gap_ids),
        "progressed": bool(transitions.resolved_gap_ids),
        "external_input_ids": list(observation.external_input_ids),
        "original_prediction_status": "weakened" if mismatches else "matched",
        "factual_future_prediction_licensed": False,
        "claim_boundary": "This comparison updates only the current TraceGuard task model; it does not license factual future prediction.",
    }


def _validate_comparison(data: Mapping[str, Any]) -> dict[str, Any]:
    if data.get("schema_version") != COMPARISON_SCHEMA:
        raise TaskIterationError(f"schema_version must equal {COMPARISON_SCHEMA}")
    if _sha256_file(str(data.get("baseline_model_path", ""))) != str(
        data.get("baseline_model_sha256", "")
    ):
        raise TaskIterationError("comparison baseline model is stale")
    return dict(data)


def load_comparison(path: str | Path) -> dict[str, Any]:
    return _validate_comparison(_load_mapping(path))


def decide_candidate_revision(
    *,
    comparison: Mapping[str, Any],
    candidate_model_path: str | Path,
    observation: EvidenceBatchObservation,
    holdout_observation: EvidenceBatchObservation | None = None,
    required_holdout_evidence_ids: Iterable[str] = (),
    addressed_mismatch_ids: Iterable[str] = (),
    force_rollback: bool = False,
) -> dict[str, Any]:
    """Revalidate and accept, reject, or roll back one candidate model.

    The holdout observation is optional.  When it is given it must be
    independent of the construction observation and every holdout evidence id
    must exist in the candidate.
    """

    comparison = _validate_comparison(comparison)
    if observation.observation_id != str(comparison.get("observation_id", "")):
        raise TaskIterationError(
            "candidate decision observation does not match the compared observation"
        )
    if holdout_observation is not None:
        if holdout_observation.observation_id == observation.observation_id:
            raise TaskIterationError("holdout observation must be independent")
        construction_ids = set(observation.evidence_ids) | {row.evidence_id for row in observation.new_evidence}
        holdout_ids = set(holdout_observation.evidence_ids) | {row.evidence_id for row in holdout_observation.new_evidence}
        if holdout_ids & construction_ids:
            raise TaskIterationError("holdout evidence ids must be disjoint from construction evidence")
    baseline_path = Path(str(comparison.get("baseline_model_path", ""))).resolve()
    candidate_path = Path(candidate_model_path).resolve()
    if baseline_path == candidate_path:
        raise TaskIterationError("candidate model path must differ from baseline")
    baseline_hash = _sha256_file(baseline_path)
    candidate_hash = _sha256_file(candidate_path)
    if candidate_hash == baseline_hash:
        raise TaskIterationError("candidate model content must differ from baseline")

    baseline_model = load_model(baseline_path)
    candidate_model = load_model(candidate_path)
    candidate_result = evaluate_model(candidate_model)
    result_payload = candidate_result.to_dict()
    _require_observed_ids(candidate_model, observation, "construction")
    _require_new_records(candidate_model, observation)
    if holdout_observation is not None:
        _require_observed_ids(candidate_model, holdout_observation, "holdout")
    candidate_depth = evaluate_storyline_depth(candidate_model, candidate_result)
    mismatch_ids = {
        str(item.get("mismatch_id", ""))
        for item in comparison.get("mismatches", [])
        if isinstance(item, Mapping)
    }
    addressed = set(_ordered_unique(addressed_mismatch_ids))
    unknown_addressed = sorted(addressed - mismatch_ids)
    unaddressed = sorted(mismatch_ids - addressed)
    required_holdout = _ordered_unique(required_holdout_evidence_ids)
    missing_holdout = (
        sorted(set(required_holdout) - set(holdout_observation.evidence_ids))
        if holdout_observation is not None
        else []
    )
    reasons: list[str] = []
    if unknown_addressed:
        reasons.append("unknown addressed mismatch ids: " + ", ".join(unknown_addressed))
    if unaddressed:
        reasons.append("unaddressed mismatch ids: " + ", ".join(unaddressed))
    if holdout_observation is not None and not required_holdout:
        reasons.append("at least one holdout evidence id is required")
    if missing_holdout:
        reasons.append("missing holdout evidence ids: " + ", ".join(missing_holdout))
    if not candidate_result.ok:
        reasons.append("canonical candidate evaluation did not pass")
    if observation.quality_status != "valid" or (
        holdout_observation is not None and holdout_observation.quality_status != "valid"
    ):
        reasons.append("construction and holdout observations must both be valid")

    coverage_ids = tuple(str(item) for item in comparison.get("coverage_ids", ()))
    candidate_gap_ids = list(_native_gap_ids(candidate_model, candidate_depth, coverage_ids))
    if force_rollback:
        disposition = "rolled_back"
        if "rollback explicitly requested" not in reasons:
            reasons.append("rollback explicitly requested")
    elif reasons:
        disposition = "rejected"
    else:
        disposition = "accepted"
    # Recompute the baseline for old comparison artifacts lacking the new field.
    if "baseline_gap_ids" in comparison:
        input_gaps = set(comparison["baseline_gap_ids"])
    else:
        baseline_depth = evaluate_storyline_depth(baseline_model, evaluate_model(baseline_model))
        input_gaps = set(_native_gap_ids(baseline_model, baseline_depth, coverage_ids))
    current_gaps = set(candidate_gap_ids)
    resolved_gaps, persisted_gaps, introduced_gaps, transitions = gap_lineage(input_gaps, current_gaps)
    if observation.external_input_ids:
        terminal_reason = "external_input_required"
    elif not candidate_gap_ids and disposition == "accepted":
        terminal_reason = "model_closed_for_task"
    elif comparison.get("terminal_reason") == "iteration_limit":
        terminal_reason = "iteration_limit"
    elif current_gaps == set(comparison.get("prior_open_gap_ids", comparison.get("input_gap_ids", ()))) and int(comparison.get("iteration", 0)) > 0:
        terminal_reason = "progress_stalled"
    elif missing_holdout or disposition in {"rejected", "rolled_back"}:
        terminal_reason = "external_input_required"
    else:
        terminal_reason = "continue_iteration"

    effective_hash = candidate_hash if disposition == "accepted" else baseline_hash
    return {
        "schema_version": REVISION_SCHEMA,
        "prediction_id": comparison.get("prediction_id", ""),
        "observation_id": observation.observation_id,
        "holdout_observation_id": (
            holdout_observation.observation_id if holdout_observation is not None else ""
        ),
        "baseline_model_path": str(baseline_path),
        "baseline_model_sha256": baseline_hash,
        "candidate_model_path": str(candidate_path),
        "candidate_model_sha256": candidate_hash,
        "addressed_mismatch_ids": sorted(addressed),
        "unaddressed_mismatch_ids": unaddressed,
        "required_holdout_evidence_ids": list(required_holdout),
        "missing_holdout_evidence_ids": missing_holdout,
        "candidate_evaluation_ok": bool(candidate_result.ok),
        "live_alternative_ids": list(candidate_depth.live_alternative_ids),
        "causal_boundaries": list(candidate_depth.causal_boundaries),
        "deepest_proven_layer": candidate_depth.deepest_proven_layer,
        "first_unresolved_gap": candidate_depth.first_unresolved_gap,
        "disposition": disposition,
        "rejection_reasons": reasons,
        "task_id": comparison.get("task_id", ""),
        "iteration": comparison.get("iteration", 0),
        "input_gap_ids": sorted(input_gaps),
        "resolved_gap_ids": list(resolved_gaps),
        "persisted_gap_ids": list(persisted_gaps),
        "introduced_gap_ids": list(introduced_gaps),
        "open_gap_ids": candidate_gap_ids,
        "gap_transitions": transitions,
        "next_actions": ["deepen_trace_evidence"] if candidate_gap_ids else ["no_model_change_needed"],
        "terminal_reason": terminal_reason,
        "progressed": bool(resolved_gaps),
        "effective_model_sha256": effective_hash,
        "factual_future_prediction_licensed": False,
        "claim_boundary": (
            "Acceptance changes only the selected model for this task. "
            "TraceGuard core rules, thresholds, solver policy, and other Guards "
            "remain unchanged."
        ),
    }


__all__ = [
    "COMPARISON_SCHEMA",
    "EvidenceBatchObservation",
    "OBSERVATION_SCHEMA",
    "PREDICTION_SCHEMA",
    "PredictionSnapshot",
    "REVISION_SCHEMA",
    "StorylineMismatch",
    "TaskIterationError",
    "compare_prediction_observation",
    "decide_candidate_revision",
    "freeze_prediction",
    "load_comparison",
    "load_observation",
    "load_prediction",
    "write_artifact",
]
