"""FlowGuard child model for SourceGuard content-anchor oracle alignment.

Claim boundary: this model proves only the finite relation between a
content-anchor condition, the native blocking decision, and the emitted
finding identity. Native SourceGuard execution and tests remain separate
required evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import json

from flowguard import (
    FlowGuardCheckPlan,
    FunctionResult,
    Invariant,
    InvariantResult,
    KnownBadProof,
    MinimumModelContract,
    RiskIntent,
    RiskProfile,
    Scenario,
    ScenarioExpectation,
    StateClosureDimension,
    StateClosurePlan,
    TemplateHarvestReview,
    TemplateReuseReview,
    Workflow,
    review_scenarios,
    run_model_first_checks,
)


MODEL_ID = "researchguard.source.content_anchor_oracle.current"
PARENT_MODEL_ID = "researchguard.source.evidence_discovery.current"
DECLARED_FINDING = "sourceguard_blocked:contentless-anchor"
RETIRED_FINDING = "no_content_qualified_anchor"


@dataclass(frozen=True)
class AnchorDepthInput:
    case_id: str
    content_qualified: bool
    emitted_findings: tuple[str, ...]


@dataclass(frozen=True)
class AnchorDepthState:
    case_id: str = "not_run"
    content_qualified: bool = True
    depth_status: str = "not_run"
    emitted_findings: tuple[str, ...] = ()
    proof_status: str = "not_run"


CONTENT_GOOD = AnchorDepthInput(
    case_id="content-bearing-known-good",
    content_qualified=True,
    emitted_findings=(),
)
CONTENT_BAD_ALIGNED = AnchorDepthInput(
    case_id="contentless-known-bad-aligned",
    content_qualified=False,
    emitted_findings=(DECLARED_FINDING,),
)
CONTENT_BAD_DRIFTED = AnchorDepthInput(
    case_id="contentless-known-bad-drifted",
    content_qualified=False,
    emitted_findings=(RETIRED_FINDING,),
)


class EvaluateContentAnchorFinding:
    """Input x State -> Set(Output x State) for the owned identity boundary."""

    name = "EvaluateContentAnchorFinding"
    reads = ()
    writes = (
        "case_id",
        "content_qualified",
        "depth_status",
        "emitted_findings",
        "proof_status",
    )

    def apply(self, input_obj: AnchorDepthInput, state: AnchorDepthState):
        del state
        blocked = not input_obj.content_qualified
        finding_matches = DECLARED_FINDING in input_obj.emitted_findings
        return (
            FunctionResult(
                output=input_obj.case_id,
                new_state=AnchorDepthState(
                    case_id=input_obj.case_id,
                    content_qualified=input_obj.content_qualified,
                    depth_status="blocked" if blocked else "pass",
                    emitted_findings=input_obj.emitted_findings,
                    proof_status=(
                        "blocked_proven"
                        if blocked and finding_matches
                        else "good_proven"
                        if not blocked and not finding_matches
                        else "identity_mismatch"
                    ),
                ),
                label=input_obj.case_id,
            ),
        )


def content_anchor_identity_is_singular(
    state: AnchorDepthState,
    trace,
) -> InvariantResult:
    del trace
    if state.proof_status == "not_run":
        return InvariantResult.pass_()
    findings = set(state.emitted_findings)
    if state.content_qualified:
        if DECLARED_FINDING in findings or state.depth_status != "pass":
            return InvariantResult.fail(
                "Content-bearing known-good case was blocked by the content-anchor oracle.",
                {"case_id": state.case_id},
            )
        return InvariantResult.pass_()
    if state.depth_status != "blocked" or DECLARED_FINDING not in findings:
        return InvariantResult.fail(
            "Contentless known-bad case did not expose the catalog-declared blocking finding.",
            {
                "case_id": state.case_id,
                "expected": DECLARED_FINDING,
                "observed": sorted(findings),
            },
        )
    if RETIRED_FINDING in findings:
        return InvariantResult.fail(
            "Content-anchor depth retained the retired alternate finding.",
            {"case_id": state.case_id, "retired": RETIRED_FINDING},
        )
    return InvariantResult.pass_()


def workflow() -> Workflow:
    return Workflow(
        (EvaluateContentAnchorFinding(),),
        name="sourceguard_content_anchor_oracle_alignment",
    )


def invariants() -> tuple[Invariant, ...]:
    return (
        Invariant(
            "content_anchor_identity_is_singular",
            "Content-anchor depth and purpose proof use one catalog-declared finding.",
            content_anchor_identity_is_singular,
        ),
    )


def scenarios() -> tuple[Scenario, ...]:
    common = {"workflow": workflow(), "invariants": invariants()}
    return (
        Scenario(
            name=CONTENT_GOOD.case_id,
            description="Content-bearing anchor passes the content-anchor oracle.",
            initial_state=AnchorDepthState(),
            external_input_sequence=(CONTENT_GOOD,),
            expected=ScenarioExpectation(expected_status="ok", summary="known-good passes"),
            **common,
        ),
        Scenario(
            name=CONTENT_BAD_ALIGNED.case_id,
            description="Contentless anchor blocks with the declared current finding.",
            initial_state=AnchorDepthState(),
            external_input_sequence=(CONTENT_BAD_ALIGNED,),
            expected=ScenarioExpectation(expected_status="ok", summary="known-bad is proven"),
            **common,
        ),
        Scenario(
            name=CONTENT_BAD_DRIFTED.case_id,
            description="Observed v0.1.2 drift emits the retired finding identity.",
            initial_state=AnchorDepthState(),
            external_input_sequence=(CONTENT_BAD_DRIFTED,),
            expected=ScenarioExpectation(
                expected_status="violation",
                expected_violation_names=("content_anchor_identity_is_singular",),
                summary="drifted finding is rejected",
            ),
            **common,
        ),
    )


def formal_plan() -> FlowGuardCheckPlan:
    return FlowGuardCheckPlan(
        workflow=workflow(),
        initial_states=(AnchorDepthState(),),
        external_inputs=(CONTENT_GOOD, CONTENT_BAD_ALIGNED),
        invariants=invariants(),
        max_sequence_length=1,
        scenarios=scenarios(),
        risk_profile=RiskProfile(
            modeled_boundary=(
                "SourceGuard content-anchor native finding identity under the existing "
                "evidence-discovery owner"
            ),
            risk_classes=("contract_identity", "fail_closed_gate"),
            confidence_goal="model_level",
            risk_intent=RiskIntent(
                failure_modes=(
                    "contentless anchor is blocked under a finding code that the target-purpose proof cannot observe",
                ),
                protected_error_classes=("native_oracle_finding_drift",),
                protected_harms=(
                    "valid SourceGuard target contracts cannot prove their declared known-bad case",
                ),
                must_model_state=("content_qualified", "depth_status", "proof_status"),
                must_model_side_effects=("emitted_findings",),
                completion_evidence=("declared finding", "native receipt finding", "purpose proof status"),
                adversarial_inputs=("contentless anchor", "retired finding emission"),
                hard_invariants=("one current content-anchor finding identity",),
                known_bad_cases=(CONTENT_BAD_DRIFTED.case_id,),
                template_no_match_reason="project-specific SourceGuard oracle identity repair",
                blindspots=("anchor semantic qualification is owned and tested by SourceGuard",),
            ),
        ),
        template_reuse_review=TemplateReuseReview(
            no_match_reason="project-specific SourceGuard oracle identity repair",
            searched_layers=("public", "local"),
        ),
        minimum_model_contract=MinimumModelContract(
            protected_error_classes=("native_oracle_finding_drift",),
            modeled_state=("content_qualified", "depth_status", "proof_status"),
            modeled_side_effects=("emitted_findings",),
            completion_evidence=("declared finding", "native receipt finding", "purpose proof status"),
            known_bad_cases=(CONTENT_BAD_DRIFTED.case_id,),
        ),
        known_bad_proofs=(
            KnownBadProof(
                CONTENT_BAD_DRIFTED.case_id,
                protected_error_class="native_oracle_finding_drift",
                method="scenario_review",
                observed_status="failed",
                observed_failure=(
                    "v0.1.2 depth emitted no_content_qualified_anchor while the content-anchor oracle "
                    "declared sourceguard_blocked:contentless-anchor"
                ),
                evidence_id="reproduction:sourceguard-content-anchor-gate-v0.1.2",
            ),
        ),
        template_harvest_review=TemplateHarvestReview(
            disposition="not_harvestable",
            not_harvestable_reason="not_reusable_project_specific",
        ),
        state_closure_plan=StateClosurePlan(
            "sourceguard_content_anchor_closed_state",
            dimensions=(
                StateClosureDimension(
                    "external_input",
                    "external_input",
                    policy="open_boundary",
                    known_values=(CONTENT_GOOD, CONTENT_BAD_ALIGNED),
                    representative_unknowns=(
                        AnchorDepthInput("unsupported-input", False, ()),
                    ),
                    handling="reject_before_side_effect",
                ),
                StateClosureDimension(
                    "state.depth_status",
                    "state_field",
                    policy="closed_enumeration",
                    known_values=("not_run", "pass", "blocked"),
                    handling="reject_before_side_effect",
                ),
                StateClosureDimension(
                    "state.proof_status",
                    "state_field",
                    policy="closed_enumeration",
                    known_values=(
                        "not_run",
                        "good_proven",
                        "blocked_proven",
                        "identity_mismatch",
                    ),
                    handling="reject_before_side_effect",
                ),
            ),
            claim_scope="model_level",
            allow_scoped_confidence=False,
            notes="Unknown inputs reject before any external side effect.",
        ),
        scenario_matrix_config={"enabled": False},
        metadata={
            "model_id": MODEL_ID,
            "parent_model_id": PARENT_MODEL_ID,
            "claim_boundary": (
                "Model-level finding identity only; native SourceGuard and release checks remain required."
            ),
        },
    )


def main() -> int:
    scenario_report = review_scenarios(scenarios())
    formal_report = run_model_first_checks(formal_plan())
    print(scenario_report.format_text(max_counterexamples=3))
    print(formal_report.format_text())
    payload = {
        "artifact_kind": "sourceguard_content_anchor_oracle_flowguard_report",
        "model_id": MODEL_ID,
        "parent_model_id": PARENT_MODEL_ID,
        "scenario_status": "pass" if scenario_report.ok else "failed",
        "formal_status": formal_report.overall_status,
        "known_bad_rejected": scenario_report.ok,
        "claim_boundary": (
            "This proves the finite content-anchor finding identity relation only; "
            "native SourceGuard execution and tests remain required."
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    required_sections = {
        section.name: section.status
        for section in formal_report.sections
        if section.name
        in {
            "minimum_model_review",
            "known_bad_proof",
            "template_harvest_review",
            "model_quality_audit",
            "state_closure",
            "topology_hazard",
            "model_check",
            "scenario_review",
        }
    }
    required_pass = required_sections and all(
        status == "pass" for status in required_sections.values()
    )
    return 0 if scenario_report.ok and required_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
