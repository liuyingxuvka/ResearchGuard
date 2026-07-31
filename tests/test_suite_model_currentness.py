from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tomllib

from researchguard import __version__


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / ".flowguard" / "researchguard_suite_model.py"
JSON_MODEL_PATH = ROOT / ".flowguard" / "researchguard_suite_model.json"


def _load_model():
    spec = importlib.util.spec_from_file_location(
        "researchguard_suite_currentness_test_model",
        MODEL_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_all_suite_version_authorities_are_current() -> None:
    package = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    topology = json.loads(JSON_MODEL_PATH.read_text(encoding="utf-8"))
    model = _load_model()

    assert package["project"]["version"] == "0.3.0"
    assert __version__ == "0.3.0"
    assert model.CURRENT_RESEARCHGUARD_VERSION == "0.3.0"
    assert topology["model_id"] == "researchguard.suite.v0.3.0"
    assert (
        "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git"
        "@b6f30533d67b62bcb6a0838937e5dcc5d965e58a"
        in package["project"]["optional-dependencies"]["test"]
    )


def test_suite_model_runner_and_currentness_test_are_freshness_inputs() -> None:
    builder = (
        ROOT / "scripts" / "build_skillguard_contracts.py"
    ).read_text(encoding="utf-8")
    for relative_path in (
        ".flowguard/researchguard_suite_model.py",
        ".flowguard/researchguard_suite_model.json",
        ".flowguard/run_researchguard_suite_model.py",
        "tests/test_suite_model_currentness.py",
    ):
        assert relative_path in builder
