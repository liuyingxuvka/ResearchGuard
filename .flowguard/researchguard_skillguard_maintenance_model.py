"""Executable FlowGuard model for ResearchGuard SkillGuard maintenance.

The model extends the four existing member contract exports. It governs only
author-maintenance order, structural ownership, validation inventory, and the
no-install/no-predecessor-write boundary. Target skills retain domain meaning.
"""

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

from researchguard_skill_contract_model_common import MEMBERS, build_contract_model


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
MAINTENANCE_UNIT_ID = "unit:researchguard-suite"
MEMBER_SET = frozenset(MEMBERS)


def declared_check_ids(member: str) -> tuple[str, str]:
    model = build_contract_model(member)
    obligations = tuple(row["obligation_id"] for row in model["obligations"])
    if len(obligations) != 2:
        raise ValueError(f"{member} must retain exactly two target-owned obligations")
    return (
        f"check:{member}:consumer-contract",
        f"check:{member}:native-tests",
    )


DECLARED_CHECKS = tuple(
    check_id for member in MEMBERS for check_id in declared_check_ids(member)
)

STRUCTURE_MESH = {
    "mesh_id": "researchguard.skillguard-maintenance.structure.current",
    "source_model_ids": [
        build_contract_model(member)["model_id"] for member in MEMBERS
    ],
    "parent_surface": "researchguard-suite",
    "facade": "single researchguard Python distribution plus four consumer SKILL.md entrypoints",
    "children": [
        {
            "member_id": member,
            "public_entrypoint": f"skills/{member}/SKILL.md",
            "author_contract_root": f"skills/{member}/.skillguard",
            "function_blocks": [
                f"function:researchguard:{member}",
                f"step:researchguard:{member}:contract",
                f"step:researchguard:{member}:tests",
            ],
            "state_owner": f"owner:researchguard:{member}",
            "side_effect_owner": "skillguard-current-compiler",
            "validation_ids": list(declared_check_ids(member)),
        }
        for member in MEMBERS
    ],
    "protected_external_surfaces": [
        "old-logicguard-repository",
        "old-sourceguard-repository",
        "old-traceguard-repository",
    ],
    "dependency_cycles": [],
    "alternate_success_paths": [],
}

TEST_MESH = {
    "mesh_id": "researchguard.skillguard-maintenance.tests.current",
    "source_model_id": "researchguard.skillguard-maintenance.process.current",
    "inventory_revision": "four-members-eight-target-declared-checks",
    "parent_gate": "unit:researchguard-suite:affected-validation",
    "required_check_ids": list(DECLARED_CHECKS),
    "child_suites": [
        {
            "suite_id": f"suite:{member}:declared-checks",
            "member_id": member,
            "owned_check_ids": list(declared_check_ids(member)),
            "execution_owner_count": 2,
            "release_scope": "routine-local-maintenance",
        }
        for member in MEMBERS
    ],
    "open_spec_is_test_evidence": False,
    "cross_unit_receipt_reuse": False,
}

DEVELOPMENT_PROCESS = {
    "model_id": "researchguard.skillguard-maintenance.process.current",
    "modes": {
        "plan_detailing": "not_needed",
        "strategy_selection": "not_needed",
        "agent_workflow": "active",
        "execution_freshness": "active",
    },
    "ordered_steps": [
        "openspec-context",
        "existing-model-preflight",
        "flowguard-structure-and-test-boundary",
        "skillguard-author-adoption",
        "direct-current-contract-compile",
        "same-unit-declared-check-validation",
        "consumer-projection-diff",
        "bounded-local-closure",
    ],
    "hard_stops": [
        "peer-write-overlap",
        "foreign-maintenance-unit",
        "inferred-domain-check",
        "stale-or-nonterminal-declared-evidence",
        "consumer-author-state-leak",
        "global-install-attempt",
        "predecessor-repository-write",
    ],
    "freshness_domains": [
        "repository-source",
        "flowguard-models",
        "skillguard-contract-authority",
        "owner-evidence",
        "consumer-projection",
        "installed-consumer-content",
        "git-worktree",
    ],
    "excluded_claims": ["installation", "publication", "predecessor-retirement"],
}


@dataclass(frozen=True)
class MaintenanceRequest:
    action: str
    member_id: str = ""
    source_contract_current: bool = True
    declared_check_count: int = 2
    check_status: str = "pass"
    consumer_has_author_leak: bool = False
    activate_installation: bool = False
    write_predecessor_repository: bool = False
    foreign_maintenance_unit: bool = False


@dataclass(frozen=True)
class MaintenanceState:
    phase: str = "planned"
    maintenance_unit_id: str = ""
    members: tuple[str, ...] = ()
    compiled_members: tuple[str, ...] = ()
    validated_check_ids: tuple[str, ...] = ()
    audited_consumers: tuple[str, ...] = ()
    terminal_status: str = ""
    domain_check_additions: int = 0
    predecessor_write_count: int = 0
    installation_activated: bool = False


def _append_once(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    return values if value in values else (*values, value)


class BindAuthorUnit:
    name = "BindAuthorUnit"
    accepted_input_type = MaintenanceRequest
    reads = ("action", "foreign_maintenance_unit", "write_predecessor_repository")
    writes = ("phase", "maintenance_unit_id", "members", "terminal_status")
    input_description = "one explicit current author-adoption request"
    output_description = "one four-member maintenance-unit authority or a visible block"
    idempotency = "the same four-member inventory binds the same single unit"

    def apply(self, request: MaintenanceRequest, state: MaintenanceState):
        if request.action != "adopt":
            yield FunctionResult(request, state, label="adoption_not_requested")
            return
        if state.phase != "planned":
            yield FunctionResult(request, replace(state, phase="blocked", terminal_status="order"), label="maintenance_order_blocked")
            return
        if request.foreign_maintenance_unit:
            yield FunctionResult(request, replace(state, phase="blocked", terminal_status="foreign_unit"), label="foreign_unit_blocked")
            return
        if request.write_predecessor_repository:
            yield FunctionResult(request, replace(state, phase="blocked", terminal_status="predecessor_write"), label="predecessor_write_blocked")
            return
        yield FunctionResult(
            request,
            replace(state, phase="adopted", maintenance_unit_id=MAINTENANCE_UNIT_ID, members=MEMBERS),
            label="author_unit_bound",
        )


class CompileCurrentMember:
    name = "CompileCurrentMember"
    accepted_input_type = MaintenanceRequest
    reads = ("action", "member_id", "source_contract_current", "phase")
    writes = ("phase", "compiled_members", "terminal_status")
    input_description = "one member current source contract"
    output_description = "one directly regenerated current contract authority"
    idempotency = "a member source identity compiles to one canonical authority"

    def apply(self, request: MaintenanceRequest, state: MaintenanceState):
        if request.action != "compile":
            yield FunctionResult(request, state, label="compile_not_requested")
            return
        if state.phase not in {"adopted", "compiling"} or request.member_id not in MEMBER_SET:
            yield FunctionResult(request, replace(state, phase="blocked", terminal_status="compile_order"), label="maintenance_order_blocked")
            return
        if not request.source_contract_current:
            yield FunctionResult(request, replace(state, phase="blocked", terminal_status="source_contract"), label="source_contract_blocked")
            return
        compiled = _append_once(state.compiled_members, request.member_id)
        yield FunctionResult(request, replace(state, phase="compiling", compiled_members=compiled), label=f"compiled_{request.member_id}")


class ValidateDeclaredMember:
    name = "ValidateDeclaredMember"
    accepted_input_type = MaintenanceRequest
    reads = ("action", "member_id", "declared_check_count", "check_status")
    writes = ("phase", "validated_check_ids", "terminal_status", "domain_check_additions")
    input_description = "one member's exact two target-declared checks"
    output_description = "two current same-unit check identities or a visible block"
    idempotency = "each declared check id is attached at most once"

    def apply(self, request: MaintenanceRequest, state: MaintenanceState):
        if request.action != "validate":
            yield FunctionResult(request, state, label="validation_not_requested")
            return
        if set(state.compiled_members) != MEMBER_SET or request.member_id not in MEMBER_SET:
            yield FunctionResult(request, replace(state, phase="blocked", terminal_status="validation_order"), label="maintenance_order_blocked")
            return
        if request.declared_check_count != 2:
            additions = max(0, request.declared_check_count - 2)
            yield FunctionResult(request, replace(state, phase="blocked", terminal_status="check_inventory", domain_check_additions=additions), label="declared_check_inventory_blocked")
            return
        if request.check_status != "pass":
            yield FunctionResult(request, replace(state, phase="blocked", terminal_status=request.check_status), label="declared_evidence_blocked")
            return
        checks = state.validated_check_ids
        for check_id in declared_check_ids(request.member_id):
            checks = _append_once(checks, check_id)
        yield FunctionResult(request, replace(state, phase="validating", validated_check_ids=checks), label=f"validated_{request.member_id}")


class AuditConsumerProjection:
    name = "AuditConsumerProjection"
    accepted_input_type = MaintenanceRequest
    reads = ("action", "member_id", "consumer_has_author_leak", "activate_installation")
    writes = ("phase", "audited_consumers", "terminal_status", "installation_activated")
    input_description = "one target-owned clean consumer projection"
    output_description = "content-parity evidence without activation"
    idempotency = "each member projection is audited at most once"

    def apply(self, request: MaintenanceRequest, state: MaintenanceState):
        if request.action != "project":
            yield FunctionResult(request, state, label="projection_not_requested")
            return
        if set(state.validated_check_ids) != set(DECLARED_CHECKS) or request.member_id not in MEMBER_SET:
            yield FunctionResult(request, replace(state, phase="blocked", terminal_status="projection_order"), label="maintenance_order_blocked")
            return
        if request.consumer_has_author_leak:
            yield FunctionResult(request, replace(state, phase="blocked", terminal_status="consumer_leak"), label="consumer_author_leak_blocked")
            return
        if request.activate_installation:
            yield FunctionResult(request, replace(state, phase="blocked", terminal_status="installation_scope", installation_activated=True), label="installation_activation_blocked")
            return
        audited = _append_once(state.audited_consumers, request.member_id)
        terminal = set(audited) == MEMBER_SET
        yield FunctionResult(
            request,
            replace(state, phase="terminal" if terminal else "projecting", audited_consumers=audited, terminal_status="pass" if terminal else ""),
            label="unit_terminal_pass" if terminal else f"projected_{request.member_id}",
        )


def maintenance_invariants() -> tuple[Invariant, ...]:
    def one_unit(state: MaintenanceState, _trace):
        if state.maintenance_unit_id and (
            state.maintenance_unit_id != MAINTENANCE_UNIT_ID or set(state.members) != MEMBER_SET
        ):
            return InvariantResult.fail("author maintenance escaped the sole four-member unit")
        return InvariantResult.pass_()

    def no_added_depth(state: MaintenanceState, _trace):
        if state.domain_check_additions:
            return InvariantResult.fail("SkillGuard attempted to add target-domain depth")
        return InvariantResult.pass_()

    def no_external_mutation(state: MaintenanceState, _trace):
        if state.predecessor_write_count or state.installation_activated:
            return InvariantResult.fail("maintenance crossed the predecessor/install scope boundary")
        return InvariantResult.pass_()

    def exact_checks(state: MaintenanceState, _trace):
        if not set(state.validated_check_ids).issubset(set(DECLARED_CHECKS)):
            return InvariantResult.fail("validation contains a non-declared check")
        return InvariantResult.pass_()

    return (
        Invariant("one_four_member_unit", "One suite unit owns exactly four member author boundaries.", one_unit),
        Invariant("skillguard_adds_no_domain_depth", "Only target-declared checks may be validated.", no_added_depth),
        Invariant("no_install_or_predecessor_write", "This local maintenance change has no external activation or predecessor write.", no_external_mutation),
        Invariant("exact_eight_check_inventory", "Validated checks are a subset of the exact eight target declarations.", exact_checks),
    )


INVARIANTS = maintenance_invariants()


def build_workflow() -> Workflow:
    return Workflow(
        (BindAuthorUnit(), CompileCurrentMember(), ValidateDeclaredMember(), AuditConsumerProjection()),
        name="researchguard_skillguard_maintenance",
    )


def _good_sequence() -> tuple[MaintenanceRequest, ...]:
    return (
        MaintenanceRequest("adopt"),
        *(MaintenanceRequest("compile", member_id=member) for member in MEMBERS),
        *(MaintenanceRequest("validate", member_id=member) for member in MEMBERS),
        *(MaintenanceRequest("project", member_id=member) for member in MEMBERS),
    )


def scenarios() -> tuple[Scenario, ...]:
    workflow = build_workflow()
    compiled = tuple(MaintenanceRequest("compile", member_id=member) for member in MEMBERS)
    validated = tuple(MaintenanceRequest("validate", member_id=member) for member in MEMBERS)
    return (
        Scenario(
            name="SGM01_current_four_member_closure",
            description="Current adoption, direct compile, exact declared checks, and clean projection close locally.",
            initial_state=MaintenanceState(),
            external_input_sequence=_good_sequence(),
            expected=ScenarioExpectation(expected_status="ok", required_trace_labels=("author_unit_bound", "compiled_traceguard", "validated_traceguard", "unit_terminal_pass"), summary="four-member maintenance closes without install"),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="SGM02_predecessor_write_blocks",
            description="Old standalone repositories cannot become maintenance targets.",
            initial_state=MaintenanceState(),
            external_input_sequence=(MaintenanceRequest("adopt", write_predecessor_repository=True),),
            expected=ScenarioExpectation(expected_status="ok", required_trace_labels=("predecessor_write_blocked",), summary="predecessor write is visible and blocked"),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="SGM03_inferred_depth_blocks",
            description="A third inferred domain check cannot enter the frozen target inventory.",
            initial_state=MaintenanceState(),
            external_input_sequence=(MaintenanceRequest("adopt"), *compiled, MaintenanceRequest("validate", member_id="researchguard", declared_check_count=3)),
            expected=ScenarioExpectation(expected_status="violation", expected_violation_names=("skillguard_adds_no_domain_depth",), required_trace_labels=("declared_check_inventory_blocked",), summary="inferred target depth violates the hard boundary"),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="SGM04_consumer_leak_blocks",
            description="Author control state cannot enter a consumer projection.",
            initial_state=MaintenanceState(),
            external_input_sequence=(MaintenanceRequest("adopt"), *compiled, *validated, MaintenanceRequest("project", member_id="researchguard", consumer_has_author_leak=True)),
            expected=ScenarioExpectation(expected_status="ok", required_trace_labels=("consumer_author_leak_blocked",), summary="author-state leakage is rejected"),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="SGM05_install_activation_blocks",
            description="Projection comparison cannot activate the global installation.",
            initial_state=MaintenanceState(),
            external_input_sequence=(MaintenanceRequest("adopt"), *compiled, *validated, MaintenanceRequest("project", member_id="researchguard", activate_installation=True)),
            expected=ScenarioExpectation(expected_status="violation", expected_violation_names=("no_install_or_predecessor_write",), required_trace_labels=("installation_activation_blocked",), summary="global activation violates the scoped maintenance boundary"),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
    )


__all__ = [
    "DECLARED_CHECKS",
    "DEVELOPMENT_PROCESS",
    "INVARIANTS",
    "MAINTENANCE_UNIT_ID",
    "MEMBERS",
    "STRUCTURE_MESH",
    "TEST_MESH",
    "build_workflow",
    "scenarios",
]
