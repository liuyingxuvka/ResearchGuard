"""Read-only current FlowGuard map and native ResearchGuard DNA check.

The living map owns repository structure. The existing native software-DNA
contract owns its model/code/test/resource indexes. This command reports their
static currentness; executable model and pytest results remain separate.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any


REPORT_KIND = "researchguard.flowguard_software_self_dna_report.v1"
LAYER_IDS = (
    "evidence_qualification",
    "implementation_inventory",
    "traceability",
    "independent_semantics",
    "model_code_test_binding",
    "resource_oracle_binding",
    "static_blueprint_readiness",
)


def _package_identity() -> dict[str, str]:
    try:
        version = importlib.metadata.version("flowguard")
    except importlib.metadata.PackageNotFoundError:
        version = "unavailable"
    try:
        import flowguard

        return {
            "package": "flowguard",
            "version": version,
            "schema_version": "flowguard.map.v1",
            "module": str(Path(flowguard.__file__).resolve()),
        }
    except (ImportError, AttributeError) as exc:
        return {
            "package": "flowguard",
            "version": version,
            "schema_version": "unavailable",
            "module": "unavailable",
            "import_error": f"{type(exc).__name__}: {exc}",
        }


def _empty_layers(*, status: str = "not_run", gap: str = "") -> list[dict[str, Any]]:
    return [
        {
            "layer": layer,
            "status": status,
            "gap": gap if index == 0 and gap else "",
        }
        for index, layer in enumerate(LAYER_IDS)
    ]


def _blocked(
    root: Path,
    code: str,
    message: str,
    *,
    exc: Exception | None = None,
    software_dna: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "report_kind": REPORT_KIND,
        "software_id": "researchguard",
        "target_kind": "software",
        "status": "blocked",
        "ok": False,
        "root": str(root),
        "claim_boundary": (
            "ResearchGuard software self-DNA is claimed only inside the exact "
            "repository boundary and only by the current FlowGuard provider."
        ),
        "flowguard": _package_identity(),
        "readiness": {
            "layers": _empty_layers(status="blocked", gap=code),
            "deepest_proven_layer": "",
            "first_gap": code,
            "gap_count": 1,
        },
        "gap": {"code": code, "message": message},
        "dna_qualification": {
            "status": "blocked",
            "qualified": False,
            "reasons": [code],
        },
    }
    if software_dna is not None:
        payload["software_dna"] = software_dna
    if exc is not None:
        payload["gap"]["exception"] = f"{type(exc).__name__}: {exc}"
    return payload


def _run_build(root: Path) -> tuple[dict[str, Any], Any | None]:
    from .software_dna import check_software_dna_contract

    software_dna = check_software_dna_contract(root)
    if not software_dna.get("ready", False):
        return _blocked(root, "software_dna_contract_not_ready",
                        "Native model, code, test or resource bindings are incomplete.",
                        software_dna=software_dna), None
    try:
        from flowguard.map.mapfile import load_map, ignore_patterns, model_registry
        from flowguard.map.inventory import build_inventory
        from flowguard.map.check import run_check
        data = load_map(root)
        inventory = build_inventory(root, ignore_patterns(data))
        findings = run_check(root, data, inventory, strict=True)
        registry = model_registry(root, data)
    except Exception as exc:
        return _blocked(root, "flowguard_map_not_ready",
                        "Current FlowGuard map could not be checked.", exc=exc,
                        software_dna=software_dna), None
    errors = [finding for finding in findings if finding.level == "error"]
    ok = not errors and not registry.issues
    payload = {
        "report_kind": REPORT_KIND, "software_id": "researchguard", "target_kind": "software",
        "status": "ready" if ok else "not_ready", "ok": ok, "root": str(root),
        "flowguard": _package_identity(), "software_dna": software_dna,
        "readiness": {"status": "ready" if ok else "blocked",
                      "deepest_proven_layer": "static_blueprint_readiness" if ok else "",
                      "first_gap": errors[0].code if errors else "",
                      "gap_count": len(errors)},
        "map_findings": [asdict(finding) for finding in findings],
        "model_execution": {"status": "not_run", "model_ids": [entry.id for entry in registry.entries]},
        "claim_boundary": "Current map and native model/code/test/resource bindings only; executable models and native tests run separately.",
    }
    return payload, None


def check(root: str | Path, *, compact: bool = False) -> tuple[dict[str, Any], int]:
    root_path = Path(root).resolve()
    payload, _bundle = _run_build(root_path)
    if compact:
        readiness = payload.get("readiness", {})
        payload = {
            key: payload[key]
            for key in ("report_kind", "software_id", "target_kind", "status", "ok", "flowguard", "software_dna", "model_execution")
            if key in payload
        }
        payload["readiness"] = {
            key: readiness.get(key)
            for key in ("status", "deepest_proven_layer", "first_gap", "gap_count", "implementation_admitted", "rows")
            if key in readiness
        }
        if "gap" in readiness:
            payload["gap"] = readiness["gap"]
        if "gap" in payload:
            payload["gap"] = payload["gap"]
        if isinstance(payload.get("software_dna"), dict):
            software_dna = payload["software_dna"]
            local_readiness = software_dna.get("readiness", {})
            payload["software_dna"] = {
                key: software_dna[key]
                for key in ("schema_version", "dna_id", "status", "ready", "counts")
                if key in software_dna
            }
            payload["software_dna"]["readiness"] = {
                key: local_readiness.get(key)
                for key in ("status", "deepest_proven_layer", "first_gap", "gap_count")
                if key in local_readiness
            }
    return payload, 0 if payload.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if not raw_args or raw_args[0] in {"-h", "--help"}:
        parser = argparse.ArgumentParser(prog="researchguard self-dna")
        parser.add_argument("command", choices=("check",))
        parser.add_argument("--root", default=".")
        parser.add_argument("--compact", action="store_true")
        parser.print_help()
        return 0 if raw_args and raw_args[0] in {"-h", "--help"} else 2
    if raw_args[0] != "check":
        payload = _blocked(
            Path(".").resolve(),
            "unknown-self-dna-operation",
            "Only the read-only self-dna check operation is public; the native directory and its bound models are the software-DNA authority.",
        )
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        return 2
    parser = argparse.ArgumentParser(prog="researchguard self-dna")
    parser.add_argument("command", choices=("check",), help="audit the FlowGuard-owned repository self-DNA")
    parser.add_argument("--root", default=".")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(raw_args)
    payload, code = check(args.root, compact=args.compact)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return code


__all__ = ["check", "main"]
