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

    result = _run("create", "--output", str(created))
    assert result.returncode == 0, result.stderr
    assert created.exists()

    result = _run("validate", str(created), "--pretty")
    assert result.returncode == 0, result.stderr
    assert '"ok": true' in result.stdout

    result = _run("plan", "examples/source/fuel_cell_project_discovery.yaml", "--limit", "3", "--pretty")
    assert result.returncode == 0, result.stderr
    assert "selected_actions" in result.stdout

    result = _run("depth", str(created), "--pretty")
    assert result.returncode == 0, result.stderr
    depth_payload = json.loads(result.stdout)
    assert depth_payload["status"] == "planning_only"
    assert depth_payload["observation_depth_completed"] is False

    result = _run("depth", "examples/source/starter_researchguard.source.yaml", "--observation", "examples/source/qualified_observation.yaml", "--pretty")
    assert result.returncode == 0, result.stderr
    observed_depth = json.loads(result.stdout)
    assert observed_depth["observation_depth_completed"] is True
    assert observed_depth["status"] == "bounded"
    assert observed_depth["requested_claim_scope"] == "bounded"
    assert observed_depth["covered_claim_scope"] == "bounded"
    assert observed_depth["adequacy_status"] == "bounded"
    assert observed_depth["broad_claim_licensed"] is False
    assert observed_depth["coverage_universe"]["dimensions"]
    assert observed_depth["replan_comparison"]["removed_action_ids"]

    result = _run("report", "examples/source/fuel_cell_project_discovery.yaml", "--format", "markdown")
    assert result.returncode == 0, result.stderr
    assert "SourceGuard Summary" in result.stdout

    result = _run("export-traceguard", "examples/source/fuel_cell_project_discovery.yaml", "--output", str(trace))
    assert result.returncode == 0, result.stderr
    assert trace.exists()


def test_model_backed_simulate_and_compare(tmp_path):
    result = _run("simulate", "--mode", "gap-closure", "--model", "examples/source/fuel_cell_project_discovery.yaml", "--pretty")
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

    result = _run("compare", str(before), str(after), "--pretty")
    assert result.returncode == 2
    assert "gap.status is retired" in result.stderr


def test_failure_returns_2():
    result = _run("validate", "missing-file.yaml", "--pretty")
    assert result.returncode == 2
    assert '"ok": false' in result.stderr


def test_grown_model_still_loads_after_evidence_for_the_guarded_gap(tmp_path):
    name = "paper_citation_discovery.yaml"
    (tmp_path / name).write_text((ROOT / "examples" / "source" / name).read_text(encoding="utf-8"), encoding="utf-8")
    observation = {
        "observation_id": "obs-baseline-1",
        "observed_sources": [{"source_id": "src-history-1", "title": "Historical baseline paper",
                              "source_type": "paper", "source_status": "saved", "source_reliability": 0.9,
                              "source_role": "historical_background", "lineage_id": "lineage-history-1", "access_status": "public"}],
        "observed_anchors": [{"anchor_id": "anchor-history-1", "source_id": "src-history-1", "anchor_type": "paragraph",
                              "locator": "section=background;paragraph=2", "normalized_summary": "A historical paper states the baseline rate.",
                              "modality": "text", "extraction_confidence": 0.9, "specificity": 0.9,
                              "supports": ["gap-baseline"], "usable_for_claim": True}],
        "new_entities": [], "new_leads": [], "new_gaps": [], "contradictions": [],
    }
    path = tmp_path / "obs.yaml"
    path.write_text(yaml.safe_dump(observation), encoding="utf-8")
    result = _run("add-observation", str(tmp_path / "paper_citation_discovery.yaml"), "--observation", str(path), "--output", str(tmp_path / "v2.yaml"))
    assert result.returncode == 0, result.stdout + result.stderr
    result = _run("validate", str(tmp_path / "v2.yaml"))
    assert result.returncode == 0, result.stdout + result.stderr


def test_plan_prints_scores_only_on_request():
    argv = ("plan", "examples/source/fuel_cell_project_discovery.yaml",)
    ordinary = _run(*argv)
    detailed = _run(*argv, "--all-scores")
    assert ordinary.returncode == detailed.returncode == 0
    assert "scored_actions" not in json.loads(ordinary.stdout)
    assert json.loads(detailed.stdout)["scored_actions"]


def test_create_plan_and_add_observation_need_no_model_contract(tmp_path):
    starter = tmp_path / "starter.yaml"
    grown = tmp_path / "grown.yaml"
    result = _run("create", "--output", str(starter))
    assert result.returncode == 0, result.stderr
    result = _run("plan", str(starter), "--limit", "2")
    assert result.returncode == 0, result.stderr
    assert "selected_actions" in json.loads(result.stdout)
    result = _run("add-observation", str(starter), "--observation", "examples/source/qualified_observation.yaml", "--output", str(grown))
    assert result.returncode == 0, result.stderr
    result = _run("validate", str(grown))
    assert result.returncode == 0, result.stderr


def test_plan_and_score_actions_agree() -> None:
    fixture = str(Path(__file__).parent / "fixtures/evergiven/src_v1.yaml")
    planned, scored = _run("plan", fixture, "--all-scores"), _run("score-actions", fixture)
    assert planned.returncode == scored.returncode == 0
    p = {item["action_id"]: item for item in json.loads(planned.stdout)["scored_actions"]}
    q = {item["action_id"]: item for item in json.loads(scored.stdout)["scored_actions"]}
    assert p == q
    assert p["act-pretrend"]["total_score"] == q["act-pretrend"]["total_score"]


def test_compare_a_model_with_its_grown_version(tmp_path: Path) -> None:
    fixtures = Path(__file__).parent / "fixtures/evergiven"
    baseline, observation = fixtures / "src_v1.yaml", fixtures / "obs1.yaml"
    original_bytes = baseline.read_bytes()
    grown = tmp_path / "grown.yaml"
    added = _run("add-observation", str(baseline), "--observation", str(observation), "--output", str(grown))
    assert added.returncode == 0, added.stdout + added.stderr
    result = _run("compare", str(baseline), str(grown))
    assert result.returncode == 0, result.stdout + result.stderr
    compared = json.loads(result.stdout)
    assert compared["ok"] is True
    changes = next(item["changes"] for item in compared["gap_delta"]["changed"] if item["gap_id"] == "gap-event-dates")
    assert changes["semantic_state"] == {"before": "discovered", "after": "closed"}
    assert changes["qualification_decision"] == {"before": "not_evaluated", "after": "claim_usable"}
    assert "status" not in changes
    self_result = _run("compare", str(baseline), str(baseline))
    assert self_result.returncode == 0, self_result.stdout + self_result.stderr
    self_comparison = json.loads(self_result.stdout)
    assert self_comparison["ok"] is True
    for key in ("source_delta", "anchor_delta", "gap_delta", "action_delta"):
        assert not any(self_comparison[key].values())
    assert baseline.read_bytes() == original_bytes


def test_report_lists_sources_anchors_and_closure() -> None:
    path = ROOT / "tests/source/fixtures/evergiven/src_v4.yaml"
    for format_name in ("markdown", "txt"):
        result = _run("report", str(path), "--format", format_name)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Sources and Anchors" in result.stdout
        assert "anc-sca-dates" in result.stdout
        assert any("gap-event-dates" in line and "anc-sca-dates" in line for line in result.stdout.splitlines())
        assert "sources=" in result.stdout
        assert "lineage=" in result.stdout


def test_reports_keep_anchors_whose_source_row_is_absent() -> None:
    from researchguard.source.report import render_markdown, render_text
    from researchguard.source.schema import BeliefState

    model = BeliefState.from_dict({"anchors": [{"anchor_id": "orphan-anchor", "source_id": "absent-source", "locator": "Page 4"}]})
    for render in (render_markdown, render_text):
        report = render(model)
        assert "orphan-anchor" in report
        assert "source_id=absent-source" in report
        assert "source row absent" in report
        assert "Page 4" in report
    assert not model.sources


def test_retired_logic_export_is_an_unknown_command():
    result = _run("export-logicguard", "unused.yaml", "--output", "unused-output.yaml")
    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_add_anchor_adds_source_and_anchor(tmp_path):
    from researchguard.source.cli import main
    from researchguard.source.loader import load_model, write_yaml
    from researchguard.source.schema import BeliefState
    model = tmp_path / 'source.yaml'
    write_yaml(model, BeliefState())
    def add(source_id, anchor_id, output):
        return main(['add-anchor', str(model), '--source-id', source_id, '--anchor-id', anchor_id,
            '--quote', 'A verified passage', '--locator', 'page 4', '--title', 'A source',
            '--url', 'https://example.org', '--date', '2026-10-27', '--output', str(output)])
    assert add('s', 'a', model) == 0
    assert add('s', 'b', model) == 0
    result = load_model(model)
    assert len(result.sources) == 1 and [a.anchor_id for a in result.anchors] == ['a', 'b']
    assert result.sources[0].source_date == '2026-10-27'
    assert result.anchors[0].text == 'A verified passage' and result.anchors[0].locator == 'page 4'
    before = model.read_bytes()
    assert add('s', 'a', model) == 1 and model.read_bytes() == before
    absent = tmp_path / 'absent.yaml'
    assert add('other', 'a', absent) == 1 and not absent.exists()
