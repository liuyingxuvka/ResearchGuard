"""Opaque, current-only transport contracts for ResearchGuard composition.

This module deliberately imports no member schema.  It validates transport
identity, freshness, handoff topology, and terminal visibility while treating
every member-native payload as uninterpreted bytes.
"""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
import hashlib
import importlib
import json
import re
from typing import Any, Iterable, Literal, Mapping, Sequence

from .native_receipts import NativeReceiptReference


MEMBER_MODEL_ENVELOPE_SCHEMA = "researchguard.member-model-envelope.v3"
NATIVE_OWNER_ATTESTATION_SCHEMA = "researchguard.native-owner-attestation.v2"
HANDOFF_FIELD_CONTRACT_SCHEMA = "researchguard.handoff-field-contract.v1"
BEHAVIOR_TRANSITION_CASE_SCHEMA = "researchguard.member-behavior-transition-case.v1"
MEMBER_BEHAVIOR_MANIFEST_SCHEMA = "researchguard.member-behavior-manifest.v1"
MEMBER_IDS = {"logicguard", "sourceguard", "traceguard", "experimentguard"}
TERMINAL_STATUSES = {
    "passed", "blocked", "failed", "stale", "skipped", "not_run", "non_terminal"
}
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def _digest(value: object) -> str:
    body = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _json_canonical(value: object) -> object:
    """Return the exact JSON value that survives a portable bundle round trip."""

    return json.loads(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    )


def payload_fingerprint(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _exact(raw: Mapping[str, object], allowed: set[str], where: str) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ValueError(f"{where} contains unknown current fields: {unknown!r}")


def _text(value: object, where: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{where} is required")
    return result


def _sha(value: object, where: str) -> str:
    result = _text(value, where)
    if not _SHA256.fullmatch(result):
        raise ValueError(f"{where} must be an exact sha256 fingerprint")
    return result


def _rows(value: object, where: str) -> Sequence[Mapping[str, object]]:
    if not isinstance(value, list):
        raise ValueError(f"{where} must be an array")
    result: list[Mapping[str, object]] = []
    for index, row in enumerate(value):
        if not isinstance(row, Mapping):
            raise ValueError(f"{where}[{index}] must be an object")
        result.append(row)
    return result


def _ids(value: object, where: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{where} must be an array")
    result = tuple(_text(item, where) for item in value)
    if len(result) != len(set(result)):
        raise ValueError(f"{where} must contain unique ids")
    return result


@dataclass(frozen=True)
class BehaviorTransitionCase:
    case_id: str
    behavior_id: str
    input: Mapping[str, object]
    pre_state: Mapping[str, object]
    permitted_output: Mapping[str, object]
    post_state: Mapping[str, object]
    effect: tuple[str, ...]
    protected_failure: str
    oracle: Mapping[str, object]
    schema_version: str = BEHAVIOR_TRANSITION_CASE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != BEHAVIOR_TRANSITION_CASE_SCHEMA:
            raise ValueError("member behavior case requires the current schema")
        _text(self.case_id, "member behavior case id")
        _text(self.behavior_id, "member behavior id")
        for name in ("input", "pre_state", "permitted_output", "post_state", "oracle"):
            value = getattr(self, name)
            if not isinstance(value, Mapping) or not value:
                raise ValueError(f"member behavior case {name} must be a non-empty object")
            json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        if not self.effect or len(self.effect) != len(set(self.effect)):
            raise ValueError("member behavior case effect must be non-empty and unique")
        if any(not str(item).strip() for item in self.effect):
            raise ValueError("member behavior case effect contains an empty value")
        _text(self.protected_failure, "member behavior protected failure")
        required_oracle = {
            "owner",
            "entrypoint",
            "checker_id",
            "checker_version",
            "result_fingerprint",
            "native_receipt_id",
            "good_case",
            "bad_case",
        }
        if set(self.oracle) != required_oracle:
            raise ValueError("member behavior case oracle is incomplete or foreign")
        _sha(self.oracle["result_fingerprint"], "member behavior oracle result fingerprint")
        good = self.oracle["good_case"]
        bad = self.oracle["bad_case"]
        if not isinstance(good, Mapping) or set(good) != {
            "transition_fingerprint",
            "expected_status",
            "native_evidence",
        }:
            raise ValueError("member behavior good oracle is incomplete or foreign")
        if not isinstance(bad, Mapping) or set(bad) != {
            "mutation_path",
            "mutation_operator",
            "expected_status",
            "expected_failure",
            "failure_class_id",
            "native_evidence",
        }:
            raise ValueError("member behavior bad oracle is incomplete or foreign")
        if _sha(
            good["transition_fingerprint"],
            "member behavior good transition fingerprint",
        ) != self.transition_fingerprint or good["expected_status"] != "passed":
            raise ValueError("member behavior good oracle does not bind the transition")
        if bad["expected_status"] != "blocked" or bad["expected_failure"] != self.protected_failure:
            raise ValueError("member behavior bad oracle does not bind the protected failure")
        _text(bad["mutation_path"], "member behavior bad mutation path")
        _text(bad["mutation_operator"], "member behavior bad mutation operator")
        _text(bad["failure_class_id"], "member behavior bad failure class")
        if not isinstance(good["native_evidence"], Mapping) or not good["native_evidence"]:
            raise ValueError("member behavior good native evidence is empty")
        if not isinstance(bad["native_evidence"], Mapping) or not bad["native_evidence"]:
            raise ValueError("member behavior bad native evidence is empty")

    @property
    def transition_payload(self) -> dict[str, object]:
        return {
            "input": dict(self.input),
            "pre_state": dict(self.pre_state),
            "permitted_output": dict(self.permitted_output),
            "post_state": dict(self.post_state),
            "effect": list(self.effect),
        }

    @property
    def transition_fingerprint(self) -> str:
        return _digest(self.transition_payload)

    @property
    def case_fingerprint(self) -> str:
        return _digest(self.to_dict(include_fingerprint=False))

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "BehaviorTransitionCase":
        fields = {
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
            "case_fingerprint",
        }
        if set(raw) != fields:
            raise ValueError("member behavior case contains unknown or missing fields")
        if any(not isinstance(raw.get(name), Mapping) for name in (
            "input", "pre_state", "permitted_output", "post_state", "oracle"
        )):
            raise ValueError("member behavior case objects are invalid")
        case = cls(
            schema_version=str(raw.get("schema_version", "")),
            case_id=_text(raw.get("case_id"), "member behavior case id"),
            behavior_id=_text(raw.get("behavior_id"), "member behavior id"),
            input=dict(raw["input"]),  # type: ignore[arg-type]
            pre_state=dict(raw["pre_state"]),  # type: ignore[arg-type]
            permitted_output=dict(raw["permitted_output"]),  # type: ignore[arg-type]
            post_state=dict(raw["post_state"]),  # type: ignore[arg-type]
            effect=_ids(raw.get("effect"), "member behavior effects"),
            protected_failure=_text(
                raw.get("protected_failure"), "member behavior protected failure"
            ),
            oracle=dict(raw["oracle"]),  # type: ignore[arg-type]
        )
        if _sha(raw.get("case_fingerprint"), "member behavior case fingerprint") != case.case_fingerprint:
            raise ValueError("member behavior case fingerprint is stale or foreign")
        return case

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, object]:
        result: dict[str, object] = {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "behavior_id": self.behavior_id,
            "input": dict(self.input),
            "pre_state": dict(self.pre_state),
            "permitted_output": dict(self.permitted_output),
            "post_state": dict(self.post_state),
            "effect": list(self.effect),
            "protected_failure": self.protected_failure,
            "oracle": dict(self.oracle),
        }
        if include_fingerprint:
            result["case_fingerprint"] = self.case_fingerprint
        return result


@dataclass(frozen=True)
class MemberBehaviorManifest:
    member_id: str
    native_model_id: str
    model_fingerprint: str
    expected_target_anchor_id: str
    expected_target_anchor_fingerprint: str
    domain_behavior_denominator_ids: tuple[str, ...]
    hierarchy_node_ids: tuple[str, ...]
    interface_binding_ids: tuple[str, ...]
    target_binding_ids: tuple[str, ...]
    native_receipt_expectations: tuple[Mapping[str, str], ...]
    domain_behavior_cases: tuple[BehaviorTransitionCase, ...]
    integrity_case_ids: tuple[str, ...]
    integrity_cases: tuple[BehaviorTransitionCase, ...]
    native_verifier_result: Mapping[str, object]
    manifest_id: str = ""
    manifest_fingerprint: str = ""
    schema_version: str = MEMBER_BEHAVIOR_MANIFEST_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != MEMBER_BEHAVIOR_MANIFEST_SCHEMA:
            raise ValueError("member behavior manifest requires the current schema")
        if self.member_id not in MEMBER_IDS:
            raise ValueError("member behavior manifest has an unknown member")
        _text(self.native_model_id, "member behavior native model id")
        _sha(self.model_fingerprint, "member behavior model fingerprint")
        _text(self.expected_target_anchor_id, "member behavior target anchor id")
        _sha(
            self.expected_target_anchor_fingerprint,
            "member behavior target anchor fingerprint",
        )
        if (
            not self.domain_behavior_denominator_ids
            or not self.hierarchy_node_ids
            or not self.interface_binding_ids
            or not self.target_binding_ids
        ):
            raise ValueError("member behavior manifest denominators are incomplete")
        for values, label in (
            (self.domain_behavior_denominator_ids, "domain behavior"),
            (self.integrity_case_ids, "integrity case"),
            (self.hierarchy_node_ids, "hierarchy"),
            (self.interface_binding_ids, "interface"),
            (self.target_binding_ids, "target binding"),
        ):
            if len(values) != len(set(values)) or any(not str(item).strip() for item in values):
                raise ValueError(f"member behavior {label} denominator is invalid")
        if not self.native_receipt_expectations:
            raise ValueError("member behavior manifest requires native receipt linkage")
        expected_receipt_fields = {
            "receipt_id",
            "checker_id",
            "checker_version",
            "result_fingerprint",
        }
        for item in self.native_receipt_expectations:
            if set(item) != expected_receipt_fields:
                raise ValueError("member behavior receipt linkage is incomplete or foreign")
            _text(item["receipt_id"], "member behavior receipt id")
            _text(item["checker_id"], "member behavior receipt checker")
            _text(item["checker_version"], "member behavior receipt checker version")
            _sha(item["result_fingerprint"], "member behavior receipt result fingerprint")
        if {item.behavior_id for item in self.domain_behavior_cases} != set(
            self.domain_behavior_denominator_ids
        ) or len(self.domain_behavior_cases) != len(self.domain_behavior_denominator_ids):
            raise ValueError("member domain behavior cases do not cover the declared denominator")
        if {item.behavior_id for item in self.integrity_cases} != set(
            self.integrity_case_ids
        ) or len(self.integrity_cases) != len(self.integrity_case_ids):
            raise ValueError("member integrity cases do not cover the declared denominator")
        if set(self.domain_behavior_denominator_ids).intersection(self.integrity_case_ids):
            raise ValueError("member domain behaviors and integrity cases must stay separate")
        verifier_fields = {
            "checker_id",
            "checker_version",
            "checker_entrypoint",
            "result_fingerprint",
            "terminal_status",
            "status",
        }
        if set(self.native_verifier_result) != verifier_fields:
            raise ValueError("member behavior verifier result is incomplete or foreign")
        _sha(
            self.native_verifier_result["result_fingerprint"],
            "member behavior verifier result fingerprint",
        )
        verifier_status = str(self.native_verifier_result["status"])
        terminal_status = str(self.native_verifier_result["terminal_status"])
        if verifier_status not in {"passed", "blocked"}:
            raise ValueError("member behavior verifier result has an invalid status")
        if terminal_status not in TERMINAL_STATUSES:
            raise ValueError("member behavior verifier terminal is not current")
        if (verifier_status == "passed") != (terminal_status == "passed"):
            raise ValueError("member behavior verifier status and terminal disagree")
        if self.manifest_fingerprint:
            _sha(self.manifest_fingerprint, "member behavior manifest fingerprint")
            if self.manifest_fingerprint != self.expected_fingerprint:
                raise ValueError("member behavior manifest fingerprint is stale or foreign")
        if self.manifest_id and self.manifest_id != self.expected_id:
            raise ValueError("member behavior manifest id is stale or foreign")

    @property
    def core(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "member_id": self.member_id,
            "native_model_id": self.native_model_id,
            "model_fingerprint": self.model_fingerprint,
            "expected_target_anchor_id": self.expected_target_anchor_id,
            "expected_target_anchor_fingerprint": self.expected_target_anchor_fingerprint,
            "domain_behavior_denominator_ids": list(self.domain_behavior_denominator_ids),
            "hierarchy_node_ids": list(self.hierarchy_node_ids),
            "interface_binding_ids": list(self.interface_binding_ids),
            "target_binding_ids": list(self.target_binding_ids),
            "native_receipt_expectations": [
                dict(item) for item in self.native_receipt_expectations
            ],
            "domain_behavior_cases": [item.to_dict() for item in self.domain_behavior_cases],
            "integrity_case_ids": list(self.integrity_case_ids),
            "integrity_cases": [item.to_dict() for item in self.integrity_cases],
            "native_verifier_result": dict(self.native_verifier_result),
        }

    @property
    def expected_fingerprint(self) -> str:
        return _digest(self.core)

    @property
    def expected_id(self) -> str:
        return (
            f"member-behavior-manifest:{self.member_id}:"
            + self.expected_fingerprint.removeprefix("sha256:")
        )

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "MemberBehaviorManifest":
        fields = {
            "schema_version",
            "manifest_id",
            "manifest_fingerprint",
            "member_id",
            "native_model_id",
            "model_fingerprint",
            "expected_target_anchor_id",
            "expected_target_anchor_fingerprint",
            "domain_behavior_denominator_ids",
            "hierarchy_node_ids",
            "interface_binding_ids",
            "target_binding_ids",
            "native_receipt_expectations",
            "domain_behavior_cases",
            "integrity_case_ids",
            "integrity_cases",
            "native_verifier_result",
        }
        if set(raw) != fields:
            raise ValueError("member behavior manifest contains unknown or missing fields")
        receipt_rows = _rows(
            raw.get("native_receipt_expectations"),
            "member behavior receipt expectations",
        )
        manifest = cls(
            schema_version=str(raw.get("schema_version", "")),
            manifest_id=_text(raw.get("manifest_id"), "member behavior manifest id"),
            manifest_fingerprint=_sha(
                raw.get("manifest_fingerprint"),
                "member behavior manifest fingerprint",
            ),
            member_id=str(raw.get("member_id", "")),
            native_model_id=_text(raw.get("native_model_id"), "member behavior native model"),
            model_fingerprint=_sha(raw.get("model_fingerprint"), "member behavior model fingerprint"),
            expected_target_anchor_id=_text(
                raw.get("expected_target_anchor_id"), "member behavior target anchor"
            ),
            expected_target_anchor_fingerprint=_sha(
                raw.get("expected_target_anchor_fingerprint"),
                "member behavior target anchor fingerprint",
            ),
            domain_behavior_denominator_ids=_ids(
                raw.get("domain_behavior_denominator_ids"), "member domain behavior denominator"
            ),
            hierarchy_node_ids=_ids(
                raw.get("hierarchy_node_ids"), "member behavior hierarchy denominator"
            ),
            interface_binding_ids=_ids(
                raw.get("interface_binding_ids"), "member behavior interface denominator"
            ),
            target_binding_ids=_ids(
                raw.get("target_binding_ids"), "member behavior target denominator"
            ),
            native_receipt_expectations=tuple(
                {str(key): str(value) for key, value in item.items()}
                for item in receipt_rows
            ),
            domain_behavior_cases=tuple(
                BehaviorTransitionCase.from_dict(item)
                for item in _rows(raw.get("domain_behavior_cases"), "member domain behavior cases")
            ),
            integrity_case_ids=_ids(
                raw.get("integrity_case_ids"), "member integrity case denominator"
            ),
            integrity_cases=tuple(
                BehaviorTransitionCase.from_dict(item)
                for item in _rows(raw.get("integrity_cases"), "member integrity cases")
            ),
            native_verifier_result=dict(
                raw.get("native_verifier_result")  # type: ignore[arg-type]
                if isinstance(raw.get("native_verifier_result"), Mapping)
                else {}
            ),
        )
        return manifest

    def to_dict(self) -> dict[str, object]:
        return {
            **self.core,
            "manifest_id": self.expected_id,
            "manifest_fingerprint": self.expected_fingerprint,
        }


def build_behavior_transition_case(
    *,
    case_id: str,
    behavior_id: str,
    input: Mapping[str, object],
    pre_state: Mapping[str, object],
    permitted_output: Mapping[str, object],
    post_state: Mapping[str, object],
    effect: Iterable[str],
    protected_failure: str,
    owner: str,
    checker_entrypoint: str,
    checker_id: str,
    checker_version: str,
    result_fingerprint: str,
    native_receipt_id: str,
    bad_mutation_path: str,
    bad_mutation_operator: str = "replace_with_foreign_value",
    failure_class_id: str = "transition-semantic-mismatch",
    good_native_evidence: Mapping[str, object] | None = None,
    bad_native_evidence: Mapping[str, object] | None = None,
) -> BehaviorTransitionCase:
    """Build one executable good/bad transition oracle from native semantics."""

    effects = tuple(str(item) for item in effect)
    canonical_input = _json_canonical(dict(input))
    canonical_pre_state = _json_canonical(dict(pre_state))
    canonical_output = _json_canonical(dict(permitted_output))
    canonical_post_state = _json_canonical(dict(post_state))
    if not all(
        isinstance(item, Mapping)
        for item in (
            canonical_input,
            canonical_pre_state,
            canonical_output,
            canonical_post_state,
        )
    ):
        raise ValueError("behavior transition values must be JSON objects")
    transition = {
        "input": canonical_input,
        "pre_state": canonical_pre_state,
        "permitted_output": canonical_output,
        "post_state": canonical_post_state,
        "effect": list(effects),
    }
    oracle = {
        "owner": owner,
        "entrypoint": checker_entrypoint,
        "checker_id": checker_id,
        "checker_version": checker_version,
        "result_fingerprint": result_fingerprint,
        "native_receipt_id": native_receipt_id,
        "good_case": {
            "transition_fingerprint": _digest(transition),
            "expected_status": "passed",
            "native_evidence": _json_canonical(
                dict(good_native_evidence or {"kind": "transport-integrity-good"})
            ),
        },
        "bad_case": {
            "mutation_path": bad_mutation_path,
            "mutation_operator": bad_mutation_operator,
            "expected_status": "blocked",
            "expected_failure": protected_failure,
            "failure_class_id": failure_class_id,
            "native_evidence": _json_canonical(
                dict(bad_native_evidence or {"kind": "transport-integrity-bad"})
            ),
        },
    }
    return BehaviorTransitionCase(
        case_id=case_id,
        behavior_id=behavior_id,
        input=canonical_input,
        pre_state=canonical_pre_state,
        permitted_output=canonical_output,
        post_state=canonical_post_state,
        effect=effects,
        protected_failure=protected_failure,
        oracle=oracle,
    )


def replay_behavior_transition_oracle(
    envelope: "MemberModelEnvelope",
    case: BehaviorTransitionCase,
    candidate_transition: Mapping[str, object],
) -> dict[str, str]:
    """Dispatch an executable domain replay to the manifest's native owner."""

    if case not in envelope.behavior_manifest.domain_behavior_cases:
        raise ValueError("domain behavior case is not owned by the envelope manifest")
    module_name = {
        "sourceguard": "researchguard.source.owner_attestation",
        "traceguard": "researchguard.trace.owner_attestation",
        "logicguard": "researchguard.logic.owner_attestation",
        "experimentguard": "researchguard.experiment.owner_attestation",
    }[envelope.member_id]
    evaluator = getattr(
        importlib.import_module(module_name), "evaluate_domain_behavior_transition"
    )
    return evaluator(envelope, case.behavior_id, candidate_transition)


def _compare_native_domain_transition(
    canonical: BehaviorTransitionCase,
    candidate_transition: Mapping[str, object],
) -> dict[str, str]:
    """Member-owner helper after that owner has rerun native domain semantics."""

    candidate = dict(candidate_transition)
    candidate_fingerprint = _digest(candidate)
    if candidate == canonical.transition_payload:
        return {
            "status": "passed",
            "behavior_id": canonical.behavior_id,
            "transition_fingerprint": candidate_fingerprint,
            "failure": "",
        }
    return {
        "status": "blocked",
        "behavior_id": canonical.behavior_id,
        "transition_fingerprint": candidate_fingerprint,
        "failure": canonical.protected_failure,
    }


def build_member_behavior_manifest(
    *,
    member_id: str,
    native_model_id: str,
    model_fingerprint: str,
    expected_target_anchor_id: str,
    expected_target_anchor_fingerprint: str,
    hierarchy_node_ids: Iterable[str],
    interface_binding_ids: Iterable[str],
    target_binding_ids: Iterable[str],
    native_receipt_ids: Iterable[str],
    domain_behavior_cases: Iterable[BehaviorTransitionCase],
    checker_id: str,
    checker_version: str,
    checker_entrypoint: str,
    result_fingerprint: str,
    terminal_status: str,
) -> MemberBehaviorManifest:
    """Build the canonical member-owned behavior denominator carrier."""

    hierarchy = tuple(sorted(set(str(item) for item in hierarchy_node_ids)))
    interfaces = tuple(sorted(set(str(item) for item in interface_binding_ids)))
    targets = tuple(sorted(set(str(item) for item in target_binding_ids)))
    receipt_ids = tuple(sorted(set(str(item) for item in native_receipt_ids)))
    domain_cases = tuple(domain_behavior_cases)
    if not hierarchy or not interfaces or not targets or not receipt_ids or not domain_cases:
        raise ValueError("member behavior manifest inputs are incomplete")
    definitions = tuple(
        (
            f"{member_id}.hierarchy:{object_id}",
            {"hierarchy_node_id": object_id},
            ["replay_native_hierarchy", "verify_complete_hierarchy_denominator"],
            "missing, foreign, duplicate, or cyclic hierarchy ownership",
        )
        for object_id in hierarchy
    ) + tuple(
        (
            f"{member_id}.interface:{object_id}",
            {"interface_binding_id": object_id},
            ["replay_native_interfaces", "verify_parent_consumes_child_outputs"],
            "missing producer, consumer, schema, or acknowledgement linkage",
        )
        for object_id in interfaces
    ) + tuple(
        (
            f"{member_id}.target-binding:{object_id}",
            {"target_binding_id": object_id},
            ["replay_expected_target", "verify_independent_target_denominator"],
            "missing or changed externally admitted target binding",
        )
        for object_id in targets
    ) + tuple(
        (
            f"{member_id}.native-receipt:{object_id}",
            {"native_receipt_id": object_id},
            ["resolve_immutable_native_receipts", "verify_exact_native_result"],
            "unresolved, foreign, stale, or differently produced native receipt",
        )
        for object_id in receipt_ids
    )
    integrity_cases = tuple(
        build_behavior_transition_case(
            case_id=f"case:{behavior_id}",
            behavior_id=behavior_id,
            input={
                "native_model_id": native_model_id,
                "model_fingerprint": model_fingerprint,
                "expected_target_anchor_id": expected_target_anchor_id,
                "expected_target_anchor_fingerprint": expected_target_anchor_fingerprint,
                **denominator,
            },
            pre_state={
                "verification_status": "not_run",
                "terminal_status": "not_run",
            },
            permitted_output={
                "verification_status": (
                    "passed" if terminal_status == "passed" else "blocked"
                ),
                "terminal_status": terminal_status,
                "result_fingerprint": result_fingerprint,
                **denominator,
            },
            post_state={
                "verification_status": (
                    "passed" if terminal_status == "passed" else "blocked"
                ),
                "terminal_status": terminal_status,
                "model_fingerprint": model_fingerprint,
            },
            effect=tuple(effects),
            protected_failure=failure,
            owner=member_id,
            checker_entrypoint=checker_entrypoint,
            checker_id=checker_id,
            checker_version=checker_version,
            result_fingerprint=result_fingerprint,
            native_receipt_id=receipt_ids[0],
            bad_mutation_path=next(iter(denominator)),
        )
        for behavior_id, denominator, effects, failure in definitions
    )
    receipt_expectations = tuple(
        {
            "receipt_id": receipt_id,
            "checker_id": checker_id,
            "checker_version": checker_version,
            "result_fingerprint": result_fingerprint,
        }
        for receipt_id in receipt_ids
    )
    return MemberBehaviorManifest(
        member_id=member_id,
        native_model_id=native_model_id,
        model_fingerprint=model_fingerprint,
        expected_target_anchor_id=expected_target_anchor_id,
        expected_target_anchor_fingerprint=expected_target_anchor_fingerprint,
        domain_behavior_denominator_ids=tuple(item.behavior_id for item in domain_cases),
        hierarchy_node_ids=hierarchy,
        interface_binding_ids=interfaces,
        target_binding_ids=targets,
        native_receipt_expectations=receipt_expectations,
        domain_behavior_cases=domain_cases,
        integrity_case_ids=tuple(item.behavior_id for item in integrity_cases),
        integrity_cases=integrity_cases,
        native_verifier_result={
            "checker_id": checker_id,
            "checker_version": checker_version,
            "checker_entrypoint": checker_entrypoint,
            "result_fingerprint": result_fingerprint,
            "terminal_status": terminal_status,
            "status": "passed" if terminal_status == "passed" else "blocked",
        },
    )


@dataclass(frozen=True)
class NativeOwnerAttestation:
    """Minimal opaque proof emitted outside the caller-authored composition.

    ResearchGuard may compare this transport record with its frozen member
    registry and with a member envelope.  It deliberately cannot interpret the
    member's native model or decide whether its domain result is correct.
    """

    attestation_id: str
    member_id: str
    native_owner_id: str
    checker_id: str
    checker_version: str
    registry_identity: str
    task_id: str
    envelope_id: str
    envelope_fingerprint: str
    native_model_id: str
    model_fingerprint: str
    expected_target_anchor_id: str
    expected_target_anchor_fingerprint: str
    request_fingerprint: str
    input_fingerprint: str
    result_fingerprint: str
    native_receipt_refs: tuple[NativeReceiptReference, ...]
    terminal_status: Literal[
        "passed", "blocked", "failed", "stale", "skipped", "not_run", "non_terminal"
    ]
    schema_version: str = NATIVE_OWNER_ATTESTATION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != NATIVE_OWNER_ATTESTATION_SCHEMA:
            raise ValueError("native owner attestation requires the current schema")
        for name in (
            "attestation_id", "native_owner_id", "checker_id", "checker_version",
            "task_id", "envelope_id", "native_model_id",
            "expected_target_anchor_id",
        ):
            _text(getattr(self, name), f"native owner attestation {name}")
        if self.member_id not in MEMBER_IDS:
            raise ValueError(f"native owner attestation has unknown member_id {self.member_id!r}")
        _sha(self.registry_identity, "native owner attestation registry identity")
        _sha(self.envelope_fingerprint, "native owner attestation envelope fingerprint")
        _sha(self.model_fingerprint, "native owner attestation model fingerprint")
        _sha(
            self.expected_target_anchor_fingerprint,
            "native owner attestation expected target anchor fingerprint",
        )
        _sha(self.request_fingerprint, "native owner attestation request fingerprint")
        _sha(self.input_fingerprint, "native owner attestation input fingerprint")
        _sha(self.result_fingerprint, "native owner attestation result fingerprint")
        if not self.native_receipt_refs:
            raise ValueError("native owner attestation requires at least one native receipt")
        if any(item.task_id != self.task_id for item in self.native_receipt_refs):
            raise ValueError("native owner attestation receipt lineage is stale or foreign")
        if len({item.receipt_id for item in self.native_receipt_refs}) != len(self.native_receipt_refs):
            raise ValueError("native owner attestation receipt ids must be unique")
        if any(
            item.expected_target_anchor_id != self.expected_target_anchor_id
            or item.expected_target_anchor_fingerprint
            != self.expected_target_anchor_fingerprint
            or item.native_model_id != self.native_model_id
            or item.model_fingerprint != self.model_fingerprint
            or item.member_id != self.member_id
            for item in self.native_receipt_refs
        ):
            raise ValueError("native owner attestation receipt authority is stale or foreign")
        if self.terminal_status not in TERMINAL_STATUSES:
            raise ValueError("native owner attestation terminal status is not current")

    @property
    def attestation_fingerprint(self) -> str:
        return _digest(self.to_dict(include_fingerprint=False))

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "NativeOwnerAttestation":
        _exact(
            raw,
            {
                "schema_version", "attestation_id", "member_id", "native_owner_id",
                "checker_id", "checker_version",
                "registry_identity", "task_id", "envelope_id", "envelope_fingerprint",
                "native_model_id", "model_fingerprint", "native_receipt_refs",
                "expected_target_anchor_id", "expected_target_anchor_fingerprint",
                "request_fingerprint", "input_fingerprint", "result_fingerprint",
                "terminal_status", "attestation_fingerprint",
            },
            "native owner attestation",
        )
        attestation = cls(
            schema_version=str(raw.get("schema_version", "")),
            attestation_id=_text(raw.get("attestation_id"), "native owner attestation id"),
            member_id=str(raw.get("member_id", "")),
            native_owner_id=_text(raw.get("native_owner_id"), "native owner attestation owner"),
            checker_id=_text(raw.get("checker_id"), "native owner attestation checker"),
            checker_version=_text(raw.get("checker_version"), "native owner attestation checker version"),
            registry_identity=_sha(raw.get("registry_identity"), "native owner attestation registry identity"),
            task_id=_text(raw.get("task_id"), "native owner attestation task id"),
            envelope_id=_text(raw.get("envelope_id"), "native owner attestation envelope id"),
            envelope_fingerprint=_sha(raw.get("envelope_fingerprint"), "native owner attestation envelope fingerprint"),
            native_model_id=_text(raw.get("native_model_id"), "native owner attestation model id"),
            model_fingerprint=_sha(raw.get("model_fingerprint"), "native owner attestation model fingerprint"),
            expected_target_anchor_id=_text(
                raw.get("expected_target_anchor_id"),
                "native owner attestation expected target anchor id",
            ),
            expected_target_anchor_fingerprint=_sha(
                raw.get("expected_target_anchor_fingerprint"),
                "native owner attestation expected target anchor fingerprint",
            ),
            request_fingerprint=_sha(raw.get("request_fingerprint"), "native owner attestation request fingerprint"),
            input_fingerprint=_sha(raw.get("input_fingerprint"), "native owner attestation input fingerprint"),
            result_fingerprint=_sha(raw.get("result_fingerprint"), "native owner attestation result fingerprint"),
            native_receipt_refs=tuple(
                NativeReceiptReference.from_dict(item)
                for item in _rows(raw.get("native_receipt_refs"), "native owner attestation receipts")
            ),
            terminal_status=str(raw.get("terminal_status", "")),  # type: ignore[arg-type]
        )
        supplied = _sha(raw.get("attestation_fingerprint"), "native owner attestation fingerprint")
        if supplied != attestation.attestation_fingerprint:
            raise ValueError("native owner attestation fingerprint is stale or foreign")
        return attestation

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, object]:
        result: dict[str, object] = {
            "schema_version": self.schema_version,
            "attestation_id": self.attestation_id,
            "member_id": self.member_id,
            "native_owner_id": self.native_owner_id,
            "checker_id": self.checker_id,
            "checker_version": self.checker_version,
            "registry_identity": self.registry_identity,
            "task_id": self.task_id,
            "envelope_id": self.envelope_id,
            "envelope_fingerprint": self.envelope_fingerprint,
            "native_model_id": self.native_model_id,
            "model_fingerprint": self.model_fingerprint,
            "expected_target_anchor_id": self.expected_target_anchor_id,
            "expected_target_anchor_fingerprint": self.expected_target_anchor_fingerprint,
            "request_fingerprint": self.request_fingerprint,
            "input_fingerprint": self.input_fingerprint,
            "result_fingerprint": self.result_fingerprint,
            "native_receipt_refs": [item.to_dict() for item in self.native_receipt_refs],
            "terminal_status": self.terminal_status,
        }
        if include_fingerprint:
            result["attestation_fingerprint"] = self.attestation_fingerprint
        return result


def _issue_replayed_native_owner_attestation(
    envelope: "MemberModelEnvelope",
    *,
    native_owner_id: str,
    checker_id: str,
    checker_version: str,
    registry_identity: str,
    request_fingerprint: str,
    input_fingerprint: str,
    result_fingerprint: str,
) -> NativeOwnerAttestation:
    """Internal carrier issuer called only after a member-native replay passes.

    The public generic self-signing entry intentionally does not exist.  Each
    registered member parser must first replay its opaque input, result, and
    exact receipt identities, then call this private transport constructor.
    """

    owner = _text(native_owner_id, "native owner id")
    checker = _text(checker_id, "native owner checker id")
    version = _text(checker_version, "native owner checker version")
    registry = _sha(registry_identity, "native owner registry identity")
    request = _sha(request_fingerprint, "native owner request fingerprint")
    input_value = _sha(input_fingerprint, "native owner input fingerprint")
    result = _sha(result_fingerprint, "native owner result fingerprint")
    material = {
        "member_id": envelope.member_id,
        "native_owner_id": owner,
        "checker_id": checker,
        "checker_version": version,
        "registry_identity": registry,
        "task_id": envelope.task_id,
        "envelope_fingerprint": envelope.envelope_fingerprint,
        "request_fingerprint": request,
        "input_fingerprint": input_value,
        "result_fingerprint": result,
    }
    suffix = _digest(material)[7:31]
    return NativeOwnerAttestation(
        attestation_id=f"native-attestation:{envelope.member_id}:{suffix}",
        member_id=envelope.member_id,
        native_owner_id=owner,
        checker_id=checker,
        checker_version=version,
        registry_identity=registry,
        task_id=envelope.task_id,
        envelope_id=envelope.envelope_id,
        envelope_fingerprint=envelope.envelope_fingerprint,
        native_model_id=envelope.native_model_id,
        model_fingerprint=envelope.model_fingerprint,
        expected_target_anchor_id=envelope.expected_target_anchor_id,
        expected_target_anchor_fingerprint=envelope.expected_target_anchor_fingerprint,
        request_fingerprint=request,
        input_fingerprint=input_value,
        result_fingerprint=result,
        native_receipt_refs=envelope.native_receipt_refs,
        terminal_status=envelope.terminal_status,
    )


@dataclass(frozen=True)
class ResponsibilitySpan:
    source_id: str
    start: int
    end: int
    quote: str

    def __post_init__(self) -> None:
        _text(self.source_id, "responsibility span source_id")
        if self.start < 0 or self.end <= self.start or len(self.quote) != self.end - self.start:
            raise ValueError("responsibility span must bind exact source offsets and quote")

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "ResponsibilitySpan":
        _exact(raw, {"source_id", "start", "end", "quote"}, "responsibility span")
        if not isinstance(raw.get("start"), int) or not isinstance(raw.get("end"), int):
            raise ValueError("responsibility span offsets must be integers")
        return cls(
            source_id=_text(raw.get("source_id"), "responsibility span source_id"),
            start=int(raw["start"]),
            end=int(raw["end"]),
            quote=str(raw.get("quote", "")),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MemberModelEnvelope:
    envelope_id: str
    task_id: str
    member_id: str
    native_model_id: str
    native_schema_id: str
    native_schema_version: str
    model_fingerprint: str
    expected_target_anchor_id: str
    expected_target_anchor_fingerprint: str
    payload_fingerprint: str
    input_field_ids: tuple[str, ...]
    output_field_ids: tuple[str, ...]
    native_receipt_refs: tuple[NativeReceiptReference, ...]
    behavior_manifest: MemberBehaviorManifest
    open_gap_refs: tuple[str, ...]
    terminal_status: Literal[
        "passed", "blocked", "failed", "stale", "skipped", "not_run", "non_terminal"
    ]
    claim_boundary: str
    responsibility_spans: tuple[ResponsibilitySpan, ...]
    opaque_payload: bytes | None = None
    schema_version: str = MEMBER_MODEL_ENVELOPE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != MEMBER_MODEL_ENVELOPE_SCHEMA:
            raise ValueError("member envelope requires the current schema")
        for name in (
            "envelope_id", "task_id", "native_model_id", "native_schema_id",
            "native_schema_version", "claim_boundary",
            "expected_target_anchor_id",
        ):
            _text(getattr(self, name), f"member envelope {name}")
        if self.member_id not in MEMBER_IDS:
            raise ValueError(f"member envelope has unknown member_id {self.member_id!r}")
        _sha(self.model_fingerprint, "member envelope model_fingerprint")
        _sha(
            self.expected_target_anchor_fingerprint,
            "member envelope expected target anchor fingerprint",
        )
        _sha(self.payload_fingerprint, "member envelope payload_fingerprint")
        if self.opaque_payload is not None and payload_fingerprint(self.opaque_payload) != self.payload_fingerprint:
            raise ValueError("member envelope opaque payload digest mismatch")
        if not self.native_receipt_refs:
            raise ValueError("member envelope requires at least one native receipt reference")
        if any(item.task_id != self.task_id for item in self.native_receipt_refs):
            raise ValueError("member envelope receipt lineage must stay in one task")
        if len({item.receipt_id for item in self.native_receipt_refs}) != len(self.native_receipt_refs):
            raise ValueError("member envelope native receipt ids must be unique")
        if any(
            item.member_id != self.member_id
            or item.native_model_id != self.native_model_id
            or item.model_fingerprint != self.model_fingerprint
            or item.expected_target_anchor_id != self.expected_target_anchor_id
            or item.expected_target_anchor_fingerprint
            != self.expected_target_anchor_fingerprint
            for item in self.native_receipt_refs
        ):
            raise ValueError("member envelope native receipt authority is stale or foreign")
        manifest = self.behavior_manifest
        if (
            manifest.member_id != self.member_id
            or manifest.native_model_id != self.native_model_id
            or manifest.model_fingerprint != self.model_fingerprint
            or manifest.expected_target_anchor_id != self.expected_target_anchor_id
            or manifest.expected_target_anchor_fingerprint
            != self.expected_target_anchor_fingerprint
        ):
            raise ValueError("member behavior manifest authority is stale or foreign")
        receipt_links = {
            (
                item.receipt_id,
                item.checker_id,
                item.checker_version,
                item.result_fingerprint,
            )
            for item in self.native_receipt_refs
        }
        manifest_links = {
            (
                str(item["receipt_id"]),
                str(item["checker_id"]),
                str(item["checker_version"]),
                str(item["result_fingerprint"]),
            )
            for item in manifest.native_receipt_expectations
        }
        if manifest_links != receipt_links:
            raise ValueError("member behavior manifest receipt linkage is incomplete or foreign")
        manifest_receipts = tuple(
            item
            for item in self.native_receipt_refs
            if item.native_owner_id == self.member_id
            and item.checker_id == str(manifest.native_verifier_result["checker_id"])
            and item.checker_version
            == str(manifest.native_verifier_result["checker_version"])
        )
        if len(manifest_receipts) != 1 or manifest_receipts[0].behavior_manifest_fingerprint != manifest.expected_fingerprint:
            raise ValueError(
                "member behavior manifest is not bound by one exact native producer receipt"
            )
        if len(set(self.input_field_ids)) != len(self.input_field_ids) or len(set(self.output_field_ids)) != len(self.output_field_ids):
            raise ValueError("member envelope input/output field ids must be unique")
        if self.terminal_status not in TERMINAL_STATUSES:
            raise ValueError("member envelope terminal status is not current")
        if self.terminal_status == "passed" and self.open_gap_refs:
            raise ValueError("passed member envelope cannot retain open gaps")
        if self.terminal_status != "passed" and not self.open_gap_refs:
            raise ValueError("non-passed member envelope must preserve at least one open gap")
        if not self.responsibility_spans:
            raise ValueError("member envelope requires a source-bound responsibility span")

    @property
    def envelope_fingerprint(self) -> str:
        return _digest(self.to_dict(include_payload=False, include_fingerprint=False))

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "MemberModelEnvelope":
        _exact(
            raw,
            {
                "schema_version", "envelope_id", "task_id", "member_id", "native_model_id",
                "native_schema_id", "native_schema_version", "model_fingerprint",
                "expected_target_anchor_id", "expected_target_anchor_fingerprint",
                "payload_fingerprint", "opaque_payload_b64", "input_field_ids",
                "output_field_ids", "native_receipt_refs", "open_gap_refs", "terminal_status",
                "behavior_manifest", "claim_boundary", "responsibility_spans", "envelope_fingerprint",
            },
            "member envelope",
        )
        encoded = raw.get("opaque_payload_b64")
        payload: bytes | None = None
        if encoded is not None:
            if not isinstance(encoded, str):
                raise ValueError("member envelope opaque_payload_b64 must be a string or null")
            try:
                payload = base64.b64decode(encoded.encode("ascii"), validate=True)
            except (ValueError, UnicodeError) as exc:
                raise ValueError("member envelope opaque payload is not canonical base64") from exc
        envelope = cls(
            schema_version=str(raw.get("schema_version", "")),
            envelope_id=_text(raw.get("envelope_id"), "member envelope id"),
            task_id=_text(raw.get("task_id"), "member envelope task id"),
            member_id=str(raw.get("member_id", "")),
            native_model_id=_text(raw.get("native_model_id"), "member native model id"),
            native_schema_id=_text(raw.get("native_schema_id"), "member native schema id"),
            native_schema_version=_text(raw.get("native_schema_version"), "member native schema version"),
            model_fingerprint=_sha(raw.get("model_fingerprint"), "member model fingerprint"),
            expected_target_anchor_id=_text(
                raw.get("expected_target_anchor_id"),
                "member envelope expected target anchor id",
            ),
            expected_target_anchor_fingerprint=_sha(
                raw.get("expected_target_anchor_fingerprint"),
                "member envelope expected target anchor fingerprint",
            ),
            payload_fingerprint=_sha(raw.get("payload_fingerprint"), "member payload fingerprint"),
            opaque_payload=payload,
            input_field_ids=_ids(raw.get("input_field_ids"), "member envelope input_field_ids"),
            output_field_ids=_ids(raw.get("output_field_ids"), "member envelope output_field_ids"),
            native_receipt_refs=tuple(
                NativeReceiptReference.from_dict(item)
                for item in _rows(raw.get("native_receipt_refs"), "member envelope native_receipt_refs")
            ),
            behavior_manifest=MemberBehaviorManifest.from_dict(
                raw.get("behavior_manifest")  # type: ignore[arg-type]
                if isinstance(raw.get("behavior_manifest"), Mapping)
                else {}
            ),
            open_gap_refs=_ids(raw.get("open_gap_refs"), "member envelope open_gap_refs"),
            terminal_status=str(raw.get("terminal_status", "")),  # type: ignore[arg-type]
            claim_boundary=_text(raw.get("claim_boundary"), "member envelope claim boundary"),
            responsibility_spans=tuple(
                ResponsibilitySpan.from_dict(item)
                for item in _rows(raw.get("responsibility_spans"), "member envelope responsibility_spans")
            ),
        )
        supplied = _sha(raw.get("envelope_fingerprint"), "member envelope fingerprint")
        if supplied != envelope.envelope_fingerprint:
            raise ValueError("member envelope fingerprint is stale or foreign")
        return envelope

    def to_dict(
        self, *, include_payload: bool = True, include_fingerprint: bool = True
    ) -> dict[str, object]:
        result: dict[str, object] = {
            "schema_version": self.schema_version,
            "envelope_id": self.envelope_id,
            "task_id": self.task_id,
            "member_id": self.member_id,
            "native_model_id": self.native_model_id,
            "native_schema_id": self.native_schema_id,
            "native_schema_version": self.native_schema_version,
            "model_fingerprint": self.model_fingerprint,
            "expected_target_anchor_id": self.expected_target_anchor_id,
            "expected_target_anchor_fingerprint": self.expected_target_anchor_fingerprint,
            "payload_fingerprint": self.payload_fingerprint,
            "input_field_ids": list(self.input_field_ids),
            "output_field_ids": list(self.output_field_ids),
            "native_receipt_refs": [item.to_dict() for item in self.native_receipt_refs],
            "behavior_manifest": self.behavior_manifest.to_dict(),
            "open_gap_refs": list(self.open_gap_refs),
            "terminal_status": self.terminal_status,
            "claim_boundary": self.claim_boundary,
            "responsibility_spans": [item.to_dict() for item in self.responsibility_spans],
        }
        if include_payload:
            result["opaque_payload_b64"] = (
                base64.b64encode(self.opaque_payload).decode("ascii")
                if self.opaque_payload is not None
                else None
            )
        if include_fingerprint:
            result["envelope_fingerprint"] = self.envelope_fingerprint
        return result


@dataclass(frozen=True)
class HandoffConsumerRequirement:
    member_id: str
    step_id: str
    requirement_id: str

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "HandoffConsumerRequirement":
        _exact(raw, {"member_id", "step_id", "requirement_id"}, "handoff consumer requirement")
        member_id = str(raw.get("member_id", ""))
        if member_id not in MEMBER_IDS:
            raise ValueError("handoff consumer requirement has unknown member")
        return cls(
            member_id=member_id,
            step_id=_text(raw.get("step_id"), "handoff consumer step id"),
            requirement_id=_text(raw.get("requirement_id"), "handoff consumer requirement id"),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class HandoffConsumerAcknowledgement:
    member_id: str
    step_id: str
    requirement_id: str
    status: Literal["consumed", "rejected", "not_run"]
    consumed_payload_fingerprint: str
    native_receipt_id: str
    native_receipt_fingerprint: str
    task_id: str
    rejection_reason: str = ""

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "HandoffConsumerAcknowledgement":
        _exact(
            raw,
            {
                "member_id", "step_id", "requirement_id", "status",
                "consumed_payload_fingerprint", "native_receipt_id",
                "native_receipt_fingerprint", "task_id", "rejection_reason",
            },
            "handoff consumer acknowledgement",
        )
        member_id = str(raw.get("member_id", ""))
        status = str(raw.get("status", ""))
        if member_id not in MEMBER_IDS or status not in {"consumed", "rejected", "not_run"}:
            raise ValueError("handoff consumer acknowledgement has unknown member or status")
        consumed = str(raw.get("consumed_payload_fingerprint", ""))
        receipt_id = str(raw.get("native_receipt_id", ""))
        receipt_fingerprint = str(raw.get("native_receipt_fingerprint", ""))
        rejection = str(raw.get("rejection_reason", ""))
        if status == "consumed":
            _sha(consumed, "consumer consumed payload fingerprint")
            _text(receipt_id, "consumer native receipt id")
            _sha(receipt_fingerprint, "consumer native receipt fingerprint")
        elif status == "rejected" and not rejection.strip():
            raise ValueError("rejected handoff acknowledgement requires a reason")
        return cls(
            member_id=member_id,
            step_id=_text(raw.get("step_id"), "handoff consumer acknowledgement step"),
            requirement_id=_text(raw.get("requirement_id"), "handoff consumer acknowledgement requirement"),
            status=status,  # type: ignore[arg-type]
            consumed_payload_fingerprint=consumed,
            native_receipt_id=receipt_id,
            native_receipt_fingerprint=receipt_fingerprint,
            task_id=_text(raw.get("task_id"), "handoff consumer acknowledgement task"),
            rejection_reason=rejection,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class HandoffFieldContract:
    handoff_id: str
    task_id: str
    field_id: str
    field_schema_id: str
    payload_fingerprint: str
    producer_member_id: str
    producer_step_id: str
    producer_envelope_id: str
    producer_envelope_fingerprint: str
    producer_native_receipt_id: str
    producer_native_receipt_fingerprint: str
    consumers: tuple[HandoffConsumerRequirement, ...]
    acknowledgements: tuple[HandoffConsumerAcknowledgement, ...]
    schema_version: str = HANDOFF_FIELD_CONTRACT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != HANDOFF_FIELD_CONTRACT_SCHEMA:
            raise ValueError("handoff field contract requires the current schema")
        for name in (
            "handoff_id", "task_id", "field_id", "field_schema_id", "producer_step_id",
            "producer_envelope_id", "producer_native_receipt_id",
        ):
            _text(getattr(self, name), f"handoff {name}")
        if self.producer_member_id not in MEMBER_IDS:
            raise ValueError("handoff producer member is unknown")
        _sha(self.payload_fingerprint, "handoff payload fingerprint")
        _sha(self.producer_envelope_fingerprint, "handoff producer envelope fingerprint")
        _sha(self.producer_native_receipt_fingerprint, "handoff producer receipt fingerprint")
        if not self.consumers:
            raise ValueError("handoff field requires at least one declared consumer")
        consumer_keys = [(item.member_id, item.step_id, item.requirement_id) for item in self.consumers]
        acknowledgement_keys = [
            (item.member_id, item.step_id, item.requirement_id) for item in self.acknowledgements
        ]
        if len(consumer_keys) != len(set(consumer_keys)):
            raise ValueError("handoff consumer requirements must be unique")
        if len(acknowledgement_keys) != len(set(acknowledgement_keys)):
            raise ValueError("handoff consumer acknowledgements must be unique")
        if not set(acknowledgement_keys).issubset(set(consumer_keys)):
            raise ValueError("handoff acknowledgement is foreign to its consumer denominator")
        if any(item.task_id != self.task_id for item in self.acknowledgements):
            raise ValueError("handoff acknowledgement receipt lineage must stay in one task")

    @property
    def contract_fingerprint(self) -> str:
        return _digest(self.to_dict(include_fingerprint=False))

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "HandoffFieldContract":
        _exact(
            raw,
            {
                "schema_version", "handoff_id", "task_id", "field_id", "field_schema_id",
                "payload_fingerprint", "producer_member_id", "producer_step_id",
                "producer_envelope_id", "producer_envelope_fingerprint",
                "producer_native_receipt_id", "producer_native_receipt_fingerprint",
                "consumers", "acknowledgements", "contract_fingerprint",
            },
            "handoff field contract",
        )
        contract = cls(
            schema_version=str(raw.get("schema_version", "")),
            handoff_id=_text(raw.get("handoff_id"), "handoff id"),
            task_id=_text(raw.get("task_id"), "handoff task id"),
            field_id=_text(raw.get("field_id"), "handoff field id"),
            field_schema_id=_text(raw.get("field_schema_id"), "handoff field schema id"),
            payload_fingerprint=_sha(raw.get("payload_fingerprint"), "handoff payload fingerprint"),
            producer_member_id=str(raw.get("producer_member_id", "")),
            producer_step_id=_text(raw.get("producer_step_id"), "handoff producer step"),
            producer_envelope_id=_text(raw.get("producer_envelope_id"), "handoff producer envelope"),
            producer_envelope_fingerprint=_sha(raw.get("producer_envelope_fingerprint"), "handoff producer envelope fingerprint"),
            producer_native_receipt_id=_text(raw.get("producer_native_receipt_id"), "handoff producer receipt"),
            producer_native_receipt_fingerprint=_sha(raw.get("producer_native_receipt_fingerprint"), "handoff producer receipt fingerprint"),
            consumers=tuple(
                HandoffConsumerRequirement.from_dict(item)
                for item in _rows(raw.get("consumers"), "handoff consumers")
            ),
            acknowledgements=tuple(
                HandoffConsumerAcknowledgement.from_dict(item)
                for item in _rows(raw.get("acknowledgements"), "handoff acknowledgements")
            ),
        )
        supplied = _sha(raw.get("contract_fingerprint"), "handoff contract fingerprint")
        if supplied != contract.contract_fingerprint:
            raise ValueError("handoff field contract fingerprint is stale or foreign")
        return contract

    def validation_gaps(self) -> tuple[dict[str, str], ...]:
        acknowledgements = {
            (item.member_id, item.step_id, item.requirement_id): item
            for item in self.acknowledgements
        }
        gaps: list[dict[str, str]] = []
        for requirement in self.consumers:
            key = (requirement.member_id, requirement.step_id, requirement.requirement_id)
            acknowledgement = acknowledgements.get(key)
            if acknowledgement is None or acknowledgement.status == "not_run":
                gaps.append({"code": "consumer-acknowledgement-missing", "object_id": requirement.step_id})
            elif acknowledgement.status == "consumed" and acknowledgement.consumed_payload_fingerprint != self.payload_fingerprint:
                gaps.append({"code": "consumer-payload-fingerprint-mismatch", "object_id": requirement.step_id})
        return tuple(gaps)

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, object]:
        result: dict[str, object] = {
            "schema_version": self.schema_version,
            "handoff_id": self.handoff_id,
            "task_id": self.task_id,
            "field_id": self.field_id,
            "field_schema_id": self.field_schema_id,
            "payload_fingerprint": self.payload_fingerprint,
            "producer_member_id": self.producer_member_id,
            "producer_step_id": self.producer_step_id,
            "producer_envelope_id": self.producer_envelope_id,
            "producer_envelope_fingerprint": self.producer_envelope_fingerprint,
            "producer_native_receipt_id": self.producer_native_receipt_id,
            "producer_native_receipt_fingerprint": self.producer_native_receipt_fingerprint,
            "consumers": [item.to_dict() for item in self.consumers],
            "acknowledgements": [item.to_dict() for item in self.acknowledgements],
        }
        if include_fingerprint:
            result["contract_fingerprint"] = self.contract_fingerprint
        return result


__all__ = [
    "BEHAVIOR_TRANSITION_CASE_SCHEMA",
    "BehaviorTransitionCase",
    "HANDOFF_FIELD_CONTRACT_SCHEMA",
    "MEMBER_BEHAVIOR_MANIFEST_SCHEMA",
    "MEMBER_MODEL_ENVELOPE_SCHEMA",
    "NATIVE_OWNER_ATTESTATION_SCHEMA",
    "HandoffConsumerAcknowledgement",
    "HandoffConsumerRequirement",
    "HandoffFieldContract",
    "MemberModelEnvelope",
    "MemberBehaviorManifest",
    "build_behavior_transition_case",
    "build_member_behavior_manifest",
    "NativeReceiptReference",
    "NativeOwnerAttestation",
    "ResponsibilitySpan",
    "payload_fingerprint",
    "replay_behavior_transition_oracle",
]
