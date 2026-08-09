"""Canonical ResearchGuard suite identity."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from . import MEMBER_IDS, SUITE_ID, __version__
from .model_envelope import HANDOFF_FIELD_CONTRACT_SCHEMA, MEMBER_MODEL_ENVELOPE_SCHEMA


_PACKAGE_ROOT = Path(__file__).resolve().parent
_IGNORED_PARTS = {"__pycache__"}
_IGNORED_SUFFIXES = {".pyc", ".pyo"}
_CONTENT_ADDRESSED_RESOURCE_ROOTS = {
    ("resources", "external_domain_dna"),
}


def governed_file_manifest() -> tuple[tuple[str, str], ...]:
    """Return the deterministic content manifest for the installed runtime."""

    rows: list[tuple[str, str]] = []
    for path in sorted(_PACKAGE_ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(_PACKAGE_ROOT)
        if any(part in _IGNORED_PARTS for part in relative.parts):
            continue
        if path.suffix.lower() in _IGNORED_SUFFIXES:
            continue
        if any(
            relative.parts[: len(root_parts)] == root_parts
            for root_parts in _CONTENT_ADDRESSED_RESOURCE_ROOTS
        ):
            # These generated model packages carry their own exact content
            # fingerprints and embed the suite identity they were produced
            # against. Including them here would create a self-referential
            # hash whose value changes every time the same model is rebuilt.
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append((relative.as_posix(), digest))
    return tuple(rows)


def suite_fingerprint() -> str:
    """Return one content-addressed identity for all native members."""

    digest = hashlib.sha256()
    digest.update(f"{SUITE_ID}\0{__version__}\0".encode("utf-8"))
    for relative, file_digest in governed_file_manifest():
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def suite_identity() -> dict[str, Any]:
    """Return the canonical machine-readable suite identity."""

    return {
        "suite_id": SUITE_ID,
        "version": __version__,
        "members": list(MEMBER_IDS),
        "distribution": "researchguard",
        "console_script": "researchguard",
        "fingerprint": suite_fingerprint(),
        "composition_transport": {
            "member_envelope_schema": MEMBER_MODEL_ENVELOPE_SCHEMA,
            "handoff_field_schema": HANDOFF_FIELD_CONTRACT_SCHEMA,
            "member_payload_semantics": "opaque",
        },
    }


def suite_composition_projection(composition: Any) -> dict[str, Any]:
    """Project umbrella transport state without importing member-native schemas."""

    return {
        "status": composition.status,
        "task_id": composition.task_id,
        "composition_fingerprint": composition.composition_fingerprint,
        "member_ids": list(composition.member_ids),
        "member_envelopes": list(composition.member_envelopes),
        "handoff_field_contracts": list(composition.handoff_field_contracts),
        "stale_step_ids": list(composition.stale_step_ids),
        "blocking_member_ids": list(composition.blocking_member_ids),
        "composition_gaps": list(composition.composition_gaps),
        "member_payload_semantics": "opaque",
    }


__all__ = ["governed_file_manifest", "suite_composition_projection", "suite_fingerprint", "suite_identity"]
