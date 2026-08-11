"""Validate ResearchGuard's source-native software DNA contract.

The contract lives with the repository model sources.  It is an index over the
real parent/child behavior models, code owners, tests, and evidence owners; it
is not an exported copy of the repository and it is not a second FlowGuard
schema.  FlowGuard remains the whole-repository qualification authority.
"""

from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


SOFTWARE_DNA_SCHEMA = "researchguard.software-dna-contract.v1"
SOFTWARE_DNA_PATH = Path("models/software_dna/researchguard.json")
ROOT_MODEL_ID = "researchguard-suite"
MEMBER_MODEL_IDS = (
    "logicguard",
    "sourceguard",
    "traceguard",
    "experimentguard",
)
REQUIRED_TARGET_ADAPTERS = (
    "paper",
    "structured_model",
    "test_workflow",
    "generic_file_tree",
)
REQUIRED_DENOMINATOR_ROOTS = (
    ".flowguard",
    "models",
    "openspec",
    "scripts",
    "skills",
    "src/researchguard",
    "tests",
)


class SoftwareDnaError(ValueError):
    """Raised when the checked-in software-DNA contract is malformed."""


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SoftwareDnaError(f"{label} must be an object")
    return value


def _rows(value: object, label: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SoftwareDnaError(f"{label} must be a list")
    rows = tuple(_object(item, f"{label} row") for item in value)
    if not rows:
        raise SoftwareDnaError(f"{label} must not be empty")
    return rows


def _strings(value: object, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SoftwareDnaError(f"{label} must be a string list")
    values = tuple(str(item) for item in value)
    if any(not item for item in values) or len(values) != len(set(values)):
        raise SoftwareDnaError(f"{label} must contain unique non-empty strings")
    if not allow_empty and not values:
        raise SoftwareDnaError(f"{label} must not be empty")
    return values


def _symbol_names(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise SoftwareDnaError(f"cannot parse bound Python file {path}: {exc}") from exc
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def _bound_symbol(root: Path, binding: Mapping[str, Any], label: str) -> tuple[str, str]:
    path_text = str(binding.get("path", ""))
    symbol = str(binding.get("symbol", ""))
    if not path_text or not symbol:
        raise SoftwareDnaError(f"{label} requires path and symbol")
    path = root / path_text
    if not path.is_file():
        raise SoftwareDnaError(f"{label} path is missing: {path_text}")
    if path.suffix != ".py":
        raise SoftwareDnaError(f"{label} must bind a Python symbol: {path_text}")
    if symbol not in _symbol_names(path):
        raise SoftwareDnaError(f"{label} symbol is missing: {path_text}#{symbol}")
    return path_text, symbol


def _test_binding(root: Path, binding: Mapping[str, Any], label: str) -> tuple[str, str]:
    path_text = str(binding.get("path", ""))
    node_id = str(binding.get("node_id", ""))
    oracle = str(binding.get("oracle", ""))
    if not path_text or not node_id or not oracle:
        raise SoftwareDnaError(f"{label} requires path, node_id, and oracle")
    if not node_id.startswith("test_"):
        raise SoftwareDnaError(f"{label} node_id must name one pytest test")
    path = root / path_text
    if not path.is_file():
        raise SoftwareDnaError(f"{label} path is missing: {path_text}")
    if node_id not in _symbol_names(path):
        raise SoftwareDnaError(f"{label} test node is missing: {path_text}::{node_id}")
    return path_text, node_id


def _evidence_binding(root: Path, binding: Mapping[str, Any], label: str) -> str:
    path_text = str(binding.get("path", ""))
    owner_id = str(binding.get("owner_id", ""))
    claim = str(binding.get("claim", ""))
    if not path_text or not owner_id or not claim:
        raise SoftwareDnaError(f"{label} requires path, owner_id, and claim")
    if not (root / path_text).is_file():
        raise SoftwareDnaError(f"{label} path is missing: {path_text}")
    return path_text


def check_software_dna_contract(root: str | Path) -> dict[str, Any]:
    """Check the native parent/child, code, test, and evidence bindings."""

    root_path = Path(root).resolve()
    contract_path = root_path / SOFTWARE_DNA_PATH
    try:
        raw = json.loads(contract_path.read_text(encoding="utf-8"))
        contract = _object(raw, "software DNA contract")
        if contract.get("schema_version") != SOFTWARE_DNA_SCHEMA:
            raise SoftwareDnaError("software DNA schema is not current")
        if contract.get("dna_id") != "software-dna:researchguard":
            raise SoftwareDnaError("software DNA identity is not ResearchGuard")
        if contract.get("system_model_id") != ROOT_MODEL_ID:
            raise SoftwareDnaError("software DNA has no single ResearchGuard suite root")

        denominator = _object(contract.get("denominator"), "denominator")
        included_roots = _strings(denominator.get("included_roots"), "included roots")
        if tuple(sorted(included_roots)) != REQUIRED_DENOMINATOR_ROOTS:
            raise SoftwareDnaError("software DNA denominator roots are incomplete or foreign")
        for relative in included_roots:
            if not (root_path / relative).exists():
                raise SoftwareDnaError(f"denominator root is missing: {relative}")
        excluded = _strings(
            denominator.get("excluded_runtime_outputs"),
            "excluded runtime outputs",
        )
        if not all("evidence" in item or "model-mesh" in item or "__pycache__" in item for item in excluded):
            raise SoftwareDnaError("runtime exclusions may not remove source authority")

        adapters = _rows(contract.get("external_target_adapters"), "external target adapters")
        adapter_ids = tuple(str(row.get("adapter_id", "")) for row in adapters)
        if tuple(sorted(adapter_ids)) != tuple(sorted(REQUIRED_TARGET_ADAPTERS)):
            raise SoftwareDnaError("provider-neutral external target adapters are incomplete")
        for row in adapters:
            _strings(row.get("selector_kinds"), f"adapter {row.get('adapter_id')} selectors")
            if not str(row.get("claim_boundary", "")):
                raise SoftwareDnaError("every target adapter needs a claim boundary")

        models = _rows(contract.get("models"), "models")
        model_by_id = {str(row.get("model_id", "")): row for row in models}
        expected_ids = {ROOT_MODEL_ID, *MEMBER_MODEL_IDS}
        if set(model_by_id) != expected_ids or len(model_by_id) != len(models):
            raise SoftwareDnaError("software DNA must contain one root and exactly four members")
        root_model = model_by_id[ROOT_MODEL_ID]
        if str(root_model.get("parent_model_id", "")):
            raise SoftwareDnaError("the suite root cannot have a structural parent")
        child_ids = _strings(root_model.get("child_model_ids"), "root child model ids")
        if set(child_ids) != set(MEMBER_MODEL_IDS):
            raise SoftwareDnaError("the suite root must own exactly four member subtrees")
        for member_id in MEMBER_MODEL_IDS:
            member = model_by_id[member_id]
            if member.get("parent_model_id") != ROOT_MODEL_ID:
                raise SoftwareDnaError(f"{member_id} is not attached to the suite root")
            if _strings(member.get("child_model_ids"), f"{member_id} child ids", allow_empty=True):
                raise SoftwareDnaError(f"{member_id} unexpectedly declares another structural child")

        code_owners: list[tuple[str, str]] = []
        test_owners: list[tuple[str, str]] = []
        evidence_paths: list[str] = []
        block_ids: list[str] = []
        public_outputs: dict[str, tuple[str, ...]] = {}
        for model_id, model in model_by_id.items():
            public_inputs = _strings(model.get("public_input_ids"), f"{model_id} public inputs")
            outputs = _strings(model.get("public_output_ids"), f"{model_id} public outputs")
            public_outputs[model_id] = outputs
            blocks = _rows(model.get("function_blocks"), f"{model_id} function blocks")
            for block in blocks:
                block_id = str(block.get("block_id", ""))
                if not block_id or not block_id.startswith(f"block:{model_id}:"):
                    raise SoftwareDnaError(f"{model_id} has an invalid function-block identity")
                block_ids.append(block_id)
                signature = _object(block.get("signature"), f"{block_id} signature")
                for field in ("input", "state", "effect", "output", "completion"):
                    _strings(signature.get(field), f"{block_id} {field}")
                if not set(_strings(signature.get("input"), f"{block_id} input")).intersection(public_inputs):
                    raise SoftwareDnaError(f"{block_id} consumes no declared model input")
                code_owners.append(
                    _bound_symbol(root_path, _object(block.get("code_owner"), f"{block_id} code owner"), f"{block_id} code owner")
                )
                test_owners.append(
                    _test_binding(root_path, _object(block.get("test_binding"), f"{block_id} test binding"), f"{block_id} test binding")
                )
                evidence_paths.append(
                    _evidence_binding(root_path, _object(block.get("evidence_binding"), f"{block_id} evidence binding"), f"{block_id} evidence binding")
                )

        if len(block_ids) != len(set(block_ids)):
            raise SoftwareDnaError("function-block identities are not unique")
        duplicate_code = [item for item, count in Counter(code_owners).items() if count > 1]
        if duplicate_code:
            raise SoftwareDnaError(f"code symbols have duplicate primary owners: {duplicate_code!r}")
        duplicate_tests = [item for item, count in Counter(test_owners).items() if count > 1]
        if duplicate_tests:
            raise SoftwareDnaError(f"tests have duplicate primary model owners: {duplicate_tests!r}")

        root_inputs = set(_strings(root_model.get("public_input_ids"), "root public inputs"))
        interface_rows = _rows(contract.get("child_interface_bindings"), "child interface bindings")
        expected_child_outputs = {
            (member_id, output_id)
            for member_id in MEMBER_MODEL_IDS
            for output_id in public_outputs[member_id]
        }
        observed_child_outputs: set[tuple[str, str]] = set()
        for row in interface_rows:
            member_id = str(row.get("child_model_id", ""))
            output_id = str(row.get("child_output_id", ""))
            parent_input_id = str(row.get("parent_input_id", ""))
            if member_id not in MEMBER_MODEL_IDS or output_id not in public_outputs.get(member_id, ()):
                raise SoftwareDnaError("child interface binds an unknown child output")
            if parent_input_id not in root_inputs:
                raise SoftwareDnaError("child interface does not terminate at a root input")
            if not str(row.get("disposition", "")):
                raise SoftwareDnaError("child output requires one parent disposition")
            observed_child_outputs.add((member_id, output_id))
        if observed_child_outputs != expected_child_outputs or len(interface_rows) != len(observed_child_outputs):
            raise SoftwareDnaError("parent does not consume every child output exactly once")

        report = {
            "schema_version": SOFTWARE_DNA_SCHEMA,
            "dna_id": contract["dna_id"],
            "status": "ready",
            "ready": True,
            "contract_path": SOFTWARE_DNA_PATH.as_posix(),
            "system_model_id": ROOT_MODEL_ID,
            "member_model_ids": list(MEMBER_MODEL_IDS),
            "counts": {
                "models": len(models),
                "function_blocks": len(block_ids),
                "code_bindings": len(code_owners),
                "test_bindings": len(test_owners),
                "evidence_bindings": len(evidence_paths),
                "child_interface_bindings": len(interface_rows),
                "target_adapters": len(adapters),
                "denominator_roots": len(included_roots),
            },
            "claim_boundary": str(contract.get("claim_boundary", "")),
        }
        if not report["claim_boundary"]:
            raise SoftwareDnaError("software DNA requires an explicit claim boundary")
        return report
    except (OSError, json.JSONDecodeError, SoftwareDnaError) as exc:
        return {
            "schema_version": SOFTWARE_DNA_SCHEMA,
            "dna_id": "software-dna:researchguard",
            "status": "blocked",
            "ready": False,
            "contract_path": SOFTWARE_DNA_PATH.as_posix(),
            "gap": {
                "code": "software_dna_contract_invalid",
                "message": str(exc),
            },
        }


__all__ = [
    "MEMBER_MODEL_IDS",
    "ROOT_MODEL_ID",
    "SOFTWARE_DNA_PATH",
    "SOFTWARE_DNA_SCHEMA",
    "SoftwareDnaError",
    "check_software_dna_contract",
]
