"""Exact ResearchGuard member routing with no alternate-success path."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Literal, Sequence

from . import __version__
from .suite import suite_fingerprint


MemberID = Literal["logicguard", "sourceguard", "traceguard"]

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
}


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
                "Select exactly one member: logicguard, sourceguard, or "
                "traceguard."
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
    "MemberID",
    "RouteBinding",
    "TypedGap",
    "TypedHandoff",
    "bind_member_request",
    "create_handoff",
]
