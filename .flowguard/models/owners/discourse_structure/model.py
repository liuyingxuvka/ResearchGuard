"""Executable owner for cross-block discourse contribution structure."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
MODEL_ID = "discourse_structure"
CODE_OWNER = "src/researchguard/logic/structure_audit.py"
TEST_OWNER = "tests/logic/test_structured_artifact.py"
PROTECTED_FAILURE_IDS = (
    "researchguard:discourse_structure:missing-parent-contribution",
    "researchguard:discourse_structure:missing-downstream-consumer",
    "researchguard:discourse_structure:missing-sibling-progression",
    "researchguard:discourse_structure:unrecovered-conclusion-obligation",
    "researchguard:discourse_structure:missing-structure-input",
)
KNOWN_GOOD_CASE_ID = "native:discourse_structure:current-good"
KNOWN_BAD_CASE_IDS = (
    "case:discourse_structure:missing-parent-contribution",
    "case:discourse_structure:missing-downstream-consumer",
    "case:discourse_structure:missing-sibling-progression",
    "case:discourse_structure:unrecovered-conclusion-obligation",
    "case:discourse_structure:missing-structure-input",
)


@dataclass(frozen=True)
class StructureState:
    structure_input_present: bool
    parent_contribution_bound: bool
    downstream_consumer_bound: bool
    sibling_progression_bound: bool
    conclusion_recovered: bool

    @property
    def accepted(self) -> bool:
        return all((
            self.structure_input_present,
            self.parent_contribution_bound,
            self.downstream_consumer_bound,
            self.sibling_progression_bound,
            self.conclusion_recovered,
        ))


def run_model() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
    from researchguard.logic.model import LogicModel
    from researchguard.logic.structure_audit import audit_structure
    native_report = audit_structure(LogicModel(id="native-structure-check"), {})
    assert native_report.findings and native_report.findings[0].code == "coverage_gap"
    good = StructureState(True, True, True, True, True)
    assert good.accepted
    for index in range(5):
        values = [True] * 5
        values[index] = False
        assert not StructureState(*values).accepted


if __name__ == "__main__":
    run_model()
    print(f"{MODEL_ID}: pass")
