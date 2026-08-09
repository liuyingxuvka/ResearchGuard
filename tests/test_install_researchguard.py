from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import install_researchguard


class _ConsumerDistributionAPI:
    def __init__(self) -> None:
        self.plan_calls: list[str] = []

    @staticmethod
    def _plan(member: str) -> dict[str, object]:
        return {
            "status": "passed",
            "skill_id": member,
            "projection_id": "projection:consumer-distribution",
            "release_id": f"release:{member}",
            "release_manifest_path": "consumer-release.json",
            "files": [
                {
                    "path": "SKILL.md",
                    "content_hash": f"sha256:{member}",
                }
            ],
            "findings": [],
        }

    def consumer_distribution_plan(
        self, _skill_root: Path, contract: dict[str, object]
    ) -> dict[str, object]:
        member = str(contract["skill_id"])
        self.plan_calls.append(member)
        return self._plan(member)

class _TargetInstallationAPI:
    def __init__(
        self,
        *,
        fail_prepare: str = "",
        fail_verify: str = "",
        fail_activate: str = "",
        fail_rollback: str = "",
    ) -> None:
        self.fail_prepare = fail_prepare
        self.fail_verify = fail_verify
        self.fail_activate = fail_activate
        self.fail_rollback = fail_rollback
        self.calls: list[tuple[str, str]] = []

    @staticmethod
    def _manifest(root: Path, member: str, release_id: str | None = None) -> None:
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(member, encoding="utf-8")
        (root / "consumer-release.json").write_text(
            json.dumps(
                {
                    "skill_id": member,
                    "release_id": release_id or f"release:{member}",
                }
            ),
            encoding="utf-8",
        )

    def verify_target_stage(
        self,
        _repository_root: Path,
        canonical_skill_root: Path,
        stage_skill_root: Path,
    ) -> dict[str, object]:
        member = canonical_skill_root.name
        self.calls.append(("verify", member))
        if member == self.fail_verify:
            return {
                "status": "blocked",
                "skill_id": member,
                "blockers": ["simulated_verify_failure"],
            }
        manifest_path = stage_skill_root / "consumer-release.json"
        if not manifest_path.is_file():
            return {
                "status": "blocked",
                "skill_id": member,
                "blockers": ["consumer_release_manifest_missing"],
            }
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = f"release:{member}"
        actual = str(manifest.get("release_id", ""))
        return {
            "status": "passed",
            "skill_id": str(manifest.get("skill_id", "")),
            "canonical_projection": {"release_id": expected},
            "stage_projection": {"release_id": actual},
            "comparison_current": actual == expected,
            "blockers": [],
            "stage_verification_hash": f"verify:{member}:{actual}",
        }

    def prepare_target_stage(
        self,
        repository_root: Path,
        canonical_skill_root: Path,
        stage_skill_root: Path,
    ) -> dict[str, object]:
        member = canonical_skill_root.name
        self.calls.append(("prepare", member))
        if member == self.fail_prepare:
            return {
                "status": "blocked",
                "skill_id": member,
                "blockers": ["simulated_prepare_failure"],
            }
        self._manifest(stage_skill_root, member)
        verification = self.verify_target_stage(
            repository_root,
            canonical_skill_root,
            stage_skill_root,
        )
        self.calls.pop()
        return {
            "status": "passed",
            "skill_id": member,
            "verification": verification,
            "blockers": [],
        }

    def activate_target_stage(
        self,
        _repository_root: Path,
        canonical_skill_root: Path,
        _stage_skill_root: Path,
        _codex_home: Path,
        *,
        stage_verification: dict[str, object],
    ) -> dict[str, object]:
        member = canonical_skill_root.name
        self.calls.append(("activate", member))
        assert stage_verification["status"] == "passed"
        if member == self.fail_activate:
            return {
                "status": "blocked",
                "skill_id": member,
                "blockers": ["simulated_activation_failure"],
            }
        transaction_id = f"target-install-{hashlib.md5(member.encode()).hexdigest()}"
        receipt_hash = hashlib.sha256(member.encode()).hexdigest().upper()
        return {
            "status": "passed",
            "skill_id": member,
            "transaction_id": transaction_id,
            "receipt": {
                "status": "committed",
                "skill_id": member,
                "transaction_id": transaction_id,
                "receipt_hash": receipt_hash,
                "canonical_projection": {"release_id": f"release:{member}"},
            },
            "head": {
                "skill_id": member,
                "transaction_id": transaction_id,
                "receipt_hash": receipt_hash,
                "generation": 1,
            },
            "blockers": [],
        }

    def rollback_target_install(
        self,
        _codex_home: Path,
        member: str,
        transaction_id: str,
    ) -> dict[str, object]:
        self.calls.append(("rollback", member))
        if member == self.fail_rollback:
            return {
                "status": "blocked",
                "skill_id": member,
                "blockers": ["simulated_rollback_failure"],
            }
        return {
            "status": "passed",
            "skill_id": member,
            "transaction_id": transaction_id,
            "restored_status": "manually_rolled_back",
            "blockers": [],
        }


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


def _use_fake_consumer_authority(
    monkeypatch: pytest.MonkeyPatch,
    api: _ConsumerDistributionAPI,
) -> None:
    monkeypatch.setattr(
        install_researchguard,
        "_consumer_distribution_api",
        lambda: api,
    )
    monkeypatch.setattr(
        install_researchguard,
        "_compiled_contract",
        lambda member: {"skill_id": member},
    )


def _use_fake_target_authority(
    monkeypatch: pytest.MonkeyPatch,
    api: _TargetInstallationAPI,
) -> None:
    monkeypatch.setattr(
        install_researchguard,
        "_target_installation_api",
        lambda: api,
    )


def test_source_projection_uses_the_skillguard_consumer_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _ConsumerDistributionAPI()
    _use_fake_consumer_authority(monkeypatch, api)

    projection = install_researchguard._source_skill_projection("logicguard")

    assert projection == {
        "release_id": "release:logicguard",
        "release_manifest_path": "consumer-release.json",
        "files": {"SKILL.md": "sha256:logicguard"},
    }
    assert api.plan_calls == ["logicguard"]
    assert not any(path.startswith(".skillguard/") for path in projection["files"])


def test_consumer_authority_blocks_an_import_from_a_different_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts_root = tmp_path / "current" / "scripts"
    module_path = scripts_root / "skillguard_v2" / "consumer_distribution.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("# current authority\n", encoding="utf-8")
    wrong_module = tmp_path / "stale" / "consumer_distribution.py"
    wrong_module.parent.mkdir()
    wrong_module.write_text("# stale authority\n", encoding="utf-8")
    monkeypatch.setattr(install_researchguard, "SKILLGUARD_SCRIPTS_ROOT", scripts_root)
    monkeypatch.setattr(install_researchguard.sys, "path", list(install_researchguard.sys.path))
    monkeypatch.setattr(
        install_researchguard.importlib,
        "import_module",
        lambda _name: SimpleNamespace(__file__=str(wrong_module)),
    )

    with pytest.raises(
        install_researchguard.InstallError,
        match="unexpected installation",
    ):
        install_researchguard._consumer_distribution_api()


def test_consumer_authority_blocks_foreign_transitive_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripts_root = tmp_path / "current" / "scripts"
    package_root = scripts_root / "skillguard_v2"
    module_path = package_root / "consumer_distribution.py"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("# current package\n", encoding="utf-8")
    module_path.write_text("# current authority\n", encoding="utf-8")
    foreign = tmp_path / "foreign" / "contract_compiler.py"
    foreign.parent.mkdir()
    foreign.write_text("# foreign dependency\n", encoding="utf-8")
    for name in tuple(install_researchguard.sys.modules):
        if name == "skillguard_v2" or name.startswith("skillguard_v2."):
            monkeypatch.delitem(install_researchguard.sys.modules, name, raising=False)
    monkeypatch.setitem(
        install_researchguard.sys.modules,
        "skillguard_v2.contract_compiler",
        SimpleNamespace(__file__=str(foreign)),
    )
    monkeypatch.setattr(install_researchguard, "SKILLGUARD_SCRIPTS_ROOT", scripts_root)
    monkeypatch.setattr(
        install_researchguard.importlib,
        "import_module",
        lambda _name: SimpleNamespace(__file__=str(module_path)),
    )

    with pytest.raises(
        install_researchguard.InstallError,
        match="foreign dependency modules",
    ):
        install_researchguard._consumer_distribution_api()


def test_all_members_are_prepared_and_verified_before_any_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active_root = tmp_path / "skills"
    active_root.mkdir()
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", active_root)
    monkeypatch.setattr(install_researchguard, "MEMBERS", ("alpha", "beta"))
    monkeypatch.setattr(install_researchguard, "RETIRED_SKILLS", ())
    api = _TargetInstallationAPI()
    _use_fake_target_authority(monkeypatch, api)

    prepared = install_researchguard._prepare_skill_stages(tmp_path / "stages")
    activations = install_researchguard._activate_prepared_skills(prepared)

    assert [row["skill_id"] for row in activations] == ["alpha", "beta"]
    assert api.calls == [
        ("prepare", "alpha"),
        ("prepare", "beta"),
        ("verify", "alpha"),
        ("verify", "beta"),
        ("activate", "alpha"),
        ("activate", "beta"),
    ]


def test_prepare_failure_starts_no_activation_and_leaves_active_skills_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active_root = tmp_path / "skills"
    active_root.mkdir()
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", active_root)
    monkeypatch.setattr(install_researchguard, "MEMBERS", ("alpha", "beta"))
    monkeypatch.setattr(install_researchguard, "RETIRED_SKILLS", ())
    api = _TargetInstallationAPI(fail_prepare="beta")
    _use_fake_target_authority(monkeypatch, api)
    for name in ("alpha", "beta"):
        prior = active_root / name
        prior.mkdir()
        (prior / "prior.txt").write_text(name, encoding="utf-8")

    with pytest.raises(
        install_researchguard.InstallError,
        match="stage preparation is blocked: beta",
    ):
        install_researchguard._prepare_skill_stages(tmp_path / "stages")

    for name in ("alpha", "beta"):
        assert (active_root / name / "prior.txt").read_text(encoding="utf-8") == name
    assert not any(action == "activate" for action, _member in api.calls)


def test_verify_failure_starts_no_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active_root = tmp_path / "skills"
    active_root.mkdir()
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", active_root)
    monkeypatch.setattr(install_researchguard, "MEMBERS", ("alpha", "beta"))
    monkeypatch.setattr(install_researchguard, "RETIRED_SKILLS", ())
    api = _TargetInstallationAPI(fail_verify="beta")
    _use_fake_target_authority(monkeypatch, api)

    with pytest.raises(
        install_researchguard.InstallError,
        match="stage verification is blocked: beta",
    ):
        install_researchguard._prepare_skill_stages(tmp_path / "stages")

    assert not any(action == "activate" for action, _member in api.calls)


def test_activation_failure_rolls_back_prior_members_in_reverse_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active_root = tmp_path / "skills"
    active_root.mkdir()
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", active_root)
    monkeypatch.setattr(
        install_researchguard,
        "MEMBERS",
        ("alpha", "beta", "gamma"),
    )
    monkeypatch.setattr(install_researchguard, "RETIRED_SKILLS", ())
    api = _TargetInstallationAPI(fail_activate="gamma")
    _use_fake_target_authority(monkeypatch, api)
    prepared = install_researchguard._prepare_skill_stages(tmp_path / "stages")

    with pytest.raises(
        install_researchguard.InstallError,
        match="prior members were restored",
    ):
        install_researchguard._activate_prepared_skills(prepared)

    assert api.calls[-5:] == [
        ("activate", "alpha"),
        ("activate", "beta"),
        ("activate", "gamma"),
        ("rollback", "beta"),
        ("rollback", "alpha"),
    ]


def test_activation_reports_a_visible_rollback_residual(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active_root = tmp_path / "skills"
    active_root.mkdir()
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", active_root)
    monkeypatch.setattr(install_researchguard, "MEMBERS", ("alpha", "beta"))
    monkeypatch.setattr(install_researchguard, "RETIRED_SKILLS", ())
    api = _TargetInstallationAPI(
        fail_activate="beta",
        fail_rollback="alpha",
    )
    _use_fake_target_authority(monkeypatch, api)
    prepared = install_researchguard._prepare_skill_stages(tmp_path / "stages")

    with pytest.raises(
        install_researchguard.InstallError,
        match="activation and rollback are blocked",
    ) as captured:
        install_researchguard._activate_prepared_skills(prepared)

    assert captured.value.status == "cleanup_unconfirmed"

    assert api.calls[-3:] == [
        ("activate", "alpha"),
        ("activate", "beta"),
        ("rollback", "alpha"),
    ]


def test_activation_exception_rolls_back_every_prior_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active_root = tmp_path / "skills"
    active_root.mkdir()
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", active_root)
    monkeypatch.setattr(
        install_researchguard, "MEMBERS", ("alpha", "beta", "gamma")
    )
    monkeypatch.setattr(install_researchguard, "RETIRED_SKILLS", ())
    api = _TargetInstallationAPI()
    original_activate = api.activate_target_stage

    def raising_activate(*args, **kwargs):
        member = args[1].name
        if member == "gamma":
            api.calls.append(("activate", member))
            raise RuntimeError("simulated activation exception")
        return original_activate(*args, **kwargs)

    api.activate_target_stage = raising_activate  # type: ignore[method-assign]
    _use_fake_target_authority(monkeypatch, api)
    prepared = install_researchguard._prepare_skill_stages(tmp_path / "stages")

    with pytest.raises(install_researchguard.InstallError, match="prior members were restored"):
        install_researchguard._activate_prepared_skills(prepared)

    assert api.calls[-5:] == [
        ("activate", "alpha"),
        ("activate", "beta"),
        ("activate", "gamma"),
        ("rollback", "beta"),
        ("rollback", "alpha"),
    ]


def test_rollback_exception_does_not_stop_remaining_reverse_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active_root = tmp_path / "skills"
    active_root.mkdir()
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", active_root)
    monkeypatch.setattr(
        install_researchguard, "MEMBERS", ("alpha", "beta", "gamma")
    )
    monkeypatch.setattr(install_researchguard, "RETIRED_SKILLS", ())
    api = _TargetInstallationAPI(fail_activate="gamma")
    original_rollback = api.rollback_target_install

    def raising_rollback(_home, member, transaction_id):
        if member == "beta":
            api.calls.append(("rollback", member))
            raise RuntimeError("simulated rollback exception")
        return original_rollback(_home, member, transaction_id)

    api.rollback_target_install = raising_rollback  # type: ignore[method-assign]
    _use_fake_target_authority(monkeypatch, api)
    prepared = install_researchguard._prepare_skill_stages(tmp_path / "stages")

    with pytest.raises(
        install_researchguard.InstallError,
        match="activation and rollback are blocked",
    ):
        install_researchguard._activate_prepared_skills(prepared)

    assert api.calls[-5:] == [
        ("activate", "alpha"),
        ("activate", "beta"),
        ("activate", "gamma"),
        ("rollback", "beta"),
        ("rollback", "alpha"),
    ]


@pytest.mark.parametrize(
    "drift",
    ["skill_id", "transaction_id", "restored_status"],
)
def test_rollback_pass_requires_exact_terminal_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    active_root = tmp_path / "skills"
    active_root.mkdir()
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", active_root)
    monkeypatch.setattr(install_researchguard, "MEMBERS", ("alpha", "beta"))
    monkeypatch.setattr(install_researchguard, "RETIRED_SKILLS", ())
    api = _TargetInstallationAPI(fail_activate="beta")
    original_rollback = api.rollback_target_install

    def drifting_rollback(*args, **kwargs):
        result = original_rollback(*args, **kwargs)
        result[drift] = "foreign-value"
        return result

    api.rollback_target_install = drifting_rollback  # type: ignore[method-assign]
    _use_fake_target_authority(monkeypatch, api)
    prepared = install_researchguard._prepare_skill_stages(tmp_path / "stages")

    with pytest.raises(
        install_researchguard.InstallError,
        match="activation and rollback are blocked",
    ):
        install_researchguard._activate_prepared_skills(prepared)


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


def test_malformed_passed_activation_is_rolled_back_with_prior_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active_root = tmp_path / "skills"
    active_root.mkdir()
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", active_root)
    monkeypatch.setattr(install_researchguard, "MEMBERS", ("alpha", "beta"))
    monkeypatch.setattr(install_researchguard, "RETIRED_SKILLS", ())
    api = _TargetInstallationAPI()
    original_activate = api.activate_target_stage

    def identity_drift_activate(*args, **kwargs):
        result = original_activate(*args, **kwargs)
        if args[1].name == "beta":
            result["skill_id"] = "foreign"
        return result

    api.activate_target_stage = identity_drift_activate  # type: ignore[method-assign]
    _use_fake_target_authority(monkeypatch, api)
    prepared = install_researchguard._prepare_skill_stages(tmp_path / "stages")

    with pytest.raises(install_researchguard.InstallError):
        install_researchguard._activate_prepared_skills(prepared)

    assert api.calls[-4:] == [
        ("activate", "alpha"),
        ("activate", "beta"),
        ("rollback", "beta"),
        ("rollback", "alpha"),
    ]


def test_retired_residual_blocks_before_any_member_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active_root = tmp_path / "skills"
    (active_root / "retired").mkdir(parents=True)
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", active_root)
    monkeypatch.setattr(install_researchguard, "MEMBERS", ("alpha",))
    monkeypatch.setattr(install_researchguard, "RETIRED_SKILLS", ("retired",))
    api = _TargetInstallationAPI()
    _use_fake_target_authority(monkeypatch, api)
    prepared = install_researchguard._prepare_skill_stages(tmp_path / "stages")

    with pytest.raises(
        install_researchguard.InstallError,
        match="retired skill residuals require explicit lifecycle cleanup",
    ):
        install_researchguard._activate_prepared_skills(prepared)

    assert not any(action == "activate" for action, _member in api.calls)


def test_installed_consumer_audit_blocks_a_missing_release_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active_root = tmp_path / "skills"
    (active_root / "logicguard").mkdir(parents=True)
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", active_root)
    api = _TargetInstallationAPI()
    _use_fake_target_authority(monkeypatch, api)

    with pytest.raises(
        install_researchguard.InstallError,
        match="installed consumer projection is invalid: logicguard",
    ):
        install_researchguard._audit_installed_skill(
            "logicguard",
            {"release_id": "release:logicguard"},
        )
    assert api.calls == [("verify", "logicguard")]


def test_installed_consumer_audit_blocks_a_stale_release_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active_root = tmp_path / "skills"
    installed = active_root / "logicguard"
    installed.mkdir(parents=True)
    (installed / "consumer-release.json").write_text(
        json.dumps(
            {
                "skill_id": "logicguard",
                "release_id": "release:old",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(install_researchguard, "ACTIVE_SKILL_ROOT", active_root)
    api = _TargetInstallationAPI()
    _use_fake_target_authority(monkeypatch, api)

    with pytest.raises(
        install_researchguard.InstallError,
        match="installed consumer release is stale: logicguard",
    ):
        install_researchguard._audit_installed_skill(
            "logicguard",
            {"release_id": "release:logicguard"},
        )
    assert api.calls == [("verify", "logicguard")]


def test_install_manifest_requires_one_activation_pointer_per_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(install_researchguard, "MEMBERS", ("alpha", "beta"))
    monkeypatch.setattr(install_researchguard, "RETIRED_SKILLS", ())
    source = {
        "source_fingerprint": "source:current",
        "package": {"__init__.py": "package-hash"},
        "skills": {
            "alpha": {"release_id": "release:alpha"},
            "beta": {"release_id": "release:beta"},
        },
    }
    manifest = {
        "schema_version": "researchguard.install-manifest.v2",
        "version": install_researchguard.VERSION,
        "skill_ids": ["alpha", "beta"],
        "retired_skill_ids": [],
        "source_fingerprint": source["source_fingerprint"],
        "package_fingerprint": install_researchguard._digest(source["package"]),
        "skill_release_ids": {
            member: source["skills"][member]["release_id"]
            for member in ("alpha", "beta")
        },
        "activation_pointers": {
            "alpha": {
                "transaction_id": "target-install-" + "a" * 32,
                "receipt_hash": "A" * 64,
                "head_generation": 1,
            }
        },
    }

    assert install_researchguard._installation_manifest_findings(
        manifest,
        source,
    ) == ["installation manifest activation pointer inventory is incomplete"]

    manifest["activation_pointers"]["beta"] = {
        "transaction_id": "target-install-beta",
        "receipt_hash": "receipt:beta",
        "head_generation": 1,
    }
    assert install_researchguard._installation_manifest_findings(manifest, source) == [
        "installation manifest activation pointer is invalid: beta"
    ]
    manifest["activation_pointers"]["beta"] = {
        "transaction_id": "target-install-" + "b" * 32,
        "receipt_hash": "B" * 64,
        "head_generation": 1,
    }
    assert install_researchguard._installation_manifest_findings(manifest, source) == []


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
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "researchguard.install-manifest.v2",
                "version": install_researchguard.VERSION,
                "skill_ids": [],
                "retired_skill_ids": [],
                "source_fingerprint": source["source_fingerprint"],
                "package_fingerprint": install_researchguard._digest(source["package"]),
                "skill_release_ids": {},
                "activation_pointers": {},
            }
        ),
        encoding="utf-8",
    )
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


def test_skillguard_authority_is_not_redefined_by_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale = tmp_path / "stale-skillguard" / "scripts"
    monkeypatch.setenv("SKILLGUARD_SCRIPTS_ROOT", str(stale))

    assert install_researchguard.SKILLGUARD_SCRIPTS_ROOT != stale
    source = Path(install_researchguard.__file__).read_text(encoding="utf-8")
    assert 'os.environ.get("SKILLGUARD_SCRIPTS_ROOT"' not in source


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


def test_suite_rollback_attempts_consumers_package_and_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def consumers(_activations):
        calls.append("consumers")
        return {"status": "passed", "reports": [], "blockers": []}

    def package(_snapshot):
        calls.append("package")
        return {"status": "passed", "findings": []}

    def manifest(_snapshot):
        calls.append("manifest")
        return {"status": "passed", "findings": []}

    monkeypatch.setattr(install_researchguard, "_rollback_activated_skills", consumers)
    monkeypatch.setattr(install_researchguard, "_restore_package_state", package)
    monkeypatch.setattr(install_researchguard, "_restore_manifest_state", manifest)

    result = install_researchguard._restore_suite_state(
        activations=[{"skill_id": "researchguard"}],
        package_snapshot={"status": "present"},
        manifest_snapshot={"status": "present"},
    )

    assert result["status"] == "passed"
    assert result["cleanup_confirmed"] is True
    assert calls == ["consumers", "package", "manifest"]


def test_suite_rollback_is_cleanup_unconfirmed_but_attempts_every_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def consumers(_activations):
        calls.append("consumers")
        return {
            "status": "cleanup_unconfirmed",
            "reports": [],
            "blockers": ["simulated"],
        }

    def package(_snapshot):
        calls.append("package")
        raise RuntimeError("simulated package restore failure")

    def manifest(_snapshot):
        calls.append("manifest")
        return {"status": "passed", "findings": []}

    monkeypatch.setattr(install_researchguard, "_rollback_activated_skills", consumers)
    monkeypatch.setattr(install_researchguard, "_restore_package_state", package)
    monkeypatch.setattr(install_researchguard, "_restore_manifest_state", manifest)

    result = install_researchguard._restore_suite_state(
        activations=[{"skill_id": "researchguard"}],
        package_snapshot={"status": "present"},
        manifest_snapshot={"status": "present"},
    )

    assert result["status"] == "cleanup_unconfirmed"
    assert result["cleanup_confirmed"] is False
    assert calls == ["consumers", "package", "manifest"]
    assert [row["domain"] for row in result["reports"]] == [
        "consumers",
        "python-package",
        "suite-manifest",
    ]


@pytest.mark.parametrize("failing_domain", ["consumers", "python-package"])
def test_consumer_or_package_restore_failure_alone_is_cleanup_unconfirmed(
    monkeypatch: pytest.MonkeyPatch,
    failing_domain: str,
) -> None:
    monkeypatch.setattr(
        install_researchguard,
        "_rollback_activated_skills",
        lambda _activations: {
            "status": (
                "cleanup_unconfirmed" if failing_domain == "consumers" else "passed"
            ),
            "reports": [],
            "blockers": (
                ["simulated consumer rollback failure"]
                if failing_domain == "consumers"
                else []
            ),
        },
    )
    monkeypatch.setattr(
        install_researchguard,
        "_restore_package_state",
        lambda _snapshot: {
            "status": (
                "cleanup_unconfirmed"
                if failing_domain == "python-package"
                else "passed"
            ),
            "findings": (
                ["simulated package restoration failure"]
                if failing_domain == "python-package"
                else []
            ),
        },
    )
    monkeypatch.setattr(
        install_researchguard,
        "_restore_manifest_state",
        lambda _snapshot: {"status": "passed", "findings": []},
    )

    result = install_researchguard._restore_suite_state(
        activations=[{"skill_id": "researchguard"}],
        package_snapshot={"status": "present"},
        manifest_snapshot={"status": "present"},
    )

    assert result["status"] == "cleanup_unconfirmed"
    failed = [row for row in result["reports"] if row["status"] != "passed"]
    assert [row["domain"] for row in failed] == [failing_domain]


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


@pytest.mark.parametrize(
    ("cleanup_status", "expected_status"),
    [("passed", "blocked"), ("cleanup_unconfirmed", "cleanup_unconfirmed")],
)
def test_late_install_failure_routes_all_state_through_suite_restoration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cleanup_status: str,
    expected_status: str,
) -> None:
    monkeypatch.setattr(install_researchguard, "MEMBERS", ("alpha",))
    monkeypatch.setattr(install_researchguard, "RETIRED_SKILLS", ())
    monkeypatch.setattr(install_researchguard, "_validate_install_paths", lambda: {})
    monkeypatch.setattr(install_researchguard, "_retired_skill_residuals", lambda: [])
    monkeypatch.setattr(install_researchguard, "_validate_source", lambda: None)
    monkeypatch.setattr(
        install_researchguard.importlib.metadata,
        "version",
        lambda _name: install_researchguard.VERSION,
    )
    monkeypatch.setattr(
        install_researchguard,
        "_prepare_skill_stages",
        lambda _root: {"alpha": {"stage": tmp_path / "stage"}},
    )
    monkeypatch.setattr(
        install_researchguard,
        "_capture_package_state",
        lambda _root: {"status": "present", "version": "prior"},
    )
    monkeypatch.setattr(
        install_researchguard,
        "_capture_manifest_state",
        lambda: {"status": "present", "body": b"prior"},
    )
    activation = {
        "skill_id": "alpha",
        "transaction_id": "target-install-" + "a" * 32,
        "receipt": {"receipt_hash": "A" * 64},
        "head": {"generation": 1},
    }
    monkeypatch.setattr(
        install_researchguard,
        "_activate_prepared_skills",
        lambda _prepared: [activation],
    )
    source = {
        "source_fingerprint": "source",
        "package": {"__init__.py": "hash"},
        "skills": {"alpha": {"release_id": "release:alpha"}},
    }
    monkeypatch.setattr(install_researchguard, "_source_state", lambda: source)
    monkeypatch.setattr(install_researchguard, "_write_manifest", lambda _value: None)
    monkeypatch.setattr(
        install_researchguard,
        "check_current",
        lambda: {"status": "blocked", "findings": ["late failure"]},
    )
    restore_calls: list[dict[str, object]] = []

    def restore(**kwargs):
        restore_calls.append(kwargs)
        return {
            "status": cleanup_status,
            "cleanup_confirmed": cleanup_status == "passed",
            "reports": [],
        }

    monkeypatch.setattr(install_researchguard, "_restore_suite_state", restore)

    def native_command(args, *, timeout=300):
        if "wheel" in args:
            wheel_root = Path(args[args.index("--wheel-dir") + 1])
            wheel_root.joinpath(
                f"researchguard-{install_researchguard.VERSION}-py3-none-any.whl"
            ).write_bytes(b"wheel")

    monkeypatch.setattr(install_researchguard, "_native_command", native_command)

    with pytest.raises(install_researchguard.InstallError) as captured:
        install_researchguard._install_locked({"kind": "test-lock"})

    assert captured.value.status == expected_status
    assert len(restore_calls) == 1
    assert restore_calls[0]["activations"] == [activation]
    assert restore_calls[0]["package_snapshot"]["version"] == "prior"
    assert restore_calls[0]["manifest_snapshot"]["body"] == b"prior"
    assert captured.value.cleanup_report["original_failure"] == {
        "type": "InstallError",
        "status": "blocked",
        "message": '{"status": "blocked", "findings": ["late failure"]}',
    }
