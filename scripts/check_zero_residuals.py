"""Fail when a retired ResearchGuard runtime surface remains executable."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys
import tomllib


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
RETIRED_DISTRIBUTIONS = {"logicguard", "sourceguard", "traceguard"}
METADATA_QUERY_NAMES = {"distribution", "files", "metadata", "requires", "version"}


def _normalized_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _python_path_label(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def python_predecessor_dependencies(path: Path) -> list[dict[str, str]]:
    """Return retired imports and literal distribution metadata queries."""

    findings: list[dict[str, str]] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [
            {
                "kind": "python_parse_failure",
                "path": _python_path_label(path),
                "token": f"line {exc.lineno}: {exc.msg}",
            }
        ]

    metadata_module_aliases: set[str] = set()
    metadata_function_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".", 1)[0]
                if root_name in RETIRED_DISTRIBUTIONS:
                    findings.append(
                        {
                            "kind": "retired_python_import",
                            "path": _python_path_label(path),
                            "token": alias.name,
                        }
                    )
                if alias.name == "importlib.metadata":
                    metadata_module_aliases.add(alias.asname or "importlib.metadata")
        elif isinstance(node, ast.ImportFrom):
            root_name = (node.module or "").split(".", 1)[0]
            if root_name in RETIRED_DISTRIBUTIONS:
                findings.append(
                    {
                        "kind": "retired_python_import",
                        "path": _python_path_label(path),
                        "token": node.module or root_name,
                    }
                )
            if node.module == "importlib":
                for alias in node.names:
                    if alias.name == "metadata":
                        metadata_module_aliases.add(alias.asname or alias.name)
            elif node.module == "importlib.metadata":
                for alias in node.names:
                    if alias.name in METADATA_QUERY_NAMES:
                        metadata_function_aliases.add(alias.asname or alias.name)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        query_name = ""
        function = node.func
        if isinstance(function, ast.Name) and function.id in metadata_function_aliases:
            query_name = function.id
        elif isinstance(function, ast.Attribute) and function.attr in METADATA_QUERY_NAMES:
            if isinstance(function.value, ast.Name):
                if function.value.id in metadata_module_aliases:
                    query_name = function.attr
            elif (
                isinstance(function.value, ast.Attribute)
                and isinstance(function.value.value, ast.Name)
                and function.value.value.id == "importlib"
                and function.value.attr == "metadata"
            ):
                query_name = function.attr
        if not query_name:
            continue
        distribution = node.args[0]
        if not isinstance(distribution, ast.Constant) or not isinstance(
            distribution.value, str
        ):
            continue
        normalized = _normalized_distribution_name(distribution.value)
        if normalized in RETIRED_DISTRIBUTIONS:
            findings.append(
                {
                    "kind": "retired_distribution_metadata_query",
                    "path": _python_path_label(path),
                    "token": f"{query_name}({distribution.value!r})",
                }
            )
    return findings


def declared_predecessor_dependencies(path: Path) -> list[dict[str, str]]:
    """Return retired packages declared by the current Python distribution."""

    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    project = payload.get("project") or {}
    groups = {
        "project.dependencies": project.get("dependencies") or (),
        **{
            f"project.optional-dependencies.{name}": requirements
            for name, requirements in (
                project.get("optional-dependencies") or {}
            ).items()
        },
    }
    findings: list[dict[str, str]] = []
    for group, requirements in groups.items():
        for requirement in requirements:
            match = re.match(r"\s*([A-Za-z0-9_.-]+)", requirement)
            if not match:
                continue
            distribution = _normalized_distribution_name(match.group(1))
            if distribution in RETIRED_DISTRIBUTIONS:
                findings.append(
                    {
                        "kind": "retired_declared_dependency",
                        "path": _python_path_label(path),
                        "token": f"{group}:{requirement}",
                    }
                )
    return findings


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
            if path.suffix.lower() == ".py":
                residuals.extend(python_predecessor_dependencies(path))
    residuals.extend(declared_predecessor_dependencies(ROOT / "pyproject.toml"))
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
