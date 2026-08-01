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
CURRENT_RESEARCHGUARD_VERSION = "0.4.1"


MEMBER_BY_INTENT = {
    "argument_licensing": ("logicguard", "researchguard.logic"),
    "evidence_discovery": ("sourceguard", "researchguard.source"),
    "trace_reconstruction": ("traceguard", "researchguard.trace"),
    "experiment_discrimination": (
        "experimentguard",
        "researchguard.experiment",
    ),
}
MEMBER_PATHS = {member_id: path_id for member_id, path_id in MEMBER_BY_INTENT.values()}


@dataclass(frozen=True)
class ResearchRequest:
    intent: str
    entrypoint: str = "researchguard"
    admission_row_count: int = 0
    minimum_sufficient_members: tuple[str, ...] = ()
    composition_member_ids: tuple[str, ...] = ()
    composition_valid: bool = False
    task_facts_current: bool = True
    primary_action_fact_count: int = 1
    source_spans_valid: bool = True
    forbidden_review_complete: bool = True
    selected_member_load_count: int = 1
    nonselected_member_load_count: int = 0
    untriggered_reference_count: int = 0
    deep_triggered: bool = False
    deep_reference_loaded: bool = False
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
    reads = (
        "intent",
        "entrypoint",
        "already_routed",
        "admission_row_count",
        "minimum_sufficient_members",
        "composition_member_ids",
        "composition_valid",
        "task_facts_current",
        "primary_action_fact_count",
        "source_spans_valid",
        "forbidden_review_complete",
    )
    writes = ("phase", "member_id", "primary_path_id")
    input_description = (
        "one direct request or one umbrella request with source-bound task facts and four derived member rows"
    )
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

        if request.entrypoint in {
            "logicguard",
            "sourceguard",
            "traceguard",
            "experimentguard",
        }:
            direct_intent = {
                "logicguard": "argument_licensing",
                "sourceguard": "evidence_discovery",
                "traceguard": "trace_reconstruction",
                "experimentguard": "experiment_discrimination",
            }[request.entrypoint]
            if request.intent != direct_intent:
                yield FunctionResult(
                    request,
                    replace(state, phase="blocked", terminal_status="intent_mismatch"),
                    label="route_direct_mismatch_blocked",
                )
                return

        if request.entrypoint == "researchguard":
            if (
                request.admission_row_count != 4
                or not request.task_facts_current
                or request.primary_action_fact_count < 1
                or not request.source_spans_valid
                or not request.forbidden_review_complete
            ):
                yield FunctionResult(
                    request,
                    replace(state, phase="blocked", terminal_status="task_facts_invalid"),
                    label="task_facts_invalid_blocked",
                )
                return
            if (
                len(set(request.minimum_sufficient_members)) != len(request.minimum_sufficient_members)
                or any(member not in MEMBER_PATHS for member in request.minimum_sufficient_members)
            ):
                yield FunctionResult(
                    request,
                    replace(state, phase="blocked", terminal_status="admission_malformed"),
                    label="member_admission_malformed_blocked",
                )
                return
            if not request.minimum_sufficient_members:
                yield FunctionResult(
                    request,
                    replace(state, phase="blocked", terminal_status="no_match"),
                    label="member_admission_no_match_blocked",
                )
                return
            if len(request.minimum_sufficient_members) == 1:
                if request.composition_member_ids:
                    yield FunctionResult(
                        request,
                        replace(state, phase="blocked", terminal_status="over_selection"),
                        label="member_over_selection_blocked",
                    )
                    return
                member_id = request.minimum_sufficient_members[0]
                primary_path_id = MEMBER_PATHS[member_id]
            else:
                if (
                    tuple(request.composition_member_ids) != tuple(request.minimum_sufficient_members)
                    or not request.composition_valid
                ):
                    yield FunctionResult(
                        request,
                        replace(state, phase="blocked", terminal_status="composition_invalid"),
                        label="member_composition_invalid_blocked",
                    )
                    return
                yield FunctionResult(
                    request,
                    replace(
                        state,
                        phase="composition_ready",
                        member_id="+".join(request.minimum_sufficient_members),
                        primary_path_id="researchguard.composition",
                        terminal_status="planning_only",
                    ),
                    label="member_composition_ready",
                )
                return
        else:
            selected = MEMBER_BY_INTENT.get(request.intent)
            if selected is None:
                yield FunctionResult(
                    request,
                    replace(state, phase="blocked", terminal_status="intent_mismatch"),
                    label="route_direct_mismatch_blocked",
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


class ValidatePromptLoad:
    name = "ValidatePromptLoad"
    accepted_input_type = ResearchRequest
    reads = (
        "phase",
        "member_id",
        "selected_member_load_count",
        "nonselected_member_load_count",
        "untriggered_reference_count",
        "deep_triggered",
        "deep_reference_loaded",
    )
    writes = ("phase", "terminal_status")
    input_description = "one routed member plus its declared conditional prompt-load graph"
    output_description = "one selected-only prompt load or a visible load gap"
    idempotency = "the same route and triggers admit the same files"

    def apply(self, request: ResearchRequest, state: RouteState):
        if state.phase != "routed":
            yield FunctionResult(request, state, label="prompt_load_not_run")
            return
        if (
            request.selected_member_load_count != 1
            or request.nonselected_member_load_count != 0
            or request.untriggered_reference_count != 0
        ):
            yield FunctionResult(
                request,
                replace(state, phase="blocked", terminal_status="prompt_load_invalid"),
                label="prompt_load_invalid_blocked",
            )
            return
        if request.deep_triggered and not request.deep_reference_loaded:
            yield FunctionResult(
                request,
                replace(state, phase="blocked", terminal_status="deep_reference_missing"),
                label="deep_reference_missing_blocked",
            )
            return
        yield FunctionResult(request, state, label="prompt_load_selected_only")


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
            "experimentguard": "experiment_discrimination",
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
        (Route(), ValidatePromptLoad(), ExecuteMember(), OrchestrateHandoff()),
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
            description="Source-bound umbrella dispatch reaches the same sole logic path.",
            initial_state=RouteState(),
            external_input_sequence=(
                ResearchRequest(
                    "argument_licensing",
                    admission_row_count=4,
                    minimum_sufficient_members=("logicguard",),
                ),
            ),
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
            description="A complete derived admission set with no match blocks before native execution.",
            initial_state=RouteState(),
            external_input_sequence=(
                ResearchRequest("unknown", admission_row_count=4),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("member_admission_no_match_blocked",),
                summary="zero member admission is visible",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="RG04_member_failure_terminal",
            description="Selected SourceGuard failure cannot reroute to another member.",
            initial_state=RouteState(),
            external_input_sequence=(
                ResearchRequest(
                    "evidence_discovery",
                    admission_row_count=4,
                    minimum_sufficient_members=("sourceguard",),
                    native_status="failed",
                ),
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
                    admission_row_count=4,
                    minimum_sufficient_members=("logicguard",),
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
                ResearchRequest(
                    "trace_reconstruction",
                    admission_row_count=4,
                    minimum_sufficient_members=("traceguard",),
                    already_routed=True,
                ),
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
        Scenario(
            name="RG09_direct_experiment",
            description=(
                "Direct ExperimentGuard selects the sole recommendation-only "
                "experiment path."
            ),
            initial_state=RouteState(),
            external_input_sequence=(
                ResearchRequest(
                    "experiment_discrimination",
                    entrypoint="experimentguard",
                ),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=(
                    "route_selected_experimentguard",
                    "member_terminal_pass",
                ),
                summary=(
                    "direct experiment reaches researchguard.experiment"
                ),
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="RG10_minimum_pair_composition_ready",
            description="Two irreducible owners are accepted only through one exact composition.",
            initial_state=RouteState(),
            external_input_sequence=(
                ResearchRequest(
                    "cross_guard_research",
                    admission_row_count=4,
                    primary_action_fact_count=2,
                    minimum_sufficient_members=("sourceguard", "traceguard"),
                    composition_member_ids=("sourceguard", "traceguard"),
                    composition_valid=True,
                ),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("member_composition_ready",),
                summary="necessary pair yields planning-only composition evidence",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="RG11_stale_task_facts_block",
            description="Incomplete or stale task facts cannot select a route.",
            initial_state=RouteState(),
            external_input_sequence=(
                ResearchRequest(
                    "argument_licensing",
                    admission_row_count=4,
                    minimum_sufficient_members=("logicguard",),
                    task_facts_current=False,
                ),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("task_facts_invalid_blocked",),
                summary="stale task facts block before execution",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="RG12_nonselected_member_load_blocks",
            description="An exact route cannot eagerly load a sibling member.",
            initial_state=RouteState(),
            external_input_sequence=(
                ResearchRequest(
                    "argument_licensing",
                    entrypoint="logicguard",
                    nonselected_member_load_count=1,
                ),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("prompt_load_invalid_blocked",),
                summary="sibling prompt load is visible and blocked",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="RG13_deep_trigger_requires_reference",
            description="A fired deep trigger cannot remain on the entry shell.",
            initial_state=RouteState(),
            external_input_sequence=(
                ResearchRequest(
                    "trace_reconstruction",
                    entrypoint="traceguard",
                    deep_triggered=True,
                    deep_reference_loaded=False,
                ),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("deep_reference_missing_blocked",),
                summary="deep trigger requires its owning reference",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="RG14_over_selection_blocks",
            description="A caller cannot compose siblings when one member is sufficient.",
            initial_state=RouteState(),
            external_input_sequence=(
                ResearchRequest(
                    "argument_licensing",
                    admission_row_count=4,
                    minimum_sufficient_members=("logicguard",),
                    composition_member_ids=("logicguard", "sourceguard"),
                    composition_valid=True,
                ),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("member_over_selection_blocked",),
                summary="one sufficient member rejects a larger set",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="RG15_incomplete_composition_blocks",
            description="A necessary pair without complete order, ownership, and handoff evidence blocks.",
            initial_state=RouteState(),
            external_input_sequence=(
                ResearchRequest(
                    "cross_guard_research",
                    admission_row_count=4,
                    primary_action_fact_count=2,
                    minimum_sufficient_members=("sourceguard", "traceguard"),
                    composition_member_ids=("sourceguard", "traceguard"),
                    composition_valid=False,
                ),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("member_composition_invalid_blocked",),
                summary="invalid composition never reaches member execution",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
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
