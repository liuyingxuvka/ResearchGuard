from __future__ import annotations

import json

from researchguard.cli import main


def test_root_cli_has_exact_four_commands(capsys) -> None:
    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "{run|logic|source|trace}" in output


def test_umbrella_without_member_returns_typed_gap(capsys) -> None:
    assert main(["run"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "blocked"
    assert payload["code"] == "member-selection-required"


def test_umbrella_reentry_is_terminal(capsys) -> None:
    assert (
        main(
            [
                "run",
                "--member",
                "logicguard",
                "--active-request-id",
                "request:already-routed",
                "--",
                "--help",
            ]
        )
        == 2
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["code"] == "researchguard-recursion"
