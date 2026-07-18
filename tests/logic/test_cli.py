from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from researchguard.logic import __version__


ROOT = Path(__file__).resolve().parents[2]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "researchguard", "logic", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_cli_validate_and_evaluate_smoke(tmp_path: Path) -> None:
    example = "examples/logic/engineering_efficiency_argument.yaml"
    validation = _run("validate", example)
    assert validation.returncode == 0
    assert "validation: OK" in validation.stdout

    output = tmp_path / "evaluation.json"
    evaluation = _run("evaluate", example, "--output", str(output))
    assert evaluation.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["root_claim"] == "C0"


def test_cli_version_smoke() -> None:
    result = _run("--version")
    assert result.returncode == 0
    assert f"logicguard {__version__}" in result.stdout


def test_cli_report_outline_and_simulate_smoke(tmp_path: Path) -> None:
    example = "examples/logic/engineering_efficiency_argument.yaml"
    report = tmp_path / "report.md"
    outline = tmp_path / "outline.md"
    fragility = tmp_path / "fragility.json"
    combo = tmp_path / "combo.json"
    gaps = tmp_path / "gaps.json"
    assert _run("report", example, "--output", str(report)).returncode == 0
    assert _run("outline", example, "--output", str(outline)).returncode == 0
    assert _run("simulate", example, "--root", "C0", "--mode", "fragility", "--output", str(fragility)).returncode == 0
    assert _run("simulate", example, "--root", "C0", "--mode", "combination-counterexample", "--output", str(combo)).returncode == 0
    assert _run("gaps", example, "--output", str(gaps)).returncode == 0
    assert "Executive Summary" in report.read_text(encoding="utf-8")
    assert "Root Claim" in outline.read_text(encoding="utf-8")
    assert json.loads(fragility.read_text(encoding="utf-8"))["mode"] == "fragility"
    assert json.loads(combo.read_text(encoding="utf-8"))["mode"] == "combination-counterexample"
    assert json.loads(gaps.read_text(encoding="utf-8"))["route_summary"]


def test_cli_argument_and_library_workflow_smoke(tmp_path: Path) -> None:
    argument = tmp_path / "argument.yaml"
    created_argument = _run(
        "argument",
        "create",
        str(argument),
        "--id",
        "ai_efficiency",
        "--title",
        "AI Efficiency",
        "--claim",
        "AI tools can improve short-term software engineering efficiency.",
        "--section",
        "Controlled task evidence matters.",
    )
    assert created_argument.returncode == 0
    assert argument.exists()

    library_root = tmp_path / "library"
    source_file = tmp_path / "paper.txt"
    source_file.write_text("study text", encoding="utf-8")
    assert _run("library", "init", str(library_root)).returncode == 0
    imported = _run(
        "library",
        "import",
        str(library_root),
        str(source_file),
        "--title",
        "AI Study",
        "--source-date",
        "2024",
        "--coverage-period",
        "2021-2023",
    )
    assert imported.returncode == 0
    imported_payload = json.loads(imported.stdout)
    source_id = imported_payload["source"]["source_id"]
    assert imported_payload["source"]["coverage_period"] == "2021-2023"

    model_result = _run(
        "library",
        "model-source",
        str(library_root),
        source_id,
        "--claim",
        "AI tools reduce task time.",
        "--evidence",
        "Participants completed tasks faster.",
        "--locator",
        "abstract",
    )
    assert model_result.returncode == 0

    project = _run("library", "create-project", str(library_root), "AI Paper", "--topic", "AI efficiency")
    assert project.returncode == 0
    project_id = json.loads(project.stdout)["project_id"]
    assert _run("library", "select-source", str(library_root), project_id, source_id).returncode == 0
    assert _run(
        "library",
        "deepen-source",
        str(library_root),
        source_id,
        "--project",
        project_id,
        "--topic-focus",
        "task time",
        "--locator",
        "section 4",
        "--anchor-node",
        "C1",
        "--branch-role",
        "evidence_detail",
        "--evidence",
        "Treatment group finished faster.",
    ).returncode == 0

    branches = _run("library", "branches", str(library_root), source_id, "--anchor-node", "C1")
    assert branches.returncode == 0
    branch_payload = json.loads(branches.stdout)["branches"]
    assert branch_payload[0]["anchor_node_id"] == "C1"

    search = _run("library", "search", str(library_root), "finished faster", "--project", project_id, "--branch", branch_payload[0]["branch_id"])
    assert search.returncode == 0
    hits = json.loads(search.stdout)["hits"]
    assert hits
    assert hits[0]["branch_id"] == branch_payload[0]["branch_id"]

    audit = _run("library", "audit-branches", str(library_root), source_id, "--json")
    assert audit.returncode == 0
    assert json.loads(audit.stdout)["ok"] is True

    linked = _run(
        "library",
        "link",
        str(library_root),
        project_id,
        "--project-node",
        "C1",
        "--source-id",
        source_id,
        "--source-node",
        hits[0]["node_id"],
        "--relation",
        "supports",
    )
    assert linked.returncode == 0
    assert json.loads(linked.stdout)["source_branch_id"] == branch_payload[0]["branch_id"]
    links = _run("library", "links", str(library_root), project_id, "--project-node", "C1")
    assert links.returncode == 0
    assert json.loads(links.stdout)["links"][0]["source_id"] == source_id

    snapshot = _run("library", "view-snapshot", str(library_root))
    assert snapshot.returncode == 0
    snapshot_payload = json.loads(snapshot.stdout)
    assert snapshot_payload["summary"]["source_count"] == 1
    assert snapshot_payload["cards"][0]["project_ids"] == [project_id]
    assert snapshot_payload["cards"][0]["source_date"] == "2024"

    graph = _run("library", "view-graph", str(library_root), source_id)
    assert graph.returncode == 0
    assert json.loads(graph.stdout)["root_claim"] == "C1"

    localized = tmp_path / "i18n.json"
    localized.write_text(
        json.dumps(
                {
                    "en": {
                        "claim": "AI tools reduce task time.",
                        "evidence": "Participants completed tasks faster.",
                        "title": "AI Study",
                    },
                    "zh-CN": {
                        "claim": "AI 工具减少任务时间。",
                        "evidence": "参与者更快完成了任务。",
                        "title": "AI 研究",
                    },
                }
        ),
        encoding="utf-8",
    )
    assert _run("library", "model-source", str(library_root), source_id, "--i18n-json", str(localized)).returncode == 0
    graph_zh = _run("library", "view-graph", str(library_root), source_id, "--language", "zh-CN")
    assert graph_zh.returncode == 1
    assert "missing exact localized field" in graph_zh.stdout

    package = tmp_path / "project.researchguard.logic.zip"
    export = _run("library", "export-package", str(library_root), str(package), "--project", project_id)
    assert export.returncode == 0
    assert json.loads(export.stdout)["source_ids"] == [source_id]

    inspect = _run("library", "inspect-package", str(package))
    assert inspect.returncode == 0
    assert json.loads(inspect.stdout)["package_format"] == "researchguard.logic.source-library-package.v1"

    imported_root = tmp_path / "imported-library"
    dry_run = _run("library", "import-package", str(imported_root), str(package), "--dry-run")
    assert dry_run.returncode == 0
    assert json.loads(dry_run.stdout)["dry_run"] is True
    assert not imported_root.exists()

    imported = _run("library", "import-package", str(imported_root), str(package))
    assert imported.returncode == 0
    assert json.loads(imported.stdout)["created_projects"] == [project_id]


def test_cli_intake_preserves_and_models_materials(tmp_path: Path) -> None:
    library_root = tmp_path / "library"
    source_file = tmp_path / "paper.txt"
    source_file.write_text("Claim: AI tools reduce task time.\nEvidence: Participants finished faster.", encoding="utf-8")

    intake = _run(
        "intake",
        str(library_root),
        "--file",
        str(source_file),
        "--project",
        "AI Paper",
        "--project-topic",
        "AI efficiency",
        "--source-date",
        "2024",
        "--coverage-period",
        "2023",
        "--json",
    )
    assert intake.returncode == 0
    payload = json.loads(intake.stdout)
    assert payload["summary"]["saved"] == 1
    assert payload["summary"]["project_assigned"] == 1
    assert payload["summary"]["modeled"] == 1
    item = payload["materials"][0]
    assert item["project_id"] == "ai-paper"
    assert item["modeling_status"] == "modeled"
    assert item["extracted_fields"] == ["claim", "evidence"]

    repeated = _run("library", "intake", str(library_root), "--file", str(source_file), "--json")
    assert repeated.returncode == 0
    repeated_payload = json.loads(repeated.stdout)
    assert repeated_payload["summary"]["reused"] == 1

    human = _run("intake", str(tmp_path / "other-library"), "--text", "Claim: Saved text")
    assert human.returncode == 0
    assert "Intake complete:" in human.stdout


def test_cli_importance_structure_and_synthesis_smoke(tmp_path: Path) -> None:
    model = tmp_path / "artifact.yaml"
    model.write_text(
        """
model:
  id: cli_artifact
  root_claim: C1
  artifact_kind: presentation
nodes:
  D0:
    type: Document
    text: Deck
  B1:
    type: ArgumentBlock
    text: Slide 1
    order_index: 1
  B2:
    type: ArgumentBlock
    text: Slide 2
    order_index: 2
  C1:
    type: Claim
    text: Main claim.
    parent: B1
    importance: 0.95
    salience: core
  L1:
    type: Limitation
    text: Validated range only.
    parent: B2
    importance: 0.9
    salience: risk
edges:
  - source: L1
    target: C1
    type: qualifies
hierarchy:
  D0: [B1, B2]
  B1: [C1]
  B2: [L1]
""",
        encoding="utf-8",
    )

    importance = _run("importance", str(model), "--json")
    assert importance.returncode == 0
    assert json.loads(importance.stdout)["records"][0]["id"] == "C1"

    audit = _run("structure", "audit", str(model), "--json")
    assert audit.returncode == 0
    assert json.loads(audit.stdout)["findings"]

    synthesis = _run("synthesize", str(model), "--goal", "Create a short deck", "--delivery", "--json")
    assert synthesis.returncode == 0
    payload = json.loads(synthesis.stdout)
    assert payload["plan"]["selected_items"][0]["node_id"] == "C1"
    suggestions = "\n".join(item["suggested_text"] for item in payload["delivery"]["suggestions"])
    assert "missing_handoff" not in suggestions


def test_cli_structure_from_markdown(tmp_path: Path) -> None:
    source = tmp_path / "outline.md"
    source.write_text(
        "\n".join(
            [
                "# Report",
                "## Results",
                "### Main result",
                "Claim: The result is usable.",
                "Evidence: Validation traces match.",
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "model.yaml"

    result = _run("structure", "from-markdown", str(source), "--artifact-kind", "report", "--output", str(output))

    assert result.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["model"]["artifact_kind"] == "report"
    assert payload["model"]["root_claim"] == "C1"
    assert payload["hierarchy"]["B1"] == ["C1", "E1"]
