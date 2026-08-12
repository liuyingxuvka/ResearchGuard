"""Run the registered ResearchGuard suite model."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def software_dna_report() -> dict[str, object]:
    """Return the read-only native self-DNA report for focused checks."""

    sys.path.insert(0, str(ROOT / "src"))
    from researchguard.software_dna import check_software_dna_contract

    return check_software_dna_contract(ROOT)


def main() -> int:
    completed = subprocess.run(
        [sys.executable, ".flowguard/run_researchguard_suite_model.py"],
        cwd=ROOT,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
