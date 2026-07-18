"""Fail when a retired ResearchGuard runtime surface remains executable."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCANNED_ROOTS = (ROOT / "src", ROOT / "skills")
TEXT_SUFFIXES = {".json", ".md", ".py", ".toml", ".yaml", ".yml"}
RETIRED_TOKENS = (
    "logicguard-source-library",
    "logicguard-structured-artifact",
    "logicguard-model-deepening",
    "logicguard-artifact-synthesis",
    "logicguard-project-library-viewer",
    "traceguard-library",
    "python -m logicguard",
    "python -m sourceguard",
    "python -m traceguard",
    "run_logicguard.py",
    "run_sourceguard.py",
    "run_traceguard.py",
    ".skillguard/",
    ".skillguard\\",
    "skillguard.",
)
RETIRED_PACKAGE_PATHS = (
    ROOT / "src" / "logicguard",
    ROOT / "src" / "sourceguard",
    ROOT / "src" / "traceguard",
)


def find_residuals() -> list[dict[str, str]]:
    residuals: list[dict[str, str]] = []
    for path in RETIRED_PACKAGE_PATHS:
        if path.exists():
            residuals.append(
                {
                    "kind": "retired_package_path",
                    "path": path.relative_to(ROOT).as_posix(),
                    "token": "",
                }
            )
    for root in SCANNED_ROOTS:
        for path in sorted(root.rglob("*")):
            if (
                not path.is_file()
                or path.suffix.lower() not in TEXT_SUFFIXES
                or "__pycache__" in path.parts
                or ".skillguard" in path.parts
            ):
                continue
            text = path.read_text(encoding="utf-8").lower()
            for token in RETIRED_TOKENS:
                if token.lower() in text:
                    residuals.append(
                        {
                            "kind": "retired_runtime_token",
                            "path": path.relative_to(ROOT).as_posix(),
                            "token": token,
                        }
                    )
    return residuals


def main() -> int:
    residuals = find_residuals()
    result = {
        "schema_version": "researchguard.zero-residual-check.v1",
        "status": "pass" if not residuals else "blocked",
        "scanned_roots": [
            root.relative_to(ROOT).as_posix() for root in SCANNED_ROOTS
        ],
        "residual_count": len(residuals),
        "residuals": residuals,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not residuals else 1


if __name__ == "__main__":
    raise SystemExit(main())
