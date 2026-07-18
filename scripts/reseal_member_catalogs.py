"""Reseal member template catalogs after intentional current-path changes."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from researchguard.source.schema import (
    SourceGuardModelContract,
    sourceguard_model_contract_fingerprint,
)
from researchguard.logic_template_packs.canonical import canonical_sha256
from researchguard.logic_template_packs.native_validators import (
    callable_fingerprint,
    resolve_callable,
)
from researchguard.source.template_packs import seal_catalog as seal_source_catalog
from researchguard.trace.template_packs import seal_catalog as seal_trace_catalog

def _reseal(relative: str, seal) -> None:
    path = ROOT / relative
    payload = json.loads(path.read_text(encoding="utf-8"))
    sealed = seal(payload)
    path.write_text(
        json.dumps(sealed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="",
    )


def _reseal_source_examples() -> int:
    changed = 0
    for path in sorted((ROOT / "examples" / "source").glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(
            payload.get("guard_contract"), dict
        ):
            continue
        contract = SourceGuardModelContract.from_dict(payload["guard_contract"])
        expected = sourceguard_model_contract_fingerprint(contract)
        if payload.get("candidate_contract_fingerprint") == expected:
            continue
        payload["candidate_contract_fingerprint"] = expected
        path.write_text(
            yaml.safe_dump(
                payload,
                allow_unicode=True,
                sort_keys=False,
                width=120,
            ),
            encoding="utf-8",
        )
        changed += 1
    return changed


def _reseal_logic_catalog() -> None:
    catalog_root = (
        ROOT / "src" / "researchguard" / "logic_template_packs" / "catalog"
    )
    manifest_path = catalog_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["profiles"]:
        profile_path = catalog_root / entry["path"]
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        native_binding = profile["native_binding"]
        native_binding["owner_fingerprint"] = callable_fingerprint(
            resolve_callable(native_binding["owner_callable"])
        )
        for validator in native_binding["validators"]:
            validator["callable_fingerprint"] = callable_fingerprint(
                resolve_callable(validator["callable"])
            )
        profile_path.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="",
        )
        entry["sha256"] = canonical_sha256(profile)
    digest_payload = dict(manifest)
    digest_payload.pop("catalog_digest", None)
    manifest["catalog_digest"] = canonical_sha256(digest_payload)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="",
    )


def main() -> int:
    _reseal_logic_catalog()
    _reseal(
        "src/researchguard/source/template_pack_catalog.json",
        seal_source_catalog,
    )
    _reseal(
        "src/researchguard/trace/template_pack_catalog.json",
        seal_trace_catalog,
    )
    examples = _reseal_source_examples()
    print(
        "ResearchGuard member catalogs resealed; "
        f"logic=1 source=1 trace=1 source_examples={examples}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
