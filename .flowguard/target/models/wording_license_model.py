"""A wording license cannot outrun native support, blockers or claim state."""
from dataclasses import dataclass, replace
from pathlib import Path

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer

MODEL_ID = "wording_license"
PARENT = "logic-evaluation"
COMPONENTS = ["logic-evaluation"]
IMPLEMENTED_BY = {"License": "src/researchguard/logic/minimal_sets.py:license_model_claim"}
USES = {
    'LoadModel': 'src/researchguard/logic/loader.py:load_model',
    'LoadModelFromDict': 'src/researchguard/logic/loader.py:load_model_from_dict',
}
NOT_MODELED = {
    "src/researchguard/logic/model.py:LogicModel._ensure_edge_indexes": "Rebuilds the in-memory edge index from the edge list; it never changes nodes, edges or argument state.",
    "src/researchguard/logic/model.py:LogicModel.rebuild_edge_indexes": "Rebuilds the in-memory edge index from the edge list; it never changes nodes, edges or argument state.",
}
TESTED_BY = {
    "blocked_claim_is_withheld": ["tests/logic/test_minimal_sets.py:test_blocked_claim_names_its_attackers"],
    "assert_needs_support_and_no_blocker": ["tests/logic/test_minimal_sets.py:test_missing_support_withholds_conclusion"],
    "license_never_exceeds_state": ["tests/logic/test_minimal_sets.py:test_model_claim_sets_come_from_the_model_evaluator"],
}


@dataclass(frozen=True)
class State:
    case: str = ""
    license: str = "withhold"
    support: bool = False
    blocker: bool = False
    claim_state: str = "UNDECIDED"


CASES = (State("blocked", "withhold", False, True, "OUT"),
         State("unsupported", "withhold", False, False, "UNDECIDED"),
         State("qualified", "qualify", True, True, "IN"),
         State("supported", "assert", True, False, "IN"))


class License:
    name = "License"
    reads = ()
    writes = ("case", "license", "support", "blocker", "claim_state")
    broken = ""

    def apply(self, case, state):
        result = replace(case, license="assert") if self.broken == case.case else case
        yield FunctionResult(result.license, result, label=case.case)


def blocked(state, trace):
    if state.case == "blocked" and state.license != "withhold":
        return InvariantResult.fail("a blocked claim was licensed")
    return InvariantResult.pass_()


def support(state, trace):
    if state.license == "assert" and (not state.support or state.blocker):
        return InvariantResult.fail("assert requires support without blockers")
    return InvariantResult.pass_()


def strength(state, trace):
    if state.case == "qualified" and state.license == "assert" or state.claim_state != "IN" and state.license != "withhold":
        return InvariantResult.fail("wording was upgraded beyond native evidence")
    return InvariantResult.pass_()


INVARIANTS = (Invariant("blocked_claim_is_withheld", "Blocked claims remain withheld.", blocked),
              Invariant("assert_needs_support_and_no_blocker", "Assertions need unblocked support.", support),
              Invariant("license_never_exceeds_state", "A qualified or non-IN claim is never upgraded.", strength))


def build_explorer(step=None):
    return Explorer(Workflow((step or License(),)), (State(),), CASES, INVARIANTS, progress_steps=0)


def broken_variants():
    result = {}
    for name, case in (("assert_despite_blocker", "blocked"), ("assert_without_support", "unsupported"), ("qualify_upgraded_to_assert", "qualified")):
        step = License()
        step.broken = case
        result[name] = build_explorer(step)
    return result


def conformance():
    from flowguard.conformance import ConformanceReport, ConformanceViolation
    from flowguard.replay import ReplayObservation
    from researchguard.logic.loader import load_model, load_model_from_dict
    from researchguard.logic.minimal_sets import license_model_claim
    root = Path(__file__).resolve().parents[2]
    qualified = load_model_from_dict({"model": {"id": "qualified", "root_claim": "C"}, "nodes": {
        "C": {"type": "Claim", "text": "claim", "confidence": .8},
        "E": {"type": "Evidence", "text": "support", "confidence": .9},
        "R": {"type": "Rebuttal", "text": "counter", "confidence": .9, "active": False}},
        "edges": [{"source": "E", "target": "C", "type": "supports", "weight": .9},
                  {"source": "R", "target": "C", "type": "attacks", "weight": .9}],
        "acceptance": {"C": {"any_of": ["E"], "no_undefeated_rebuttal": True}}})
    unsupported = load_model_from_dict({"model": {"id": "unsupported"}, "nodes": {"C": {"type": "Claim", "text": "claim"}}, "edges": []})
    fixtures = ((load_model(root / "tests/logic/fixtures/evergiven/lg_v1.yaml"), "C0"),
                (unsupported, "C"), (qualified, "C"),
                (load_model(root / "examples/logic/structured_artifact_deck.yaml"), "C1"))
    observations, violations = [], []
    for case, (model, claim) in zip(CASES, fixtures):
        actual = license_model_claim(model, claim)
        observations.append(ReplayObservation("License", actual.wording_license, replace(case, license=actual.wording_license)))
        if actual.wording_license != case.license:
            violations.append(ConformanceViolation(step_index=1, rule_name="License", message=f"{case.case}: {actual.wording_license} != {case.license}"))
    return ConformanceReport(ok=not violations, violations=tuple(violations), replayed_steps=tuple(observations),
        summary="Four actual argument models exercise blocked, unsupported, qualified and supported wording.")
