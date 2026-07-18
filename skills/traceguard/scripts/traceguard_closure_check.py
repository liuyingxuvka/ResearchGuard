#!/usr/bin/env python
"""Wrap TraceGuard CLI checks in a Guard-family closure report."""

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
        "_stdout_full": completed.stdout,
    }


def _finding(severity: str, kind: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"severity": severity, "type": kind, "message": message, **extra}


def _gap_rows(value: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, status in value.items():
            normalized = str(status.get("status") if isinstance(status, dict) else status).lower().replace("-", "_").replace(" ", "_")
            if normalized in {"", "missing", "gap", "partial", "access_gap", "unknown", "not_run", "overclaim"}:
                rows.append({"item": str(key), "status": normalized or "missing"})
    elif isinstance(value, list):
        for index, item in enumerate(value, 1):
            if isinstance(item, dict):
                key = item.get("trace_id") or item.get("layer") or item.get("lead") or f"row_{index}"
                normalized = str(item.get("status") or item.get("coverage") or "").lower().replace("-", "_").replace(" ", "_")
                if normalized in {"", "missing", "gap", "partial", "access_gap", "unknown", "not_run", "overclaim"}:
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
        missing_inputs.append({"field": "model", "message": "No TraceGuard model was provided."})
    else:
        checked_inputs.append({"check": "traceguard_model", "path": str(args.model)})
        for command in (
            [sys.executable, "-m", "traceguard", "validate", str(args.model)],
            [sys.executable, "-m", "traceguard", "evaluate", str(args.model), "--pretty"],
            [sys.executable, "-m", "traceguard", "depth", str(args.model), "--pretty"],
            [sys.executable, "-m", "traceguard", "diagnose", str(args.model), "--pretty"],
            [sys.executable, "-m", "traceguard", "gaps", str(args.model), "--pretty"],
            [sys.executable, "-m", "traceguard", "report", str(args.model), "--format", "json"],
        ):
            result = _run(command)
            full_stdout = result.pop("_stdout_full", result["stdout"])
            command_results.append(result)
            if result["returncode"] != 0:
                findings.append(_finding("error", "traceguard_command_failed", f"Command failed: {result['command']}", command=result["command"]))
            elif " traceguard depth " in f" {result['command']} ":
                try:
                    receipt = json.loads(full_stdout)
                except json.JSONDecodeError:
                    findings.append(
                        _finding(
                            "error",
                            "storyline_depth_receipt_invalid",
                            "TraceGuard depth command did not emit a parseable native receipt.",
                        )
                    )
                else:
                    required = {
                        "receipt_id",
                        "model_fingerprint",
                        "baseline",
                        "hypotheses",
                        "alternatives",
                        "perturbation_plan",
                        "effects",
                        "unresolved_gaps",
                        "closure_status",
                        "claim_boundary",
                    }
                    missing = sorted(required.difference(receipt))
                    if missing:
                        findings.append(
                            _finding(
                                "error",
                                "storyline_depth_receipt_missing_fields",
                                "Native TraceGuard depth receipt is incomplete.",
                                missing=missing,
                            )
                        )
                    else:
                        checked_inputs.append(
                            {
                                "check": "native_storyline_depth_receipt",
                                "path": str(receipt.get("receipt_id", "")),
                            }
                        )
                        depth_status = str(receipt.get("closure_status", "")).upper()
                        if depth_status == "BLOCKED":
                            findings.append(
                                _finding(
                                    "error",
                                    "storyline_depth_blocked",
                                    "Native TraceGuard storyline-depth closure is blocked.",
                                    gaps=receipt.get("unresolved_gaps", []),
                                )
                            )
                        elif depth_status != "PASS":
                            findings.append(
                                _finding(
                                    "warning",
                                    "storyline_depth_incomplete",
                                    "Native TraceGuard storyline-depth closure is incomplete.",
                                    status=depth_status or "UNKNOWN",
                                    gaps=receipt.get("unresolved_gaps", []),
                                )
                            )

    for field in ("trace_layer_coverage", "weakest_link", "safe_wording", "downstream_handoff"):
        if field not in ledger:
            missing_inputs.append({"field": field, "message": f"TraceGuard closure ledger is missing {field}."})

    open_layers = _gap_rows(ledger.get("trace_layer_coverage"))
    if open_layers:
        findings.append(_finding("warning", "trace_layers_open", "Trace layer coverage has missing or partial rows.", rows=open_layers, count=len(open_layers)))

    if str(ledger.get("single_storyline_only", "")).lower() in {"true", "yes", "1"} and str(ledger.get("competing_storylines_checked", "")).lower() not in {"true", "yes", "1"}:
        findings.append(_finding("warning", "single_storyline_without_competition_check", "Only one storyline is recorded and competing alternatives were not checked."))

    if str(ledger.get("safe_wording", "")).strip() == "":
        findings.append(_finding("warning", "safe_wording_missing", "TraceGuard safe wording is missing."))

    if str(ledger.get("final_claim_changed_after_trace_review", "")).lower() in {"true", "yes", "1"}:
        stale_evidence.append({"field": "final_claim_changed_after_trace_review", "message": "Final claim changed after TraceGuard review."})

    for item in ledger.get("skipped_checks", []) if isinstance(ledger.get("skipped_checks"), list) else []:
        skipped_checks.append({"check": str(item), "message": "TraceGuard ledger records a skipped check."})

    if missing_inputs:
        findings.append(_finding("warning", "traceguard_ledger_missing_fields", "TraceGuard closure ledger is incomplete.", count=len(missing_inputs)))
    if stale_evidence:
        findings.append(_finding("error", "stale_traceguard_evidence", "TraceGuard evidence is stale.", count=len(stale_evidence)))

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
        next_actions.append({"owner": "traceguard", "action": "build_or_select_traceguard_model"})
    if open_layers:
        next_actions.append({"owner": "traceguard", "action": "fill_or_downgrade_missing_trace_layers"})
    if stale_evidence:
        next_actions.append({"owner": "flowguard", "action": "rerun_trace_review_after_claim_change"})

    return {
        "owner_guard": "traceguard",
        "artifact_kind": "traceguard_closure",
        "closure_status": closure_status,
        "checked_inputs": checked_inputs,
        "findings": findings,
        "missing_inputs": missing_inputs,
        "stale_evidence": stale_evidence,
        "skipped_checks": skipped_checks,
        "next_actions": next_actions,
        "safe_claim": ledger.get("safe_claim", "TraceGuard can support only the trace layers currently modeled and evaluated."),
        "unsafe_claim_boundary": ledger.get("unsafe_claim_boundary", "Do not turn event facts, chronology, announcements, or one clean storyline into outcome, causality, or final argument proof."),
        "command_results": command_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run TraceGuard closure checks.")
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = check(args)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['closure_status'].upper()}: TraceGuard closure")
        for finding in result["findings"]:
            print(f"- {finding.get('severity', 'warning')}: {finding.get('type', '')}".rstrip())
    return 0 if result["closure_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
