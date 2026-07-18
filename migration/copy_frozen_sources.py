"""Copy the three frozen Guard runtimes into the ResearchGuard namespace.

This is an author-side, direct-to-current migration utility. It is not imported
by normal runtime and deliberately refuses overlays, dirty sources, or source
revision drift.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path


EXPECTED_HEADS = {
    "logicguard": "6724b21104d0fb8d9a6191a25d053cb054651bf5",
    "sourceguard": "9b601c09799c1407ebba14989d17ff812aa93559",
    "traceguard": "7751471292244dce3bfb27cd220a6efb320fc3e8",
}

PACKAGE_MOVES = (
    ("logicguard", "logic", "logicguard"),
    ("logicguard", "logic_template_packs", "logicguard_template_packs"),
    ("logicguard", "logic_viewer", "logicguard_viewer"),
    ("sourceguard", "source", "sourceguard"),
    ("traceguard", "trace", "traceguard"),
)

IMPORT_REWRITES = (
    (re.compile(r"(?m)^(\s*from\s+)logicguard_template_packs(?=[.\s])"), r"\1researchguard.logic_template_packs"),
    (re.compile(r"(?m)^(\s*import\s+)logicguard_template_packs(?=[.\s,]|$)"), r"\1researchguard.logic_template_packs"),
    (re.compile(r"(?m)^(\s*from\s+)logicguard_viewer(?=[.\s])"), r"\1researchguard.logic_viewer"),
    (re.compile(r"(?m)^(\s*import\s+)logicguard_viewer(?=[.\s,]|$)"), r"\1researchguard.logic_viewer"),
    (re.compile(r"(?m)^(\s*from\s+)logicguard(?=[.\s])"), r"\1researchguard.logic"),
    (re.compile(r"(?m)^(\s*import\s+)logicguard(?=[.\s,]|$)"), r"\1researchguard.logic"),
    (re.compile(r"(?m)^(\s*from\s+)sourceguard(?=[.\s])"), r"\1researchguard.source"),
    (re.compile(r"(?m)^(\s*import\s+)sourceguard(?=[.\s,]|$)"), r"\1researchguard.source"),
    (re.compile(r"(?m)^(\s*from\s+)traceguard(?=[.\s])"), r"\1researchguard.trace"),
    (re.compile(r"(?m)^(\s*import\s+)traceguard(?=[.\s,]|$)"), r"\1researchguard.trace"),
)

CANONICAL_TEXT_REWRITES = (
    ("https://github.com/liuyingxuvka/LogicGuard", "https://github.com/liuyingxuvka/ResearchGuard"),
    ("https://github.com/liuyingxuvka/SourceGuard", "https://github.com/liuyingxuvka/ResearchGuard"),
    ("https://github.com/liuyingxuvka/TraceGuard", "https://github.com/liuyingxuvka/ResearchGuard"),
    ("python -m logicguard", "researchguard logic"),
    ("python -m sourceguard", "researchguard source"),
    ("python -m traceguard", "researchguard trace"),
    ('prog="logicguard"', 'prog="researchguard logic"'),
    ('prog="sourceguard"', 'prog="researchguard source"'),
    ('prog="traceguard"', 'prog="researchguard trace"'),
)


def _git(root: Path, *args: str) -> str:
    candidates = (
        shutil.which("git.exe"),
        str(Path(os.environ.get("ProgramFiles", "")) / "Git" / "cmd" / "git.exe"),
        str(Path(os.environ.get("ProgramFiles", "")) / "Git" / "bin" / "git.exe"),
    )
    executable = next(
        (candidate for candidate in candidates if candidate and Path(candidate).is_file()),
        None,
    )
    if executable is None:
        raise RuntimeError("git.exe is required for frozen-source verification")
    result = subprocess.run(
        [executable, "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _verify_source(source_id: str, root: Path) -> None:
    if not (root / ".git").exists() and not _git(root, "rev-parse", "--git-dir"):
        raise RuntimeError(f"{source_id}: source is not a Git worktree")
    actual_head = _git(root, "rev-parse", "HEAD")
    if actual_head != EXPECTED_HEADS[source_id]:
        raise RuntimeError(
            f"{source_id}: frozen head mismatch: expected "
            f"{EXPECTED_HEADS[source_id]}, got {actual_head}"
        )
    dirty = _git(root, "status", "--porcelain")
    if dirty:
        raise RuntimeError(f"{source_id}: source worktree is not clean")


def _rewrite_python(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    rewritten = original
    for pattern, replacement in IMPORT_REWRITES:
        rewritten = pattern.sub(replacement, rewritten)
    if rewritten != original:
        path.write_text(rewritten, encoding="utf-8", newline="")


def canonicalize_current_tree(package_root: Path) -> None:
    for path in package_root.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".md", ".json"}:
            continue
        original = path.read_text(encoding="utf-8")
        rewritten = original
        if path.suffix.lower() == ".py":
            for pattern, replacement in IMPORT_REWRITES:
                rewritten = pattern.sub(replacement, rewritten)
        for old, new in CANONICAL_TEXT_REWRITES:
            rewritten = rewritten.replace(old, new)
        if rewritten != original:
            path.write_text(rewritten, encoding="utf-8", newline="")


def _copy_package(source: Path, destination: Path) -> None:
    if destination.exists():
        raise RuntimeError(f"destination already exists: {destination}")
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    for path in destination.rglob("*.py"):
        _rewrite_python(path)


def _copy_trace_guard_model(trace_root: Path, trace_destination: Path) -> None:
    source = trace_root / "guard-model"
    destination = trace_destination / "guard_model"
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

    package_root = args.target_root.resolve() / "src" / "researchguard"
    if not (package_root / "__init__.py").is_file():
        raise RuntimeError("target is not an initialized ResearchGuard source tree")

    for source_id, destination_name, source_name in PACKAGE_MOVES:
        _copy_package(
            roots[source_id] / source_name,
            package_root / destination_name,
        )

    _copy_trace_guard_model(roots["traceguard"], package_root / "trace")
    canonicalize_current_tree(package_root)
    print("ResearchGuard frozen-source migration completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
