from __future__ import annotations

import json

from researchguard.cli import main


def test_root_cli_has_only_current_public_commands(capsys) -> None:
    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "{logic|source|trace|experiment}" in output
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


def test_direct_member_request_does_not_require_task_facts(monkeypatch) -> None:
    monkeypatch.setattr("researchguard.cli._member_main", lambda member_id: lambda argv: 0)
    assert main(["experiment", "recommend", "spec.json"]) == 0
