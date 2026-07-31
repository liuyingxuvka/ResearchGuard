"""Run the registered ResearchGuard suite model."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    completed = subprocess.run(
        [sys.executable, ".flowguard/run_researchguard_suite_model.py"],
        cwd=ROOT,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
