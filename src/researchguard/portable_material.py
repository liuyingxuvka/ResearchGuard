"""Context-local native material carried by one portable qualification.

Portable records are integrity-bound transport, not trust roots.  The scope is
read-only and is always reset, so installed-wheel replay never registers a
producer or writes bundle bytes into the user profile.
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
from typing import Iterable, Mapping


_PORTABLE_NATIVE_MATERIALS: ContextVar[
    Mapping[tuple[str, str], bytes] | None
] = ContextVar("researchguard_portable_native_materials", default=None)
_PORTABLE_NATIVE_MATERIAL_IDS: ContextVar[
    Mapping[tuple[str, str], bytes] | None
] = ContextVar("researchguard_portable_native_material_ids", default=None)


def portable_native_material_record(
    *, member_id: str, material_id: str, media_type: str, body: bytes
) -> dict[str, object]:
    fingerprint = "sha256:" + hashlib.sha256(body).hexdigest()
    return {
        "member_id": str(member_id),
        "material_id": str(material_id),
        "media_type": str(media_type),
        "material_fingerprint": fingerprint,
        "material_bytes_b64": base64.b64encode(body).decode("ascii"),
    }


def verify_portable_native_material_record(
    record: Mapping[str, object],
) -> tuple[tuple[str, str], ...]:
    fields = {
        "member_id",
        "material_id",
        "media_type",
        "material_fingerprint",
        "material_bytes_b64",
    }
    if set(record) != fields:
        return (("portable-native-material-record-invalid", "field-denominator"),)
    member_id = str(record.get("member_id", "")).strip()
    material_id = str(record.get("material_id", "")).strip()
    media_type = str(record.get("media_type", "")).strip()
    fingerprint = str(record.get("material_fingerprint", "")).strip()
    if not member_id or not material_id or not media_type:
        return (("portable-native-material-record-invalid", material_id),)
    try:
        body = base64.b64decode(
            str(record.get("material_bytes_b64", "")).encode("ascii"),
            validate=True,
        )
    except (UnicodeError, ValueError):
        return (("portable-native-material-record-invalid", material_id),)
    actual = "sha256:" + hashlib.sha256(body).hexdigest()
    if fingerprint != actual:
        return (("portable-native-material-fingerprint-mismatch", material_id),)
    return ()


@contextmanager
def portable_native_material_scope(records: Iterable[Mapping[str, object]]):
    by_identity: dict[tuple[str, str], bytes] = {}
    by_material_id: dict[tuple[str, str], bytes] = {}
    for record in records:
        gaps = verify_portable_native_material_record(record)
        if gaps:
            raise ValueError(f"{gaps[0][0]}:{gaps[0][1]}")
        member_id = str(record["member_id"])
        fingerprint = str(record["material_fingerprint"])
        key = (member_id, fingerprint)
        body = base64.b64decode(str(record["material_bytes_b64"]).encode("ascii"))
        previous = by_identity.get(key)
        if previous is not None and previous != body:
            raise ValueError("portable native material identity is ambiguous")
        by_identity[key] = body
        material_key = (member_id, str(record["material_id"]))
        previous_by_id = by_material_id.get(material_key)
        if previous_by_id is not None and previous_by_id != body:
            raise ValueError("portable native material id is ambiguous")
        by_material_id[material_key] = body
    token = _PORTABLE_NATIVE_MATERIALS.set(by_identity)
    id_token = _PORTABLE_NATIVE_MATERIAL_IDS.set(by_material_id)
    try:
        yield
    finally:
        _PORTABLE_NATIVE_MATERIAL_IDS.reset(id_token)
        _PORTABLE_NATIVE_MATERIALS.reset(token)


def portable_native_material_bytes(
    *, member_id: str, material_fingerprint: str
) -> bytes | None:
    records = _PORTABLE_NATIVE_MATERIALS.get()
    if records is None:
        return None
    key = (str(member_id), str(material_fingerprint))
    if key not in records:
        raise ValueError(
            f"portable native material is missing:{member_id}:{material_fingerprint}"
        )
    return records[key]


def portable_native_material_bytes_by_id(
    *, member_id: str, material_id: str
) -> bytes | None:
    """Return one exact bundle-carried material by its semantic owner id.

    ``None`` means no portable qualification scope is active.  An active scope
    with a missing id is a closed-denominator failure, never permission to read
    a local fallback file.
    """

    records = _PORTABLE_NATIVE_MATERIAL_IDS.get()
    if records is None:
        return None
    key = (str(member_id), str(material_id))
    if key not in records:
        raise ValueError(f"portable native material id is missing:{member_id}:{material_id}")
    return records[key]


__all__ = [
    "portable_native_material_bytes",
    "portable_native_material_bytes_by_id",
    "portable_native_material_record",
    "portable_native_material_scope",
    "verify_portable_native_material_record",
]
