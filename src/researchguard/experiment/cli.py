"""ExperimentGuard command-line owner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping


from .engine import observe_experiments, recommend_experiments
from .schema import (
    EXPERIMENT_SPEC_SCHEMA,
    ExperimentObservation,
    ExperimentSpec,
    HypothesisPrediction,
)


def _load_spec(path: Path) -> ExperimentSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _load_spec_payload(payload)


def _load_spec_payload(payload: object) -> ExperimentSpec:
    if not isinstance(payload, Mapping):
        raise ValueError("experiment spec root must be an object")
    if "cost_by_experiment" in payload and not isinstance(payload["cost_by_experiment"], Mapping):
        raise ValueError("cost_by_experiment must be an experiment-id to cost mapping")
    return ExperimentSpec(
        schema_version=str(payload.get("schema_version") or EXPERIMENT_SPEC_SCHEMA),
        task_id=str(payload.get("task_id") or "recommendation"),
        purpose=str(payload.get("purpose") or "Recommend the smallest experiment set that separates the declared hypotheses."),
        coverage_ids=tuple(str(item) for item in (payload.get("coverage_ids") or ["all-hypothesis-pairs"])),
        assumptions=tuple(str(item) for item in payload.get("assumptions", [])),
        unknowns=tuple(str(item) for item in payload.get("unknowns", [])),
        iteration=int(payload.get("iteration", 0)),
        max_iterations=int(payload.get("max_iterations", 1)),
        prior_open_gap_ids=tuple(str(item) for item in payload.get("prior_open_gap_ids", [])),
        hypothesis_predictions=tuple(
            HypothesisPrediction(
                hypothesis_id=str(item["hypothesis_id"]),
                outcomes_by_experiment={
                    str(key): str(value)
                    for key, value in item["outcomes_by_experiment"].items()
                },

            )
            for item in payload["hypothesis_predictions"]
        ),
        candidate_experiment_ids=tuple(
            str(item) for item in payload["candidate_experiment_ids"]
        ),
        maximum_experiment_count=payload.get("maximum_experiment_count"),
        cost_by_experiment=payload.get("cost_by_experiment"),
    )


def _load_observations(path: Path) -> tuple[ExperimentObservation, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("observations", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("observations artifact must contain a list")
    return tuple(
        ExperimentObservation(
            experiment_id=str(item["experiment_id"]),
            observed_outcome=str(item["observed_outcome"]),
            evidence_id=str(item["evidence_id"]),
            source_ref=str(item["source_ref"]),
            observed_at=str(item["observed_at"]),
            role=str(item["role"]),
            status=str(item.get("status", "valid")),
        )
        for item in rows
    )


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except (KeyError, ValueError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False, sort_keys=True))
        return 2


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="researchguard experiment")
    subparsers = parser.add_subparsers(dest="command", required=True)
    recommend = subparsers.add_parser("recommend")
    recommend.add_argument("spec", type=Path)
    observe = subparsers.add_parser("observe")
    observe.add_argument("spec", type=Path)
    observe.add_argument("observations", type=Path)
    args = parser.parse_args(argv)
    if args.command == "recommend":
        result = recommend_experiments(_load_spec(args.spec))
        print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
        return 0 if result.status == "recommended" else 2
    result = observe_experiments(_load_spec(args.spec), _load_observations(args.observations))
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if result.terminal_reason == "model_closed_for_task" else 2


if __name__ == "__main__":
    raise SystemExit(main())
