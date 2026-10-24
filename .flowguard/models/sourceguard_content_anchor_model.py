"""FlowGuard contract model: SourceGuard blocks a contentless anchor with one finding.

Bound to the real code: conformance replays `_anchor_depth_rows` with and
without anchor content and reads `src/researchguard/source/depth.py` to check
that it emits the declared finding and never the retired one.
"""

from __future__ import annotations

from dataclasses import dataclass
import json

from flowguard import FunctionResult, Invariant, InvariantResult, Scenario, ScenarioExpectation, Workflow


MODEL_ID = "sourceguard_content_anchor"
PARENT = "sourceguard"
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
                "Content-bearing known-good case was blocked by the content-anchor check.",
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
        name="sourceguard_content_anchor_alignment",
    )


def invariants() -> tuple[Invariant, ...]:
    return (
        Invariant(
            "content_anchor_identity_is_singular",
            "Content-anchor depth reports one finding for contentless anchors.",
            content_anchor_identity_is_singular,
        ),
    )


def scenarios() -> tuple[Scenario, ...]:
    common = {"workflow": workflow(), "invariants": invariants()}
    return (
        Scenario(
            name=CONTENT_GOOD.case_id,
            description="Content-bearing anchor passes the content-anchor check.",
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


COMPONENTS = ["sourceguard"]
IMPLEMENTED_BY = {"content_qualification": "src/researchguard/source/depth.py:_anchor_depth_rows"}
TESTED_BY = {"content_anchor_identity_is_singular": ["tests/source/test_semantic_gap_depth.py:test_contentless_anchor_is_blocked_by_source_depth"]}


def build_explorer():
    from flowguard.explorer import Explorer
    return Explorer(workflow(), (AnchorDepthState(),), (CONTENT_GOOD, CONTENT_BAD_ALIGNED), invariants())


def broken_variants():
    from flowguard.explorer import Explorer
    return {"retired_finding": Explorer(workflow(), (AnchorDepthState(),), (CONTENT_BAD_DRIFTED,), invariants())}


def conformance():
    # Replay this checkout's src-layout owner even when a distribution is installed.
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from flowguard.conformance import ConformanceReport, ConformanceViolation
    from flowguard.replay import ReplayObservation
    from researchguard.source.depth import _anchor_depth_rows
    from researchguard.source.schema import BeliefState, EvidenceAnchor, SourceRecord
    observations = []
    violations = []
    for content in (True, False):
        state = BeliefState(sources=[SourceRecord(source_id="source:model", source_type="paper",
            source_role="primary_source", source_reliability=0.95, access_status="public")],
            anchors=[EvidenceAnchor(anchor_id="anchor:model", source_id="source:model", anchor_type="paragraph",
                locator="paragraph:1", modality="text", text="observed content" if content else "",
                extraction_confidence=0.95, specificity=0.95, supports=["gap:model"], usable_for_claim=True)])
        qualified = bool(_anchor_depth_rows(state)[0]["qualified"])
        observations.append(ReplayObservation("content_qualification", qualified, content))
        if qualified != content:
            violations.append(ConformanceViolation(step_index=1, message=f"native content qualification differs: {content}", rule_name="content_qualification"))
    # Code facts: the depth owner emits exactly the declared finding identity.
    source = (Path(__file__).resolve().parents[2] / "src" / "researchguard" / "source" / "depth.py").read_text(encoding="utf-8")
    emitted = (f'"{DECLARED_FINDING}"' in source, f'"{RETIRED_FINDING}"' in source)
    observations.append(ReplayObservation("finding_identity", emitted, (True, False)))
    if emitted != (True, False):
        violations.append(ConformanceViolation(step_index=1, message=f"depth.py finding identity differs: declared/retired present = {emitted}", rule_name="finding_identity"))
    return ConformanceReport(ok=not violations, violations=tuple(violations), replayed_steps=tuple(observations),
                             summary="Native anchor qualification replayed with and without content; the emitted finding identity read from depth.py.")
