"""ExperimentGuard-owned admission contract for the ResearchGuard umbrella."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence


CONTRACT = {
    "contract_id": "researchguard.member-admission.experimentguard.v1",
    "member_id": "experimentguard",
    "applicability": "minimum finite observation or intervention set selection across explicit competing hypotheses",
    "forbidden_conditions": (
        "experiment execution, source discovery, trace reconstruction, logical "
        "support, physical diagnosis, or software-test selection"
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
        "member_id": "experimentguard",
        "authored_by": "experimentguard",
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
