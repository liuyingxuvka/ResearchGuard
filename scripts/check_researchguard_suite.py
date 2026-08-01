"""Native ResearchGuard suite and consumer-skill contract check."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from researchguard import __version__  # noqa: E402
from researchguard.admission import COMPOSITION_SCHEMA, TASK_FACTS_SCHEMA  # noqa: E402
from researchguard.routing import (  # noqa: E402
    MEMBER_ADMISSION_CONTRACTS,
    RouteBinding,
    RouteComposition,
    bind_member_request,
    request_fingerprint,
    select_member_request,
)
from researchguard.source.schema import Gap, SchemaError  # noqa: E402


MEMBERS = (
    "researchguard",
    "logicguard",
    "sourceguard",
    "traceguard",
    "experimentguard",
)
CURRENT_VERSION = "0.4.1"
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


def _suite_model_version() -> str:
    model_path = ROOT / ".flowguard" / "researchguard_suite_model.py"
    spec = importlib.util.spec_from_file_location(
        "researchguard_suite_currentness_model",
        model_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load suite model {model_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return str(module.CURRENT_RESEARCHGUARD_VERSION)


def _json_model_version() -> str:
    payload = json.loads(
        (ROOT / ".flowguard" / "researchguard_suite_model.json").read_text(
            encoding="utf-8"
        )
    )
    prefix = "researchguard.suite.v"
    model_id = str(payload.get("model_id", ""))
    return model_id[len(prefix) :] if model_id.startswith(prefix) else ""


def _package_metadata_version() -> str:
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(payload["project"]["version"])


def _check_common(checks: list[dict[str, str]]) -> None:
    versions = {
        "module": __version__,
        "package_metadata": _package_metadata_version(),
        "executable_model": _suite_model_version(),
        "json_model": _json_model_version(),
    }
    _assert(
        set(versions.values()) == {CURRENT_VERSION},
        f"suite identity sources are exactly {CURRENT_VERSION}: {versions}",
        checks,
    )
    skill_dirs = sorted(path.name for path in (ROOT / "skills").iterdir() if path.is_dir())
    _assert(
        skill_dirs == sorted(MEMBERS),
        "consumer skill inventory is exactly the five current skill surfaces",
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
    result = _python("scripts/check_prompt_bundles.py", "--json")
    prompt_payload = json.loads(result.stdout) if result.returncode == 0 else {}
    _assert(
        result.returncode == 0 and prompt_payload.get("status") == "pass",
        "target-owned prompt bundles, load graph, and generated admission index pass",
        checks,
    )


def _task_facts(member: str, argv: tuple[str, ...], intent: str) -> dict:
    primary = {
        "logicguard": "logic.argument_structure",
        "sourceguard": "source.primary_discovery",
        "traceguard": "trace.temporal_reconstruction",
        "experimentguard": "experiment.discriminating_set",
    }[member]
    context = {
        "experimentguard": (
            "experiment.explicit_hypotheses",
            "experiment.finite_candidates",
            "experiment.predicted_outcomes",
        )
    }.get(member, ())
    kinds = (primary, *context)
    facts = []
    for index, kind in enumerate(kinds):
        quote = f"native suite fact {index}: {kind}"
        facts.append(
            {
                "fact_id": f"fact:{index}",
                "kind": kind,
                "role": "primary_action" if index == 0 else "context",
                "statement": quote,
                "source_span": {"source_id": f"native-suite:{index}", "start": 0, "end": len(quote), "quote": quote},
            }
        )
    review_quote = str(facts[0]["source_span"]["quote"])
    reviews = []
    for candidate, contract in MEMBER_ADMISSION_CONTRACTS.items():
        for condition in contract["forbidden_conditions"]:
            present = bool(set(kinds).intersection(condition["any_fact_kinds"]))
            reviews.append(
                {
                    "member_id": candidate,
                    "condition_id": condition["condition_id"],
                    "disposition": "present" if present else "absent",
                    "source_span": {"source_id": "native-suite:review", "start": 0, "end": len(review_quote), "quote": review_quote},
                }
            )
    return {
        "schema_version": TASK_FACTS_SCHEMA,
        "request_fingerprint": request_fingerprint(argv, business_intent_id=intent),
        "facts": facts,
        "forbidden_reviews": reviews,
    }


def _check_researchguard(checks: list[dict[str, str]]) -> None:
    for member in (
        "logicguard",
        "sourceguard",
        "traceguard",
        "experimentguard",
    ):
        direct = bind_member_request(member, ("--help",))
        intent = f"intent:native-suite:{member}"
        evidence = _task_facts(member, ("--help",), intent)
        umbrella = select_member_request(
            evidence,
            ("--help",),
            business_intent_id=intent,
        )
        _assert(
            isinstance(direct, RouteBinding)
            and isinstance(umbrella, RouteBinding)
            and direct.native_owner_id == umbrella.native_owner_id
            and direct.primary_path_id == umbrella.primary_path_id,
            f"direct and umbrella {member} bindings share one owner and path",
            checks,
        )
    pair_argv = ("plan", "mixed-task.json")
    pair_intent = "intent:native-suite:source-trace"
    pair = _task_facts("sourceguard", pair_argv, pair_intent)
    trace_quote = "native suite fact 1: trace.temporal_reconstruction"
    pair["facts"].append(
        {
            "fact_id": "fact:trace",
            "kind": "trace.temporal_reconstruction",
            "role": "primary_action",
            "statement": trace_quote,
            "source_span": {
                "source_id": "native-suite:trace",
                "start": 0,
                "end": len(trace_quote),
                "quote": trace_quote,
            },
        }
    )
    pair["composition"] = {
        "schema_version": COMPOSITION_SCHEMA,
        "steps": [
            {
                "step_id": "step:source",
                "order": 1,
                "member_id": "sourceguard",
                "responsibility_condition_ids": ["source.primary.discovery"],
                "depends_on_step_ids": [],
                "input_handoff_ids": [],
                "output_handoff_ids": ["handoff:source-trace"],
            },
            {
                "step_id": "step:trace",
                "order": 2,
                "member_id": "traceguard",
                "responsibility_condition_ids": ["trace.primary.reconstruction"],
                "depends_on_step_ids": ["step:source"],
                "input_handoff_ids": ["handoff:source-trace"],
                "output_handoff_ids": [],
            },
        ],
        "handoffs": [
            {
                "handoff_id": "handoff:source-trace",
                "from_step_id": "step:source",
                "to_step_id": "step:trace",
                "field_ids": ["field:evidence-anchors"],
            }
        ],
        "field_owners": [
            {"field_id": "field:evidence-anchors", "owner_step_id": "step:source"}
        ],
        "overall_claim_boundary": "This proves route composition only, not native member completion.",
    }
    composed = select_member_request(pair, pair_argv, business_intent_id=pair_intent)
    _assert(
        isinstance(composed, RouteComposition)
        and composed.member_ids == ("sourceguard", "traceguard"),
        "umbrella accepts one necessary minimum-sufficient composition",
        checks,
    )
    result = _python("-m", "researchguard", "--help")
    _assert(
        result.returncode == 0
        and "run|logic|source|trace|experiment" in result.stdout,
        "sole suite console exposes exactly the five current commands",
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


def _check_experimentguard(checks: list[dict[str, str]]) -> None:
    from researchguard.experiment import (  # noqa: PLC0415
        ExperimentSpec,
        HypothesisPrediction,
        recommend_experiments,
    )

    result = recommend_experiments(
        ExperimentSpec(
            task_id="task:native-suite:experimentguard",
            purpose="verify finite recommendation",
            coverage_ids=("hypotheses:h1-h2", "experiments:e1-e2"),
            assumptions=(),
            unknowns=(),
            iteration=0,
            max_iterations=2,
            hypothesis_predictions=(
                HypothesisPrediction("h1", {"e1": "up", "e2": "same"}),
                HypothesisPrediction("h2", {"e1": "down", "e2": "same"}),
            ),
            candidate_experiment_ids=("e1", "e2"),
        )
    )
    _assert(
        result.status == "recommended"
        and result.selected_experiment_ids == ("e1",),
        "ExperimentGuard returns a recommendation-only exact minimum set",
        checks,
    )


CHECKERS: dict[str, Callable[[list[dict[str, str]]], None]] = {
    "researchguard": _check_researchguard,
    "logicguard": _check_logicguard,
    "sourceguard": _check_sourceguard,
    "traceguard": _check_traceguard,
    "experimentguard": _check_experimentguard,
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
        "suite_version": CURRENT_VERSION,
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
