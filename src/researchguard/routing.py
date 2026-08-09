"""Minimum-sufficient ResearchGuard routing with no alternate-success path."""

from __future__ import annotations

import base64
import hashlib
import importlib
import itertools
import json
from dataclasses import asdict, dataclass
from pathlib import Path
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
from .model_envelope import (
    HandoffFieldContract,
    MemberModelEnvelope,
    NativeOwnerAttestation,
    replay_behavior_transition_oracle,
)
from .native_receipts import (
    NativeReceiptReference,
    _portable_native_receipt_record_scope,
    native_receipt_portable_record,
    native_receipt_signing_payload,
    resolve_native_receipt_reference,
)
from .portable_material import (
    portable_native_material_bytes,
    portable_native_material_record,
    portable_native_material_scope,
    verify_portable_native_material_record,
)
from .target_authority import (
    ExpectedTargetAnchor,
    _portable_expected_target_record_scope,
    _verify_rsa_pkcs1v15_sha256,
    expected_target_admission_signing_payload,
    expected_target_portable_record,
)
from .experiment.admission import CONTRACT as EXPERIMENT_ADMISSION_CONTRACT
from .experiment.admission import author_admission_evidence as experiment_admission_evidence
from .experiment.admission import contract_fingerprint as experiment_admission_fingerprint
from .logic.admission import CONTRACT as LOGIC_ADMISSION_CONTRACT
from .logic.admission import author_admission_evidence as logic_admission_evidence
from .logic.admission import contract_fingerprint as logic_admission_fingerprint
from .logic.guard_model_contract import (
    PORTABLE_TARGET_PROOF_MATERIAL_ID,
    build_portable_target_contract_material,
)
from .source.admission import CONTRACT as SOURCE_ADMISSION_CONTRACT
from .source.admission import author_admission_evidence as source_admission_evidence
from .source.admission import contract_fingerprint as source_admission_fingerprint
from .source.guard_contract import (
    PORTABLE_TARGET_PROOF_MATERIAL_ID as SOURCE_PORTABLE_TARGET_PROOF_MATERIAL_ID,
    build_portable_target_contract_material as build_source_portable_target_material,
)
from .trace.admission import CONTRACT as TRACE_ADMISSION_CONTRACT
from .trace.admission import author_admission_evidence as trace_admission_evidence
from .trace.admission import contract_fingerprint as trace_admission_fingerprint
from .trace.purpose_contract import (
    PORTABLE_TARGET_PROOF_MATERIAL_ID as TRACE_PORTABLE_TARGET_PROOF_MATERIAL_ID,
    build_portable_target_contract_material as build_trace_portable_target_material,
)


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

NATIVE_OWNER_REGISTRY_SCHEMA = "researchguard.native-owner-registry.v1"
PORTABLE_COMPOSITION_BUNDLE_SCHEMA = "researchguard.portable-composition-bundle.v2"
BEHAVIOR_TRANSITION_CASE_SCHEMA = "researchguard.behavior-transition-case.v1"

MEMBER_NATIVE_CHECKERS: dict[MemberID, tuple[str, str, str, str]] = {
    "logicguard": (
        "researchguard.logic.blueprint-check",
        "1",
        "researchguard.logic.owner_attestation",
        "replay_native_owner_attestation",
    ),
    "sourceguard": (
        "researchguard.source.blueprint-check",
        "1",
        "researchguard.source.owner_attestation",
        "replay_native_owner_attestation",
    ),
    "traceguard": (
        "researchguard.trace.blueprint-check",
        "1",
        "researchguard.trace.owner_attestation",
        "replay_native_owner_attestation",
    ),
    "experimentguard": (
        "researchguard.experiment.blueprint-check",
        "1",
        "researchguard.experiment.owner_attestation",
        "replay_native_owner_attestation",
    ),
}


def native_owner_registry_identity(member_id: str) -> str:
    """Return the frozen identity for one opaque member-native owner route."""

    if member_id not in MEMBER_BINDINGS:
        raise ValueError(f"unknown member-native owner: {member_id}")
    native_owner_id, primary_path_id, machine_path = MEMBER_BINDINGS[member_id]  # type: ignore[index]
    checker_id, checker_version, checker_module, checker_function = (
        MEMBER_NATIVE_CHECKERS[member_id]  # type: ignore[index]
    )
    material = json.dumps(
        {
            "schema_version": NATIVE_OWNER_REGISTRY_SCHEMA,
            "member_id": member_id,
            "native_owner_id": native_owner_id,
            "primary_path_id": primary_path_id,
            "machine_path": machine_path,
            "checker_id": checker_id,
            "checker_version": checker_version,
            "checker_module": checker_module,
            "checker_function": checker_function,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(material).hexdigest()


def _replay_native_owner_attestation(
    envelope: MemberModelEnvelope,
) -> NativeOwnerAttestation:
    """Invoke the exact closed member checker while keeping payload bytes opaque here."""

    checker_id, checker_version, module_name, function_name = (
        MEMBER_NATIVE_CHECKERS[envelope.member_id]  # type: ignore[index]
    )
    module = importlib.import_module(module_name)
    checker = getattr(module, function_name, None)
    if not callable(checker):
        raise ValueError(f"{envelope.member_id} current native checker is unavailable")
    attestation = checker(
        envelope,
        registry_identity=native_owner_registry_identity(envelope.member_id),
    )
    if not isinstance(attestation, NativeOwnerAttestation):
        raise ValueError(f"{envelope.member_id} native checker returned a foreign result")
    if (
        attestation.checker_id != checker_id
        or attestation.checker_version != checker_version
    ):
        raise ValueError(f"{envelope.member_id} native checker capability is stale")
    return attestation

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


def _transport_digest(value: object) -> str:
    body = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


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
    status: Literal["composition_ready", "composition_blocked"]
    request_id: str
    business_intent_id: str
    task_id: str
    member_ids: tuple[MemberID, ...]
    steps: tuple[Mapping[str, Any], ...]
    handoffs: tuple[Mapping[str, Any], ...]
    field_owners: tuple[Mapping[str, Any], ...]
    member_envelopes: tuple[Mapping[str, Any], ...]
    native_owner_attestations: tuple[Mapping[str, Any], ...]
    handoff_field_contracts: tuple[Mapping[str, Any], ...]
    stale_step_ids: tuple[str, ...]
    blocking_member_ids: tuple[MemberID, ...]
    composition_gaps: tuple[Mapping[str, str], ...]
    composition_fingerprint: str
    overall_claim_boundary: str
    suite_version: str
    suite_fingerprint: str
    portable_member_envelopes: tuple[Mapping[str, Any], ...] = ()
    expected_target_anchors: tuple[Mapping[str, Any], ...] = ()
    schema_version: str = COMPOSITION_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result.pop("portable_member_envelopes")
        result.pop("expected_target_anchors")
        return result


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
    native_owner_attestations: Sequence[Mapping[str, object]],
) -> RouteComposition:
    allowed_root = {
        "schema_version",
        "task_id",
        "steps",
        "handoffs",
        "field_owners",
        "member_envelopes",
        "expected_target_anchors",
        "handoff_field_contracts",
        "overall_claim_boundary",
    }
    unknown_root = set(raw).difference(allowed_root)
    if unknown_root:
        raise ValueError(
            "composition contains unknown fields: " + ", ".join(sorted(unknown_root))
        )
    if raw.get("schema_version") != COMPOSITION_SCHEMA:
        raise ValueError("composition requires the current schema")
    task_id = str(raw.get("task_id", "")).strip()
    if not task_id:
        raise ValueError("composition requires one current task_id")
    steps_raw = raw.get("steps")
    handoffs_raw = raw.get("handoffs")
    owners_raw = raw.get("field_owners")
    envelopes_raw = raw.get("member_envelopes")
    expected_target_anchors_raw = raw.get("expected_target_anchors")
    handoff_contracts_raw = raw.get("handoff_field_contracts")
    claim_boundary = str(raw.get("overall_claim_boundary", "")).strip()
    if not all(
        isinstance(item, list)
        for item in (
            steps_raw,
            handoffs_raw,
            owners_raw,
            envelopes_raw,
            expected_target_anchors_raw,
            handoff_contracts_raw,
        )
    ):
        raise ValueError("composition steps, handoffs, field owners, envelopes, and handoff contracts must be arrays")
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
        "member_envelope_id",
        "consumed_envelope_fingerprints",
        "claim_boundary_id",
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
        consumed_envelopes_raw = item.get("consumed_envelope_fingerprints")
        if not isinstance(consumed_envelopes_raw, list):
            raise ValueError(f"{step_id}.consumed_envelope_fingerprints must be an array")
        consumed_envelopes: list[dict[str, str]] = []
        for consumed_index, consumed in enumerate(consumed_envelopes_raw):
            if not isinstance(consumed, Mapping) or set(consumed) != {"envelope_id", "envelope_fingerprint"}:
                raise ValueError(f"{step_id}.consumed_envelope_fingerprints[{consumed_index}] is invalid")
            envelope_id = str(consumed.get("envelope_id", "")).strip()
            envelope_fingerprint = str(consumed.get("envelope_fingerprint", "")).strip()
            if not envelope_id or not envelope_fingerprint.startswith("sha256:"):
                raise ValueError(f"{step_id} consumed envelope identity is incomplete")
            consumed_envelopes.append(
                {"envelope_id": envelope_id, "envelope_fingerprint": envelope_fingerprint}
            )
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
                "member_envelope_id": str(item.get("member_envelope_id", "")).strip(),
                "consumed_envelope_fingerprints": consumed_envelopes,
                "claim_boundary_id": str(item.get("claim_boundary_id", "")).strip(),
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

    envelopes = tuple(MemberModelEnvelope.from_dict(item) for item in envelopes_raw)
    if len(envelopes) != len(required_members):
        raise ValueError("composition requires exactly one current envelope per selected member")
    envelope_ids = [item.envelope_id for item in envelopes]
    if len(envelope_ids) != len(set(envelope_ids)):
        raise ValueError("composition member envelope ids must be unique")
    envelopes_by_id = {item.envelope_id: item for item in envelopes}
    if {item.member_id for item in envelopes} != set(required_members):
        raise ValueError("composition envelope member set must equal the minimum-sufficient member set")
    if any(item.task_id != task_id for item in envelopes):
        raise ValueError("composition envelope task lineage is stale or foreign")

    expected_target_anchors = tuple(
        ExpectedTargetAnchor.from_dict(item) for item in expected_target_anchors_raw
    )
    if len(expected_target_anchors) != len(required_members):
        raise ValueError("composition requires exactly one expected-target anchor per selected member")
    anchor_members = [item.member_id for item in expected_target_anchors]
    if len(anchor_members) != len(set(anchor_members)) or set(anchor_members) != set(required_members):
        raise ValueError("composition expected-target anchor member set is incomplete or foreign")
    anchors_by_member = {item.member_id: item for item in expected_target_anchors}
    for envelope in envelopes:
        anchor = anchors_by_member[envelope.member_id]
        if (
            anchor.anchor_id != envelope.expected_target_anchor_id
            or anchor.anchor_fingerprint != envelope.expected_target_anchor_fingerprint
        ):
            raise ValueError(
                f"{envelope.member_id} expected-target anchor is stale or foreign"
            )

    handoff_contracts = tuple(
        HandoffFieldContract.from_dict(item) for item in handoff_contracts_raw
    )
    contract_ids = [item.handoff_id for item in handoff_contracts]
    if len(contract_ids) != len(set(contract_ids)):
        raise ValueError("handoff contract ids must be unique")
    if any(item.task_id != task_id for item in handoff_contracts):
        raise ValueError("handoff contract task lineage is stale or foreign")

    expected_responsibilities = {
        row.member_id: set(row.matched_positive_condition_ids)
        for row in rows
        if row.member_id in required_members
    }
    seen_responsibilities: set[str] = set()
    for step in steps:
        if not step["member_envelope_id"] or not step["claim_boundary_id"]:
            raise ValueError(f"{step['step_id']} requires an envelope and claim-boundary identity")
        envelope = envelopes_by_id.get(step["member_envelope_id"])
        if envelope is None or envelope.member_id != step["member_id"]:
            raise ValueError(f"{step['step_id']} envelope is missing or belongs to another member")
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
        expected_consumed_envelopes = {
            envelopes_by_id[by_step[dependency]["member_envelope_id"]].envelope_id:
            envelopes_by_id[by_step[dependency]["member_envelope_id"]].envelope_fingerprint
            for dependency in dependencies
        }
        actual_consumed_envelopes = {
            item["envelope_id"]: item["envelope_fingerprint"]
            for item in step["consumed_envelope_fingerprints"]
        }
        if actual_consumed_envelopes != expected_consumed_envelopes:
            raise ValueError(f"{step['step_id']} consumed envelope fingerprints are stale or incomplete")

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

    contracts_by_field = {item.field_id: item for item in handoff_contracts}
    if len(contracts_by_field) != len(handoff_contracts):
        raise ValueError("each handoff field must have exactly one current contract")
    if set(contracts_by_field) != handed_fields:
        raise ValueError("handoff field contracts must exactly cover every handed-off field")
    composition_gaps: list[dict[str, str]] = []
    blocking_members: set[MemberID] = set()
    stale_steps: set[str] = set()
    for step in steps:
        envelope = envelopes_by_id[step["member_envelope_id"]]
        for receipt in envelope.native_receipt_refs:
            for code, detail in resolve_native_receipt_reference(receipt):
                blocking_members.add(step["member_id"])
                stale_steps.add(step["step_id"])
                composition_gaps.append(
                    {
                        "code": code,
                        "object_id": receipt.receipt_id,
                        "detail": detail,
                    }
                )
        if envelope.terminal_status != "passed" or any(
            receipt.status != "passed" for receipt in envelope.native_receipt_refs
        ):
            blocking_members.add(step["member_id"])
            stale_steps.add(step["step_id"])
            composition_gaps.append(
                {
                    "code": f"member-terminal-{envelope.terminal_status}",
                    "object_id": step["step_id"],
                    "detail": ",".join(envelope.open_gap_refs),
                }
            )
    for handoff in handoffs:
        for field_id in handoff["field_ids"]:
            contract = contracts_by_field[field_id]
            producer_step = by_step[handoff["from_step_id"]]
            consumer_step = by_step[handoff["to_step_id"]]
            producer_envelope = envelopes_by_id[producer_step["member_envelope_id"]]
            consumer_envelope = envelopes_by_id[consumer_step["member_envelope_id"]]
            if (
                contract.handoff_id != handoff["handoff_id"]
                or contract.producer_step_id != producer_step["step_id"]
                or contract.producer_member_id != producer_step["member_id"]
                or contract.producer_envelope_id != producer_envelope.envelope_id
                or contract.producer_envelope_fingerprint != producer_envelope.envelope_fingerprint
            ):
                raise ValueError(f"handoff field {field_id} producer identity is stale or foreign")
            if field_id not in producer_envelope.output_field_ids:
                raise ValueError(f"handoff field {field_id} is absent from producer envelope outputs")
            producer_receipts = {
                (item.receipt_id, item.receipt_fingerprint)
                for item in producer_envelope.native_receipt_refs
            }
            if (
                contract.producer_native_receipt_id,
                contract.producer_native_receipt_fingerprint,
            ) not in producer_receipts:
                raise ValueError(f"handoff field {field_id} producer receipt is stale or foreign")
            expected_consumers = {
                (consumer_step["member_id"], consumer_step["step_id"])
            }
            actual_consumers = {(item.member_id, item.step_id) for item in contract.consumers}
            if actual_consumers != expected_consumers:
                raise ValueError(f"handoff field {field_id} consumer denominator is incomplete or foreign")
            if field_id not in consumer_envelope.input_field_ids:
                raise ValueError(f"handoff field {field_id} is absent from consumer envelope inputs")
            consumer_receipts = {
                (item.receipt_id, item.receipt_fingerprint)
                for item in consumer_envelope.native_receipt_refs
            }
            for acknowledgement in contract.acknowledgements:
                if acknowledgement.status == "consumed" and (
                    acknowledgement.native_receipt_id,
                    acknowledgement.native_receipt_fingerprint,
                ) not in consumer_receipts:
                    raise ValueError(f"handoff field {field_id} consumer receipt is stale or foreign")
                if acknowledgement.status == "rejected":
                    blocking_members.add(consumer_step["member_id"])
                    stale_steps.add(consumer_step["step_id"])
                    composition_gaps.append(
                        {
                            "code": "consumer-explicitly-rejected",
                            "object_id": consumer_step["step_id"],
                            "detail": acknowledgement.rejection_reason,
                        }
                    )
            for gap in contract.validation_gaps():
                blocking_members.add(consumer_step["member_id"])
                stale_steps.add(consumer_step["step_id"])
                composition_gaps.append({**gap, "detail": field_id})

    expected_inputs = {
        envelope.envelope_id: {
            field_id
            for contract in handoff_contracts
            for consumer in contract.consumers
            if consumer.member_id == envelope.member_id
            for field_id in (contract.field_id,)
        }
        for envelope in envelopes
    }
    expected_outputs = {
        envelope.envelope_id: {
            contract.field_id
            for contract in handoff_contracts
            if contract.producer_member_id == envelope.member_id
        }
        for envelope in envelopes
    }
    for envelope in envelopes:
        if set(envelope.input_field_ids) != expected_inputs[envelope.envelope_id]:
            raise ValueError(f"{envelope.envelope_id} input field denominator is incomplete or foreign")
        if set(envelope.output_field_ids) != expected_outputs[envelope.envelope_id]:
            raise ValueError(f"{envelope.envelope_id} output field denominator is incomplete or foreign")

    parsed_attestations: list[NativeOwnerAttestation] = []
    for index, item in enumerate(native_owner_attestations):
        try:
            parsed_attestations.append(NativeOwnerAttestation.from_dict(item))
        except (TypeError, ValueError) as exc:
            composition_gaps.append(
                {
                    "code": "native-owner-attestation-invalid",
                    "object_id": f"attestation:{index}",
                    "detail": str(exc),
                }
            )
    attestation_members = [item.member_id for item in parsed_attestations]
    if len(attestation_members) != len(set(attestation_members)):
        composition_gaps.append(
            {
                "code": "native-owner-attestation-duplicate",
                "object_id": task_id,
                "detail": "composition requires one native attestation candidate per member",
            }
        )
    foreign_members = sorted(set(attestation_members) - set(required_members))
    for member_id in foreign_members:
        composition_gaps.append(
            {
                "code": "native-owner-attestation-foreign-member",
                "object_id": member_id,
                "detail": "attestation member is outside the minimum-sufficient member set",
            }
        )
    candidates_by_member = {
        item.member_id: item
        for item in parsed_attestations
        if item.member_id in required_members
    }
    verified_attestations: list[NativeOwnerAttestation] = []
    for envelope in envelopes:
        candidate = candidates_by_member.get(envelope.member_id)
        if candidate is None:
            blocking_members.add(envelope.member_id)
            composition_gaps.append(
                {
                    "code": "native-owner-attestation-missing",
                    "object_id": envelope.member_id,
                    "detail": "the exact member-native checker must replay this envelope",
                }
            )
            continue
        try:
            replayed = _replay_native_owner_attestation(envelope)
        except Exception as exc:
            blocking_members.add(envelope.member_id)
            composition_gaps.append(
                {
                    "code": "native-owner-replay-failed",
                    "object_id": envelope.member_id,
                    "detail": str(exc),
                }
            )
            continue
        if candidate.to_dict() != replayed.to_dict():
            blocking_members.add(envelope.member_id)
            composition_gaps.append(
                {
                    "code": "native-owner-attestation-not-current",
                    "object_id": envelope.member_id,
                    "detail": "supplied attestation differs from the exact current member replay",
                }
            )
            continue
        verified_attestations.append(replayed)

    attestations = tuple(verified_attestations)

    fingerprint = suite_fingerprint()
    request_material = json.dumps(
        {
            "business_intent_id": business_intent_id,
            "composition": raw,
            "native_owner_attestations": [
                item.to_dict()
                for item in sorted(attestations, key=lambda item: item.member_id)
            ],
            "suite_version": __version__,
            "suite_fingerprint": fingerprint,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    composition_fingerprint = "sha256:" + hashlib.sha256(request_material).hexdigest()
    return RouteComposition(
        status="composition_blocked" if composition_gaps else "composition_ready",
        request_id=f"request:{hashlib.sha256(request_material).hexdigest()}",
        business_intent_id=business_intent_id,
        task_id=task_id,
        member_ids=tuple(row["member_id"] for row in steps),
        steps=tuple(steps),
        handoffs=tuple(handoffs),
        field_owners=tuple(owners),
        member_envelopes=tuple(
            item.to_dict(include_payload=False) for item in sorted(envelopes, key=lambda item: item.envelope_id)
        ),
        native_owner_attestations=tuple(
            item.to_dict() for item in sorted(attestations, key=lambda item: item.member_id)
        ),
        handoff_field_contracts=tuple(
            item.to_dict() for item in sorted(handoff_contracts, key=lambda item: item.field_id)
        ),
        stale_step_ids=tuple(sorted(stale_steps)),
        blocking_member_ids=tuple(sorted(blocking_members)),
        composition_gaps=tuple(composition_gaps),
        composition_fingerprint=composition_fingerprint,
        overall_claim_boundary=claim_boundary,
        suite_version=__version__,
        suite_fingerprint=fingerprint,
        portable_member_envelopes=tuple(
            item.to_dict(include_payload=True)
            for item in sorted(envelopes, key=lambda item: item.envelope_id)
        ),
        expected_target_anchors=tuple(
            item.to_dict()
            for item in sorted(expected_target_anchors, key=lambda item: item.member_id)
        ),
    )


def select_member_request(
    task_facts: Mapping[str, Any],
    argv: Sequence[str],
    *,
    business_intent_id: str,
    active_request_id: str | None = None,
    native_owner_attestations: Sequence[Mapping[str, object]] = (),
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
            native_owner_attestations=native_owner_attestations,
        )
    except (TypeError, ValueError) as exc:
        return TypedGap(status="blocked", code="member-composition-invalid", message=str(exc))


def composition_impact(
    composition: RouteComposition,
    changed_ids: Sequence[str],
) -> dict[str, Any]:
    """Project exact declared downstream staleness without executing a member."""

    changed = set(changed_ids)
    if composition.status != "composition_ready":
        return {
            "qualification_status": composition.status,
            "composition_fingerprint": composition.composition_fingerprint,
            "composition_status": composition.status,
            "blocking_member_ids": list(composition.blocking_member_ids),
            "composition_gaps": [dict(item) for item in composition.composition_gaps],
            "changed_ids": sorted(changed),
            "affected_step_ids": [],
            "affected_handoff_field_ids": [],
            "affected_claim_boundary_ids": [],
            "unaffected_step_ids": [],
            "unknown_dependency_ids": [],
            "unknown_ownership": False,
            "run_all_selected": False,
            "partial_result_suppressed": True,
            "claim_boundary": composition.overall_claim_boundary,
        }
    steps = {str(item["step_id"]): item for item in composition.steps}
    envelope_owner_step = {
        str(step["member_envelope_id"]): step_id for step_id, step in steps.items()
    }
    envelopes = {
        str(item["envelope_id"]): item for item in composition.member_envelopes
    }
    contracts = {
        str(item["field_id"]): item for item in composition.handoff_field_contracts
    }
    attestations = {
        str(item["member_id"]): item for item in composition.native_owner_attestations
    }
    known: set[str] = {
        composition.task_id,
        composition.request_id,
        composition.composition_fingerprint,
        composition.overall_claim_boundary,
    }
    affected_steps: set[str] = set(changed) & set(steps)
    affected_fields: set[str] = set()
    for step_id, step in steps.items():
        tokens = {
            step_id,
            str(step["claim_boundary_id"]),
            *(str(value) for value in step["responsibility_condition_ids"]),
        }
        known.update(tokens)
        if changed & tokens:
            affected_steps.add(step_id)
    for envelope_id, envelope in envelopes.items():
        tokens = {
            envelope_id,
            str(envelope["envelope_fingerprint"]),
            str(envelope["model_fingerprint"]),
            str(envelope["payload_fingerprint"]),
            str(envelope["native_model_id"]),
            str(envelope["native_schema_id"]),
            str(envelope["native_schema_version"]),
            *(str(item["receipt_id"]) for item in envelope["native_receipt_refs"]),
            *(str(item["receipt_fingerprint"]) for item in envelope["native_receipt_refs"]),
            *(str(item) for item in envelope["open_gap_refs"]),
        }
        known.update(tokens)
        if changed & tokens:
            affected_steps.add(envelope_owner_step[envelope_id])
    for member_id, attestation in attestations.items():
        step_id = next(
            step_id for step_id, step in steps.items() if str(step["member_id"]) == member_id
        )
        tokens = {
            str(attestation["attestation_id"]),
            str(attestation["attestation_fingerprint"]),
            str(attestation["registry_identity"]),
        }
        known.update(tokens)
        if changed & tokens:
            affected_steps.add(step_id)
    for field_id, contract in contracts.items():
        tokens = {
            field_id,
            str(contract["handoff_id"]),
            str(contract["field_schema_id"]),
            str(contract["payload_fingerprint"]),
            str(contract["contract_fingerprint"]),
            str(contract["producer_native_receipt_id"]),
            str(contract["producer_native_receipt_fingerprint"]),
        }
        known.update(tokens)
        if changed & tokens:
            affected_fields.add(field_id)
            affected_steps.update(str(item["step_id"]) for item in contract["consumers"])

    # A changed step invalidates its emitted fields, direct consumers, and then
    # only declared transitive dependants. No sibling or run-all expansion exists.
    while True:
        before = (len(affected_steps), len(affected_fields))
        for field_id, contract in contracts.items():
            if str(contract["producer_step_id"]) in affected_steps:
                affected_fields.add(field_id)
            if field_id in affected_fields:
                affected_steps.update(str(item["step_id"]) for item in contract["consumers"])
        for step_id, step in steps.items():
            if set(str(item) for item in step["depends_on_step_ids"]) & affected_steps:
                affected_steps.add(step_id)
        if before == (len(affected_steps), len(affected_fields)):
            break

    unknown = sorted(changed - known)
    result: dict[str, Any] = {
        "qualification_status": composition.status,
        "composition_status": composition.status,
        "blocking_member_ids": [],
        "composition_gaps": [],
        "composition_fingerprint": composition.composition_fingerprint,
        "changed_ids": sorted(changed),
        "affected_step_ids": sorted(affected_steps),
        "affected_handoff_field_ids": sorted(affected_fields),
        "affected_claim_boundary_ids": sorted(
            str(steps[item]["claim_boundary_id"]) for item in affected_steps
        ),
        "unaffected_step_ids": sorted(set(steps) - affected_steps),
        "unknown_dependency_ids": unknown,
        "unknown_ownership": bool(unknown),
        "run_all_selected": False,
    }
    if unknown:
        result["affected_step_ids"] = []
        result["affected_handoff_field_ids"] = []
        result["affected_claim_boundary_ids"] = []
        result["unaffected_step_ids"] = []
        result["partial_result_suppressed"] = True
    else:
        result["partial_result_suppressed"] = False
    return result


def reverse_trace_composition(
    composition: RouteComposition,
    output_id: str,
) -> dict[str, Any]:
    """Trace transport provenance and stop at every native receipt boundary."""

    if composition.status != "composition_ready":
        return {
            "output_id": output_id,
            "output_kind": "unresolved_due_to_composition",
            "overall_claim_boundary": composition.overall_claim_boundary,
            "qualification_status": composition.status,
            "composition_status": composition.status,
            "blocking_member_ids": list(composition.blocking_member_ids),
            "composition_gaps": [dict(item) for item in composition.composition_gaps],
            "trace_status": "incomplete",
            "steps": [],
            "handoff_fields": [],
            "partial_result_suppressed": True,
            "payload_interpreted": False,
            "native_semantics_interpreted": False,
            "terminal_capability_boundary": (
                "ResearchGuard composition qualification failed before output resolution; "
                "only the composition blockers and claim boundary are available."
            ),
        }
    steps = {str(item["step_id"]): item for item in composition.steps}
    envelopes = {
        str(item["envelope_id"]): item for item in composition.member_envelopes
    }
    attestations = {
        str(item["member_id"]): item for item in composition.native_owner_attestations
    }
    if output_id in {"overall", composition.overall_claim_boundary}:
        selected_steps = list(steps.values())
        output_kind = "overall_claim_boundary"
    else:
        selected_steps = [
            item for item in steps.values() if str(item["claim_boundary_id"]) == output_id
        ]
        output_kind = "step_claim_boundary"
    if not selected_steps:
        raise ValueError(f"composition output {output_id!r} has no declared owner")
    selected_step_ids = {str(item["step_id"]) for item in selected_steps}
    handoffs = [
        item
        for item in composition.handoff_field_contracts
        if str(item["producer_step_id"]) in selected_step_ids
        or any(str(row["step_id"]) in selected_step_ids for row in item["consumers"])
    ]
    return {
        "output_id": output_id,
        "output_kind": output_kind,
        "overall_claim_boundary": composition.overall_claim_boundary,
        "composition_status": composition.status,
        "qualification_status": composition.status,
        "blocking_member_ids": list(composition.blocking_member_ids),
        "composition_gaps": [dict(item) for item in composition.composition_gaps],
        "trace_status": "complete" if composition.status == "composition_ready" else "incomplete",
        "steps": [
            {
                "step_id": step["step_id"],
                "member_id": step["member_id"],
                "claim_boundary_id": step["claim_boundary_id"],
                "responsibility_condition_ids": list(step["responsibility_condition_ids"]),
                "envelope": {
                    key: envelopes[str(step["member_envelope_id"])][key]
                    for key in (
                        "envelope_id", "member_id", "native_model_id", "native_schema_id",
                        "native_schema_version", "model_fingerprint", "payload_fingerprint",
                        "envelope_fingerprint", "terminal_status", "claim_boundary",
                        "open_gap_refs", "responsibility_spans", "native_receipt_refs",
                    )
                },
                "native_interpretation_owner": step["member_id"],
                "native_owner_attestation": attestations.get(str(step["member_id"])),
                "trace_stops_at": "native_receipt_boundary",
            }
            for step in sorted(selected_steps, key=lambda item: int(item["order"]))
        ],
        "handoff_fields": handoffs,
        "partial_result_suppressed": False,
        "payload_interpreted": False,
        "native_semantics_interpreted": False,
        "terminal_capability_boundary": (
            "ResearchGuard proves only envelope identity, handoff topology, freshness, and receipt lineage; "
            "the named member must be invoked to interpret a native receipt."
        ),
    }


def _composition_behavior_transition_cases(
    composition: RouteComposition,
) -> tuple[dict[str, object], ...]:
    """Return complete executable-case contracts for transport-owned behavior."""

    ordered_steps = sorted(composition.steps, key=lambda item: int(item["order"]))
    changed_ids = (
        [str(ordered_steps[0]["step_id"])]
        if ordered_steps
        else [composition.composition_fingerprint]
    )
    impact_result = composition_impact(composition, changed_ids)
    reverse_result = reverse_trace_composition(composition, "overall")
    qualification_result = {
        "status": composition.status,
        "member_ids": list(composition.member_ids),
        "step_ids": [str(item["step_id"]) for item in ordered_steps],
        "handoff_field_ids": sorted(
            str(item["field_id"]) for item in composition.handoff_field_contracts
        ),
        "blocking_member_ids": list(composition.blocking_member_ids),
        "composition_gap_codes": sorted(
            str(item["code"]) for item in composition.composition_gaps
        ),
    }
    impact_projection = {
        "qualification_status": impact_result["qualification_status"],
        "changed_ids": impact_result["changed_ids"],
        "affected_step_ids": impact_result["affected_step_ids"],
        "affected_handoff_field_ids": impact_result[
            "affected_handoff_field_ids"
        ],
        "affected_claim_boundary_ids": impact_result[
            "affected_claim_boundary_ids"
        ],
        "unaffected_step_ids": impact_result["unaffected_step_ids"],
        "unknown_dependency_ids": impact_result["unknown_dependency_ids"],
        "partial_result_suppressed": impact_result["partial_result_suppressed"],
        "result_fingerprint": _transport_digest(impact_result),
    }
    reverse_projection = {
        "qualification_status": reverse_result["qualification_status"],
        "trace_status": reverse_result["trace_status"],
        "step_ids": [str(item["step_id"]) for item in reverse_result["steps"]],
        "handoff_field_ids": sorted(
            str(item["field_id"]) for item in reverse_result["handoff_fields"]
        ),
        "envelope_ids": sorted(
            str(item["envelope"]["envelope_id"])
            for item in reverse_result["steps"]
        ),
        "native_receipt_ids": sorted(
            str(receipt["receipt_id"])
            for item in reverse_result["steps"]
            for receipt in item["envelope"]["native_receipt_refs"]
        ),
        "partial_result_suppressed": reverse_result["partial_result_suppressed"],
        "result_fingerprint": _transport_digest(reverse_result),
    }
    pre_state = {
        "composition_status": composition.status,
        "composition_fingerprint": composition.composition_fingerprint,
        "selected_member_ids": list(composition.member_ids),
        "blocking_member_ids": list(composition.blocking_member_ids),
        "composition_gap_codes": sorted(
            str(item["code"]) for item in composition.composition_gaps
        ),
    }
    stable_post_state = dict(pre_state)
    definitions = (
        (
            "case:composition-qualification",
            "researchguard.composition.qualification",
            {"composition_fingerprint": composition.composition_fingerprint},
            qualification_result,
            ["emit_complete_composition_terminal", "preserve_native_payload_opacity"],
            "composition_not_ready",
            {
                "owner": "researchguard",
                "entrypoint": "researchguard.routing:_validate_composition",
                "expected_result_fingerprint": _transport_digest(
                    qualification_result
                ),
            },
        ),
        (
            "case:composition-impact",
            "researchguard.composition.impact",
            {"changed_ids": changed_ids},
            impact_projection,
            ["emit_declared_affected_closure", "preserve_unaffected_siblings"],
            "unknown_or_unqualified_impact_owner",
            {
                "owner": "researchguard",
                "entrypoint": "researchguard.routing:composition_impact",
                "expected_result_fingerprint": _transport_digest(impact_result),
            },
        ),
        (
            "case:composition-reverse-trace",
            "researchguard.composition.reverse-trace",
            {"output_id": "overall"},
            reverse_projection,
            ["emit_declared_reverse_denominator", "stop_at_native_receipt_boundary"],
            "unqualified_or_unowned_output",
            {
                "owner": "researchguard",
                "entrypoint": "researchguard.routing:reverse_trace_composition",
                "expected_result_fingerprint": _transport_digest(reverse_result),
            },
        ),
        (
            "case:portable-bundle-handoff",
            "researchguard.portable-bundle.handoff",
            {"input_kind": "portable_bundle_bytes"},
            {
                "self_consistency_status": (
                    "verified"
                    if composition.status == "composition_ready"
                    else "blocked"
                ),
                "producer_authenticity": "requires_external_trust",
                "qualified_status": "handoff_qualified",
            },
            ["verify_bundle_transport", "require_external_producer_trust"],
            "bundle_identity_or_evidence_gap",
            {
                "owner": "researchguard",
                "entrypoint": "researchguard.routing:qualify_portable_composition_bundle",
                "expected_composition_fingerprint": composition.composition_fingerprint,
            },
        ),
    )
    cases: list[dict[str, object]] = []
    for (
        case_id,
        behavior_id,
        input_value,
        output_value,
        effect,
        protected_failure,
        oracle,
    ) in definitions:
        transition = {
            "input": input_value,
            "pre_state": pre_state,
            "permitted_output": output_value,
            "post_state": stable_post_state,
            "effect": effect,
        }
        cases.append({
            "schema_version": BEHAVIOR_TRANSITION_CASE_SCHEMA,
            "case_id": case_id,
            "behavior_id": behavior_id,
            "input": input_value,
            "pre_state": pre_state,
            "permitted_output": output_value,
            "post_state": stable_post_state,
            "effect": effect,
            "protected_failure": protected_failure,
            "oracle": {
                **oracle,
                "good_case": {
                    "transition_fingerprint": _transport_digest(transition),
                    "expected_status": "passed",
                },
                "bad_case": {
                    "mutation_path": "input." + next(iter(input_value)),
                    "mutation_operator": "replace_with_foreign_value",
                    "expected_status": "blocked",
                    "expected_failure": protected_failure,
                },
            },
        })
    return tuple(cases)


def replay_composition_behavior_oracle(
    case: Mapping[str, object], candidate_transition: Mapping[str, object]
) -> dict[str, str]:
    """Execute one umbrella-domain good/bad transition boundary."""

    oracle = case.get("oracle")
    if not isinstance(oracle, Mapping) or not isinstance(
        oracle.get("good_case"), Mapping
    ):
        raise ValueError("composition behavior oracle is incomplete")
    candidate_fingerprint = _transport_digest(dict(candidate_transition))
    expected = str(oracle["good_case"].get("transition_fingerprint", ""))  # type: ignore[union-attr]
    if candidate_fingerprint == expected:
        return {
            "status": "passed",
            "behavior_id": str(case.get("behavior_id", "")),
            "transition_fingerprint": candidate_fingerprint,
            "failure": "",
        }
    return {
        "status": "blocked",
        "behavior_id": str(case.get("behavior_id", "")),
        "transition_fingerprint": candidate_fingerprint,
        "failure": str(case.get("protected_failure", "")),
    }


def _embedded_native_receipt_references(
    envelope: MemberModelEnvelope,
) -> tuple[NativeReceiptReference, ...]:
    """Return every exact receipt consumed by the member's native replay.

    A member envelope has one top-level producer receipt, while its opaque
    native model may consume additional purpose/interface receipts.  Portable
    replay has to carry that complete transitive denominator; otherwise a
    clean process silently depends on the exporting machine's authority root.
    """

    found: dict[tuple[str, str], NativeReceiptReference] = {
        (item.member_id, item.receipt_id): item
        for item in envelope.native_receipt_refs
    }

    def visit(value: object) -> None:
        if isinstance(value, Mapping):
            try:
                receipt = NativeReceiptReference.from_dict(value)
            except (TypeError, ValueError):
                for child in value.values():
                    visit(child)
            else:
                key = (receipt.member_id, receipt.receipt_id)
                previous = found.get(key)
                if previous is not None and previous.to_dict() != receipt.to_dict():
                    raise ValueError(
                        "portable composition contains conflicting embedded receipt identities"
                    )
                found[key] = receipt
        elif isinstance(value, list):
            for child in value:
                visit(child)

    if envelope.opaque_payload is not None:
        try:
            opaque = json.loads(envelope.opaque_payload.decode("utf-8"))
            visit(opaque)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("member opaque payload is not canonical JSON") from exc
        # ExperimentGuard's current native input freezes its exact spec by path
        # and hash.  Export resolves that source-owned material once so every
        # receipt consumed by the blueprint is transported with the bundle.
        if envelope.member_id == "experimentguard" and isinstance(opaque, Mapping):
            experiment_input = opaque.get("experiment_input")
            material = (
                experiment_input.get("material")
                if isinstance(experiment_input, Mapping)
                else None
            )
            if not isinstance(material, Mapping) or set(material) != {
                "spec_path",
                "spec_fingerprint",
            }:
                raise ValueError("ExperimentGuard portable input is not exact-current")
            spec_path = Path(str(material.get("spec_path", ""))).resolve()
            spec_body = portable_native_material_bytes(
                member_id=envelope.member_id,
                material_fingerprint=str(material.get("spec_fingerprint", "")),
            )
            if spec_body is None:
                try:
                    spec_body = spec_path.read_bytes()
                except OSError as exc:
                    raise ValueError(
                        "ExperimentGuard frozen spec material is unavailable for export"
                    ) from exc
            if (
                "sha256:" + hashlib.sha256(spec_body).hexdigest()
                != material.get("spec_fingerprint")
            ):
                raise ValueError("ExperimentGuard frozen spec material changed")
            try:
                visit(json.loads(spec_body.decode("utf-8")))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError("ExperimentGuard frozen spec is not canonical JSON") from exc
    return tuple(found[key] for key in sorted(found))


def _member_portable_native_material_records(
    envelope: MemberModelEnvelope,
) -> tuple[dict[str, object], ...]:
    if envelope.member_id == "logicguard":
        if envelope.opaque_payload is None:
            raise ValueError("LogicGuard portable envelope has no native material")
        try:
            opaque = json.loads(envelope.opaque_payload.decode("utf-8"))
            logic_input = opaque["argument_artifact_input"]
            material = logic_input["material"]
            depth = material["native_depth_evidence"]
            if not isinstance(depth, Mapping):
                raise ValueError("LogicGuard native depth evidence is invalid")
            body = build_portable_target_contract_material(
                target_root=str(depth["target_root"]),
                contract_path=str(depth["guard_contract"]),
            )
        except (KeyError, OSError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                "LogicGuard target proof material is unavailable for export"
            ) from exc
        return (
            portable_native_material_record(
                member_id=envelope.member_id,
                material_id=PORTABLE_TARGET_PROOF_MATERIAL_ID,
                media_type="application/json",
                body=body,
            ),
        )
    if envelope.member_id == "sourceguard":
        if envelope.opaque_payload is None:
            raise ValueError("SourceGuard portable envelope has no native material")
        try:
            opaque = json.loads(envelope.opaque_payload.decode("utf-8"))
            source_input = opaque["information_input"]
            material = source_input["material"]
            if not isinstance(material, Mapping):
                raise ValueError("SourceGuard native input is invalid")
            from .source.schema import BeliefState

            state = BeliefState.from_dict(dict(material["belief_state"]))
            body = build_source_portable_target_material(
                state,
                contract_path=str(material["contract_path"]),
            )
        except (KeyError, OSError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                "SourceGuard target proof material is unavailable for export"
            ) from exc
        return (
            portable_native_material_record(
                member_id=envelope.member_id,
                material_id=SOURCE_PORTABLE_TARGET_PROOF_MATERIAL_ID,
                media_type="application/json",
                body=body,
            ),
        )
    if envelope.member_id == "traceguard":
        if envelope.opaque_payload is None:
            raise ValueError("TraceGuard portable envelope has no native material")
        try:
            opaque = json.loads(envelope.opaque_payload.decode("utf-8"))
            trace_input = opaque["trace_input"]
            material = trace_input["material"]
            if not isinstance(material, Mapping) or not isinstance(
                material.get("model"), Mapping
            ):
                raise ValueError("TraceGuard native input is invalid")
            body = build_trace_portable_target_material(
                material["model"],
                candidate_path=str(material["candidate_path"]),
            )
        except (KeyError, OSError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                "TraceGuard target proof material is unavailable for export"
            ) from exc
        return (
            portable_native_material_record(
                member_id=envelope.member_id,
                material_id=TRACE_PORTABLE_TARGET_PROOF_MATERIAL_ID,
                media_type="application/json",
                body=body,
            ),
        )
    if envelope.member_id != "experimentguard":
        return ()
    if envelope.opaque_payload is None:
        raise ValueError("ExperimentGuard portable envelope has no native material")
    try:
        opaque = json.loads(envelope.opaque_payload.decode("utf-8"))
        experiment_input = opaque["experiment_input"]
        material = experiment_input["material"]
        if not isinstance(material, Mapping) or set(material) != {
            "spec_path",
            "spec_fingerprint",
        }:
            raise ValueError("ExperimentGuard portable input is not exact-current")
        spec_path = Path(str(material["spec_path"])).resolve()
        body = spec_path.read_bytes()
    except (KeyError, OSError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("ExperimentGuard frozen spec is unavailable for export") from exc
    fingerprint = "sha256:" + hashlib.sha256(body).hexdigest()
    if fingerprint != material["spec_fingerprint"]:
        raise ValueError("ExperimentGuard frozen spec material changed")
    return (
        portable_native_material_record(
            member_id=envelope.member_id,
            material_id="experimentguard:frozen-spec",
            media_type="application/json",
            body=body,
        ),
    )


def export_portable_composition_bundle(
    composition: RouteComposition,
) -> bytes:
    """Export deterministic complete transport evidence for an independent AI."""

    if composition.status != "composition_ready":
        raise ValueError("portable composition export requires composition_ready")
    if not composition.portable_member_envelopes:
        raise ValueError("portable composition export requires full opaque member envelopes")
    if not composition.expected_target_anchors:
        raise ValueError("portable composition export requires expected-target anchors")
    full_envelopes = tuple(
        MemberModelEnvelope.from_dict(item)
        for item in composition.portable_member_envelopes
    )
    target_records = tuple(
        expected_target_portable_record(ExpectedTargetAnchor.from_dict(item))
        for item in composition.expected_target_anchors
    )
    receipt_records_by_key: dict[tuple[str, str], dict[str, object]] = {}
    native_material_records_by_key: dict[tuple[str, str], dict[str, object]] = {}
    for envelope in full_envelopes:
        for record in _member_portable_native_material_records(envelope):
            key = (
                str(record["member_id"]),
                str(record["material_fingerprint"]),
            )
            existing = native_material_records_by_key.get(key)
            if existing is not None and existing != record:
                raise ValueError("portable composition contains conflicting native material")
            native_material_records_by_key[key] = record
    with portable_native_material_scope(native_material_records_by_key.values()):
        for envelope in full_envelopes:
            for receipt in _embedded_native_receipt_references(envelope):
                key = (receipt.member_id, receipt.receipt_id)
                record = native_receipt_portable_record(receipt)
                existing = receipt_records_by_key.get(key)
                if existing is not None and existing != record:
                    raise ValueError(
                        "portable composition contains conflicting receipt identities"
                    )
                receipt_records_by_key[key] = record
    core: dict[str, object] = {
        "schema_version": PORTABLE_COMPOSITION_BUNDLE_SCHEMA,
        "composition": composition.to_dict(),
        "portable_member_envelopes": [
            item.to_dict(include_payload=True)
            for item in sorted(full_envelopes, key=lambda item: item.member_id)
        ],
        "expected_target_records": sorted(
            target_records,
            key=lambda item: str(item["anchor"]["member_id"]),  # type: ignore[index]
        ),
        "native_receipt_records": [
            receipt_records_by_key[key] for key in sorted(receipt_records_by_key)
        ],
        "native_material_records": [
            native_material_records_by_key[key]
            for key in sorted(native_material_records_by_key)
        ],
        "behavior_transition_cases": list(
            _composition_behavior_transition_cases(composition)
        ),
        "claim_boundary": (
            "This bundle proves deterministic ResearchGuard transport structure, signed "
            "target/receipt self-consistency, handoff topology, and canonical transport "
            "transition cases. Bundle-carried public keys are not trust roots: producer "
            "authenticity and handoff_qualified require separately supplied exact trusted "
            "producer-descriptor fingerprints. Each member-native behavior manifest is "
            "member-derived, denominator-complete, and signed through its exact native "
            "producer receipt; it is authenticity-licensed only with those out-of-band "
            "producer trust declarations. Receipt identity uniqueness and carried-byte "
            "equality are proven only inside this one supplied bundle. Without a shared "
            "immutable authority or transparency log, one bundle cannot prove that its "
            "producer did not publish a conflicting receipt under the same identity in "
            "another independently isolated bundle."
        ),
    }
    fingerprint = _transport_digest(core)
    payload = {
        **core,
        "bundle_id": "portable-composition:" + fingerprint.removeprefix("sha256:"),
        "bundle_fingerprint": fingerprint,
    }
    return json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _portable_anchor_gaps(
    record: Mapping[str, object],
) -> tuple[ExpectedTargetAnchor | None, list[tuple[str, str]]]:
    gaps: list[tuple[str, str]] = []
    try:
        anchor_raw = record["anchor"]
        receipt_payload = record["receipt_payload"]
        descriptor = record["admission_producer_descriptor"]
        material_bytes = base64.b64decode(
            str(record["material_bytes_b64"]).encode("ascii"), validate=True
        )
        if not isinstance(anchor_raw, Mapping) or not isinstance(
            receipt_payload, Mapping
        ) or not isinstance(descriptor, Mapping):
            raise ValueError("portable expected-target record has invalid objects")
        anchor = ExpectedTargetAnchor.from_dict(anchor_raw)
    except (KeyError, TypeError, ValueError) as exc:
        return None, [("portable-target-record-invalid", str(exc))]
    if dict(receipt_payload) != anchor.receipt_payload:
        gaps.append(("portable-target-receipt-payload-mismatch", anchor.anchor_id))
    receipt_body = json.dumps(
        anchor.receipt_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if "sha256:" + hashlib.sha256(receipt_body).hexdigest() != anchor.receipt_fingerprint:
        gaps.append(("portable-target-receipt-fingerprint-mismatch", anchor.anchor_id))
    if "sha256:" + hashlib.sha256(material_bytes).hexdigest() != anchor.material_fingerprint:
        gaps.append(("portable-target-material-fingerprint-mismatch", anchor.anchor_id))
    public_key_fingerprint = _transport_digest(
        {
            "algorithm": str(descriptor.get("signature_algorithm", "")),
            "public_exponent": int(descriptor.get("public_exponent", 0)),
            "public_modulus_hex": str(descriptor.get("public_modulus_hex", "")).lower(),
        }
    )
    descriptor_fingerprint = _transport_digest(
        {
            "admission_owner_id": str(descriptor.get("admission_owner_id", "")),
            "admission_producer_id": str(descriptor.get("admission_producer_id", "")),
            "admission_producer_version": str(
                descriptor.get("admission_producer_version", "")
            ),
            "signing_key_id": str(descriptor.get("signing_key_id", "")),
            "signature_algorithm": str(descriptor.get("signature_algorithm", "")),
            "public_key_fingerprint": public_key_fingerprint,
        }
    )
    descriptor_checks = (
        (descriptor.get("admission_owner_id"), anchor.admission_owner_id),
        (descriptor.get("admission_producer_id"), anchor.admission_producer_id),
        (descriptor.get("admission_producer_version"), anchor.admission_producer_version),
        (descriptor.get("signing_key_id"), anchor.admission_key_id),
        (descriptor.get("signature_algorithm"), "rsa-pkcs1v15-sha256"),
        (descriptor.get("public_key_fingerprint"), public_key_fingerprint),
        (descriptor.get("producer_descriptor_fingerprint"), descriptor_fingerprint),
    )
    if any(str(actual) != str(expected) for actual, expected in descriptor_checks):
        gaps.append(("portable-target-producer-descriptor-mismatch", anchor.anchor_id))
    signing_payload = expected_target_admission_signing_payload(
        anchor_id=anchor.anchor_id,
        result_material=anchor.result_material,
        admission_input_fingerprint=anchor.admission_input_fingerprint,
        admission_result_fingerprint=anchor.admission_result_fingerprint,
        admission_key_id=anchor.admission_key_id,
    )
    verification_descriptor = {
        "algorithm": str(descriptor.get("signature_algorithm", "")),
        "public_exponent": int(descriptor.get("public_exponent", 0)),
        "public_modulus_hex": str(descriptor.get("public_modulus_hex", "")),
    }
    if not _verify_rsa_pkcs1v15_sha256(
        signing_payload, anchor.admission_signature, verification_descriptor
    ):
        gaps.append(("portable-target-signature-invalid", anchor.anchor_id))
    return anchor, gaps


def _portable_receipt_gaps(
    record: Mapping[str, object],
) -> tuple[NativeReceiptReference | None, list[tuple[str, str]]]:
    gaps: list[tuple[str, str]] = []
    try:
        reference_raw = record["reference"]
        receipt_payload = record["receipt_payload"]
        descriptor = record["producer_descriptor"]
        if not isinstance(reference_raw, Mapping) or not isinstance(
            receipt_payload, Mapping
        ) or not isinstance(descriptor, Mapping):
            raise ValueError("portable native-receipt record has invalid objects")
        receipt = NativeReceiptReference.from_dict(reference_raw)
    except (KeyError, TypeError, ValueError) as exc:
        return None, [("portable-native-receipt-record-invalid", str(exc))]
    if dict(receipt_payload) != receipt.receipt_payload:
        gaps.append(("portable-native-receipt-payload-mismatch", receipt.receipt_id))
    receipt_body = json.dumps(
        receipt.receipt_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if "sha256:" + hashlib.sha256(receipt_body).hexdigest() != receipt.receipt_fingerprint:
        gaps.append(("portable-native-receipt-fingerprint-mismatch", receipt.receipt_id))
    public_key_fingerprint = _transport_digest(
        {
            "algorithm": str(descriptor.get("signature_algorithm", "")),
            "public_exponent": int(descriptor.get("public_exponent", 0)),
            "public_modulus_hex": str(descriptor.get("public_modulus_hex", "")).lower(),
        }
    )
    descriptor_fingerprint = _transport_digest(
        {
            "member_id": str(descriptor.get("member_id", "")),
            "native_owner_id": str(descriptor.get("native_owner_id", "")),
            "producer_id": str(descriptor.get("producer_id", "")),
            "producer_version": str(descriptor.get("producer_version", "")),
            "checker_id": str(descriptor.get("checker_id", "")),
            "checker_version": str(descriptor.get("checker_version", "")),
            "checker_entrypoint": str(descriptor.get("checker_entrypoint", "")),
            "signature_algorithm": str(descriptor.get("signature_algorithm", "")),
            "signing_key_id": str(descriptor.get("signing_key_id", "")),
            "public_key_fingerprint": public_key_fingerprint,
        }
    )
    descriptor_checks = (
        (descriptor.get("member_id"), receipt.member_id),
        (descriptor.get("native_owner_id"), receipt.native_owner_id),
        (descriptor.get("producer_id"), receipt.producer_id),
        (descriptor.get("producer_version"), receipt.producer_version),
        (descriptor.get("checker_id"), receipt.checker_id),
        (descriptor.get("checker_version"), receipt.checker_version),
        (descriptor.get("checker_entrypoint"), receipt.checker_entrypoint),
        (descriptor.get("signature_algorithm"), receipt.signature_algorithm),
        (descriptor.get("signing_key_id"), receipt.signing_key_id),
        (descriptor.get("public_key_fingerprint"), public_key_fingerprint),
        (descriptor.get("producer_descriptor_fingerprint"), descriptor_fingerprint),
    )
    if any(str(actual) != str(expected) for actual, expected in descriptor_checks):
        gaps.append(("portable-native-receipt-producer-descriptor-mismatch", receipt.receipt_id))
    verification_descriptor = {
        "algorithm": str(descriptor.get("signature_algorithm", "")),
        "public_exponent": int(descriptor.get("public_exponent", 0)),
        "public_modulus_hex": str(descriptor.get("public_modulus_hex", "")),
    }
    signing_payload = native_receipt_signing_payload(
        receipt_id=receipt.receipt_id,
        core=receipt.core,
        signing_key_id=receipt.signing_key_id,
    )
    if not _verify_rsa_pkcs1v15_sha256(
        signing_payload, receipt.producer_signature, verification_descriptor
    ):
        gaps.append(("portable-native-receipt-signature-invalid", receipt.receipt_id))
    return receipt, gaps


def _portable_attestation_gaps(
    composition_raw: Mapping[str, object],
    full_envelopes: Sequence[MemberModelEnvelope],
) -> tuple[tuple[NativeOwnerAttestation, ...], tuple[tuple[str, str], ...]]:
    """Validate bundle-carried member attestations without consulting a registry."""

    raw_attestations = composition_raw.get("native_owner_attestations")
    if not isinstance(raw_attestations, list):
        return (), (("portable-native-owner-attestation-invalid", "not-an-array"),)
    try:
        attestations = tuple(
            NativeOwnerAttestation.from_dict(item) for item in raw_attestations
        )
    except (TypeError, ValueError) as exc:
        return (), (("portable-native-owner-attestation-invalid", str(exc)),)
    member_ids = [item.member_id for item in attestations]
    envelope_members = {item.member_id for item in full_envelopes}
    if len(member_ids) != len(set(member_ids)) or set(member_ids) != envelope_members:
        return (), (("portable-native-owner-attestation-denominator-mismatch", ",".join(sorted(member_ids))),)

    gaps: list[tuple[str, str]] = []
    by_member = {item.member_id: item for item in attestations}
    for envelope in full_envelopes:
        attestation = by_member[envelope.member_id]
        native_owner_id = MEMBER_BINDINGS[envelope.member_id][0]  # type: ignore[index]
        checker_id, checker_version, _module, _function = MEMBER_NATIVE_CHECKERS[
            envelope.member_id
        ]  # type: ignore[index]
        owner_receipts = tuple(
            item
            for item in envelope.native_receipt_refs
            if item.native_owner_id == native_owner_id
            and item.checker_id == checker_id
            and item.checker_version == checker_version
        )
        if len(owner_receipts) != 1:
            gaps.append(
                (
                    "portable-native-owner-receipt-denominator-mismatch",
                    envelope.member_id,
                )
            )
            continue
        owner_receipt = owner_receipts[0]
        expected_registry_identity = native_owner_registry_identity(envelope.member_id)
        checks = (
            (attestation.native_owner_id, native_owner_id, "owner"),
            (attestation.checker_id, checker_id, "checker"),
            (attestation.checker_version, checker_version, "checker-version"),
            (
                attestation.registry_identity,
                expected_registry_identity,
                "registry-identity",
            ),
            (attestation.task_id, envelope.task_id, "task"),
            (attestation.envelope_id, envelope.envelope_id, "envelope"),
            (
                attestation.envelope_fingerprint,
                envelope.envelope_fingerprint,
                "envelope-fingerprint",
            ),
            (attestation.native_model_id, envelope.native_model_id, "model"),
            (
                attestation.model_fingerprint,
                envelope.model_fingerprint,
                "model-fingerprint",
            ),
            (
                attestation.expected_target_anchor_id,
                envelope.expected_target_anchor_id,
                "target-anchor",
            ),
            (
                attestation.expected_target_anchor_fingerprint,
                envelope.expected_target_anchor_fingerprint,
                "target-anchor-fingerprint",
            ),
            (
                attestation.request_fingerprint,
                owner_receipt.request_fingerprint,
                "request-fingerprint",
            ),
            (
                attestation.input_fingerprint,
                owner_receipt.input_fingerprint,
                "input-fingerprint",
            ),
            (
                attestation.result_fingerprint,
                owner_receipt.result_fingerprint,
                "result-fingerprint",
            ),
            (attestation.terminal_status, envelope.terminal_status, "terminal"),
        )
        for actual, expected, field in checks:
            if actual != expected:
                gaps.append(
                    (
                        f"portable-native-owner-attestation-{field}-mismatch",
                        envelope.member_id,
                    )
                )
        if tuple(item.to_dict() for item in attestation.native_receipt_refs) != tuple(
            item.to_dict() for item in envelope.native_receipt_refs
        ):
            gaps.append(
                (
                    "portable-native-owner-attestation-receipts-mismatch",
                    envelope.member_id,
                )
            )
        identity_material = {
            "member_id": envelope.member_id,
            "native_owner_id": attestation.native_owner_id,
            "checker_id": attestation.checker_id,
            "checker_version": attestation.checker_version,
            "registry_identity": attestation.registry_identity,
            "task_id": envelope.task_id,
            "envelope_fingerprint": envelope.envelope_fingerprint,
            "request_fingerprint": attestation.request_fingerprint,
            "input_fingerprint": attestation.input_fingerprint,
            "result_fingerprint": attestation.result_fingerprint,
        }
        expected_attestation_id = (
            f"native-attestation:{envelope.member_id}:"
            + _transport_digest(identity_material)[7:31]
        )
        if attestation.attestation_id != expected_attestation_id:
            gaps.append(
                (
                    "portable-native-owner-attestation-id-mismatch",
                    envelope.member_id,
                )
            )
    if gaps:
        return (), tuple(sorted(set(gaps)))
    return attestations, ()


def _portable_topology_gaps(
    composition_raw: Mapping[str, object],
    full_envelopes: Sequence[MemberModelEnvelope],
    handoff_contracts: Sequence[HandoffFieldContract],
) -> tuple[tuple[str, str], ...]:
    """Replay the complete transport topology from bundle-carried identities."""

    gaps: list[tuple[str, str]] = []
    member_ids_raw = composition_raw.get("member_ids")
    steps_raw = composition_raw.get("steps")
    handoffs_raw = composition_raw.get("handoffs")
    owners_raw = composition_raw.get("field_owners")
    if not all(
        isinstance(item, list)
        for item in (member_ids_raw, steps_raw, handoffs_raw, owners_raw)
    ):
        return (("portable-composition-topology-invalid", "collections"),)
    member_ids = tuple(str(item) for item in member_ids_raw)
    if (
        not member_ids
        or len(member_ids) != len(set(member_ids))
        or set(member_ids) != {item.member_id for item in full_envelopes}
    ):
        gaps.append(("portable-composition-member-denominator-mismatch", ",".join(member_ids)))
    if composition_raw.get("stale_step_ids") or composition_raw.get(
        "blocking_member_ids"
    ) or composition_raw.get("composition_gaps"):
        gaps.append(("portable-composition-retains-blockers", str(composition_raw.get("task_id", ""))))

    if any(not isinstance(item, Mapping) for item in steps_raw):
        return tuple(sorted(set(gaps + [("portable-composition-step-invalid", "not-an-object")])))
    steps = [dict(item) for item in steps_raw]
    step_ids = [str(item.get("step_id", "")) for item in steps]
    if len(steps) != len(member_ids) or len(step_ids) != len(set(step_ids)):
        gaps.append(("portable-composition-step-denominator-mismatch", str(len(steps))))
    if sorted(item.get("order") for item in steps if isinstance(item.get("order"), int)) != list(
        range(1, len(steps) + 1)
    ):
        gaps.append(("portable-composition-order-invalid", str(len(steps))))
    by_step = {str(item.get("step_id", "")): item for item in steps}
    envelope_by_id = {item.envelope_id: item for item in full_envelopes}
    for step in steps:
        step_id = str(step.get("step_id", ""))
        member_id = str(step.get("member_id", ""))
        envelope = envelope_by_id.get(str(step.get("member_envelope_id", "")))
        if envelope is None or envelope.member_id != member_id:
            gaps.append(("portable-composition-step-envelope-mismatch", step_id))
            continue
        dependencies = step.get("depends_on_step_ids")
        consumed = step.get("consumed_envelope_fingerprints")
        if not isinstance(dependencies, list) or not isinstance(consumed, list):
            gaps.append(("portable-composition-step-dependency-invalid", step_id))
            continue
        expected_consumed: dict[str, str] = {}
        for dependency_id in dependencies:
            dependency = by_step.get(str(dependency_id))
            if dependency is None or not isinstance(dependency.get("order"), int) or not isinstance(
                step.get("order"), int
            ) or int(dependency["order"]) >= int(step["order"]):
                gaps.append(("portable-composition-dependency-invalid", step_id))
                continue
            dependency_envelope = envelope_by_id.get(
                str(dependency.get("member_envelope_id", ""))
            )
            if dependency_envelope is None:
                gaps.append(("portable-composition-dependency-envelope-missing", step_id))
                continue
            expected_consumed[
                dependency_envelope.envelope_id
            ] = dependency_envelope.envelope_fingerprint
        actual_consumed = {
            str(item.get("envelope_id", "")): str(
                item.get("envelope_fingerprint", "")
            )
            for item in consumed
            if isinstance(item, Mapping)
        }
        if actual_consumed != expected_consumed:
            gaps.append(("portable-composition-consumed-envelope-mismatch", step_id))

    if any(not isinstance(item, Mapping) for item in handoffs_raw):
        return tuple(sorted(set(gaps + [("portable-composition-handoff-invalid", "not-an-object")])))
    handoffs = [dict(item) for item in handoffs_raw]
    handoff_ids = [str(item.get("handoff_id", "")) for item in handoffs]
    if len(handoff_ids) != len(set(handoff_ids)):
        gaps.append(("portable-composition-handoff-duplicate", str(len(handoffs))))
    handed_fields: set[str] = set()
    for handoff in handoffs:
        handoff_id = str(handoff.get("handoff_id", ""))
        source_id = str(handoff.get("from_step_id", ""))
        target_id = str(handoff.get("to_step_id", ""))
        fields = handoff.get("field_ids")
        source = by_step.get(source_id)
        target = by_step.get(target_id)
        if source is None or target is None or not isinstance(fields, list):
            gaps.append(("portable-composition-handoff-endpoint-invalid", handoff_id))
            continue
        if source_id not in target.get("depends_on_step_ids", []):
            gaps.append(("portable-composition-handoff-dependency-mismatch", handoff_id))
        if handoff_id not in source.get("output_handoff_ids", []) or handoff_id not in target.get(
            "input_handoff_ids", []
        ):
            gaps.append(("portable-composition-step-handoff-inventory-mismatch", handoff_id))
        handed_fields.update(str(item) for item in fields)

    owner_map = {
        str(item.get("field_id", "")): str(item.get("owner_step_id", ""))
        for item in owners_raw
        if isinstance(item, Mapping)
    }
    if len(owner_map) != len(owners_raw) or set(owner_map) != handed_fields:
        gaps.append(("portable-composition-field-owner-denominator-mismatch", str(len(owner_map))))
    contracts_by_field = {item.field_id: item for item in handoff_contracts}
    if len(contracts_by_field) != len(handoff_contracts) or set(contracts_by_field) != handed_fields:
        gaps.append(("portable-handoff-contract-denominator-mismatch", str(len(contracts_by_field))))
    for handoff in handoffs:
        handoff_id = str(handoff.get("handoff_id", ""))
        source_id = str(handoff.get("from_step_id", ""))
        target_id = str(handoff.get("to_step_id", ""))
        source = by_step.get(source_id)
        target = by_step.get(target_id)
        if source is None or target is None:
            continue
        producer_envelope = envelope_by_id.get(str(source.get("member_envelope_id", "")))
        consumer_envelope = envelope_by_id.get(str(target.get("member_envelope_id", "")))
        if producer_envelope is None or consumer_envelope is None:
            continue
        for field_id in handoff.get("field_ids", []):
            field_id = str(field_id)
            contract = contracts_by_field.get(field_id)
            if contract is None:
                continue
            if (
                owner_map.get(field_id) != source_id
                or contract.handoff_id != handoff_id
                or contract.producer_step_id != source_id
                or contract.producer_member_id != source.get("member_id")
                or contract.producer_envelope_id != producer_envelope.envelope_id
                or contract.producer_envelope_fingerprint
                != producer_envelope.envelope_fingerprint
                or field_id not in producer_envelope.output_field_ids
                or field_id not in consumer_envelope.input_field_ids
            ):
                gaps.append(("portable-handoff-contract-topology-mismatch", field_id))
            if (
                contract.producer_native_receipt_id,
                contract.producer_native_receipt_fingerprint,
            ) not in {
                (item.receipt_id, item.receipt_fingerprint)
                for item in producer_envelope.native_receipt_refs
            }:
                gaps.append(("portable-handoff-producer-receipt-mismatch", field_id))
            expected_consumers = {(str(target.get("member_id", "")), target_id)}
            if {(item.member_id, item.step_id) for item in contract.consumers} != expected_consumers:
                gaps.append(("portable-handoff-consumer-denominator-mismatch", field_id))

    expected_inputs = {
        envelope.member_id: {
            contract.field_id
            for contract in handoff_contracts
            for consumer in contract.consumers
            if consumer.member_id == envelope.member_id
        }
        for envelope in full_envelopes
    }
    expected_outputs = {
        envelope.member_id: {
            contract.field_id
            for contract in handoff_contracts
            if contract.producer_member_id == envelope.member_id
        }
        for envelope in full_envelopes
    }
    for envelope in full_envelopes:
        if set(envelope.input_field_ids) != expected_inputs[envelope.member_id]:
            gaps.append(("portable-envelope-input-denominator-mismatch", envelope.member_id))
        if set(envelope.output_field_ids) != expected_outputs[envelope.member_id]:
            gaps.append(("portable-envelope-output-denominator-mismatch", envelope.member_id))
    return tuple(sorted(set(gaps)))


def _portable_route_composition(
    raw: Mapping[str, object],
) -> RouteComposition:
    """Reconstruct the exact public composition projection for canonical replay."""

    fields = {
        "status",
        "request_id",
        "business_intent_id",
        "task_id",
        "member_ids",
        "steps",
        "handoffs",
        "field_owners",
        "member_envelopes",
        "native_owner_attestations",
        "handoff_field_contracts",
        "stale_step_ids",
        "blocking_member_ids",
        "composition_gaps",
        "composition_fingerprint",
        "overall_claim_boundary",
        "suite_version",
        "suite_fingerprint",
        "schema_version",
    }
    if set(raw) != fields:
        raise ValueError("portable composition projection has unknown or missing fields")
    status = str(raw.get("status", ""))
    if status not in {"composition_ready", "composition_blocked"}:
        raise ValueError("portable composition projection has an invalid status")
    collection_fields = (
        "member_ids",
        "steps",
        "handoffs",
        "field_owners",
        "member_envelopes",
        "native_owner_attestations",
        "handoff_field_contracts",
        "stale_step_ids",
        "blocking_member_ids",
        "composition_gaps",
    )
    if any(not isinstance(raw.get(field), list) for field in collection_fields):
        raise ValueError("portable composition projection collections are invalid")
    mapping_fields = (
        "steps",
        "handoffs",
        "field_owners",
        "member_envelopes",
        "native_owner_attestations",
        "handoff_field_contracts",
        "composition_gaps",
    )
    if any(
        not isinstance(item, Mapping)
        for field in mapping_fields
        for item in raw[field]  # type: ignore[index]
    ):
        raise ValueError("portable composition projection rows are invalid")
    member_ids = tuple(str(item) for item in raw["member_ids"])  # type: ignore[index]
    blocking_member_ids = tuple(
        str(item) for item in raw["blocking_member_ids"]  # type: ignore[index]
    )
    if any(item not in MEMBER_BINDINGS for item in (*member_ids, *blocking_member_ids)):
        raise ValueError("portable composition projection contains an unknown member")
    return RouteComposition(
        status=status,  # type: ignore[arg-type]
        request_id=str(raw["request_id"]),
        business_intent_id=str(raw["business_intent_id"]),
        task_id=str(raw["task_id"]),
        member_ids=member_ids,  # type: ignore[arg-type]
        steps=tuple(dict(item) for item in raw["steps"]),  # type: ignore[index]
        handoffs=tuple(dict(item) for item in raw["handoffs"]),  # type: ignore[index]
        field_owners=tuple(dict(item) for item in raw["field_owners"]),  # type: ignore[index]
        member_envelopes=tuple(
            dict(item) for item in raw["member_envelopes"]  # type: ignore[index]
        ),
        native_owner_attestations=tuple(
            dict(item)
            for item in raw["native_owner_attestations"]  # type: ignore[index]
        ),
        handoff_field_contracts=tuple(
            dict(item)
            for item in raw["handoff_field_contracts"]  # type: ignore[index]
        ),
        stale_step_ids=tuple(
            str(item) for item in raw["stale_step_ids"]  # type: ignore[index]
        ),
        blocking_member_ids=blocking_member_ids,  # type: ignore[arg-type]
        composition_gaps=tuple(
            dict(item) for item in raw["composition_gaps"]  # type: ignore[index]
        ),
        composition_fingerprint=str(raw["composition_fingerprint"]),
        overall_claim_boundary=str(raw["overall_claim_boundary"]),
        suite_version=str(raw["suite_version"]),
        suite_fingerprint=str(raw["suite_fingerprint"]),
        schema_version=str(raw["schema_version"]),
    )


def qualify_portable_composition_bundle(
    bundle_bytes: bytes,
    *,
    trusted_producer_descriptor_fingerprints: Sequence[str] = (),
) -> dict[str, object]:
    """Qualify a portable handoff without repository, registry, or authority access."""

    trusted_descriptors = {
        str(item).strip() for item in trusted_producer_descriptor_fingerprints
    }
    if any(
        not item.startswith("sha256:") or len(item) != 71
        for item in trusted_descriptors
    ):
        raise ValueError("trusted producer descriptor fingerprints must be sha256 identities")
    gaps: list[tuple[str, str]] = []
    required_trusted_descriptors: set[str] = set()
    member_required_trust: dict[str, set[str]] = {}
    try:
        raw = json.loads(bundle_bytes.decode("utf-8"))
        if not isinstance(raw, Mapping):
            raise ValueError("portable composition bundle must be an object")
        expected_fields = {
            "schema_version",
            "bundle_id",
            "bundle_fingerprint",
            "composition",
            "portable_member_envelopes",
            "expected_target_records",
            "native_receipt_records",
            "native_material_records",
            "behavior_transition_cases",
            "claim_boundary",
        }
        if set(raw) != expected_fields:
            raise ValueError("portable composition bundle has unknown or missing fields")
        if raw.get("schema_version") != PORTABLE_COMPOSITION_BUNDLE_SCHEMA:
            raise ValueError("portable composition bundle requires the current schema")
        core = {key: raw[key] for key in expected_fields - {"bundle_id", "bundle_fingerprint"}}
        expected_fingerprint = _transport_digest(core)
        if raw.get("bundle_fingerprint") != expected_fingerprint or raw.get(
            "bundle_id"
        ) != "portable-composition:" + expected_fingerprint.removeprefix("sha256:"):
            raise ValueError("portable composition bundle identity is stale or foreign")
        composition_raw = raw["composition"]
        full_envelopes_raw = raw["portable_member_envelopes"]
        target_records_raw = raw["expected_target_records"]
        receipt_records_raw = raw["native_receipt_records"]
        native_material_records_raw = raw["native_material_records"]
        cases_raw = raw["behavior_transition_cases"]
        if not isinstance(composition_raw, Mapping) or not all(
            isinstance(item, list)
            for item in (
                full_envelopes_raw,
                target_records_raw,
                receipt_records_raw,
                native_material_records_raw,
                cases_raw,
            )
        ):
            raise ValueError("portable composition bundle collections are invalid")
        portable_composition = _portable_route_composition(composition_raw)
    except (UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return {
            "status": "handoff_blocked",
            "bundle_fingerprint": "",
            "composition_status": "unknown",
            "member_ids": [],
            "first_gap": {"code": "portable-bundle-invalid", "detail": str(exc)},
            "gaps": [{"code": "portable-bundle-invalid", "detail": str(exc)}],
            "partial_result_suppressed": True,
            "producer_authenticity": "failed",
            "required_trusted_producer_descriptor_fingerprints": [],
            "untrusted_producer_descriptor_fingerprints": [],
            "member_envelopes": [],
            "handoff_field_contracts": [],
            "member_object_dna_status": "not_licensed",
            "member_object_dna_gaps": [],
            "member_object_dna_results": [],
        }

    composition_status = str(composition_raw.get("status", ""))
    member_ids = tuple(str(item) for item in composition_raw.get("member_ids", []))
    if composition_status != "composition_ready":
        gaps.append(("portable-composition-not-ready", composition_status))
    try:
        full_envelopes = tuple(
            MemberModelEnvelope.from_dict(item) for item in full_envelopes_raw
        )
    except (TypeError, ValueError) as exc:
        full_envelopes = ()
        gaps.append(("portable-member-envelope-invalid", str(exc)))
    # Verify and index all signed portable authority records before native replay.
    # The replay receives these records through context-local scopes, so a clean
    # installed process needs neither the repository nor user-profile authority
    # files and no producer registration survives this qualification call.
    anchors: dict[str, ExpectedTargetAnchor] = {}
    portable_target_scope_records: list[Mapping[str, object]] = []
    for item in target_records_raw:
        if not isinstance(item, Mapping):
            gaps.append(("portable-target-record-invalid", "not-an-object"))
            continue
        descriptor = item.get("admission_producer_descriptor")
        if isinstance(descriptor, Mapping):
            required_trusted_descriptors.add(
                str(descriptor.get("producer_descriptor_fingerprint", ""))
            )
        anchor, anchor_gaps = _portable_anchor_gaps(item)
        gaps.extend(anchor_gaps)
        if anchor is not None and not anchor_gaps:
            portable_target_scope_records.append(item)
            anchors[anchor.member_id] = anchor
            if isinstance(descriptor, Mapping):
                member_required_trust.setdefault(anchor.member_id, set()).add(
                    str(descriptor.get("producer_descriptor_fingerprint", ""))
                )
    if set(anchors) != set(member_ids):
        gaps.append(("portable-target-denominator-mismatch", ",".join(member_ids)))
    for envelope in full_envelopes:
        anchor = anchors.get(envelope.member_id)
        if anchor is None or (
            anchor.anchor_id != envelope.expected_target_anchor_id
            or anchor.anchor_fingerprint != envelope.expected_target_anchor_fingerprint
        ):
            gaps.append(("portable-target-envelope-mismatch", envelope.member_id))

    receipts: dict[tuple[str, str], NativeReceiptReference] = {}
    portable_receipt_scope_records: list[Mapping[str, object]] = []
    for item in receipt_records_raw:
        if not isinstance(item, Mapping):
            gaps.append(("portable-native-receipt-record-invalid", "not-an-object"))
            continue
        descriptor = item.get("producer_descriptor")
        if isinstance(descriptor, Mapping):
            required_trusted_descriptors.add(
                str(descriptor.get("producer_descriptor_fingerprint", ""))
            )
        receipt, receipt_gaps = _portable_receipt_gaps(item)
        gaps.extend(receipt_gaps)
        if receipt is not None and not receipt_gaps:
            portable_receipt_scope_records.append(item)
            if isinstance(descriptor, Mapping):
                member_required_trust.setdefault(receipt.member_id, set()).add(
                    str(descriptor.get("producer_descriptor_fingerprint", ""))
                )
            key = (receipt.member_id, receipt.receipt_id)
            if key in receipts:
                gaps.append(("portable-native-receipt-duplicate", ":".join(key)))
            receipts[key] = receipt
    native_material_records: dict[tuple[str, str], Mapping[str, object]] = {}
    for item in native_material_records_raw:
        if not isinstance(item, Mapping):
            gaps.append(("portable-native-material-record-invalid", "not-an-object"))
            continue
        material_gaps = verify_portable_native_material_record(item)
        gaps.extend(material_gaps)
        if material_gaps:
            continue
        key = (str(item["member_id"]), str(item["material_fingerprint"]))
        if key in native_material_records:
            gaps.append(("portable-native-material-duplicate", ":".join(key)))
        native_material_records[key] = item
    required_native_materials: set[tuple[str, str]] = set()
    for envelope in full_envelopes:
        portable_material_id = {
            "logicguard": PORTABLE_TARGET_PROOF_MATERIAL_ID,
            "sourceguard": SOURCE_PORTABLE_TARGET_PROOF_MATERIAL_ID,
            "traceguard": TRACE_PORTABLE_TARGET_PROOF_MATERIAL_ID,
        }.get(envelope.member_id)
        if portable_material_id is not None:
            member_records = [
                (key, item)
                for key, item in native_material_records.items()
                if key[0] == envelope.member_id
                and str(item.get("material_id", ""))
                == portable_material_id
            ]
            if len(member_records) != 1:
                gaps.append(
                    (
                        "portable-native-material-binding-invalid",
                        f"{envelope.member_id}:target-proof-material-denominator",
                    )
                )
            else:
                required_native_materials.add(member_records[0][0])
            continue
        if envelope.member_id != "experimentguard" or envelope.opaque_payload is None:
            continue
        try:
            opaque = json.loads(envelope.opaque_payload.decode("utf-8"))
            material = opaque["experiment_input"]["material"]
            if not isinstance(material, Mapping) or set(material) != {
                "spec_path",
                "spec_fingerprint",
            }:
                raise ValueError("ExperimentGuard portable input is not exact-current")
            required_native_materials.add(
                (envelope.member_id, str(material["spec_fingerprint"]))
            )
        except (KeyError, TypeError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            gaps.append(("portable-native-material-binding-invalid", str(exc)))
    if set(native_material_records) != required_native_materials:
        gaps.append(
            (
                "portable-native-material-denominator-mismatch",
                str(len(required_native_materials)),
            )
        )

    expected_receipts: dict[tuple[str, str], NativeReceiptReference] = {}
    try:
        with portable_native_material_scope(native_material_records.values()):
            expected_receipts = {
                (receipt.member_id, receipt.receipt_id): receipt
                for envelope in full_envelopes
                for receipt in _embedded_native_receipt_references(envelope)
            }
    except (TypeError, ValueError) as exc:
        gaps.append(("portable-native-receipt-denominator-unresolved", str(exc)))
    if set(receipts) != set(expected_receipts):
        gaps.append(
            (
                "portable-native-receipt-denominator-mismatch",
                str(len(expected_receipts)),
            )
        )
    for key, expected in expected_receipts.items():
        actual = receipts.get(key)
        if actual is None or actual.to_dict() != expected.to_dict():
            gaps.append(("portable-native-receipt-envelope-mismatch", ":".join(key)))

    member_domain_gaps: dict[str, list[tuple[str, str]]] = {}
    try:
        with _portable_expected_target_record_scope(
            portable_target_scope_records
        ), _portable_native_receipt_record_scope(
            portable_receipt_scope_records
        ), portable_native_material_scope(native_material_records.values()):
            for envelope in full_envelopes:
                for case in envelope.behavior_manifest.domain_behavior_cases:
                    try:
                        result = replay_behavior_transition_oracle(
                            envelope, case, case.transition_payload
                        )
                    except (ImportError, OSError, TypeError, ValueError) as exc:
                        member_domain_gaps.setdefault(envelope.member_id, []).append(
                            ("member-native-domain-replay-failed", str(exc))
                        )
                        continue
                    if result.get("status") != "passed":
                        member_domain_gaps.setdefault(envelope.member_id, []).append(
                            (
                                "member-native-domain-oracle-rejected-good",
                                str(result.get("failure", case.behavior_id)),
                            )
                        )
    except (TypeError, ValueError) as exc:
        gaps.append(("portable-authority-scope-invalid", str(exc)))
    for member_id, rows in member_domain_gaps.items():
        gaps.extend((code, f"{member_id}:{detail}") for code, detail in rows)
    public_envelopes = {
        str(item.get("member_id", "")): item
        for item in composition_raw.get("member_envelopes", [])
        if isinstance(item, Mapping)
    }
    if {item.member_id for item in full_envelopes} != set(member_ids):
        gaps.append(("portable-member-envelope-denominator-mismatch", ",".join(member_ids)))
    for envelope in full_envelopes:
        if public_envelopes.get(envelope.member_id) != envelope.to_dict(
            include_payload=False
        ):
            gaps.append(("portable-member-envelope-projection-mismatch", envelope.member_id))

    _attestations, attestation_gaps = _portable_attestation_gaps(
        composition_raw, full_envelopes
    )
    gaps.extend(attestation_gaps)

    try:
        handoff_contracts = tuple(
            HandoffFieldContract.from_dict(item)
            for item in composition_raw.get("handoff_field_contracts", [])
        )
        for contract in handoff_contracts:
            gaps.extend(
                (str(item["code"]), str(item["object_id"]))
                for item in contract.validation_gaps()
            )
    except (TypeError, ValueError) as exc:
        handoff_contracts = ()
        gaps.append(("portable-handoff-contract-invalid", str(exc)))
    gaps.extend(
        _portable_topology_gaps(
            composition_raw,
            full_envelopes,
            handoff_contracts,
        )
    )

    required_case_fields = {
        "schema_version",
        "case_id",
        "behavior_id",
        "input",
        "pre_state",
        "permitted_output",
        "post_state",
        "effect",
        "protected_failure",
        "oracle",
    }
    case_ids: set[str] = set()
    behavior_ids: set[str] = set()
    for case in cases_raw:
        if not isinstance(case, Mapping) or set(case) != required_case_fields:
            gaps.append(("portable-behavior-case-invalid", "field-denominator"))
            continue
        if case.get("schema_version") != BEHAVIOR_TRANSITION_CASE_SCHEMA:
            gaps.append(("portable-behavior-case-invalid", str(case.get("case_id", ""))))
            continue
        case_id = str(case.get("case_id", ""))
        behavior_id = str(case.get("behavior_id", ""))
        oracle = case.get("oracle")
        if (
            not case_id
            or not behavior_id
            or not isinstance(case.get("input"), Mapping)
            or not isinstance(case.get("pre_state"), Mapping)
            or not isinstance(case.get("permitted_output"), Mapping)
            or not isinstance(case.get("post_state"), Mapping)
            or not isinstance(case.get("effect"), list)
            or not str(case.get("protected_failure", "")).strip()
            or not isinstance(oracle, Mapping)
            or not str(oracle.get("entrypoint", "")).strip()
            or not isinstance(oracle.get("good_case"), Mapping)
            or not isinstance(oracle.get("bad_case"), Mapping)
        ):
            gaps.append(("portable-behavior-case-incomplete", case_id))
            continue
        transition = {
            key: case[key]
            for key in (
                "input",
                "pre_state",
                "permitted_output",
                "post_state",
                "effect",
            )
        }
        good_case = oracle["good_case"]
        bad_case = oracle["bad_case"]
        if (
            set(good_case) != {"transition_fingerprint", "expected_status"}
            or good_case.get("transition_fingerprint") != _transport_digest(transition)
            or good_case.get("expected_status") != "passed"
            or set(bad_case) != {
                "mutation_path",
                "mutation_operator",
                "expected_status",
                "expected_failure",
            }
            or bad_case.get("expected_status") != "blocked"
            or bad_case.get("expected_failure") != case.get("protected_failure")
        ):
            gaps.append(("portable-behavior-oracle-invalid", case_id))
            continue
        if case_id in case_ids or behavior_id in behavior_ids:
            gaps.append(("portable-behavior-case-duplicate", case_id))
        case_ids.add(case_id)
        behavior_ids.add(behavior_id)
    expected_behaviors = {
        "researchguard.composition.qualification",
        "researchguard.composition.impact",
        "researchguard.composition.reverse-trace",
        "researchguard.portable-bundle.handoff",
    }
    if behavior_ids != expected_behaviors:
        gaps.append(("portable-behavior-case-denominator-mismatch", ",".join(sorted(behavior_ids))))

    canonical_cases = list(_composition_behavior_transition_cases(portable_composition))
    if cases_raw != canonical_cases:
        gaps.append(
            (
                "portable-behavior-case-canonical-mismatch",
                _transport_digest(cases_raw),
            )
        )

    unique_gaps = sorted(set(gaps))
    structural_blocked = bool(unique_gaps)
    untrusted_descriptors = sorted(
        required_trusted_descriptors.difference(trusted_descriptors)
    )
    trust_gaps = (
        [
            (
                "portable-producer-trust-not-licensed",
                ",".join(untrusted_descriptors),
            )
        ]
        if not structural_blocked and untrusted_descriptors
        else []
    )
    result_gaps = unique_gaps + trust_gaps
    if structural_blocked:
        status = "handoff_blocked"
        producer_authenticity = "failed"
    elif untrusted_descriptors:
        status = "handoff_self_consistent"
        producer_authenticity = "not_licensed"
    else:
        status = "handoff_qualified"
        producer_authenticity = "licensed"
    suppressed = status != "handoff_qualified"
    first_gap = (
        {"code": result_gaps[0][0], "detail": result_gaps[0][1]}
        if result_gaps
        else None
    )
    envelope_by_member = {item.member_id: item for item in full_envelopes}
    member_object_dna_results: list[dict[str, object]] = []
    member_object_dna_gaps: list[dict[str, str]] = []
    for member_id in member_ids:
        envelope = envelope_by_member.get(member_id)
        if envelope is None:
            member_gap = {
                "code": "member-behavior-manifest-missing",
                "member_id": member_id,
                "detail": "no exact current member envelope and behavior manifest were carried",
            }
            member_object_dna_gaps.append(member_gap)
            member_object_dna_results.append(
                {
                    "member_id": member_id,
                    "status": "not_licensed",
                    "manifest_fingerprint": "",
                    "domain_behavior_case_count": 0,
                    "integrity_case_count": 0,
                    "hierarchy_node_count": 0,
                    "interface_binding_count": 0,
                    "target_binding_count": 0,
                    "first_gap": member_gap,
                }
            )
            continue
        manifest = envelope.behavior_manifest
        required_member_trust = member_required_trust.get(member_id, set())
        untrusted_member = sorted(required_member_trust.difference(trusted_descriptors))
        if member_domain_gaps.get(member_id):
            member_status = "not_licensed"
            code, detail = member_domain_gaps[member_id][0]
            member_gap = {
                "code": code,
                "member_id": member_id,
                "detail": detail,
            }
        elif manifest.native_verifier_result.get("status") != "passed":
            member_status = "not_licensed"
            member_gap = {
                "code": "member-native-verifier-not-passed",
                "member_id": member_id,
                "detail": str(manifest.native_verifier_result.get("terminal_status", "")),
            }
        elif untrusted_member:
            member_status = "self_consistent"
            member_gap = {
                "code": "member-producer-trust-not-licensed",
                "member_id": member_id,
                "detail": ",".join(untrusted_member),
            }
        else:
            member_status = "licensed"
            member_gap = None
        if member_gap is not None:
            member_object_dna_gaps.append(member_gap)
        member_object_dna_results.append(
            {
                "member_id": member_id,
                "status": member_status,
                "manifest_id": manifest.expected_id,
                "manifest_fingerprint": manifest.expected_fingerprint,
                "domain_behavior_case_count": len(manifest.domain_behavior_cases),
                "integrity_case_count": len(manifest.integrity_cases),
                "hierarchy_node_count": len(manifest.hierarchy_node_ids),
                "interface_binding_count": len(manifest.interface_binding_ids),
                "target_binding_count": len(manifest.target_binding_ids),
                "native_receipt_count": len(manifest.native_receipt_expectations),
                "first_gap": member_gap,
            }
        )
    member_statuses = {
        str(item["status"]) for item in member_object_dna_results
    }
    if member_object_dna_results and member_statuses == {"licensed"}:
        member_object_dna_status = "licensed"
    elif member_object_dna_results and member_statuses.issubset(
        {"licensed", "self_consistent"}
    ):
        member_object_dna_status = "self_consistent"
    else:
        member_object_dna_status = "not_licensed"
    return {
        "status": status,
        "bundle_fingerprint": str(raw["bundle_fingerprint"]),
        "composition_status": composition_status,
        "member_ids": list(member_ids),
        "first_gap": first_gap,
        "gaps": [
            {"code": code, "detail": detail} for code, detail in result_gaps
        ],
        "partial_result_suppressed": suppressed,
        "producer_authenticity": producer_authenticity,
        "required_trusted_producer_descriptor_fingerprints": sorted(
            required_trusted_descriptors
        ),
        "untrusted_producer_descriptor_fingerprints": untrusted_descriptors,
        "member_envelopes": (
            []
            if suppressed
            else [item.to_dict(include_payload=False) for item in full_envelopes]
        ),
        "handoff_field_contracts": (
            [] if suppressed else [item.to_dict() for item in handoff_contracts]
        ),
        "member_object_dna_status": member_object_dna_status,
        "member_object_dna_gaps": member_object_dna_gaps,
        "member_object_dna_results": member_object_dna_results,
        "claim_boundary": str(raw["claim_boundary"]),
    }


def project_portable_composition_bundle(
    bundle_bytes: bytes,
    *,
    trusted_producer_descriptor_fingerprints: Sequence[str] = (),
    query_kind: Literal["member", "behavior", "handoff", "impact", "reverse"] | None = None,
    object_id: str = "",
) -> dict[str, object]:
    """Return a compact AI projection, with one explicit object-level drill-down.

    The complete bundle remains a disk artifact.  This entrypoint deliberately
    does not place opaque payloads, all behavior cases, or all handoffs into the
    default context projection.
    """

    qualified = qualify_portable_composition_bundle(
        bundle_bytes,
        trusted_producer_descriptor_fingerprints=(
            trusted_producer_descriptor_fingerprints
        ),
    )
    try:
        raw = json.loads(bundle_bytes.decode("utf-8"))
        composition_raw = raw["composition"]
        envelope_rows = raw["portable_member_envelopes"]
        if not isinstance(composition_raw, Mapping) or not isinstance(
            envelope_rows, list
        ):
            raise ValueError("portable projection collections are invalid")
        envelopes = tuple(MemberModelEnvelope.from_dict(item) for item in envelope_rows)
    except (UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        raw = {}
        composition_raw = {}
        envelopes = ()

    dna_by_member = {
        str(item.get("member_id", "")): item
        for item in qualified.get("member_object_dna_results", [])
        if isinstance(item, Mapping)
    }
    member_summaries = []
    for envelope in sorted(envelopes, key=lambda item: item.member_id):
        dna = dna_by_member.get(envelope.member_id, {})
        member_summaries.append(
            {
                "member_id": envelope.member_id,
                "terminal_status": envelope.terminal_status,
                "model_fingerprint": envelope.model_fingerprint,
                "envelope_fingerprint": envelope.envelope_fingerprint,
                "behavior_manifest_fingerprint": envelope.behavior_manifest.expected_fingerprint,
                "member_object_dna_status": str(dna.get("status", "not_licensed")),
                "domain_behavior_case_count": len(envelope.behavior_manifest.domain_behavior_cases),
                "integrity_case_count": len(envelope.behavior_manifest.integrity_cases),
                "hierarchy_node_count": len(envelope.behavior_manifest.hierarchy_node_ids),
                "interface_binding_count": len(envelope.behavior_manifest.interface_binding_ids),
                "target_binding_count": len(envelope.behavior_manifest.target_binding_ids),
                "native_receipt_count": len(envelope.native_receipt_refs),
            }
        )
    composition_cases = raw.get("behavior_transition_cases", [])
    handoff_rows = (
        composition_raw.get("handoff_field_contracts", [])
        if isinstance(composition_raw, Mapping)
        else []
    )
    summary: dict[str, object] = {
        "schema_version": "researchguard.portable-composition-projection.v1",
        "view": "summary" if query_kind is None else query_kind,
        "status": qualified.get("status", "handoff_blocked"),
        "bundle_fingerprint": qualified.get("bundle_fingerprint", ""),
        "composition_fingerprint": (
            str(composition_raw.get("composition_fingerprint", ""))
            if isinstance(composition_raw, Mapping)
            else ""
        ),
        "composition_status": qualified.get("composition_status", "unknown"),
        "producer_authenticity": qualified.get("producer_authenticity", "failed"),
        "member_object_dna_status": qualified.get(
            "member_object_dna_status", "not_licensed"
        ),
        "member_summaries": member_summaries,
        "counts": {
            "bundle_bytes": len(bundle_bytes),
            "members": len(envelopes),
            "composition_behavior_cases": (
                len(composition_cases) if isinstance(composition_cases, list) else 0
            ),
            "member_domain_behavior_cases": sum(
                len(item.behavior_manifest.domain_behavior_cases) for item in envelopes
            ),
            "member_integrity_cases": sum(
                len(item.behavior_manifest.integrity_cases) for item in envelopes
            ),
            "handoff_field_contracts": (
                len(handoff_rows) if isinstance(handoff_rows, list) else 0
            ),
            "native_receipt_records": len(raw.get("native_receipt_records", []))
            if isinstance(raw.get("native_receipt_records", []), list)
            else 0,
            "native_material_records": len(raw.get("native_material_records", []))
            if isinstance(raw.get("native_material_records", []), list)
            else 0,
            "expected_target_records": len(raw.get("expected_target_records", []))
            if isinstance(raw.get("expected_target_records", []), list)
            else 0,
        },
        "first_gap": qualified.get("first_gap"),
        "claim_boundary": qualified.get("claim_boundary", ""),
        "available_queries": {
            "member": "member_id",
            "behavior": "behavior_id_or_case_id",
            "handoff": "handoff_id_or_field_id",
            "impact": "changed_object_id",
            "reverse": "output_id",
        },
    }
    if query_kind is None:
        return summary
    query_id = str(object_id).strip()
    summary["object_id"] = query_id
    if not query_id:
        summary["query_status"] = "blocked"
        summary["query_gap"] = {"code": "portable-query-id-required", "detail": query_kind}
        return summary
    if qualified.get("status") != "handoff_qualified":
        summary["query_status"] = "suppressed"
        summary["query_gap"] = {
            "code": "portable-query-requires-qualified-handoff",
            "detail": query_id,
        }
        return summary

    detail: object | None = None
    if query_kind == "member":
        envelope = next((item for item in envelopes if item.member_id == query_id), None)
        if envelope is not None:
            manifest = envelope.behavior_manifest
            detail = {
                "member_id": envelope.member_id,
                "native_model_id": envelope.native_model_id,
                "model_fingerprint": envelope.model_fingerprint,
                "envelope_id": envelope.envelope_id,
                "envelope_fingerprint": envelope.envelope_fingerprint,
                "terminal_status": envelope.terminal_status,
                "claim_boundary": envelope.claim_boundary,
                "behavior_manifest_id": manifest.expected_id,
                "behavior_manifest_fingerprint": manifest.expected_fingerprint,
                "domain_behavior_denominator_ids": list(manifest.domain_behavior_denominator_ids),
                "integrity_case_ids": list(manifest.integrity_case_ids),
                "hierarchy_node_ids": list(manifest.hierarchy_node_ids),
                "interface_binding_ids": list(manifest.interface_binding_ids),
                "target_binding_ids": list(manifest.target_binding_ids),
                "native_receipt_ids": [
                    item.receipt_id for item in envelope.native_receipt_refs
                ],
                "native_verifier_result": dict(manifest.native_verifier_result),
            }
    elif query_kind == "behavior":
        candidates: list[Mapping[str, object]] = []
        if isinstance(composition_cases, list):
            candidates.extend(
                item for item in composition_cases if isinstance(item, Mapping)
            )
        for envelope in envelopes:
            candidates.extend(
                item.to_dict()
                for item in envelope.behavior_manifest.domain_behavior_cases
            )
            candidates.extend(
                item.to_dict() for item in envelope.behavior_manifest.integrity_cases
            )
        detail = next(
            (
                dict(item)
                for item in candidates
                if str(item.get("behavior_id", "")) == query_id
                or str(item.get("case_id", "")) == query_id
            ),
            None,
        )
    elif query_kind == "handoff":
        if isinstance(handoff_rows, list):
            detail = next(
                (
                    dict(item)
                    for item in handoff_rows
                    if isinstance(item, Mapping)
                    and (
                        str(item.get("handoff_id", "")) == query_id
                        or str(item.get("field_id", "")) == query_id
                    )
                ),
                None,
            )
    elif query_kind == "impact":
        detail = composition_impact(
            _portable_route_composition(composition_raw), [query_id]
        )
    elif query_kind == "reverse":
        try:
            detail = reverse_trace_composition(
                _portable_route_composition(composition_raw), query_id
            )
        except ValueError:
            detail = None
    if detail is None:
        summary["query_status"] = "not_found"
        summary["query_gap"] = {"code": "portable-query-object-not-found", "detail": query_id}
    else:
        summary["query_status"] = "found"
        summary["detail"] = detail
    return summary


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
    "composition_impact",
    "export_portable_composition_bundle",
    "create_handoff",
    "request_fingerprint",
    "reverse_trace_composition",
    "qualify_portable_composition_bundle",
    "project_portable_composition_bundle",
    "replay_composition_behavior_oracle",
    "select_member_request",
]
