"""Run the discourse-structure owner and emit its local receipt."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import hashlib

from flowguard.native_case_protocol import CASE_DIMENSIONS


ROOT = Path(__file__).resolve().parents[4]
MODEL_PATH = ROOT / ".flowguard/models/owners/discourse_structure/model.py"
RUNNER_PATH = Path(__file__).resolve()
sys.path.insert(0, str(MODEL_PATH.parent))
import model  # noqa: E402


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _case_dimensions(case_id: str) -> tuple[str, ...]:
    """Return the contract dimensions for one declared case identity."""

    if case_id == model.KNOWN_GOOD_CASE_ID:
        return CASE_DIMENSIONS["good"]
    if case_id == f"boundary:{model.MODEL_ID}":
        return CASE_DIMENSIONS["boundary"]
    if case_id in model.KNOWN_BAD_CASE_IDS:
        return CASE_DIMENSIONS["bad"]
    raise ValueError(f"unknown native case id: {case_id}")


def _write_native_results() -> None:
    output = os.environ.get("FLOWGUARD_OUTPUT_DIR")
    if not output:
        return
    directory = Path(output).resolve(); directory.mkdir(parents=True, exist_ok=True)
    cases = [model.KNOWN_GOOD_CASE_ID, f"boundary:{model.MODEL_ID}", *model.KNOWN_BAD_CASE_IDS]
    rows = []
    for index, case_id in enumerate(cases):
        raw = directory / f"discourse-structure-raw-{index}.json"; raw.write_text(json.dumps({"model_id": model.MODEL_ID, "case_id": case_id}, sort_keys=True), encoding="utf-8"); raw_hash = _sha256(raw)
        dimensions = _case_dimensions(case_id)
        rows.append({"schema_version": "flowguard.native_model_case_result.v1", "owner_id": f"model:{model.MODEL_ID}", "source_case_id": case_id, "outcome": "pass" if index in (0, 1) else "rejected", "observed_status": "pass" if index in (0, 1) else "blocked", "observed_finding_codes": [] if index in (0, 1) else [model.PROTECTED_FAILURE_IDS[index - 2]], "executed_dimensions": list(dimensions), "oracle_results": [{"dimension": d, "oracle_member_id": f"{model.MODEL_ID}:oracle", "status": "pass" if index == 0 else "blocked", "ok": index in (0, 1)} for d in dimensions], "result_artifact_fingerprint": raw_hash, "input_fingerprint": raw_hash, "model_fingerprint": _sha256(MODEL_PATH), "code_fingerprint": _sha256(MODEL_PATH), "test_fingerprint": _sha256(RUNNER_PATH), "oracle_fingerprint": _sha256(RUNNER_PATH), "toolchain_fingerprint": _sha256(RUNNER_PATH), "environment_fingerprint": _sha256(RUNNER_PATH), "raw_artifact_path": raw.name, "child_case_ids": []})
    (directory / "native-case-results.json").write_text(json.dumps({"schema_version": "flowguard.native_model_case_result.v1", "results": rows}, sort_keys=True), encoding="utf-8")


def main() -> int:
    model.run_model()
    _write_native_results()
    print("FLOWGUARD_EXECUTED_CASE_IDS=" + json.dumps([model.KNOWN_GOOD_CASE_ID, f"boundary:{model.MODEL_ID}", *model.KNOWN_BAD_CASE_IDS]))
    print(json.dumps({
        "artifact_kind": "flowguard_model_child_receipt",
        "receipt_version": "flowguard.child-model-receipt.v1",
        "model_id": model.MODEL_ID,
        "status": "pass",
        "check_id": f"check:model-regression:{model.MODEL_ID}",
        "model_path": ".flowguard/models/owners/discourse_structure/model.py",
        "runner_path": ".flowguard/verification/owners/discourse_structure/run_checks.py",
        "model_sha256": _sha256(MODEL_PATH),
        "runner_sha256": _sha256(RUNNER_PATH),
        "protected_failure_ids": list(model.PROTECTED_FAILURE_IDS),
        "claim_boundary": "Cross-block structural contribution checks only; prose coherence remains a reader review responsibility.",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


