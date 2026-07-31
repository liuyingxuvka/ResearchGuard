"""Exact ResearchGuard member routing with no alternate-success path."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping, Sequence

from . import __version__
from .suite import suite_fingerprint
from .experiment.admission import CONTRACT as EXPERIMENT_ADMISSION_CONTRACT
from .experiment.admission import contract_fingerprint as experiment_admission_fingerprint
from .logic.admission import CONTRACT as LOGIC_ADMISSION_CONTRACT
from .logic.admission import contract_fingerprint as logic_admission_fingerprint
from .source.admission import CONTRACT as SOURCE_ADMISSION_CONTRACT
from .source.admission import contract_fingerprint as source_admission_fingerprint
from .trace.admission import CONTRACT as TRACE_ADMISSION_CONTRACT
from .trace.admission import contract_fingerprint as trace_admission_fingerprint


MemberID = Literal[
    "logicguard",
    "sourceguard",
    "traceguard",
    "experimentguard",
]

MEMBER_BINDINGS: dict[MemberID, tuple[str, str, str]] = {
    "logicguard": (
        "logicguard",
        "primary:researchguard:logic",
        "researchguard.logic.cli:main",
    ),
    "sourceguard": (
        "sourceguard",
        "primary:researchguard:source",
        "researchguard.source.cli:main",
    ),
    "traceguard": (
        "traceguard",
        "primary:researchguard:trace",
        "researchguard.trace.cli:main",
    ),
    "experimentguard": (
        "experimentguard",
        "primary:researchguard:experiment",
        "researchguard.experiment.cli:main",
    ),
}

MEMBER_ADMISSION_AUTHORITIES: dict[MemberID, tuple[str, str]] = {
    "logicguard": (
        str(LOGIC_ADMISSION_CONTRACT["contract_id"]),
        logic_admission_fingerprint(),
    ),
    "sourceguard": (
        str(SOURCE_ADMISSION_CONTRACT["contract_id"]),
        source_admission_fingerprint(),
    ),
    "traceguard": (
        str(TRACE_ADMISSION_CONTRACT["contract_id"]),
        trace_admission_fingerprint(),
    ),
    "experimentguard": (
        str(EXPERIMENT_ADMISSION_CONTRACT["contract_id"]),
        experiment_admission_fingerprint(),
    ),
}

ADMISSION_SCHEMA = "researchguard.member-admission-evidence.v1"
ADMISSION_SET_SCHEMA = "researchguard.member-admission-set.v1"
VALID_APPLICABILITY = {"applicable", "not_applicable", "blocked"}
VALID_FORBIDDEN = {"clear", "present", "unknown"}


def request_fingerprint(argv: Sequence[str], *, business_intent_id: str) -> str:
    material = json.dumps(
        {
            "argv": _normalized_args(argv),
            "business_intent_id": business_intent_id,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(material).hexdigest()}"


def _string_ids(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    rows = tuple(str(item).strip() for item in value)
    if any(not item for item in rows) or len(set(rows)) != len(rows):
        raise ValueError(f"{field} must contain unique non-empty strings")
    return rows


@dataclass(frozen=True)
class MemberAdmissionEvidence:
    member_id: MemberID
    request_fingerprint: str
    applicability: Literal["applicable", "not_applicable", "blocked"]
    forbidden_status: Literal["clear", "present", "unknown"]
    applicability_evidence_refs: tuple[str, ...]
    forbidden_evidence_refs: tuple[str, ...]
    forbidden_condition_ids: tuple[str, ...]
    contract_id: str
    contract_fingerprint: str
    authored_by: str
    schema_version: str = ADMISSION_SCHEMA

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MemberAdmissionEvidence":
        if raw.get("schema_version", ADMISSION_SCHEMA) != ADMISSION_SCHEMA:
            raise ValueError("member admission evidence requires the current schema")
        member_id = str(raw.get("member_id", ""))
        if member_id not in MEMBER_BINDINGS:
            raise ValueError(f"unknown admission member: {member_id}")
        applicability = str(raw.get("applicability", ""))
        forbidden = str(raw.get("forbidden_status", ""))
        if applicability not in VALID_APPLICABILITY:
            raise ValueError(f"invalid applicability for {member_id}")
        if forbidden not in VALID_FORBIDDEN:
            raise ValueError(f"invalid forbidden_status for {member_id}")
        expected_contract_id, expected_contract_fingerprint = (
            MEMBER_ADMISSION_AUTHORITIES[member_id]  # type: ignore[index]
        )
        authored_by = str(raw.get("authored_by", ""))
        contract_id = str(raw.get("contract_id", ""))
        contract_fingerprint = str(raw.get("contract_fingerprint", ""))
        if authored_by != member_id:
            raise ValueError(f"{member_id} admission evidence must be member-authored")
        if (contract_id, contract_fingerprint) != (
            expected_contract_id,
            expected_contract_fingerprint,
        ):
            raise ValueError(f"{member_id} admission contract is stale or foreign")
        request_digest = str(raw.get("request_fingerprint", ""))
        if not request_digest.startswith("sha256:"):
            raise ValueError(f"{member_id} admission request fingerprint is required")
        applicability_refs = _string_ids(
            raw.get("applicability_evidence_refs"),
            f"{member_id}.applicability_evidence_refs",
        )
        forbidden_refs = _string_ids(
            raw.get("forbidden_evidence_refs"),
            f"{member_id}.forbidden_evidence_refs",
        )
        forbidden_ids = _string_ids(
            raw.get("forbidden_condition_ids", []),
            f"{member_id}.forbidden_condition_ids",
        )
        if not applicability_refs or not forbidden_refs:
            raise ValueError(f"{member_id} admission evidence refs must not be empty")
        if forbidden == "present" and not forbidden_ids:
            raise ValueError(f"{member_id} present forbidden status requires condition ids")
        return cls(
            member_id=member_id,  # type: ignore[arg-type]
            request_fingerprint=request_digest,
            applicability=applicability,  # type: ignore[arg-type]
            forbidden_status=forbidden,  # type: ignore[arg-type]
            applicability_evidence_refs=applicability_refs,
            forbidden_evidence_refs=forbidden_refs,
            forbidden_condition_ids=forbidden_ids,
            contract_id=contract_id,
            contract_fingerprint=contract_fingerprint,
            authored_by=authored_by,
        )

    @property
    def admitted(self) -> bool:
        return self.applicability == "applicable" and self.forbidden_status == "clear"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TypedGap:
    status: Literal["blocked"]
    code: str
    message: str
    allowed_members: tuple[MemberID, ...] = tuple(MEMBER_BINDINGS)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RouteBinding:
    status: Literal["routed"]
    request_id: str
    business_intent_id: str
    member_id: MemberID
    native_owner_id: str
    primary_path_id: str
    machine_path: str
    suite_version: str
    suite_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TypedHandoff:
    status: Literal["awaiting_owner"]
    source_request_id: str
    source_member_id: MemberID
    target_member_id: MemberID
    handoff_kind: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalized_args(argv: Sequence[str]) -> tuple[str, ...]:
    return tuple(str(item) for item in argv)


def _derived_business_intent(member_id: MemberID, argv: Sequence[str]) -> str:
    encoded = json.dumps(
        {"member_id": member_id, "argv": _normalized_args(argv)},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"intent:researchguard:{hashlib.sha256(encoded).hexdigest()[:24]}"


def bind_member_request(
    member_id: str | None,
    argv: Sequence[str],
    *,
    business_intent_id: str | None = None,
    active_request_id: str | None = None,
) -> RouteBinding | TypedGap:
    """Bind one explicit member or block before any member executes."""

    if active_request_id:
        return TypedGap(
            status="blocked",
            code="researchguard-recursion",
            message=(
                "An already-routed request cannot re-enter the ResearchGuard "
                "umbrella."
            ),
        )
    if member_id is None:
        return TypedGap(
            status="blocked",
            code="member-selection-required",
            message=(
                "Select exactly one member: logicguard, sourceguard, "
                "traceguard, or experimentguard."
            ),
        )
    if member_id not in MEMBER_BINDINGS:
        return TypedGap(
            status="blocked",
            code="unknown-member",
            message=f"Unknown ResearchGuard member: {member_id}",
        )

    typed_member: MemberID = member_id
    native_owner_id, primary_path_id, machine_path = MEMBER_BINDINGS[typed_member]
    normalized_args = _normalized_args(argv)
    normalized_intent = business_intent_id or _derived_business_intent(
        typed_member,
        normalized_args,
    )
    fingerprint = suite_fingerprint()
    request_material = json.dumps(
        {
            "business_intent_id": normalized_intent,
            "member_id": typed_member,
            "argv": normalized_args,
            "suite_version": __version__,
            "suite_fingerprint": fingerprint,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    request_id = f"request:{hashlib.sha256(request_material).hexdigest()}"
    return RouteBinding(
        status="routed",
        request_id=request_id,
        business_intent_id=normalized_intent,
        member_id=typed_member,
        native_owner_id=native_owner_id,
        primary_path_id=primary_path_id,
        machine_path=machine_path,
        suite_version=__version__,
        suite_fingerprint=fingerprint,
    )


def select_member_request(
    admission_set: Mapping[str, Any],
    argv: Sequence[str],
    *,
    business_intent_id: str,
    active_request_id: str | None = None,
) -> RouteBinding | TypedGap:
    """Reconcile all four member-authored rows without lexical fallback."""

    if admission_set.get("schema_version") != ADMISSION_SET_SCHEMA:
        return TypedGap(
            status="blocked",
            code="admission-schema-invalid",
            message="The umbrella requires one current member-admission set.",
        )
    raw_rows = admission_set.get("member_evidence")
    if not isinstance(raw_rows, list):
        return TypedGap(
            status="blocked",
            code="admission-inventory-invalid",
            message="member_evidence must contain the exact four-member inventory.",
        )
    try:
        rows = tuple(MemberAdmissionEvidence.from_dict(row) for row in raw_rows)
    except (TypeError, ValueError) as exc:
        return TypedGap(
            status="blocked",
            code="admission-evidence-invalid",
            message=str(exc),
        )
    if len(rows) != len(MEMBER_BINDINGS) or {row.member_id for row in rows} != set(
        MEMBER_BINDINGS
    ):
        return TypedGap(
            status="blocked",
            code="admission-inventory-invalid",
            message="Admission evidence must contain each current member exactly once.",
        )
    expected_request = request_fingerprint(
        argv,
        business_intent_id=business_intent_id,
    )
    if any(row.request_fingerprint != expected_request for row in rows):
        return TypedGap(
            status="blocked",
            code="admission-request-stale",
            message="Every member admission row must bind the exact current request.",
        )
    admitted = tuple(row.member_id for row in rows if row.admitted)
    if len(admitted) != 1:
        return TypedGap(
            status="blocked",
            code=(
                "member-admission-no-match"
                if not admitted
                else "member-admission-ambiguous"
            ),
            message=(
                "Member-authored applicability and forbidden evidence did not "
                "admit exactly one member; no lexical or list-order fallback is allowed."
            ),
        )
    return bind_member_request(
        admitted[0],
        argv,
        business_intent_id=business_intent_id,
        active_request_id=active_request_id,
    )


def create_handoff(
    binding: RouteBinding,
    *,
    target_member_id: MemberID,
    handoff_kind: str,
    payload: dict[str, Any],
) -> TypedHandoff:
    """Create a handoff request without executing the target member."""

    if target_member_id == binding.member_id:
        raise ValueError("a member cannot hand off to itself")
    return TypedHandoff(
        status="awaiting_owner",
        source_request_id=binding.request_id,
        source_member_id=binding.member_id,
        target_member_id=target_member_id,
        handoff_kind=handoff_kind,
        payload=dict(payload),
    )


__all__ = [
    "MEMBER_BINDINGS",
    "MEMBER_ADMISSION_AUTHORITIES",
    "ADMISSION_SCHEMA",
    "ADMISSION_SET_SCHEMA",
    "MemberID",
    "MemberAdmissionEvidence",
    "RouteBinding",
    "TypedGap",
    "TypedHandoff",
    "bind_member_request",
    "create_handoff",
    "request_fingerprint",
    "select_member_request",
]
