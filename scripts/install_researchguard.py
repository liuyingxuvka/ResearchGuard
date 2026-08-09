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
import re
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
SKILLGUARD_SCRIPTS_ROOT = CODEX_HOME / "skills" / "skillguard" / "scripts"
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
TRANSACTION_ID_PATTERN = re.compile(r"^target-install-[0-9a-f]{32}$")
CANONICAL_HASH_PATTERN = re.compile(r"^[0-9A-F]{64}$")


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
    return "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}


def _inventory(root: Path) -> dict[str, str]:
    if not root.is_dir():
        raise InstallError(f"required directory is missing: {root}")
    rows: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if not _included(relative):
            continue
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


def _skillguard_api(module_name: str):
    lexical_scripts = Path(SKILLGUARD_SCRIPTS_ROOT).expanduser()
    if not lexical_scripts.is_absolute():
        raise InstallError("current SkillGuard authority root must be absolute")
    if _is_link_or_reparse(lexical_scripts) or not lexical_scripts.is_dir():
        raise InstallError("current SkillGuard authority root is missing or unsafe")
    scripts_root = lexical_scripts.resolve(strict=True)
    package_root = scripts_root / "skillguard_v2"
    module_path = package_root / f"{module_name}.py"
    if (
        _is_link_or_reparse(package_root)
        or not package_root.is_dir()
        or _is_link_or_reparse(module_path)
        or not module_path.is_file()
    ):
        raise InstallError(
            f"current SkillGuard {module_name.replace('_', '-')} authority is unavailable"
        )
    resolved_module_path = module_path.resolve(strict=True)
    if not resolved_module_path.is_relative_to(scripts_root):
        raise InstallError(
            f"current SkillGuard {module_name.replace('_', '-')} authority escapes its installation"
        )
    scripts_text = str(scripts_root)
    inserted = False
    if scripts_text not in sys.path:
        sys.path.insert(0, scripts_text)
        inserted = True
    try:
        module = importlib.import_module(f"skillguard_v2.{module_name}")
    except ImportError as exc:
        raise InstallError(
            f"current SkillGuard {module_name.replace('_', '-')} authority cannot be imported"
        ) from exc
    finally:
        if inserted:
            sys.path.remove(scripts_text)
    resolved_module = Path(str(getattr(module, "__file__", ""))).resolve()
    if resolved_module != resolved_module_path:
        raise InstallError(
            f"current SkillGuard {module_name.replace('_', '-')} authority resolved from an "
            "unexpected installation"
        )
    resolved_package_root = package_root.resolve(strict=True)
    foreign_modules: list[str] = []
    for loaded_name, loaded_module in tuple(sys.modules.items()):
        if loaded_name != "skillguard_v2" and not loaded_name.startswith(
            "skillguard_v2."
        ):
            continue
        loaded_path = getattr(loaded_module, "__file__", None)
        try:
            current_path = Path(str(loaded_path)).resolve(strict=True)
        except (OSError, RuntimeError):
            foreign_modules.append(loaded_name)
            continue
        if not current_path.is_relative_to(resolved_package_root):
            foreign_modules.append(loaded_name)
    if foreign_modules:
        raise InstallError(
            "current SkillGuard authority loaded foreign dependency modules: "
            f"{sorted(foreign_modules)}"
        )
    return module


def _consumer_distribution_api():
    return _skillguard_api("consumer_distribution")


def _target_installation_api():
    _consumer_distribution_api()
    return _skillguard_api("target_installation")


def _compiled_contract(member: str) -> dict[str, object]:
    member_root = (SKILL_SOURCE / member).resolve(strict=True)
    control_root = member_root / ".skillguard"
    path = control_root / "compiled-contract.json"
    if (
        _is_link_or_reparse(control_root)
        or not control_root.is_dir()
        or _is_link_or_reparse(path)
        or not path.is_file()
    ):
        raise InstallError(f"compiled consumer contract is missing: {member}")
    path = path.resolve(strict=True)
    if not path.is_relative_to(member_root):
        raise InstallError(f"compiled consumer contract escapes its member root: {member}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("skill_id") != member:
        raise InstallError(f"compiled consumer contract identity is invalid: {member}")
    return payload


def _source_skill_projection(member: str) -> dict[str, object]:
    api = _consumer_distribution_api()
    raw_plan = api.consumer_distribution_plan(
        SKILL_SOURCE / member,
        _compiled_contract(member),
    )
    if not isinstance(raw_plan, Mapping):
        raise InstallError(f"consumer projection result is malformed: {member}")
    plan = dict(raw_plan)
    files = plan.get("files")
    findings = plan.get("findings")
    if (
        plan.get("status") != "passed"
        or plan.get("skill_id") != member
        or plan.get("projection_id") != "projection:consumer-distribution"
        or plan.get("release_manifest_path") != "consumer-release.json"
        or not str(plan.get("release_id", ""))
        or not isinstance(files, list)
        or not files
        or not isinstance(findings, list)
        or bool(findings)
    ):
        raise InstallError(
            f"consumer projection is blocked: {member}: "
            f"{json.dumps(plan.get('findings', []), ensure_ascii=False)}"
        )
    projected_files: dict[str, str] = {}
    for row in files:
        if not isinstance(row, Mapping):
            raise InstallError(f"consumer projection file row is malformed: {member}")
        relative = str(row.get("path", ""))
        content_hash = str(row.get("content_hash", ""))
        if not relative or not content_hash or relative in projected_files:
            raise InstallError(f"consumer projection file identity is malformed: {member}")
        projected_files[relative] = content_hash
    return {
        "release_id": str(plan["release_id"]),
        "release_manifest_path": str(plan["release_manifest_path"]),
        "files": projected_files,
    }


def _audit_installed_skill(
    member: str, expected: dict[str, object]
) -> dict[str, object]:
    active = ACTIVE_SKILL_ROOT / member
    if not active.is_dir():
        raise InstallError(f"installed skill is missing: {member}")
    raw_result = _target_installation_api().verify_target_stage(
        ROOT,
        SKILL_SOURCE / member,
        active,
    )
    if not isinstance(raw_result, Mapping):
        raise InstallError(f"installed consumer verification result is malformed: {member}")
    result = dict(raw_result)
    if result.get("status") != "passed":
        raise InstallError(
            f"installed consumer projection is invalid: {member}: "
            f"{json.dumps(result.get('blockers', []), ensure_ascii=False)}"
        )
    canonical = result.get("canonical_projection", {})
    installed = result.get("stage_projection", {})
    if result.get("skill_id") != member:
        raise InstallError(f"installed consumer identity mismatch: {member}")
    if not str(result.get("stage_verification_hash", "")):
        raise InstallError(f"installed consumer verification identity is missing: {member}")
    if (
        not isinstance(canonical, dict)
        or not isinstance(installed, dict)
        or canonical.get("release_id") != expected.get("release_id")
        or installed.get("release_id") != expected.get("release_id")
    ):
        raise InstallError(f"installed consumer release is stale: {member}")
    if not result.get("comparison_current"):
        raise InstallError(f"installed consumer projection is not current: {member}")
    return result


def _verified_stage_result(
    member: str, raw_result: object
) -> dict[str, object]:
    if not isinstance(raw_result, Mapping):
        raise InstallError(f"consumer stage verification result is malformed: {member}")
    result = dict(raw_result)
    canonical = result.get("canonical_projection")
    staged = result.get("stage_projection")
    if (
        result.get("status") != "passed"
        or result.get("skill_id") != member
        or not result.get("comparison_current")
        or not str(result.get("stage_verification_hash", ""))
        or not isinstance(canonical, Mapping)
        or not isinstance(staged, Mapping)
        or not str(canonical.get("release_id", ""))
        or canonical.get("release_id") != staged.get("release_id")
    ):
        raise InstallError(
            f"consumer stage verification is blocked: {member}: "
            f"{json.dumps(result.get('blockers', []), ensure_ascii=False)}"
        )
    return result


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


def _distribution_file_inventory(
    distribution: object,
) -> tuple[Path, dict[Path, str]]:
    """Return the exact regular-file inventory owned by one installed distribution."""

    base = Path(distribution.locate_file(".")).resolve(strict=True)
    authority_root = base.parent.resolve(strict=True)
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
    _native_command(
        [
            sys.executable,
            "scripts/check_researchguard_suite.py",
            "--member",
            "all",
            "--json",
        ]
    )


def _prepare_skill_stages(stage_root: Path) -> dict[str, dict[str, object]]:
    api = _target_installation_api()
    stage_root.mkdir(parents=True, exist_ok=False)
    prepared: dict[str, dict[str, object]] = {}
    for member in MEMBERS:
        stage = stage_root / member
        raw_report = api.prepare_target_stage(ROOT, SKILL_SOURCE / member, stage)
        if not isinstance(raw_report, Mapping):
            raise InstallError(f"consumer stage preparation result is malformed: {member}")
        report = dict(raw_report)
        if report.get("status") != "passed":
            raise InstallError(
                f"consumer stage preparation is blocked: {member}: "
                f"{json.dumps(report.get('blockers', []), ensure_ascii=False)}"
            )
        if report.get("skill_id") != member:
            raise InstallError(f"consumer stage preparation identity mismatch: {member}")
        prepared[member] = {"stage": stage}

    for member, row in prepared.items():
        verification = _verified_stage_result(
            member,
            api.verify_target_stage(
                ROOT,
                SKILL_SOURCE / member,
                Path(row["stage"]),
            ),
        )
        row["verification"] = verification
    return prepared


def _rollback_activated_skills(
    activations: list[dict[str, object]],
    *,
    api: object | None = None,
) -> dict[str, object]:
    target_api = api if api is not None else _target_installation_api()
    reports: list[dict[str, object]] = []
    for activation in reversed(activations):
        member = str(activation.get("skill_id", ""))
        transaction_id = str(activation.get("transaction_id", ""))
        try:
            if not member or not TRANSACTION_ID_PATTERN.fullmatch(transaction_id):
                raise InstallError("activation pointer is unavailable for rollback")
            raw_report = target_api.rollback_target_install(
                ACTIVE_SKILL_ROOT.parent,
                member,
                transaction_id,
            )
            if not isinstance(raw_report, Mapping):
                raise InstallError("rollback result is malformed")
            report = dict(raw_report)
            if (
                report.get("status") == "passed"
                and (
                    report.get("skill_id") != member
                    or report.get("transaction_id") != transaction_id
                    or report.get("restored_status") != "manually_rolled_back"
                )
            ):
                report = {
                    "status": "blocked",
                    "skill_id": member,
                    "transaction_id": transaction_id,
                    "blockers": ["rollback terminal identity mismatch"],
                    "observed_result": report,
                }
        except Exception as exc:
            report = {
                "status": "blocked",
                "skill_id": member,
                "blockers": [f"rollback exception: {type(exc).__name__}: {exc}"],
            }
        reports.append(report)
    blockers = [
        {
            "skill_id": report.get("skill_id"),
            "blockers": report.get("blockers", []),
        }
        for report in reports
        if report.get("status") != "passed"
    ]
    return {
        "status": "passed" if not blockers else "cleanup_unconfirmed",
        "reports": reports,
        "blockers": blockers,
    }


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


def _activation_result_findings(
    member: str,
    result: Mapping[str, object],
    verification: Mapping[str, object],
) -> list[str]:
    findings: list[str] = []
    transaction_id = str(result.get("transaction_id", ""))
    receipt = result.get("receipt")
    head = result.get("head")
    if result.get("status") != "passed":
        findings.append("activation status is blocked")
    if result.get("skill_id") != member:
        findings.append("activation skill identity mismatch")
    if not TRANSACTION_ID_PATTERN.fullmatch(transaction_id):
        findings.append("activation transaction pointer is malformed")
    if not isinstance(receipt, Mapping):
        findings.append("activation receipt pointer is missing")
        receipt = {}
    if not isinstance(head, Mapping):
        findings.append("activation HEAD pointer is missing")
        head = {}
    receipt_hash = str(receipt.get("receipt_hash", ""))
    if (
        receipt.get("skill_id") != member
        or receipt.get("transaction_id") != transaction_id
        or receipt.get("status") != "committed"
        or not CANONICAL_HASH_PATTERN.fullmatch(receipt_hash)
    ):
        findings.append("activation receipt pointer identity mismatch")
    if (
        head.get("skill_id") != member
        or head.get("transaction_id") != transaction_id
        or head.get("receipt_hash") != receipt_hash
        or not isinstance(head.get("generation"), int)
        or int(head.get("generation", 0)) < 1
    ):
        findings.append("activation HEAD pointer identity mismatch")
    expected_projection = verification.get("canonical_projection")
    receipt_projection = receipt.get("canonical_projection")
    if (
        not isinstance(expected_projection, Mapping)
        or not isinstance(receipt_projection, Mapping)
        or receipt_projection.get("release_id")
        != expected_projection.get("release_id")
    ):
        findings.append("activation receipt projection identity mismatch")
    return findings


def _activate_prepared_skills(
    prepared: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    residuals = _retired_skill_residuals()
    if residuals:
        raise InstallError(
            "retired skill residuals require explicit lifecycle cleanup before "
            f"suite activation: {residuals}"
        )
    api = _target_installation_api()
    activations: list[dict[str, object]] = []
    for member in MEMBERS:
        row = prepared[member]
        try:
            raw_result = api.activate_target_stage(
                ROOT,
                SKILL_SOURCE / member,
                Path(row["stage"]),
                ACTIVE_SKILL_ROOT.parent,
                stage_verification=row["verification"],
            )
            if not isinstance(raw_result, Mapping):
                raise InstallError("activation result is malformed")
            result = dict(raw_result)
            activation_findings = _activation_result_findings(
                member,
                result,
                row["verification"],
            )
        except Exception as exc:
            result = {
                "status": "blocked",
                "skill_id": member,
                "blockers": [f"activation exception: {type(exc).__name__}: {exc}"],
            }
            activation_findings = ["activation API raised an exception"]
        if activation_findings:
            rollback_candidates = list(activations)
            transaction_id = str(result.get("transaction_id", ""))
            if (
                result.get("status") == "passed"
                and TRANSACTION_ID_PATTERN.fullmatch(transaction_id)
            ):
                rollback_candidates.append(
                    {"skill_id": member, "transaction_id": transaction_id}
                )
            elif result.get("status") == "passed":
                activation_findings.append(
                    "current activation cannot be rolled back from its returned pointer"
                )
            rollback = _rollback_activated_skills(rollback_candidates, api=api)
            if (
                result.get("status") == "passed"
                and not TRANSACTION_ID_PATTERN.fullmatch(transaction_id)
            ):
                rollback = {
                    **rollback,
                    "status": "cleanup_unconfirmed",
                    "blockers": [
                        *rollback.get("blockers", []),
                        {
                            "skill_id": member,
                            "blockers": [
                                "successful activation returned no usable rollback pointer"
                            ],
                        },
                    ],
                }
            detail = {
                "member": member,
                "activation": result,
                "activation_findings": activation_findings,
                "rollback": rollback,
            }
            if rollback["status"] != "passed":
                raise InstallError(
                    "consumer suite activation and rollback are blocked: "
                    f"{json.dumps(detail, ensure_ascii=False)}",
                    status="cleanup_unconfirmed",
                    cleanup_report={"consumers": rollback},
                )
            raise InstallError(
                "consumer suite activation is blocked and prior members were restored: "
                f"{json.dumps(detail, ensure_ascii=False)}",
                cleanup_report={"consumers": rollback},
            )
        activations.append(result)
    return activations


def _retired_skill_residuals() -> list[str]:
    return [
        skill_id
        for skill_id in RETIRED_SKILLS
        if (ACTIVE_SKILL_ROOT / skill_id).exists()
        or (ACTIVE_SKILL_ROOT / skill_id).is_symlink()
    ]


def _write_manifest(payload: dict[str, object]) -> None:
    _write_manifest_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


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


def _installation_manifest_findings(
    manifest: dict[str, object],
    source: dict[str, object],
) -> list[str]:
    findings: list[str] = []
    if manifest.get("schema_version") != "researchguard.install-manifest.v2":
        findings.append("installation manifest schema is invalid")
    if manifest.get("version") != VERSION:
        findings.append("installation manifest version is stale")
    if manifest.get("source_fingerprint") != source["source_fingerprint"]:
        findings.append("installation manifest is stale")
    if manifest.get("skill_ids") != list(MEMBERS):
        findings.append("installation manifest member inventory is stale")
    if manifest.get("retired_skill_ids") != list(RETIRED_SKILLS):
        findings.append("installation manifest retirement inventory is stale")
    if manifest.get("package_fingerprint") != _digest(source["package"]):
        findings.append("installation manifest package identity is stale")
    expected_release_ids = {
        member: source["skills"][member]["release_id"] for member in MEMBERS
    }
    if manifest.get("skill_release_ids") != expected_release_ids:
        findings.append("installation manifest skill projection identities are stale")
    pointers = manifest.get("activation_pointers")
    if not isinstance(pointers, dict) or set(pointers) != set(MEMBERS):
        findings.append("installation manifest activation pointer inventory is incomplete")
    else:
        for member in MEMBERS:
            row = pointers.get(member)
            if (
                not isinstance(row, dict)
                or not TRANSACTION_ID_PATTERN.fullmatch(
                    str(row.get("transaction_id", ""))
                )
                or not CANONICAL_HASH_PATTERN.fullmatch(
                    str(row.get("receipt_hash", ""))
                )
                or not isinstance(row.get("head_generation"), int)
                or int(row["head_generation"]) < 1
            ):
                findings.append(
                    f"installation manifest activation pointer is invalid: {member}"
                )
    return findings


def check_current() -> dict[str, object]:
    source = _source_state()
    findings: list[str] = []
    try:
        _validate_install_paths()
        install_paths_safe = True
    except InstallError as exc:
        install_paths_safe = False
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
    if not install_paths_safe:
        manifest: dict[str, object] = {}
    elif not MANIFEST_PATH.is_file():
        findings.append("installation manifest is missing")
        manifest = {}
    else:
        try:
            loaded_manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            findings.append(f"installation manifest is unreadable: {type(exc).__name__}")
            loaded_manifest = {}
        if not isinstance(loaded_manifest, dict):
            findings.append("installation manifest is invalid")
            manifest = {}
        else:
            manifest = loaded_manifest
            findings.extend(_installation_manifest_findings(manifest, source))
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
            "Pass proves the current package bytes, console declaration, five static "
            "consumer projections, retirement residual absence, and suite manifest "
            "shape. Activation pointers are recorded provenance only; this check "
            "does not independently revalidate SkillGuard HEAD, receipt, or journal "
            "state, nor Git, tag, or GitHub release identity."
        ),
    }


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
    with tempfile.TemporaryDirectory(prefix="researchguard-install-") as temporary:
        temporary_root = Path(temporary)
        prepared = _prepare_skill_stages(temporary_root / "skills")
        wheel_dir = temporary_root / "wheel"
        wheel_dir.mkdir()
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
                    str(wheels[0]),
                ],
                timeout=600,
            )
            activations = _activate_prepared_skills(prepared)
            source = _source_state()
            _write_manifest(
                {
                    "schema_version": "researchguard.install-manifest.v2",
                    "version": VERSION,
                    "skill_ids": list(MEMBERS),
                    "retired_skill_ids": list(RETIRED_SKILLS),
                    "source_fingerprint": source["source_fingerprint"],
                    "package_fingerprint": _digest(source["package"]),
                    "skill_release_ids": {
                        member: source["skills"][member]["release_id"]
                        for member in MEMBERS
                    },
                    "activation_pointers": {
                        str(row["skill_id"]): {
                            "transaction_id": row["transaction_id"],
                            "receipt_hash": row["receipt"]["receipt_hash"],
                            "head_generation": row["head"]["generation"],
                        }
                        for row in activations
                    },
                    "claim_boundary": (
                        "These pointers record values returned by five current SkillGuard "
                        "activations. This suite manifest does not independently revalidate "
                        "SkillGuard HEAD, receipt, or journal state. Static consumer "
                        "currentness, the Python package, Git, tag, and GitHub release are "
                        "separate identity domains."
                    ),
                }
            )
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
