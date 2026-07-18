import subprocess
import sys
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _run(*args):
    return subprocess.run([sys.executable, "-m", "researchguard", "source", *args], text=True, capture_output=True)


def test_create_validate_plan_report_and_export_smoke(tmp_path):
    created = tmp_path / "starter.yaml"
    trace = tmp_path / "trace.yaml"
    logic = tmp_path / "logic.yaml"

    result = _run(
        "create",
        "--output",
        str(created),
        "--model-contract",
        "examples/source/starter_researchguard.source.contract.json",
    )
    assert result.returncode == 0, result.stderr
    assert created.exists()

    result = _run("validate", str(created), "--model-contract", "examples/source/starter_researchguard.source.contract.json", "--pretty")
    assert result.returncode == 0, result.stderr
    assert '"ok": true' in result.stdout

    result = _run("plan", "examples/source/fuel_cell_project_discovery.yaml", "--model-contract", "examples/source/fuel_cell_project_discovery.contract.json", "--limit", "3", "--pretty")
    assert result.returncode == 0, result.stderr
    assert "selected_actions" in result.stdout

    result = _run("depth", str(created), "--model-contract", "examples/source/starter_researchguard.source.contract.json", "--pretty")
    assert result.returncode == 0, result.stderr
    depth_payload = json.loads(result.stdout)
    assert depth_payload["status"] == "planning_only"
    assert depth_payload["observation_depth_completed"] is False

    result = _run(
        "depth",
        "examples/source/starter_researchguard.source.yaml",
        "--model-contract",
        "examples/source/starter_researchguard.source.contract.json",
        "--observation",
        "examples/source/qualified_observation.yaml",
        "--pretty",
    )
    assert result.returncode == 0, result.stderr
    observed_depth = json.loads(result.stdout)
    assert observed_depth["observation_depth_completed"] is True
    assert observed_depth["status"] == "bounded"
    assert observed_depth["requested_claim_scope"] == "bounded"
    assert observed_depth["covered_claim_scope"] == "bounded"
    assert observed_depth["adequacy_status"] == "bounded"
    assert observed_depth["broad_claim_licensed"] is False
    assert observed_depth["coverage_universe"]["universe_fingerprint"]
    assert observed_depth["replan_comparison"]["removed_action_ids"]

    result = _run("report", "examples/source/fuel_cell_project_discovery.yaml", "--model-contract", "examples/source/fuel_cell_project_discovery.contract.json", "--format", "markdown")
    assert result.returncode == 0, result.stderr
    assert "SourceGuard Summary" in result.stdout

    result = _run("export-traceguard", "examples/source/fuel_cell_project_discovery.yaml", "--model-contract", "examples/source/fuel_cell_project_discovery.contract.json", "--output", str(trace))
    assert result.returncode == 0, result.stderr
    assert trace.exists()

    result = _run("export-logicguard", "examples/source/fuel_cell_project_discovery.yaml", "--model-contract", "examples/source/fuel_cell_project_discovery.contract.json", "--output", str(logic))
    assert result.returncode == 0, result.stderr
    assert logic.exists()


def test_model_backed_simulate_and_compare(tmp_path):
    result = _run(
        "simulate",
        "--mode",
        "gap-closure",
        "--model",
        "examples/source/fuel_cell_project_discovery.yaml",
        "--model-contract",
        "examples/source/fuel_cell_project_discovery.contract.json",
        "--pretty",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "gap-closure"
    assert payload["frontier"]["open_gap_count"] >= 1
    assert payload["selected_actions"]
    assert "not truth" in payload["boundary"]

    before = ROOT / "examples" / "source" / "fuel_cell_project_discovery.yaml"
    data = yaml.safe_load(before.read_text(encoding="utf-8"))
    data["gaps"][0]["status"] = "closed"
    after = tmp_path / "after.yaml"
    after.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    result = _run(
        "compare",
        str(before),
        str(after),
        "--before-model-contract",
        "examples/source/fuel_cell_project_discovery.contract.json",
        "--after-model-contract",
        "examples/source/fuel_cell_project_discovery.contract.json",
        "--pretty",
    )
    assert result.returncode == 2
    assert "gap.status is retired" in result.stderr


def test_failure_returns_2():
    result = _run("validate", "missing-file.yaml", "--model-contract", "missing-contract.json", "--pretty")
    assert result.returncode == 2
    assert '"ok": false' in result.stderr
