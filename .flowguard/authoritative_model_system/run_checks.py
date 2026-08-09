"""Run the researchguard software-DNA root model checks."""

from __future__ import annotations

import json
from pathlib import Path

import model

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    model.run_model()
    report = model.check_blueprint_inputs(ROOT)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if not report["ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
