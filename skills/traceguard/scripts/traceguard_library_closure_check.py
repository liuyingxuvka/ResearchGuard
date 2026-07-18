#!/usr/bin/env python
"""Check TraceGuard case-library closure state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


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
    findings: list[dict[str, Any]] = []
    missing_inputs: list[dict[str, str]] = []
    stale_evidence: list[dict[str, str]] = []
    skipped_checks: list[dict[str, str]] = []

    required = (
        "case_sources_saved",
        "lead_map_status",
        "model_built",
        "evaluation_status",
        "gaps_written_back",
    )
    for field in required:
        if field not in ledger:
            missing_inputs.append({"field": field, "message": f"TraceGuard case-library ledger is missing {field}."})

    if ledger.get("case_sources_saved") is False:
        findings.append(_finding("error", "sources_not_saved", "Case sources are not recorded as saved."))
    if ledger.get("model_built") is False:
        findings.append(_finding("warning", "model_not_built", "Case material was saved but no TraceGuard model is recorded."))
    if str(ledger.get("evaluation_status", "")).lower() in {"", "not_run", "failed", "stale"}:
        findings.append(_finding("warning", "evaluation_not_current", "TraceGuard case evaluation is missing, failed, or stale."))
    if ledger.get("gaps_written_back") is False:
        findings.append(_finding("warning", "gaps_not_written_back", "Evaluation gaps were not written back to the case library."))
    if str(ledger.get("case_material_changed_after_evaluation", "")).lower() in {"true", "yes", "1"}:
        stale_evidence.append({"field": "case_material_changed_after_evaluation", "message": "Case material changed after evaluation."})

    for item in ledger.get("skipped_checks", []) if isinstance(ledger.get("skipped_checks"), list) else []:
        skipped_checks.append({"check": str(item), "message": "TraceGuard library ledger records a skipped check."})

    if missing_inputs:
        findings.append(_finding("warning", "traceguard_library_ledger_missing_fields", "TraceGuard case-library closure ledger is incomplete.", count=len(missing_inputs)))
    if stale_evidence:
        findings.append(_finding("error", "stale_traceguard_library_evidence", "TraceGuard case-library evidence is stale.", count=len(stale_evidence)))

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
    if any(item.get("type") == "model_not_built" for item in findings):
        next_actions.append({"owner": "traceguard.case-library", "action": "build_traceguard_model_from_case_material"})
    if any(item.get("type") == "evaluation_not_current" for item in findings):
        next_actions.append({"owner": "traceguard", "action": "evaluate_case_model"})
    if any(item.get("type") == "gaps_not_written_back" for item in findings):
        next_actions.append({"owner": "traceguard.case-library", "action": "write_gaps_back_to_case_library"})
    if stale_evidence:
        next_actions.append({"owner": "flowguard", "action": "rerun_case_evaluation_after_material_change"})

    return {
        "owner_guard": "traceguard.case-library",
        "artifact_kind": "traceguard_case_library_closure",
        "closure_status": closure_status,
        "checked_inputs": [{"check": "case_library_ledger", "path": str(args.ledger)}] if args.ledger else [],
        "findings": findings,
        "missing_inputs": missing_inputs,
        "stale_evidence": stale_evidence,
        "skipped_checks": skipped_checks,
        "next_actions": next_actions,
        "safe_claim": ledger.get("safe_claim", "TraceGuard case library closure covers saved investigation state, not final argument proof."),
        "unsafe_claim_boundary": ledger.get("unsafe_claim_boundary", "Do not treat saved sources or notes as evaluated trace evidence until model, evaluation, and gap write-back are current."),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run TraceGuard case-library closure checks.")
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = check(args)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['closure_status'].upper()}: TraceGuard case-library closure")
        for finding in result["findings"]:
            print(f"- {finding.get('severity', 'warning')}: {finding.get('type', '')}".rstrip())
    return 0 if result["closure_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
