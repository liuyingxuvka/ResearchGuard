from __future__ import annotations

import json
from pathlib import Path

from admission_fixtures import composition, member_task_facts, task_facts
from researchguard.cli import main


def test_root_cli_has_exact_five_commands(capsys) -> None:
    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "{run|logic|source|trace|experiment}" in output


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
    assert main(
        [
            "run",
            "--business-intent-id",
            intent,
            "--task-facts",
            str(facts_path),
            "--",
            *member_argv,
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "composition_ready"
    assert payload["member_ids"] == ["sourceguard", "traceguard"]
