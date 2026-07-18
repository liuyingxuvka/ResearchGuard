from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import install_researchguard


class _Distribution:
    def __init__(self, executable: Path, *, duplicate: Path | None = None) -> None:
        self.entry_points = [
            SimpleNamespace(
                group="console_scripts",
                name="researchguard",
                value="researchguard.cli:main",
            )
        ]
        self.files = [Path("../Scripts/researchguard.exe")]
        self._paths = {
            "../Scripts/researchguard.exe": executable,
        }
        if duplicate is not None:
            self.files.append(Path("../bin/researchguard"))
            self._paths["../bin/researchguard"] = duplicate

    def locate_file(self, relative: Path) -> Path:
        return self._paths[relative.as_posix()]


def test_console_entrypoint_is_resolved_from_installed_distribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "researchguard.exe"
    executable.write_bytes(b"current console")
    monkeypatch.setattr(
        install_researchguard.importlib.metadata,
        "distribution",
        lambda _name: _Distribution(executable),
    )

    assert install_researchguard._installed_console_entrypoint() == executable.resolve()


def test_console_entrypoint_rejects_multiple_materialized_executables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows_executable = tmp_path / "researchguard.exe"
    posix_executable = tmp_path / "researchguard"
    windows_executable.write_bytes(b"windows")
    posix_executable.write_bytes(b"posix")
    monkeypatch.setattr(
        install_researchguard.importlib.metadata,
        "distribution",
        lambda _name: _Distribution(
            windows_executable,
            duplicate=posix_executable,
        ),
    )

    with pytest.raises(
        install_researchguard.InstallError,
        match="exactly one researchguard console executable",
    ):
        install_researchguard._installed_console_entrypoint()
