from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path
import re
import runpy
from typing import Iterator

import pytest


REPOSITORY = Path(__file__).resolve().parents[1]
COMPILER = REPOSITORY / "scripts" / "compile_external_domain_dna_examples.py"
MACHINE_PATH = re.compile(
    r"(?i)(?:\b[a-z]:[\\/]|appdata[\\/]|researchguard-external-domain-dna-compiler-)"
)


def _decoded_json(value: str) -> object | None:
    candidate = value
    if value.startswith("data:") and ";base64," in value:
        candidate = value.split(";base64,", 1)[1]
    try:
        body = base64.b64decode(candidate.encode("ascii"), validate=True)
        text = body.decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError, binascii.Error, ValueError):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _all_text(value: object, *, field: str = "") -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _all_text(child, field=str(key))
        return
    if isinstance(value, list):
        for child in value:
            yield from _all_text(child, field=field)
        return
    if not isinstance(value, str):
        return
    yield value
    if field.endswith("_b64") or (
        value.startswith("data:") and ";base64," in value
    ):
        decoded = _decoded_json(value)
        if decoded is not None:
            yield from _all_text(decoded, field="decoded")


def test_canonical_native_bundle_is_reproducible_and_machine_independent() -> None:
    namespace = runpy.run_path(str(COMPILER))
    build_native_bundle = namespace["_native_bundle"]

    first = build_native_bundle()
    second = build_native_bundle()

    assert first == second
    decoded = json.loads(first.decode("utf-8"))
    leaked = sorted({text for text in _all_text(decoded) if MACHINE_PATH.search(text)})
    assert leaked == []


def test_paper_compiler_requires_one_explicit_external_material_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = runpy.run_path(str(COMPILER))
    variable = str(namespace["PAPER_ROOT_ENV"])
    monkeypatch.delenv(variable, raising=False)

    with pytest.raises(RuntimeError, match=variable):
        namespace["_paper_root"]()
