"""Copy frozen public examples and assets into member-owned namespaces."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from .copy_frozen_sources import CANONICAL_TEXT_REWRITES, _verify_source


RESOURCE_MOVES = (
    ("logicguard", "examples", "examples/logic"),
    ("sourceguard", "examples", "examples/source"),
    ("traceguard", "examples", "examples/trace"),
    ("logicguard", "assets", "resources/logic"),
    ("sourceguard", "assets", "resources/source"),
    ("traceguard", "assets", "resources/trace"),
    ("traceguard", "references", "references/trace"),
)


def _rewrite_shard_paths(tests_root: Path, shard: str) -> None:
    shard_root = tests_root / shard
    for path in shard_root.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".json", ".yaml", ".yml", ".md"}:
            continue
        original = path.read_text(encoding="utf-8")
        rewritten = re.sub(
            rf'(["\'])examples/(?!{re.escape(shard)}/)',
            rf"\1examples/{shard}/",
            original,
        )
        if path.suffix.lower() == ".py":
            rewritten = re.sub(
                rf'ROOT / "examples"(?! / "{re.escape(shard)}")',
                f'ROOT / "examples" / "{shard}"',
                rewritten,
            )
            rewritten = re.sub(
                rf'Path\("examples/(?!{re.escape(shard)}/)',
                f'Path("examples/{shard}/',
                rewritten,
            )
        if rewritten != original:
            path.write_text(rewritten, encoding="utf-8", newline="")


def canonicalize_resource_tree(target_root: Path) -> None:
    for path in (
        list((target_root / "examples").rglob("*"))
        + list((target_root / "resources").rglob("*"))
        + list((target_root / "references").rglob("*"))
    ):
        if not path.is_file() or path.suffix.lower() not in {
            ".json",
            ".md",
            ".py",
            ".yaml",
            ".yml",
        }:
            continue
        original = path.read_text(encoding="utf-8")
        rewritten = original
        for old, new in CANONICAL_TEXT_REWRITES:
            rewritten = rewritten.replace(old, new)
        if "source" in path.parts and path.suffix.lower() in {".yaml", ".yml"}:
            rewritten = re.sub(
                r"(?m)^(\s*version:\s*)[0-9]+\.[0-9]+\.[0-9]+\s*$",
                r"\g<1>0.1.0",
                rewritten,
            )
        if rewritten != original:
            path.write_text(rewritten, encoding="utf-8", newline="")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--logic-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--trace-root", type=Path, required=True)
    parser.add_argument("--target-root", type=Path, required=True)
    args = parser.parse_args()

    roots = {
        "logicguard": args.logic_root.resolve(),
        "sourceguard": args.source_root.resolve(),
        "traceguard": args.trace_root.resolve(),
    }
    for source_id, root in roots.items():
        _verify_source(source_id, root)

    target_root = args.target_root.resolve()
    for source_id, source_name, destination_name in RESOURCE_MOVES:
        source = roots[source_id] / source_name
        destination = target_root / destination_name
        if destination.exists():
            raise RuntimeError(f"destination already exists: {destination}")
        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )

    tests_root = target_root / "tests"
    for shard in ("logic", "source", "trace"):
        _rewrite_shard_paths(tests_root, shard)
    canonicalize_resource_tree(target_root)
    print("ResearchGuard frozen resources copied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
