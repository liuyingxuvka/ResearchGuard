"""Finite composition kernel for the researchguard model mesh.

The kernel records the minimum sequence needed to connect a model to its
interfaces, bindings, and current evidence. It is a model-level contract, not
a request to rebuild the target software.
"""

from __future__ import annotations

from dataclasses import dataclass

FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
MODEL_ID = "compositional_verification_kernel"
PROTECTED_FAILURE_IDS = (
    "researchguard:compositional_verification_kernel:definition-missing",
    "researchguard:compositional_verification_kernel:binding-missing",
    "researchguard:compositional_verification_kernel:evidence-stale",
)
KNOWN_GOOD_CASE_ID = "native:compositional_verification_kernel:current-good"
KNOWN_BAD_CASE_IDS = (
    "native:compositional_verification_kernel:definition-missing",
    "native:compositional_verification_kernel:binding-missing",
    "native:compositional_verification_kernel:evidence-stale",
)

STAGES = ("model", "interface", "binding", "evidence")


@dataclass(frozen=True)
class CompositionState:
    completed: tuple[str, ...] = ()


def advance(state: CompositionState, stage: str) -> CompositionState:
    if stage not in STAGES:
        raise ValueError(f"unknown composition stage: {stage}")
    if state.completed and STAGES.index(stage) != STAGES.index(state.completed[-1]) + 1:
        raise ValueError("composition stages must advance in order")
    if not state.completed and stage != STAGES[0]:
        raise ValueError("composition must start with the model")
    return CompositionState(state.completed + (stage,))


def accept(state: CompositionState) -> bool:
    return state.completed == STAGES


def run_model() -> None:
    state = CompositionState()
    for stage in STAGES:
        state = advance(state, stage)
    assert accept(state)
    for missing in STAGES:
        candidate = tuple(stage for stage in STAGES if stage != missing)
        assert not accept(CompositionState(candidate))


if __name__ == "__main__":
    run_model()
    print("compositional_verification_kernel: pass")
