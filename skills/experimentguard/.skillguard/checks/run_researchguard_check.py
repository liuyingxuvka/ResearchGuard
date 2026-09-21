from __future__ import annotations

import json
import os
import subprocess
import sys
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CHECKS = {'consumer-contract': ['scripts/check_researchguard_suite.py', '--member', 'experimentguard', '--json'], 'prompt-load': ['scripts/check_prompt_bundles.py', '--member', 'experimentguard', '--json'], 'native-tests': ['-m', 'pytest', 'tests/experiment', '-q'], 'task-model-closure': ['-m', 'pytest', 'tests/experiment/test_recommendation.py', '-q']}

def _environment() -> dict[str, str]:
    env = os.environ.copy()
    source = REPO / "src"
    if (source / "researchguard").is_dir():
        current = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join([str(source)] + ([current] if current else []))
    return env

def _python() -> str:
    return shutil.which("python") or sys.executable

name = sys.argv[1] if len(sys.argv) == 2 else ""
if name not in CHECKS:
    raise SystemExit(f"unknown check: {name}")
args = CHECKS[name]
completed = subprocess.run([_python(), "-B", *args], cwd=REPO, env=_environment(), check=False)
raise SystemExit(completed.returncode)
