"""ExperimentGuard command-line owner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


from .engine import observe_experiments, recommend_experiments
from .loader import load_spec, load_spec_payload, load_observations


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
        result = recommend_experiments(load_spec(args.spec))
        print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
        return 0 if result.status == "recommended" else 2
    result = observe_experiments(load_spec(args.spec), load_observations(args.observations))
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if result.terminal_reason == "model_closed_for_task" else 2


if __name__ == "__main__":
    raise SystemExit(main())
