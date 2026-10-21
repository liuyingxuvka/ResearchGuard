"""Check ResearchGuard entry budgets and conditional reference edges."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))



MANIFEST_PATH = ROOT / "scripts" / "prompt_bundle_manifest.json"


def _read_manifest(path: Path = MANIFEST_PATH) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "researchguard.prompt-bundle-manifest.v1":
        raise ValueError("prompt bundle manifest requires the current schema")
    return payload


def check_prompt_bundles(
    manifest: Mapping[str, Any] | None = None,
    *,
    member: str = "all",
) -> dict[str, Any]:
    manifest = _read_manifest() if manifest is None else manifest
    failures: list[dict[str, str]] = []
    bundles: list[dict[str, Any]] = []
    bundle_entries: dict[str, str] = {}
    for row in manifest.get("bundles", []):
        skill_id = str(row.get("skill_id", ""))
        if member != "all" and skill_id != member:
            continue
        paths = [ROOT / str(path) for path in row.get("entry_files", [])]
        missing = [path.relative_to(ROOT).as_posix() for path in paths if not path.is_file()]
        if missing:
            failures.append({"code": "entry-file-missing", "skill_id": skill_id, "detail": ", ".join(missing)})
            continue
        total = sum(path.stat().st_size for path in paths)
        limit = int(row.get("max_entry_bytes", 0))
        headroom = limit - total
        minimum = int(row.get("minimum_headroom_bytes", 0))
        if total > limit:
            failures.append({"code": "entry-budget-exceeded", "skill_id": skill_id, "detail": f"{total}>{limit}"})
        if headroom < minimum:
            failures.append({"code": "entry-headroom-insufficient", "skill_id": skill_id, "detail": f"{headroom}<{minimum}"})
        bundle_entries[skill_id] = "\n".join(
            path.read_text(encoding="utf-8") for path in paths
        )
        bundles.append(
            {
                "skill_id": skill_id,
                "entry_bytes": total,
                "limit_bytes": limit,
                "headroom_bytes": headroom,
                "entry_files": [path.relative_to(ROOT).as_posix() for path in paths],
            }
        )

    for edge in manifest.get("reference_edges", []):
        if member != "all" and str(edge.get("skill_id", "")) != member:
            continue
        declared_in = ROOT / str(edge.get("declared_in", ""))
        reference = str(edge.get("reference", ""))
        trigger = str(edge.get("trigger_id", ""))
        target = ROOT / reference
        if not declared_in.is_file() or not target.is_file():
            failures.append({"code": "reference-edge-missing", "skill_id": str(edge.get("skill_id", "")), "detail": reference})
            continue
        declaration = declared_in.read_text(encoding="utf-8")
        relative_reference = Path(reference).relative_to(Path("skills") / str(edge["skill_id"])).as_posix()
        if relative_reference not in declaration or trigger not in declaration:
            failures.append({"code": "reference-edge-undeclared", "skill_id": str(edge.get("skill_id", "")), "detail": f"{trigger}:{relative_reference}"})

    if member in {"all", "researchguard"}:
        umbrella = (ROOT / "skills" / "researchguard" / "SKILL.md").read_text(encoding="utf-8")
        for prohibited in manifest.get("prohibited_eager_member_paths", []):
            if str(prohibited) in umbrella:
                failures.append({"code": "umbrella-eager-member-load", "skill_id": "researchguard", "detail": str(prohibited)})

    return {
        "schema_version": "researchguard.prompt-bundle-check.v1",
        "status": "pass" if not failures else "fail",
        "bundles": bundles,
        "failures": failures,
        "claim_boundary": manifest.get("claim_boundary"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--member", choices=("all", "researchguard", "logicguard", "sourceguard", "traceguard", "experimentguard"), default="all")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = check_prompt_bundles(member=args.member)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) if args.json else result["status"])
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
