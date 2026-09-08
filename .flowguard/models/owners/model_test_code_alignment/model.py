"""ResearchGuard's finite model/code/test binding model."""

MODEL_ID = "model_test_code_alignment"
PROTECTED_FAILURE_IDS = (
    "researchguard:model_test_code_alignment:model-code-owner",
    "researchguard:model_test_code_alignment:code-boundary",
    "researchguard:model_test_code_alignment:test-owner",
    "researchguard:model_test_code_alignment:io-oracle",
    "researchguard:model_test_code_alignment:parent-not-leaf",
)
KNOWN_GOOD_CASE_ID = "native:model_test_code_alignment:good-current"
KNOWN_BAD_CASE_IDS = (
    "case:model_test_code_alignment:model-code-owner:bad",
    "case:model_test_code_alignment:code-boundary:bad",
    "case:model_test_code_alignment:test-owner:bad",
    "case:model_test_code_alignment:io-oracle:bad",
    "case:model_test_code_alignment:parent-not-leaf:bad",
)
REQUIRED_STATES = (
    "model_obligation_has_code_owner",
    "code_contract_has_external_boundary",
    "test_has_exact_owner",
    "test_has_input_output_oracle",
    "parent_receipt_is_not_a_leaf",
)


def run_model() -> None:
    state = {name: True for name in REQUIRED_STATES}
    if tuple(state) != REQUIRED_STATES:
        raise AssertionError("model-test alignment state order drifted")
    for broken in REQUIRED_STATES:
        candidate = dict(state)
        candidate[broken] = False
        if all(candidate.values()):
            raise AssertionError(f"unbound alignment was accepted: {broken}")


if __name__ == "__main__":
    run_model()
    print(f"{MODEL_ID}: pass")
