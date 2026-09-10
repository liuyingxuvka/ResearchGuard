"""Refresh or verify current model-purpose file identities.

The regression manifest stores canonical ``source_file_fingerprint`` values,
which normalize text newlines before hashing.  This small author-side helper
keeps the ten manifest purpose closures aligned with their checked-in model
and native-runner files without changing any semantic purpose fields.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from flowguard.model_purpose import build_model_purpose_closure
from flowguard.source_identity import source_file_fingerprint


def _current_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / ".flowguard" / "models" / "regression-manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        raise ValueError("regression manifest must contain a models list")
    return payload


def _refresh_closure(root: Path, entry: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    model_id = str(entry.get("model_id", ""))
    model_path = str(entry.get("model_path", ""))
    runner = entry.get("runner")
    if not model_id or not model_path or not isinstance(runner, list) or len(runner) != 2:
        raise ValueError(f"invalid manifest model entry: {model_id or '<missing>'}")
    runner_path = str(runner[1])
    if runner_path.startswith("{"):
        raise ValueError(f"runner path is not a concrete file: {model_id}")
    model_fingerprint = source_file_fingerprint(root / model_path)
    runner_fingerprint = source_file_fingerprint(root / runner_path)
    old = entry.get("purpose_closure")
    if not isinstance(old, dict):
        raise ValueError(f"missing purpose_closure: {model_id}")
    closure = build_model_purpose_closure(
        model_instance_id=str(old["model_instance_id"]),
        reusable_model_type_id=str(old["reusable_model_type_id"]),
        task_intent_id=str(old["task_intent_id"]),
        guarded_purpose=str(old["guarded_purpose"]),
        protected_failure_ids=list(old["protected_failure_ids"]),
        known_good_case_id=str(old["known_good_case_id"]),
        failure_bindings=list(old["failure_bindings"]),
        claim_boundary=str(old["claim_boundary"]),
        evidence_check_ids=list(old["evidence_check_ids"]),
        model_sha256=model_fingerprint,
        runner_sha256=runner_fingerprint,
    )
    refreshed = closure.to_dict()
    return refreshed, refreshed != old


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    manifest_path = root / ".flowguard" / "models" / "regression-manifest.json"
    manifest = _current_manifest(root)
    changes: list[dict[str, str]] = []
    for entry in manifest["models"]:
        if not isinstance(entry, dict):
            raise ValueError("manifest model entries must be objects")
        refreshed, changed = _refresh_closure(root, entry)
        if changed:
            changes.append({"model_id": str(entry.get("model_id", "")), "status": "stale"})
            entry["purpose_closure"] = refreshed
    result = {
        "manifest": str(manifest_path),
        "model_count": len(manifest["models"]),
        "changed_count": len(changes),
        "changes": changes,
        "status": "stale" if changes else "current",
        "mode": "check" if args.check else "write",
    }
    if args.check:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if changes else 0
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    result["status"] = "written"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
