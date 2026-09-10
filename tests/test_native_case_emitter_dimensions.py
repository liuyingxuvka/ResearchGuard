from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from flowguard.native_case_protocol import CASE_DIMENSIONS


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
    spec = importlib.util.spec_from_file_location("researchguard_suite_runner_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _expected_kind(index: int) -> str:
    if index == 0:
        return "good"
    if index == 1:
        return "boundary"
    return "bad"


@pytest.mark.parametrize(
    "model_id",
    [
        "authoritative_model_system",
        "compositional_verification_kernel",
        "hierarchical_model_mesh",
        "model_test_code_alignment",
        "logic_synthesis",
        "logic_selection_contract",
        "argument_support_closure",
        "discourse_structure",
        "trace_domain_export",
    ],
)
def test_child_native_emitter_uses_declared_case_kind_dimensions(
    model_id: str, tmp_path: Path
) -> None:
    """Every child result row must use the dimensions of its case kind."""

    output = tmp_path / model_id
    environment = os.environ.copy()
    environment["FLOWGUARD_OUTPUT_DIR"] = str(output)
    runner = ROOT / f".flowguard/verification/owners/{model_id}/run_checks.py"
    completed = subprocess.run(
        [sys.executable, "-B", str(runner)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    envelope = json.loads((output / "native-case-results.json").read_text(encoding="utf-8"))
    rows = envelope["results"]
    assert len(rows) >= 3
    for index, row in enumerate(rows):
        expected = set(CASE_DIMENSIONS[_expected_kind(index)])
        assert set(row["executed_dimensions"]) == expected
        assert {
            oracle["dimension"] for oracle in row["oracle_results"]
        } == expected


def test_parent_native_emitter_uses_declared_case_kind_dimensions() -> None:
    runner = _load_suite_runner()
    model = runner.model
    assert set(runner._case_dimensions(model.KNOWN_GOOD_CASE_ID)) == set(
        CASE_DIMENSIONS["good"]
    )
    assert set(runner._case_dimensions(f"boundary:{model.MODEL_ID}")) == set(
        CASE_DIMENSIONS["boundary"]
    )
    for case_id in model.KNOWN_BAD_CASE_IDS:
        assert set(runner._case_dimensions(case_id)) == set(CASE_DIMENSIONS["bad"])


def test_parent_child_output_paths_remain_compact_for_long_simulator_roots() -> None:
    runner = _load_suite_runner()
    long_root = Path("C:/") / ("content-addressed-run-" + "x" * 180)
    paths = [
        runner._child_output_dir(long_root, model_id)
        for model_id in CHILD_MODEL_IDS
    ]
    assert len({str(path) for path in paths}) == len(CHILD_MODEL_IDS)
    assert all(path.parts[-2] == "c" for path in paths)
    assert all("/" not in path.parts[-1] for path in paths)
    assert all(len(path.parts[-1]) <= 4 for path in paths)
