"""SourceGuard-owned admission contract for the ResearchGuard umbrella."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence


CONTRACT = {
    "contract_id": "researchguard.member-admission.sourceguard.v1",
    "member_id": "sourceguard",
    "applicability": "evidence discovery, retrieval, provenance, source-role gaps, or claim-use qualification",
    "forbidden_conditions": (
        "argument licensing, temporal/storyline reconstruction, or finite "
        "discriminating-experiment selection"
    ),
}


def contract_fingerprint() -> str:
    body = json.dumps(CONTRACT, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(body).hexdigest()}"


def author_admission_evidence(
    *,
    request_fingerprint: str,
    applicability: str,
    forbidden_status: str,
    applicability_evidence_refs: Sequence[str],
    forbidden_evidence_refs: Sequence[str],
    forbidden_condition_ids: Sequence[str] = (),
) -> Mapping[str, Any]:
    return {
        "schema_version": "researchguard.member-admission-evidence.v1",
        "member_id": "sourceguard",
        "authored_by": "sourceguard",
        "contract_id": CONTRACT["contract_id"],
        "contract_fingerprint": contract_fingerprint(),
        "request_fingerprint": request_fingerprint,
        "applicability": applicability,
        "applicability_evidence_refs": list(applicability_evidence_refs),
        "forbidden_status": forbidden_status,
        "forbidden_condition_ids": list(forbidden_condition_ids),
        "forbidden_evidence_refs": list(forbidden_evidence_refs),
    }


__all__ = ["CONTRACT", "author_admission_evidence", "contract_fingerprint"]
