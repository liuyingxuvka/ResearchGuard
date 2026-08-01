"""Minimum-sufficient ResearchGuard routing with no alternate-success path."""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping, Sequence

from . import __version__
from .admission import (
    ADMISSION_SCHEMA,
    ADMISSION_SET_SCHEMA,
    COMPOSITION_SCHEMA,
    TASK_FACTS_SCHEMA,
    TaskFactPacket,
    contract_fact_kinds,
    expected_forbidden_review_keys,
)
from .suite import suite_fingerprint
from .experiment.admission import CONTRACT as EXPERIMENT_ADMISSION_CONTRACT
from .experiment.admission import author_admission_evidence as experiment_admission_evidence
from .experiment.admission import contract_fingerprint as experiment_admission_fingerprint
from .logic.admission import CONTRACT as LOGIC_ADMISSION_CONTRACT
from .logic.admission import author_admission_evidence as logic_admission_evidence
from .logic.admission import contract_fingerprint as logic_admission_fingerprint
from .source.admission import CONTRACT as SOURCE_ADMISSION_CONTRACT
from .source.admission import author_admission_evidence as source_admission_evidence
from .source.admission import contract_fingerprint as source_admission_fingerprint
from .trace.admission import CONTRACT as TRACE_ADMISSION_CONTRACT
from .trace.admission import author_admission_evidence as trace_admission_evidence
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

VALID_APPLICABILITY = {"applicable", "not_applicable", "blocked"}
VALID_FORBIDDEN = {"clear", "present", "unknown"}

MEMBER_ADMISSION_CONTRACTS: dict[MemberID, Mapping[str, Any]] = {
    "logicguard": LOGIC_ADMISSION_CONTRACT,
    "sourceguard": SOURCE_ADMISSION_CONTRACT,
    "traceguard": TRACE_ADMISSION_CONTRACT,
    "experimentguard": EXPERIMENT_ADMISSION_CONTRACT,
}

MEMBER_ADMISSION_BUILDERS = {
    "logicguard": logic_admission_evidence,
    "sourceguard": source_admission_evidence,
    "traceguard": trace_admission_evidence,
    "experimentguard": experiment_admission_evidence,
}


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
    task_facts_fingerprint: str
    matched_positive_condition_ids: tuple[str, ...]
    matching_task_fact_ids: tuple[str, ...]
    missing_required_condition_ids: tuple[str, ...]
    forbidden_dispositions: tuple[Mapping[str, Any], ...]
    first_action: str
    first_reference: str
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
        task_facts_fingerprint = str(raw.get("task_facts_fingerprint", ""))
        if not task_facts_fingerprint.startswith("sha256:"):
            raise ValueError(f"{member_id} task-facts fingerprint is required")
        positive_ids = _string_ids(
            raw.get("matched_positive_condition_ids", []),
            f"{member_id}.matched_positive_condition_ids",
        )
        matching_fact_ids = _string_ids(
            raw.get("matching_task_fact_ids", []),
            f"{member_id}.matching_task_fact_ids",
        )
        missing_required_ids = _string_ids(
            raw.get("missing_required_condition_ids", []),
            f"{member_id}.missing_required_condition_ids",
        )
        forbidden_rows = raw.get("forbidden_dispositions")
        if not isinstance(forbidden_rows, list) or not forbidden_rows:
            raise ValueError(f"{member_id}.forbidden_dispositions must be non-empty")
        if any(not isinstance(row, Mapping) for row in forbidden_rows):
            raise ValueError(f"{member_id}.forbidden_dispositions must contain objects")
        first_action = str(raw.get("first_action", ""))
        first_reference = str(raw.get("first_reference", ""))
        if applicability == "applicable" and (
            not positive_ids or not matching_fact_ids or not first_action or not first_reference
        ):
            raise ValueError(f"{member_id} applicable evidence lacks derived first action")
        return cls(
            member_id=member_id,  # type: ignore[arg-type]
            request_fingerprint=request_digest,
            applicability=applicability,  # type: ignore[arg-type]
            forbidden_status=forbidden,  # type: ignore[arg-type]
            task_facts_fingerprint=task_facts_fingerprint,
            matched_positive_condition_ids=positive_ids,
            matching_task_fact_ids=matching_fact_ids,
            missing_required_condition_ids=missing_required_ids,
            forbidden_dispositions=tuple(dict(row) for row in forbidden_rows),
            first_action=first_action,
            first_reference=first_reference,
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
class RouteComposition:
    status: Literal["composition_ready"]
    request_id: str
    business_intent_id: str
    member_ids: tuple[MemberID, ...]
    steps: tuple[Mapping[str, Any], ...]
    handoffs: tuple[Mapping[str, Any], ...]
    field_owners: tuple[Mapping[str, Any], ...]
    overall_claim_boundary: str
    suite_version: str
    suite_fingerprint: str
    schema_version: str = COMPOSITION_SCHEMA

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


def build_admission_set(
    task_facts: Mapping[str, Any],
    argv: Sequence[str],
    *,
    business_intent_id: str,
) -> dict[str, Any]:
    """Derive all member rows from one current source-bound task-facts packet."""

    packet = TaskFactPacket.from_dict(task_facts)
    expected_request = request_fingerprint(argv, business_intent_id=business_intent_id)
    if packet.request_fingerprint != expected_request:
        raise ValueError("task facts do not bind the exact current request")
    known_kinds = set().union(
        *(contract_fact_kinds(contract) for contract in MEMBER_ADMISSION_CONTRACTS.values())
    )
    unknown_kinds = sorted({row.kind for row in packet.facts}.difference(known_kinds))
    if unknown_kinds:
        raise ValueError("task facts contain unknown kinds: " + ", ".join(unknown_kinds))
    expected_reviews = expected_forbidden_review_keys(tuple(MEMBER_ADMISSION_CONTRACTS.values()))
    actual_reviews = {(row.member_id, row.condition_id) for row in packet.forbidden_reviews}
    if actual_reviews != expected_reviews:
        missing = sorted(expected_reviews.difference(actual_reviews))
        foreign = sorted(actual_reviews.difference(expected_reviews))
        raise ValueError(f"forbidden review inventory mismatch; missing={missing}; foreign={foreign}")
    rows = [
        MEMBER_ADMISSION_BUILDERS[member](task_facts=packet)
        for member in MEMBER_BINDINGS
    ]
    return {
        "schema_version": ADMISSION_SET_SCHEMA,
        "request_fingerprint": packet.request_fingerprint,
        "task_facts_fingerprint": packet.fingerprint(),
        "member_evidence": rows,
    }


def _minimum_sufficient_members(
    rows: Sequence[MemberAdmissionEvidence],
    packet: TaskFactPacket,
) -> tuple[tuple[MemberID, ...], ...]:
    """Return every minimum-cardinality member set covering all primary facts."""

    required_fact_ids = {
        row.fact_id for row in packet.facts if row.role == "primary_action"
    }
    admitted = tuple(row for row in rows if row.admitted)
    for size in range(1, len(admitted) + 1):
        matches: list[tuple[MemberID, ...]] = []
        for subset in itertools.combinations(admitted, size):
            covered = set().union(
                *(set(row.matching_task_fact_ids) for row in subset)
            )
            if covered == required_fact_ids:
                matches.append(tuple(row.member_id for row in subset))
        if matches:
            return tuple(matches)
    return ()


def _validate_composition(
    raw: Mapping[str, Any],
    *,
    required_members: tuple[MemberID, ...],
    rows: Sequence[MemberAdmissionEvidence],
    business_intent_id: str,
) -> RouteComposition:
    allowed_root = {
        "schema_version",
        "steps",
        "handoffs",
        "field_owners",
        "overall_claim_boundary",
    }
    unknown_root = set(raw).difference(allowed_root)
    if unknown_root:
        raise ValueError(
            "composition contains unknown fields: " + ", ".join(sorted(unknown_root))
        )
    if raw.get("schema_version") != COMPOSITION_SCHEMA:
        raise ValueError("composition requires the current schema")
    steps_raw = raw.get("steps")
    handoffs_raw = raw.get("handoffs")
    owners_raw = raw.get("field_owners")
    claim_boundary = str(raw.get("overall_claim_boundary", "")).strip()
    if not isinstance(steps_raw, list) or not isinstance(handoffs_raw, list) or not isinstance(owners_raw, list):
        raise ValueError("composition steps, handoffs, and field_owners must be arrays")
    if not claim_boundary or claim_boundary.lower() in {"placeholder", "tbd", "unknown"}:
        raise ValueError("composition requires one explicit overall claim boundary")

    allowed_step = {
        "step_id",
        "order",
        "member_id",
        "responsibility_condition_ids",
        "depends_on_step_ids",
        "input_handoff_ids",
        "output_handoff_ids",
    }
    steps: list[dict[str, Any]] = []
    for index, item in enumerate(steps_raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"composition.steps[{index}] must be an object")
        unknown = set(item).difference(allowed_step)
        if unknown:
            raise ValueError(
                f"composition.steps[{index}] contains unknown fields: "
                + ", ".join(sorted(unknown))
            )
        step_id = str(item.get("step_id", "")).strip()
        member_id = str(item.get("member_id", "")).strip()
        order = item.get("order")
        if not step_id or member_id not in MEMBER_BINDINGS or not isinstance(order, int):
            raise ValueError(f"composition.steps[{index}] has invalid identity or order")
        steps.append(
            {
                "step_id": step_id,
                "order": order,
                "member_id": member_id,
                "responsibility_condition_ids": list(
                    _string_ids(item.get("responsibility_condition_ids"), f"{step_id}.responsibility_condition_ids")
                ),
                "depends_on_step_ids": list(
                    _string_ids(item.get("depends_on_step_ids"), f"{step_id}.depends_on_step_ids")
                ),
                "input_handoff_ids": list(
                    _string_ids(item.get("input_handoff_ids"), f"{step_id}.input_handoff_ids")
                ),
                "output_handoff_ids": list(
                    _string_ids(item.get("output_handoff_ids"), f"{step_id}.output_handoff_ids")
                ),
            }
        )
    if len(steps) != len(required_members):
        raise ValueError("composition must contain exactly one step for each minimum-sufficient member")
    step_ids = [row["step_id"] for row in steps]
    if len(step_ids) != len(set(step_ids)):
        raise ValueError("composition step ids must be unique")
    member_ids = tuple(row["member_id"] for row in steps)
    if len(set(member_ids)) != len(member_ids) or set(member_ids) != set(required_members):
        raise ValueError("composition member set must equal the minimum-sufficient member set")
    if sorted(row["order"] for row in steps) != list(range(1, len(steps) + 1)):
        raise ValueError("composition order must be the contiguous range 1..N")
    steps.sort(key=lambda row: row["order"])
    by_step = {row["step_id"]: row for row in steps}

    expected_responsibilities = {
        row.member_id: set(row.matched_positive_condition_ids)
        for row in rows
        if row.member_id in required_members
    }
    seen_responsibilities: set[str] = set()
    for step in steps:
        responsibilities = set(step["responsibility_condition_ids"])
        if responsibilities != expected_responsibilities[step["member_id"]]:
            raise ValueError(
                f"{step['step_id']} responsibility set does not equal its derived member responsibility"
            )
        if seen_responsibilities.intersection(responsibilities):
            raise ValueError("composition responsibilities have multiple owners")
        seen_responsibilities.update(responsibilities)
        dependencies = set(step["depends_on_step_ids"])
        if step["order"] == 1 and dependencies:
            raise ValueError("the first composition step cannot depend on another step")
        if step["order"] > 1 and not dependencies:
            raise ValueError("every non-first composition step requires an explicit dependency")
        for dependency in dependencies:
            if dependency not in by_step or by_step[dependency]["order"] >= step["order"]:
                raise ValueError("composition dependencies must point to an earlier declared step")

    allowed_handoff = {"handoff_id", "from_step_id", "to_step_id", "field_ids"}
    handoffs: list[dict[str, Any]] = []
    for index, item in enumerate(handoffs_raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"composition.handoffs[{index}] must be an object")
        unknown = set(item).difference(allowed_handoff)
        if unknown:
            raise ValueError(f"composition.handoffs[{index}] contains unknown fields")
        handoff_id = str(item.get("handoff_id", "")).strip()
        source = str(item.get("from_step_id", "")).strip()
        target = str(item.get("to_step_id", "")).strip()
        fields = _string_ids(item.get("field_ids"), f"{handoff_id}.field_ids")
        if not handoff_id or source not in by_step or target not in by_step or source == target:
            raise ValueError(f"composition.handoffs[{index}] has invalid endpoints")
        if source not in by_step[target]["depends_on_step_ids"]:
            raise ValueError("every handoff must correspond to a declared target dependency")
        handoffs.append(
            {
                "handoff_id": handoff_id,
                "from_step_id": source,
                "to_step_id": target,
                "field_ids": list(fields),
            }
        )
    handoff_ids = [row["handoff_id"] for row in handoffs]
    if len(handoff_ids) != len(set(handoff_ids)):
        raise ValueError("composition handoff ids must be unique")
    by_handoff = {row["handoff_id"]: row for row in handoffs}
    for step in steps:
        expected_inputs = {
            row["handoff_id"] for row in handoffs if row["to_step_id"] == step["step_id"]
        }
        expected_outputs = {
            row["handoff_id"] for row in handoffs if row["from_step_id"] == step["step_id"]
        }
        if set(step["input_handoff_ids"]) != expected_inputs or set(step["output_handoff_ids"]) != expected_outputs:
            raise ValueError("composition step handoff inventories are incomplete or foreign")
        for dependency in step["depends_on_step_ids"]:
            if not any(
                row["from_step_id"] == dependency and row["to_step_id"] == step["step_id"]
                for row in handoffs
            ):
                raise ValueError("every declared dependency requires an explicit handoff")

    allowed_owner = {"field_id", "owner_step_id"}
    owners: list[dict[str, str]] = []
    for index, item in enumerate(owners_raw):
        if not isinstance(item, Mapping) or set(item).difference(allowed_owner):
            raise ValueError(f"composition.field_owners[{index}] is invalid")
        field_id = str(item.get("field_id", "")).strip()
        owner_step_id = str(item.get("owner_step_id", "")).strip()
        if not field_id or owner_step_id not in by_step:
            raise ValueError(f"composition.field_owners[{index}] has invalid values")
        owners.append({"field_id": field_id, "owner_step_id": owner_step_id})
    owner_map = {row["field_id"]: row["owner_step_id"] for row in owners}
    if len(owner_map) != len(owners):
        raise ValueError("each composition field must have exactly one owner")
    handed_fields = {
        field_id for handoff in handoffs for field_id in handoff["field_ids"]
    }
    if set(owner_map) != handed_fields:
        raise ValueError("field ownership must exactly cover every handed-off field")
    for handoff in handoffs:
        if any(owner_map[field_id] != handoff["from_step_id"] for field_id in handoff["field_ids"]):
            raise ValueError("handoff fields must be owned by the producing step")

    fingerprint = suite_fingerprint()
    request_material = json.dumps(
        {
            "business_intent_id": business_intent_id,
            "composition": raw,
            "suite_version": __version__,
            "suite_fingerprint": fingerprint,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return RouteComposition(
        status="composition_ready",
        request_id=f"request:{hashlib.sha256(request_material).hexdigest()}",
        business_intent_id=business_intent_id,
        member_ids=tuple(row["member_id"] for row in steps),
        steps=tuple(steps),
        handoffs=tuple(handoffs),
        field_owners=tuple(owners),
        overall_claim_boundary=claim_boundary,
        suite_version=__version__,
        suite_fingerprint=fingerprint,
    )


def select_member_request(
    task_facts: Mapping[str, Any],
    argv: Sequence[str],
    *,
    business_intent_id: str,
    active_request_id: str | None = None,
) -> RouteBinding | RouteComposition | TypedGap:
    """Derive and reconcile all four member rows without lexical fallback."""

    try:
        admission_set = build_admission_set(
            task_facts,
            argv,
            business_intent_id=business_intent_id,
        )
        rows = tuple(
            MemberAdmissionEvidence.from_dict(row)
            for row in admission_set["member_evidence"]
        )
    except (TypeError, ValueError) as exc:
        return TypedGap(
            status="blocked",
            code="task-facts-invalid",
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
    packet = TaskFactPacket.from_dict(task_facts)
    candidate_sets = _minimum_sufficient_members(rows, packet)
    if not candidate_sets:
        return TypedGap(
            status="blocked",
            code="member-admission-no-match",
            message=(
                "No applicable member set covers every source-bound primary responsibility; "
                "no lexical, list-order, or failure fallback is allowed."
            ),
        )
    if len(candidate_sets) != 1:
        return TypedGap(
            status="blocked",
            code="member-set-ambiguous",
            message="More than one equal-cardinality member set can cover the task; facts must distinguish ownership.",
        )
    required_members = candidate_sets[0]
    if len(required_members) == 1:
        if packet.composition is not None:
            return TypedGap(
                status="blocked",
                code="member-over-selection",
                message="One member can close the task independently; a composition would over-select the family.",
            )
        return bind_member_request(
            required_members[0],
            argv,
            business_intent_id=business_intent_id,
            active_request_id=active_request_id,
        )
    if active_request_id:
        return TypedGap(
            status="blocked",
            code="researchguard-recursion",
            message="An already-routed request cannot re-enter the ResearchGuard umbrella.",
        )
    if packet.composition is None:
        return TypedGap(
            status="blocked",
            code="member-composition-required",
            message="Multiple irreducible responsibilities require one explicit declarative composition.",
        )
    try:
        return _validate_composition(
            packet.composition,
            required_members=required_members,
            rows=rows,
            business_intent_id=business_intent_id,
        )
    except (TypeError, ValueError) as exc:
        return TypedGap(status="blocked", code="member-composition-invalid", message=str(exc))


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
    "COMPOSITION_SCHEMA",
    "TASK_FACTS_SCHEMA",
    "MemberID",
    "MemberAdmissionEvidence",
    "RouteBinding",
    "RouteComposition",
    "TypedGap",
    "TypedHandoff",
    "bind_member_request",
    "build_admission_set",
    "create_handoff",
    "request_fingerprint",
    "select_member_request",
]
