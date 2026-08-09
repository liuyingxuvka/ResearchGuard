"""Test/developer-only signer for independent external scope authorities.

The private exponent remains outside ``src/`` and packaged resources.  Runtime
ResearchGuard can validate a portable public descriptor but cannot produce an
authority or establish trust in it.
"""

from __future__ import annotations

import hashlib
import json
from typing import Mapping

from researchguard.external_scope_authority import (
    assemble_external_scope_authority_record,
    external_scope_authority_signing_payload,
)
from target_material_fixtures import (
    _TEST_ADMISSION_MODULUS_HEX,
    _TEST_ADMISSION_PRIVATE_EXPONENT_HEX,
)


SCOPE_AUTHORITY_TEST_PRODUCER_DESCRIPTOR = {
    "producer_id": "researchguard.tests.external-scope-authority",
    "producer_version": "1",
    "signature_algorithm": "rsa-pkcs1v15-sha256",
    "signing_key_id": "researchguard-test-external-scope-authority-2026-01",
    "public_exponent": 65537,
    "public_modulus_hex": _TEST_ADMISSION_MODULUS_HEX,
}


def _digest(value: object) -> str:
    body = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _sign(payload: bytes) -> str:
    modulus = int(_TEST_ADMISSION_MODULUS_HEX, 16)
    private_exponent = int(_TEST_ADMISSION_PRIVATE_EXPONENT_HEX, 16)
    width = (modulus.bit_length() + 7) // 8
    digest_info = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(
        payload
    ).digest()
    encoded = (
        b"\x00\x01"
        + (b"\xff" * (width - len(digest_info) - 3))
        + b"\x00"
        + digest_info
    )
    signature = pow(int.from_bytes(encoded, "big"), private_exponent, modulus).to_bytes(
        width, "big"
    )
    return "rsa-pkcs1v15-sha256:" + signature.hex()


def signed_scope_authority(authority: Mapping[str, object]) -> dict[str, object]:
    authority_fingerprint = _digest(authority)
    descriptor_fingerprint = _digest(SCOPE_AUTHORITY_TEST_PRODUCER_DESCRIPTOR)
    payload = external_scope_authority_signing_payload(
        authority_fingerprint=authority_fingerprint,
        producer_descriptor_fingerprint=descriptor_fingerprint,
        signing_key_id=str(SCOPE_AUTHORITY_TEST_PRODUCER_DESCRIPTOR["signing_key_id"]),
    )
    return assemble_external_scope_authority_record(
        authority,
        SCOPE_AUTHORITY_TEST_PRODUCER_DESCRIPTOR,
        authority_signature=_sign(payload),
    )


__all__ = [
    "SCOPE_AUTHORITY_TEST_PRODUCER_DESCRIPTOR",
    "signed_scope_authority",
]
