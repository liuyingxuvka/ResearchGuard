from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import install_researchguard


def test_source_validation_uses_complete_suite_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], int]] = []
    monkeypatch.setattr(
        install_researchguard,
        "_validate_source_version_identity",
        lambda: None,
    )

    def fake_native_command(args: list[str], *, timeout: int = 300) -> None:
        calls.append((args, timeout))

    monkeypatch.setattr(install_researchguard, "_native_command", fake_native_command)
    install_researchguard._validate_source()

    assert len(calls) == 1
    command, timeout = calls[0]
    assert command[-4:] == ["scripts/check_researchguard_suite.py", "--member", "all", "--json"]
    assert 0 < timeout <= 1200


def test_package_wheel_build_uses_disposable_local_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    package_root = source_root / "src" / "researchguard"
    package_root.mkdir(parents=True)
    (source_root / "pyproject.toml").write_text("[project]\nname='researchguard'\n", encoding="utf-8")
    (source_root / "README.md").write_text("readme\n", encoding="utf-8")
    (package_root / "cli.py").write_text("main = None\n", encoding="utf-8")
    monkeypatch.setattr(install_researchguard, "ROOT", source_root)
    monkeypatch.setattr(install_researchguard, "SOURCE_PACKAGE", package_root)

    calls: list[tuple[list[str], int]] = []

    def fake_native_command(args: list[str], *, timeout: int = 300) -> None:
        calls.append((args, timeout))
        wheel_dir = Path(args[args.index("--wheel-dir") + 1])
        wheel_dir.mkdir(parents=True, exist_ok=True)
        (wheel_dir / f"researchguard-{install_researchguard.VERSION}-py3-none-any.whl").write_bytes(
            b"wheel"
        )

    monkeypatch.setattr(install_researchguard, "_native_command", fake_native_command)
    wheel_dir = tmp_path / "wheel"
    temporary_root = tmp_path / "temporary"
    temporary_root.mkdir()
    wheel = install_researchguard._build_package_wheel(temporary_root, wheel_dir)

    assert wheel == wheel_dir / f"researchguard-{install_researchguard.VERSION}-py3-none-any.whl"
    assert len(calls) == 1
    command, timeout = calls[0]
    assert timeout == 600
    build_context = Path(command[-1])
    assert build_context.name == "package-context"
    assert build_context.is_relative_to(tmp_path)
    assert build_context != source_root
    assert (build_context / "pyproject.toml").read_text(encoding="utf-8") == (
        "[project]\nname='researchguard'\n"
    )
    assert (build_context / "src" / "researchguard" / "cli.py").is_file()





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


class _PackageDistribution:
    def __init__(self, base: Path, version: str, files: tuple[str, ...]) -> None:
        self._base = base
        self.version = version
        self.files = [Path(value) for value in files]

    def locate_file(self, relative: object) -> Path:
        value = Path(str(relative))
        return self._base if value.as_posix() == "." else self._base / value


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


def test_distribution_inventory_accepts_windows_console_script_within_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    interpreter = tmp_path / "venv"
    site_packages = interpreter / "Lib" / "site-packages"
    package = site_packages / "researchguard/__init__.py"
    console = interpreter / "Scripts/researchguard.exe"
    package.parent.mkdir(parents=True)
    console.parent.mkdir(parents=True)
    package.write_bytes(b"package")
    console.write_bytes(b"console")
    distribution = _PackageDistribution(
        site_packages,
        "1.0.0",
        (
            "researchguard/__init__.py",
            "../../Scripts/researchguard.exe",
        ),
    )
    monkeypatch.setattr(install_researchguard.sys, "prefix", str(interpreter))

    authority_root, inventory = install_researchguard._distribution_file_inventory(
        distribution
    )

    assert authority_root == interpreter.resolve()
    assert console.resolve() in inventory




























def test_source_version_identity_rejects_package_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "researchguard"
    package.mkdir()
    (package / "__init__.py").write_text(
        '__version__ = "99.0.0"\n', encoding="utf-8"
    )
    monkeypatch.setattr(install_researchguard, "SOURCE_PACKAGE", package)

    with pytest.raises(
        install_researchguard.InstallError,
        match="source version mismatch",
    ):
        install_researchguard._validate_source_version_identity()












def test_check_current_rejects_an_observed_empty_package_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty_package = tmp_path / "empty-package"
    empty_package.mkdir()
    console = tmp_path / "researchguard.exe"
    console.write_bytes(b"console")
    manifest_path = tmp_path / "install-manifest.json"
    source = {
        "version": install_researchguard.VERSION,
        "skills": {},
        "package": {"__init__.py": "current-hash"},
        "source_fingerprint": "source:current",
    }
    manifest_path.write_bytes(b"legacy manifest is not authority")
    monkeypatch.setattr(install_researchguard, "MEMBERS", ())
    monkeypatch.setattr(install_researchguard, "RETIRED_SKILLS", ())
    monkeypatch.setattr(install_researchguard, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(install_researchguard, "_source_state", lambda: source)
    monkeypatch.setattr(install_researchguard, "_validate_install_paths", lambda: {})
    monkeypatch.setattr(
        install_researchguard, "_installed_version", lambda: install_researchguard.VERSION
    )
    monkeypatch.setattr(
        install_researchguard, "_installed_package_root", lambda: empty_package
    )
    monkeypatch.setattr(
        install_researchguard, "_installed_console_entrypoint", lambda: console
    )

    report = install_researchguard.check_current()

    assert report["status"] == "blocked"
    assert (
        "installed Python package differs from the current source projection"
        in report["findings"]
    )


def test_install_path_preflight_rejects_relative_codex_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(install_researchguard, "CODEX_HOME", Path("relative-home"))
    monkeypatch.setattr(
        install_researchguard, "ACTIVE_SKILL_ROOT", Path("relative-home/skills")
    )
    monkeypatch.setattr(
        install_researchguard, "INSTALL_ROOT", Path("relative-home/researchguard")
    )
    monkeypatch.setattr(
        install_researchguard,
        "MANIFEST_PATH",
        Path("relative-home/researchguard/install-manifest.json"),
    )

    with pytest.raises(install_researchguard.InstallError, match="absolute path"):
        install_researchguard._validate_install_paths()


def test_install_path_preflight_rejects_linked_manifest_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "codex-home"
    skills = home / "skills"
    skills.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    install_root = home / "researchguard"
    try:
        install_root.symlink_to(external, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")
    monkeypatch.setattr(install_researchguard, "CODEX_HOME", home)
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", skills)
    monkeypatch.setattr(install_researchguard, "INSTALL_ROOT", install_root)
    monkeypatch.setattr(
        install_researchguard, "MANIFEST_PATH", install_root / "install-manifest.json"
    )

    with pytest.raises(install_researchguard.InstallError, match="unsafe path"):
        install_researchguard._validate_install_paths()




def test_suite_install_lock_rejects_a_concurrent_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "codex-home"
    skills = home / "skills"
    skills.mkdir(parents=True)
    install_root = home / "researchguard"
    monkeypatch.setattr(install_researchguard, "CODEX_HOME", home)
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", skills)
    monkeypatch.setattr(install_researchguard, "INSTALL_ROOT", install_root)
    monkeypatch.setattr(
        install_researchguard,
        "MANIFEST_PATH",
        install_root / "install-manifest.json",
    )

    with install_researchguard._suite_install_lock() as identity:
        assert identity["kind"] in {"windows-byte-lock", "posix-flock"}
        with pytest.raises(
            install_researchguard.InstallError,
            match="suite install lock is already held",
        ):
            with install_researchguard._suite_install_lock():
                pass


def test_suite_install_lock_accepts_a_stale_unlocked_lock_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "codex-home"
    skills = home / "skills"
    install_root = home / "researchguard"
    skills.mkdir(parents=True)
    install_root.mkdir()
    lock_path = install_root / "suite-install.lock"
    lock_path.write_bytes(b"\0")
    monkeypatch.setattr(install_researchguard, "CODEX_HOME", home)
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", skills)
    monkeypatch.setattr(install_researchguard, "INSTALL_ROOT", install_root)
    monkeypatch.setattr(
        install_researchguard,
        "MANIFEST_PATH",
        install_root / "install-manifest.json",
    )

    with install_researchguard._suite_install_lock() as identity:
        assert identity["path"] == str(lock_path.resolve(strict=True))


def test_suite_install_lock_releases_after_body_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "codex-home"
    skills = home / "skills"
    install_root = home / "researchguard"
    skills.mkdir(parents=True)
    monkeypatch.setattr(install_researchguard, "CODEX_HOME", home)
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", skills)
    monkeypatch.setattr(install_researchguard, "INSTALL_ROOT", install_root)
    monkeypatch.setattr(
        install_researchguard,
        "MANIFEST_PATH",
        install_root / "install-manifest.json",
    )

    with pytest.raises(RuntimeError, match="simulated install failure"):
        with install_researchguard._suite_install_lock():
            raise RuntimeError("simulated install failure")

    with install_researchguard._suite_install_lock() as identity:
        assert identity["kind"] in {"windows-byte-lock", "posix-flock"}


def test_package_snapshot_restores_exact_prior_distribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site_packages = tmp_path / "Python312" / "site-packages"
    old_package = site_packages / "researchguard/__init__.py"
    old_metadata = site_packages / "researchguard-1.0.0.dist-info/METADATA"
    old_package.parent.mkdir(parents=True)
    old_metadata.parent.mkdir()
    old_package.write_bytes(b"old package")
    old_metadata.write_bytes(b"Version: 1.0.0\n")
    old = _PackageDistribution(
        site_packages,
        "1.0.0",
        (
            "researchguard/__init__.py",
            "researchguard-1.0.0.dist-info/METADATA",
        ),
    )
    new_package = site_packages / "researchguard/__init__.py"
    new_metadata = site_packages / "researchguard-2.0.0.dist-info/METADATA"
    new = _PackageDistribution(
        site_packages,
        "2.0.0",
        (
            "researchguard/__init__.py",
            "researchguard-2.0.0.dist-info/METADATA",
        ),
    )

    def current_distribution(_name: str):
        if old_metadata.is_file():
            return old
        if new_metadata.is_file():
            return new
        raise install_researchguard.importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(
        install_researchguard.importlib.metadata,
        "distribution",
        current_distribution,
    )
    snapshot = install_researchguard._capture_package_state(tmp_path / "backup")

    old_package.unlink()
    old_metadata.unlink()
    new_package.parent.mkdir(parents=True, exist_ok=True)
    new_metadata.parent.mkdir()
    new_package.write_bytes(b"new package")
    new_metadata.write_bytes(b"Version: 2.0.0\n")

    result = install_researchguard._restore_package_state(snapshot)

    assert result["status"] == "passed", result["findings"]
    assert old_package.read_bytes() == b"old package"
    assert old_metadata.read_bytes() == b"Version: 1.0.0\n"
    assert not new_metadata.exists()








def test_manifest_snapshot_restores_prior_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = tmp_path / "install-manifest.json"
    manifest.write_bytes(b"prior manifest")
    monkeypatch.setattr(install_researchguard, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(
        install_researchguard,
        "_write_manifest_bytes",
        lambda body: manifest.write_bytes(body),
    )
    snapshot = install_researchguard._capture_manifest_state()
    manifest.write_bytes(b"new manifest")

    result = install_researchguard._restore_manifest_state(snapshot)

    assert result["status"] == "passed"
    assert manifest.read_bytes() == b"prior manifest"




def _skill_paths(tmp_path, monkeypatch):
    home = tmp_path / "home"
    active = home / "skills"
    active.mkdir(parents=True)
    source = tmp_path / "source"
    for member in ("alpha", "beta"):
        (source / member).mkdir(parents=True)
        (source / member / "SKILL.md").write_bytes(b"current " + member.encode())
        (active / member).mkdir()
        (active / member / "SKILL.md").write_bytes(b"prior " + member.encode())
    monkeypatch.setattr(install_researchguard, "CODEX_HOME", home)
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", active)
    monkeypatch.setattr(install_researchguard, "SKILL_SOURCE", source)
    monkeypatch.setattr(install_researchguard, "INSTALL_ROOT", home / "researchguard")
    monkeypatch.setattr(install_researchguard, "MANIFEST_PATH", home / "researchguard/install-manifest.json")
    monkeypatch.setattr(install_researchguard, "MEMBERS", ("alpha", "beta"))
    monkeypatch.setattr(install_researchguard, "RETIRED_SKILLS", ())
    return source, active


def test_all_members_are_prepared_and_verified_before_any_activation(tmp_path, monkeypatch):
    source, active = _skill_paths(tmp_path, monkeypatch)
    prepared = install_researchguard._prepare_skill_stages(tmp_path / "stages")
    assert (active / "alpha/SKILL.md").read_bytes() == b"prior alpha"
    activations = install_researchguard._activate_prepared_skills(prepared)
    for member in install_researchguard.MEMBERS:
        assert install_researchguard._inventory(active / member) == install_researchguard._inventory(source / member)
    assert install_researchguard._rollback_activated_skills(activations)["status"] == "passed"
    assert (active / "beta/SKILL.md").read_bytes() == b"prior beta"


def test_activation_failure_rolls_back_prior_members_in_reverse_order(tmp_path, monkeypatch):
    _, active = _skill_paths(tmp_path, monkeypatch)
    prepared = install_researchguard._prepare_skill_stages(tmp_path / "stages")
    copytree = install_researchguard.shutil.copytree
    def fail_second(source, destination, *args, **kwargs):
        if Path(destination) == active / "beta":
            raise OSError("second copy failed")
        return copytree(source, destination, *args, **kwargs)
    monkeypatch.setattr(install_researchguard.shutil, "copytree", fail_second)
    with pytest.raises(install_researchguard.InstallError) as caught:
        install_researchguard._activate_prepared_skills(prepared)
    assert caught.value.status == "blocked"
    for member in ("alpha", "beta"):
        assert (active / member / "SKILL.md").read_bytes() == b"prior " + member.encode()


def test_changed_stage_is_rejected_before_replacing_active_files(tmp_path, monkeypatch):
    _, active = _skill_paths(tmp_path, monkeypatch)
    prepared = install_researchguard._prepare_skill_stages(tmp_path / "stages")
    (prepared["alpha"]["stage"] / "SKILL.md").write_bytes(b"tampered")
    with pytest.raises(install_researchguard.InstallError, match="changed before activation"):
        install_researchguard._activate_prepared_skills(prepared)
    assert (active / "alpha/SKILL.md").read_bytes() == b"prior alpha"


def test_currentness_compares_files_without_an_author_tool_or_manifest(tmp_path, monkeypatch):
    _, active = _skill_paths(tmp_path, monkeypatch)
    prepared = install_researchguard._prepare_skill_stages(tmp_path / "stages")
    install_researchguard._activate_prepared_skills(prepared)
    console = tmp_path / "researchguard"
    console.write_bytes(b"console")
    monkeypatch.setattr(install_researchguard, "_installed_version", lambda: install_researchguard.VERSION)
    monkeypatch.setattr(install_researchguard, "_installed_package_root", lambda: install_researchguard.SOURCE_PACKAGE)
    monkeypatch.setattr(install_researchguard, "_installed_console_entrypoint", lambda: console)
    assert not install_researchguard.MANIFEST_PATH.exists()
    assert install_researchguard.check_current()["status"] == "pass"
    (active / "beta/SKILL.md").write_bytes(b"stale bytes")
    assert install_researchguard.check_current()["status"] == "blocked"


def _changed_states(tmp_path, monkeypatch):
    _, active = _skill_paths(tmp_path, monkeypatch)
    site = tmp_path / "site"
    package = site / "researchguard/__init__.py"
    metadata = site / "researchguard-1.0.0.dist-info/METADATA"
    package.parent.mkdir(parents=True)
    metadata.parent.mkdir()
    package.write_bytes(b"prior package")
    metadata.write_bytes(b"Version: 1.0.0")
    distribution = _PackageDistribution(site, "1.0.0", (
        "researchguard/__init__.py", "researchguard-1.0.0.dist-info/METADATA"))
    monkeypatch.setattr(install_researchguard.importlib.metadata, "distribution", lambda _: distribution)
    package_snapshot = install_researchguard._capture_package_state(tmp_path / "package-backup")
    manifest = install_researchguard.MANIFEST_PATH
    manifest.parent.mkdir()
    manifest.write_bytes(b"prior legacy manifest")
    manifest_snapshot = install_researchguard._capture_manifest_state()
    prepared = install_researchguard._prepare_skill_stages(tmp_path / "stages")
    activations = install_researchguard._activate_prepared_skills(prepared)
    package.write_bytes(b"new package")
    manifest.write_bytes(b"new manifest")
    return active, package, manifest, dict(activations=activations,
        package_snapshot=package_snapshot, manifest_snapshot=manifest_snapshot)


def test_suite_rollback_attempts_consumers_package_and_manifest(tmp_path, monkeypatch):
    active, package, manifest, snapshots = _changed_states(tmp_path, monkeypatch)
    result = install_researchguard._restore_suite_state(**snapshots)
    assert result["status"] == "passed"
    assert package.read_bytes() == b"prior package"
    assert manifest.read_bytes() == b"prior legacy manifest"
    for member in ("alpha", "beta"):
        assert (active / member / "SKILL.md").read_bytes() == b"prior " + member.encode()


def test_suite_rollback_is_cleanup_unconfirmed_but_attempts_every_domain(tmp_path, monkeypatch):
    active, package, manifest, snapshots = _changed_states(tmp_path, monkeypatch)
    def failed_package(_):
        raise OSError("package restoration failed")
    monkeypatch.setattr(install_researchguard, "_restore_package_state", failed_package)
    result = install_researchguard._restore_suite_state(**snapshots)
    assert result["status"] == "cleanup_unconfirmed"
    assert package.read_bytes() == b"new package"
    assert manifest.read_bytes() == b"prior legacy manifest"
    assert (active / "beta/SKILL.md").read_bytes() == b"prior beta"
    assert [row["domain"] for row in result["reports"]] == ["consumers", "python-package", "suite-manifest"]


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_late_install_failure_routes_all_state_through_suite_restoration(tmp_path, monkeypatch, cleanup_fails):
    source, active = _skill_paths(tmp_path, monkeypatch)
    # Prepare real prior distribution files; stage and activate in the actual installer.
    site = tmp_path / "site"
    package = site / "researchguard/__init__.py"
    package.parent.mkdir(parents=True)
    package.write_bytes(b"prior package")
    distribution = _PackageDistribution(site, install_researchguard.VERSION, ("researchguard/__init__.py",))
    monkeypatch.setattr(install_researchguard.importlib.metadata, "distribution", lambda _: distribution)
    monkeypatch.setattr(install_researchguard.importlib.metadata, "version", lambda _: install_researchguard.VERSION)
    manifest = install_researchguard.MANIFEST_PATH
    manifest.parent.mkdir()
    manifest.write_bytes(b"prior manifest")
    monkeypatch.setattr(install_researchguard, "_validate_source", lambda: None)
    def build_wheel(root, wheel_dir):
        wheel = wheel_dir / "researchguard.whl"
        wheel.write_bytes(b"wheel")
        return wheel
    monkeypatch.setattr(install_researchguard, "_build_package_wheel", build_wheel)
    def install_wheel(args, **kwargs):
        assert "install" in args
        package.write_bytes(b"new package")
    monkeypatch.setattr(install_researchguard, "_native_command", install_wheel)
    monkeypatch.setattr(install_researchguard, "check_current", lambda: {"status": "blocked", "findings": ["late failure"]})
    if cleanup_fails:
        def failed_package_restore(_snapshot):
            raise OSError("package restoration unavailable")
        monkeypatch.setattr(install_researchguard, "_restore_package_state", failed_package_restore)
    with pytest.raises(install_researchguard.InstallError) as caught:
        install_researchguard._install_locked({"kind": "test"})
    assert caught.value.status == ("cleanup_unconfirmed" if cleanup_fails else "blocked")
    if cleanup_fails:
        recovery = Path(caught.value.cleanup_report["recovery_directory"])
        assert recovery.is_dir()
        snapshot = caught.value.cleanup_report["package_snapshot"]
        assert Path(snapshot["files"][0]["backup"]).read_bytes() == b"prior package"
        assert Path(caught.value.cleanup_report["prior_manifest_backup"]).read_bytes() == b"prior manifest"
        assert package.read_bytes() == b"new package"
        install_researchguard.shutil.rmtree(recovery)
    else:
        assert package.read_bytes() == b"prior package"
    assert manifest.read_bytes() == b"prior manifest"
    for member in ("alpha", "beta"):
        assert (active / member / "SKILL.md").read_bytes() == b"prior " + member.encode()
