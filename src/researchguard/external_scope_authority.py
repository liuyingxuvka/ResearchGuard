"""Independent, signed scope authority for external-object DNA qualification.

The candidate model is deliberately not an authority producer.  A caller,
target owner, OpenSpec/Spark/ChangeLog adapter, or another independently owned
requirements channel freezes the target and semantic obligation denominator,
then signs it outside this package.  ResearchGuard only validates the portable
record and compares a candidate with it.

Production contains no private key and no built-in trusted producer.  Merely
embedding a valid record therefore proves self-consistency, not trust.  A
qualifier must explicitly supply the authority fingerprint or producer
descriptor fingerprint it trusts.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Mapping, Sequence

from .target_authority import _verify_rsa_pkcs1v15_sha256


EXTERNAL_SCOPE_AUTHORITY_SCHEMA = "researchguard.external-scope-authority.v1"
EXTERNAL_SCOPE_AUTHORITY_SIGNATURE_SCHEMA = (
    "researchguard.external-scope-authority-signature.v1"
)
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


class ExternalScopeAuthorityError(ValueError):
    """One exact current-format scope-authority failure."""


def _canonical(value: object) -> object:
    return json.loads(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    )


def _digest(value: object) -> str:
    body = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _mapping(value: object, fields: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ExternalScopeAuthorityError(f"{label} is not exact-current")
    return value


def _rows(value: object, label: str) -> Sequence[Mapping[str, object]]:
    if not isinstance(value, list) or any(not isinstance(row, Mapping) for row in value):
        raise ExternalScopeAuthorityError(f"{label} must be an array of objects")
    return value  # type: ignore[return-value]


def _text(value: object, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ExternalScopeAuthorityError(f"{label} is required")
    return result


def _ids(value: object, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ExternalScopeAuthorityError(f"{label} must be an array")
    result = tuple(_text(item, label) for item in value)
    if len(result) != len(set(result)):
        raise ExternalScopeAuthorityError(f"{label} must contain unique ids")
    if not result and not allow_empty:
        raise ExternalScopeAuthorityError(f"{label} must not be empty")
    return result


def _fingerprint(value: object, label: str) -> str:
    result = _text(value, label)
    if not _SHA256.fullmatch(result):
        raise ExternalScopeAuthorityError(f"{label} must be an exact sha256 fingerprint")
    return result


def external_scope_authority_signing_payload(
    *,
    authority_fingerprint: str,
    producer_descriptor_fingerprint: str,
    signing_key_id: str,
) -> bytes:
    """Return the only current bytes an independent authority producer signs."""

    material = {
        "schema_version": EXTERNAL_SCOPE_AUTHORITY_SIGNATURE_SCHEMA,
        "authority_fingerprint": _fingerprint(
            authority_fingerprint, "scope authority fingerprint"
        ),
        "producer_descriptor_fingerprint": _fingerprint(
            producer_descriptor_fingerprint,
            "scope authority producer descriptor fingerprint",
        ),
        "signing_key_id": _text(signing_key_id, "scope authority signing key id"),
    }
    return json.dumps(
        material, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def assemble_external_scope_authority_record(
    authority: Mapping[str, object],
    producer_descriptor: Mapping[str, object],
    *,
    authority_signature: str,
) -> dict[str, object]:
    """Assemble a portable record from externally produced material/signature.

    This helper never signs and has no access to a private key.  It is useful to
    deterministic external producers and test fixtures after they have signed
    :func:`external_scope_authority_signing_payload`.
    """

    canonical_authority = _canonical(authority)
    canonical_descriptor = _canonical(producer_descriptor)
    return {
        "schema_version": EXTERNAL_SCOPE_AUTHORITY_SCHEMA,
        "authority": canonical_authority,
        "authority_fingerprint": _digest(canonical_authority),
        "producer_descriptor": canonical_descriptor,
        "producer_descriptor_fingerprint": _digest(canonical_descriptor),
        "authority_signature": _text(
            authority_signature, "scope authority signature"
        ),
    }


def _validate_artifact(row: object) -> None:
    artifact = _mapping(
        row,
        {
            "artifact_id",
            "role",
            "official_url",
            "relative_path",
            "sha256",
            "byte_length",
            "embedded",
            "disposition",
        },
        "scope authority artifact",
    )
    for field in ("artifact_id", "role", "official_url", "relative_path", "disposition"):
        _text(artifact[field], f"scope authority artifact {field}")
    sha256 = str(artifact["sha256"])
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ExternalScopeAuthorityError("scope authority artifact sha256 is invalid")
    if not isinstance(artifact["byte_length"], int) or artifact["byte_length"] < 1:
        raise ExternalScopeAuthorityError("scope authority artifact byte length is invalid")
    if artifact["embedded"] is not False:
        raise ExternalScopeAuthorityError("scope authority cannot embed target bytes")


def _validate_authority(authority: object) -> Mapping[str, object]:
    record = _mapping(
        authority,
        {
            "authority_id",
            "authority_revision",
            "provenance",
            "target",
            "scope",
        },
        "scope authority",
    )
    _text(record["authority_id"], "scope authority id")
    _text(record["authority_revision"], "scope authority revision")
    provenance = _mapping(
        record["provenance"],
        {"origin_kind", "origin_id", "issued_at", "request_fingerprint"},
        "scope authority provenance",
    )
    for field in ("origin_kind", "origin_id", "issued_at"):
        _text(provenance[field], f"scope authority provenance {field}")
    if provenance["origin_kind"] not in {
        "user",
        "openspec",
        "spark",
        "changelog",
        "target_owner",
        "external_contract",
        "test_fixture",
    }:
        raise ExternalScopeAuthorityError("scope authority provenance kind is not current")
    _fingerprint(
        provenance["request_fingerprint"],
        "scope authority provenance request fingerprint",
    )

    target = _mapping(
        record["target"],
        {
            "target_id",
            "title",
            "kind",
            "version",
            "official_url",
            "material_inventory_policy",
            "source_authorities",
            "artifacts",
        },
        "scope authority target",
    )
    for field in ("target_id", "title", "kind", "version", "official_url"):
        _text(target[field], f"scope authority target {field}")
    if not isinstance(target["material_inventory_policy"], Mapping):
        raise ExternalScopeAuthorityError("scope authority material inventory policy is missing")
    artifacts = _rows(target["artifacts"], "scope authority artifacts")
    if not artifacts:
        raise ExternalScopeAuthorityError("scope authority material inventory is empty")
    artifact_ids: list[str] = []
    for row in artifacts:
        _validate_artifact(row)
        artifact_ids.append(str(row["artifact_id"]))
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ExternalScopeAuthorityError("scope authority artifact ids are duplicated")
    source_rows = _rows(target["source_authorities"], "scope authority sources")
    if not source_rows:
        raise ExternalScopeAuthorityError("scope authority source denominator is empty")
    for row in source_rows:
        source = _mapping(
            row, {"source_id", "role", "coverage_ids"}, "scope authority source"
        )
        _text(source["source_id"], "scope authority source id")
        _text(source["role"], "scope authority source role")
        _ids(source["coverage_ids"], "scope authority source coverage")

    scope = _mapping(
        record["scope"],
        {
            "scope_id",
            "purpose",
            "scope_kind",
            "completion_status",
            "whole_target_semantics_claimed",
            "included_question_ids",
            "included_structure_node_ids",
            "excluded_semantic_region_ids",
            "expansion_frontier_ids",
            "structure_obligations",
            "anchor_obligations",
            "member_obligations",
            "cross_member_handoffs",
            "scope_limits",
        },
        "scope authority scope",
    )
    for field in ("scope_id", "purpose", "scope_kind", "completion_status"):
        _text(scope[field], f"scope authority {field}")
    if not isinstance(scope["whole_target_semantics_claimed"], bool):
        raise ExternalScopeAuthorityError("scope authority whole-target flag is invalid")
    _ids(scope["included_question_ids"], "scope authority questions")
    included = set(
        _ids(scope["included_structure_node_ids"], "scope authority included structures")
    )
    _ids(
        scope["excluded_semantic_region_ids"],
        "scope authority exclusions",
        allow_empty=True,
    )
    _ids(
        scope["expansion_frontier_ids"],
        "scope authority frontier",
        allow_empty=True,
    )
    structure_rows = _rows(
        scope["structure_obligations"], "scope authority structure obligations"
    )
    if not structure_rows:
        raise ExternalScopeAuthorityError("scope authority structure denominator is empty")
    structure_ids: list[str] = []
    for row in structure_rows:
        item = _mapping(
            row,
            {
                "node_id",
                "parent_id",
                "kind",
                "semantic_role",
                "locator",
                "required_member_ids",
                "required_artifact_ids",
                "required_bound_object_ids",
            },
            "scope authority structure obligation",
        )
        structure_ids.append(_text(item["node_id"], "scope authority structure id"))
        if item["parent_id"] is not None:
            _text(item["parent_id"], "scope authority structure parent")
        for field in ("kind", "semantic_role", "locator"):
            _text(item[field], f"scope authority structure {field}")
        _ids(item["required_member_ids"], "scope authority required members")
        _ids(
            item["required_artifact_ids"],
            "scope authority required artifacts",
            allow_empty=True,
        )
        _ids(
            item["required_bound_object_ids"],
            "scope authority required bound objects",
            allow_empty=True,
        )
    if len(structure_ids) != len(set(structure_ids)):
        raise ExternalScopeAuthorityError("scope authority structure ids are duplicated")
    if not included.issubset(structure_ids):
        raise ExternalScopeAuthorityError("scope authority included structure is undefined")

    occurrence_ids: list[str] = []
    anchor_ids: list[str] = []
    for row in _rows(scope["anchor_obligations"], "scope authority anchors"):
        anchor = _mapping(
            row,
            {
                "anchor_id",
                "claim_id",
                "source_id",
                "role",
                "artifact_id",
                "structure_node_id",
                "expected_structure_kind",
                "selector",
                "expected_value",
            },
            "scope authority anchor",
        )
        anchor_ids.append(_text(anchor["anchor_id"], "scope authority anchor id"))
        for field in (
            "claim_id",
            "source_id",
            "role",
            "artifact_id",
            "structure_node_id",
            "expected_structure_kind",
            "expected_value",
        ):
            _text(anchor[field], f"scope authority anchor {field}")
        selector = _mapping(
            anchor["selector"],
            {"selector_kind", "occurrence_id", "locator", "fingerprint", "parameters"},
            "scope authority anchor selector",
        )
        _text(selector["selector_kind"], "scope authority selector kind")
        occurrence_ids.append(
            _text(selector["occurrence_id"], "scope authority selector occurrence id")
        )
        _text(selector["locator"], "scope authority selector locator")
        _fingerprint(selector["fingerprint"], "scope authority selector fingerprint")
        if not isinstance(selector["parameters"], Mapping):
            raise ExternalScopeAuthorityError("scope authority selector parameters are invalid")
    if len(anchor_ids) != len(set(anchor_ids)):
        raise ExternalScopeAuthorityError("scope authority anchor ids are duplicated")
    if len(occurrence_ids) != len(set(occurrence_ids)):
        raise ExternalScopeAuthorityError(
            "scope authority anchors must name distinct semantic occurrences"
        )

    member_ids: list[str] = []
    all_required_outputs: set[str] = set()
    for row in _rows(scope["member_obligations"], "scope authority members"):
        member = _mapping(
            row,
            {
                "member_id",
                "required_input_object_ids",
                "required_output_object_ids",
                "required_output_kinds",
            },
            "scope authority member obligation",
        )
        member_ids.append(_text(member["member_id"], "scope authority member id"))
        _ids(member["required_input_object_ids"], "scope authority member inputs")
        output_ids = set(
            _ids(member["required_output_object_ids"], "scope authority member outputs")
        )
        all_required_outputs.update(output_ids)
        kind_objects: set[str] = set()
        kinds: list[str] = []
        for kind_row in _rows(
            member["required_output_kinds"], "scope authority member output kinds"
        ):
            kind = _mapping(
                kind_row, {"kind", "object_ids"}, "scope authority output kind"
            )
            kinds.append(_text(kind["kind"], "scope authority output kind"))
            kind_objects.update(
                _ids(kind["object_ids"], "scope authority output-kind objects", allow_empty=True)
            )
        if len(kinds) != len(set(kinds)) or kind_objects != output_ids:
            raise ExternalScopeAuthorityError(
                "scope authority output-kind denominator differs from member outputs"
            )
    if len(member_ids) != len(set(member_ids)):
        raise ExternalScopeAuthorityError("scope authority member ids are duplicated")

    handoff_objects: set[str] = set()
    for row in _rows(scope["cross_member_handoffs"], "scope authority handoffs"):
        handoff = _mapping(
            row,
            {"object_id", "producer_member_id", "consumer_member_ids"},
            "scope authority handoff",
        )
        object_id = _text(handoff["object_id"], "scope authority handoff object")
        if object_id in handoff_objects:
            raise ExternalScopeAuthorityError("scope authority handoff object is duplicated")
        handoff_objects.add(object_id)
        _text(handoff["producer_member_id"], "scope authority handoff producer")
        _ids(
            handoff["consumer_member_ids"],
            "scope authority handoff consumers",
            allow_empty=True,
        )
    if handoff_objects != all_required_outputs:
        raise ExternalScopeAuthorityError(
            "scope authority handoffs must dispose every required member output"
        )
    if not isinstance(scope["scope_limits"], list) or any(
        not str(item).strip() for item in scope["scope_limits"]
    ):
        raise ExternalScopeAuthorityError("scope authority scope limits are invalid")
    return record


def validate_external_scope_authority_record(
    raw: object,
) -> dict[str, object]:
    """Validate exact shape, fingerprints, and signature without granting trust."""

    record = _mapping(
        raw,
        {
            "schema_version",
            "authority",
            "authority_fingerprint",
            "producer_descriptor",
            "producer_descriptor_fingerprint",
            "authority_signature",
        },
        "external scope authority record",
    )
    if record["schema_version"] != EXTERNAL_SCOPE_AUTHORITY_SCHEMA:
        raise ExternalScopeAuthorityError("external scope authority schema is not current")
    authority = _validate_authority(record["authority"])
    authority_fingerprint = _fingerprint(
        record["authority_fingerprint"], "scope authority fingerprint"
    )
    if authority_fingerprint != _digest(authority):
        raise ExternalScopeAuthorityError("scope authority fingerprint is stale")
    descriptor = _mapping(
        record["producer_descriptor"],
        {
            "producer_id",
            "producer_version",
            "signature_algorithm",
            "signing_key_id",
            "public_exponent",
            "public_modulus_hex",
        },
        "scope authority producer descriptor",
    )
    for field in ("producer_id", "producer_version", "signing_key_id"):
        _text(descriptor[field], f"scope authority producer {field}")
    if descriptor["signature_algorithm"] != "rsa-pkcs1v15-sha256":
        raise ExternalScopeAuthorityError("scope authority signature algorithm is not current")
    if not isinstance(descriptor["public_exponent"], int) or descriptor["public_exponent"] < 3:
        raise ExternalScopeAuthorityError("scope authority public exponent is invalid")
    try:
        modulus = int(_text(descriptor["public_modulus_hex"], "scope authority modulus"), 16)
    except ValueError as exc:
        raise ExternalScopeAuthorityError("scope authority modulus is invalid") from exc
    if modulus.bit_length() < 2048:
        raise ExternalScopeAuthorityError("scope authority public key is too small")
    descriptor_fingerprint = _fingerprint(
        record["producer_descriptor_fingerprint"],
        "scope authority producer descriptor fingerprint",
    )
    if descriptor_fingerprint != _digest(descriptor):
        raise ExternalScopeAuthorityError(
            "scope authority producer descriptor fingerprint is stale"
        )
    payload = external_scope_authority_signing_payload(
        authority_fingerprint=authority_fingerprint,
        producer_descriptor_fingerprint=descriptor_fingerprint,
        signing_key_id=str(descriptor["signing_key_id"]),
    )
    verifier_descriptor = {
        "public_modulus_hex": str(descriptor["public_modulus_hex"]),
        "public_exponent": int(descriptor["public_exponent"]),
    }
    signature = _text(record["authority_signature"], "scope authority signature")
    if not _verify_rsa_pkcs1v15_sha256(payload, signature, verifier_descriptor):
        raise ExternalScopeAuthorityError("scope authority signature is invalid")
    return {
        "record": _canonical(record),
        "authority": _canonical(authority),
        "authority_fingerprint": authority_fingerprint,
        "producer_descriptor_fingerprint": descriptor_fingerprint,
        "required_trust": {
            "authority_fingerprint": authority_fingerprint,
            "producer_descriptor_fingerprint": descriptor_fingerprint,
        },
    }


__all__ = [
    "EXTERNAL_SCOPE_AUTHORITY_SCHEMA",
    "EXTERNAL_SCOPE_AUTHORITY_SIGNATURE_SCHEMA",
    "ExternalScopeAuthorityError",
    "assemble_external_scope_authority_record",
    "external_scope_authority_signing_payload",
    "validate_external_scope_authority_record",
]
