"""Canonical JSON and digest helpers for LogicGuard template packs."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Iterable, Mapping


class CanonicalValueError(ValueError):
    """Raised when a value cannot participate in a portable JSON identity."""


def canonical_json(value: Any) -> str:
    normalized = normalize_json(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalize_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalValueError("non-finite numbers are not portable JSON")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalValueError("JSON object keys must be strings")
            if key in normalized:
                raise CanonicalValueError(f"duplicate JSON key: {key}")
            normalized[key] = normalize_json(item)
        return normalized
    if isinstance(value, (list, tuple)):
        return [normalize_json(item) for item in value]
    raise CanonicalValueError(f"unsupported JSON value type: {type(value).__name__}")


def canonical_string_list(values: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise CanonicalValueError(
                "canonical string lists require non-empty string items"
            )
        normalized.append(value.strip())
    return tuple(sorted(set(normalized)))


def decode_canonical(value_json: str) -> Any:
    return json.loads(value_json)
