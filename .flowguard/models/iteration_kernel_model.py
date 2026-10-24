"""Finite shared lifecycle boundaries replayed against the actual kernel."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer

MODEL_ID = "iteration_kernel"
PARENT = "researchguard-suite"
COMPONENTS = ["researchguard-suite"]
IMPLEMENTED_BY = {"Identity": "src/researchguard/iteration.py:require_prediction_identity",
                  "Candidate": "src/researchguard/iteration.py:validate_candidate",
                  "Terminal": "src/researchguard/iteration.py:select_terminal"}
TESTED_BY = {
    "stale_prediction_is_refused": ["tests/test_iteration.py:test_prediction_identity_is_content_bound"],
    "candidate_never_overwrites_current": ["tests/test_iteration.py:test_candidate_never_overwrites_current"],
    "no_progress_is_stalled": ["tests/test_iteration.py:test_no_progress_is_stalled"],
    "limit_stops_iteration": ["tests/test_iteration.py:test_limit_stops_iteration"],
}
EXPECTED = {"stale": True, "same_path": True, "same_content": True, "stalled": "progress_stalled", "limit": "iteration_limit"}


@dataclass(frozen=True)
class State:
    case: str = ""
    outcome: object = None


class Check:
    name = "Identity"
    reads = ()
    writes = ("case", "outcome")
    broken = ""

    def apply(self, case, state):
        value = EXPECTED[case]
        if case == self.broken:
            value = False if isinstance(value, bool) else "continue_iteration"
        yield FunctionResult(value, State(case, value), label=case)


def rule(cases):
    def check(state, trace):
        if state.case in cases and state.outcome != EXPECTED[state.case]:
            return InvariantResult.fail(f"{state.case}: unsafe shared lifecycle outcome")
        return InvariantResult.pass_()
    return check


INVARIANTS = (
    Invariant("stale_prediction_is_refused", "Changed baselines are refused.", rule(("stale",))),
    Invariant("candidate_never_overwrites_current", "Candidate paths and contents must differ.", rule(("same_path", "same_content"))),
    Invariant("no_progress_is_stalled", "No progress is visible.", rule(("stalled",))),
    Invariant("limit_stops_iteration", "The explicit iteration bound stops the loop.", rule(("limit",))),
)


def build_explorer(step=None):
    return Explorer(Workflow((step or Check(),)), (State(),), tuple(EXPECTED), INVARIANTS, progress_steps=0)


def broken_variants():
    result = {}
    for case in EXPECTED:
        step = Check()
        step.broken = case
        result[f"ignore_{case}"] = build_explorer(step)
    return result


def conformance():
    from flowguard.conformance import ConformanceReport, ConformanceViolation
    from flowguard.replay import ReplayObservation
    from researchguard.iteration import baseline_identity, require_prediction_identity, validate_candidate, select_terminal
    observed = {}
    try:
        require_prediction_identity(baseline_identity({"x": 1}), baseline_identity({"x": 2}))
    except ValueError as exc:
        observed["stale"] = str(exc).startswith("stale_prediction: re-freeze")
    with TemporaryDirectory() as directory:
        current, candidate = Path(directory) / "current", Path(directory) / "candidate"
        current.write_text("untouched")
        for case, path, plain in (("same_path", current, {"x": 2}), ("same_content", candidate, {"x": 1})):
            try:
                validate_candidate(current, path, {"x": 1}, plain)
            except ValueError:
                observed[case] = current.read_text() == "untouched" and not candidate.exists()
    observed["stalled"] = select_terminal(stalled=True)
    observed["limit"] = select_terminal(iteration=1, max_iterations=1)
    violations = tuple(ConformanceViolation(step_index=1, rule_name="Identity", message=f"{case}: {observed.get(case)!r}") for case in EXPECTED if observed.get(case) != EXPECTED[case])
    return ConformanceReport(ok=not violations, violations=violations,
        replayed_steps=tuple(ReplayObservation("Identity", value, State(case, value)) for case, value in observed.items()),
        summary="Actual identity refusal, candidate non-write and shared terminal selection.")
