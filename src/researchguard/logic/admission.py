"""LogicGuard-owned admission contract for the ResearchGuard umbrella."""

from __future__ import annotations

from typing import Any, Mapping

from ..admission import (
    CONTRACT_SCHEMA,
    TaskFactPacket,
    contract_fingerprint as _contract_fingerprint,
    derive_member_admission_evidence,
)


CONTRACT = {
    "schema_version": CONTRACT_SCHEMA,
    "contract_id": "researchguard.member-admission.logicguard.v2",
    "member_id": "logicguard",
    "positive_conditions": [
        {
            "condition_id": "logic.primary.general-argument",
            "any_fact_kinds": ["logic.argument_structure", "logic.claim_licensing", "logic.mixed_workflow"],
            "first_action": "Build or inspect the current argument model and run its native structural checks.",
            "first_reference": "references/general-argument.md",
        },
        {
            "condition_id": "logic.primary.source-library",
            "any_fact_kinds": ["logic.source_library"],
            "first_action": "Preserve or reuse the concrete source in the LogicGuard source library.",
            "first_reference": "references/routes/source-library.md",
        },
        {
            "condition_id": "logic.primary.structured-artifact",
            "any_fact_kinds": ["logic.structured_artifact"],
            "first_action": "Map the artifact's natural structure before judging or rewriting it.",
            "first_reference": "references/routes/structured-artifact.md",
        },
        {
            "condition_id": "logic.primary.model-deepening",
            "any_fact_kinds": ["logic.model_deepening"],
            "first_action": "Select the highest-impact under-modeled node and deepen it in place.",
            "first_reference": "references/routes/model-deepening.md",
        },
        {
            "condition_id": "logic.primary.artifact-synthesis",
            "any_fact_kinds": ["logic.artifact_synthesis"],
            "first_action": "Freeze the target goal and synthesize one inspectable story plan from current models.",
            "first_reference": "references/routes/artifact-synthesis.md",
        },
        {
            "condition_id": "logic.primary.project-library-viewer",
            "any_fact_kinds": ["logic.project_library_viewer"],
            "first_action": "Open or check the read-only project-library viewer.",
            "first_reference": "references/routes/project-library-viewer.md",
        },
    ],
    "required_conditions": [
        {
            "condition_id": "logic.required.reasoning-target",
            "any_fact_kinds": [
                "logic.argument_structure", "logic.claim_licensing", "logic.mixed_workflow",
                "logic.source_library", "logic.structured_artifact", "logic.model_deepening",
                "logic.artifact_synthesis", "logic.project_library_viewer",
            ],
        }
    ],
    "forbidden_conditions": [
        {"condition_id": "logic.forbidden.silent-external-search", "any_fact_kinds": ["logic.silent_external_search"]},
        {"condition_id": "logic.forbidden.chronology-as-causality", "any_fact_kinds": ["logic.chronology_as_causality"]},
        {"condition_id": "logic.forbidden.experiment-execution", "any_fact_kinds": ["logic.experiment_execution"]},
    ],
}


def contract_fingerprint() -> str:
    return _contract_fingerprint(CONTRACT)


def author_admission_evidence(*, task_facts: TaskFactPacket) -> Mapping[str, Any]:
    return derive_member_admission_evidence(CONTRACT, task_facts)


__all__ = ["CONTRACT", "author_admission_evidence", "contract_fingerprint"]
