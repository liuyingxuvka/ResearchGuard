"""Copy frozen predecessor tests into namespaced ResearchGuard test shards."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from .copy_frozen_sources import (
    CANONICAL_TEXT_REWRITES,
    IMPORT_REWRITES,
    EXPECTED_HEADS,
    _verify_source,
)


TEST_MOVES = (
    ("logicguard", "tests", "logic"),
    ("logicguard", "tests_template_packs", "logic_template_packs"),
    ("sourceguard", "tests", "source"),
    ("traceguard", "tests", "trace"),
)

QUALIFIED_TEST_REWRITES = (
    (re.compile(r'(["\'])logicguard_template_packs(?=\.)([^"\']*)(["\'])'), r"\1researchguard.logic_template_packs\2\3"),
    (re.compile(r'(["\'])logicguard_viewer(?=\.)([^"\']*)(["\'])'), r"\1researchguard.logic_viewer\2\3"),
    (re.compile(r'(["\'])logicguard(?=\.)([^"\']*)(["\'])'), r"\1researchguard.logic\2\3"),
    (re.compile(r'(["\'])sourceguard(?=\.)([^"\']*)(["\'])'), r"\1researchguard.source\2\3"),
    (re.compile(r'(["\'])traceguard(?=\.)([^"\']*)(["\'])'), r"\1researchguard.trace\2\3"),
)

LOCAL_TEST_IMPORT_REWRITES = (
    ("from model_mesh_test_support import", "from .model_mesh_test_support import"),
    ("from model_mesh_scale_support import", "from .model_mesh_scale_support import"),
)

SOLE_CLI_REWRITES = (
    ('[sys.executable, "-m", "logicguard",', '[sys.executable, "-m", "researchguard", "logic",'),
    ('[sys.executable, "-m", "sourceguard",', '[sys.executable, "-m", "researchguard", "source",'),
    ('[sys.executable, "-m", "traceguard",', '[sys.executable, "-m", "researchguard", "trace",'),
)


def _rewrite_test(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    rewritten = original
    if path.suffix.lower() in {".py", ".md", ".json", ".yaml", ".yml"}:
        for old, new in CANONICAL_TEXT_REWRITES:
            rewritten = rewritten.replace(old, new)
    if path.suffix.lower() == ".py":
        for pattern, replacement in IMPORT_REWRITES:
            rewritten = pattern.sub(replacement, rewritten)
        for pattern, replacement in QUALIFIED_TEST_REWRITES:
            rewritten = pattern.sub(replacement, rewritten)
        for old, new in LOCAL_TEST_IMPORT_REWRITES:
            rewritten = rewritten.replace(old, new)
        for old, new in SOLE_CLI_REWRITES:
            rewritten = rewritten.replace(old, new)
        rewritten = re.sub(
            r'(["\']-m["\'],\s*)["\'](logicguard|sourceguard|traceguard)["\']\s*,',
            lambda match: (
                f'{match.group(1)}"researchguard", '
                f'"{match.group(2).removesuffix("guard")}",'
            ),
            rewritten,
        )
        rewritten = rewritten.replace(
            "Path(__file__).resolve().parents[1]",
            "Path(__file__).resolve().parents[2]",
        )
        if "logic_template_packs" in path.parts:
            rewritten = rewritten.replace(
                'ROOT / "template_pack_fixtures"',
                'Path(__file__).resolve().parent / "fixtures"',
            )
    if rewritten != original:
        path.write_text(rewritten, encoding="utf-8", newline="")


def canonicalize_test_tree(tests_root: Path) -> None:
    for path in tests_root.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            _rewrite_test(path)


def copy_logic_fixtures(logic_root: Path, tests_root: Path) -> None:
    source = logic_root / "template_pack_fixtures"
    destination = tests_root / "logic_template_packs" / "fixtures"
    if destination.exists():
        raise RuntimeError(f"destination already exists: {destination}")
    shutil.copytree(source, destination)


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

    tests_root = args.target_root.resolve() / "tests"
    tests_root.mkdir(exist_ok=True)
    for source_id, source_name, destination_name in TEST_MOVES:
        source = roots[source_id] / source_name
        destination = tests_root / destination_name
        if destination.exists():
            raise RuntimeError(f"destination already exists: {destination}")
        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        (destination / "__init__.py").touch(exist_ok=False)
        for path in destination.rglob("*"):
            if path.is_file():
                _rewrite_test(path)

    copy_logic_fixtures(roots["logicguard"], tests_root)
    canonicalize_test_tree(tests_root)
    print(
        "ResearchGuard frozen tests copied for "
        + ", ".join(EXPECTED_HEADS)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
