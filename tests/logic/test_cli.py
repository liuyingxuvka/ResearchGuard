from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from researchguard.logic import __version__, load_model, model_fingerprint


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

    loaded = load_model(model)
    selection_request = tmp_path / "selection.json"
    selection_request.write_text(json.dumps({
        "schema": "researchguard.logic.synthesis-request.v1", "request_id": "req", "target_id": "artifact",
        "target_goal": "Create a short deck", "artifact_kind": "presentation", "reader_id": "reader",
        "model_id": loaded.id, "model_fingerprint": model_fingerprint(loaded), "body_unit_order": ["u1"],
        "max_body_units": 1, "units": [{"unit_id": "u1", "parent_unit_id": None, "reader_question": "What?",
        "unit_job": "State claim", "claim_ids": ["C1"], "predecessor_unit_ids": [], "progression_relation": "concludes",
        "editorial_prominence": "lead", "placement": "body", "placement_reason": "required", "required": True}],
        "source_branch_bindings": []
    }), encoding="utf-8")
    synthesis = _run("synthesize", str(model), "--selection-request", str(selection_request), "--delivery", "--json")
    assert synthesis.returncode == 3
    payload = json.loads(synthesis.stdout)
    assert payload["plan"]["units"][0]["claim_ids"] == ["C1"]
    assert payload["delivery"]["status"] == "blocked_support_gap"
    assert payload["delivery"]["suggestions"] == []
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


def test_cli_depth_without_contract_prints_gap_summary(tmp_path: Path) -> None:
    output = tmp_path / "depth.json"
    result = _run("depth", "examples/logic/scientific_causal_claim.yaml", "--output", str(output))
    assert result.returncode == 3
    summary = json.loads(result.stdout)
    assert summary["status"] == "blocked"
    assert "claim_role_missing:C0:warrant" in summary["unresolved_gaps"]
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "blocked"


def test_cli_import_handoff_reads_a_traceguard_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.yaml"
    model = tmp_path / "model.yaml"
    result = subprocess.run([sys.executable, "-m", "researchguard", "trace", "export-logicguard",
                             "examples/trace/incident_response_storyline.yaml", "--output", str(bundle)],
                            cwd=ROOT, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    imported = _run("import-handoff", str(bundle), "--output", str(model))
    assert imported.returncode == 0, imported.stdout + imported.stderr
    assert json.loads(imported.stdout)["root_claim"] == "claim_trace_metadata_incident"
    assert "validation: OK" in _run("validate", str(model)).stdout
    assert "missing_warrant" in _run("diagnose", str(model)).stdout


def test_import_handoff_builds_one_claim_per_hypothesis(tmp_path: Path) -> None:
    import yaml
    from researchguard.logic.provenance import content_hash_for
    fixture = ROOT / "tests/trace/fixtures/evergiven/tr_v2b.yaml"
    bundle_path, model_path = tmp_path / "signed-bundle.yaml", tmp_path / "signed-model.yaml"
    exported = subprocess.run([sys.executable, "-m", "researchguard", "trace", "export-logicguard",
                               str(fixture), "--output", str(bundle_path)], cwd=ROOT, capture_output=True, text=True)
    assert exported.returncode == 0, exported.stdout + exported.stderr
    bundle = yaml.safe_load(bundle_path.read_text())
    imported = _run("import-handoff", str(bundle_path), "--output", str(model_path))
    assert imported.returncode == 0, imported.stdout + imported.stderr
    assert json.loads(imported.stdout)["root_claim"] == "h_suez"
    data = yaml.safe_load(model_path.read_text())
    assert data["nodes"]["h_suez"]["type"] == data["nodes"]["h_demand"]["type"] == "Claim"
    assert not any(edge["source"] == "anc-transpacific" and edge["target"] == "h_suez" and edge["type"] == "supports"
                   for edge in data["edges"])
    attackers = {edge["source"] for edge in data["edges"] if edge["target"] == "h_suez" and edge["type"] == "attacks"}
    assert attackers and all(data["nodes"][item]["type"] == "Rebuttal" for item in attackers)
    assert any(edge["source"] == "anc-transpacific" and edge["target"] in attackers and edge["type"] == "supports"
               for edge in data["edges"])
    assert not any(edge["source"] in {"h_suez", "h_demand"} and edge["target"] in {"h_suez", "h_demand"}
                   for edge in data["edges"])
    evidence = {item["evidence_id"]: item for item in bundle["evidence"]}
    for node_id, node in data["nodes"].items():
        if node["type"] != "Evidence":
            continue
        original = evidence[node_id]
        assert node["text"] == original["text"]
        provenance = node["provenance"][0]
        assert provenance["origin_kind"] == "external_source"
        assert provenance["source_id"] == original["source_id"]
        assert provenance["locator"] == node_id
        assert provenance["metadata"]["locator_text"] == original["locator"]
        assert provenance["content_hash"] == content_hash_for(node["text"])
    validated = _run("validate", str(model_path))
    assert validated.returncode == 0, validated.stdout + validated.stderr
    assert "validation: OK" in validated.stdout
    assert "no provenance" not in validated.stdout + validated.stderr
    assert "missing_warrant" in _run("diagnose", str(model_path)).stdout


def test_validate_checks_provenance_against_the_source_model(tmp_path: Path) -> None:
    import yaml
    raw = {"model": {"id": "anchors", "root_claim": "C"}, "nodes": {
        "C": {"type": "Claim", "text": "Bounded claim"},
        "E": {"type": "Evidence", "text": "Dates", "provenance": [
            {"origin_kind": "external_source", "source_id": "src-sca-2021", "locator": "anc-sca-dates", "quote": "Dates"}]},
    }, "edges": []}
    path = tmp_path / "logic.yaml"
    source = "tests/source/fixtures/evergiven/src_v4.yaml"
    for source_id, locator, expected in [("src-sca-2021", "anc-sca-dates", 0),
                                           ("src-sca-2021", "anc-nope", 2),
                                           ("src-nope", "anc-sca-dates", 2)]:
        raw["nodes"]["E"]["provenance"][0].update(source_id=source_id, locator=locator)
        path.write_text(yaml.safe_dump(raw))
        result = _run("validate", str(path), "--source-model", source)
        assert result.returncode == expected, result.stdout
        if expected:
            assert "E" in result.stdout and source_id in result.stdout and locator in result.stdout


def test_intake_uses_the_given_source_id(tmp_path: Path) -> None:
    from researchguard.logic import SourceLibrary
    library = tmp_path / "library"
    for route in [("intake",), ("library", "intake")]:
        result = _run(*route, str(library), "--text", "A short preserved source.", "--source-id", "src-canonical", "--json")
        assert result.returncode == 0, result.stdout
        assert "src-canonical" in result.stdout
    text = tmp_path / "source.txt"
    text.write_text("Different content.")
    result = _run("library", "import", str(library), str(text), "--source-id", "src-canonical")
    assert result.returncode != 0 and "different content" in result.stdout
    assert len(SourceLibrary(library).list_sources()) == 1


def test_import_handoff_into_keeps_hand_built_nodes(tmp_path: Path) -> None:
    import yaml
    bundle = {'schema': 'researchguard.trace.logic-handoff.v1', 'hypotheses': [
        {'hypothesis_id': 'h', 'claim': 'Hypothesis', 'role': 'primary', 'supporting_evidence_ids': ['a'],
         'opposing_evidence_ids': [], 'limiting_evidence_ids': []}],
        'evidence': [{'evidence_id': 'a', 'source_id': 's', 'text': 'Observation', 'locator': 'p1'}]}
    bundle_path, into, out = (tmp_path / name for name in ('bundle.yaml', 'logic.yaml', 'new.yaml'))
    bundle_path.write_text(yaml.safe_dump(bundle))
    assert _run('import-handoff', str(bundle_path), '--output', str(into)).returncode == 0
    existing = yaml.safe_load(into.read_text())
    existing['nodes']['hand-built'] = {'type': 'Warrant', 'text': 'Hand-written reasoning'}
    existing['nodes']['h']['text'] = 'Authored claim'
    existing['edges'][0]['weight'] = .7
    into.write_text(yaml.safe_dump(existing))
    before = into.read_bytes()
    bundle['evidence'].append({'evidence_id': 'b', 'source_id': 's', 'text': 'New evidence', 'locator': 'p2'})
    bundle['hypotheses'][0]['supporting_evidence_ids'].append('b')
    bundle_path.write_text(yaml.safe_dump(bundle))
    rejected = _run('import-handoff', str(bundle_path), '--into', str(into), '--output', str(into))
    assert rejected.returncode != 0 and into.read_bytes() == before
    result = _run('import-handoff', str(bundle_path), '--into', str(into), '--output', str(out))
    assert result.returncode == 0, result.stdout
    summary = json.loads(result.stdout)
    assert summary['added']['nodes'] == ['b']
    assert {'kind': 'nodes', 'id': 'h'} in summary['conflicts']
    assert any(row['kind'] == 'edges' for row in summary['conflicts'])
    merged = yaml.safe_load(out.read_text())
    assert into.read_bytes() == before
    for node_id, row in existing['nodes'].items():
        assert merged['nodes'][node_id] == row
    assert merged['edges'][:len(existing['edges'])] == existing['edges']
    assert _run('validate', str(out)).returncode == 0
