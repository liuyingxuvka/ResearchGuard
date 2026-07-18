"""Reseal the current TraceGuard task contract and dispose retired bindings."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from researchguard.trace.purpose_contract import (
    bind_task_guard_purpose,
    canonical_candidate_fingerprint,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "trace"
CONTRACT_PATH = EXAMPLES / "project_radar_task_purpose.json"
CURRENT_BINDING_SCHEMA = "researchguard.trace.guard_purpose_binding.v3"


def _read_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"example is not a mapping: {path}")
    return payload


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
        newline="",
    )


def main() -> int:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    case_rows = [contract["known_good"], *contract["known_bad_cases"]]
    for row in case_rows:
        model_path = EXAMPLES / row["model_path"]
        row["model_sha256"] = canonical_candidate_fingerprint(
            _read_yaml(model_path)
        )
    CONTRACT_PATH.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="",
    )

    bound_path = EXAMPLES / contract["known_good"]["model_path"]
    bound_payload = _read_yaml(bound_path)
    metadata = bound_payload.get("metadata")
    if not isinstance(metadata, dict):
        raise RuntimeError("known-good example metadata must be a mapping")
    metadata.pop("guard_purpose_contract", None)
    rebound = bind_task_guard_purpose(
        bound_payload,
        contract_path=CONTRACT_PATH,
        candidate_path=bound_path,
    )
    _write_yaml(bound_path, rebound)

    for path in EXAMPLES.glob("*.yaml"):
        if path == bound_path:
            continue
        payload = _read_yaml(path)
        metadata = payload.get("metadata")
        binding = (
            metadata.get("guard_purpose_contract")
            if isinstance(metadata, dict)
            else None
        )
        if isinstance(binding, dict) and binding.get("schema_version") != CURRENT_BINDING_SCHEMA:
            metadata.pop("guard_purpose_contract", None)
            _write_yaml(path, payload)

    print("TraceGuard example purpose authority resealed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
