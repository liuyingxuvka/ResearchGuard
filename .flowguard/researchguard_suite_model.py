"""Executable FlowGuard model for ResearchGuard route and install authority."""

from __future__ import annotations

from dataclasses import dataclass, replace

from flowguard import (
    FunctionResult,
    Invariant,
    InvariantResult,
    Scenario,
    ScenarioExpectation,
    Workflow,
)

FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
CURRENT_RESEARCHGUARD_VERSION = "0.1.1"


MEMBER_BY_INTENT = {
    "argument_licensing": ("logicguard", "researchguard.logic"),
    "evidence_discovery": ("sourceguard", "researchguard.source"),
    "trace_reconstruction": ("traceguard", "researchguard.trace"),
}


@dataclass(frozen=True)
class ResearchRequest:
    intent: str
    entrypoint: str = "researchguard"
    native_status: str = "pass"
    handoff_target: str = ""
    allow_handoff: bool = False
    already_routed: bool = False


@dataclass(frozen=True)
class RouteState:
    phase: str = "unrouted"
    member_id: str = ""
    primary_path_id: str = ""
    terminal_status: str = ""
    handoff_target: str = ""
    alternate_attempts: int = 0


@dataclass(frozen=True)
class PackageIdentityRequest:
    researchguard_version: str
    predecessor_distribution_state: str
    predecessor_version: str = ""


@dataclass(frozen=True)
class PackageIdentityState:
    phase: str = "unresolved"
    package_version: str = ""
    fingerprint_owner: str = ""
    predecessor_queries: int = 0
    alternate_attempts: int = 0


class Route:
    name = "Route"
    accepted_input_type = ResearchRequest
    reads = ("intent", "entrypoint", "already_routed")
    writes = ("phase", "member_id", "primary_path_id")
    input_description = "one direct or umbrella research request"
    output_description = "one selected member path or typed route gap"
    idempotency = "the same current request selects the same sole path"

    def apply(self, request: ResearchRequest, state: RouteState):
        if request.already_routed or state.phase != "unrouted":
            yield FunctionResult(
                request,
                replace(state, phase="blocked", terminal_status="recursion"),
                label="route_recursion_blocked",
            )
            return

        if request.entrypoint in {"logicguard", "sourceguard", "traceguard"}:
            direct_intent = {
                "logicguard": "argument_licensing",
                "sourceguard": "evidence_discovery",
                "traceguard": "trace_reconstruction",
            }[request.entrypoint]
            if request.intent != direct_intent:
                yield FunctionResult(
                    request,
                    replace(state, phase="blocked", terminal_status="intent_mismatch"),
                    label="route_direct_mismatch_blocked",
                )
                return

        selected = MEMBER_BY_INTENT.get(request.intent)
        if selected is None:
            yield FunctionResult(
                request,
                replace(state, phase="blocked", terminal_status="ambiguous"),
                label="route_ambiguous_blocked",
            )
            return

        member_id, primary_path_id = selected
        yield FunctionResult(
            request,
            replace(
                state,
                phase="routed",
                member_id=member_id,
                primary_path_id=primary_path_id,
            ),
            label=f"route_selected_{member_id}",
        )


class ExecuteMember:
    name = "ExecuteMember"
    accepted_input_type = ResearchRequest
    reads = ("phase", "member_id", "native_status")
    writes = ("phase", "terminal_status", "handoff_target")
    input_description = "one routed native member request"
    output_description = "the selected member's native terminal result"
    idempotency = "one route executes one native owner once"

    def apply(self, request: ResearchRequest, state: RouteState):
        if state.phase != "routed":
            yield FunctionResult(
                request,
                state,
                label="member_not_run",
            )
            return
        if request.native_status != "pass":
            yield FunctionResult(
                request,
                replace(
                    state,
                    phase="terminal",
                    terminal_status=request.native_status,
                    alternate_attempts=0,
                ),
                label="member_failure_terminal",
            )
            return
        if request.handoff_target:
            yield FunctionResult(
                request,
                replace(
                    state,
                    phase="awaiting_owner",
                    terminal_status="handoff_requested",
                    handoff_target=request.handoff_target,
                ),
                label="typed_handoff_waits",
            )
            return
        yield FunctionResult(
            request,
            replace(state, phase="terminal", terminal_status="pass"),
            label="member_terminal_pass",
        )


class OrchestrateHandoff:
    name = "OrchestrateHandoff"
    accepted_input_type = ResearchRequest
    reads = ("phase", "handoff_target", "allow_handoff")
    writes = ("phase", "member_id", "primary_path_id", "terminal_status")
    input_description = "a typed handoff plus explicit outer-owner decision"
    output_description = "one explicitly selected sibling route or waiting state"
    idempotency = "one handoff is consumed at most once by the explicit owner"

    def apply(self, request: ResearchRequest, state: RouteState):
        if state.phase != "awaiting_owner":
            yield FunctionResult(
                request,
                state,
                label="handoff_not_applicable",
            )
            return
        if not request.allow_handoff:
            yield FunctionResult(
                request,
                state,
                label="handoff_not_automatic",
            )
            return
        target_intent = {
            "logicguard": "argument_licensing",
            "sourceguard": "evidence_discovery",
            "traceguard": "trace_reconstruction",
        }.get(state.handoff_target)
        selected = MEMBER_BY_INTENT.get(target_intent or "")
        if selected is None:
            yield FunctionResult(
                request,
                replace(state, phase="blocked", terminal_status="invalid_handoff"),
                label="handoff_invalid_blocked",
            )
            return
        member_id, primary_path_id = selected
        yield FunctionResult(
            request,
            replace(
                state,
                phase="routed",
                member_id=member_id,
                primary_path_id=primary_path_id,
                terminal_status="",
                handoff_target="",
            ),
            label=f"handoff_selected_{member_id}",
        )


class ResolveMeshStorePackageIdentity:
    name = "ResolveMeshStorePackageIdentity"
    accepted_input_type = PackageIdentityRequest
    reads = ("researchguard_version",)
    writes = (
        "phase",
        "package_version",
        "fingerprint_owner",
        "predecessor_queries",
    )
    input_description = "the sole current ResearchGuard in-package version"
    output_description = "one current durable mesh-store identity"
    idempotency = "predecessor distribution state is outside the relation"

    def apply(
        self,
        request: PackageIdentityRequest,
        state: PackageIdentityState,
    ):
        if (
            state.phase != "unresolved"
            or request.researchguard_version != CURRENT_RESEARCHGUARD_VERSION
        ):
            yield FunctionResult(
                request,
                replace(state, phase="blocked"),
                label="package_identity_blocked",
            )
            return
        yield FunctionResult(
            request,
            replace(
                state,
                phase="resolved",
                package_version=request.researchguard_version,
                fingerprint_owner="researchguard",
                predecessor_queries=0,
            ),
            label="package_identity_resolved_current",
        )


def no_alternate_success() -> Invariant:
    def predicate(state: RouteState, _trace):
        if state.alternate_attempts:
            return InvariantResult.fail("a selected route attempted alternate success")
        return InvariantResult.pass_()

    return Invariant(
        "no_alternate_success",
        "A selected ResearchGuard route has no fallback or alternate-success edge.",
        predicate,
    )


def terminal_failure_stays_terminal() -> Invariant:
    def predicate(state: RouteState, _trace):
        if state.terminal_status in {
            "failed",
            "blocked",
            "stale",
            "timeout",
            "unsupported",
            "unavailable",
        } and state.phase != "terminal":
            return InvariantResult.fail("native failure escaped terminal state")
        return InvariantResult.pass_()

    return Invariant(
        "terminal_failure_stays_terminal",
        "A native member failure cannot trigger another route.",
        predicate,
    )


INVARIANTS = (no_alternate_success(), terminal_failure_stays_terminal())


def current_package_identity() -> Invariant:
    def predicate(state: PackageIdentityState, _trace):
        if state.phase == "resolved" and (
            state.package_version != CURRENT_RESEARCHGUARD_VERSION
            or state.fingerprint_owner != "researchguard"
        ):
            return InvariantResult.fail("mesh store identity is not current ResearchGuard")
        return InvariantResult.pass_()

    return Invariant(
        "mesh_store_uses_researchguard_package_identity",
        "Durable mesh-store identity is owned only by the current ResearchGuard package.",
        predicate,
    )


def no_predecessor_distribution_query() -> Invariant:
    def predicate(state: PackageIdentityState, _trace):
        if state.predecessor_queries:
            return InvariantResult.fail("a retired distribution influenced current identity")
        return InvariantResult.pass_()

    return Invariant(
        "no_predecessor_distribution_query",
        "Current identity never queries a retired Guard distribution.",
        predicate,
    )


PACKAGE_IDENTITY_INVARIANTS = (
    current_package_identity(),
    no_predecessor_distribution_query(),
)


def build_workflow() -> Workflow:
    return Workflow(
        (Route(), ExecuteMember(), OrchestrateHandoff()),
        name="researchguard_route_authority",
    )


def build_package_identity_workflow() -> Workflow:
    return Workflow(
        (ResolveMeshStorePackageIdentity(),),
        name="researchguard_package_identity",
    )


def scenarios() -> tuple[Scenario, ...]:
    workflow = build_workflow()
    identity_workflow = build_package_identity_workflow()
    return (
        Scenario(
            name="RG01_direct_logic",
            description="Direct LogicGuard selects the sole namespaced logic path.",
            initial_state=RouteState(),
            external_input_sequence=(
                ResearchRequest("argument_licensing", entrypoint="logicguard"),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=(
                    "route_selected_logicguard",
                    "member_terminal_pass",
                ),
                summary="direct logic reaches researchguard.logic",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="RG02_umbrella_logic",
            description="Umbrella dispatch reaches the same sole logic path.",
            initial_state=RouteState(),
            external_input_sequence=(ResearchRequest("argument_licensing"),),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=(
                    "route_selected_logicguard",
                    "member_terminal_pass",
                ),
                summary="umbrella logic reaches researchguard.logic",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="RG03_ambiguous_blocks",
            description="Unknown intent blocks before native execution.",
            initial_state=RouteState(),
            external_input_sequence=(ResearchRequest("unknown"),),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("route_ambiguous_blocked",),
                summary="ambiguous intent is visible",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="RG04_member_failure_terminal",
            description="Selected SourceGuard failure cannot reroute to another member.",
            initial_state=RouteState(),
            external_input_sequence=(
                ResearchRequest("evidence_discovery", native_status="failed"),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=(
                    "route_selected_sourceguard",
                    "member_failure_terminal",
                ),
                summary="member failure is terminal",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="RG05_handoff_waits",
            description="A typed handoff is not automatic.",
            initial_state=RouteState(),
            external_input_sequence=(
                ResearchRequest(
                    "argument_licensing",
                    handoff_target="sourceguard",
                    allow_handoff=False,
                ),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=(
                    "typed_handoff_waits",
                    "handoff_not_automatic",
                ),
                summary="typed handoff awaits explicit owner",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="RG06_recursion_blocks",
            description="An already routed request cannot re-enter the umbrella.",
            initial_state=RouteState(),
            external_input_sequence=(
                ResearchRequest("trace_reconstruction", already_routed=True),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("route_recursion_blocked",),
                summary="recursive dispatch is blocked",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="RG07_predecessor_distribution_absent",
            description="Missing retired LogicGuard distribution cannot alter current identity.",
            initial_state=PackageIdentityState(),
            external_input_sequence=(
                PackageIdentityRequest(
                    CURRENT_RESEARCHGUARD_VERSION,
                    predecessor_distribution_state="absent",
                ),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("package_identity_resolved_current",),
                summary="current ResearchGuard identity resolves without predecessor query",
            ),
            workflow=identity_workflow,
            invariants=PACKAGE_IDENTITY_INVARIANTS,
        ),
        Scenario(
            name="RG08_predecessor_distribution_present",
            description="Installed retired LogicGuard distribution cannot alter current identity.",
            initial_state=PackageIdentityState(),
            external_input_sequence=(
                PackageIdentityRequest(
                    CURRENT_RESEARCHGUARD_VERSION,
                    predecessor_distribution_state="present",
                    predecessor_version="999.999.999",
                ),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("package_identity_resolved_current",),
                summary="the same current identity resolves when predecessor is present",
            ),
            workflow=identity_workflow,
            invariants=PACKAGE_IDENTITY_INVARIANTS,
        ),
    )


__all__ = [
    "INVARIANTS",
    "PACKAGE_IDENTITY_INVARIANTS",
    "MEMBER_BY_INTENT",
    "PackageIdentityRequest",
    "PackageIdentityState",
    "ResearchRequest",
    "RouteState",
    "build_package_identity_workflow",
    "build_workflow",
    "scenarios",
]
