from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_prompt_bundles.py"
SPEC = importlib.util.spec_from_file_location("researchguard_prompt_bundles", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def manifest() -> dict:
    return json.loads((ROOT / "researchguard" / "prompt_bundle_manifest.json").read_text(encoding="utf-8"))


def test_current_prompt_bundles_and_index_pass() -> None:
    result = MODULE.check_prompt_bundles()
    assert result["status"] == "pass", result["failures"]
    assert {row["skill_id"] for row in result["bundles"]} == {
        "researchguard", "logicguard", "sourceguard", "traceguard", "experimentguard"
    }
    assert all(row["headroom_bytes"] > 0 for row in result["bundles"])


def test_entry_budget_without_headroom_fails() -> None:
    payload = manifest()
    row = next(row for row in payload["bundles"] if row["skill_id"] == "logicguard")
    row["max_entry_bytes"] = 1
    result = MODULE.check_prompt_bundles(payload)
    assert {row["code"] for row in result["failures"]} >= {
        "entry-budget-exceeded", "entry-headroom-insufficient"
    }


def test_missing_or_untriggered_reference_edge_fails() -> None:
    payload = manifest()
    bad = deepcopy(payload["reference_edges"][0])
    bad["trigger_id"] = "trigger:not-declared"
    payload["reference_edges"].append(bad)
    result = MODULE.check_prompt_bundles(payload)
    assert "reference-edge-undeclared" in {row["code"] for row in result["failures"]}


def test_generated_member_index_is_exact() -> None:
    index = ROOT / "skills" / "researchguard" / "references" / "member-admission-index.md"
    assert index.read_text(encoding="utf-8") == MODULE.render_member_admission_index()


def test_manifest_forbids_eager_sibling_skill_paths() -> None:
    payload = manifest()
    prohibited = set(payload["prohibited_eager_member_paths"])
    umbrella = (ROOT / "skills" / "researchguard" / "SKILL.md").read_text(encoding="utf-8")
    assert prohibited.isdisjoint(path for path in prohibited if path in umbrella)
