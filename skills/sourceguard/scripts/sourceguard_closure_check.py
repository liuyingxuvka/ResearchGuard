#!/usr/bin/env python
"""Wrap SourceGuard checks in a Guard-family closure report."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return value


def _run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, text=True, capture_output=True)
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def _finding(severity: str, kind: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"severity": severity, "type": kind, "message": message, **extra}


def _open_statuses(mapping: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if isinstance(mapping, dict):
        for key, value in mapping.items():
            status = value.get("status") if isinstance(value, dict) else value
            normalized = str(status or "").lower().replace("-", "_").replace(" ", "_")
            if normalized in {"", "gap", "blocked", "access_gap", "not_run", "missing", "unknown", "downgrade_needed"}:
                rows.append({"item": str(key), "status": normalized or "missing"})
    elif isinstance(mapping, list):
        for index, value in enumerate(mapping, 1):
            if isinstance(value, dict):
                key = value.get("source_role") or value.get("source_class") or value.get("gap_id") or f"row_{index}"
                normalized = str(value.get("status") or "").lower().replace("-", "_").replace(" ", "_")
                if normalized in {"", "gap", "blocked", "access_gap", "not_run", "missing", "unknown", "downgrade_needed"}:
                    rows.append({"item": str(key), "status": normalized or "missing"})
    return rows


def check(args: argparse.Namespace) -> dict[str, Any]:
    ledger = _load_json(args.ledger)
    checked_inputs: list[dict[str, str]] = []
    findings: list[dict[str, Any]] = []
    missing_inputs: list[dict[str, str]] = []
    stale_evidence: list[dict[str, str]] = []
    skipped_checks: list[dict[str, str]] = []
    command_results: list[dict[str, Any]] = []

    if args.model is None:
        missing_inputs.append({"field": "model", "message": "No SourceGuard model was provided."})
    else:
        checked_inputs.append({"check": "sourceguard_model", "path": str(args.model)})
        for command in (
            [sys.executable, "-m", "sourceguard", "validate", str(args.model), "--pretty"],
            [sys.executable, "-m", "sourceguard", "frontier", str(args.model), "--pretty"],
            [sys.executable, "-m", "sourceguard", "report", str(args.model), "--format", "markdown"],
        ):
            result = _run(command)
            command_results.append(result)
            if result["returncode"] != 0:
                findings.append(_finding("error", "sourceguard_command_failed", f"Command failed: {result['command']}", command=result["command"]))

    required_fields = (
        "source_role_coverage",
        "source_portfolio",
        "key_number_provenance",
        "bridge_evidence_status",
    )
    for field in required_fields:
        if field not in ledger:
            missing_inputs.append({"field": field, "message": f"SourceGuard closure ledger is missing {field}."})

    for field in ("source_role_coverage", "source_portfolio", "key_number_provenance", "bridge_evidence_status"):
        open_rows = _open_statuses(ledger.get(field))
        if open_rows:
            findings.append(_finding("warning", f"{field}_open", f"{field} contains open source gaps.", count=len(open_rows), rows=open_rows))

    if str(ledger.get("candidate_handoff_status", "")).lower() in {"treated_as_validated", "promoted_without_downstream_review"}:
        findings.append(_finding("error", "candidate_handoff_overclaim", "Candidate handoff is being treated as downstream validation."))

    if str(ledger.get("final_draft_changed_after_source_review", "")).lower() in {"true", "yes", "1"}:
        stale_evidence.append({"field": "final_draft_changed_after_source_review", "message": "Final draft changed after SourceGuard review."})

    for item in ledger.get("skipped_checks", []) if isinstance(ledger.get("skipped_checks"), list) else []:
        skipped_checks.append({"check": str(item), "message": "SourceGuard ledger records a skipped check."})

    if missing_inputs:
        findings.append(_finding("warning", "sourceguard_ledger_missing_fields", "SourceGuard closure ledger is incomplete.", count=len(missing_inputs)))
    if stale_evidence:
        findings.append(_finding("error", "stale_sourceguard_evidence", "SourceGuard evidence is stale.", count=len(stale_evidence)))

    hard = any(str(item.get("severity", "")).lower() in {"error", "blocker"} for item in findings)
    declared = str(ledger.get("closure_status", "")).lower()
    if hard:
        closure_status = "blocked"
    elif declared in {"passed", "partial", "blocked", "downgraded"}:
        closure_status = declared
    elif findings or missing_inputs:
        closure_status = "partial"
    else:
        closure_status = "passed"

    next_actions = []
    if args.model is None:
        next_actions.append({"owner": "sourceguard", "action": "build_or_select_sourceguard_belief_state"})
    if any(str(item.get("type", "")).endswith("_open") for item in findings):
        next_actions.append({"owner": "sourceguard", "action": "run_targeted_search_or_downgrade_claim_strength"})
    if stale_evidence:
        next_actions.append({"owner": "flowguard", "action": "rerun_source_review_after_final_draft_change"})

    return {
        "owner_guard": "sourceguard",
        "artifact_kind": "sourceguard_closure",
        "closure_status": closure_status,
        "checked_inputs": checked_inputs,
        "findings": findings,
        "missing_inputs": missing_inputs,
        "stale_evidence": stale_evidence,
        "skipped_checks": skipped_checks,
        "next_actions": next_actions,
        "safe_claim": ledger.get("safe_claim", "SourceGuard can rank and record source-discovery coverage, not final proof."),
        "unsafe_claim_boundary": ledger.get("unsafe_claim_boundary", "Do not treat source candidates, search hits, or utility scores as validated evidence."),
        "command_results": command_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SourceGuard closure checks.")
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = check(args)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['closure_status'].upper()}: SourceGuard closure")
        for finding in result["findings"]:
            print(f"- {finding.get('severity', 'warning')}: {finding.get('type', '')}".rstrip())
    return 0 if result["closure_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
