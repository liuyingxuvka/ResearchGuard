"""Check the researchguard skill's entry and route budgets and its conditional reference edges."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "researchguard"
MANIFEST_PATH = ROOT / "scripts" / "prompt_bundle_manifest.json"


def _read_manifest(path: Path = MANIFEST_PATH) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "researchguard.prompt-bundle-manifest.v1":
        raise ValueError("prompt bundle manifest requires the current schema")
    return payload


def check_prompt_bundles(
    manifest: Mapping[str, Any] | None = None,
    *,
    bundle: str = "all",
) -> dict[str, Any]:
    manifest = _read_manifest() if manifest is None else manifest
    failures: list[dict[str, str]] = []
    bundles: list[dict[str, Any]] = []
    selected_files: set[str] = set()
    for row in manifest.get("bundles", []):
        bundle_id = str(row.get("bundle_id", ""))
        if bundle != "all" and bundle_id != bundle:
            continue
        paths = [ROOT / str(path) for path in row.get("entry_files", [])]
        selected_files.update(path.relative_to(ROOT).as_posix() for path in paths)
        missing = [path.relative_to(ROOT).as_posix() for path in paths if not path.is_file()]
        if missing:
            failures.append({"code": "entry-file-missing", "bundle_id": bundle_id, "detail": ", ".join(missing)})
            continue
        total = sum(path.stat().st_size for path in paths)
        limit = int(row.get("max_entry_bytes", 0))
        headroom = limit - total
        minimum = int(row.get("minimum_headroom_bytes", 0))
        if total > limit:
            failures.append({"code": "entry-budget-exceeded", "bundle_id": bundle_id, "detail": f"{total}>{limit}"})
        if headroom < minimum:
            failures.append({"code": "entry-headroom-insufficient", "bundle_id": bundle_id, "detail": f"{headroom}<{minimum}"})
        bundles.append(
            {
                "bundle_id": bundle_id,
                "entry_bytes": total,
                "limit_bytes": limit,
                "headroom_bytes": headroom,
                "entry_files": [path.relative_to(ROOT).as_posix() for path in paths],
            }
        )

    for edge in manifest.get("reference_edges", []):
        declared = str(edge.get("declared_in", ""))
        if bundle != "all" and declared not in selected_files:
            continue
        reference = str(edge.get("reference", ""))
        trigger = str(edge.get("trigger_id", ""))
        declared_in = ROOT / declared
        target = ROOT / reference
        if not declared_in.is_file() or not target.is_file():
            failures.append({"code": "reference-edge-missing", "bundle_id": declared, "detail": reference})
            continue
        text = declared_in.read_text(encoding="utf-8")
        relative_reference = target.relative_to(SKILL_ROOT).as_posix()
        if relative_reference not in text or (trigger and trigger not in text):
            failures.append({"code": "reference-edge-undeclared", "bundle_id": declared, "detail": f"{trigger}:{relative_reference}"})

    return {
        "schema_version": "researchguard.prompt-bundle-check.v1",
        "status": "pass" if not failures else "fail",
        "bundles": bundles,
        "failures": failures,
        "claim_boundary": manifest.get("claim_boundary"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", default="all", help="all, researchguard, route:logic, route:source, route:trace or route:experiment")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = check_prompt_bundles(bundle=args.bundle)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) if args.json else result["status"])
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
