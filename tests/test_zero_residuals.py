from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_active_runtime_has_zero_retired_surfaces() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_zero_residuals.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"residual_count": 0' in result.stdout
    assert '"status": "pass"' in result.stdout
