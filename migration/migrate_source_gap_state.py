"""One-way migration from the retired SourceGuard gap status projection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
ROOTS = (
    ROOT / "examples" / "source",
    ROOT / "tests" / "source",
    ROOT / "src" / "researchguard" / "source" / "template_pack_catalog.json",
)


def migrate(value: Any) -> int:
    changed = 0
    if isinstance(value, dict):
        if "gap_id" in value and "gap_type" in value:
            retired = value.pop("status", None)
            if "semantic_state" not in value:
                value["semantic_state"] = {
                    "closed": "closed",
                    "blocked": "blocked",
                    "downgraded": "contradicted",
                }.get(str(retired or ""), "discovered")
            if retired is not None:
                changed += 1
        for child in value.values():
            changed += migrate(child)
    elif isinstance(value, list):
        for child in value:
            changed += migrate(child)
    return changed


def files() -> list[Path]:
    output: list[Path] = []
    for root in ROOTS:
        if root.is_file():
            output.append(root)
        elif root.exists():
            output.extend(
                path
                for path in root.rglob("*")
                if path.is_file() and path.suffix.lower() in {".json", ".yaml", ".yml"}
            )
    return sorted(set(output))


def main() -> int:
    changed_files = 0
    changed_records = 0
    for path in files():
        raw = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            payload = json.loads(raw)
        else:
            payload = yaml.safe_load(raw)
        count = migrate(payload)
        if not count:
            continue
        if path.suffix.lower() == ".json":
            rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        else:
            rendered = yaml.safe_dump(
                payload,
                allow_unicode=True,
                sort_keys=False,
                width=120,
            )
        path.write_text(rendered, encoding="utf-8")
        changed_files += 1
        changed_records += count
    print(
        json.dumps(
            {"changed_files": changed_files, "changed_records": changed_records},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
