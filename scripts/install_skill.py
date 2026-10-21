"""Install the five ResearchGuard skills into an agent's skills directory.

    python scripts/install_skill.py --target "$CODEX_HOME/skills"            # or ~/.claude/skills
    python scripts/install_skill.py --target "$CODEX_HOME/skills" --dry-run
    python scripts/install_skill.py --target "$CODEX_HOME/skills" --check    # exit 1 if the copy differs

Copies skills/<name>/ to <target>/<name>/ for each of the five skills (replacing older copies).
The Python engine is installed separately: pip install -e <this repository>.
"""

from __future__ import annotations

import argparse
import os
import re
import filecmp
import shutil
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "skills"
MEMBERS = ("researchguard", "logicguard", "sourceguard", "traceguard", "experimentguard")


def differences(src: Path, dst: Path) -> list[str]:
    if not dst.is_dir():
        return [f"missing {dst}"]
    out = []
    cmp = filecmp.dircmp(src, dst, ignore=["__pycache__"])
    stack = [(cmp, Path("."))]
    while stack:
        node, rel = stack.pop()
        out += [f"only in source: {rel / n}" for n in node.left_only]
        out += [f"only in target: {rel / n}" for n in node.right_only]
        out += [f"differs: {rel / n}" for n in node.diff_files]
        stack += [(sub, rel / name) for name, sub in node.subdirs.items()]
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, help="skills directory, e.g. $CODEX_HOME/skills or ~/.claude/skills")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    # Also accept a literal shell-style path passed through a GUI or quoted command.
    required = re.findall(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))|%([A-Za-z_][A-Za-z0-9_]*)%", args.target)
    missing = [next(part for part in match if part) for match in required
               if not os.environ.get(next(part for part in match if part))]
    if missing:
        parser.error("target environment variable is unset: " + ", ".join(missing))
    target = re.sub(r"%([A-Za-z_][A-Za-z0-9_]*)%", lambda m: os.environ[m[1]], args.target)
    root = Path(os.path.expandvars(target)).expanduser()
    for name in MEMBERS:
        if not (SOURCE / name / "SKILL.md").is_file():
            print(f"skill source not found: {SOURCE / name}", file=sys.stderr)
            return 2
    diff = [f"{name}: {line}" for name in MEMBERS
            for line in differences(SOURCE / name, root / name)]
    if args.check:
        print("\n".join(diff) or "installed skills are current")
        return 1 if diff else 0
    if args.dry_run:
        print(f"would copy 5 skills from {SOURCE} -> {root}")
        return 0
    for name in MEMBERS:
        dst = root / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(SOURCE / name, dst, ignore=shutil.ignore_patterns("__pycache__"))
        print(f"installed {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
