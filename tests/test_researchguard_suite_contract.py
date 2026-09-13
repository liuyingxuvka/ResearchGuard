from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path

import pytest

from flowguard.model_regressions import (
    ModelRegressionManifest,
    build_model_instance_ref,
    resolve_entry_input_inventory,
)


ROOT = Path(__file__).resolve().parents[1]
CHILD_MODEL_IDS = (
    "authoritative_model_system",
    "compositional_verification_kernel",
    "hierarchical_model_mesh",
    "model_test_code_alignment",
    "logic_synthesis",
    "logic_selection_contract",
    "argument_support_closure",
    "discourse_structure",
    "trace_domain_export",
)


def _load_suite_runner():
    path = ROOT / ".flowguard/verification/owners/researchguard_suite/run_checks.py"
    spec = importlib.util.spec_from_file_location(
        "researchguard_suite_timeout_contract_runner",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _nested_owner_paths() -> tuple[str, ...]:
    return tuple(
        path
        for model_id in CHILD_MODEL_IDS
        for path in (
            f".flowguard/models/owners/{model_id}/model.py",
            f".flowguard/verification/owners/{model_id}/run_checks.py",
        )
    )


def test_native_timeout_defaults_to_420_and_accepts_finite_positive_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _load_suite_runner()
    monkeypatch.delenv("FLOWGUARD_RESEARCHGUARD_NATIVE_TIMEOUT_SECONDS", raising=False)
    assert runner._positive_timeout_from_env(
        "FLOWGUARD_RESEARCHGUARD_NATIVE_TIMEOUT_SECONDS",
        420.0,
    ) == 420.0

    monkeypatch.setenv("FLOWGUARD_RESEARCHGUARD_NATIVE_TIMEOUT_SECONDS", "123.5")
    assert runner._positive_timeout_from_env(
        "FLOWGUARD_RESEARCHGUARD_NATIVE_TIMEOUT_SECONDS",
        420.0,
    ) == 123.5


@pytest.mark.parametrize("raw", ["0", "-1", "nan", "inf", "not-a-number"])
def test_native_timeout_rejects_non_positive_or_non_finite_override(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    runner = _load_suite_runner()
    monkeypatch.setenv("FLOWGUARD_RESEARCHGUARD_NATIVE_TIMEOUT_SECONDS", raw)
    with pytest.raises(ValueError, match="finite positive number"):
        runner._positive_timeout_from_env(
            "FLOWGUARD_RESEARCHGUARD_NATIVE_TIMEOUT_SECONDS",
            420.0,
        )


def test_suite_manifest_covers_nested_children_and_child_change_stales_root(
    tmp_path: Path,
) -> None:
    manifest = ModelRegressionManifest.load(ROOT)
    entry = next(
        item for item in manifest.entries if item.model_id == "researchguard_suite"
    )
    nested_paths = _nested_owner_paths()
    assert entry.timeout_seconds == 1200.0
    assert set(nested_paths).issubset(set(entry.input_globs))

    root_paths = (
        entry.model_path,
        entry.runner[1],
        *nested_paths,
    )
    for relative in root_paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())

    synthetic_entry = replace(
        entry,
        input_globs=root_paths,
        intent_source_inputs=(),
    )
    baseline_inventory = resolve_entry_input_inventory(tmp_path, synthetic_entry)
    baseline_instance = build_model_instance_ref(
        tmp_path,
        logical_model_id=synthetic_entry.model_id,
        model_kind=synthetic_entry.model_kind,
        model_path=synthetic_entry.model_path,
        runner_path=synthetic_entry.runner[1],
        purpose_closure_fingerprint=synthetic_entry.purpose_closure.closure_fingerprint,
        input_paths=tuple(item["path"] for item in baseline_inventory),
    )

    changed_relative = ".flowguard/verification/owners/trace_domain_export/run_checks.py"
    changed_path = tmp_path / changed_relative
    changed_path.write_bytes(changed_path.read_bytes() + b"\n")
    changed_inventory = resolve_entry_input_inventory(tmp_path, synthetic_entry)
    changed_instance = build_model_instance_ref(
        tmp_path,
        logical_model_id=synthetic_entry.model_id,
        model_kind=synthetic_entry.model_kind,
        model_path=synthetic_entry.model_path,
        runner_path=synthetic_entry.runner[1],
        purpose_closure_fingerprint=synthetic_entry.purpose_closure.closure_fingerprint,
        input_paths=tuple(item["path"] for item in changed_inventory),
    )

    assert changed_relative in {item["path"] for item in baseline_inventory}
    assert baseline_instance.input_inventory_fingerprint != changed_instance.input_inventory_fingerprint
    assert baseline_instance.fingerprint != changed_instance.fingerprint
