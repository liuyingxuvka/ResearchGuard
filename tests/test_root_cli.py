from __future__ import annotations

import json
from pathlib import Path

from researchguard.cli import main
from researchguard.experiment.admission import author_admission_evidence as experiment_evidence
from researchguard.logic.admission import author_admission_evidence as logic_evidence
from researchguard.routing import ADMISSION_SET_SCHEMA, request_fingerprint
from researchguard.source.admission import author_admission_evidence as source_evidence
from researchguard.trace.admission import author_admission_evidence as trace_evidence


def test_root_cli_has_exact_five_commands(capsys) -> None:
    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "{run|logic|source|trace|experiment}" in output


def test_umbrella_without_member_returns_typed_gap(capsys) -> None:
    assert main(["run"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "blocked"
    assert payload["code"] == "member-admission-required"


def _write_admission(path: Path, *, argv: list[str], intent: str) -> None:
    digest = request_fingerprint(argv, business_intent_id=intent)
    builders = {
        "logicguard": logic_evidence,
        "sourceguard": source_evidence,
        "traceguard": trace_evidence,
        "experimentguard": experiment_evidence,
    }
    payload = {
        "schema_version": ADMISSION_SET_SCHEMA,
        "member_evidence": [
            builder(
                request_fingerprint=digest,
                applicability=(
                    "applicable" if member == "logicguard" else "not_applicable"
                ),
                forbidden_status="clear",
                applicability_evidence_refs=(f"native:{member}:applicability",),
                forbidden_evidence_refs=(f"native:{member}:forbidden-review",),
            )
            for member, builder in builders.items()
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_umbrella_reentry_is_terminal(tmp_path, capsys) -> None:
    evidence = tmp_path / "admission.json"
    member_argv = ["--help"]
    intent = "intent:test:logic"
    _write_admission(evidence, argv=member_argv, intent=intent)
    assert main(
        [
            "run",
            "--business-intent-id",
            intent,
            "--admission-evidence",
            str(evidence),
            "--active-request-id",
            "request:already-routed",
            "--",
            *member_argv,
        ]
    ) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["code"] == "researchguard-recursion"


def test_retired_member_selector_is_rejected(capsys) -> None:
    assert main(["run", "--member", "logicguard", "--", "--help"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["code"] == "unknown-umbrella-option"
