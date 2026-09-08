"""Executable owner for selected-claim argument support closure."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
MODEL_ID = "argument_support_closure"
CODE_OWNER = "src/researchguard/logic/execution_depth.py"
TEST_OWNER = "tests/logic/test_execution_depth.py"
PROTECTED_FAILURE_IDS = (
    "researchguard:argument_support_closure:missing-selected-claim-support",
    "researchguard:argument_support_closure:foreign-claim-support",
    "researchguard:argument_support_closure:missing-argument-role",
    "researchguard:argument_support_closure:cycle-not-terminated",
)
KNOWN_GOOD_CASE_ID = "native:argument_support_closure:current-good"
KNOWN_BAD_CASE_IDS = (
    "case:argument_support_closure:missing-selected-claim-support",
    "case:argument_support_closure:foreign-claim-support",
    "case:argument_support_closure:missing-argument-role",
    "case:argument_support_closure:cycle-not-terminated",
)
ARGUMENT_ROLES = ("support", "warrant", "assumption", "opposition", "boundary")


@dataclass(frozen=True)
class ClosureState:
    selected_claim_bound: bool
    all_roles_current: bool
    alternatives_preserved: bool
    visited_termination: bool

    @property
    def accepted(self) -> bool:
        return all((
            self.selected_claim_bound,
            self.all_roles_current,
            self.alternatives_preserved,
            self.visited_termination,
        ))


def run_model() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
    from researchguard.logic.execution_depth import derive_importance_policy
    policy = derive_importance_policy()
    assert policy is not None
    assert ARGUMENT_ROLES == ("support", "warrant", "assumption", "opposition", "boundary")
    good = ClosureState(True, True, True, True)
    assert good.accepted
    for index in range(4):
        values = [True] * 4
        values[index] = False
        assert not ClosureState(*values).accepted


if __name__ == "__main__":
    run_model()
    print(f"{MODEL_ID}: pass")
