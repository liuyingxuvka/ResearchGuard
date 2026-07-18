from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from researchguard.trace import library as case_library
from researchguard.trace.entity_resolution import score_entities
from researchguard.trace.evaluator import evaluate_model
from researchguard.trace.handoff import derive_trace_handoffs, review_trace_consolidation
from researchguard.trace.loader import load_model
from researchguard.trace.schema import EntityMention, SchemaError, TraceGuardModel
from researchguard.trace.soft_logic import implication_violation, soft_and, soft_not, soft_or, weighted_loss


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples" / "trace"


def example(name: str) -> Path:
    return EXAMPLES / name


def copy_case_library(tmp_path: Path) -> Path:
    target = tmp_path / "case_library"
    shutil.copytree(EXAMPLES / "case_library", target)
    return target


def test_yaml_loading_header_and_valid_schema() -> None:
    model = load_model(example("project_radar_hydrogen_trace.yaml"))
    assert model.metadata["skill"] == "TraceGuard"
    assert model.sources
    assert model.evidence
    assert model.traces


def test_schema_rejects_missing_evidence_reference(tmp_path: Path) -> None:
    data = yaml.safe_load(example("project_radar_hydrogen_trace.yaml").read_text(encoding="utf-8"))
    data["events"][0]["evidence_ids"] = ["missing_evidence"]
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    with pytest.raises(SchemaError, match="missing evidence"):
        load_model(bad)


def test_generic_predicate_bypass_is_rejected() -> None:
    data = yaml.safe_load(example("project_radar_hydrogen_trace.yaml").read_text(encoding="utf-8"))
    data["predicates"] = [{"name": "SourceReliable", "args": ["src_funding"], "value": 1.2}]
    with pytest.raises(SchemaError, match="retired schema fields.*predicates"):
        TraceGuardModel.from_dict(data)


def test_soft_logic_operators_and_loss() -> None:
    assert soft_not(0.25) == pytest.approx(0.75)
    assert soft_and(0.8, 0.7) == pytest.approx(0.5)
    assert soft_and(0.9, 0.9, 0.9) == pytest.approx(0.7)
    assert soft_or(0.6, 0.7) == pytest.approx(1.0)
    assert implication_violation(0.8, 0.3) == pytest.approx(0.5)
    assert weighted_loss(0.5, 2.0) == pytest.approx(1.0)
    assert weighted_loss(0.5, 2.0, squared=True) == pytest.approx(0.5)


def test_project_radar_candidate_report_boundaries() -> None:
    result = evaluate_model(load_model(example("project_radar_hydrogen_trace.yaml")))
    trace = result.traces[0]
    assert trace.validation_status == "candidate"
    assert trace.support < 1
    assert any(gap.gap_id == "access_gap" for gap in trace.gaps)
    assert "not support confirmed" in trace.safe_wording
    assert "structural support" in trace.claim_boundary


def test_invalid_source_cannot_validate_trace() -> None:
    result = evaluate_model(load_model(example("invalid_source_example.yaml")))
    assert result.traces[0].validation_status == "insufficient"
    assert any(item.diagnostic_id == "invalid_source_not_validation_evidence" for item in result.diagnostics)


def test_source_only_cannot_become_project() -> None:
    result = evaluate_model(load_model(example("source_registry_only.yaml")))
    assert result.traces[0].validation_status == "source_only"
    assert "source-only material" in result.traces[0].safe_wording


def test_patent_and_hiring_only_remain_weak_signals() -> None:
    patent = evaluate_model(load_model(example("patent_as_weak_signal.yaml"))).traces[0]
    hiring = evaluate_model(load_model(example("hiring_as_weak_signal.yaml"))).traces[0]
    assert patent.validation_status == "weak_signal"
    assert hiring.validation_status == "weak_signal"
    assert "not validation" in patent.safe_wording
    assert "not validation" in hiring.safe_wording


def test_caller_cannot_prefill_weak_source_validation_status(tmp_path: Path) -> None:
    data = yaml.safe_load(example("patent_as_weak_signal.yaml").read_text(encoding="utf-8"))
    data["traces"][0]["validation_status"] = "validated"
    path = tmp_path / "validated_patent.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    with pytest.raises(SchemaError, match="inference outputs are forbidden"):
        load_model(path)


def test_funding_tender_company_forms_candidate_not_validated() -> None:
    result = evaluate_model(load_model(example("project_radar_hydrogen_trace.yaml")))
    assert {"ev_funding", "ev_tender", "ev_company"} <= set(result.traces[0].evidence_ids)
    assert result.traces[0].validation_status == "candidate"


def test_temporal_contradiction_and_stage_reversal_are_visible() -> None:
    result = evaluate_model(load_model(example("operation_before_tender_contradiction.yaml")))
    ids = {item.contradiction_id for item in result.contradictions}
    assert "operation_before_tender" in ids
    assert "stage_reversal" in ids
    assert result.traces[0].validation_status == "contradicted"


def test_missing_location_date_and_location_role_diagnostics() -> None:
    result = evaluate_model(load_model(example("invalid_source_example.yaml")))
    assert any(gap.gap_id == "missing_date" for gap in result.gaps)
    assert any(item.diagnostic_id == "location_role_required" for item in result.diagnostics)


def test_entity_scorer_high_for_alias_and_low_with_blockers() -> None:
    left = EntityMention("a", None, "Rhine Hydrogen Hub", "rhine hydrogen hub", aliases=["Rhine H2 Hub"], country="DE", role="project", confidence=0.9)
    right = EntityMention("b", None, "Rhine H2 Hub", "rhine h2 hub", aliases=["Rhine Hydrogen Hub"], country="DE", role="project", confidence=0.8)
    assert score_entities(left, right).relation == "same_as"
    blocked = EntityMention("c", None, "Rhine Hydrogen Hub", "rhine hydrogen hub", aliases=[], country="US", role="patent_office_country", confidence=0.8)
    blocked_score = score_entities(left, blocked)
    assert blocked_score.score < 0.86
    assert blocked_score.blockers


def test_overmerge_and_undermerge_risk_diagnostics(tmp_path: Path) -> None:
    data = yaml.safe_load(example("project_radar_hydrogen_trace.yaml").read_text(encoding="utf-8"))
    data["entity_resolutions"].append(
        {
            "left_id": "ent_project",
            "right_id": "ent_company",
            "relation": "same_as",
            "score": 0.6,
            "reasons": ["manual_merge"],
            "blockers": ["role_blocker"],
        }
    )
    data["entities"].append(
        {
            "mention_id": "ent_project_variant",
            "evidence_id": "ev_company",
            "raw_name": "Rhine Hydrogen Hub Phase 1",
            "normalized_name": "rhine hydrogen hub phase 1",
            "entity_type": "project",
            "aliases": [],
            "country": "DE",
            "role": "project",
            "confidence": 0.7,
        }
    )
    path = tmp_path / "entities.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    result = evaluate_model(load_model(path))
    ids = {item.diagnostic_id for item in result.diagnostics}
    assert "overmerge_risk" in ids
    assert "undermerge_risk" in ids


def test_report_and_logicguard_export_include_boundaries(tmp_path: Path) -> None:
    report = subprocess.run(
        [sys.executable, "-m", "researchguard", "trace", "report", str(example("project_radar_hydrogen_trace.yaml")), "--format", "markdown"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "Validation status" in report
    assert "Claim boundary" in report
    assert "Report Handoff" in report
    assert "Consolidation And Same-Class Review" in report
    assert "structural support" in report
    assert "candidate" in report
    bundle = tmp_path / "bundle.yaml"
    subprocess.run(
        [sys.executable, "-m", "researchguard", "trace", "export-logicguard", str(example("project_radar_hydrogen_trace.yaml")), "--output", str(bundle)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    exported = yaml.safe_load(bundle.read_text(encoding="utf-8"))
    claim = exported["claims"][0]
    assert {"claim", "evidence", "warrant", "assumption", "limitation", "scope"} <= set(claim)
    assert exported["handoffs"][0]["claim_id"] == "claim_trace_rhine_h2"
    assert exported["consolidation_findings"]


def test_trace_handoff_contains_report_and_logicguard_fields() -> None:
    model = load_model(example("project_radar_hydrogen_trace.yaml"))
    result = evaluate_model(model)
    handoff = derive_trace_handoffs(result)[0]
    assert handoff.trace_id == "trace_rhine_h2"
    assert handoff.claim_id == "claim_trace_rhine_h2"
    assert handoff.paragraph_target == "trace:trace_rhine_h2"
    assert "access_gap" in " ".join(handoff.missing_evidence)
    assert "candidate storyline" in handoff.safe_wording


def test_structural_trace_fields_survive_evaluation_handoff_and_export(tmp_path: Path) -> None:
    model = load_model(example("structural_thesis_trace.yaml"))
    result = evaluate_model(model)
    trace = result.traces[0]
    assert trace.structure_unit_id == "chapter_3.technology_summary"
    assert trace.destination_unit_id == "chapter_4.method_gap"
    assert trace.trace_layer == "requirement_to_design"
    assert trace.weakest_link
    handoff = derive_trace_handoffs(result)[0]
    assert handoff.paragraph_target == "chapter_3.technology_summary"
    assert handoff.conclusion_transfer_status == "partial"

    bundle = tmp_path / "structural_bundle.yaml"
    subprocess.run(
        [sys.executable, "-m", "researchguard", "trace", "export-logicguard", str(example("structural_thesis_trace.yaml")), "--output", str(bundle)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    exported = yaml.safe_load(bundle.read_text(encoding="utf-8"))
    assert exported["claims"][0]["source_unit_id"] == "chapter_3.technology_summary"
    assert exported["claims"][0]["destination_unit_id"] == "chapter_4.method_gap"
    assert exported["handoffs"][0]["weakest_link"] == "Only one synthetic method note is present."


def test_consolidation_finds_duplicate_evidence_and_same_class_reviews(tmp_path: Path) -> None:
    data = yaml.safe_load(example("project_radar_hydrogen_trace.yaml").read_text(encoding="utf-8"))
    duplicate = dict(data["evidence"][0])
    duplicate["evidence_id"] = "ev_funding_duplicate"
    data["evidence"].append(duplicate)
    path = tmp_path / "duplicate_evidence.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    model = load_model(path)
    result = evaluate_model(model)
    findings = review_trace_consolidation(model, result)
    types = {item.finding_type for item in findings}
    assert "possible_duplicate_evidence" in types
    assert "patent_deployment_review" in types
    assert "hiring_operation_review" in types


def test_generic_incident_storyline_is_not_project_bound() -> None:
    result = evaluate_model(load_model(example("incident_response_storyline.yaml")))
    trace = result.traces[0]
    assert trace.trace_type == "incident_storyline"
    assert trace.validation_status == "validated"
    assert not any(gap.gap_id == "missing_location" for gap in trace.gaps)
    assert "project" not in trace.safe_wording.lower()


@pytest.mark.parametrize(
    "subcommand,args",
    [
        ("validate", ["examples/trace/project_radar_hydrogen_trace.yaml"]),
        ("evaluate", ["examples/trace/project_radar_hydrogen_trace.yaml", "--pretty"]),
        ("diagnose", ["examples/trace/project_radar_hydrogen_trace.yaml", "--pretty"]),
        ("gaps", ["examples/trace/project_radar_hydrogen_trace.yaml", "--pretty"]),
        ("report", ["examples/trace/project_radar_hydrogen_trace.yaml", "--format", "markdown"]),
        ("evaluate", ["examples/trace/incident_response_storyline.yaml", "--pretty"]),
        ("validate", ["examples/trace/operation_before_tender_contradiction.yaml"]),
        ("diagnose", ["examples/trace/operation_before_tender_contradiction.yaml", "--pretty"]),
    ],
)
def test_cli_smoke_commands(subcommand: str, args: list[str]) -> None:
    completed = subprocess.run([sys.executable, "-m", "researchguard", "trace", subcommand, *args], cwd=ROOT, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_cli_create_and_simulate(tmp_path: Path) -> None:
    starter = tmp_path / "starter.yaml"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "researchguard", "trace",
            "create",
            "--output",
            str(starter),
            "--purpose-contract",
            str(EXAMPLES / "project_radar_task_purpose.json"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert load_model(starter).metadata["skill"] == "TraceGuard"
    validated = subprocess.run(
        [
            sys.executable,
            "-m",
            "researchguard", "trace",
            "validate",
            str(starter),
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    validation_payload = json.loads(validated.stdout)
    assert validation_payload["schema_ok"] is True
    assert validation_payload["inference_status"] == "NOT_RUN_EMPTY_MODEL"
    completed = subprocess.run([sys.executable, "-m", "researchguard", "trace", "simulate", "--mode", "storyline", "--pretty"], cwd=ROOT, text=True, capture_output=True, check=True)
    payload = json.loads(completed.stdout)
    assert payload["pipeline"][0] == "source"
    assert "storyline" in payload["pipeline"]


def test_cli_model_backed_simulations_and_compare(tmp_path: Path) -> None:
    for mode in ["evidence-removal", "contradiction-injection"]:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "researchguard", "trace",
                "simulate",
                "--mode",
                mode,
                "--model",
                "examples/trace/project_radar_hydrogen_trace.yaml",
                "--pretty",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(completed.stdout)
        assert payload["mode"] == mode
        assert payload["before"]["trace_statuses"]
        assert payload["after"]["trace_statuses"]
        assert "original model file was not changed" in payload["boundary"]

    data = yaml.safe_load(example("project_radar_hydrogen_trace.yaml").read_text(encoding="utf-8"))
    data["events"][0]["evidence_ids"] = []
    after = tmp_path / "after.yaml"
    after.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "researchguard", "trace",
            "compare",
            "examples/trace/project_radar_hydrogen_trace.yaml",
            str(after),
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["diagnostic_count_delta"] >= 1
    assert payload["trace_delta"]["changed"]
    assert "not a new factual source" in payload["boundary"]


def test_all_examples_are_loadable_and_cli_validates() -> None:
    for path in EXAMPLES.glob("*.yaml"):
        load_model(path)
        completed = subprocess.run([sys.executable, "-m", "researchguard", "trace", "validate", str(path)], cwd=ROOT, text=True, capture_output=True)
        assert completed.returncode == 0, path.name


def test_case_library_example_validates_and_builds_model(tmp_path: Path) -> None:
    root = copy_case_library(tmp_path)
    validation = case_library.validate_library(root)
    assert validation["ok"]
    assert validation["case_count"] == 1

    model_path = tmp_path / "metadata_trace.yaml"
    built = case_library.write_model(
        root,
        "metadata-api-incident",
        model_path,
        purpose_contract=EXAMPLES / "project_radar_task_purpose.json",
    )
    assert built["metadata"]["case_id"] == "metadata-api-incident"
    assert built["metadata"]["directions"] == ["root-cause"]
    assert built["metadata"]["guard_purpose_contract"]["contract_fingerprint"]

    result = evaluate_model(load_model(model_path))
    assert result.traces[0].trace_id == "trace_metadata_incident"
    assert result.traces[0].validation_status == "validated"


def test_case_library_create_persist_search_and_gap_writeback(tmp_path: Path) -> None:
    root = tmp_path / "library"
    case_library.init_library(root, name="Investigation Memory")
    case_library.create_case(root, "Incident A", title="Incident A", topic="metadata")
    case_library.create_direction(root, "incident-a", "Root Cause", title="Root Cause", question="What broke?", search_terms=["cache"])
    case_library.add_source(root, "incident-a", "root-cause", source_id="Issue 7", title="Issue 7", source_type="issue", reliability=0.8)
    evidence = case_library.add_evidence(
        root,
        "incident-a",
        "root-cause",
        evidence_id="Cache Note",
        source_id="issue-7",
        raw_text="Cache invalidation caused stale metadata reads.",
        evidence_type="issue_note",
        summary="Cache invalidation suspected.",
        confidence=0.82,
        specificity=0.79,
        limits=["needs log corroboration"],
    )
    assert evidence["evidence_id"] == "cache-note"

    directions = case_library.list_directions(root, "incident-a")
    assert directions[0]["direction_id"] == "root-cause"
    assert case_library.validate_library(root)["ok"]
    matches = case_library.search_library(root, "stale metadata", case_id="incident-a")
    assert any(match["path"].endswith("evidence.yaml") for match in matches)

    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "gaps": [{"message": "Need customer impact evidence."}],
                "contradictions": [{"message": "Issue and log disagree on start time."}],
                "traces": [{"trace_id": "trace_a", "gaps": [{"gap_id": "missing_resolution", "message": "Need resolution proof."}]}],
            }
        ),
        encoding="utf-8",
    )
    payload = case_library.write_back_gaps(root, "incident-a", result_path)
    assert payload == {
        "ok": True,
        "gaps_written": 2,
        "contradictions_written": 1,
        "inference_receipt_written": False,
    }

    paths = case_library.LibraryPaths(root)
    gaps = case_library.read_yaml(paths.case_ledger("incident-a", "gaps.yaml"), [])
    contradictions = case_library.read_yaml(paths.case_ledger("incident-a", "contradictions.yaml"), [])
    assert {gap["gap_id"] for gap in gaps} == {"gap_1", "missing_resolution"}
    assert contradictions[0]["contradiction_id"] == "contradiction_1"


def test_case_library_writeback_preserves_handoff_followups(tmp_path: Path) -> None:
    root = tmp_path / "library"
    case_library.init_library(root, name="Investigation Memory")
    case_library.create_case(root, "Incident A", title="Incident A", topic="metadata")
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "handoffs": [
                    {
                        "trace_id": "trace_a",
                        "lead_id": "lead_trace_a",
                        "missing_evidence": ["missing_resolution: Need resolution proof."],
                        "next_search_task": "Find release notes.",
                    }
                ],
                "consolidation_findings": [
                    {
                        "finding_id": "same_class_overclaim:trace_a:patent",
                        "finding_type": "patent_deployment_review",
                        "message": "Review sibling deployment claims.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    payload = case_library.write_back_gaps(root, "incident-a", result_path)
    assert payload == {
        "ok": True,
        "gaps_written": 2,
        "contradictions_written": 0,
        "inference_receipt_written": False,
    }
    paths = case_library.LibraryPaths(root)
    gaps = case_library.read_yaml(paths.case_ledger("incident-a", "gaps.yaml"), [])
    assert {gap["gap_id"] for gap in gaps} == {
        "lead_trace_a:missing_evidence:1",
        "same_class_overclaim:trace_a:patent",
    }


def test_case_library_records_inference_receipts_as_observations_only(
    tmp_path: Path,
) -> None:
    root = tmp_path / "library"
    case_library.init_library(root, name="Investigation Memory")
    case_library.create_case(root, "Incident A", title="Incident A")
    result = evaluate_model(
        load_model(example("incident_response_storyline.yaml")),
        include_storyline_depth=False,
    )
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(result.to_dict()), encoding="utf-8")

    payload = case_library.write_back_gaps(root, "incident-a", result_path)
    assert payload["inference_receipt_written"] is True
    paths = case_library.require_library(root)
    saved = case_library.read_yaml(
        paths.case_ledger("incident-a", "inference_receipts.yaml"),
        [],
    )
    assert saved[0]["record_kind"] == "inference_observation"
    assert saved[0]["solver_id"] == "osqp.direct.v1"
    assert saved[0]["trace_projections"]


def test_case_library_rejects_missing_direction_source_write(tmp_path: Path) -> None:
    root = tmp_path / "library"
    case_library.init_library(root)
    case_library.create_case(root, "incident-a", title="Incident A")
    with pytest.raises(case_library.LibraryError, match="direction does not exist"):
        case_library.add_source(root, "incident-a", "missing", source_id="src", title="Missing direction")


def test_cli_library_smoke_commands(tmp_path: Path) -> None:
    model_path = tmp_path / "built_from_library.yaml"
    validate = subprocess.run(
        [sys.executable, "-m", "researchguard", "trace", "library", "validate", "examples/trace/case_library", "--pretty"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(validate.stdout)["ok"]

    list_cases = subprocess.run(
        [sys.executable, "-m", "researchguard", "trace", "library", "list", "examples/trace/case_library", "--pretty"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(list_cases.stdout)["cases"][0]["case_id"] == "metadata-api-incident"

    search = subprocess.run(
        [sys.executable, "-m", "researchguard", "trace", "library", "search", "examples/trace/case_library", "cache", "--pretty"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(search.stdout)["matches"]

    subprocess.run(
        [
            sys.executable,
            "-m",
            "researchguard", "trace",
            "library",
            "build-model",
            "examples/trace/case_library",
            "metadata-api-incident",
                "--output",
                str(model_path),
                "--purpose-contract",
                str(EXAMPLES / "project_radar_task_purpose.json"),
                "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert load_model(model_path).metadata["case_id"] == "metadata-api-incident"

    dynamic_root = tmp_path / "cli_library"
    subprocess.run([sys.executable, "-m", "researchguard", "trace", "library", "init", str(dynamic_root)], cwd=ROOT, text=True, capture_output=True, check=True)
    subprocess.run([sys.executable, "-m", "researchguard", "trace", "library", "create-case", str(dynamic_root), "case-a", "--title", "Case A"], cwd=ROOT, text=True, capture_output=True, check=True)
    subprocess.run([sys.executable, "-m", "researchguard", "trace", "library", "add-direction", str(dynamic_root), "case-a", "timeline", "--title", "Timeline"], cwd=ROOT, text=True, capture_output=True, check=True)
    subprocess.run([sys.executable, "-m", "researchguard", "trace", "library", "add-source", str(dynamic_root), "case-a", "timeline", "--source-id", "src-a", "--title", "Source A"], cwd=ROOT, text=True, capture_output=True, check=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "researchguard", "trace",
            "library",
            "add-evidence",
            str(dynamic_root),
            "case-a",
            "timeline",
            "--evidence-id",
            "ev-a",
            "--source-id",
            "src-a",
            "--text",
            "Source A says the event happened after deployment.",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    direction_payload = subprocess.run(
        [sys.executable, "-m", "researchguard", "trace", "library", "list", str(dynamic_root), "--case-id", "case-a", "--direction-id", "timeline", "--pretty"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(direction_payload.stdout)["evidence"][0]["evidence_id"] == "ev-a"
