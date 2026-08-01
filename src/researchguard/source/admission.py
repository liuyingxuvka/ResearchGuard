"""SourceGuard-owned admission contract for the ResearchGuard umbrella."""

from __future__ import annotations

from typing import Any, Mapping

from ..admission import CONTRACT_SCHEMA, TaskFactPacket, contract_fingerprint as _fingerprint, derive_member_admission_evidence


CONTRACT = {
    "schema_version": CONTRACT_SCHEMA,
    "contract_id": "researchguard.member-admission.sourceguard.v2",
    "member_id": "sourceguard",
    "positive_conditions": [
        {
            "condition_id": "source.primary.discovery",
            "any_fact_kinds": ["source.primary_discovery"],
            "first_action": "Declare the target claim and source-role gaps before choosing a search action.",
            "first_reference": "references/source-model-protocol.md",
        }
    ],
    "required_conditions": [
        {"condition_id": "source.required.discovery-target", "any_fact_kinds": ["source.primary_discovery"]}
    ],
    "forbidden_conditions": [
        {"condition_id": "source.forbidden.final-argument-license", "any_fact_kinds": ["source.final_argument_license"]},
        {"condition_id": "source.forbidden.storyline-inference", "any_fact_kinds": ["source.storyline_inference"]},
        {"condition_id": "source.forbidden.experiment-execution", "any_fact_kinds": ["source.experiment_execution"]},
    ],
}


def contract_fingerprint() -> str:
    return _fingerprint(CONTRACT)


def author_admission_evidence(*, task_facts: TaskFactPacket) -> Mapping[str, Any]:
    return derive_member_admission_evidence(CONTRACT, task_facts)


__all__ = ["CONTRACT", "author_admission_evidence", "contract_fingerprint"]
