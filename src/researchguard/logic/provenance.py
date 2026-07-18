"""Typed provenance and durable evidence-boundary validation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Iterable, Mapping


class ProvenanceError(ValueError):
    """Raised when provenance cannot support a durable declared role."""


class OriginKind(str, Enum):
    EXTERNAL_SOURCE = "external_source"
    OBSERVED_EVENT = "observed_event"
    USER_ATTESTATION = "user_attestation"
    TEST_RESULT = "test_result"
    HUMAN_OBSERVATION = "human_observation"
    INSTRUMENT_MEASUREMENT = "instrument_measurement"
    IMPORTED_RECORD = "imported_record"
    AI_GENERATED = "ai_generated"
    DERIVED = "derived"


EVIDENTIARY_ORIGINS = frozenset(
    {
        OriginKind.EXTERNAL_SOURCE,
        OriginKind.OBSERVED_EVENT,
        OriginKind.USER_ATTESTATION,
        OriginKind.TEST_RESULT,
        OriginKind.HUMAN_OBSERVATION,
        OriginKind.INSTRUMENT_MEASUREMENT,
        OriginKind.IMPORTED_RECORD,
    }
)

_SHA256_PATTERN = re.compile(r"^(?:sha256:)?([0-9a-fA-F]{64})$")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def normalize_content_hash(value: str) -> str:
    match = _SHA256_PATTERN.fullmatch(str(value).strip())
    if not match:
        raise ProvenanceError("content_hash must be a sha256 digest")
    return f"sha256:{match.group(1).lower()}"


def content_hash_for(value: bytes | str) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _validate_temporal_clue(value: str | None, field_name: str) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    try:
        if "T" in text or text.endswith("Z"):
            datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            date.fromisoformat(text)
    except ValueError as exc:
        raise ProvenanceError(f"{field_name} must be an ISO-8601 date or datetime") from exc
    return text


@dataclass(frozen=True)
class ProvenanceRecord:
    """One content-addressed declaration of where modeled material came from."""

    origin_kind: OriginKind | str
    content_hash: str
    source_id: str | None = None
    source_reference: str | None = None
    observed_at: str | None = None
    source_date: str | None = None
    actor: str = ""
    independence_group: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            origin = OriginKind(self.origin_kind)
        except ValueError as exc:
            raise ProvenanceError(f"unsupported origin_kind: {self.origin_kind!r}") from exc
        object.__setattr__(self, "origin_kind", origin)
        object.__setattr__(self, "content_hash", normalize_content_hash(self.content_hash))
        source_id = str(self.source_id).strip() if self.source_id not in (None, "") else None
        source_reference = (
            str(self.source_reference).strip()
            if self.source_reference not in (None, "")
            else None
        )
        if not source_id and not source_reference:
            raise ProvenanceError("provenance requires source_id or source_reference")
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "source_reference", source_reference)
        object.__setattr__(
            self, "observed_at", _validate_temporal_clue(self.observed_at, "observed_at")
        )
        object.__setattr__(
            self, "source_date", _validate_temporal_clue(self.source_date, "source_date")
        )
        metadata = _freeze(dict(self.metadata or {}))
        object.__setattr__(self, "metadata", metadata)
        group = str(self.independence_group).strip() if self.independence_group else None
        if not group:
            group = default_independence_group(
                source_id=source_id,
                source_reference=source_reference,
                content_hash=self.content_hash,
            )
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,191}", group):
            raise ProvenanceError("independence_group is not a portable identity")
        object.__setattr__(self, "independence_group", group)

    @property
    def is_evidentiary(self) -> bool:
        return self.origin_kind in EVIDENTIARY_ORIGINS

    @property
    def normalized_source_identity(self) -> str:
        return self.source_id or self.source_reference or ""

    @property
    def reviewed_separation(self) -> bool:
        return bool(self.metadata.get("reviewed_separation")) and bool(
            self.metadata.get("separation_receipt_id")
        )

    def source_content_key(self) -> tuple[str, str]:
        return (self.normalized_source_identity, self.content_hash)

    def to_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "origin_kind": self.origin_kind.value,
                "source_id": self.source_id,
                "source_reference": self.source_reference,
                "content_hash": self.content_hash,
                "observed_at": self.observed_at,
                "source_date": self.source_date,
                "actor": self.actor,
                "independence_group": self.independence_group,
                "metadata": _thaw(self.metadata),
            }.items()
            if value not in (None, "", {})
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ProvenanceRecord":
        return cls(
            origin_kind=str(raw.get("origin_kind", "")),
            source_id=raw.get("source_id"),
            source_reference=raw.get("source_reference"),
            content_hash=str(raw.get("content_hash", "")),
            observed_at=raw.get("observed_at"),
            source_date=raw.get("source_date"),
            actor=str(raw.get("actor", "")),
            independence_group=raw.get("independence_group"),
            metadata=dict(raw.get("metadata") or {}),
        )


def default_independence_group(
    *, source_id: str | None, source_reference: str | None, content_hash: str
) -> str:
    identity = source_id or source_reference or ""
    payload = json.dumps(
        [identity, normalize_content_hash(content_hash)],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"ind-{hashlib.sha256(payload).hexdigest()}"


def coerce_provenance(records: Iterable[ProvenanceRecord | Mapping[str, Any]]) -> tuple[ProvenanceRecord, ...]:
    normalized: list[ProvenanceRecord] = []
    for record in records:
        if isinstance(record, ProvenanceRecord):
            normalized.append(record)
        elif isinstance(record, Mapping):
            normalized.append(ProvenanceRecord.from_dict(record))
        else:
            raise ProvenanceError(f"provenance record must be a mapping, got {type(record).__name__}")
    return tuple(normalized)


def validate_evidence_provenance(
    node_id: str,
    records: Iterable[ProvenanceRecord | Mapping[str, Any]],
) -> tuple[ProvenanceRecord, ...]:
    normalized = coerce_provenance(records)
    if not any(record.is_evidentiary for record in normalized):
        raise ProvenanceError(
            f"Evidence node {node_id!r} requires at least one non-ai_generated evidentiary provenance record"
        )
    return normalized


def normalize_duplicate_independence(
    records: Iterable[ProvenanceRecord | Mapping[str, Any]],
) -> tuple[ProvenanceRecord, ...]:
    """Make exact duplicate source/content records share one independence group.

    Explicit reviewed separation remains distinct only when it names a review
    receipt.  No external truth or actual independence is inferred here.
    """

    normalized = list(coerce_provenance(records))
    canonical_groups: dict[tuple[str, str], str] = {}
    output: list[ProvenanceRecord] = []
    for record in normalized:
        key = record.source_content_key()
        canonical = canonical_groups.setdefault(key, record.independence_group or "")
        if record.independence_group != canonical and not record.reviewed_separation:
            record = replace(record, independence_group=canonical)
        output.append(record)
    return tuple(output)


__all__ = [
    "EVIDENTIARY_ORIGINS",
    "OriginKind",
    "ProvenanceError",
    "ProvenanceRecord",
    "coerce_provenance",
    "content_hash_for",
    "default_independence_group",
    "normalize_content_hash",
    "normalize_duplicate_independence",
    "validate_evidence_provenance",
]
