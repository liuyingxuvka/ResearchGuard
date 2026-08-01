"""ExperimentGuard-owned admission contract for the ResearchGuard umbrella."""

from __future__ import annotations

from typing import Any, Mapping

from ..admission import CONTRACT_SCHEMA, TaskFactPacket, contract_fingerprint as _fingerprint, derive_member_admission_evidence


CONTRACT = {
    "schema_version": CONTRACT_SCHEMA,
    "contract_id": "researchguard.member-admission.experimentguard.v2",
    "member_id": "experimentguard",
    "positive_conditions": [
        {
            "condition_id": "experiment.primary.discriminating-set",
            "any_fact_kinds": ["experiment.discriminating_set"],
            "first_action": "Freeze the declared hypothesis and finite candidate-experiment inventories.",
            "first_reference": "SKILL.md#required-inputs",
        }
    ],
    "required_conditions": [
        {"condition_id": "experiment.required.explicit-hypotheses", "any_fact_kinds": ["experiment.explicit_hypotheses"]},
        {"condition_id": "experiment.required.finite-candidates", "any_fact_kinds": ["experiment.finite_candidates"]},
        {"condition_id": "experiment.required.predicted-outcomes", "any_fact_kinds": ["experiment.predicted_outcomes"]},
    ],
    "forbidden_conditions": [
        {"condition_id": "experiment.forbidden.execution", "any_fact_kinds": ["experiment.execution_requested"]},
        {"condition_id": "experiment.forbidden.physical-diagnosis", "any_fact_kinds": ["physics.diagnosis"]},
        {"condition_id": "experiment.forbidden.software-test-selection", "any_fact_kinds": ["software.test_selection"]},
    ],
}


def contract_fingerprint() -> str:
    return _fingerprint(CONTRACT)


def author_admission_evidence(*, task_facts: TaskFactPacket) -> Mapping[str, Any]:
    return derive_member_admission_evidence(CONTRACT, task_facts)


__all__ = ["CONTRACT", "author_admission_evidence", "contract_fingerprint"]
