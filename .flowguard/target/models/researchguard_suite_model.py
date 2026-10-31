"""FlowGuard contract model: one researchguard skill, four routes, one console.

It is bound to the real things it describes: the console dispatch
(`src/researchguard/cli.py:_member_main`) and the installer
(`scripts/install_skill.py:main`) are replayed, the route table in
`skills/researchguard/SKILL.md` and the skill folders are read as code facts,
and the package member table `researchguard.MEMBER_IDS` is compared.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from flowguard import FunctionResult, Invariant, InvariantResult, Scenario, ScenarioExpectation, Workflow

# intent -> (route, CLI member owner)
ROUTES = {
    "argument_licensing": ("logic", "logicguard"),
    "evidence_discovery": ("source", "sourceguard"),
    "trace_reconstruction": ("trace", "traceguard"),
    "experiment_discrimination": ("experiment", "experimentguard"),
}
MEMBER_BY_ROUTE = dict(ROUTES.values())
RETIRED_SKILLS = ("logicguard", "sourceguard", "traceguard", "experimentguard")
FAILURES = {"failed", "blocked", "stale", "timeout", "unsupported", "unavailable"}


@dataclass(frozen=True)
class ResearchRequest:
    intent: str
    loaded_route_files: int = 1
    native_status: str = "pass"
    handoff_target: str = ""
    run_handoff: bool = False
    already_routed: bool = False


@dataclass(frozen=True)
class RouteState:
    phase: str = "unrouted"
    route: str = ""
    member: str = ""
    terminal_status: str = ""
    handoff_target: str = ""
    alternate_attempts: int = 0


class PickRoute:
    """The SKILL.md route table: one intent selects one route."""

    name = "PickRoute"
    accepted_input_type = ResearchRequest
    reads = ("intent", "already_routed")
    writes = ("phase", "route", "member", "terminal_status")

    def apply(self, request: ResearchRequest, state: RouteState):
        if request.already_routed or state.phase != "unrouted":
            yield FunctionResult(request, replace(state, phase="blocked", terminal_status="recursion"), label="route_recursion_blocked")
            return
        selected = ROUTES.get(request.intent)
        if selected is None:
            yield FunctionResult(request, replace(state, phase="blocked", terminal_status="no_route"), label="no_route_blocked")
            return
        route, member = selected
        yield FunctionResult(request, replace(state, phase="routed", route=route, member=member), label=f"route_selected_{route}")


class LoadRouteFile:
    """After picking a route the agent loads exactly that route's file."""

    name = "LoadRouteFile"
    accepted_input_type = ResearchRequest
    reads = ("phase", "loaded_route_files")
    writes = ("phase", "terminal_status")

    def apply(self, request: ResearchRequest, state: RouteState):
        if state.phase != "routed":
            yield FunctionResult(request, state, label="route_file_not_loaded")
            return
        if request.loaded_route_files != 1:
            yield FunctionResult(request, replace(state, phase="blocked", terminal_status="route_load_invalid"), label="route_load_invalid_blocked")
            return
        yield FunctionResult(request, state, label="one_route_file_loaded")


class RunRoute:
    """`researchguard <route> ...` runs the member owner once; a failure is terminal."""

    name = "RunRoute"
    accepted_input_type = ResearchRequest
    reads = ("phase", "native_status", "handoff_target")
    writes = ("phase", "terminal_status", "handoff_target")

    def apply(self, request: ResearchRequest, state: RouteState):
        if state.phase != "routed":
            yield FunctionResult(request, state, label="route_not_run")
            return
        if request.native_status != "pass":
            yield FunctionResult(request, replace(state, phase="terminal", terminal_status=request.native_status), label="route_failure_terminal")
            return
        if request.handoff_target:
            yield FunctionResult(
                request,
                replace(state, phase="awaiting_owner", terminal_status="handoff_requested", handoff_target=request.handoff_target),
                label="handoff_waits",
            )
            return
        yield FunctionResult(request, replace(state, phase="terminal", terminal_status="pass"), label="route_terminal_pass")


class FollowHandoff:
    """A handoff names another route; it runs only when the agent explicitly runs it."""

    name = "FollowHandoff"
    accepted_input_type = ResearchRequest
    reads = ("phase", "handoff_target", "run_handoff")
    writes = ("phase", "route", "member", "terminal_status", "handoff_target")

    def apply(self, request: ResearchRequest, state: RouteState):
        if state.phase != "awaiting_owner":
            yield FunctionResult(request, state, label="handoff_not_applicable")
            return
        if not request.run_handoff:
            yield FunctionResult(request, state, label="handoff_not_automatic")
            return
        member = MEMBER_BY_ROUTE.get(state.handoff_target)
        if member is None:
            yield FunctionResult(request, replace(state, phase="blocked", terminal_status="invalid_handoff"), label="handoff_invalid_blocked")
            return
        yield FunctionResult(
            request,
            replace(state, phase="routed", route=state.handoff_target, member=member, terminal_status="", handoff_target=""),
            label=f"handoff_selected_{state.handoff_target}",
        )


def _no_alternate_success(state: RouteState, _trace) -> InvariantResult:
    if state.alternate_attempts:
        return InvariantResult.fail("a selected route attempted alternate success")
    return InvariantResult.pass_()


def _failure_stays_terminal(state: RouteState, _trace) -> InvariantResult:
    if state.terminal_status in FAILURES and state.phase != "terminal":
        return InvariantResult.fail("a route failure escaped the terminal state")
    return InvariantResult.pass_()


def _route_matches_member(state: RouteState, _trace) -> InvariantResult:
    if state.route and MEMBER_BY_ROUTE.get(state.route) != state.member:
        return InvariantResult.fail(f"route {state.route!r} runs the wrong member {state.member!r}")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant("no_alternate_success", "A selected route has no fallback or alternate-success edge.", _no_alternate_success),
    Invariant("terminal_failure_stays_terminal", "A route failure cannot trigger another route.", _failure_stays_terminal),
    Invariant("route_matches_member", "Each route runs its own member owner.", _route_matches_member),
)


def build_workflow(run_route=None, pick_route=None) -> Workflow:
    return Workflow((pick_route or PickRoute(), LoadRouteFile(), run_route or RunRoute(), FollowHandoff()), name="researchguard_one_skill_four_routes")


def _scenario(name: str, request: ResearchRequest, labels: tuple[str, ...], summary: str) -> Scenario:
    return Scenario(
        name=name,
        description=summary,
        initial_state=RouteState(),
        external_input_sequence=(request,),
        expected=ScenarioExpectation(expected_status="ok", required_trace_labels=labels, summary=summary),
        workflow=build_workflow(),
        invariants=INVARIANTS,
    )


def scenarios() -> tuple[Scenario, ...]:
    return (
        _scenario("RG01_logic_route", ResearchRequest("argument_licensing"), ("route_selected_logic", "route_terminal_pass"), "argument work runs the logic route"),
        _scenario("RG02_experiment_route", ResearchRequest("experiment_discrimination"), ("route_selected_experiment", "route_terminal_pass"), "experiment work runs the experiment route"),
        _scenario("RG04_failure_terminal", ResearchRequest("evidence_discovery", native_status="failed"), ("route_selected_source", "route_failure_terminal"), "a source failure is terminal"),
        _scenario("RG05_handoff_waits", ResearchRequest("argument_licensing", handoff_target="source"), ("handoff_waits", "handoff_not_automatic"), "a handoff is not automatic"),
        _scenario("RG06_handoff_runs_when_asked", ResearchRequest("trace_reconstruction", handoff_target="logic", run_handoff=True), ("handoff_waits", "handoff_selected_logic"), "an explicit handoff runs the named route"),
        _scenario("RG07_recursion_blocks", ResearchRequest("trace_reconstruction", already_routed=True), ("route_recursion_blocked",), "a routed request cannot re-enter the table"),
        _scenario("RG08_two_route_files_block", ResearchRequest("argument_licensing", loaded_route_files=2), ("route_load_invalid_blocked",), "loading a second route file is visible and blocked"),
        _scenario("RG09_unknown_intent_blocks", ResearchRequest("write_the_report"), ("no_route_blocked",), "a request outside the four routes is blocked"),
    )


# Current FlowGuard model contract.
MODEL_ID = "researchguard_suite"
PARENT = "system"
COMPONENTS = ["researchguard-suite"]
IMPLEMENTED_BY = {
    "PickRoute": "skills/researchguard/SKILL.md:routes",
    "RunRoute": "src/researchguard/cli.py:_member_main",
    "Console": "src/researchguard/cli.py:main",
    "Install": "scripts/install_skill.py:main",
}
TESTED_BY = {
    "no_alternate_success": ["tests/test_root_cli.py:test_direct_member_request_does_not_require_task_facts"],
    "terminal_failure_stays_terminal": ["tests/test_root_cli.py:test_retired_standalone_routes_are_unknown_commands"],
    "route_matches_member": [
        "tests/test_skill_suite.py:test_one_skill_with_a_route_table_and_a_description",
        "tests/test_install_skill.py:test_install_copies_one_skill_removes_retired_members_and_check_detects_drift",
        "tests/test_root_cli.py:test_root_cli_has_only_current_public_commands",
    ],
}


def build_explorer():
    from flowguard.explorer import Explorer

    inputs = tuple(scenario.external_input_sequence[0] for scenario in scenarios())
    return Explorer(build_workflow(), (RouteState(),), inputs, INVARIANTS)


def broken_variants():
    from flowguard.explorer import Explorer

    class AlternateRoute(RunRoute):
        def apply(self, request, state):
            for result in super().apply(request, state):
                yield replace(result, new_state=replace(result.new_state, alternate_attempts=1))

    class RerouteOnFailure(RunRoute):
        def apply(self, request, state):
            for result in super().apply(request, state):
                if result.new_state.terminal_status in FAILURES:
                    yield replace(result, new_state=replace(result.new_state, phase="routed"))
                else:
                    yield result

    class WrongMember(PickRoute):
        def apply(self, request, state):
            for result in super().apply(request, state):
                if result.new_state.route == "logic":
                    yield replace(result, new_state=replace(result.new_state, member="sourceguard"))
                else:
                    yield result

    return {
        "wrong_member": Explorer(
            build_workflow(pick_route=WrongMember()), (RouteState(),), (ResearchRequest("argument_licensing"),), INVARIANTS
        ),
        "alternate_route": Explorer(build_workflow(AlternateRoute()), (RouteState(),), (ResearchRequest("argument_licensing"),), INVARIANTS),
        "reroute_on_failure": Explorer(
            build_workflow(RerouteOnFailure()), (RouteState(),), (ResearchRequest("evidence_discovery", native_status="failed"),), INVARIANTS
        ),
    }


def conformance():
    # Replay this checkout's src-layout owner even when a distribution is installed.
    import contextlib
    import importlib.util
    import io
    import sys
    import tempfile
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "src"))
    from flowguard.conformance import ConformanceReport, ConformanceViolation
    from flowguard.replay import ReplayObservation
    from researchguard import MEMBER_IDS
    from researchguard.cli import _member_main, main

    observations = []
    violations = []

    def check(rule: str, expected, actual) -> None:
        observations.append(ReplayObservation(rule, expected, actual))
        if expected != actual:
            violations.append(ConformanceViolation(step_index=1, message=f"{rule}: expected {expected!r}, got {actual!r}", rule_name=rule))

    # Replay: each route's console command runs its own member owner.
    for intent, (route, member) in ROUTES.items():
        picked = next(PickRoute().apply(ResearchRequest(intent), RouteState())).new_state
        check(f"route:{route}", f"researchguard.{picked.route}.cli", _member_main(picked.member).__module__)
    with contextlib.redirect_stdout(io.StringIO()):
        check("retired_umbrella_run", 2, main(["run"]))
    sync_help = io.StringIO()
    with contextlib.redirect_stdout(sync_help):
        try:
            sync_exit = main(["sync", "--help"])
        except SystemExit as exc:
            sync_exit = exc.code
    check("sync_public_command", 0, sync_exit)
    check("sync_help", True, "researchguard sync" in sync_help.getvalue())
    check("member_ids", tuple(MEMBER_BY_ROUTE.values()), tuple(MEMBER_IDS))
    # Code facts: the skill is one route table whose route files exist, and no member skill is left.
    skill = (root / "skills" / "researchguard" / "SKILL.md").read_text(encoding="utf-8")
    for route in MEMBER_BY_ROUTE:
        reference = f"references/routes/{route}.md"
        check(f"route_file:{route}", True, reference in skill and (root / "skills" / "researchguard" / reference).is_file())
    check("skill_dirs", ["researchguard"], sorted(path.name for path in (root / "skills").iterdir() if path.is_dir()))
    # Replay: installing over the old member skills leaves only the one skill, and --check agrees.
    spec = importlib.util.spec_from_file_location("researchguard_install_skill", root / "scripts" / "install_skill.py")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    saved_argv = sys.argv
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "skills"
        for name in RETIRED_SKILLS:
            (target / name).mkdir(parents=True)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                sys.argv = ["install_skill.py", "--target", str(target)]
                installed = installer.main()
                sys.argv = ["install_skill.py", "--target", str(target), "--check"]
                checked = installer.main()
        finally:
            sys.argv = saved_argv
        check("install", (0, 0, ["researchguard"]), (installed, checked, sorted(path.name for path in target.iterdir())))
    return ConformanceReport(
        ok=not violations,
        violations=tuple(violations),
        replayed_steps=tuple(observations),
        summary="Four routes and the installer replayed; route table and skill folders compared as code facts.",
    )


NOT_MODELED = {
    "src/researchguard/logic/cli.py:main": "Argparse dispatch and explicit report IO; native argument, library and synthesis behavior is guarded by tests/logic/test_cli.py and member models.",
    "src/researchguard/source/cli.py:main": "Argparse dispatch only; source planning, sync and stop behavior is guarded by tests/source/test_cli.py and source models.",
    "src/researchguard/trace/cli.py:main": "Argparse dispatch only; native inference and explicit handoffs are guarded by tests/trace and research-tree replay.",
    "src/researchguard/experiment/cli.py:main": "Argparse dispatch only; finite discrimination and observation behavior is guarded by tests/experiment.",
    "src/researchguard/logic_viewer/launcher.py:main": "Optional desktop viewer startup has no research lifecycle; tests cover its launch and API boundary without requiring GUI display.",
}
