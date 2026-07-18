#!/usr/bin/env python
"""Wrap LogicGuard CLI checks in a Guard-family closure report."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, text=True, capture_output=True)
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return value


def _finding(severity: str, kind: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"severity": severity, "type": kind, "message": message, **extra}


def check(args: argparse.Namespace) -> dict[str, Any]:
    ledger = _load_json(args.ledger)
    checked_inputs: list[dict[str, str]] = []
    findings: list[dict[str, Any]] = []
    missing_inputs: list[dict[str, str]] = []
    stale_evidence: list[dict[str, str]] = []
    skipped_checks: list[dict[str, str]] = []
    command_results: list[dict[str, Any]] = []

    if args.model is None:
        missing_inputs.append({"field": "model", "message": "No LogicGuard model was provided."})
    else:
        checked_inputs.append({"check": "logicguard_model", "path": str(args.model)})
        commands = [
            [sys.executable, "-m", "logicguard", "validate", str(args.model)],
            [sys.executable, "-m", "logicguard", "evaluate", str(args.model)],
            [sys.executable, "-m", "logicguard", "diagnose", str(args.model)],
            [sys.executable, "-m", "logicguard", "gaps", str(args.model)],
        ]
        for command in commands:
            result = _run(command)
            command_results.append(result)
            if result["returncode"] != 0:
                findings.append(_finding("error", "logicguard_command_failed", f"Command failed: {result['command']}", command=result["command"]))

    if args.structure_model:
        checked_inputs.append({"check": "logicguard_structure_audit", "path": str(args.structure_model)})
        result = _run([sys.executable, "-m", "logicguard", "structure", "audit", str(args.structure_model)])
        command_results.append(result)
        if result["returncode"] != 0:
            findings.append(_finding("error", "structure_audit_failed", "LogicGuard structure audit failed.", command=result["command"]))

    if args.citation_model:
        checked_inputs.append({"check": "logicguard_citation_audit", "path": str(args.citation_model)})
        result = _run([sys.executable, "-m", "logicguard", "citation", "audit", str(args.citation_model)])
        command_results.append(result)
        if result["returncode"] != 0:
            findings.append(_finding("error", "citation_audit_failed", "LogicGuard citation audit failed.", command=result["command"]))

    for field in ("model_card_coverage", "high_importance_open_gaps", "postwrite_status"):
        if field not in ledger:
            missing_inputs.append({"field": field, "message": f"LogicGuard closure ledger is missing {field}."})

    if str(ledger.get("postwrite_status", "")).lower() in {"stale_after_edit", "changed_after_audit", "not_run"}:
        stale_evidence.append({"field": "postwrite_status", "message": "Final prose changed after LogicGuard audit or postwrite audit was not run."})

    gaps = ledger.get("high_importance_open_gaps", [])
    if isinstance(gaps, list) and gaps:
        findings.append(_finding("warning", "high_importance_gaps_open", "High-importance LogicGuard gaps remain open.", count=len(gaps)))

    for item in ledger.get("skipped_checks", []) if isinstance(ledger.get("skipped_checks"), list) else []:
        skipped_checks.append({"check": str(item), "message": "LogicGuard ledger records a skipped check."})

    if missing_inputs:
        findings.append(_finding("warning", "logicguard_ledger_missing_fields", "LogicGuard closure ledger is incomplete.", count=len(missing_inputs)))
    if stale_evidence:
        findings.append(_finding("error", "stale_logicguard_evidence", "LogicGuard closure evidence is stale.", count=len(stale_evidence)))

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
    if missing_inputs:
        next_actions.append({"owner": "logicguard", "action": "create_or_update_closure_ledger"})
    if args.model is None:
        next_actions.append({"owner": "logicguard", "action": "build_or_select_argument_model"})
    if any(item.get("type") == "high_importance_gaps_open" for item in findings):
        next_actions.append({"owner": "logicguard.route.model-deepening", "action": "deepen_or_terminally_classify_high_importance_gaps"})
    if stale_evidence:
        next_actions.append({"owner": "logicguard", "action": "rerun_postwrite_claim_audit"})

    return {
        "owner_guard": "logicguard",
        "artifact_kind": "logicguard_closure",
        "closure_status": closure_status,
        "checked_inputs": checked_inputs,
        "findings": findings,
        "missing_inputs": missing_inputs,
        "stale_evidence": stale_evidence,
        "skipped_checks": skipped_checks,
        "next_actions": next_actions,
        "safe_claim": ledger.get("safe_claim", "LogicGuard support is limited to the current model, structure, citation, and postwrite evidence."),
        "unsafe_claim_boundary": ledger.get("unsafe_claim_boundary", "Do not claim final reasoning closure when the model, gap ledger, citation audit, or postwrite audit is missing or stale."),
        "command_results": command_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run LogicGuard closure checks.")
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--structure-model", type=Path)
    parser.add_argument("--citation-model", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = check(args)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['closure_status'].upper()}: LogicGuard closure")
        for finding in result["findings"]:
            print(f"- {finding.get('severity', 'warning')}: {finding.get('type', '')}".rstrip())
    return 0 if result["closure_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
