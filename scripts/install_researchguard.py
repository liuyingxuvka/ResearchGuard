"""Install or check the sole current ResearchGuard suite projection."""

from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PACKAGE = ROOT / "src" / "researchguard"
SKILL_SOURCE = ROOT / "skills"
CODEX_HOME = Path(
    os.environ.get("CODEX_HOME") or (Path.home() / ".codex")
).expanduser()
ACTIVE_SKILL_ROOT = CODEX_HOME / "skills"
INSTALL_ROOT = CODEX_HOME / "researchguard"
MANIFEST_PATH = INSTALL_ROOT / "install-manifest.json"
MEMBERS = (
    "researchguard",
    "logicguard",
    "sourceguard",
    "traceguard",
    "experimentguard",
)
RETIRED_SKILLS = (
    "logicguard-source-library",
    "logicguard-structured-artifact",
    "logicguard-model-deepening",
    "logicguard-artifact-synthesis",
    "logicguard-project-library-viewer",
    "traceguard-library",
)
VERSION = str(
    tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
)


class InstallError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status: str = "blocked",
        cleanup_report: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.cleanup_report = dict(cleanup_report or {})


def _source_package_version() -> str:
    path = SOURCE_PACKAGE / "__init__.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise InstallError(
            f"ResearchGuard source version declaration is unreadable: {type(exc).__name__}"
        ) from exc
    versions = [
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    if len(versions) != 1 or not versions[0]:
        raise InstallError("ResearchGuard source must declare exactly one __version__")
    return versions[0]


def _validate_source_version_identity() -> None:
    package_version = _source_package_version()
    if package_version != VERSION:
        raise InstallError(
            "ResearchGuard source version mismatch: "
            f"pyproject={VERSION}, package={package_version}"
        )


def _included(path: Path) -> bool:
    return (
        not {"__pycache__", ".skillguard"}.intersection(path.parts)
        and path.suffix not in {".pyc", ".pyo"}
    )


def _inventory(root: Path) -> dict[str, str]:
    if not root.is_dir():
        raise InstallError(f"required directory is missing: {root}")
    if _is_link_or_reparse(root):
        raise InstallError(f"unsafe linked directory: {root}")
    rows: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not _included(path.relative_to(root)):
            continue
        if _is_link_or_reparse(path):
            raise InstallError(f"unsafe linked file or directory: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        rows[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _validate_install_paths() -> dict[str, Path]:
    """Resolve the one authorized install root before any package or skill write."""

    lexical_home = Path(CODEX_HOME).expanduser()
    if not lexical_home.is_absolute():
        raise InstallError("CODEX_HOME must be an absolute path")
    if _is_link_or_reparse(lexical_home) or not lexical_home.is_dir():
        raise InstallError("CODEX_HOME is missing or is an unsafe link/reparse path")
    home = lexical_home.resolve(strict=True)
    expected_active = lexical_home / "skills"
    expected_install = lexical_home / "researchguard"
    if Path(ACTIVE_SKILL_ROOT).absolute() != expected_active.absolute():
        raise InstallError("active skill root is outside the authorized CODEX_HOME layout")
    if Path(INSTALL_ROOT).absolute() != expected_install.absolute():
        raise InstallError("ResearchGuard install root is outside the authorized CODEX_HOME layout")
    if Path(MANIFEST_PATH).absolute() != (expected_install / "install-manifest.json").absolute():
        raise InstallError("ResearchGuard install manifest path is outside the authorized layout")
    if _is_link_or_reparse(expected_active) or not expected_active.is_dir():
        raise InstallError("active skill root is missing or is an unsafe link/reparse path")
    active = expected_active.resolve(strict=True)
    if not active.is_relative_to(home):
        raise InstallError("active skill root escapes CODEX_HOME")
    if expected_install.exists() or expected_install.is_symlink():
        if _is_link_or_reparse(expected_install) or not expected_install.is_dir():
            raise InstallError("ResearchGuard install root is an unsafe path")
        install = expected_install.resolve(strict=True)
        if not install.is_relative_to(home):
            raise InstallError("ResearchGuard install root escapes CODEX_HOME")
    else:
        install = expected_install
    manifest = expected_install / "install-manifest.json"
    if manifest.exists() or manifest.is_symlink():
        if _is_link_or_reparse(manifest) or not manifest.is_file():
            raise InstallError("ResearchGuard install manifest is an unsafe path")
        if not manifest.resolve(strict=True).is_relative_to(home):
            raise InstallError("ResearchGuard install manifest escapes CODEX_HOME")
    suite_lock = expected_install / "suite-install.lock"
    if suite_lock.exists() or suite_lock.is_symlink():
        if _is_link_or_reparse(suite_lock) or not suite_lock.is_file():
            raise InstallError("ResearchGuard suite install lock is an unsafe path")
        if not suite_lock.resolve(strict=True).is_relative_to(home):
            raise InstallError("ResearchGuard suite install lock escapes CODEX_HOME")
    return {
        "home": home,
        "active": active,
        "install": install,
        "manifest": manifest,
        "suite_lock": suite_lock,
    }


def _acquire_file_lock(handle: object) -> str:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt  # noqa: PLC0415

        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise InstallError("ResearchGuard suite install lock is already held") from exc
        return "windows-byte-lock"
    import fcntl  # noqa: PLC0415

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        raise InstallError("ResearchGuard suite install lock is already held") from exc
    return "posix-flock"


def _release_file_lock(handle: object, lock_kind: str) -> None:
    handle.seek(0)
    if lock_kind == "windows-byte-lock":
        import msvcrt  # noqa: PLC0415

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl  # noqa: PLC0415

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def _suite_install_lock():
    """Hold one process-owned lease across every suite mutation and restoration."""

    paths = _validate_install_paths()
    install_root = paths["install"]
    if not install_root.exists():
        install_root.mkdir(parents=False, exist_ok=False)
    if _is_link_or_reparse(install_root) or not install_root.is_dir():
        raise InstallError("ResearchGuard install root became unsafe before locking")
    lock_path = paths["suite_lock"]
    handle = lock_path.open("a+b")
    lock_kind = ""
    try:
        if lock_path.stat().st_size == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        if _is_link_or_reparse(lock_path):
            raise InstallError("ResearchGuard suite install lock became unsafe")
        lock_kind = _acquire_file_lock(handle)
        yield {
            "path": str(lock_path.resolve(strict=True)),
            "kind": lock_kind,
        }
    finally:
        try:
            if lock_kind:
                _release_file_lock(handle, lock_kind)
        finally:
            # Closing the process-owned handle is the authoritative lease release,
            # including when an explicit unlock call itself raises.
            handle.close()














def _source_skill_projection(member: str) -> dict[str, object]:
    return {"files": _inventory(SKILL_SOURCE / member)}



def _audit_installed_skill(member: str, expected: dict[str, object]) -> dict[str, object]:
    observed = _inventory(ACTIVE_SKILL_ROOT / member)
    if observed != expected["files"]:
        raise InstallError(f"installed skill differs from current source: {member}")
    return {"status": "passed", "file_count": len(observed)}






def _digest(value: object) -> str:
    body = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _source_state() -> dict[str, object]:
    _validate_source_version_identity()
    skills = {
        member: _source_skill_projection(member)
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


def _prepare_package_build_context(temporary_root: Path) -> Path:
    """Copy the package inputs into the local temporary build workspace.

    Setuptools creates its intermediate ``build`` and ``*.egg-info`` trees
    relative to the project argument.  Building directly from ``ROOT`` makes a
    slow archive-backed checkout part of the timed wheel step and leaves build
    artifacts in the source tree when the command is interrupted.  Keeping the
    project metadata and package files together under the installer temporary
    directory makes the build location explicit and disposable.
    """

    context = temporary_root / "package-context"
    source_metadata = {
        "pyproject.toml": ROOT / "pyproject.toml",
        "README.md": ROOT / "README.md",
    }
    try:
        context.mkdir(parents=False, exist_ok=False)
        for name, source in source_metadata.items():
            if _is_link_or_reparse(source) or not source.is_file():
                raise InstallError(f"package build input is missing or unsafe: {name}")
            shutil.copy2(source, context / name)
        package_destination = context / "src" / "researchguard"
        package_destination.parent.mkdir(parents=True, exist_ok=False)
        if _is_link_or_reparse(SOURCE_PACKAGE) or not SOURCE_PACKAGE.is_dir():
            raise InstallError("ResearchGuard package build source is missing or unsafe")
        shutil.copytree(
            SOURCE_PACKAGE,
            package_destination,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
    except InstallError:
        raise
    except OSError as exc:
        raise InstallError(
            f"package build context preparation failed: {type(exc).__name__}: {exc}"
        ) from exc
    return context


def _build_package_wheel(temporary_root: Path, wheel_dir: Path) -> Path:
    """Build one wheel from the disposable local package context."""

    build_context = _prepare_package_build_context(temporary_root)
    _native_command(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            str(wheel_dir),
            str(build_context),
        ],
        timeout=600,
    )
    wheels = sorted(wheel_dir.glob(f"researchguard-{VERSION}-*.whl"))
    if len(wheels) != 1:
        raise InstallError(
            f"wheel build did not produce exactly one v{VERSION} artifact"
        )
    return wheels[0]


def _distribution_file_inventory(
    distribution: object,
) -> tuple[Path, dict[Path, str]]:
    """Return the exact regular-file inventory owned by one installed distribution."""

    base = Path(distribution.locate_file(".")).resolve(strict=True)
    # On Windows, pip places console scripts in ``<venv>\\Scripts`` while
    # package files live in ``<venv>\\Lib\\site-packages``.  Treating the
    # site-packages parent (``<venv>\\Lib``) as the interpreter root rejects
    # every normal wheel installation before the installer can verify it.
    # Keep the containment check rooted at the active interpreter when the
    # distribution is inside that interpreter; retain the local distribution
    # parent for the small synthetic distributions used by unit tests and for
    # externally managed user-site distributions.
    interpreter_root = Path(sys.prefix).resolve(strict=True)
    authority_root = (
        interpreter_root
        if base.is_relative_to(interpreter_root)
        else base.parent.resolve(strict=True)
    )
    files = list(distribution.files or ())
    if not files:
        raise InstallError("ResearchGuard distribution file inventory is empty")
    inventory: dict[Path, str] = {}
    for relative in files:
        lexical = Path(distribution.locate_file(relative))
        if not lexical.is_absolute():
            lexical = base / lexical
        if _is_link_or_reparse(lexical) or not lexical.is_file():
            raise InstallError(
                f"ResearchGuard distribution file is missing or unsafe: {relative}"
            )
        target = lexical.resolve(strict=True)
        if not target.is_relative_to(authority_root):
            raise InstallError(
                f"ResearchGuard distribution file escapes its interpreter root: {relative}"
            )
        if target in inventory:
            raise InstallError(
                f"ResearchGuard distribution file identity is duplicated: {relative}"
            )
        inventory[target] = hashlib.sha256(target.read_bytes()).hexdigest()
    return authority_root, inventory


def _capture_package_state(snapshot_root: Path) -> dict[str, object]:
    """Freeze exact pre-install package bytes before pip is allowed to mutate them."""

    snapshot_root.mkdir(parents=True, exist_ok=False)
    try:
        distribution = importlib.metadata.distribution("researchguard")
    except importlib.metadata.PackageNotFoundError:
        return {
            "status": "absent",
            "version": "",
            "authority_root": "",
            "files": [],
        }
    authority_root, inventory = _distribution_file_inventory(distribution)
    rows: list[dict[str, object]] = []
    for index, (target, content_hash) in enumerate(sorted(inventory.items())):
        backup = snapshot_root / f"{index:06d}.bin"
        shutil.copy2(target, backup)
        rows.append(
            {
                "target": str(target),
                "backup": str(backup),
                "content_hash": content_hash,
                "mode": stat.S_IMODE(target.stat().st_mode),
            }
        )
    return {
        "status": "present",
        "version": str(distribution.version),
        "authority_root": str(authority_root),
        "files": rows,
    }


def _remove_distribution_files(
    authority_root: Path,
    inventory: Mapping[Path, str],
) -> None:
    for target in sorted(inventory, key=lambda path: len(path.parts), reverse=True):
        if not target.is_relative_to(authority_root):
            raise InstallError("current package cleanup target escapes its interpreter root")
        if target.exists() or target.is_symlink():
            if _is_link_or_reparse(target) or not target.is_file():
                raise InstallError(f"current package cleanup target is unsafe: {target}")
            target.unlink()
    parents = sorted(
        {
            parent
            for target in inventory
            for parent in target.parents
            if parent != authority_root and parent.is_relative_to(authority_root)
        },
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for parent in parents:
        try:
            parent.rmdir()
        except OSError:
            continue


def _restore_snapshot_file(
    *,
    target: Path,
    backup: Path,
    authority_root: Path,
    mode: int,
) -> None:
    if not target.is_relative_to(authority_root):
        raise InstallError("package restoration target escapes its interpreter root")
    if _is_link_or_reparse(backup) or not backup.is_file():
        raise InstallError("package restoration backup is missing or unsafe")
    relative_parent = target.parent.relative_to(authority_root)
    cursor = authority_root
    for part in relative_parent.parts:
        cursor = cursor / part
        if cursor.exists() or cursor.is_symlink():
            if _is_link_or_reparse(cursor) or not cursor.is_dir():
                raise InstallError(f"package restoration parent is unsafe: {cursor}")
        else:
            cursor.mkdir()
    if target.exists() or target.is_symlink():
        if _is_link_or_reparse(target) or not target.is_file():
            raise InstallError(f"package restoration target is unsafe: {target}")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{target.name}-restore-",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            with backup.open("rb") as source:
                shutil.copyfileobj(source, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None and temporary.is_file():
            temporary.unlink()


def _restore_package_state(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Restore the exact package distribution or return cleanup_unconfirmed."""

    findings: list[str] = []
    try:
        current_distribution = importlib.metadata.distribution("researchguard")
    except importlib.metadata.PackageNotFoundError:
        current_distribution = None
    if current_distribution is None:
        findings.append("current distribution inventory unavailable before cleanup")
    else:
        try:
            current_root, current_inventory = _distribution_file_inventory(
                current_distribution
            )
            _remove_distribution_files(current_root, current_inventory)
        except Exception as exc:
            findings.append(f"current distribution cleanup failed: {type(exc).__name__}: {exc}")

    prior_status = str(snapshot.get("status", ""))
    if prior_status == "present":
        try:
            authority_root = Path(str(snapshot["authority_root"])).resolve(strict=True)
            rows = snapshot.get("files", [])
            if not isinstance(rows, list) or not rows:
                raise InstallError("package restoration snapshot inventory is empty")
            expected: dict[Path, str] = {}
            for row in rows:
                if not isinstance(row, Mapping):
                    raise InstallError("package restoration row is malformed")
                target = Path(str(row.get("target", "")))
                backup = Path(str(row.get("backup", "")))
                content_hash = str(row.get("content_hash", ""))
                mode = row.get("mode")
                if not target.is_absolute() or not content_hash or not isinstance(mode, int):
                    raise InstallError("package restoration identity is malformed")
                _restore_snapshot_file(
                    target=target,
                    backup=backup,
                    authority_root=authority_root,
                    mode=mode,
                )
                expected[target.resolve(strict=True)] = content_hash
            importlib.invalidate_caches()
            restored = importlib.metadata.distribution("researchguard")
            restored_root, restored_inventory = _distribution_file_inventory(restored)
            if (
                restored_root != authority_root
                or str(restored.version) != str(snapshot.get("version", ""))
                or restored_inventory != expected
            ):
                raise InstallError("restored package identity does not match the snapshot")
        except Exception as exc:
            findings.append(f"prior package restoration failed: {type(exc).__name__}: {exc}")
    elif prior_status == "absent":
        importlib.invalidate_caches()
        try:
            importlib.metadata.distribution("researchguard")
        except importlib.metadata.PackageNotFoundError:
            pass
        else:
            findings.append("ResearchGuard distribution remains after absent-state rollback")
    else:
        findings.append("package restoration snapshot status is invalid")
    return {
        "status": "passed" if not findings else "cleanup_unconfirmed",
        "findings": findings,
        "restored_version": str(snapshot.get("version", "")),
    }


def _capture_manifest_state() -> dict[str, object]:
    if MANIFEST_PATH.is_file():
        return {"status": "present", "body": MANIFEST_PATH.read_bytes()}
    return {"status": "absent", "body": b""}


def _restore_manifest_state(snapshot: Mapping[str, object]) -> dict[str, object]:
    findings: list[str] = []
    try:
        status = str(snapshot.get("status", ""))
        if status == "present":
            body = snapshot.get("body")
            if not isinstance(body, bytes):
                raise InstallError("manifest restoration bytes are unavailable")
            _write_manifest_bytes(body)
            if not MANIFEST_PATH.is_file() or MANIFEST_PATH.read_bytes() != body:
                raise InstallError("manifest restoration identity mismatch")
        elif status == "absent":
            if MANIFEST_PATH.exists() or MANIFEST_PATH.is_symlink():
                _validate_install_paths()
                if _is_link_or_reparse(MANIFEST_PATH) or not MANIFEST_PATH.is_file():
                    raise InstallError("manifest cleanup target is unsafe")
                MANIFEST_PATH.unlink()
            if MANIFEST_PATH.exists() or MANIFEST_PATH.is_symlink():
                raise InstallError("manifest remains after absent-state rollback")
        else:
            raise InstallError("manifest restoration snapshot status is invalid")
    except Exception as exc:
        findings.append(f"manifest restoration failed: {type(exc).__name__}: {exc}")
    return {
        "status": "passed" if not findings else "cleanup_unconfirmed",
        "findings": findings,
    }


def _validate_source() -> None:
    _validate_source_version_identity()
    # The source checker runs the provider-neutral denominator and four
    # current member probes serially.  On the archive-backed source checkout
    # that legitimate cold check can take several minutes; keep it bounded
    # while giving the complete pre-install check enough time to finish.
    _native_command(
        [
            sys.executable,
            "scripts/check_researchguard_suite.py",
            "--member",
            "all",
            "--json",
        ],
        timeout=1200,
    )


def _prepare_skill_stages(stage_root: Path) -> dict[str, dict[str, object]]:
    stage_root.mkdir(parents=True, exist_ok=False)
    prepared: dict[str, dict[str, object]] = {}
    for member in MEMBERS:
        source = SKILL_SOURCE / member
        expected = _inventory(source)
        if "SKILL.md" not in expected:
            raise InstallError(f"source skill entry is missing: {member}")
        stage = stage_root / member
        shutil.copytree(source, stage, ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "*.pyo", ".skillguard"
        ))
        if _inventory(stage) != expected:
            raise InstallError(f"staged skill differs from source: {member}")
        prepared[member] = {"stage": stage, "files": expected}
    return prepared



def _rollback_activated_skills(activations: list[dict[str, object]]) -> dict[str, object]:
    reports: list[dict[str, object]] = []
    for activation in reversed(activations):
        member = str(activation["skill_id"])
        active = ACTIVE_SKILL_ROOT / member
        backup = Path(activation["backup"])
        try:
            if _is_link_or_reparse(active):
                raise InstallError(f"active skill became an unsafe link: {member}")
            if active.exists():
                shutil.rmtree(active)
            if activation["had_prior"]:
                shutil.move(str(backup), str(active))
                if _inventory(active) != activation["prior_files"]:
                    raise InstallError(f"restored skill bytes differ: {member}")
            reports.append({"skill_id": member, "status": "passed"})
        except Exception as exc:
            reports.append({"skill_id": member, "status": "cleanup_unconfirmed",
                            "findings": [f"{type(exc).__name__}: {exc}"]})
    return {"status": "passed" if all(r["status"] == "passed" for r in reports)
            else "cleanup_unconfirmed", "reports": reports}



def _cleanup_result(
    domain: str,
    action: object,
) -> dict[str, object]:
    try:
        raw_result = action()
        if not isinstance(raw_result, Mapping):
            raise InstallError("cleanup result is malformed")
        result = dict(raw_result)
        if result.get("status") not in {"passed", "cleanup_unconfirmed"}:
            result = {
                "status": "cleanup_unconfirmed",
                "findings": ["cleanup terminal status is invalid"],
                "observed_result": result,
            }
    except Exception as exc:
        result = {
            "status": "cleanup_unconfirmed",
            "findings": [f"cleanup exception: {type(exc).__name__}: {exc}"],
        }
    result["domain"] = domain
    return result


def _restore_suite_state(
    *,
    activations: list[dict[str, object]],
    package_snapshot: Mapping[str, object],
    manifest_snapshot: Mapping[str, object],
    prior_consumer_cleanup: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Attempt every rollback domain while the caller still holds the suite lock."""

    if prior_consumer_cleanup is None:
        consumer_action = lambda: (
            _rollback_activated_skills(activations)
            if activations
            else {"status": "passed", "reports": [], "blockers": []}
        )
    else:
        consumer_action = lambda: dict(prior_consumer_cleanup)
    reports = [
        _cleanup_result("consumers", consumer_action),
        _cleanup_result("python-package", lambda: _restore_package_state(package_snapshot)),
        _cleanup_result("suite-manifest", lambda: _restore_manifest_state(manifest_snapshot)),
    ]
    cleanup_confirmed = all(report.get("status") == "passed" for report in reports)
    return {
        "status": "passed" if cleanup_confirmed else "cleanup_unconfirmed",
        "reports": reports,
        "cleanup_confirmed": cleanup_confirmed,
    }





def _activate_prepared_skills(prepared: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    residuals = _retired_skill_residuals()
    if residuals:
        raise InstallError(f"retired skill residuals require cleanup: {residuals}")
    activations: list[dict[str, object]] = []
    try:
        for member in MEMBERS:
            row = prepared[member]
            stage = Path(row["stage"])
            if _inventory(stage) != row["files"]:
                raise InstallError(f"staged skill changed before activation: {member}")
            active = ACTIVE_SKILL_ROOT / member
            if _is_link_or_reparse(active):
                raise InstallError(f"active skill is an unsafe link: {member}")
            had_prior = active.exists()
            prior_files = _inventory(active) if had_prior else {}
            backup = stage.parent / "rollback" / member
            backup.parent.mkdir(exist_ok=True)
            if had_prior:
                shutil.move(str(active), str(backup))
            activation = {"skill_id": member, "backup": backup,
                          "had_prior": had_prior, "prior_files": prior_files}
            activations.append(activation)
            shutil.copytree(stage, active)
            if _inventory(active) != row["files"]:
                raise InstallError(f"copied skill differs from stage: {member}")
    except Exception as exc:
        cleanup = _rollback_activated_skills(activations)
        raise InstallError(
            f"skill copy failed: {type(exc).__name__}: {exc}",
            status="blocked" if cleanup["status"] == "passed" else "cleanup_unconfirmed",
            cleanup_report={"consumers": cleanup},
        ) from exc
    return activations



def _retired_skill_residuals() -> list[str]:
    return [
        skill_id
        for skill_id in RETIRED_SKILLS
        if (ACTIVE_SKILL_ROOT / skill_id).exists()
        or (ACTIVE_SKILL_ROOT / skill_id).is_symlink()
    ]





def _write_manifest_bytes(body: bytes) -> None:
    paths = _validate_install_paths()
    install_root = paths["install"]
    if not install_root.exists():
        install_root.mkdir(parents=False, exist_ok=False)
    if _is_link_or_reparse(install_root) or not install_root.is_dir():
        raise InstallError("ResearchGuard install root became unsafe before manifest write")
    install_root = install_root.resolve(strict=True)
    if not install_root.is_relative_to(paths["home"]):
        raise InstallError("ResearchGuard install root escaped before manifest write")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".install-manifest-",
            suffix=".tmp",
            dir=install_root,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        if _is_link_or_reparse(temporary_path):
            raise InstallError("temporary install manifest became an unsafe path")
        os.replace(temporary_path, install_root / "install-manifest.json")
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.is_file():
            temporary_path.unlink()





def check_current() -> dict[str, object]:
    source = _source_state()
    findings: list[str] = []
    try:
        _validate_install_paths()
    except InstallError as exc:
        findings.append(str(exc))
    try:
        installed_version = _installed_version()
    except InstallError as exc:
        installed_version = ""
        findings.append(str(exc))
    if installed_version and installed_version != VERSION:
        findings.append(
            f"installed version mismatch: expected {VERSION}, got {installed_version}"
        )
    installed_package_root: Path | None = None
    package_import_mode = "unavailable"
    package_inventory_observed = False
    try:
        installed_package_root = _installed_package_root()
        package_import_mode = (
            "repository-source-projection"
            if installed_package_root == SOURCE_PACKAGE.resolve(strict=True)
            else "installed-distribution"
        )
        installed_package = _inventory(installed_package_root)
        package_inventory_observed = True
    except (InstallError, OSError) as exc:
        installed_package = {}
        findings.append(str(exc))
    if package_inventory_observed and installed_package != source["package"]:
        findings.append("installed Python package differs from the current source projection")
    try:
        console_entrypoint = str(_installed_console_entrypoint())
    except InstallError as exc:
        console_entrypoint = ""
        findings.append(str(exc))
    installed_skills: dict[str, dict[str, object]] = {}
    for member in MEMBERS:
        try:
            installed_skills[member] = _audit_installed_skill(
                member,
                source["skills"][member],
            )
        except InstallError as exc:
            findings.append(str(exc))
    residuals = _retired_skill_residuals()
    if residuals:
        findings.append(f"retired skill residuals remain: {residuals}")
    return {
        "schema_version": "researchguard.install-check.v1",
        "status": "pass" if not findings else "blocked",
        "version": VERSION,
        "source_fingerprint": source["source_fingerprint"],
        "package_root": str(installed_package_root) if installed_package_root else "",
        "package_import_mode": package_import_mode,
        "console_entrypoint": console_entrypoint,
        "installed_skill_ids": sorted(installed_skills),
        "retired_residuals": residuals,
        "findings": findings,
        "claim_boundary": (
            "Pass proves current package bytes, console declaration, five skill file "
            "inventories and retired-skill absence. It does not prove Git or release identity."
        ),
    }


@contextmanager
def _installation_workspace():
    temporary_root = Path(tempfile.mkdtemp(prefix="researchguard-install-"))
    retain = False
    try:
        yield temporary_root
    except InstallError as exc:
        retain = exc.status == "cleanup_unconfirmed"
        if retain:
            exc.cleanup_report["recovery_directory"] = str(temporary_root)
        raise
    finally:
        if not retain:
            shutil.rmtree(temporary_root)


def _install_locked(lock_identity: Mapping[str, object]) -> dict[str, object]:
    _validate_install_paths()
    residuals = _retired_skill_residuals()
    if residuals:
        raise InstallError(
            "retired skill residuals require explicit lifecycle cleanup before "
            f"package installation: {residuals}"
        )
    _validate_source()
    try:
        prior_version = importlib.metadata.version("researchguard")
    except importlib.metadata.PackageNotFoundError:
        prior_version = ""
    if prior_version and tuple(map(int, prior_version.split("."))) > tuple(
        map(int, VERSION.split("."))
    ):
        raise InstallError(
            f"direct current replacement refuses to downgrade newer ResearchGuard "
            f"distribution {prior_version} to {VERSION}"
        )
    with _installation_workspace() as temporary_root:
        prepared = _prepare_skill_stages(temporary_root / "skills")
        wheel_dir = temporary_root / "wheel"
        wheel_dir.mkdir()
        wheel = _build_package_wheel(temporary_root, wheel_dir)
        package_snapshot = _capture_package_state(
            temporary_root / "package-rollback"
        )
        manifest_snapshot = _capture_manifest_state()
        activations: list[dict[str, object]] = []
        try:
            _native_command(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-deps",
                    "--force-reinstall",
                    str(wheel),
                ],
                timeout=600,
            )
            activations = _activate_prepared_skills(prepared)
            # The old suite manifest carried retired author-tool authority.
            # Retire it only after package and skill replacement; rollback still
            # restores its exact old bytes if any later verification fails.
            if MANIFEST_PATH.exists():
                MANIFEST_PATH.unlink()
            report = check_current()
            if report["status"] != "pass":
                raise InstallError(json.dumps(report, ensure_ascii=False))
            console = str(_installed_console_entrypoint())
            _native_command([console, "--version"])
            for command in ("logic", "source", "trace", "experiment"):
                _native_command([console, command, "--help"])
        except Exception as exc:
            prior_consumer_cleanup = None
            if isinstance(exc, InstallError):
                candidate = exc.cleanup_report.get("consumers")
                if isinstance(candidate, Mapping):
                    prior_consumer_cleanup = candidate
            rollback = _restore_suite_state(
                activations=activations,
                package_snapshot=package_snapshot,
                manifest_snapshot=manifest_snapshot,
                prior_consumer_cleanup=prior_consumer_cleanup,
            )
            failure = {
                "type": type(exc).__name__,
                "status": (
                    exc.status if isinstance(exc, InstallError) else "blocked"
                ),
                "message": str(exc),
            }
            cleanup_report = {**rollback, "original_failure": failure}
            if rollback["status"] != "passed":
                # Keep the original byte copies and their existing target map
                # available for recovery; this is not an install authority.
                cleanup_report["package_snapshot"] = dict(package_snapshot)
                if manifest_snapshot.get("status") == "present":
                    backup = temporary_root / "prior-install-manifest.bin"
                    try:
                        backup.write_bytes(bytes(manifest_snapshot["body"]))
                        cleanup_report["prior_manifest_backup"] = str(backup)
                    except OSError as backup_error:
                        cleanup_report["backup_finding"] = str(backup_error)
                raise InstallError(
                    "suite installation failed and restoration is cleanup_unconfirmed: "
                    f"{json.dumps(cleanup_report, ensure_ascii=False)}",
                    status="cleanup_unconfirmed",
                    cleanup_report=cleanup_report,
                ) from exc
            raise InstallError(
                "suite installation failed and the prior Python package, all activated "
                "consumers, and suite manifest were restored: "
                f"{exc}",
                cleanup_report=cleanup_report,
            ) from exc
        report["suite_install_lock"] = {
            "kind": str(lock_identity.get("kind", "")),
            "held_through_terminal_verification": True,
        }
    return report


def install() -> dict[str, object]:
    with _suite_install_lock() as lock_identity:
        return _install_locked(lock_identity)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = check_current() if args.check else install()
    except Exception as exc:
        status = exc.status if isinstance(exc, InstallError) else "blocked"
        report = {
            "schema_version": "researchguard.install-check.v1",
            "status": status,
            "findings": [str(exc)],
        }
        if isinstance(exc, InstallError) and exc.cleanup_report:
            report["cleanup_report"] = exc.cleanup_report
    print(
        json.dumps(report, ensure_ascii=False, indent=2)
        if args.json
        else report
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
