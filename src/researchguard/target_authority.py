"""Small current-only transport for independently owned target denominators.

The carrier deliberately knows nothing about ExperimentGuard, LogicGuard,
SourceGuard, or TraceGuard semantics.  A native owner freezes the request,
input, target revision, tool revision, and one disposition for every target
item.  Member blueprint code then compares this independent denominator with
both its declared universe and the objects actually present.
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable, Literal, Mapping
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname


TARGET_PURPOSE_AUTHORITY_SCHEMA = "researchguard.target-purpose-authority.v3"
NATIVE_TARGET_ATTESTATION_SCHEMA = "researchguard.native-target-attestation.v3"
EXPECTED_TARGET_ANCHOR_SCHEMA = "researchguard.expected-target-anchor.v1"
EXPECTED_TARGET_ADMISSION_RECEIPT_SCHEMA = (
    "researchguard.expected-target-admission-receipt.v1"
)
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")

# Production intentionally starts with no active producer.  Deployment may
# install a descriptor only when its private key is externally held.  Missing
# external authority is unverified; no repository test key is a trust root.
_CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS: dict[
    tuple[str, str, str], dict[str, object]
] = {}
_PORTABLE_EXPECTED_TARGET_RECORDS: ContextVar[
    Mapping[str, Mapping[str, object]] | None
] = ContextVar("researchguard_portable_expected_target_records", default=None)
_EXPECTED_TARGET_AUTHORITY_LOCATOR_PREFIX = (
    "researchguard-authority:expected-target-admission/"
)


def _digest(value: object) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _text(value: object, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{field} is required")
    return result


def _sha(value: object, field: str) -> str:
    result = str(value or "").strip()
    if not _SHA256.fullmatch(result):
        raise ValueError(f"{field} must be an exact sha256 fingerprint")
    return result


def content_addressed_request_id(request_fingerprint: str) -> str:
    """Return the sole current request id for canonical request material."""

    fingerprint = _sha(request_fingerprint, "request fingerprint")
    return f"request:{fingerprint.removeprefix('sha256:')}"


def content_addressed_authority_id(member_id: str, material_fingerprint: str) -> str:
    """Bind an issued authority id to the exact independently replayed bytes."""

    member = _text(member_id, "target authority member id")
    fingerprint = _sha(material_fingerprint, "target material fingerprint")
    return f"authority:{member}:{fingerprint.removeprefix('sha256:')}"


@dataclass(frozen=True)
class TargetAuthorityItem:
    kind: str
    object_id: str
    disposition: Literal["required", "excluded", "unresolved"]
    reason: str = ""

    def __post_init__(self) -> None:
        _text(self.kind, "target authority item kind")
        _text(self.object_id, "target authority item object_id")
        if self.disposition not in {"required", "excluded", "unresolved"}:
            raise ValueError("target authority item disposition is not current")
        if self.disposition != "required" and not self.reason.strip():
            raise ValueError("non-required target authority items need a reason")

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "TargetAuthorityItem":
        if set(raw) != {"kind", "object_id", "disposition", "reason"}:
            raise ValueError("target authority item contains unknown or missing fields")
        return cls(
            kind=_text(raw.get("kind"), "target authority item kind"),
            object_id=_text(raw.get("object_id"), "target authority item object_id"),
            disposition=str(raw.get("disposition", "")),  # type: ignore[arg-type]
            reason=str(raw.get("reason", "")),
        )

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


_CURRENT_NATIVE_ADAPTERS: dict[tuple[str, str, str], tuple[str, str]] = {
    (
        "experimentguard",
        "researchguard.experiment.target-purpose",
        "researchguard.experiment.target-universe",
    ): ("researchguard.experiment.target-material-adapter", "2"),
    (
        "logicguard",
        "researchguard.logic.artifact-inventory",
        "researchguard.logic.target-parser",
    ): ("researchguard.logic.target-material-adapter", "2"),
    (
        "sourceguard",
        "researchguard.source.target-purpose",
        "researchguard.source.guard-contract+target-parser",
    ): ("researchguard.source.target-material-adapter", "2"),
    (
        "traceguard",
        "researchguard.trace.target-purpose",
        "researchguard.trace.native-inventory",
    ): ("researchguard.trace.target-material-adapter", "2"),
}
def _items_fingerprint(items: Iterable[TargetAuthorityItem]) -> str:
    return _digest(
        [
            item.to_dict()
            for item in sorted(items, key=lambda row: (row.kind, row.object_id))
        ]
    )


def read_target_material_bytes(
    locator: str,
) -> tuple[bytes | None, str, str]:
    """Read exact local/inline bytes without interpreting member semantics.

    Returns ``(bytes, fingerprint, gap)``.  Network and relative locators are
    intentionally not fetched: their native owner must first make them an
    exact replayable snapshot.  That boundary is reported as unverified.
    """

    locator = str(locator or "").strip()
    if not locator:
        return None, "", "target material locator is missing"
    if locator.startswith("data:application/json;base64,"):
        encoded = locator.split(",", 1)[1]
        try:
            body = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            return None, "", f"invalid inline target material: {exc}"
        return body, "sha256:" + hashlib.sha256(body).hexdigest(), ""
    parsed = urlparse(locator)
    if parsed.scheme == "file":
        raw_path = url2pathname(unquote(parsed.path))
        if parsed.netloc:
            raw_path = f"//{parsed.netloc}{raw_path}"
        if re.fullmatch(r"/[A-Za-z]:/.*", raw_path):
            raw_path = raw_path[1:]
        path = Path(raw_path)
    elif not parsed.scheme:
        path = Path(locator)
        if not path.is_absolute():
            return None, "", "relative target material locator is not replayable"
    else:
        return None, "", f"external target material scheme {parsed.scheme!r} is not replayable"
    try:
        body = path.read_bytes()
    except OSError as exc:
        return None, "", f"target material cannot be replayed: {exc}"
    return body, "sha256:" + hashlib.sha256(body).hexdigest(), ""


def _expected_target_result_material(
    *,
    member_id: str,
    task_id: str,
    task_request_fingerprint: str,
    target_request_id: str,
    target_request_fingerprint: str,
    target_id: str,
    target_revision: str,
    material_locator: str,
    material_media_type: str,
    material_fingerprint: str,
    admission_owner_id: str,
    admission_producer_id: str,
    admission_producer_version: str,
) -> dict[str, str]:
    return {
        "member_id": member_id,
        "task_id": task_id,
        "task_request_fingerprint": task_request_fingerprint,
        "target_request_id": target_request_id,
        "target_request_fingerprint": target_request_fingerprint,
        "target_id": target_id,
        "target_revision": target_revision,
        "material_locator": material_locator,
        "material_media_type": material_media_type,
        "material_fingerprint": material_fingerprint,
        "admission_owner_id": admission_owner_id,
        "admission_producer_id": admission_producer_id,
        "admission_producer_version": admission_producer_version,
    }


def _expected_target_receipt_payload(
    *,
    anchor_id: str,
    result_material: Mapping[str, str],
    admission_input_fingerprint: str,
    admission_result_fingerprint: str,
    admission_key_id: str,
    admission_signature: str,
) -> dict[str, object]:
    return {
        "schema_version": EXPECTED_TARGET_ADMISSION_RECEIPT_SCHEMA,
        "anchor_id": anchor_id,
        **dict(result_material),
        "admission_input_fingerprint": admission_input_fingerprint,
        "admission_result_fingerprint": admission_result_fingerprint,
        "admission_key_id": admission_key_id,
        "admission_signature": admission_signature,
    }


def expected_target_admission_signing_payload(
    *,
    anchor_id: str,
    result_material: Mapping[str, str],
    admission_input_fingerprint: str,
    admission_result_fingerprint: str,
    admission_key_id: str,
) -> bytes:
    """Return the canonical bytes an external admission producer signs."""

    material = {
        "schema_version": "researchguard.expected-target-admission-signature.v1",
        "anchor_id": anchor_id,
        "result_material": dict(result_material),
        "admission_input_fingerprint": admission_input_fingerprint,
        "admission_result_fingerprint": admission_result_fingerprint,
        "admission_key_id": admission_key_id,
    }
    return json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _verify_rsa_pkcs1v15_sha256(
    message: bytes, signature: str, descriptor: Mapping[str, object]
) -> bool:
    prefix = "rsa-pkcs1v15-sha256:"
    if not signature.startswith(prefix):
        return False
    try:
        signature_bytes = bytes.fromhex(signature.removeprefix(prefix))
        modulus = int(str(descriptor["public_modulus_hex"]), 16)
        exponent = int(descriptor["public_exponent"])
    except (KeyError, TypeError, ValueError):
        return False
    width = (modulus.bit_length() + 7) // 8
    if len(signature_bytes) != width:
        return False
    decoded = pow(int.from_bytes(signature_bytes, "big"), exponent, modulus).to_bytes(
        width, "big"
    )
    digest_info = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(
        message
    ).digest()
    padding_length = width - len(digest_info) - 3
    if padding_length < 8:
        return False
    expected = b"\x00\x01" + (b"\xff" * padding_length) + b"\x00" + digest_info
    return decoded == expected


def _verify_expected_target_producer_signature(
    *,
    producer: tuple[str, str, str],
    anchor_id: str,
    result_material: Mapping[str, str],
    admission_input_fingerprint: str,
    admission_result_fingerprint: str,
    admission_key_id: str,
    admission_signature: str,
) -> bool:
    descriptor = _active_expected_target_producers().get(producer)
    if descriptor is None:
        return False
    if descriptor.get("algorithm") != "rsa-pkcs1v15-sha256":
        return False
    if admission_key_id != descriptor.get("key_id"):
        return False
    payload = expected_target_admission_signing_payload(
        anchor_id=anchor_id,
        result_material=result_material,
        admission_input_fingerprint=admission_input_fingerprint,
        admission_result_fingerprint=admission_result_fingerprint,
        admission_key_id=admission_key_id,
    )
    return _verify_rsa_pkcs1v15_sha256(payload, admission_signature, descriptor)


def _portable_expected_target_descriptor(
    record: Mapping[str, object],
) -> tuple[tuple[str, str, str], dict[str, object]]:
    descriptor = record.get("admission_producer_descriptor")
    if not isinstance(descriptor, Mapping):
        raise ValueError("portable expected-target producer descriptor is missing")
    key = (
        _text(descriptor.get("admission_owner_id"), "portable admission owner"),
        _text(descriptor.get("admission_producer_id"), "portable admission producer"),
        _text(
            descriptor.get("admission_producer_version"),
            "portable admission producer version",
        ),
    )
    return key, {
        "algorithm": _text(
            descriptor.get("signature_algorithm"),
            "portable admission signature algorithm",
        ),
        "key_id": _text(
            descriptor.get("signing_key_id"), "portable admission signing key"
        ),
        "public_exponent": int(descriptor.get("public_exponent", 0)),
        "public_modulus_hex": _text(
            descriptor.get("public_modulus_hex"),
            "portable admission public modulus",
        ).lower(),
    }


def _active_expected_target_producers(
) -> Mapping[tuple[str, str, str], Mapping[str, object]]:
    records = _PORTABLE_EXPECTED_TARGET_RECORDS.get()
    if records is None:
        return _CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS
    result: dict[tuple[str, str, str], Mapping[str, object]] = {}
    for record in records.values():
        key, descriptor = _portable_expected_target_descriptor(record)
        prior = result.get(key)
        if prior is not None and dict(prior) != descriptor:
            raise ValueError("portable expected-target producer identity is ambiguous")
        result[key] = descriptor
    return result


@contextmanager
def _portable_expected_target_record_scope(
    records: Iterable[Mapping[str, object]],
):
    """Expose bundle-carried signed target records only to one replay call.

    The scope is context-local, read-only, and reset unconditionally.  It does
    not register a producer, write an authority root, or survive the portable
    qualification that supplied the records.
    """

    by_anchor: dict[str, Mapping[str, object]] = {}
    for record in records:
        anchor_raw = record.get("anchor")
        if not isinstance(anchor_raw, Mapping):
            raise ValueError("portable expected-target record has no anchor")
        anchor = ExpectedTargetAnchor.from_dict(anchor_raw)
        if anchor.anchor_id in by_anchor:
            raise ValueError("portable expected-target anchor is duplicated")
        by_anchor[anchor.anchor_id] = record
    token = _PORTABLE_EXPECTED_TARGET_RECORDS.set(by_anchor)
    try:
        yield
    finally:
        _PORTABLE_EXPECTED_TARGET_RECORDS.reset(token)


def _expected_target_binding_material(
    result_material: Mapping[str, str], *, anchor_id: str, receipt_id: str
) -> dict[str, str]:
    return {
        "schema_version": "researchguard.expected-target-binding.v1",
        "member_id": result_material["member_id"],
        "task_id": result_material["task_id"],
        "task_request_fingerprint": result_material["task_request_fingerprint"],
        "target_request_id": result_material["target_request_id"],
        "target_request_fingerprint": result_material["target_request_fingerprint"],
        "target_id": result_material["target_id"],
        "anchor_id": anchor_id,
        "receipt_id": receipt_id,
    }


def _expected_target_binding_key(result_material: Mapping[str, str]) -> str:
    return _digest(
        {
            "member_id": result_material["member_id"],
            "task_id": result_material["task_id"],
            "task_request_fingerprint": result_material["task_request_fingerprint"],
            "target_request_id": result_material["target_request_id"],
            "target_request_fingerprint": result_material["target_request_fingerprint"],
            "target_id": result_material["target_id"],
        }
    ).removeprefix("sha256:")


def _expected_target_authority_root() -> Path:
    """Return the sole current controlled publication root.

    There is intentionally no environment, caller path, or locator override.
    The directory stores immutable authority records, not a replay cache.
    """

    return (
        Path.home()
        / ".researchguard"
        / "authority"
        / "expected-target-v2"
    ).resolve()


def _write_immutable_authority_bytes(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(body)
    except FileExistsError:
        if path.read_bytes() != body:
            raise ValueError("immutable expected-target authority identity is already bound")


def _publish_expected_target_admission(
    *,
    receipt_payload: Mapping[str, object],
    result_material: Mapping[str, str],
) -> tuple[str, str, str]:
    """Private writer used only by the closed umbrella admission producer."""

    body = json.dumps(
        receipt_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    receipt_fingerprint = "sha256:" + hashlib.sha256(body).hexdigest()
    receipt_id = (
        "expected-target-admission:"
        + receipt_fingerprint.removeprefix("sha256:")
    )
    receipt_hex = receipt_fingerprint.removeprefix("sha256:")
    root = _expected_target_authority_root()
    receipt_path = root / "receipts" / f"{receipt_hex}.json"
    _write_immutable_authority_bytes(receipt_path, body)
    anchor_id = str(receipt_payload["anchor_id"])
    binding = _expected_target_binding_material(
        result_material, anchor_id=anchor_id, receipt_id=receipt_id
    )
    binding_body = json.dumps(
        binding, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    binding_path = (
        root / "bindings" / f"{_expected_target_binding_key(result_material)}.json"
    )
    _write_immutable_authority_bytes(binding_path, binding_body)
    locator = _EXPECTED_TARGET_AUTHORITY_LOCATOR_PREFIX + receipt_hex
    return locator, receipt_fingerprint, receipt_id


def _read_expected_target_admission_receipt(
    locator: str,
) -> tuple[bytes | None, str, str]:
    value = str(locator or "").strip()
    if not value.startswith(_EXPECTED_TARGET_AUTHORITY_LOCATOR_PREFIX):
        return None, "", "receipt is outside the closed expected-target authority root"
    suffix = value.removeprefix(_EXPECTED_TARGET_AUTHORITY_LOCATOR_PREFIX)
    if not re.fullmatch(r"[0-9a-f]{64}", suffix):
        return None, "", "expected-target authority locator is malformed"
    path = _expected_target_authority_root() / "receipts" / f"{suffix}.json"
    try:
        body = path.read_bytes()
    except OSError as exc:
        return None, "", f"expected-target admission receipt is unavailable: {exc}"
    fingerprint = "sha256:" + hashlib.sha256(body).hexdigest()
    if fingerprint.removeprefix("sha256:") != suffix:
        return None, fingerprint, "expected-target authority receipt path is stale"
    return body, fingerprint, ""


def _verify_expected_target_binding(anchor: "ExpectedTargetAnchor") -> str:
    result_material = anchor.result_material
    path = (
        _expected_target_authority_root()
        / "bindings"
        / f"{_expected_target_binding_key(result_material)}.json"
    )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return f"expected-target admission binding is unavailable: {exc}"
    expected = _expected_target_binding_material(
        result_material,
        anchor_id=anchor.anchor_id,
        receipt_id=anchor.receipt_id,
    )
    if raw != expected:
        return "expected-target task/request/target identity is bound to another admission"
    return ""


@dataclass(frozen=True)
class ExpectedTargetAnchor:
    """Provider-neutral target identity frozen before member modeling.

    The carrier does not interpret member material.  It binds exact original
    task/request facts, one raw-material snapshot, and the immutable admission
    receipt produced by the external ResearchGuard admission boundary.
    """

    anchor_id: str
    member_id: str
    task_id: str
    task_request_fingerprint: str
    target_request_id: str
    target_request_fingerprint: str
    target_id: str
    target_revision: str
    material_locator: str
    material_media_type: str
    material_fingerprint: str
    admission_owner_id: str
    admission_producer_id: str
    admission_producer_version: str
    admission_input_fingerprint: str
    admission_result_fingerprint: str
    admission_key_id: str
    admission_signature: str
    receipt_id: str
    receipt_locator: str
    receipt_fingerprint: str
    anchor_fingerprint: str = ""
    schema_version: str = EXPECTED_TARGET_ANCHOR_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != EXPECTED_TARGET_ANCHOR_SCHEMA:
            raise ValueError("expected target anchor requires the current schema")
        for name in (
            "anchor_id",
            "member_id",
            "task_id",
            "target_request_id",
            "target_id",
            "material_locator",
            "material_media_type",
            "admission_owner_id",
            "admission_producer_id",
            "admission_producer_version",
            "admission_key_id",
            "admission_signature",
            "receipt_id",
            "receipt_locator",
        ):
            _text(getattr(self, name), f"expected target anchor {name}")
        if not self.receipt_locator.startswith(
            _EXPECTED_TARGET_AUTHORITY_LOCATOR_PREFIX
        ):
            raise ValueError(
                "expected target anchor receipt is outside the closed authority root"
            )
        for name in (
            "task_request_fingerprint",
            "target_request_fingerprint",
            "target_revision",
            "material_fingerprint",
            "admission_input_fingerprint",
            "admission_result_fingerprint",
            "receipt_fingerprint",
        ):
            _sha(getattr(self, name), f"expected target anchor {name}")
        if self.member_id not in {
            "experimentguard",
            "logicguard",
            "sourceguard",
            "traceguard",
        }:
            raise ValueError("expected target anchor member is not current")
        if not self.admission_signature.startswith("rsa-pkcs1v15-sha256:"):
            raise ValueError("expected target anchor signature algorithm is not current")
        if self.target_request_id != content_addressed_request_id(
            self.target_request_fingerprint
        ):
            raise ValueError("expected target anchor request id is not content-addressed")
        if self.anchor_id != (
            "expected-target-anchor:"
            + self.admission_result_fingerprint.removeprefix("sha256:")
        ):
            raise ValueError("expected target anchor id is not content-addressed")
        if self.receipt_id != (
            "expected-target-admission:"
            + self.receipt_fingerprint.removeprefix("sha256:")
        ):
            raise ValueError("expected target admission receipt id is not content-addressed")
        if self.anchor_fingerprint:
            _sha(self.anchor_fingerprint, "expected target anchor fingerprint")
            if self.anchor_fingerprint != self.expected_fingerprint:
                raise ValueError("expected target anchor fingerprint is stale or foreign")

    @property
    def expected_result_fingerprint(self) -> str:
        return _digest(self.result_material)

    @property
    def result_material(self) -> dict[str, str]:
        return _expected_target_result_material(
            member_id=self.member_id,
            task_id=self.task_id,
            task_request_fingerprint=self.task_request_fingerprint,
            target_request_id=self.target_request_id,
            target_request_fingerprint=self.target_request_fingerprint,
            target_id=self.target_id,
            target_revision=self.target_revision,
            material_locator=self.material_locator,
            material_media_type=self.material_media_type,
            material_fingerprint=self.material_fingerprint,
            admission_owner_id=self.admission_owner_id,
            admission_producer_id=self.admission_producer_id,
            admission_producer_version=self.admission_producer_version,
        )

    @property
    def receipt_payload(self) -> dict[str, object]:
        return _expected_target_receipt_payload(
            anchor_id=self.anchor_id,
            result_material=self.result_material,
            admission_input_fingerprint=self.admission_input_fingerprint,
            admission_result_fingerprint=self.admission_result_fingerprint,
            admission_key_id=self.admission_key_id,
            admission_signature=self.admission_signature,
        )

    @property
    def expected_fingerprint(self) -> str:
        return _digest(self.to_dict(include_fingerprint=False))

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "ExpectedTargetAnchor":
        allowed = {
            "schema_version",
            "anchor_id",
            "member_id",
            "task_id",
            "task_request_fingerprint",
            "target_request_id",
            "target_request_fingerprint",
            "target_id",
            "target_revision",
            "material_locator",
            "material_media_type",
            "material_fingerprint",
            "admission_owner_id",
            "admission_producer_id",
            "admission_producer_version",
            "admission_input_fingerprint",
            "admission_result_fingerprint",
            "admission_key_id",
            "admission_signature",
            "receipt_id",
            "receipt_locator",
            "receipt_fingerprint",
            "anchor_fingerprint",
        }
        if set(raw) != allowed:
            raise ValueError("expected target anchor contains unknown or missing fields")
        return cls(**{key: str(raw.get(key, "")) for key in allowed})

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, object]:
        result: dict[str, object] = {
            "schema_version": self.schema_version,
            "anchor_id": self.anchor_id,
            "member_id": self.member_id,
            "task_id": self.task_id,
            "task_request_fingerprint": self.task_request_fingerprint,
            "target_request_id": self.target_request_id,
            "target_request_fingerprint": self.target_request_fingerprint,
            "target_id": self.target_id,
            "target_revision": self.target_revision,
            "material_locator": self.material_locator,
            "material_media_type": self.material_media_type,
            "material_fingerprint": self.material_fingerprint,
            "admission_owner_id": self.admission_owner_id,
            "admission_producer_id": self.admission_producer_id,
            "admission_producer_version": self.admission_producer_version,
            "admission_input_fingerprint": self.admission_input_fingerprint,
            "admission_result_fingerprint": self.admission_result_fingerprint,
            "admission_key_id": self.admission_key_id,
            "admission_signature": self.admission_signature,
            "receipt_id": self.receipt_id,
            "receipt_locator": self.receipt_locator,
            "receipt_fingerprint": self.receipt_fingerprint,
        }
        if include_fingerprint:
            result["anchor_fingerprint"] = self.anchor_fingerprint
        return result


def _verify_portable_expected_target_record(
    anchor: ExpectedTargetAnchor, record: Mapping[str, object]
) -> tuple[tuple[str, str], ...]:
    expected_fields = {
        "anchor",
        "receipt_payload",
        "material_media_type",
        "material_bytes_b64",
        "admission_producer_descriptor",
    }
    gaps: list[tuple[str, str]] = []
    if set(record) != expected_fields:
        return (("portable-target-record-invalid", anchor.anchor_id),)
    anchor_raw = record.get("anchor")
    receipt_payload = record.get("receipt_payload")
    descriptor_raw = record.get("admission_producer_descriptor")
    if not isinstance(anchor_raw, Mapping) or not isinstance(
        receipt_payload, Mapping
    ) or not isinstance(descriptor_raw, Mapping):
        return (("portable-target-record-invalid", anchor.anchor_id),)
    try:
        carried_anchor = ExpectedTargetAnchor.from_dict(anchor_raw)
        producer_key, descriptor = _portable_expected_target_descriptor(record)
        material = base64.b64decode(
            str(record.get("material_bytes_b64", "")).encode("ascii"),
            validate=True,
        )
    except (TypeError, ValueError) as exc:
        return (("portable-target-record-invalid", str(exc)),)
    if carried_anchor.to_dict() != anchor.to_dict():
        gaps.append(("portable-target-anchor-mismatch", anchor.anchor_id))
    if dict(receipt_payload) != anchor.receipt_payload:
        gaps.append(("portable-target-receipt-payload-mismatch", anchor.anchor_id))
    receipt_body = json.dumps(
        anchor.receipt_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if "sha256:" + hashlib.sha256(receipt_body).hexdigest() != anchor.receipt_fingerprint:
        gaps.append(("portable-target-receipt-fingerprint-mismatch", anchor.anchor_id))
    if "sha256:" + hashlib.sha256(material).hexdigest() != anchor.material_fingerprint:
        gaps.append(("portable-target-material-fingerprint-mismatch", anchor.anchor_id))
    if str(record.get("material_media_type", "")) != anchor.material_media_type:
        gaps.append(("portable-target-media-type-mismatch", anchor.anchor_id))
    public_key_fingerprint = _digest(
        {
            "algorithm": str(descriptor["algorithm"]),
            "public_exponent": int(descriptor["public_exponent"]),
            "public_modulus_hex": str(descriptor["public_modulus_hex"]).lower(),
        }
    )
    descriptor_fingerprint = _digest(
        {
            "admission_owner_id": producer_key[0],
            "admission_producer_id": producer_key[1],
            "admission_producer_version": producer_key[2],
            "signing_key_id": str(descriptor["key_id"]),
            "signature_algorithm": str(descriptor["algorithm"]),
            "public_key_fingerprint": public_key_fingerprint,
        }
    )
    descriptor_checks = (
        (producer_key[0], anchor.admission_owner_id),
        (producer_key[1], anchor.admission_producer_id),
        (producer_key[2], anchor.admission_producer_version),
        (descriptor.get("key_id"), anchor.admission_key_id),
        (descriptor.get("algorithm"), "rsa-pkcs1v15-sha256"),
        (descriptor_raw.get("public_key_fingerprint"), public_key_fingerprint),
        (
            descriptor_raw.get("producer_descriptor_fingerprint"),
            descriptor_fingerprint,
        ),
    )
    if any(str(actual) != str(expected) for actual, expected in descriptor_checks):
        gaps.append(("portable-target-producer-descriptor-mismatch", anchor.anchor_id))
    if anchor.admission_result_fingerprint != anchor.expected_result_fingerprint:
        gaps.append(("expected-target-admission-result-mismatch", anchor.anchor_id))
    if anchor.anchor_fingerprint != anchor.expected_fingerprint:
        gaps.append(("expected-target-anchor-fingerprint-mismatch", anchor.anchor_id))
    signing_payload = expected_target_admission_signing_payload(
        anchor_id=anchor.anchor_id,
        result_material=anchor.result_material,
        admission_input_fingerprint=anchor.admission_input_fingerprint,
        admission_result_fingerprint=anchor.admission_result_fingerprint,
        admission_key_id=anchor.admission_key_id,
    )
    if not _verify_rsa_pkcs1v15_sha256(
        signing_payload,
        anchor.admission_signature,
        descriptor,
    ):
        gaps.append(("portable-target-signature-invalid", anchor.anchor_id))
    return tuple(sorted(set(gaps)))


def verify_expected_target_anchor(
    anchor: ExpectedTargetAnchor,
) -> tuple[tuple[str, str], ...]:
    """Replay the admission receipt and raw bytes for one frozen anchor."""

    portable_records = _PORTABLE_EXPECTED_TARGET_RECORDS.get()
    if portable_records is not None:
        record = portable_records.get(anchor.anchor_id)
        if record is None:
            return (("portable-target-record-missing", anchor.anchor_id),)
        return _verify_portable_expected_target_record(anchor, record)

    gaps: list[tuple[str, str]] = []
    producer = (
        anchor.admission_owner_id,
        anchor.admission_producer_id,
        anchor.admission_producer_version,
    )
    if producer not in _CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS:
        gaps.append(("expected-target-admission-producer-unregistered", anchor.anchor_id))
    elif not _verify_expected_target_producer_signature(
        producer=producer,
        anchor_id=anchor.anchor_id,
        result_material=anchor.result_material,
        admission_input_fingerprint=anchor.admission_input_fingerprint,
        admission_result_fingerprint=anchor.admission_result_fingerprint,
        admission_key_id=anchor.admission_key_id,
        admission_signature=anchor.admission_signature,
    ):
        gaps.append(("expected-target-admission-signature-invalid", anchor.anchor_id))
    if anchor.admission_result_fingerprint != anchor.expected_result_fingerprint:
        gaps.append(("expected-target-admission-result-mismatch", anchor.anchor_id))
    if anchor.anchor_fingerprint != anchor.expected_fingerprint:
        gaps.append(("expected-target-anchor-fingerprint-mismatch", anchor.anchor_id))
    binding_gap = _verify_expected_target_binding(anchor)
    if binding_gap:
        gaps.append(("expected-target-admission-binding-mismatch", binding_gap))
    receipt_body, receipt_fingerprint, receipt_gap = _read_expected_target_admission_receipt(
        anchor.receipt_locator
    )
    if receipt_body is None:
        gaps.append(("expected-target-admission-receipt-unverified", receipt_gap))
    else:
        if receipt_fingerprint != anchor.receipt_fingerprint:
            gaps.append(("expected-target-admission-receipt-bytes-mismatch", anchor.receipt_id))
        try:
            receipt_payload = json.loads(receipt_body.decode("utf-8"))
        except Exception as exc:
            gaps.append(("expected-target-admission-receipt-invalid", str(exc)))
        else:
            if receipt_payload != anchor.receipt_payload:
                gaps.append(("expected-target-admission-receipt-identity-mismatch", anchor.receipt_id))
    material_body, material_fingerprint, material_gap = read_target_material_bytes(
        anchor.material_locator
    )
    if material_body is None:
        gaps.append(("expected-target-material-unverified", material_gap))
    elif material_fingerprint != anchor.material_fingerprint:
        gaps.append(("expected-target-material-mismatch", anchor.anchor_id))
    return tuple(gaps)


def expected_target_portable_record(
    anchor: ExpectedTargetAnchor,
) -> dict[str, object]:
    """Materialize one exact externally signed anchor for bundle-only replay."""

    gaps = verify_expected_target_anchor(anchor)
    if gaps:
        raise ValueError(f"expected target is not portable: {gaps[0][0]}:{gaps[0][1]}")
    producer_key = (
        anchor.admission_owner_id,
        anchor.admission_producer_id,
        anchor.admission_producer_version,
    )
    descriptor = _CURRENT_EXPECTED_TARGET_ADMISSION_PRODUCERS[producer_key]
    body, fingerprint, media_type = read_target_material_bytes(anchor.material_locator)
    if body is None or fingerprint != anchor.material_fingerprint:
        raise ValueError("expected target portable material cannot be replayed")
    public_key_fingerprint = _digest(
        {
            "algorithm": str(descriptor["algorithm"]),
            "public_exponent": int(descriptor["public_exponent"]),
            "public_modulus_hex": str(descriptor["public_modulus_hex"]).lower(),
        }
    )
    descriptor_fingerprint = _digest(
        {
            "admission_owner_id": producer_key[0],
            "admission_producer_id": producer_key[1],
            "admission_producer_version": producer_key[2],
            "signing_key_id": str(descriptor["key_id"]),
            "signature_algorithm": str(descriptor["algorithm"]),
            "public_key_fingerprint": public_key_fingerprint,
        }
    )
    return {
        "anchor": anchor.to_dict(),
        "receipt_payload": anchor.receipt_payload,
        "material_media_type": media_type or anchor.material_media_type,
        "material_bytes_b64": base64.b64encode(body).decode("ascii"),
        "admission_producer_descriptor": {
            "admission_owner_id": producer_key[0],
            "admission_producer_id": producer_key[1],
            "admission_producer_version": producer_key[2],
            "signature_algorithm": str(descriptor["algorithm"]),
            "signing_key_id": str(descriptor["key_id"]),
            "public_exponent": int(descriptor["public_exponent"]),
            "public_modulus_hex": str(descriptor["public_modulus_hex"]).lower(),
            "public_key_fingerprint": public_key_fingerprint,
            "producer_descriptor_fingerprint": descriptor_fingerprint,
        },
    }


@dataclass(frozen=True)
class NativeTargetMaterialReplay:
    """Member-produced replay result carried opaquely by the shared layer."""

    adapter_id: str
    adapter_version: str
    request_id: str
    request_fingerprint: str
    input_id: str
    input_fingerprint: str
    target_id: str
    target_revision: str
    target_fingerprint: str
    purpose_fingerprint: str
    material_locator: str
    material_media_type: str
    material_fingerprint: str
    items: tuple[TargetAuthorityItem, ...]
    status: Literal["current", "unverified", "failed"]
    detail: str = ""

    def __post_init__(self) -> None:
        for name in (
            "adapter_id", "adapter_version", "request_id", "input_id",
            "target_id", "target_revision", "material_locator", "material_media_type",
        ):
            _text(getattr(self, name), f"native target replay {name}")
        for name in (
            "request_fingerprint", "input_fingerprint", "target_fingerprint",
            "purpose_fingerprint", "material_fingerprint",
        ):
            value = getattr(self, name)
            if self.status == "current" or value:
                _sha(value, f"native target replay {name}")
        if self.status not in {"current", "unverified", "failed"}:
            raise ValueError("native target replay status is not current")
        keys = [(item.kind, item.object_id) for item in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("native target replay items must be unique")
        if self.status == "current" and not self.items:
            raise ValueError("current native target replay requires a non-empty denominator")
        if self.status != "current" and not self.detail.strip():
            raise ValueError("non-current native target replay requires a detail")
        if self.status == "current":
            expected_request_id = content_addressed_request_id(
                self.request_fingerprint
            )
            if self.request_id != expected_request_id:
                raise ValueError(
                    "current native target replay request_id is not content-addressed"
                )
            if self.target_revision != self.target_fingerprint:
                raise ValueError(
                    "current native target replay target_revision must equal the exact target fingerprint"
                )

    @property
    def items_fingerprint(self) -> str:
        return _items_fingerprint(self.items)


def _adapter_registry_identity(
    member_id: str, owner_id: str, tool_id: str, adapter_id: str, adapter_version: str
) -> str:
    return _digest(
        {
            "schema_version": NATIVE_TARGET_ATTESTATION_SCHEMA,
            "member_id": member_id,
            "owner_id": owner_id,
            "tool_id": tool_id,
            "adapter_id": adapter_id,
            "adapter_version": adapter_version,
        }
    )


@dataclass(frozen=True)
class NativeTargetAuthorityAttestation:
    registry_identity: str
    adapter_id: str
    adapter_version: str
    authority_id: str
    member_id: str
    owner_id: str
    tool_id: str
    expected_target_anchor_id: str
    expected_target_anchor_fingerprint: str
    target_id: str
    target_revision: str
    material_locator: str
    material_media_type: str
    material_fingerprint: str
    items_fingerprint: str
    status: Literal["current", "stale", "failed", "not_run", "unverified"]
    detail: str = ""
    receipt_fingerprint: str = ""
    schema_version: str = NATIVE_TARGET_ATTESTATION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != NATIVE_TARGET_ATTESTATION_SCHEMA:
            raise ValueError("native target attestation requires the current schema")
        for name in (
            "adapter_id", "adapter_version", "authority_id", "member_id", "owner_id",
            "tool_id", "expected_target_anchor_id", "target_id", "target_revision", "material_locator",
            "material_media_type",
        ):
            _text(getattr(self, name), f"native target attestation {name}")
        for name in (
            "registry_identity",
            "expected_target_anchor_fingerprint",
            "items_fingerprint",
            "material_fingerprint",
        ):
            _sha(getattr(self, name), f"native target attestation {name}")
        if self.status not in {"current", "stale", "failed", "not_run", "unverified"}:
            raise ValueError("native target attestation status is not current")
        if self.status != "current" and not self.detail.strip():
            raise ValueError("non-current native target attestation requires a detail")
        if self.receipt_fingerprint:
            _sha(self.receipt_fingerprint, "native target attestation receipt fingerprint")
            if self.receipt_fingerprint != self.expected_fingerprint:
                raise ValueError("native target attestation receipt is stale or foreign")

    @property
    def expected_fingerprint(self) -> str:
        return _digest(self.to_dict(include_fingerprint=False))

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "NativeTargetAuthorityAttestation":
        allowed = {
            "schema_version", "registry_identity", "adapter_id", "adapter_version",
            "authority_id", "member_id", "owner_id", "tool_id", "target_id",
            "expected_target_anchor_id", "expected_target_anchor_fingerprint",
            "target_revision", "material_locator", "material_media_type",
            "material_fingerprint", "items_fingerprint", "status", "detail",
            "receipt_fingerprint",
        }
        if set(raw) != allowed:
            raise ValueError("native target attestation contains unknown or missing fields")
        return cls(
            schema_version=str(raw.get("schema_version", "")),
            registry_identity=_sha(raw.get("registry_identity"), "native target registry identity"),
            adapter_id=_text(raw.get("adapter_id"), "native target adapter id"),
            adapter_version=_text(raw.get("adapter_version"), "native target adapter version"),
            authority_id=_text(raw.get("authority_id"), "native target authority id"),
            member_id=_text(raw.get("member_id"), "native target member id"),
            owner_id=_text(raw.get("owner_id"), "native target owner id"),
            tool_id=_text(raw.get("tool_id"), "native target tool id"),
            expected_target_anchor_id=_text(
                raw.get("expected_target_anchor_id"),
                "native target expected anchor id",
            ),
            expected_target_anchor_fingerprint=_sha(
                raw.get("expected_target_anchor_fingerprint"),
                "native target expected anchor fingerprint",
            ),
            target_id=_text(raw.get("target_id"), "native target id"),
            target_revision=_text(raw.get("target_revision"), "native target revision"),
            material_locator=_text(raw.get("material_locator"), "native target material locator"),
            material_media_type=_text(raw.get("material_media_type"), "native target material media type"),
            material_fingerprint=_sha(raw.get("material_fingerprint"), "native target material fingerprint"),
            items_fingerprint=_sha(raw.get("items_fingerprint"), "native target items fingerprint"),
            status=str(raw.get("status", "")),  # type: ignore[arg-type]
            detail=str(raw.get("detail", "")),
            receipt_fingerprint=_sha(raw.get("receipt_fingerprint"), "native target receipt fingerprint"),
        )

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, object]:
        result: dict[str, object] = {
            "schema_version": self.schema_version,
            "registry_identity": self.registry_identity,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "authority_id": self.authority_id,
            "member_id": self.member_id,
            "owner_id": self.owner_id,
            "tool_id": self.tool_id,
            "expected_target_anchor_id": self.expected_target_anchor_id,
            "expected_target_anchor_fingerprint": self.expected_target_anchor_fingerprint,
            "target_id": self.target_id,
            "target_revision": self.target_revision,
            "material_locator": self.material_locator,
            "material_media_type": self.material_media_type,
            "material_fingerprint": self.material_fingerprint,
            "items_fingerprint": self.items_fingerprint,
            "status": self.status,
            "detail": self.detail,
        }
        if include_fingerprint:
            result["receipt_fingerprint"] = self.receipt_fingerprint
        return result


@dataclass(frozen=True)
class TargetPurposeAuthority:
    authority_id: str
    member_id: str
    owner_id: str
    request_id: str
    request_fingerprint: str
    input_id: str
    input_fingerprint: str
    target_id: str
    target_revision: str
    target_fingerprint: str
    tool_id: str
    tool_revision: str
    purpose_fingerprint: str
    items: tuple[TargetAuthorityItem, ...]
    expected_target_anchor: ExpectedTargetAnchor
    status: Literal["current", "stale", "failed", "not_run", "unverified"] = "current"
    native_attestation: NativeTargetAuthorityAttestation | None = None
    authority_fingerprint: str = ""
    schema_version: str = TARGET_PURPOSE_AUTHORITY_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != TARGET_PURPOSE_AUTHORITY_SCHEMA:
            raise ValueError("target purpose authority requires the current schema")
        for name in (
            "authority_id",
            "member_id",
            "owner_id",
            "request_id",
            "input_id",
            "target_id",
            "target_revision",
            "tool_id",
            "tool_revision",
        ):
            _text(getattr(self, name), f"target purpose authority {name}")
        for name in (
            "request_fingerprint",
            "input_fingerprint",
            "target_fingerprint",
            "purpose_fingerprint",
        ):
            _sha(getattr(self, name), f"target purpose authority {name}")
        if self.status not in {"current", "stale", "failed", "not_run", "unverified"}:
            raise ValueError("target purpose authority status is not current")
        if self.expected_target_anchor.member_id != self.member_id:
            raise ValueError("target purpose authority anchor belongs to another member")
        keys = [(item.kind, item.object_id) for item in self.items]
        if len(keys) != len(set(keys)) or (self.status == "current" and not keys):
            raise ValueError("current target purpose authority items must be non-empty and unique")
        if self.authority_fingerprint:
            _sha(self.authority_fingerprint, "target purpose authority fingerprint")
            if self.authority_fingerprint != self.expected_fingerprint:
                raise ValueError("target purpose authority fingerprint is stale or foreign")

    @property
    def expected_fingerprint(self) -> str:
        return _digest(self.to_dict(include_fingerprint=False))

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "TargetPurposeAuthority":
        allowed = {
            "schema_version",
            "authority_id",
            "member_id",
            "owner_id",
            "request_id",
            "request_fingerprint",
            "input_id",
            "input_fingerprint",
            "target_id",
            "target_revision",
            "target_fingerprint",
            "tool_id",
            "tool_revision",
            "purpose_fingerprint",
            "items",
            "expected_target_anchor",
            "status",
            "authority_fingerprint",
            "native_attestation",
        }
        if set(raw) != allowed:
            raise ValueError("target purpose authority contains unknown or missing fields")
        rows = raw.get("items")
        if not isinstance(rows, list) or any(not isinstance(item, Mapping) for item in rows):
            raise ValueError("target purpose authority items must be an array of objects")
        anchor = raw.get("expected_target_anchor")
        if not isinstance(anchor, Mapping):
            raise ValueError("target purpose authority requires one expected target anchor")
        return cls(
            schema_version=str(raw.get("schema_version", "")),
            authority_id=_text(raw.get("authority_id"), "target purpose authority id"),
            member_id=_text(raw.get("member_id"), "target purpose authority member"),
            owner_id=_text(raw.get("owner_id"), "target purpose authority owner"),
            request_id=_text(raw.get("request_id"), "target purpose authority request"),
            request_fingerprint=_sha(raw.get("request_fingerprint"), "target purpose authority request fingerprint"),
            input_id=_text(raw.get("input_id"), "target purpose authority input"),
            input_fingerprint=_sha(raw.get("input_fingerprint"), "target purpose authority input fingerprint"),
            target_id=_text(raw.get("target_id"), "target purpose authority target"),
            target_revision=_text(raw.get("target_revision"), "target purpose authority target revision"),
            target_fingerprint=_sha(raw.get("target_fingerprint"), "target purpose authority target fingerprint"),
            tool_id=_text(raw.get("tool_id"), "target purpose authority tool"),
            tool_revision=_text(raw.get("tool_revision"), "target purpose authority tool revision"),
            purpose_fingerprint=_sha(raw.get("purpose_fingerprint"), "target purpose authority purpose fingerprint"),
            items=tuple(TargetAuthorityItem.from_dict(item) for item in rows),
            expected_target_anchor=ExpectedTargetAnchor.from_dict(anchor),
            status=str(raw.get("status", "")),  # type: ignore[arg-type]
            native_attestation=(
                NativeTargetAuthorityAttestation.from_dict(raw["native_attestation"])
                if isinstance(raw.get("native_attestation"), Mapping)
                else None
            ),
            authority_fingerprint=_sha(raw.get("authority_fingerprint"), "target purpose authority fingerprint"),
        )

    def ids(self, kind: str, disposition: str = "required") -> set[str]:
        return {
            item.object_id
            for item in self.items
            if item.kind == kind and item.disposition == disposition
        }

    @property
    def unresolved_items(self) -> tuple[TargetAuthorityItem, ...]:
        return tuple(item for item in self.items if item.disposition == "unresolved")

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, object]:
        result: dict[str, object] = {
            "schema_version": self.schema_version,
            "authority_id": self.authority_id,
            "member_id": self.member_id,
            "owner_id": self.owner_id,
            "request_id": self.request_id,
            "request_fingerprint": self.request_fingerprint,
            "input_id": self.input_id,
            "input_fingerprint": self.input_fingerprint,
            "target_id": self.target_id,
            "target_revision": self.target_revision,
            "target_fingerprint": self.target_fingerprint,
            "tool_id": self.tool_id,
            "tool_revision": self.tool_revision,
            "purpose_fingerprint": self.purpose_fingerprint,
            "items": [item.to_dict() for item in sorted(self.items, key=lambda row: (row.kind, row.object_id))],
            "expected_target_anchor": self.expected_target_anchor.to_dict(),
            "status": self.status,
            "native_attestation": (
                self.native_attestation.to_dict() if self.native_attestation else None
            ),
        }
        if include_fingerprint:
            result["authority_fingerprint"] = self.authority_fingerprint
        return result


def _issue_replayed_target_authority(
    *,
    member_id: str,
    owner_id: str,
    tool_id: str,
    tool_revision: str,
    expected_target_anchor: ExpectedTargetAnchor,
    replay: NativeTargetMaterialReplay,
) -> TargetPurposeAuthority:
    """Private transport constructor for one already executed member replay.

    The four member-owned adapters are the only callers.  Keeping this carrier
    private prevents a caller from treating the shared transport layer as a
    generic semantic authority issuer.
    """

    registration = _CURRENT_NATIVE_ADAPTERS.get((member_id, owner_id, tool_id))
    if registration is None:
        raise ValueError("target authority adapter is not in the closed current registry")
    adapter_id, adapter_version = registration
    if (replay.adapter_id, replay.adapter_version) != registration:
        raise ValueError("native member replay does not match the closed adapter capability")
    if expected_target_anchor.member_id != member_id:
        raise ValueError("expected target anchor belongs to another member")
    authority_id = content_addressed_authority_id(
        member_id, expected_target_anchor.material_fingerprint
    )
    anchor_gaps = list(verify_expected_target_anchor(expected_target_anchor))
    anchor_checks = (
        (replay.material_locator == expected_target_anchor.material_locator, "expected-target-locator-mismatch"),
        (replay.material_media_type == expected_target_anchor.material_media_type, "expected-target-media-type-mismatch"),
        (replay.material_fingerprint == expected_target_anchor.material_fingerprint, "expected-target-material-mismatch"),
        (replay.request_id == expected_target_anchor.target_request_id, "expected-target-request-id-mismatch"),
        (replay.request_fingerprint == expected_target_anchor.target_request_fingerprint, "expected-target-request-mismatch"),
        (replay.target_id == expected_target_anchor.target_id, "expected-target-id-mismatch"),
        (replay.target_revision == expected_target_anchor.target_revision, "expected-target-revision-mismatch"),
    )
    anchor_gaps.extend(
        (code, expected_target_anchor.anchor_id)
        for ok, code in anchor_checks
        if not ok
    )
    if replay.status == "failed":
        authority_status: Literal["current", "stale", "failed", "unverified"] = "failed"
    elif replay.status == "unverified" or any(
        code.endswith("-unverified") for code, _ in anchor_gaps
    ):
        authority_status = "unverified"
    elif anchor_gaps:
        authority_status = "stale"
    else:
        authority_status = "current"
    base = TargetPurposeAuthority(
        authority_id=authority_id,
        member_id=member_id,
        owner_id=owner_id,
        request_id=replay.request_id,
        request_fingerprint=replay.request_fingerprint,
        input_id=replay.input_id,
        input_fingerprint=replay.input_fingerprint,
        target_id=replay.target_id,
        target_revision=replay.target_revision,
        target_fingerprint=replay.target_fingerprint,
        tool_id=tool_id,
        tool_revision=tool_revision,
        purpose_fingerprint=replay.purpose_fingerprint,
        items=tuple(replay.items),
        expected_target_anchor=expected_target_anchor,
        status=authority_status,
    )
    base = replace(base, authority_fingerprint=base.expected_fingerprint)
    items_fingerprint = replay.items_fingerprint
    registry_identity = _adapter_registry_identity(
        member_id, owner_id, tool_id, adapter_id, adapter_version
    )
    attestation = NativeTargetAuthorityAttestation(
        registry_identity=registry_identity,
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        authority_id=base.authority_id,
        member_id=member_id,
        owner_id=owner_id,
        tool_id=tool_id,
        expected_target_anchor_id=expected_target_anchor.anchor_id,
        expected_target_anchor_fingerprint=expected_target_anchor.anchor_fingerprint,
        target_id=base.target_id,
        target_revision=base.target_revision,
        material_locator=replay.material_locator,
        material_media_type=replay.material_media_type,
        material_fingerprint=replay.material_fingerprint,
        items_fingerprint=items_fingerprint,
        status=authority_status,
        detail=(
            replay.detail
            if replay.detail
            else "; ".join(code for code, _ in anchor_gaps)
        ),
    )
    attestation = replace(
        attestation, receipt_fingerprint=attestation.expected_fingerprint
    )
    result = replace(base, native_attestation=attestation, authority_fingerprint="")
    return replace(result, authority_fingerprint=result.expected_fingerprint)


def verify_registered_target_authority(
    authority: TargetPurposeAuthority,
    replay: NativeTargetMaterialReplay | None,
) -> tuple[tuple[str, str], ...]:
    """Compare a member's current raw-input replay with its stored receipt."""

    attestation = authority.native_attestation
    if attestation is None:
        return (("missing-native-target-attestation", authority.authority_id),)
    registration = _CURRENT_NATIVE_ADAPTERS.get(
        (authority.member_id, authority.owner_id, authority.tool_id)
    )
    if registration is None:
        return (("native-target-adapter-unregistered", authority.authority_id),)
    adapter_id, adapter_version = registration
    expected_registry = _adapter_registry_identity(
        authority.member_id,
        authority.owner_id,
        authority.tool_id,
        adapter_id,
        adapter_version,
    )
    anchor = authority.expected_target_anchor
    gaps = list(verify_expected_target_anchor(anchor))
    checks = (
        (attestation.registry_identity == expected_registry, "native-target-registry-stale"),
        ((attestation.adapter_id, attestation.adapter_version) == registration, "native-target-adapter-stale"),
        (
            authority.authority_id == content_addressed_authority_id(
                authority.member_id, anchor.material_fingerprint
            ),
            "native-target-authority-id-not-content-addressed",
        ),
        (attestation.authority_id == authority.authority_id, "native-target-authority-mismatch"),
        (attestation.member_id == authority.member_id, "native-target-member-mismatch"),
        (attestation.owner_id == authority.owner_id, "native-target-owner-mismatch"),
        (attestation.tool_id == authority.tool_id, "native-target-tool-mismatch"),
        (attestation.expected_target_anchor_id == anchor.anchor_id, "native-target-anchor-id-mismatch"),
        (attestation.expected_target_anchor_fingerprint == anchor.anchor_fingerprint, "native-target-anchor-fingerprint-mismatch"),
        (attestation.target_id == authority.target_id, "native-target-id-mismatch"),
        (attestation.target_revision == authority.target_revision, "native-target-revision-mismatch"),
        (attestation.items_fingerprint == _items_fingerprint(authority.items), "native-target-denominator-self-signed"),
        (attestation.status == "current", "native-target-attestation-not-current"),
        (attestation.receipt_fingerprint == attestation.expected_fingerprint, "native-target-attestation-receipt-mismatch"),
        (authority.status == "current", "target-authority-not-current"),
    )
    gaps.extend((code, authority.authority_id) for ok, code in checks if not ok)
    if replay is None:
        gaps.append(("native-target-material-replay-not-run", authority.authority_id))
        return tuple(gaps)
    if replay.status == "unverified":
        gaps.append(("native-target-material-unverified", replay.detail))
        return tuple(gaps)
    if replay.status == "failed":
        gaps.append(("native-target-material-failed", replay.detail))
        return tuple(gaps)
    replay_checks = (
        ((replay.adapter_id, replay.adapter_version) == registration, "native-target-adapter-replay-mismatch"),
        (replay.material_locator == attestation.material_locator, "native-target-material-locator-mismatch"),
        (replay.material_media_type == attestation.material_media_type, "native-target-material-media-type-mismatch"),
        (replay.material_fingerprint == attestation.material_fingerprint, "native-target-material-mismatch"),
        (replay.request_id == authority.request_id, "native-target-request-id-mismatch"),
        (replay.request_fingerprint == authority.request_fingerprint, "native-target-request-replay-mismatch"),
        (replay.input_id == authority.input_id, "native-target-input-id-mismatch"),
        (replay.input_fingerprint == authority.input_fingerprint, "native-target-input-replay-mismatch"),
        (replay.target_id == authority.target_id, "native-target-id-replay-mismatch"),
        (replay.target_revision == authority.target_revision, "native-target-revision-replay-mismatch"),
        (replay.target_fingerprint == authority.target_fingerprint, "native-target-target-replay-mismatch"),
        (replay.request_id == content_addressed_request_id(replay.request_fingerprint), "native-target-request-id-not-content-addressed"),
        (replay.target_revision == replay.target_fingerprint, "native-target-revision-not-content-addressed"),
        (replay.purpose_fingerprint == authority.purpose_fingerprint, "native-target-purpose-replay-mismatch"),
        (replay.items_fingerprint == attestation.items_fingerprint, "native-target-denominator-mismatch"),
        (replay.items_fingerprint == _items_fingerprint(authority.items), "native-target-denominator-mismatch"),
        (replay.material_locator == anchor.material_locator, "expected-target-locator-mismatch"),
        (replay.material_media_type == anchor.material_media_type, "expected-target-media-type-mismatch"),
        (replay.material_fingerprint == anchor.material_fingerprint, "expected-target-material-mismatch"),
        (replay.request_id == anchor.target_request_id, "expected-target-request-id-mismatch"),
        (replay.request_fingerprint == anchor.target_request_fingerprint, "expected-target-request-mismatch"),
        (replay.target_id == anchor.target_id, "expected-target-id-mismatch"),
        (replay.target_revision == anchor.target_revision, "expected-target-revision-mismatch"),
    )
    gaps.extend(
        (code, authority.authority_id)
        for ok, code in replay_checks
        if not ok
    )
    return tuple(gaps)


__all__ = [
    "TARGET_PURPOSE_AUTHORITY_SCHEMA",
    "NATIVE_TARGET_ATTESTATION_SCHEMA",
    "EXPECTED_TARGET_ANCHOR_SCHEMA",
    "EXPECTED_TARGET_ADMISSION_RECEIPT_SCHEMA",
    "ExpectedTargetAnchor",
    "NativeTargetMaterialReplay",
    "NativeTargetAuthorityAttestation",
    "TargetAuthorityItem",
    "TargetPurposeAuthority",
    "content_addressed_authority_id",
    "content_addressed_request_id",
    "read_target_material_bytes",
    "verify_expected_target_anchor",
    "expected_target_admission_signing_payload",
    "expected_target_portable_record",
    "verify_registered_target_authority",
]
