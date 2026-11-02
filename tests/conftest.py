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
_collected: set[str] = set()
_reported: set[str] = set()
_failed: set[str] = set()
_MAIN_PROCESS = os.getpid()


def _refuse_in_this_process(module, name):
    """Make ``module.name`` fail the calling test in the pytest process instead of ending or replacing it.

    os._exit and the exec functions skip every pytest hook, so a run they end reports nothing and can
    exit 0. A child made by fork has another process id and gets the real function.
    """
    real = getattr(module, name, None)
    if real is None:
        return

    def refused(*args, **kwargs):
        if os.getpid() != _MAIN_PROCESS:
            return real(*args, **kwargs)
        _early_exits.append(f"{module.__name__}.{name}")
        pytest.fail(f"{module.__name__}.{name}() would end the test process; {NO_SKIP}", pytrace=False)

    setattr(module, name, refused)


for _module in {id(item): item for item in (os, sys.modules.get(os.name)) if item is not None}.values():
    for _name in ("_exit", "execv", "execve", "execl", "execle", "execlp", "execlpe", "execvp", "execvpe"):
        _refuse_in_this_process(_module, _name)


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


def pytest_collection_finish(session):
    _collected.update(item.nodeid for item in session.items)


def pytest_runtest_logreport(report):
    _reported.add(report.nodeid)
    if report.failed:
        _failed.add(report.nodeid)


def pytest_keyboard_interrupt(excinfo):
    if isinstance(excinfo.value, pytest.exit.Exception):
        _early_exits.append(f"pytest.exit({excinfo.value.msg})")


def pytest_sessionfinish(session, exitstatus):
    """Recount the run from the reports themselves, so nothing a test does to the session hides a failure."""
    if session.exitstatus != pytest.ExitCode.OK:
        return
    option = session.config.option
    problems = []
    if _early_exits:
        problems.append(f"the run was ended early ({'; '.join(_early_exits)})")
    if _failed:
        problems.append(f"{len(_failed)} test(s) failed ({', '.join(sorted(_failed)[:3])})")
    unrun = _collected - _reported
    if unrun and not (option.collectonly or getattr(option, "setuponly", False) or getattr(option, "setupplan", False)):
        problems.append(f"{len(unrun)} collected test(s) never ran ({', '.join(sorted(unrun)[:3])})")
    if problems:
        sys.stderr.write(f"{'; '.join(problems)}, but the run would exit 0; {NO_SKIP}\n")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
