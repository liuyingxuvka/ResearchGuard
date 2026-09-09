"""Executable FlowGuard owner for the current LogicGuard synthesis surface.

The model records the failures that the native synthesis owner must reject.
It does not select prose or reproduce the native argument evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
import ast
from pathlib import Path
import sys


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
MODEL_ID = "logic_synthesis"
CODE_OWNER = "src/researchguard/logic/synthesis.py"
TEST_OWNER = "tests/logic/test_artifact_synthesis.py"
PROTECTED_FAILURE_IDS = (
    "researchguard:logic_synthesis:selection-request-required",
    "researchguard:logic_synthesis:candidate-ledger-truncated",
    "researchguard:logic_synthesis:omit-delivered-to-body",
    "researchguard:logic_synthesis:foreign-support-closes-claim",
)
KNOWN_GOOD_CASE_ID = "native:logic_synthesis:current-good"
KNOWN_BAD_CASE_IDS = (
    "case:logic_synthesis:selection-request-required",
    "case:logic_synthesis:candidate-ledger-truncated",
    "case:logic_synthesis:omit-delivered-to-body",
    "case:logic_synthesis:foreign-support-closes-claim",
)


@dataclass(frozen=True)
class SynthesisState:
    selection_request_required: bool
    candidate_ledger_complete: bool
    omit_excluded_from_body: bool
    support_is_claim_local: bool

    @property
    def accepted(self) -> bool:
        return all((
            self.selection_request_required,
            self.candidate_ledger_complete,
            self.omit_excluded_from_body,
            self.support_is_claim_local,
        ))


def run_model() -> None:
    source_path = Path(__file__).resolve().parents[4] / "src/researchguard/logic/synthesis.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "synthesize_artifact_plan"]
    assert len(functions) == 1
    parameter = next((item for item in functions[0].args.kwonlyargs if item.arg == "selection_request"), None)
    assert parameter is not None
    assert len(functions[0].args.kw_defaults) == len(functions[0].args.kwonlyargs)
    index = [item.arg for item in functions[0].args.kwonlyargs].index("selection_request")
    assert functions[0].args.kw_defaults[index] is None
    good = SynthesisState(True, True, True, True)
    assert good.accepted
    for index in range(4):
        values = [True] * 4
        values[index] = False
        assert not SynthesisState(*values).accepted


if __name__ == "__main__":
    run_model()
    print(f"{MODEL_ID}: pass")
