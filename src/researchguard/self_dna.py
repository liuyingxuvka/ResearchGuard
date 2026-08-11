"""FlowGuard-owned software self-DNA entry for ResearchGuard.

This module is deliberately a thin adapter.  ResearchGuard does not define a
second software-blueprint format and it does not turn its member-domain DNA
into a repository authority.  The only authority is the current FlowGuard
self-blueprint API.  Ordinary ResearchGuard commands never call this module;
``self-dna`` is an explicit, read-only whole-repository operation.  The
standalone materialization/export path is intentionally not part of the
ResearchGuard console; FlowGuard remains the sole owner of any canonical
software-blueprint projection.
"""

from __future__ import annotations

import argparse
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
            "schema_version": str(flowguard.SCHEMA_VERSION),
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


def _blocked(root: Path, code: str, message: str, *, exc: Exception | None = None) -> dict[str, Any]:
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
    if exc is not None:
        payload["gap"]["exception"] = f"{type(exc).__name__}: {exc}"
    return payload


def _run_build(root: Path) -> tuple[dict[str, Any], Any | None]:
    try:
        from flowguard.self_blueprint import (
            FlowGuardSelfBlueprintError,
            build_flowguard_self_blueprint,
        )
    except (ImportError, AttributeError) as exc:
        return _blocked(root, "flowguard_toolchain_unavailable", "The current FlowGuard self-blueprint API cannot be imported.", exc=exc), None
    try:
        bundle = build_flowguard_self_blueprint(root)
    except FlowGuardSelfBlueprintError as exc:
        return _blocked(root, "flowguard_self_blueprint_not_ready", "FlowGuard rejected the current project authority, definition, inventory, or model evidence; no local substitute is used.", exc=exc), None
    except (OSError, ValueError) as exc:
        return _blocked(root, "flowguard_self_blueprint_input_invalid", "The current FlowGuard self-blueprint inputs are invalid or unavailable.", exc=exc), None

    ledger = bundle.readiness_ledger.to_dict()
    qualification = getattr(bundle, "dna_qualification", None)
    if qualification is None:
        return _blocked(
            root,
            "flowguard_dna_qualification_missing",
            "The current FlowGuard self-blueprint did not expose its provider-neutral DNA qualification contract.",
        ), None
    qualification_payload = qualification.to_dict()
    qualified = bool(qualification.qualified)
    payload = {
        "report_kind": REPORT_KIND,
        "software_id": "researchguard",
        "target_kind": "software",
        "status": "ready" if bundle.ok and qualified else "not_ready",
        "ok": bool(bundle.ok and qualified),
        "root": str(root),
        "claim_boundary": (
            "This is the FlowGuard repository software-DNA boundary. The four "
            "member-domain blueprints remain opaque native evidence and are not "
            "a second whole-repository authority."
        ),
        "flowguard": _package_identity(),
        "readiness": ledger,
        "dna_qualification": qualification_payload,
        "bundle": bundle.to_dict(),
    }
    return payload, bundle


def check(root: str | Path, *, compact: bool = False) -> tuple[dict[str, Any], int]:
    root_path = Path(root).resolve()
    payload, _bundle = _run_build(root_path)
    if compact:
        readiness = payload.get("readiness", {})
        payload = {
            key: payload[key]
            for key in ("report_kind", "software_id", "target_kind", "status", "ok", "flowguard")
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
            "Only the read-only self-dna check operation is public; standalone materialization is retired.",
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
