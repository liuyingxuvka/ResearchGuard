from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tomllib

from researchguard import __version__


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / ".flowguard" / "models" / "researchguard_suite_model.py"
JSON_MODEL_PATH = ROOT / ".flowguard" / "models" / "researchguard_suite" / "model-definition.json"


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

    assert package["project"]["version"] == "0.5.1"
    assert __version__ == "0.5.1"
    assert model.CURRENT_RESEARCHGUARD_VERSION == "0.5.1"
    assert topology["model_id"] == "researchguard.suite.v0.5.1"
    assert topology["software_dna"]["model_path"] == "models/software_dna/researchguard.json"
    assert topology["software_dna"]["root_model_id"] == "researchguard-suite"
    assert topology["software_dna"]["member_model_ids"] == [
        "logicguard",
        "sourceguard",
        "traceguard",
        "experimentguard",
    ]
    assert topology["software_dna"]["readiness_layer_count"] == 7
    test_dependencies = package["project"]["optional-dependencies"]["test"]
    assert "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git@3725d324fa792e0b03bf1a5472f080e55cbf3ec9" in test_dependencies


def test_suite_model_runner_and_currentness_test_are_freshness_inputs() -> None:
    builder = (
        ROOT / "scripts" / "build_skillguard_contracts.py"
    ).read_text(encoding="utf-8")
    for relative_path in (
        ".flowguard/models/researchguard_suite_model.py",
        ".flowguard/models/researchguard_suite/model-definition.json",
        ".flowguard/verification/run_researchguard_suite_model.py",
        "tests/test_suite_model_currentness.py",
        "models/software_dna/researchguard.json",
        "src/researchguard/software_dna.py",
    ):
        assert relative_path in builder
