from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import shutil
import sys

from flowguard.map.check import run_check
from flowguard.map.inventory import build_inventory
from flowguard.map.mapfile import component_files, fingerprint, ignore_patterns, load_map, model_registry
from flowguard.review import review_scenarios

ROOT = Path(__file__).resolve().parents[1]


def test_current_suite_model_executes_the_declared_scenarios() -> None:
    path = ROOT / ".flowguard/models/researchguard_suite_model.py"
    spec = importlib.util.spec_from_file_location("current_suite_model", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    report = review_scenarios(module.scenarios())
    assert report.ok, report.format_text()


def test_current_map_binds_real_models_code_and_tests() -> None:
    data = load_map(ROOT)
    registry = model_registry(ROOT, data)
    assert not registry.issues
    assert {entry.id for entry in registry.entries} == {
        "researchguard_suite", "researchguard.source.content_anchor_oracle.current"
    }
    inventory = build_inventory(ROOT, ignore_patterns(data))
    findings = run_check(ROOT, data, inventory, strict=True)
    assert not [f for f in findings if f.level == "error"], [f.line() for f in findings]


def test_bound_code_change_is_stale_and_missing_test_anchor_is_blocked(tmp_path: Path) -> None:
    data = copy.deepcopy(load_map(ROOT))
    component = next(c for c in data["components"] if c["id"] == "researchguard-suite")
    component["files"] = ["src/researchguard/routing.py"]
    component["entrypoints"] = []
    component["depends_on"] = []
    data.update(components=[component], flows=[])
    paths = ["src/researchguard/routing.py", ".flowguard/models/researchguard_suite_model.py",
             "tests/test_suite_routing.py", "tests/test_root_cli.py"]
    for relative in paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    inventory = build_inventory(tmp_path, ignore_patterns(data))
    component["fingerprint"] = fingerprint(tmp_path, component_files(component, inventory))
    assert not [f for f in run_check(tmp_path, data, inventory, strict=True) if f.level == "error"]
    code = tmp_path / paths[0]
    code.write_text(code.read_text() + "\n# changed implementation\n")
    changed = run_check(tmp_path, data, build_inventory(tmp_path, ignore_patterns(data)), strict=True)
    assert "stale" in {f.code for f in changed}
    test = tmp_path / "tests/test_suite_routing.py"
    test.write_text(test.read_text().replace("def test_selected_member_has_no_alternate_binding(", "def retired_test(", 1))
    broken = run_check(tmp_path, data, build_inventory(tmp_path, ignore_patterns(data)), strict=True)
    assert "model_test_broken" in {f.code for f in broken}
