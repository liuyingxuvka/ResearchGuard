from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")

# The repository uses a src layout. Child CLI processes must resolve the same
# current package under test instead of an older installed distribution.
existing = os.environ.get("PYTHONPATH", "")
os.environ["PYTHONPATH"] = (
    SRC if not existing else os.pathsep.join((SRC, existing))
)


import pytest

# A test may skip only because this Python lacks a platform feature the code needs. Any
# other skip, for example one taken inside an ``except`` that swallowed an error, fails.
ALLOWED_SKIP_PREFIXES = ("could not import 'tkinter'",)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if not report.skipped or hasattr(report, "wasxfail"):
        return
    reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else str(report.longrepr)
    reason = reason.removeprefix("Skipped: ")
    if not reason.startswith(ALLOWED_SKIP_PREFIXES):
        report.outcome = "failed"
        report.longrepr = f"skipped for a reason that is not an absent platform feature: {reason}"
