from __future__ import annotations

import importlib.util
import inspect
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_checker():
    path = ROOT / "scripts" / "check_researchguard_suite.py"
    spec = importlib.util.spec_from_file_location("suite_checker_bounds", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_console_probe_timeout_is_terminal_and_bounded():
    checker = _load_checker()
    started = time.monotonic()
    result = checker._python(
        "-c", "import time; time.sleep(30)", timeout=1
    )
    elapsed = time.monotonic() - started
    assert elapsed < 8
    assert result.returncode == 124
    assert "PROCESS_TREE_TIMEOUT=1" in result.stderr


def test_source_console_probe_has_a_bounded_cold_start_budget():
    checker = _load_checker()
    parameter = inspect.signature(checker._python).parameters["timeout"]
    assert checker.CONSOLE_PROBE_TIMEOUT_SECONDS == 240
    assert parameter.default == checker.CONSOLE_PROBE_TIMEOUT_SECONDS
