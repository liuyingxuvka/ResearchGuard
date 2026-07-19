"""Install or check the sole current ResearchGuard suite projection."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PACKAGE = ROOT / "src" / "researchguard"
SKILL_SOURCE = ROOT / "skills"
ACTIVE_SKILL_ROOT = Path.home() / ".codex" / "skills"
INSTALL_ROOT = Path.home() / ".codex" / "researchguard"
MANIFEST_PATH = INSTALL_ROOT / "install-manifest.json"
MEMBERS = ("researchguard", "logicguard", "sourceguard", "traceguard")
RETIRED_SKILLS = (
    "logicguard-source-library",
    "logicguard-structured-artifact",
    "logicguard-model-deepening",
    "logicguard-artifact-synthesis",
    "logicguard-project-library-viewer",
    "traceguard-library",
)
VERSION = "0.1.2"


class InstallError(RuntimeError):
    pass


def _included(path: Path) -> bool:
    return "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}


def _inventory(root: Path, *, exclude_skillguard: bool = False) -> dict[str, str]:
    if not root.is_dir():
        raise InstallError(f"required directory is missing: {root}")
    rows: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if not _included(relative):
            continue
        if exclude_skillguard and ".skillguard" in relative.parts:
            continue
        rows[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def _digest(value: object) -> str:
    body = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _source_state() -> dict[str, object]:
    skills = {
        member: _inventory(SKILL_SOURCE / member, exclude_skillguard=True)
        for member in MEMBERS
    }
    package = _inventory(SOURCE_PACKAGE)
    return {
        "version": VERSION,
        "skills": skills,
        "package": package,
        "source_fingerprint": _digest({"skills": skills, "package": package}),
    }


def _installed_package_root() -> Path:
    spec = importlib.util.find_spec("researchguard")
    if spec is None or spec.submodule_search_locations is None:
        raise InstallError("installed ResearchGuard package is unavailable")
    roots = list(spec.submodule_search_locations)
    if len(roots) != 1:
        raise InstallError("installed ResearchGuard package has ambiguous roots")
    return Path(roots[0]).resolve()


def _installed_version() -> str:
    try:
        return importlib.metadata.version("researchguard")
    except importlib.metadata.PackageNotFoundError as exc:
        raise InstallError("ResearchGuard distribution metadata is unavailable") from exc


def _installed_console_entrypoint() -> Path:
    try:
        distribution = importlib.metadata.distribution("researchguard")
    except importlib.metadata.PackageNotFoundError as exc:
        raise InstallError("ResearchGuard distribution metadata is unavailable") from exc
    entries = [
        entry
        for entry in distribution.entry_points
        if entry.group == "console_scripts"
        and entry.name == "researchguard"
        and entry.value == "researchguard.cli:main"
    ]
    if len(entries) != 1:
        raise InstallError(
            "installed distribution must declare exactly one researchguard console entry"
        )
    candidates = [
        Path(distribution.locate_file(relative)).resolve()
        for relative in distribution.files or ()
        if Path(str(relative)).name.lower() in {"researchguard", "researchguard.exe"}
    ]
    current = sorted({path for path in candidates if path.is_file()})
    if len(current) != 1:
        raise InstallError(
            "installed distribution must materialize exactly one researchguard console executable"
        )
    return current[0]


def _native_command(args: list[str], *, timeout: int = 300) -> None:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise InstallError(
            f"command failed ({completed.returncode}): {' '.join(args)}\n"
            f"{completed.stdout}\n{completed.stderr}"
        )


def _validate_source() -> None:
    _native_command(
        [
            sys.executable,
            "scripts/check_researchguard_suite.py",
            "--member",
            "all",
            "--json",
        ]
    )


def _copy_consumer(source: Path, destination: Path) -> None:
    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name == ".skillguard"}

    shutil.copytree(source, destination, ignore=ignore)


def _activate_skills() -> tuple[Path, Path]:
    ACTIVE_SKILL_ROOT.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    stage = ACTIVE_SKILL_ROOT / f".researchguard-stage-{token}"
    backup = ACTIVE_SKILL_ROOT / f".researchguard-backup-{token}"
    stage.mkdir()
    backup.mkdir()
    for member in MEMBERS:
        _copy_consumer(SKILL_SOURCE / member, stage / member)
    touched = (*MEMBERS, *RETIRED_SKILLS)
    try:
        for name in touched:
            active = ACTIVE_SKILL_ROOT / name
            if active.exists():
                os.replace(active, backup / name)
        for member in MEMBERS:
            os.replace(stage / member, ACTIVE_SKILL_ROOT / member)
        stage.rmdir()
    except Exception:
        for member in MEMBERS:
            active = ACTIVE_SKILL_ROOT / member
            if active.exists():
                shutil.rmtree(active)
        for name in touched:
            saved = backup / name
            if saved.exists():
                os.replace(saved, ACTIVE_SKILL_ROOT / name)
        shutil.rmtree(stage, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)
        raise
    return stage, backup


def _restore_skills(backup: Path) -> None:
    for member in MEMBERS:
        active = ACTIVE_SKILL_ROOT / member
        if active.exists():
            shutil.rmtree(active)
    for name in (*MEMBERS, *RETIRED_SKILLS):
        saved = backup / name
        if saved.exists():
            os.replace(saved, ACTIVE_SKILL_ROOT / name)
    shutil.rmtree(backup, ignore_errors=True)


def _write_manifest(payload: dict[str, object]) -> None:
    INSTALL_ROOT.mkdir(parents=True, exist_ok=True)
    temporary = MANIFEST_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, MANIFEST_PATH)


def check_current() -> dict[str, object]:
    source = _source_state()
    findings: list[str] = []
    try:
        installed_version = _installed_version()
    except InstallError as exc:
        installed_version = ""
        findings.append(str(exc))
    if installed_version and installed_version != VERSION:
        findings.append(
            f"installed version mismatch: expected {VERSION}, got {installed_version}"
        )
    try:
        installed_package = _inventory(_installed_package_root())
    except InstallError as exc:
        installed_package = {}
        findings.append(str(exc))
    if installed_package and installed_package != source["package"]:
        findings.append("installed Python package differs from the current source projection")
    installed_skills: dict[str, dict[str, str]] = {}
    for member in MEMBERS:
        active = ACTIVE_SKILL_ROOT / member
        if not active.is_dir():
            findings.append(f"installed skill is missing: {member}")
            continue
        current = _inventory(active)
        installed_skills[member] = current
        if current != source["skills"][member]:
            findings.append(f"installed skill differs from current source: {member}")
        if (active / ".skillguard").exists():
            findings.append(f"consumer skill contains author control files: {member}")
    residuals = [
        skill_id
        for skill_id in RETIRED_SKILLS
        if (ACTIVE_SKILL_ROOT / skill_id).exists()
    ]
    if residuals:
        findings.append(f"retired skill residuals remain: {residuals}")
    if not MANIFEST_PATH.is_file():
        findings.append("installation manifest is missing")
        manifest: dict[str, object] = {}
    else:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if manifest.get("source_fingerprint") != source["source_fingerprint"]:
            findings.append("installation manifest is stale")
    return {
        "schema_version": "researchguard.install-check.v1",
        "status": "pass" if not findings else "blocked",
        "version": VERSION,
        "source_fingerprint": source["source_fingerprint"],
        "installed_skill_ids": sorted(installed_skills),
        "retired_residuals": residuals,
        "findings": findings,
    }


def install() -> dict[str, object]:
    _validate_source()
    try:
        prior_version = importlib.metadata.version("researchguard")
    except importlib.metadata.PackageNotFoundError:
        prior_version = ""
    if prior_version not in {"", "0.1.1", VERSION}:
        raise InstallError(
            f"direct v0.1.2 replacement requires v0.1.1, v0.1.2, or no prior "
            f"ResearchGuard distribution; found {prior_version}"
        )
    prior_manifest = MANIFEST_PATH.read_bytes() if MANIFEST_PATH.is_file() else None

    with tempfile.TemporaryDirectory(prefix="researchguard-wheel-") as temporary:
        wheel_dir = Path(temporary)
        _native_command(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--wheel-dir",
                str(wheel_dir),
                ".",
            ],
            timeout=600,
        )
        wheels = sorted(wheel_dir.glob(f"researchguard-{VERSION}-*.whl"))
        if len(wheels) != 1:
            raise InstallError(
                f"wheel build did not produce exactly one v{VERSION} artifact"
            )
        _native_command(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--force-reinstall",
                str(wheels[0]),
            ],
            timeout=600,
        )

    _stage, backup = _activate_skills()
    try:
        source = _source_state()
        _write_manifest(
            {
                "schema_version": "researchguard.install-manifest.v1",
                "version": VERSION,
                "skill_ids": list(MEMBERS),
                "retired_skill_ids": list(RETIRED_SKILLS),
                "source_fingerprint": source["source_fingerprint"],
                "package_fingerprint": _digest(source["package"]),
                "skill_fingerprints": {
                    member: _digest(source["skills"][member]) for member in MEMBERS
                },
            }
        )
        report = check_current()
        if report["status"] != "pass":
            raise InstallError(json.dumps(report, ensure_ascii=False))
        console = str(_installed_console_entrypoint())
        _native_command([console, "--version"])
        for command in ("logic", "source", "trace"):
            _native_command([console, command, "--help"])
    except Exception:
        _restore_skills(backup)
        if prior_manifest is None:
            if MANIFEST_PATH.exists():
                MANIFEST_PATH.unlink()
        else:
            INSTALL_ROOT.mkdir(parents=True, exist_ok=True)
            temporary_manifest = MANIFEST_PATH.with_suffix(".restore")
            temporary_manifest.write_bytes(prior_manifest)
            os.replace(temporary_manifest, MANIFEST_PATH)
        raise
    shutil.rmtree(backup)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = check_current() if args.check else install()
    except Exception as exc:
        report = {
            "schema_version": "researchguard.install-check.v1",
            "status": "blocked",
            "findings": [str(exc)],
        }
    print(
        json.dumps(report, ensure_ascii=False, indent=2)
        if args.json
        else report
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
