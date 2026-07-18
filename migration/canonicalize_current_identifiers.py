"""Replace predecessor machine identifiers with current ResearchGuard ids."""

from __future__ import annotations

import argparse
from pathlib import Path


REWRITES = (
    ("logicguard_template_packs.", "researchguard.logic_template_packs."),
    ("logicguard_viewer.", "researchguard.logic_viewer."),
    ("logicguard.", "researchguard.logic."),
    ("sourceguard.", "researchguard.source."),
    ("traceguard.", "researchguard.trace."),
)

TEXT_SUFFIXES = {".json", ".md", ".py", ".yaml", ".yml"}
TARGET_TREES = ("src", "examples", "resources", "references", "tests")


def canonicalize(target_root: Path) -> int:
    changed = 0
    for tree_name in TARGET_TREES:
        tree = target_root / tree_name
        if not tree.exists():
            continue
        for path in tree.rglob("*"):
            if (
                not path.is_file()
                or path.suffix.lower() not in TEXT_SUFFIXES
                or "__pycache__" in path.parts
            ):
                continue
            original = path.read_text(encoding="utf-8")
            rewritten = original
            for old, new in REWRITES:
                rewritten = rewritten.replace(old, new)
            if rewritten != original:
                path.write_text(rewritten, encoding="utf-8", newline="")
                changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-root", type=Path, required=True)
    args = parser.parse_args()
    changed = canonicalize(args.target_root.resolve())
    print(f"ResearchGuard identifier migration changed {changed} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

