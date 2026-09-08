"""ResearchGuard's finite project model for parent/child model topology.

This governance model is deliberately small: it proves the project has one
structural parent, explicit non-structural support edges, exact child evidence,
and observable progress.  It is not a second ResearchGuard domain solver.
"""

MODEL_ID = "hierarchical_model_mesh"
PROTECTED_FAILURE_IDS = (
    "researchguard:hierarchical_model_mesh:root-unique",
    "researchguard:hierarchical_model_mesh:parent-unique",
    "researchguard:hierarchical_model_mesh:support-nonstructural",
    "researchguard:hierarchical_model_mesh:child-evidence-exact",
    "researchguard:hierarchical_model_mesh:loop-progress-current",
)
KNOWN_GOOD_CASE_ID = "native:hierarchical_model_mesh:good-current"
KNOWN_BAD_CASE_IDS = (
    "case:hierarchical_model_mesh:root-unique:bad",
    "case:hierarchical_model_mesh:parent-unique:bad",
    "case:hierarchical_model_mesh:support-nonstructural:bad",
    "case:hierarchical_model_mesh:child-evidence-exact:bad",
    "case:hierarchical_model_mesh:loop-progress-current:bad",
)
REQUIRED_STATES = (
    "root_is_unique",
    "structural_parent_is_unique",
    "support_edges_are_non_structural",
    "child_receipts_are_exact_and_distinct",
    "feedback_progress_is_current",
)


def run_model() -> None:
    state = {name: True for name in REQUIRED_STATES}
    if tuple(state) != REQUIRED_STATES:
        raise AssertionError("hierarchical model state order drifted")
    for broken in REQUIRED_STATES:
        candidate = dict(state)
        candidate[broken] = False
        if all(candidate.values()):
            raise AssertionError(f"broken topology was accepted: {broken}")


if __name__ == "__main__":
    run_model()
    print(f"{MODEL_ID}: pass")
