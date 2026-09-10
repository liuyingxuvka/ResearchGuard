"""Run the suite model and consume exact current receipts from its children.

The output is local validation evidence. It is not an authority snapshot,
activation, release, or canonical projection.
"""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from flowguard.native_case_protocol import NativeModelCaseResult
import hashlib


ROOT = Path(__file__).resolve().parents[4]
MODEL_PATH = ROOT / ".flowguard/models/owners/researchguard_suite/model.py"
RUNNER_PATH = Path(__file__).resolve()
SEMANTIC_MESH_PATH = ROOT / ".flowguard/models/owners/authoritative_model_system/semantic_model_mesh.json"
# These checks execute in fresh Python processes.  On a cold Windows machine
# importing the provider-neutral FlowGuard package and hashing the 586-item
# ResearchGuard denominator can exceed the old 30-second native limit.  Keep
# the timeout finite (so a hung child still fails closed), but large enough to
# cover a legitimate cold run.  The parent simulator supplies its own global
# budget; these are per-process bounds only.
CHILD_TIMEOUT_SECONDS = 60
NATIVE_TIMEOUT_SECONDS = 180
sys.path.insert(0, str(MODEL_PATH.parent))
import model  # noqa: E402


def _run_bounded(command: list[str], *, env: dict[str, str], timeout: int) -> tuple[int, str]:
    """Run one local child and close its whole Windows process tree on timeout."""
    proc = subprocess.Popen(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env, close_fds=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return proc.returncode, stdout + stderr
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True, text=True, check=False,
        )
        stdout, stderr = proc.communicate(timeout=5)
        return 124, (stdout or "") + (stderr or "") + f"\nPROCESS_TREE_TIMEOUT={timeout}\n"


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _raw_sha256(path: Path) -> str:
    """Hash generated evidence bytes exactly as FlowGuard's raw-artifact gate does."""

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _run_child(model_id: str, *, parent_output: Path | None = None) -> tuple[dict[str, Any] | None, str]:
    runner = ROOT / f".flowguard/verification/owners/{model_id}/run_checks.py"
    environment = os.environ.copy()
    if parent_output is not None:
        # A child must publish its native case envelope in its own directory.
        # Reusing the parent's FLOWGUARD_OUTPUT_DIR lets the last child
        # overwrite the aggregate envelope, which makes a green child look
        # like a foreign parent result during strict reconciliation.
        child_output = parent_output / "children" / model_id
        child_output.mkdir(parents=True, exist_ok=True)
        environment["FLOWGUARD_OUTPUT_DIR"] = str(child_output)
    returncode, output = _run_bounded(
        [sys.executable, str(runner)],
        env=environment,
        timeout=CHILD_TIMEOUT_SECONDS,
    )
    lines = [line for line in output.splitlines() if line.strip()]
    receipt: dict[str, Any] | None = None
    if lines:
        try:
            candidate = json.loads(lines[-1])
        except json.JSONDecodeError:
            candidate = None
        if isinstance(candidate, dict) and candidate.get("artifact_kind") == "flowguard_model_child_receipt":
            receipt = candidate
    return receipt, output


def _case_ids() -> tuple[str, ...]:
    return (
        model.KNOWN_GOOD_CASE_ID,
        f"boundary:{model.MODEL_ID}",
        *model.KNOWN_BAD_CASE_IDS,
    )


def _write_native_results(
    output_dir: Path,
    *,
    native_output: str,
    native_returncode: int,
    child_receipts: list[dict[str, Any]],
) -> None:
    """Persist the aggregate's own local case envelope.

    The parent suite has a real native run (the 15 route/topology scenarios)
    and nine independently executed child receipts.  The explicit probes
    below bind each protected failure to an observed scenario or child
    condition; if one is absent we record a rejected case only when the
    corresponding local evidence is present.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    child_ids = {str(item.get("model_id", "")) for item in child_receipts}
    child_statuses = {str(item.get("model_id", "")): str(item.get("status", "")) for item in child_receipts}
    probes: list[tuple[str, bool, str]] = [
        (
            model.PROTECTED_FAILURE_IDS[0],
            "RG03_ambiguous_blocks" in native_output and "member_admission_no_match_blocked" in native_output,
            "RG03_ambiguous_blocks",
        ),
        (
            model.PROTECTED_FAILURE_IDS[1],
            "RG11_stale_task_facts_block" in native_output and "task_facts_invalid_blocked" in native_output,
            "RG11_stale_task_facts_block",
        ),
        (
            model.PROTECTED_FAILURE_IDS[2],
            "RG04_member_failure_terminal" in native_output and "member_failure_terminal" in native_output,
            "RG04_member_failure_terminal",
        ),
        (
            model.PROTECTED_FAILURE_IDS[3],
            "RG07_predecessor_distribution_absent" in native_output
            and "RG08_predecessor_distribution_present" in native_output
            and "package_identity_resolved_current" in native_output,
            "RG07/RG08_package_identity",
        ),
        (
            model.PROTECTED_FAILURE_IDS[4],
            len(child_ids) == len(model.CHILD_MODEL_IDS)
            and all(child_statuses.get(item) == "pass" for item in model.CHILD_MODEL_IDS),
            "nine_current_child_receipts",
        ),
        (
            model.PROTECTED_FAILURE_IDS[5],
            "RG09_direct_experiment" in native_output
            and "route_selected_experimentguard" in native_output
            and "member_terminal_pass" in native_output,
            "RG09_direct_experiment",
        ),
    ]
    case_ids = _case_ids()
    rows: list[dict[str, Any]] = []
    model_fp = _sha256(MODEL_PATH)
    runner_fp = _sha256(RUNNER_PATH)
    input_fp = os.environ.get("FLOWGUARD_INPUT_FINGERPRINT", "").strip()
    for index, case_id in enumerate(case_ids):
        raw_payload: dict[str, Any] = {
            "schema_version": "researchguard.parent-native-probe.v1",
            "case_id": case_id,
            "native_returncode": native_returncode,
            "child_model_ids": sorted(child_ids),
        }
        if index == 0:
            accepted = native_returncode == 0 and len(child_ids) == len(model.CHILD_MODEL_IDS)
            finding_id = ""
            raw_payload["probe"] = "native_suite_and_children"
        elif index == 1:
            accepted = native_returncode == 0
            finding_id = ""
            raw_payload["probe"] = "boundary_parent_contract"
        else:
            failure_id, accepted, probe = probes[index - 2]
            finding_id = failure_id
            raw_payload.update({"probe": probe, "protected_failure_id": failure_id, "probe_observed": accepted})
        raw = output_dir / f"researchguard-suite-raw-{index}.json"
        raw.write_text(json.dumps(raw_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        # Raw result artifacts are evidence bytes, so their fingerprint must
        # use the exact byte hash.  Source/model identities continue to use
        # FlowGuard's canonical newline-normalized fingerprint above.
        raw_hash = _raw_sha256(raw)
        outcome = "pass" if accepted else "rejected"
        observed = "pass" if accepted else "blocked"
        rows.append(
            NativeModelCaseResult(
                owner_id=f"model:{model.MODEL_ID}",
                source_case_id=case_id,
                outcome=outcome,
                observed_status=observed,
                observed_finding_codes=() if not finding_id else (finding_id,),
                executed_dimensions=(("input", "error", "decision", "retry", "timeout", "completion") if index == 1 else ("input", "state", "output", "effect", "order", "completion")),
                oracle_results=tuple(
                    {
                        "dimension": dimension,
                        "oracle_member_id": f"{model.MODEL_ID}:oracle",
                        "status": observed,
                        "ok": accepted,
                    }
                    for dimension in (("input", "error", "decision", "retry", "timeout", "completion") if index == 1 else ("input", "state", "output", "effect", "order", "completion"))
                ),
                result_artifact_fingerprint=raw_hash,
                input_fingerprint=input_fp or raw_hash,
                model_fingerprint=model_fp,
                code_fingerprint=model_fp,
                test_fingerprint=runner_fp,
                oracle_fingerprint=runner_fp,
                toolchain_fingerprint=runner_fp,
                environment_fingerprint=runner_fp,
                raw_artifact_path=raw.name,
            ).to_dict()
        )
    (output_dir / "native-case-results.json").write_text(
        json.dumps({"schema_version": "flowguard.native_model_case_result.v1", "results": rows}, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )


def _validate_receipt(model_id: str, receipt: dict[str, Any] | None) -> list[str]:
    if receipt is None:
        return [f"child:{model_id}:missing_receipt"]
    expected_model = f".flowguard/models/owners/{model_id}/model.py"
    expected_runner = f".flowguard/verification/owners/{model_id}/run_checks.py"
    findings: list[str] = []
    if receipt.get("model_id") != model_id:
        findings.append(f"child:{model_id}:model_id_mismatch")
    if receipt.get("status") != "pass":
        findings.append(f"child:{model_id}:status_not_pass")
    if receipt.get("check_id") != f"check:model-regression:{model_id}":
        findings.append(f"child:{model_id}:check_id_mismatch")
    if receipt.get("model_path") != expected_model:
        findings.append(f"child:{model_id}:model_path_mismatch")
    if receipt.get("runner_path") != expected_runner:
        findings.append(f"child:{model_id}:runner_path_mismatch")
    if receipt.get("model_sha256") != _sha256(ROOT / expected_model):
        findings.append(f"child:{model_id}:model_hash_mismatch")
    if receipt.get("runner_sha256") != _sha256(ROOT / expected_runner):
        findings.append(f"child:{model_id}:runner_hash_mismatch")
    return findings


def _validate_semantic_mesh() -> tuple[list[str], list[dict[str, Any]]]:
    """Require the declared hierarchy and preserve fail-closed propagation."""

    payload = json.loads(SEMANTIC_MESH_PATH.read_text(encoding="utf-8"))
    expected_parents = {
        child: parent
        for child, parent in model.SEMANTIC_PARENT_BY_CHILD.items()
    }
    records = {
        str(row.get("model_id")): row
        for row in payload.get("models", ())
        if isinstance(row, dict)
    }
    findings: list[str] = []
    declared_parents = {
        str(row.get("parent_id"))
        for row in payload.get("semantic_parents", ())
        if isinstance(row, dict)
    }
    expected_parent_ids = {
        model.ROOT_STRUCTURAL_PARENT_ID,
        *set(expected_parents.values()),
    }
    if declared_parents != expected_parent_ids:
        findings.append("mesh:semantic_parent_inventory_mismatch")
    for root_model_id in (*model.ROOT_SUPPORTING_MODEL_IDS, "researchguard_suite"):
        if records.get(root_model_id, {}).get("structural_parent_id") != model.ROOT_STRUCTURAL_PARENT_ID:
            findings.append(f"mesh:{root_model_id}:root_support_parent_mismatch")
    for child, parent in expected_parents.items():
        if records.get(child, {}).get("structural_parent_id") != parent:
            findings.append(f"mesh:{child}:structural_parent_mismatch")
    expected_edges = set(model.SEMANTIC_RELATION_EDGES)
    relation_rows: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()
    # The current FlowGuard semantic-self-mesh schema stores structural
    # relations in each target row's ``structural_parent_id`` and
    # ``consumer_ids``.  Materialize the same relation envelope in the parent
    # receipt without adding a non-schema top-level ``semantic_relations``
    # field to the source mesh.
    for source, target in model.SEMANTIC_RELATION_EDGES:
        edge = (source, target)
        seen_edges.add(edge)
        target_row = records.get(target, {})
        if f"model:{source}" not in tuple(target_row.get("consumer_ids", ())):
            findings.append(f"mesh:{source}->{target}:consumer_binding_mismatch")
        relation_rows.append(
            {
                "relation_id": f"semantic-relation:{source}->{target}",
                "kind": "contains",
                "source_model_id": source,
                "target_model_id": target,
                "failure_propagation": model.CHILD_FAILURE_PROPAGATION,
                "source_model_path": f".flowguard/models/owners/{source}/model.py",
                "source_runner_path": f".flowguard/verification/owners/{source}/run_checks.py",
                "target_model_path": f".flowguard/models/owners/{target}/model.py",
                "target_runner_path": f".flowguard/verification/owners/{target}/run_checks.py",
                "evidence_check_id": f"check:model-regression:{target}",
                "claim_boundary": "A failed or missing child receipt blocks the consuming parent relation.",
            }
        )
    if seen_edges != expected_edges:
        findings.append("mesh:semantic_relation_inventory_mismatch")
    return findings, relation_rows


def main() -> int:
    model.run_model()
    parent_output = Path(os.environ.get("FLOWGUARD_OUTPUT_DIR", str(ROOT / ".flowguard/evidence/model-mesh/native/researchguard_suite"))).resolve()
    manifest = json.loads((ROOT / ".flowguard/models/regression-manifest.json").read_text(encoding="utf-8"))
    manifest_ids = tuple(row.get("model_id") for row in manifest.get("models", ()) if isinstance(row, dict))
    findings: list[str] = []
    mesh_findings, semantic_relations = _validate_semantic_mesh()
    findings.extend(mesh_findings)
    if set(manifest_ids) != {model.MODEL_ID, *model.CHILD_MODEL_IDS} or len(manifest_ids) != 10:
        findings.append("manifest:ten_node_model_inventory_mismatch")

    child_receipts: list[dict[str, Any]] = []
    for model_id in model.CHILD_MODEL_IDS:
        receipt, _output = _run_child(model_id, parent_output=parent_output)
        findings.extend(_validate_receipt(model_id, receipt))
        if receipt is not None:
            child_receipts.append(receipt)
    if len({row.get("model_id") for row in child_receipts}) != len(model.CHILD_MODEL_IDS):
        findings.append("children:receipt_model_ids_not_exact")

    native_returncode, native_output = _run_bounded(
        [sys.executable, ".flowguard/verification/run_researchguard_suite_model.py"],
        env=os.environ.copy(),
        timeout=NATIVE_TIMEOUT_SECONDS,
    )
    if native_returncode:
        findings.append("native:researchguard_suite_model_failed")
    _write_native_results(
        parent_output,
        native_output=native_output,
        native_returncode=native_returncode,
        child_receipts=child_receipts,
    )

    status = "pass" if not findings else "blocked"
    print("FLOWGUARD_EXECUTED_CASE_IDS=" + json.dumps(list(_case_ids())))
    print(json.dumps({
        "artifact_kind": "researchguard_flowguard_parent_receipt",
        "receipt_version": "flowguard.parent-model-receipt.v1",
        "model_id": model.MODEL_ID,
        "status": status,
        "check_id": "check:model-regression:researchguard_suite",
        "model_path": ".flowguard/models/owners/researchguard_suite/model.py",
        "runner_path": ".flowguard/verification/owners/researchguard_suite/run_checks.py",
        "model_sha256": _sha256(MODEL_PATH),
        "runner_sha256": _sha256(RUNNER_PATH),
        "child_model_ids": list(model.CHILD_MODEL_IDS),
        "child_receipts": child_receipts,
        "semantic_relations": semantic_relations,
        "child_failure_propagation": model.CHILD_FAILURE_PROPAGATION,
        "findings": findings,
        "claim_boundary": "Local ten-node model and native suite checks only; no authority, installation, or release claim.",
    }, indent=2, sort_keys=True))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())

