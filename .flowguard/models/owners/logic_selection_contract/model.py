"""Executable owner for the current explicit synthesis selection contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
MODEL_ID = "logic_selection_contract"
CODE_OWNER = "src/researchguard/logic/synthesis_contract.py"
TEST_OWNER = "tests/logic/test_synthesis_contract.py"
PROTECTED_FAILURE_IDS = (
    "researchguard:logic_selection_contract:legacy-top-n-fallback",
    "researchguard:logic_selection_contract:body-order-incomplete",
    "researchguard:logic_selection_contract:model-fingerprint-mismatch",
    "researchguard:logic_selection_contract:binding-identity-invalid",
)
KNOWN_GOOD_CASE_ID = "native:logic_selection_contract:current-good"
KNOWN_BAD_CASE_IDS = (
    "case:logic_selection_contract:legacy-top-n-fallback",
    "case:logic_selection_contract:body-order-incomplete",
    "case:logic_selection_contract:model-fingerprint-mismatch",
    "case:logic_selection_contract:binding-identity-invalid",
)


@dataclass(frozen=True)
class ContractState:
    explicit_schema: bool
    complete_body_order: bool
    current_model_identity: bool
    exact_source_bindings: bool
    acyclic_dependencies: bool

    @property
    def accepted(self) -> bool:
        return all((
            self.explicit_schema,
            self.complete_body_order,
            self.current_model_identity,
            self.exact_source_bindings,
            self.acyclic_dependencies,
        ))


def run_model() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
    from researchguard.logic.synthesis_contract import SYNTHESIS_REQUEST_SCHEMA, validate_selection_request
    assert SYNTHESIS_REQUEST_SCHEMA == "researchguard.logic.synthesis-request.v1"
    _normalized, errors = validate_selection_request({}, expected_model_id="current", expected_model_fingerprint="sha256:" + "0" * 64)
    assert "invalid_schema" in errors and "missing:selection_request" not in errors
    good = ContractState(True, True, True, True, True)
    assert good.accepted
    for index in range(5):
        values = [True] * 5
        values[index] = False
        assert not ContractState(*values).accepted


if __name__ == "__main__":
    run_model()
    print(f"{MODEL_ID}: pass")
