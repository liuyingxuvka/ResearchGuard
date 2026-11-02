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


import sys

import pytest

# No test in this suite may end skipped, expected to fail or cut short. Each of those exits 0, so a
# test that swallowed an error and skipped would look like a passing run. A test that needs a
# platform feature tests code that does not import it instead (see logic_viewer/card_text.py).
NO_SKIP = "this suite allows no skip, xfail or early exit"
_early_exits: list[str] = []


def _reason(report) -> str:
    if isinstance(report.longrepr, tuple):
        return str(report.longrepr[2]).removeprefix("Skipped: ")
    return str(report.longrepr)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    report = (yield).get_result()
    if hasattr(report, "wasxfail"):
        what, reason = "expected to fail", report.wasxfail
        del report.wasxfail  # a report that keeps it is not counted as failed
    elif report.skipped:
        what, reason = "skipped", _reason(report)
    else:
        return
    report.outcome = "failed"
    report.longrepr = f"test {what} ({reason}); {NO_SKIP}"


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    report = (yield).get_result()
    if report.skipped:
        report.outcome = "failed"
        report.longrepr = f"{collector.nodeid or collector.path} skipped at collection ({_reason(report)}); {NO_SKIP}"


def pytest_keyboard_interrupt(excinfo):
    if isinstance(excinfo.value, pytest.exit.Exception):
        _early_exits.append(str(excinfo.value.msg))


def pytest_sessionfinish(session, exitstatus):
    if _early_exits:
        sys.stderr.write(f"pytest.exit() ended the run early ({'; '.join(_early_exits)}); {NO_SKIP}\n")
        if session.exitstatus == pytest.ExitCode.OK:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
