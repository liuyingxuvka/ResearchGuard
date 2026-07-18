"""Task-local prediction, observation, and reversible storyline revision.

This module owns lifecycle integrity only.  It never scores a storyline and
never changes TraceGuard's inference policy.  Candidate evaluation is delegated
to the canonical :func:`researchguard.trace.evaluator.evaluate_model` entry point.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from .evaluator import evaluate_model
from .inference.types import fingerprint
from .loader import load_model


PREDICTION_SCHEMA = "researchguard.trace.task_prediction.v1"
OBSERVATION_SCHEMA = "researchguard.trace.evidence_batch_observation.v1"
COMPARISON_SCHEMA = "researchguard.trace.prediction_observation_comparison.v1"
REVISION_SCHEMA = "researchguard.trace.candidate_storyline_revision.v1"
VALID_TARGET_KINDS = {"storyline", "hypothesis"}
VALID_PREDICTION_KINDS = {"evidence_footprint", "future_event"}
VALID_QUALITY = {"valid", "invalid", "access_gap"}


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
    snapshot_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PredictionSnapshot":
        if data.get("schema_version") != PREDICTION_SCHEMA:
            raise TaskIterationError(f"schema_version must equal {PREDICTION_SCHEMA}")
        target_kind = str(data.get("target_kind", ""))
        prediction_kind = str(data.get("prediction_kind", ""))
        if target_kind not in VALID_TARGET_KINDS:
            raise TaskIterationError(f"invalid target_kind: {target_kind}")
        if prediction_kind not in VALID_PREDICTION_KINDS:
            raise TaskIterationError(f"invalid prediction_kind: {prediction_kind}")
        expected_evidence = _ordered_unique(data.get("expected_evidence_ids", []))
        expected_events = _ordered_unique(data.get("expected_event_ids", []))
        expected_order = tuple(str(item) for item in data.get("expected_event_order", []))
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
            "factual_future_prediction_licensed": False,
        }
        if not payload["prediction_id"] or not payload["target_id"]:
            raise TaskIterationError("prediction_id and target_id are required")
        if not payload["weakens_when"]:
            raise TaskIterationError("weakens_when is required")
        _parse_timestamp(payload["frozen_at"], "frozen_at")
        observed_model_hash = _sha256_file(payload["baseline_model_path"])
        if observed_model_hash != payload["baseline_model_sha256"]:
            raise TaskIterationError("baseline model fingerprint is stale")
        expected_fingerprint = fingerprint(payload)
        supplied_fingerprint = str(data.get("snapshot_fingerprint", ""))
        if supplied_fingerprint and supplied_fingerprint != expected_fingerprint:
            raise TaskIterationError("prediction snapshot fingerprint mismatch")
        return cls(**payload, snapshot_fingerprint=expected_fingerprint)


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
    future_holdout_validator_receipt: str
    observation_fingerprint: str

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
            "future_holdout_validator_receipt": str(
                data.get("future_holdout_validator_receipt", "")
            ),
        }
        if not payload["observation_id"]:
            raise TaskIterationError("observation_id is required")
        _parse_timestamp(payload["observed_at"], "observed_at")
        if set(payload["event_order"]) - set(payload["event_ids"]):
            raise TaskIterationError("event_order may only contain event_ids")
        expected_fingerprint = fingerprint(payload)
        supplied_fingerprint = str(data.get("observation_fingerprint", ""))
        if supplied_fingerprint and supplied_fingerprint != expected_fingerprint:
            raise TaskIterationError("observation fingerprint mismatch")
        return cls(**payload, observation_fingerprint=expected_fingerprint)


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
    weakens_when: str,
) -> PredictionSnapshot:
    """Freeze a prediction before a new evidence batch is read."""

    resolved = Path(model_path).resolve()
    load_model(resolved)
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
        "factual_future_prediction_licensed": False,
    }
    return PredictionSnapshot.from_dict(payload)


def load_prediction(path: str | Path) -> PredictionSnapshot:
    return PredictionSnapshot.from_dict(_load_mapping(path))


def load_observation(path: str | Path) -> EvidenceBatchObservation:
    return EvidenceBatchObservation.from_dict(_load_mapping(path))


def compare_prediction_observation(
    prediction: PredictionSnapshot,
    observation: EvidenceBatchObservation,
) -> dict[str, Any]:
    """Compare one frozen expectation with one later evidence batch."""

    if _parse_timestamp(observation.observed_at, "observed_at") <= _parse_timestamp(
        prediction.frozen_at, "frozen_at"
    ):
        raise TaskIterationError(
            "observation must be later than the frozen prediction"
        )
    mismatches: list[StorylineMismatch] = []

    def add(kind: str, detail: str) -> None:
        mismatches.append(
            StorylineMismatch(
                mismatch_id=f"mismatch-{len(mismatches) + 1:03d}",
                mismatch_type=kind,
                blocking_original_prediction=True,
                detail=detail,
            )
        )

    if observation.quality_status != "valid":
        add(
            "observation_invalid",
            f"observation quality is {observation.quality_status}",
        )
    missing_evidence = sorted(
        set(prediction.expected_evidence_ids) - set(observation.evidence_ids)
    )
    if missing_evidence:
        add(
            "expected_evidence_missing",
            "missing expected evidence ids: " + ", ".join(missing_evidence),
        )
    missing_events = sorted(
        set(prediction.expected_event_ids) - set(observation.event_ids)
    )
    if missing_events:
        add(
            "expected_event_missing",
            "missing expected event ids: " + ", ".join(missing_events),
        )
    if (
        prediction.expected_event_order
        and tuple(
            item
            for item in observation.event_order
            if item in prediction.expected_event_order
        )
        != prediction.expected_event_order
    ):
        add(
            "event_order_mismatch",
            "observed event order does not preserve the frozen expected order",
        )
    if observation.contradiction_ids:
        add(
            "unexpected_contradiction",
            "observation reports contradictions: "
            + ", ".join(observation.contradiction_ids),
        )
    if prediction.prediction_kind == "future_event" and (
        observation.future_holdout_status != "pass"
        or not observation.future_holdout_validator_receipt
    ):
        add(
            "future_holdout_validator_missing",
            "future-event expectation requires a passing target-owned holdout receipt",
        )
    payload: dict[str, Any] = {
        "schema_version": COMPARISON_SCHEMA,
        "prediction_id": prediction.prediction_id,
        "prediction_fingerprint": prediction.snapshot_fingerprint,
        "observation_id": observation.observation_id,
        "observation_fingerprint": observation.observation_fingerprint,
        "baseline_model_path": prediction.baseline_model_path,
        "baseline_model_sha256": prediction.baseline_model_sha256,
        "mismatches": [item.to_dict() for item in mismatches],
        "original_prediction_status": "weakened" if mismatches else "matched",
        "factual_future_prediction_licensed": False,
        "claim_boundary": (
            "This comparison updates only the current TraceGuard task model. "
            "It does not license factual future prediction."
        ),
    }
    payload["comparison_fingerprint"] = fingerprint(payload)
    return payload


def _validate_comparison(data: Mapping[str, Any]) -> dict[str, Any]:
    if data.get("schema_version") != COMPARISON_SCHEMA:
        raise TaskIterationError(f"schema_version must equal {COMPARISON_SCHEMA}")
    supplied = str(data.get("comparison_fingerprint", ""))
    check = dict(data)
    check.pop("comparison_fingerprint", None)
    if supplied != fingerprint(check):
        raise TaskIterationError("comparison fingerprint mismatch")
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
    required_holdout_evidence_ids: Iterable[str],
    addressed_mismatch_ids: Iterable[str] = (),
    force_rollback: bool = False,
) -> dict[str, Any]:
    """Revalidate and accept, reject, or roll back one candidate model."""

    comparison = _validate_comparison(comparison)
    if observation.observation_fingerprint != str(
        comparison.get("observation_fingerprint", "")
    ):
        raise TaskIterationError(
            "candidate decision observation does not match the compared observation"
        )
    baseline_path = Path(str(comparison.get("baseline_model_path", ""))).resolve()
    candidate_path = Path(candidate_model_path).resolve()
    if baseline_path == candidate_path:
        raise TaskIterationError("candidate model path must differ from baseline")
    baseline_hash = _sha256_file(baseline_path)
    candidate_hash = _sha256_file(candidate_path)
    if candidate_hash == baseline_hash:
        raise TaskIterationError("candidate model content must differ from baseline")

    candidate_result = evaluate_model(load_model(candidate_path))
    result_payload = candidate_result.to_dict()
    mismatch_ids = {
        str(item.get("mismatch_id", ""))
        for item in comparison.get("mismatches", [])
        if isinstance(item, Mapping)
    }
    addressed = set(_ordered_unique(addressed_mismatch_ids))
    unknown_addressed = sorted(addressed - mismatch_ids)
    unaddressed = sorted(mismatch_ids - addressed)
    required_holdout = _ordered_unique(required_holdout_evidence_ids)
    missing_holdout = sorted(set(required_holdout) - set(observation.evidence_ids))
    reasons: list[str] = []
    if unknown_addressed:
        reasons.append("unknown addressed mismatch ids: " + ", ".join(unknown_addressed))
    if unaddressed:
        reasons.append("unaddressed mismatch ids: " + ", ".join(unaddressed))
    if not required_holdout:
        reasons.append("at least one holdout evidence id is required")
    if missing_holdout:
        reasons.append("missing holdout evidence ids: " + ", ".join(missing_holdout))
    if not candidate_result.ok:
        reasons.append("canonical candidate evaluation did not pass")
    if observation.quality_status != "valid":
        reasons.append("observation quality is not valid")

    if force_rollback:
        disposition = "rolled_back"
        reasons.append("rollback explicitly requested")
    elif reasons:
        disposition = "rejected"
    else:
        disposition = "accepted"
    effective_hash = candidate_hash if disposition == "accepted" else baseline_hash
    payload: dict[str, Any] = {
        "schema_version": REVISION_SCHEMA,
        "revision_id": (
            "trace-revision-"
            + fingerprint(
                {
                    "comparison": comparison.get("comparison_fingerprint"),
                    "candidate": candidate_hash,
                    "observation": observation.observation_fingerprint,
                }
            )[:20]
        ),
        "baseline_model_path": str(baseline_path),
        "baseline_model_sha256": baseline_hash,
        "candidate_model_path": str(candidate_path),
        "candidate_model_sha256": candidate_hash,
        "prediction_fingerprint": comparison.get("prediction_fingerprint"),
        "observation_fingerprint": observation.observation_fingerprint,
        "comparison_fingerprint": comparison.get("comparison_fingerprint"),
        "addressed_mismatch_ids": sorted(addressed),
        "unaddressed_mismatch_ids": unaddressed,
        "required_holdout_evidence_ids": list(required_holdout),
        "missing_holdout_evidence_ids": missing_holdout,
        "candidate_evaluation_ok": bool(candidate_result.ok),
        "candidate_evaluation_fingerprint": fingerprint(result_payload),
        "candidate_inference_receipt_id": getattr(
            candidate_result.inference_receipt, "receipt_id", ""
        ),
        "disposition": disposition,
        "rejection_reasons": reasons,
        "effective_model_sha256": effective_hash,
        "factual_future_prediction_licensed": False,
        "claim_boundary": (
            "Acceptance changes only the selected model for this task. "
            "TraceGuard core rules, thresholds, solver policy, and other Guards "
            "remain unchanged."
        ),
    }
    payload["revision_fingerprint"] = fingerprint(payload)
    return payload


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
