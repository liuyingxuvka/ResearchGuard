"""Source-bound task facts and member-owned admission derivation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from typing import Any, Literal, Mapping, Sequence

from .target_authority import (
    ExpectedTargetAnchor,
    _expected_target_receipt_payload,
    _expected_target_result_material,
    _publish_expected_target_admission,
    _verify_expected_target_producer_signature,
    content_addressed_request_id,
    read_target_material_bytes,
)


TASK_FACTS_SCHEMA = "researchguard.task-facts.v1"
ADMISSION_SCHEMA = "researchguard.member-admission-evidence.v2"
ADMISSION_SET_SCHEMA = "researchguard.member-admission-set.v2"
CONTRACT_SCHEMA = "researchguard.member-admission-contract.v2"
COMPOSITION_SCHEMA = "researchguard.member-composition.v2"
FACT_ROLES = {"primary_action", "context"}
FORBIDDEN_DISPOSITIONS = {"absent", "present", "unknown"}
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_PLACEHOLDER_QUOTES = {"placeholder", "todo", "tbd", "n/a", "unknown", "evidence"}
EXPECTED_TARGET_ADMISSION_OWNER = "researchguard"
EXPECTED_TARGET_ADMISSION_PRODUCER = "researchguard.admission.expected-target-anchor"
EXPECTED_TARGET_ADMISSION_PRODUCER_VERSION = "1"


def _exact_keys(raw: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(raw).difference(allowed)
    if unknown:
        raise ValueError(f"{label} contains unknown fields: {', '.join(sorted(unknown))}")


def _unique_strings(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    rows = tuple(str(item).strip() for item in value)
    if any(not item for item in rows) or len(set(rows)) != len(rows):
        raise ValueError(f"{label} must contain unique non-empty strings")
    return rows


@dataclass(frozen=True)
class SourceSpan:
    source_id: str
    start: int
    end: int
    quote: str

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], *, label: str) -> "SourceSpan":
        _exact_keys(raw, {"source_id", "start", "end", "quote"}, label)
        source_id = str(raw.get("source_id", "")).strip()
        quote = str(raw.get("quote", ""))
        start = raw.get("start")
        end = raw.get("end")
        if not source_id or source_id.lower() in {"placeholder", "unknown", "tbd"}:
            raise ValueError(f"{label}.source_id must identify the actual request source")
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
            raise ValueError(f"{label} requires valid integer start/end offsets")
        if len(quote) != end - start or not quote.strip():
            raise ValueError(f"{label}.quote must exactly match the declared span length")
        if quote.strip().lower() in _PLACEHOLDER_QUOTES:
            raise ValueError(f"{label}.quote cannot be placeholder evidence")
        return cls(source_id=source_id, start=start, end=end, quote=quote)


@dataclass(frozen=True)
class TaskFact:
    fact_id: str
    kind: str
    role: Literal["primary_action", "context"]
    statement: str
    source_span: SourceSpan

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], *, index: int) -> "TaskFact":
        label = f"facts[{index}]"
        _exact_keys(raw, {"fact_id", "kind", "role", "statement", "source_span"}, label)
        fact_id = str(raw.get("fact_id", "")).strip()
        kind = str(raw.get("kind", "")).strip()
        role = str(raw.get("role", "")).strip()
        statement = str(raw.get("statement", "")).strip()
        if not fact_id or not kind or not statement:
            raise ValueError(f"{label} requires fact_id, kind, and statement")
        if role not in FACT_ROLES:
            raise ValueError(f"{label}.role must be primary_action or context")
        span_raw = raw.get("source_span")
        if not isinstance(span_raw, Mapping):
            raise ValueError(f"{label}.source_span must be an object")
        return cls(
            fact_id=fact_id,
            kind=kind,
            role=role,  # type: ignore[arg-type]
            statement=statement,
            source_span=SourceSpan.from_dict(span_raw, label=f"{label}.source_span"),
        )


@dataclass(frozen=True)
class ForbiddenReview:
    member_id: str
    condition_id: str
    disposition: Literal["absent", "present", "unknown"]
    source_span: SourceSpan

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], *, index: int) -> "ForbiddenReview":
        label = f"forbidden_reviews[{index}]"
        _exact_keys(raw, {"member_id", "condition_id", "disposition", "source_span"}, label)
        member_id = str(raw.get("member_id", "")).strip()
        condition_id = str(raw.get("condition_id", "")).strip()
        disposition = str(raw.get("disposition", "")).strip()
        if not member_id or not condition_id:
            raise ValueError(f"{label} requires member_id and condition_id")
        if disposition not in FORBIDDEN_DISPOSITIONS:
            raise ValueError(f"{label}.disposition is invalid")
        span_raw = raw.get("source_span")
        if not isinstance(span_raw, Mapping):
            raise ValueError(f"{label}.source_span must be an object")
        return cls(
            member_id=member_id,
            condition_id=condition_id,
            disposition=disposition,  # type: ignore[arg-type]
            source_span=SourceSpan.from_dict(span_raw, label=f"{label}.source_span"),
        )


@dataclass(frozen=True)
class TaskFactPacket:
    request_fingerprint: str
    facts: tuple[TaskFact, ...]
    forbidden_reviews: tuple[ForbiddenReview, ...]
    composition: Mapping[str, Any] | None = None
    schema_version: str = TASK_FACTS_SCHEMA

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "TaskFactPacket":
        _exact_keys(
            raw,
            {
                "schema_version",
                "request_fingerprint",
                "facts",
                "forbidden_reviews",
                "composition",
            },
            "task facts",
        )
        if raw.get("schema_version") != TASK_FACTS_SCHEMA:
            raise ValueError("task facts require the current schema")
        request_digest = str(raw.get("request_fingerprint", ""))
        if not _SHA256_RE.fullmatch(request_digest):
            raise ValueError("task facts require one lowercase sha256 request fingerprint")
        facts_raw = raw.get("facts")
        reviews_raw = raw.get("forbidden_reviews")
        if not isinstance(facts_raw, list) or not isinstance(reviews_raw, list):
            raise ValueError("facts and forbidden_reviews must be arrays")
        facts = tuple(TaskFact.from_dict(row, index=index) for index, row in enumerate(facts_raw) if isinstance(row, Mapping))
        if len(facts) != len(facts_raw) or not facts:
            raise ValueError("facts must contain only task-fact objects and cannot be empty")
        if len({row.fact_id for row in facts}) != len(facts):
            raise ValueError("task fact ids must be unique")
        primary = tuple(row for row in facts if row.role == "primary_action")
        if not primary:
            raise ValueError("task facts require at least one primary_action fact")
        reviews = tuple(
            ForbiddenReview.from_dict(row, index=index)
            for index, row in enumerate(reviews_raw)
            if isinstance(row, Mapping)
        )
        if len(reviews) != len(reviews_raw):
            raise ValueError("forbidden_reviews must contain only review objects")
        keys = {(row.member_id, row.condition_id) for row in reviews}
        if len(keys) != len(reviews):
            raise ValueError("forbidden review member/condition pairs must be unique")
        composition_raw = raw.get("composition")
        if composition_raw is not None and not isinstance(composition_raw, Mapping):
            raise ValueError("task facts composition must be an object when present")
        return cls(
            request_fingerprint=request_digest,
            facts=facts,
            forbidden_reviews=reviews,
            composition=dict(composition_raw) if composition_raw is not None else None,
        )

    def fingerprint(self) -> str:
        body = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return f"sha256:{hashlib.sha256(body).hexdigest()}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_fingerprint": self.request_fingerprint,
            "facts": [
                {
                    "fact_id": row.fact_id,
                    "kind": row.kind,
                    "role": row.role,
                    "statement": row.statement,
                    "source_span": asdict(row.source_span),
                }
                for row in self.facts
            ],
            "forbidden_reviews": [
                {
                    "member_id": row.member_id,
                    "condition_id": row.condition_id,
                    "disposition": row.disposition,
                    "source_span": asdict(row.source_span),
                }
                for row in self.forbidden_reviews
            ],
            **(
                {"composition": dict(self.composition)}
                if self.composition is not None
                else {}
            ),
        }


def _digest(value: object) -> str:
    body = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _admit_expected_target_anchor(
    packet: TaskFactPacket,
    *,
    task_id: str,
    member_id: str,
    target_request_id: str,
    target_request_fingerprint: str,
    target_id: str,
    target_revision: str,
    material_locator: str,
    material_media_type: str = "application/json",
    material_fingerprint: str = "",
    admission_owner_id: str = EXPECTED_TARGET_ADMISSION_OWNER,
    admission_producer_id: str = EXPECTED_TARGET_ADMISSION_PRODUCER,
    admission_producer_version: str = EXPECTED_TARGET_ADMISSION_PRODUCER_VERSION,
    admission_key_id: str,
    admission_signature: str,
) -> ExpectedTargetAnchor:
    """Freeze one provider-neutral target before any member models it.

    This is the sole current admission producer.  It binds source-backed task
    facts and exact raw target bytes but deliberately does not interpret member
    semantics.  Unavailable external bytes may be named by an exact supplied
    fingerprint; their later replay remains visibly unverified.
    """

    task = str(task_id or "").strip()
    member = str(member_id or "").strip()
    target = str(target_id or "").strip()
    locator = str(material_locator or "").strip()
    media_type = str(material_media_type or "").strip()
    request_fingerprint = str(target_request_fingerprint or "").strip()
    revision = str(target_revision or "").strip()
    if not all((task, member, target, locator, media_type)):
        raise ValueError("expected target admission requires task, member, target, and locator")
    if not _SHA256_RE.fullmatch(request_fingerprint):
        raise ValueError("expected target admission request fingerprint must be exact")
    if target_request_id != content_addressed_request_id(request_fingerprint):
        raise ValueError("expected target admission request id is not content-addressed")
    if not _SHA256_RE.fullmatch(revision):
        raise ValueError("expected target admission revision must be exact")
    body, replayed_fingerprint, _ = read_target_material_bytes(locator)
    supplied_fingerprint = str(material_fingerprint or "").strip()
    if body is not None:
        if supplied_fingerprint and supplied_fingerprint != replayed_fingerprint:
            raise ValueError("expected target admission raw material fingerprint mismatches bytes")
        exact_material_fingerprint = replayed_fingerprint
    else:
        if not _SHA256_RE.fullmatch(supplied_fingerprint):
            raise ValueError(
                "unavailable expected target material requires an exact supplied fingerprint"
            )
        exact_material_fingerprint = supplied_fingerprint
    result_material = _expected_target_result_material(
        member_id=member,
        task_id=task,
        task_request_fingerprint=packet.request_fingerprint,
        target_request_id=target_request_id,
        target_request_fingerprint=request_fingerprint,
        target_id=target,
        target_revision=revision,
        material_locator=locator,
        material_media_type=media_type,
        material_fingerprint=exact_material_fingerprint,
        admission_owner_id=str(admission_owner_id or "").strip(),
        admission_producer_id=str(admission_producer_id or "").strip(),
        admission_producer_version=str(admission_producer_version or "").strip(),
    )
    admission_result_fingerprint = _digest(result_material)
    anchor_id = (
        "expected-target-anchor:"
        + admission_result_fingerprint.removeprefix("sha256:")
    )
    admission_input_fingerprint = _digest(
        {
            "task_facts_fingerprint": packet.fingerprint(),
            "result_material": result_material,
        }
    )
    producer = (
        str(admission_owner_id or "").strip(),
        str(admission_producer_id or "").strip(),
        str(admission_producer_version or "").strip(),
    )
    if not _verify_expected_target_producer_signature(
        producer=producer,
        anchor_id=anchor_id,
        result_material=result_material,
        admission_input_fingerprint=admission_input_fingerprint,
        admission_result_fingerprint=admission_result_fingerprint,
        admission_key_id=str(admission_key_id or "").strip(),
        admission_signature=str(admission_signature or "").strip(),
    ):
        raise ValueError("expected target admission producer signature is invalid")
    receipt_payload = _expected_target_receipt_payload(
        anchor_id=anchor_id,
        result_material=result_material,
        admission_input_fingerprint=admission_input_fingerprint,
        admission_result_fingerprint=admission_result_fingerprint,
        admission_key_id=str(admission_key_id).strip(),
        admission_signature=str(admission_signature).strip(),
    )
    receipt_locator, receipt_fingerprint, receipt_id = (
        _publish_expected_target_admission(
            receipt_payload=receipt_payload,
            result_material=result_material,
        )
    )
    value = ExpectedTargetAnchor(
        anchor_id=anchor_id,
        member_id=member,
        task_id=task,
        task_request_fingerprint=packet.request_fingerprint,
        target_request_id=target_request_id,
        target_request_fingerprint=request_fingerprint,
        target_id=target,
        target_revision=revision,
        material_locator=locator,
        material_media_type=media_type,
        material_fingerprint=exact_material_fingerprint,
        admission_owner_id=str(admission_owner_id or "").strip(),
        admission_producer_id=str(admission_producer_id or "").strip(),
        admission_producer_version=str(admission_producer_version or "").strip(),
        admission_input_fingerprint=admission_input_fingerprint,
        admission_result_fingerprint=admission_result_fingerprint,
        admission_key_id=str(admission_key_id).strip(),
        admission_signature=str(admission_signature).strip(),
        receipt_id=receipt_id,
        receipt_locator=receipt_locator,
        receipt_fingerprint=receipt_fingerprint,
    )
    return replace(value, anchor_fingerprint=value.expected_fingerprint)


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("schema_version") != CONTRACT_SCHEMA:
        raise ValueError("member admission contract requires the current schema")
    for field in ("contract_id", "member_id"):
        if not str(contract.get(field, "")).strip():
            raise ValueError(f"member admission contract requires {field}")
    positive = contract.get("positive_conditions")
    required = contract.get("required_conditions")
    forbidden = contract.get("forbidden_conditions")
    if not isinstance(positive, list) or not positive:
        raise ValueError("member admission contract needs positive conditions")
    if not isinstance(required, list) or not isinstance(forbidden, list) or not forbidden:
        raise ValueError("member admission contract needs required and forbidden condition arrays")
    ids: list[str] = []
    for group_name, rows in (("positive", positive), ("required", required), ("forbidden", forbidden)):
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                raise ValueError(f"{group_name} condition {index} must be an object")
            condition_id = str(row.get("condition_id", "")).strip()
            kinds = row.get("any_fact_kinds")
            if not condition_id or not isinstance(kinds, list) or not kinds:
                raise ValueError(f"{group_name} condition {index} is incomplete")
            if any(not str(kind).strip() for kind in kinds):
                raise ValueError(f"{condition_id} contains an empty fact kind")
            ids.append(condition_id)
            if group_name == "positive":
                if not str(row.get("first_action", "")).strip() or not str(row.get("first_reference", "")).strip():
                    raise ValueError(f"{condition_id} requires first_action and first_reference")
    if len(ids) != len(set(ids)):
        raise ValueError("member admission condition ids must be unique")


def contract_fact_kinds(contract: Mapping[str, Any]) -> set[str]:
    validate_contract(contract)
    return {
        str(kind)
        for field in ("positive_conditions", "required_conditions", "forbidden_conditions")
        for row in contract[field]
        for kind in row["any_fact_kinds"]
    }


def expected_forbidden_review_keys(contracts: Sequence[Mapping[str, Any]]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for contract in contracts:
        validate_contract(contract)
        member_id = str(contract["member_id"])
        keys.update((member_id, str(row["condition_id"])) for row in contract["forbidden_conditions"])
    return keys


def derive_member_admission_evidence(
    contract: Mapping[str, Any],
    packet: TaskFactPacket,
) -> dict[str, Any]:
    validate_contract(contract)
    member_id = str(contract["member_id"])
    primary = tuple(row for row in packet.facts if row.role == "primary_action")
    primary_kinds = {row.kind for row in primary}
    all_kinds = {row.kind for row in packet.facts}

    matched_positive = [
        row
        for row in contract["positive_conditions"]
        if primary_kinds.intersection(str(kind) for kind in row["any_fact_kinds"])
    ]
    matched_positive_ids = tuple(str(row["condition_id"]) for row in matched_positive)
    matching_fact_ids = tuple(
        row.fact_id
        for row in primary
        if any(row.kind in condition["any_fact_kinds"] for condition in matched_positive)
    )

    missing_required: tuple[str, ...] = ()
    if matched_positive:
        missing_required = tuple(
            str(row["condition_id"])
            for row in contract["required_conditions"]
            if not all_kinds.intersection(str(kind) for kind in row["any_fact_kinds"])
        )

    review_map = {
        (row.member_id, row.condition_id): row for row in packet.forbidden_reviews
    }
    forbidden_rows: list[dict[str, Any]] = []
    for condition in contract["forbidden_conditions"]:
        condition_id = str(condition["condition_id"])
        matched_fact_ids = tuple(
            row.fact_id
            for row in packet.facts
            if row.kind in condition["any_fact_kinds"]
        )
        review = review_map.get((member_id, condition_id))
        if review is None:
            raise ValueError(f"{member_id} missing forbidden review for {condition_id}")
        derived = "present" if matched_fact_ids else review.disposition
        if matched_fact_ids and review.disposition != "present":
            raise ValueError(f"{member_id} forbidden review contradicts task facts for {condition_id}")
        if not matched_fact_ids and review.disposition == "present":
            raise ValueError(f"{member_id} forbidden present review lacks a matching task fact for {condition_id}")
        forbidden_rows.append(
            {
                "condition_id": condition_id,
                "disposition": derived,
                "evidence_fact_ids": list(matched_fact_ids),
                "review_source_span": asdict(review.source_span),
            }
        )

    dispositions = {row["disposition"] for row in forbidden_rows}
    forbidden_status = (
        "present" if "present" in dispositions else "unknown" if "unknown" in dispositions else "clear"
    )
    if not matched_positive:
        applicability = "not_applicable"
    elif missing_required or forbidden_status != "clear":
        applicability = "blocked"
    else:
        applicability = "applicable"
    selected = matched_positive[0] if matched_positive else None
    return {
        "schema_version": ADMISSION_SCHEMA,
        "member_id": member_id,
        "authored_by": member_id,
        "contract_id": contract["contract_id"],
        "contract_fingerprint": contract_fingerprint(contract),
        "request_fingerprint": packet.request_fingerprint,
        "task_facts_fingerprint": packet.fingerprint(),
        "applicability": applicability,
        "matched_positive_condition_ids": list(matched_positive_ids),
        "matching_task_fact_ids": list(matching_fact_ids),
        "missing_required_condition_ids": list(missing_required),
        "forbidden_status": forbidden_status,
        "forbidden_dispositions": forbidden_rows,
        "first_action": str(selected["first_action"]) if selected else "",
        "first_reference": str(selected["first_reference"]) if selected else "",
    }


def contract_fingerprint(contract: Mapping[str, Any]) -> str:
    validate_contract(contract)
    body = json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return f"sha256:{hashlib.sha256(body).hexdigest()}"


__all__ = [
    "ADMISSION_SCHEMA",
    "ADMISSION_SET_SCHEMA",
    "CONTRACT_SCHEMA",
    "COMPOSITION_SCHEMA",
    "TASK_FACTS_SCHEMA",
    "TaskFactPacket",
    "EXPECTED_TARGET_ADMISSION_OWNER",
    "EXPECTED_TARGET_ADMISSION_PRODUCER",
    "EXPECTED_TARGET_ADMISSION_PRODUCER_VERSION",
    "contract_fact_kinds",
    "contract_fingerprint",
    "derive_member_admission_evidence",
    "expected_forbidden_review_keys",
    "validate_contract",
]
