from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from scripts.check_zero_residuals import (
    declared_predecessor_dependencies,
    python_predecessor_dependencies,
)


ROOT = Path(__file__).resolve().parents[1]


def test_active_runtime_has_zero_retired_surfaces() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_zero_residuals.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"residual_count": 0' in result.stdout
    assert '"status": "pass"' in result.stdout


def test_retired_distribution_metadata_query_is_a_residual(tmp_path: Path) -> None:
    path = tmp_path / "old_metadata.py"
    path.write_text(
        "import importlib.metadata\n"
        "VERSION = importlib.metadata.version('logicguard')\n",
        encoding="utf-8",
    )

    findings = python_predecessor_dependencies(path)

    assert [row["kind"] for row in findings] == [
        "retired_distribution_metadata_query"
    ]


def test_retired_python_import_is_a_residual(tmp_path: Path) -> None:
    path = tmp_path / "old_import.py"
    path.write_text("from logicguard import Model\n", encoding="utf-8")

    findings = python_predecessor_dependencies(path)

    assert [row["kind"] for row in findings] == ["retired_python_import"]


def test_current_namespaced_import_is_not_a_residual(tmp_path: Path) -> None:
    path = tmp_path / "current_import.py"
    path.write_text("from researchguard.logic import Model\n", encoding="utf-8")

    assert python_predecessor_dependencies(path) == []


def test_retired_declared_dependency_is_a_residual(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text(
        "[project]\n"
        "name = 'example'\n"
        "version = '1.0.0'\n"
        "dependencies = ['sourceguard>=1']\n"
        "[project.optional-dependencies]\n"
        "test = ['pytest>=8']\n",
        encoding="utf-8",
    )

    findings = declared_predecessor_dependencies(path)

    assert [row["kind"] for row in findings] == ["retired_declared_dependency"]
