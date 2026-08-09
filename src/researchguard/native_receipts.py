"""Signed, immutable, current-only native receipt references.

The module is provider-neutral transport.  It never decides a Guard-domain
result and contains no signing key.  A deployment may register only an
externally held producer descriptor; without one, receipt qualification is
unverified.  Tests inject a separate fixture-only descriptor.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable, Literal, Mapping

from .target_authority import _verify_rsa_pkcs1v15_sha256


NATIVE_RECEIPT_SCHEMA = "researchguard.native-evidence-receipt.v3"
NATIVE_RECEIPT_LOCATOR_PREFIX = "researchguard-authority:native-receipt/"
NO_BEHAVIOR_MANIFEST_FINGERPRINT = "sha256:" + ("0" * 64)
TERMINAL_STATUSES = {
    "passed", "blocked", "failed", "stale", "skipped", "not_run", "non_terminal"
}
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")

# No repository key is a production trust root.  A deployment may install a
# descriptor only when its matching private key is held outside ResearchGuard.
_CURRENT_NATIVE_RECEIPT_PRODUCERS: dict[
    tuple[str, str, str, str, str, str], dict[str, object]
] = {}
_PORTABLE_NATIVE_RECEIPT_RECORDS: ContextVar[
    Mapping[tuple[str, str], Mapping[str, object]] | None
] = ContextVar("researchguard_portable_native_receipt_records", default=None)


def _digest(value: object) -> str:
    body = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _text(value: object, where: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{where} is required")
    return result


def _sha(value: object, where: str) -> str:
    result = _text(value, where)
    if not _SHA256.fullmatch(result):
        raise ValueError(f"{where} must be an exact sha256 fingerprint")
    return result


def _receipt_core(
    *,
    member_id: str,
    native_owner_id: str,
    producer_id: str,
    producer_version: str,
    checker_id: str,
    checker_version: str,
    checker_entrypoint: str,
    task_id: str,
    expected_target_anchor_id: str,
    expected_target_anchor_fingerprint: str,
    native_model_id: str,
    model_fingerprint: str,
    request_fingerprint: str,
    input_fingerprint: str,
    result_fingerprint: str,
    status: str,
    behavior_manifest_fingerprint: str = NO_BEHAVIOR_MANIFEST_FINGERPRINT,
) -> dict[str, str]:
    return {
        "member_id": member_id,
        "native_owner_id": native_owner_id,
        "producer_id": producer_id,
        "producer_version": producer_version,
        "checker_id": checker_id,
        "checker_version": checker_version,
        "checker_entrypoint": checker_entrypoint,
        "task_id": task_id,
        "expected_target_anchor_id": expected_target_anchor_id,
        "expected_target_anchor_fingerprint": expected_target_anchor_fingerprint,
        "native_model_id": native_model_id,
        "model_fingerprint": model_fingerprint,
        "request_fingerprint": request_fingerprint,
        "input_fingerprint": input_fingerprint,
        "result_fingerprint": result_fingerprint,
        "behavior_manifest_fingerprint": behavior_manifest_fingerprint,
        "status": status,
    }


def native_receipt_signing_payload(
    *, receipt_id: str, core: Mapping[str, str], signing_key_id: str
) -> bytes:
    """Return the canonical external-producer bytes for one named receipt."""

    material = {
        "schema_version": "researchguard.native-evidence-receipt-signature.v1",
        "receipt_id": receipt_id,
        "core": dict(core),
        "signing_key_id": signing_key_id,
    }
    body = json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return body


def _authority_root() -> Path:
    return (
        Path.home() / ".researchguard" / "authority" / "native-receipt-v3"
    ).resolve()


def _write_immutable(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(body)
    except FileExistsError:
        if path.read_bytes() != body:
            raise ValueError("immutable native receipt identity is already bound")


def _producer_key(core: Mapping[str, str]) -> tuple[str, str, str, str, str, str]:
    return (
        core["member_id"],
        core["native_owner_id"],
        core["producer_id"],
        core["producer_version"],
        core["checker_id"],
        core["checker_version"],
    )


def _public_key_fingerprint(descriptor: Mapping[str, object]) -> str:
    """Fingerprint the exact verification key without exposing private material."""

    return _digest(
        {
            "algorithm": str(descriptor.get("algorithm", "")),
            "public_exponent": int(descriptor.get("public_exponent", 0)),
            "public_modulus_hex": str(descriptor.get("public_modulus_hex", "")).lower(),
        }
    )


def _producer_descriptor_fingerprint(
    producer_key: tuple[str, str, str, str, str, str],
    descriptor: Mapping[str, object],
) -> str:
    """Bind one semantic checker route to one exact external signer descriptor."""

    return _digest(
        {
            "member_id": producer_key[0],
            "native_owner_id": producer_key[1],
            "producer_id": producer_key[2],
            "producer_version": producer_key[3],
            "checker_id": producer_key[4],
            "checker_version": producer_key[5],
            "checker_entrypoint": str(descriptor.get("checker_entrypoint", "")),
            "signature_algorithm": str(descriptor.get("algorithm", "")),
            "signing_key_id": str(descriptor.get("key_id", "")),
            "public_key_fingerprint": _public_key_fingerprint(descriptor),
        }
    )


def _portable_native_receipt_descriptor(
    record: Mapping[str, object],
) -> tuple[tuple[str, str, str, str, str, str], dict[str, object]]:
    descriptor = record.get("producer_descriptor")
    if not isinstance(descriptor, Mapping):
        raise ValueError("portable native-receipt producer descriptor is missing")
    key = (
        _text(descriptor.get("member_id"), "portable receipt member"),
        _text(descriptor.get("native_owner_id"), "portable receipt owner"),
        _text(descriptor.get("producer_id"), "portable receipt producer"),
        _text(
            descriptor.get("producer_version"), "portable receipt producer version"
        ),
        _text(descriptor.get("checker_id"), "portable receipt checker"),
        _text(
            descriptor.get("checker_version"), "portable receipt checker version"
        ),
    )
    return key, {
        "algorithm": _text(
            descriptor.get("signature_algorithm"),
            "portable receipt signature algorithm",
        ),
        "key_id": _text(descriptor.get("signing_key_id"), "portable receipt key"),
        "checker_entrypoint": _text(
            descriptor.get("checker_entrypoint"),
            "portable receipt checker entrypoint",
        ),
        "public_exponent": int(descriptor.get("public_exponent", 0)),
        "public_modulus_hex": _text(
            descriptor.get("public_modulus_hex"), "portable receipt public modulus"
        ).lower(),
    }


def _active_native_receipt_producers(
) -> Mapping[tuple[str, str, str, str, str, str], Mapping[str, object]]:
    records = _PORTABLE_NATIVE_RECEIPT_RECORDS.get()
    if records is None:
        return _CURRENT_NATIVE_RECEIPT_PRODUCERS
    result: dict[
        tuple[str, str, str, str, str, str], Mapping[str, object]
    ] = {}
    for record in records.values():
        key, descriptor = _portable_native_receipt_descriptor(record)
        prior = result.get(key)
        if prior is not None and dict(prior) != descriptor:
            raise ValueError("portable native-receipt producer identity is ambiguous")
        result[key] = descriptor
    return result


@contextmanager
def _portable_native_receipt_record_scope(
    records: Iterable[Mapping[str, object]],
):
    """Expose bundle receipt bytes to one replay without registry residue."""

    by_receipt: dict[tuple[str, str], Mapping[str, object]] = {}
    for record in records:
        reference_raw = record.get("reference")
        if not isinstance(reference_raw, Mapping):
            raise ValueError("portable native-receipt record has no reference")
        receipt = NativeReceiptReference.from_dict(reference_raw)
        key = (receipt.member_id, receipt.receipt_id)
        if key in by_receipt:
            raise ValueError("portable native-receipt identity is duplicated")
        by_receipt[key] = record
    token = _PORTABLE_NATIVE_RECEIPT_RECORDS.set(by_receipt)
    try:
        yield
    finally:
        _PORTABLE_NATIVE_RECEIPT_RECORDS.reset(token)


def _registered_producer_expectation(
    *,
    member_id: str,
    native_owner_id: str,
    checker_id: str,
    checker_version: str,
    checker_entrypoint: str,
) -> dict[str, str]:
    """Freeze one unambiguous current producer for a checker-owned expectation."""

    matches: list[tuple[tuple[str, str, str, str, str, str], Mapping[str, object]]] = []
    for key, descriptor in _active_native_receipt_producers().items():
        if (
            key[0] == member_id
            and key[1] == native_owner_id
            and key[4] == checker_id
            and key[5] == checker_version
            and descriptor.get("checker_entrypoint") == checker_entrypoint
        ):
            matches.append((key, descriptor))
    if len(matches) != 1:
        return {
            "producer_expectation_status": (
                "unregistered" if not matches else "ambiguous"
            ),
            "producer_id": "",
            "producer_version": "",
            "signature_algorithm": "",
            "signing_key_id": "",
            "public_key_fingerprint": "",
            "producer_descriptor_fingerprint": "",
        }
    key, descriptor = matches[0]
    return {
        "producer_expectation_status": "current",
        "producer_id": key[2],
        "producer_version": key[3],
        "signature_algorithm": str(descriptor.get("algorithm", "")),
        "signing_key_id": str(descriptor.get("key_id", "")),
        "public_key_fingerprint": _public_key_fingerprint(descriptor),
        "producer_descriptor_fingerprint": _producer_descriptor_fingerprint(
            key, descriptor
        ),
    }


def _verify_signature(
    receipt_id: str, core: Mapping[str, str], signing_key_id: str, signature: str
) -> bool:
    descriptor = _active_native_receipt_producers().get(_producer_key(core))
    if descriptor is None:
        return False
    if descriptor.get("algorithm") != "rsa-pkcs1v15-sha256":
        return False
    if descriptor.get("key_id") != signing_key_id:
        return False
    if descriptor.get("checker_entrypoint") != core.get("checker_entrypoint"):
        return False
    body = native_receipt_signing_payload(
        receipt_id=receipt_id, core=core, signing_key_id=signing_key_id
    )
    return _verify_rsa_pkcs1v15_sha256(body, signature, descriptor)


def _binding_key(core: Mapping[str, str]) -> str:
    return _digest(
        {
            key: core[key]
            for key in (
                "member_id", "native_owner_id", "producer_id", "producer_version",
                "checker_id", "checker_version", "checker_entrypoint", "task_id",
                "expected_target_anchor_id", "expected_target_anchor_fingerprint",
                "native_model_id", "model_fingerprint", "request_fingerprint",
                "input_fingerprint", "behavior_manifest_fingerprint",
            )
        }
    ).removeprefix("sha256:")


def _receipt_identity_key(member_id: str, receipt_id: str) -> str:
    """Return the safe filename key for one globally immutable member receipt id."""

    return _digest(
        {
            "member_id": _text(member_id, "native receipt identity member"),
            "receipt_id": _text(receipt_id, "native receipt identity id"),
        }
    ).removeprefix("sha256:")


@dataclass(frozen=True)
class NativeReceiptReference:
    receipt_id: str
    member_id: str
    native_owner_id: str
    producer_id: str
    producer_version: str
    checker_id: str
    checker_version: str
    checker_entrypoint: str
    task_id: str
    expected_target_anchor_id: str
    expected_target_anchor_fingerprint: str
    native_model_id: str
    model_fingerprint: str
    request_fingerprint: str
    input_fingerprint: str
    result_fingerprint: str
    behavior_manifest_fingerprint: str
    status: Literal[
        "passed", "blocked", "failed", "stale", "skipped", "not_run", "non_terminal"
    ]
    producer_locator: str
    receipt_fingerprint: str
    signing_key_id: str
    signature_algorithm: str
    public_key_fingerprint: str
    producer_descriptor_fingerprint: str
    producer_signature: str
    schema_version: str = NATIVE_RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != NATIVE_RECEIPT_SCHEMA:
            raise ValueError("native receipt reference requires the current schema")
        for name in (
            "receipt_id", "member_id", "native_owner_id", "producer_id",
            "producer_version", "checker_id", "checker_version",
            "checker_entrypoint", "task_id", "expected_target_anchor_id",
            "native_model_id", "producer_locator", "signing_key_id",
            "signature_algorithm", "producer_signature",
        ):
            _text(getattr(self, name), f"native receipt {name}")
        for name in (
            "expected_target_anchor_fingerprint", "model_fingerprint",
            "request_fingerprint", "input_fingerprint", "result_fingerprint",
            "behavior_manifest_fingerprint",
            "receipt_fingerprint",
            "public_key_fingerprint", "producer_descriptor_fingerprint",
        ):
            _sha(getattr(self, name), f"native receipt {name}")
        if self.status not in TERMINAL_STATUSES:
            raise ValueError("native receipt status is not current")
        if not self.producer_locator.startswith(NATIVE_RECEIPT_LOCATOR_PREFIX):
            raise ValueError("native receipt locator is outside the closed authority root")

    @property
    def core(self) -> dict[str, str]:
        return _receipt_core(
            member_id=self.member_id,
            native_owner_id=self.native_owner_id,
            producer_id=self.producer_id,
            producer_version=self.producer_version,
            checker_id=self.checker_id,
            checker_version=self.checker_version,
            checker_entrypoint=self.checker_entrypoint,
            task_id=self.task_id,
            expected_target_anchor_id=self.expected_target_anchor_id,
            expected_target_anchor_fingerprint=self.expected_target_anchor_fingerprint,
            native_model_id=self.native_model_id,
            model_fingerprint=self.model_fingerprint,
            request_fingerprint=self.request_fingerprint,
            input_fingerprint=self.input_fingerprint,
            result_fingerprint=self.result_fingerprint,
            status=self.status,
            behavior_manifest_fingerprint=self.behavior_manifest_fingerprint,
        )

    @property
    def receipt_payload(self) -> dict[str, object]:
        return {
            "schema_version": NATIVE_RECEIPT_SCHEMA,
            "receipt_id": self.receipt_id,
            "core": self.core,
            "signing_key_id": self.signing_key_id,
            "producer_signature": self.producer_signature,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "NativeReceiptReference":
        fields = {
            "schema_version", "receipt_id", "member_id", "native_owner_id",
            "producer_id", "producer_version", "checker_id", "checker_version",
            "checker_entrypoint", "task_id", "expected_target_anchor_id",
            "expected_target_anchor_fingerprint", "native_model_id",
            "model_fingerprint", "request_fingerprint", "input_fingerprint",
            "result_fingerprint", "behavior_manifest_fingerprint", "status", "producer_locator",
            "receipt_fingerprint", "signing_key_id", "signature_algorithm",
            "public_key_fingerprint", "producer_descriptor_fingerprint",
            "producer_signature",
        }
        if set(raw) != fields:
            raise ValueError("native receipt contains unknown or missing current fields")
        return cls(**{key: str(raw.get(key, "")) for key in fields})  # type: ignore[arg-type]

    def to_dict(self) -> dict[str, str]:
        return {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            **self.core,
            "producer_locator": self.producer_locator,
            "receipt_fingerprint": self.receipt_fingerprint,
            "signing_key_id": self.signing_key_id,
            "signature_algorithm": self.signature_algorithm,
            "public_key_fingerprint": self.public_key_fingerprint,
            "producer_descriptor_fingerprint": self.producer_descriptor_fingerprint,
            "producer_signature": self.producer_signature,
        }


@dataclass(frozen=True)
class NativeReceiptExpectation:
    """Exact execution identity required from one immutable native receipt.

    Expectations are checker-owned values, never values copied from the
    submitted reference.  This keeps a coherent caller-authored id/hash bundle
    from becoming evidence merely because its fields agree with each other.
    """

    receipt_id: str
    member_id: str
    native_owner_id: str
    checker_id: str
    checker_version: str
    checker_entrypoint: str
    task_id: str
    expected_target_anchor_id: str
    expected_target_anchor_fingerprint: str
    native_model_id: str
    model_fingerprint: str
    request_fingerprint: str
    input_fingerprint: str
    result_fingerprint: str
    behavior_manifest_fingerprint: str = NO_BEHAVIOR_MANIFEST_FINGERPRINT
    status: str = "passed"
    producer_expectation_status: Literal["current", "unregistered", "ambiguous"] = (
        "unregistered"
    )
    producer_id: str = ""
    producer_version: str = ""
    signature_algorithm: str = ""
    signing_key_id: str = ""
    public_key_fingerprint: str = ""
    producer_descriptor_fingerprint: str = ""


def native_receipt_expectation(**identity: str) -> NativeReceiptExpectation:
    """Build one checker-owned expectation with an exact external signer freeze."""

    producer = _registered_producer_expectation(
        member_id=identity["member_id"],
        native_owner_id=identity["native_owner_id"],
        checker_id=identity["checker_id"],
        checker_version=identity["checker_version"],
        checker_entrypoint=identity["checker_entrypoint"],
    )
    return NativeReceiptExpectation(**identity, **producer)  # type: ignore[arg-type]


def resolve_expected_native_receipts(
    receipts: Iterable[NativeReceiptReference],
    expectations: Iterable[NativeReceiptExpectation],
) -> tuple[tuple[str, str], ...]:
    """Resolve one exact receipt per checker-owned expectation.

    The set is closed: duplicate ids and undeclared receipts are visible gaps,
    while a missing receipt never falls back to an inline hash or in-memory
    result object.
    """

    supplied = tuple(receipts)
    required = tuple(expectations)
    gaps: list[tuple[str, str]] = []
    by_id: dict[str, list[NativeReceiptReference]] = {}
    for receipt in supplied:
        by_id.setdefault(receipt.receipt_id, []).append(receipt)
    expected_ids = {item.receipt_id for item in required}
    for receipt_id, rows in sorted(by_id.items()):
        if receipt_id not in expected_ids:
            gaps.append(("native-receipt-foreign", receipt_id))
        if len(rows) != 1:
            gaps.append(("native-receipt-owner-count", f"{receipt_id}:{len(rows)}"))
    for expected in required:
        rows = by_id.get(expected.receipt_id, [])
        if len(rows) != 1:
            if not rows:
                gaps.append(("native-receipt-missing", expected.receipt_id))
            continue
        receipt = rows[0]
        if expected.producer_expectation_status != "current":
            gaps.append(
                (
                    f"native-receipt-producer-expectation-{expected.producer_expectation_status}",
                    expected.receipt_id,
                )
            )
        descriptor_key = _producer_key(receipt.core)
        descriptor = _active_native_receipt_producers().get(descriptor_key)
        actual_algorithm = str(descriptor.get("algorithm", "")) if descriptor else ""
        actual_key_id = str(descriptor.get("key_id", "")) if descriptor else ""
        actual_public_key_fingerprint = (
            _public_key_fingerprint(descriptor) if descriptor else ""
        )
        actual_descriptor_fingerprint = (
            _producer_descriptor_fingerprint(descriptor_key, descriptor)
            if descriptor
            else ""
        )
        checks = (
            (receipt.member_id, expected.member_id, "member"),
            (receipt.native_owner_id, expected.native_owner_id, "owner"),
            (receipt.producer_id, expected.producer_id, "producer"),
            (receipt.producer_version, expected.producer_version, "producer-version"),
            (receipt.signature_algorithm, expected.signature_algorithm, "signature-algorithm"),
            (receipt.signing_key_id, expected.signing_key_id, "signing-key"),
            (
                receipt.public_key_fingerprint,
                expected.public_key_fingerprint,
                "public-key-fingerprint",
            ),
            (
                receipt.producer_descriptor_fingerprint,
                expected.producer_descriptor_fingerprint,
                "producer-descriptor-fingerprint",
            ),
            (receipt.checker_id, expected.checker_id, "checker"),
            (receipt.checker_version, expected.checker_version, "checker-version"),
            (receipt.checker_entrypoint, expected.checker_entrypoint, "entrypoint"),
            (receipt.task_id, expected.task_id, "task"),
            (receipt.expected_target_anchor_id, expected.expected_target_anchor_id, "anchor"),
            (
                receipt.expected_target_anchor_fingerprint,
                expected.expected_target_anchor_fingerprint,
                "anchor-fingerprint",
            ),
            (receipt.native_model_id, expected.native_model_id, "model"),
            (receipt.model_fingerprint, expected.model_fingerprint, "model-fingerprint"),
            (receipt.request_fingerprint, expected.request_fingerprint, "request"),
            (receipt.input_fingerprint, expected.input_fingerprint, "input"),
            (receipt.result_fingerprint, expected.result_fingerprint, "result"),
            (
                receipt.behavior_manifest_fingerprint,
                expected.behavior_manifest_fingerprint,
                "behavior-manifest-fingerprint",
            ),
            (receipt.status, expected.status, "status"),
        )
        for actual, wanted, field in checks:
            if actual != wanted:
                gaps.append(
                    (
                        f"native-receipt-{field}-mismatch",
                        f"{expected.receipt_id}:{actual}",
                    )
                )
        gaps.extend(resolve_native_receipt_reference(receipt))
    return tuple(sorted(set(gaps)))


def _admit_signed_native_receipt(
    *, receipt_id: str, core: Mapping[str, str], signing_key_id: str, producer_signature: str
) -> NativeReceiptReference:
    """Verify and persist one externally signed member-native receipt."""

    receipt_id = _text(receipt_id, "native receipt id")
    if not _verify_signature(receipt_id, core, signing_key_id, producer_signature):
        raise ValueError("native receipt external producer signature is invalid")
    producer_key = _producer_key(core)
    descriptor = _CURRENT_NATIVE_RECEIPT_PRODUCERS[producer_key]
    payload = {
        "schema_version": NATIVE_RECEIPT_SCHEMA,
        "receipt_id": receipt_id,
        "core": dict(core),
        "signing_key_id": signing_key_id,
        "producer_signature": producer_signature,
    }
    body = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    fingerprint = "sha256:" + hashlib.sha256(body).hexdigest()
    suffix = fingerprint.removeprefix("sha256:")
    locator = f"{NATIVE_RECEIPT_LOCATOR_PREFIX}{core['member_id']}/{suffix}"
    root = _authority_root()
    identity_binding = {
        "member_id": core["member_id"],
        "receipt_id": receipt_id,
        "receipt_fingerprint": fingerprint,
    }
    identity_binding_body = json.dumps(
        identity_binding, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    _write_immutable(
        root
        / "identity-bindings"
        / f"{_receipt_identity_key(core['member_id'], receipt_id)}.json",
        identity_binding_body,
    )
    _write_immutable(root / "receipts" / core["member_id"] / f"{suffix}.json", body)
    binding = {"receipt_id": receipt_id, "receipt_fingerprint": fingerprint}
    binding_body = json.dumps(
        binding, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    _write_immutable(root / "bindings" / f"{_binding_key(core)}.json", binding_body)
    return NativeReceiptReference(
        receipt_id=receipt_id,
        producer_locator=locator,
        receipt_fingerprint=fingerprint,
        signing_key_id=signing_key_id,
        signature_algorithm=str(descriptor["algorithm"]),
        public_key_fingerprint=_public_key_fingerprint(descriptor),
        producer_descriptor_fingerprint=_producer_descriptor_fingerprint(
            producer_key, descriptor
        ),
        producer_signature=producer_signature,
        **dict(core),
    )


def resolve_native_receipt_reference(
    receipt: NativeReceiptReference,
) -> tuple[tuple[str, str], ...]:
    """Reopen bytes, authenticate producer, and replay the execution binding."""

    portable_records = _PORTABLE_NATIVE_RECEIPT_RECORDS.get()
    if portable_records is not None:
        record = portable_records.get((receipt.member_id, receipt.receipt_id))
        if record is None:
            return (("portable-native-receipt-record-missing", receipt.receipt_id),)
        return _verify_portable_native_receipt_record(receipt, record)

    gaps: list[tuple[str, str]] = []
    descriptor_key = _producer_key(receipt.core)
    descriptor = _CURRENT_NATIVE_RECEIPT_PRODUCERS.get(descriptor_key)
    if descriptor is not None:
        if receipt.signature_algorithm != str(descriptor.get("algorithm", "")):
            gaps.append(("native-receipt-signature-algorithm-mismatch", receipt.receipt_id))
        if receipt.public_key_fingerprint != _public_key_fingerprint(descriptor):
            gaps.append(("native-receipt-public-key-fingerprint-mismatch", receipt.receipt_id))
        if receipt.producer_descriptor_fingerprint != _producer_descriptor_fingerprint(
            descriptor_key, descriptor
        ):
            gaps.append(("native-receipt-producer-descriptor-fingerprint-mismatch", receipt.receipt_id))
    if not _verify_signature(
        receipt.receipt_id,
        receipt.core,
        receipt.signing_key_id,
        receipt.producer_signature,
    ):
        gaps.append(("native-receipt-producer-signature-invalid", receipt.receipt_id))
    prefix = f"{NATIVE_RECEIPT_LOCATOR_PREFIX}{receipt.member_id}/"
    suffix = receipt.producer_locator.removeprefix(prefix)
    if not receipt.producer_locator.startswith(prefix) or not re.fullmatch(
        r"[0-9a-f]{64}", suffix
    ):
        gaps.append(("native-receipt-locator-invalid", receipt.receipt_id))
        return tuple(gaps)
    path = _authority_root() / "receipts" / receipt.member_id / f"{suffix}.json"
    try:
        body = path.read_bytes()
    except OSError as exc:
        gaps.append(("native-receipt-unresolved", str(exc)))
        return tuple(gaps)
    fingerprint = "sha256:" + hashlib.sha256(body).hexdigest()
    if fingerprint != receipt.receipt_fingerprint or suffix != fingerprint[7:]:
        gaps.append(("native-receipt-bytes-mismatch", receipt.receipt_id))
    try:
        raw = json.loads(body.decode("utf-8"))
    except Exception as exc:
        gaps.append(("native-receipt-invalid", str(exc)))
    else:
        if raw != receipt.receipt_payload:
            gaps.append(("native-receipt-identity-mismatch", receipt.receipt_id))
    binding_path = _authority_root() / "bindings" / f"{_binding_key(receipt.core)}.json"
    try:
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
    except Exception as exc:
        gaps.append(("native-receipt-binding-unresolved", str(exc)))
    else:
        expected = {
            "receipt_id": receipt.receipt_id,
            "receipt_fingerprint": receipt.receipt_fingerprint,
        }
        if binding != expected:
            gaps.append(("native-receipt-binding-mismatch", receipt.receipt_id))
    identity_binding_path = (
        _authority_root()
        / "identity-bindings"
        / f"{_receipt_identity_key(receipt.member_id, receipt.receipt_id)}.json"
    )
    try:
        identity_binding = json.loads(
            identity_binding_path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        gaps.append(("native-receipt-identity-binding-unresolved", str(exc)))
    else:
        expected_identity_binding = {
            "member_id": receipt.member_id,
            "receipt_id": receipt.receipt_id,
            "receipt_fingerprint": receipt.receipt_fingerprint,
        }
        if identity_binding != expected_identity_binding:
            gaps.append(
                ("native-receipt-identity-binding-mismatch", receipt.receipt_id)
            )
    return tuple(gaps)


def _verify_portable_native_receipt_record(
    receipt: NativeReceiptReference,
    record: Mapping[str, object],
) -> tuple[tuple[str, str], ...]:
    """Verify one bundle-carried receipt without consulting the user profile.

    This is the portable equivalent of reopening the immutable authority files.
    It verifies the exact signed bytes and producer identity carried by the
    bundle; the caller still has to license the producer descriptor separately.
    """

    expected_fields = {"reference", "receipt_payload", "producer_descriptor"}
    if set(record) != expected_fields:
        return (("portable-native-receipt-record-invalid", receipt.receipt_id),)
    reference_raw = record.get("reference")
    receipt_payload = record.get("receipt_payload")
    descriptor_raw = record.get("producer_descriptor")
    if not isinstance(reference_raw, Mapping) or not isinstance(
        receipt_payload, Mapping
    ) or not isinstance(descriptor_raw, Mapping):
        return (("portable-native-receipt-record-invalid", receipt.receipt_id),)
    try:
        carried_receipt = NativeReceiptReference.from_dict(reference_raw)
        producer_key, descriptor = _portable_native_receipt_descriptor(record)
    except (TypeError, ValueError) as exc:
        return (("portable-native-receipt-record-invalid", str(exc)),)

    gaps: list[tuple[str, str]] = []
    if carried_receipt.to_dict() != receipt.to_dict():
        gaps.append(("portable-native-receipt-reference-mismatch", receipt.receipt_id))
    if dict(receipt_payload) != receipt.receipt_payload:
        gaps.append(("portable-native-receipt-payload-mismatch", receipt.receipt_id))
    receipt_body = json.dumps(
        receipt.receipt_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    fingerprint = "sha256:" + hashlib.sha256(receipt_body).hexdigest()
    if fingerprint != receipt.receipt_fingerprint:
        gaps.append(("portable-native-receipt-fingerprint-mismatch", receipt.receipt_id))
    prefix = f"{NATIVE_RECEIPT_LOCATOR_PREFIX}{receipt.member_id}/"
    suffix = receipt.producer_locator.removeprefix(prefix)
    if (
        not receipt.producer_locator.startswith(prefix)
        or suffix != fingerprint.removeprefix("sha256:")
    ):
        gaps.append(("portable-native-receipt-locator-invalid", receipt.receipt_id))

    public_key_fingerprint = _public_key_fingerprint(descriptor)
    descriptor_fingerprint = _producer_descriptor_fingerprint(
        producer_key, descriptor
    )
    descriptor_checks = (
        (producer_key, _producer_key(receipt.core)),
        (descriptor.get("algorithm"), receipt.signature_algorithm),
        (descriptor.get("key_id"), receipt.signing_key_id),
        (descriptor.get("checker_entrypoint"), receipt.checker_entrypoint),
        (descriptor_raw.get("public_key_fingerprint"), public_key_fingerprint),
        (
            descriptor_raw.get("producer_descriptor_fingerprint"),
            descriptor_fingerprint,
        ),
        (receipt.public_key_fingerprint, public_key_fingerprint),
        (receipt.producer_descriptor_fingerprint, descriptor_fingerprint),
    )
    if any(actual != expected for actual, expected in descriptor_checks):
        gaps.append(
            (
                "portable-native-receipt-producer-descriptor-mismatch",
                receipt.receipt_id,
            )
        )
    if not _verify_rsa_pkcs1v15_sha256(
        native_receipt_signing_payload(
            receipt_id=receipt.receipt_id,
            core=receipt.core,
            signing_key_id=receipt.signing_key_id,
        ),
        receipt.producer_signature,
        descriptor,
    ):
        gaps.append(("portable-native-receipt-signature-invalid", receipt.receipt_id))
    return tuple(sorted(set(gaps)))


def native_receipt_portable_record(
    receipt: NativeReceiptReference,
) -> dict[str, object]:
    """Return exact signed receipt bytes and public producer identity for transport."""

    gaps = resolve_native_receipt_reference(receipt)
    if gaps:
        raise ValueError(f"native receipt is not portable: {gaps[0][0]}:{gaps[0][1]}")
    producer_key = _producer_key(receipt.core)
    descriptor = _CURRENT_NATIVE_RECEIPT_PRODUCERS[producer_key]
    return {
        "reference": receipt.to_dict(),
        "receipt_payload": receipt.receipt_payload,
        "producer_descriptor": {
            "member_id": producer_key[0],
            "native_owner_id": producer_key[1],
            "producer_id": producer_key[2],
            "producer_version": producer_key[3],
            "checker_id": producer_key[4],
            "checker_version": producer_key[5],
            "checker_entrypoint": str(descriptor["checker_entrypoint"]),
            "signature_algorithm": str(descriptor["algorithm"]),
            "signing_key_id": str(descriptor["key_id"]),
            "public_exponent": int(descriptor["public_exponent"]),
            "public_modulus_hex": str(descriptor["public_modulus_hex"]).lower(),
            "public_key_fingerprint": receipt.public_key_fingerprint,
            "producer_descriptor_fingerprint": receipt.producer_descriptor_fingerprint,
        },
    }


__all__ = [
    "NATIVE_RECEIPT_SCHEMA",
    "NO_BEHAVIOR_MANIFEST_FINGERPRINT",
    "NativeReceiptExpectation",
    "NativeReceiptReference",
    "native_receipt_expectation",
    "native_receipt_portable_record",
    "native_receipt_signing_payload",
    "resolve_expected_native_receipts",
    "resolve_native_receipt_reference",
]
