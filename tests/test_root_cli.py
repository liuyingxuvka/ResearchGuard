from __future__ import annotations

import json
from pathlib import Path

from admission_fixtures import (
    composition,
    member_task_facts,
    native_owner_attestations,
    task_facts,
)
from researchguard.cli import main


def test_root_cli_has_only_current_public_commands(capsys) -> None:
    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "{run|self-dna|logic|source|trace|experiment}" in output
    assert "portable" not in output
    assert "domain-dna" not in output
    assert "self-dna export" not in output


def test_retired_standalone_routes_are_unknown_commands(capsys) -> None:
    assert main(["portable", "bundle.json"]) == 2
    portable = json.loads(capsys.readouterr().out)
    assert portable["code"] == "unknown-command"
    assert main(["domain-dna", "inspect", "bundle.json"]) == 2
    domain_dna = json.loads(capsys.readouterr().out)
    assert domain_dna["code"] == "unknown-command"


def test_self_dna_export_is_retired_without_materialization(capsys) -> None:
    assert main(["self-dna", "export", "--output", "outside.json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["gap"]["code"] == "unknown-self-dna-operation"


def test_umbrella_without_task_facts_returns_typed_gap(capsys) -> None:
    assert main(["run"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["code"] == "member-admission-required"


def _write_task_facts(path: Path, *, argv: list[str], intent: str) -> None:
    path.write_text(
        json.dumps(member_task_facts("logicguard", argv=argv, intent=intent)),
        encoding="utf-8",
    )


def test_umbrella_reentry_is_terminal(tmp_path, capsys) -> None:
    facts_path = tmp_path / "task-facts.json"
    member_argv = ["--help"]
    intent = "intent:test:logic"
    _write_task_facts(facts_path, argv=member_argv, intent=intent)
    assert main(
        [
            "run",
            "--business-intent-id",
            intent,
            "--task-facts",
            str(facts_path),
            "--active-request-id",
            "request:already-routed",
            "--",
            *member_argv,
        ]
    ) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["code"] == "researchguard-recursion"


def test_retired_admission_evidence_option_is_rejected(capsys) -> None:
    assert main(["run", "--admission-evidence", "old.json", "--", "--help"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["code"] == "unknown-umbrella-option"


def test_direct_member_request_does_not_require_task_facts(monkeypatch) -> None:
    monkeypatch.setattr("researchguard.cli._member_main", lambda member_id: lambda argv: 0)
    assert main(["experiment", "recommend", "spec.json"]) == 0


def test_umbrella_emits_composition_without_claiming_member_execution(tmp_path, capsys) -> None:
    facts_path = tmp_path / "task-facts.json"
    attestations_path = tmp_path / "native-owner-attestations.json"
    member_argv = ["plan", "mixed-task.json"]
    intent = "intent:source-then-trace"
    plan = composition(
        ("sourceguard", ("source.primary.discovery",)),
        ("traceguard", ("trace.primary.reconstruction",)),
    )
    facts_path.write_text(
        json.dumps(
            task_facts(
                argv=member_argv,
                intent=intent,
                primary_kind="source.primary_discovery",
                additional_primary_kinds=("trace.temporal_reconstruction",),
                composition=plan,
            )
        ),
        encoding="utf-8",
    )
    attestations_path.write_text(
        json.dumps(native_owner_attestations(plan)), encoding="utf-8"
    )
    assert main(
        [
            "run",
            "--business-intent-id",
            intent,
            "--task-facts",
            str(facts_path),
            "--native-owner-attestations",
            str(attestations_path),
            "--",
            *member_argv,
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "composition_ready"
    assert payload["member_ids"] == ["sourceguard", "traceguard"]
    assert all("opaque_payload_b64" not in item for item in payload["member_envelopes"])


def test_umbrella_projects_affected_only_impact_and_receipt_boundary_trace(tmp_path, capsys) -> None:
    facts_path = tmp_path / "task-facts.json"
    attestations_path = tmp_path / "native-owner-attestations.json"
    member_argv = ["plan", "mixed-task.json"]
    intent = "intent:source-then-trace-operations"
    plan = composition(
        ("sourceguard", ("source.primary.discovery",)),
        ("traceguard", ("trace.primary.reconstruction",)),
    )
    facts_path.write_text(
        json.dumps(
            task_facts(
                argv=member_argv,
                intent=intent,
                primary_kind="source.primary_discovery",
                additional_primary_kinds=("trace.temporal_reconstruction",),
                composition=plan,
            )
        ),
        encoding="utf-8",
    )
    attestations_path.write_text(
        json.dumps(native_owner_attestations(plan)), encoding="utf-8"
    )
    common = [
        "run", "--business-intent-id", intent, "--task-facts", str(facts_path),
        "--native-owner-attestations", str(attestations_path),
    ]
    field_fingerprint = plan["handoff_field_contracts"][0]["payload_fingerprint"]
    assert main([*common, "--changed-id", field_fingerprint, "--", *member_argv]) == 0
    impact = json.loads(capsys.readouterr().out)
    assert impact["affected_step_ids"] == ["step:2:traceguard"]
    assert impact["run_all_selected"] is False

    assert main([*common, "--reverse-trace-output", "overall", "--", *member_argv]) == 0
    trace = json.loads(capsys.readouterr().out)
    assert trace["payload_interpreted"] is False
    assert {item["trace_stops_at"] for item in trace["steps"]} == {"native_receipt_boundary"}

    assert main(
        [*common, "--changed-id", field_fingerprint, "--changed-id", "foreign:unowned", "--", *member_argv]
    ) == 3
    blocked = json.loads(capsys.readouterr().out)
    assert blocked["partial_result_suppressed"] is True
    assert blocked["affected_step_ids"] == []
