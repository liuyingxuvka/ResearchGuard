"""TraceGuard-owned admission contract for the ResearchGuard umbrella."""

from __future__ import annotations

from typing import Any, Mapping

from ..admission import CONTRACT_SCHEMA, TaskFactPacket, contract_fingerprint as _fingerprint, derive_member_admission_evidence


CONTRACT = {
    "schema_version": CONTRACT_SCHEMA,
    "contract_id": "researchguard.member-admission.traceguard.v2",
    "member_id": "traceguard",
    "positive_conditions": [
        {
            "condition_id": "trace.primary.reconstruction",
            "any_fact_kinds": ["trace.temporal_reconstruction"],
            "first_action": "Declare the trace scope, evidence objects, and competing storylines before inference.",
            "first_reference": "references/routes/general-trace.md",
        },
        {
            "condition_id": "trace.primary.case-library",
            "any_fact_kinds": ["trace.case_library"],
            "first_action": "Preserve the messy case material and search direction before building a trace model.",
            "first_reference": "references/routes/case-library.md",
        },
    ],
    "required_conditions": [
        {"condition_id": "trace.required.trace-target", "any_fact_kinds": ["trace.temporal_reconstruction", "trace.case_library"]}
    ],
    "forbidden_conditions": [
        {"condition_id": "trace.forbidden.primary-source-search", "any_fact_kinds": ["trace.primary_source_search"]},
        {"condition_id": "trace.forbidden.final-argument-license", "any_fact_kinds": ["trace.final_argument_license"]},
        {"condition_id": "trace.forbidden.experiment-execution", "any_fact_kinds": ["trace.experiment_execution"]},
    ],
}


def contract_fingerprint() -> str:
    return _fingerprint(CONTRACT)


def author_admission_evidence(*, task_facts: TaskFactPacket) -> Mapping[str, Any]:
    return derive_member_admission_evidence(CONTRACT, task_facts)


__all__ = ["CONTRACT", "author_admission_evidence", "contract_fingerprint"]
