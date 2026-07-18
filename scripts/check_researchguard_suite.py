"""Native ResearchGuard suite and consumer-skill contract check."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from researchguard import __version__  # noqa: E402
from researchguard.routing import RouteBinding, bind_member_request  # noqa: E402
from researchguard.source.schema import Gap, SchemaError  # noqa: E402


MEMBERS = ("researchguard", "logicguard", "sourceguard", "traceguard")
RETIRED_SKILL_IDS = (
    "logicguard-source-library",
    "logicguard-structured-artifact",
    "logicguard-model-deepening",
    "logicguard-artifact-synthesis",
    "logicguard-project-library-viewer",
    "traceguard-library",
)
RETIRED_COMMANDS = (
    "python -m logicguard",
    "python -m sourceguard",
    "python -m traceguard",
    "run_logicguard.py",
    "run_sourceguard.py",
    "run_traceguard.py",
)


def _python(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(SRC)
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def _assert(condition: bool, message: str, checks: list[dict[str, str]]) -> None:
    checks.append(
        {
            "status": "pass" if condition else "fail",
            "summary": message,
        }
    )


def _check_common(checks: list[dict[str, str]]) -> None:
    _assert(__version__ == "0.1.1", "suite version is exactly 0.1.1", checks)
    skill_dirs = sorted(path.name for path in (ROOT / "skills").iterdir() if path.is_dir())
    _assert(
        skill_dirs == sorted(MEMBERS),
        "consumer skill inventory is exactly the four current members",
        checks,
    )
    current_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "skills").rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".yaml", ".yml", ".py"}
    )
    _assert(
        not any(value in current_text for value in RETIRED_SKILL_IDS),
        "consumer projection contains no retired skill id",
        checks,
    )
    _assert(
        not any(value in current_text for value in RETIRED_COMMANDS),
        "consumer projection contains no retired command or wrapper",
        checks,
    )


def _check_researchguard(checks: list[dict[str, str]]) -> None:
    for member in ("logicguard", "sourceguard", "traceguard"):
        direct = bind_member_request(member, ("--help",))
        umbrella = bind_member_request(member, ("--help",))
        _assert(
            isinstance(direct, RouteBinding)
            and isinstance(umbrella, RouteBinding)
            and direct.native_owner_id == umbrella.native_owner_id
            and direct.primary_path_id == umbrella.primary_path_id,
            f"direct and umbrella {member} bindings share one owner and path",
            checks,
        )
    result = _python("-m", "researchguard", "--help")
    _assert(
        result.returncode == 0
        and "run|logic|source|trace" in result.stdout,
        "sole suite console exposes exactly the four current commands",
        checks,
    )


def _check_logicguard(checks: list[dict[str, str]]) -> None:
    expected_routes = {
        "source-library.md",
        "structured-artifact.md",
        "model-deepening.md",
        "artifact-synthesis.md",
        "project-library-viewer.md",
    }
    actual_routes = {
        path.name
        for path in (ROOT / "skills" / "logicguard" / "references" / "routes").glob("*.md")
    }
    _assert(
        actual_routes == expected_routes,
        "LogicGuard exposes all five former satellite capabilities as internal routes",
        checks,
    )
    result = _python("-m", "researchguard", "logic", "--help")
    _assert(
        result.returncode == 0
        and "route-depth" in result.stdout
        and "library" in result.stdout,
        "LogicGuard is callable only through the ResearchGuard console",
        checks,
    )


def _check_sourceguard(checks: list[dict[str, str]]) -> None:
    _assert(
        "status" not in Gap.__dataclass_fields__,
        "SourceGuard gap schema has one semantic_state authority",
        checks,
    )
    try:
        Gap.from_dict(
            {
                "gap_id": "retired",
                "gap_type": "unknown",
                "status": "open",
                "semantic_state": "discovered",
            }
        )
    except SchemaError:
        retired_rejected = True
    else:
        retired_rejected = False
    _assert(
        retired_rejected,
        "retired SourceGuard gap status projection is rejected",
        checks,
    )
    result = _python("-m", "researchguard", "source", "--help")
    _assert(result.returncode == 0, "SourceGuard current console is callable", checks)


def _check_traceguard(checks: list[dict[str, str]]) -> None:
    route = ROOT / "skills" / "traceguard" / "references" / "routes" / "case-library.md"
    _assert(route.is_file(), "TraceGuard case library is an internal route", checks)
    result = _python("-m", "researchguard", "trace", "--help")
    _assert(
        result.returncode == 0 and "library-depth" in result.stdout,
        "TraceGuard current console owns its internal case-library depth command",
        checks,
    )


CHECKERS: dict[str, Callable[[list[dict[str, str]]], None]] = {
    "researchguard": _check_researchguard,
    "logicguard": _check_logicguard,
    "sourceguard": _check_sourceguard,
    "traceguard": _check_traceguard,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--member", choices=MEMBERS + ("all",), default="all")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    checks: list[dict[str, str]] = []
    _check_common(checks)
    selected = MEMBERS if args.member == "all" else (args.member,)
    for member in selected:
        CHECKERS[member](checks)
    status = "pass" if all(row["status"] == "pass" for row in checks) else "fail"
    payload = {
        "schema_version": "researchguard.native-suite-check.v1",
        "member": args.member,
        "status": status,
        "checks": checks,
        "claim_boundary": (
            "This check covers the current ResearchGuard consumer-skill topology, "
            "sole console, exact member bindings, and selected native boundary only."
        ),
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
