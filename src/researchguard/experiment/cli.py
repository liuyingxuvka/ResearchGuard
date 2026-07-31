"""ExperimentGuard command-line owner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import recommend_experiments
from .schema import ExperimentSpec, HypothesisPrediction


def _load_spec(path: Path) -> ExperimentSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ExperimentSpec(
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
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="researchguard experiment")
    subparsers = parser.add_subparsers(dest="command", required=True)
    recommend = subparsers.add_parser("recommend")
    recommend.add_argument("spec", type=Path)
    args = parser.parse_args(argv)
    result = recommend_experiments(_load_spec(args.spec))
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if result.status == "recommended" else 2


if __name__ == "__main__":
    raise SystemExit(main())
