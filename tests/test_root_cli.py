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


def test_retired_standalone_routes_are_unknown_commands(capsys, tmp_path) -> None:
    assert main(["portable", "bundle.json"]) == 2
    portable = json.loads(capsys.readouterr().out)
    assert portable["code"] == "unknown-command"
    assert main(["domain-dna", "inspect", "bundle.json"]) == 2
    domain_dna = json.loads(capsys.readouterr().out)
    assert domain_dna["code"] == "unknown-command"
    invalid = tmp_path / "invalid-source.yaml"
    invalid.write_text("gaps: [{gap_id: bad, status: open}]\n", encoding="utf-8")
    assert main(["source", "validate", str(invalid)]) == 2
    failure = json.loads(capsys.readouterr().err)
    assert failure["ok"] is False
    assert "gap.status is retired" in failure["error"]


def test_direct_member_request_does_not_require_task_facts(tmp_path, capsys) -> None:
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({
        "hypothesis_predictions": [
            {"hypothesis_id": "h1", "outcomes_by_experiment": {"e1": "up"}},
            {"hypothesis_id": "h2", "outcomes_by_experiment": {"e1": "down"}},
        ],
        "candidate_experiment_ids": ["e1"],
    }), encoding="utf-8")
    assert main(["experiment", "recommend", str(spec)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "recommended"
    assert result["selected_experiment_ids"] == ["e1"]
