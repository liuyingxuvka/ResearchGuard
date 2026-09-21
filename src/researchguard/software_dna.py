"""Read-only, repository-native ResearchGuard software-DNA qualification.

The model in :mod:`models/software_dna/researchguard.json` describes ownership
and interfaces; it does *not* define the denominator.  The denominator is
enumerated by the provider-neutral inventory below, using one adapter contract
for Python, declarative, workflow, text, and opaque resource surfaces.  This
keeps a caller-supplied path list or a Python-only scan from becoming a false
green.  FlowGuard remains the authority for its own canonical projection; this
module only qualifies the source-native contract and exposes deterministic
affected/reverse indexes for the explicit self-DNA operation.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
from collections import Counter, deque
from pathlib import Path
import re
import tomllib
from typing import Any, Iterable, Mapping, Sequence


SOFTWARE_DNA_SCHEMA = "researchguard.software-dna-contract.v2"
SOFTWARE_DNA_PATH = Path("models/software_dna/researchguard.json")
ROOT_MODEL_ID = "researchguard-suite"
BCL_CONNECTION_SCHEMA = "researchguard.software-dna-bcl-connection.v1"
BCL_LEDGER_ARTIFACT_TYPE = "flowguard_behavior_commitment_ledger"
BCL_LEDGER_SCHEMA_VERSION = "1.0"
BCL_LEDGER_FORMAT_VERSION = "1"
NATIVE_OWNER_MANIFEST_PATH = Path(".flowguard/models/regression-manifest.json")
NATIVE_OWNER_COUNT = 10
MEMBER_MODEL_IDS = (
    "logicguard",
    "sourceguard",
    "traceguard",
    "experimentguard",
)

# These are source boundaries, not a model-declared denominator.  The model
# must agree with them, but deleting a model row cannot shrink the inventory.
REPOSITORY_BOUNDARY_ROOTS = (
    ".flowguard",
    ".github",
    "examples",
    "models",
    "openspec",
    "scripts",
    "skills",
    "src/researchguard",
    "tests",
)
REPOSITORY_BOUNDARY_FILES = (
    ".gitignore",
    "AGENTS.md",
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "pyproject.toml",
)
GENERATED_RUNTIME_PREFIXES = (
    ".flowguard/evidence/",
    ".flowguard/history/",
    ".flowguard/models/authority/",
    ".flowguard/model-mesh/",
    ".flowguard/receipts/",
    ".flowguard/exports/",
    ".pytest_cache/",
    "build/",
    "dist/",
)
GENERATED_RUNTIME_SUFFIXES = (
    ".egg-info/",
    "/__pycache__/",
)

REQUIRED_TARGET_ADAPTERS = (
    "paper",
    "structured_model",
    "test_workflow",
    "generic_file_tree",
)
REQUIRED_INVENTORY_ADAPTERS = (
    "python",
    "json",
    "toml",
    "yaml",
    "markdown",
    "text",
    "binary_resource",
)
INDEX_KINDS = (
    "model",
    "implementation",
    "test",
    "intent",
    "resource",
    "topology",
    "public_surface",
    "native_domain",
    "external_interface",
)
READINESS_LAYERS = (
    "evidence_qualification",
    "implementation_inventory",
    "traceability",
    "independent_semantics",
    "model_code_test_binding",
    "resource_oracle_binding",
    "static_blueprint_readiness",
)


class SoftwareDnaError(ValueError):
    """Raised when the checked-in software-DNA contract is malformed."""


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SoftwareDnaError(f"{label} must be an object")
    return value


def _rows(value: object, label: str, *, allow_empty: bool = False) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SoftwareDnaError(f"{label} must be a list")
    rows = tuple(_object(item, f"{label} row") for item in value)
    if not rows and not allow_empty:
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
    if not path_text or not node_id:
        raise SoftwareDnaError(f"{label} requires path and node_id")
    if not node_id.startswith("test_"):
        raise SoftwareDnaError(f"{label} node_id must name one pytest test")
    path = root / path_text
    if not path.is_file():
        raise SoftwareDnaError(f"{label} path is missing: {path_text}")
    if node_id not in _symbol_names(path):
        raise SoftwareDnaError(f"{label} test node is missing: {path_text}::{node_id}")
    for field in (
        "setup",
        "input",
        "pre_state",
        "expected_output",
        "post_state",
        "effect",
        "failure_class",
        "oracle",
    ):
        _strings(binding.get(field), f"{label} {field}")
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


def _normalise_relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_excluded(relative: str) -> bool:
    normal = relative.replace("\\", "/")
    if normal.startswith(".") and normal.startswith(".flowguard/"):
        # Keep checked-in model sources, but never let a runtime projection or
        # receipt become its own source denominator.
        if any(normal.startswith(prefix) for prefix in GENERATED_RUNTIME_PREFIXES):
            return True
    if normal.startswith(".pytest_cache/") or normal.startswith("build/") or normal.startswith("dist/"):
        return True
    if "/__pycache__/" in f"/{normal}/" or normal.endswith("/__pycache__"):
        return True
    if ".egg-info/" in normal:
        return True
    return False


def _adapter_for(path: str) -> str | None:
    lower = path.lower()
    name = Path(lower).name
    if name in {".gitignore", "license"}:
        return "text"
    suffix = Path(lower).suffix
    if suffix == ".py":
        return "python"
    if suffix == ".json":
        return "json"
    if suffix == ".jsonl":
        return "json"
    if suffix == ".toml":
        return "toml"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix in {".md", ".rst", ".txt"}:
        return "markdown" if suffix == ".md" else "text"
    if suffix in {".png", ".ico", ".jpg", ".jpeg", ".gif", ".svg"}:
        return "binary_resource"
    return None


def _parse_surface(path: Path, adapter: str) -> tuple[str, str]:
    """Return ``(parse_status, optional_error)`` without executing source."""

    try:
        if adapter == "python":
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        elif adapter == "json":
            text = path.read_text(encoding="utf-8")
            if path.suffix.lower() == ".jsonl":
                for line in text.splitlines():
                    if line.strip():
                        json.loads(line)
            else:
                json.loads(text)
        elif adapter == "toml":
            tomllib.loads(path.read_text(encoding="utf-8"))
        elif adapter == "yaml":
            try:
                import yaml  # type: ignore
            except ImportError as exc:
                return "blocked", f"yaml-adapter-unavailable: {exc}"
            yaml.safe_load(path.read_text(encoding="utf-8"))
        # Markdown, text, and binary resources are intentionally opaque.  They
        # are still admitted with a content fingerprint and a resource oracle.
        return "parsed" if adapter in {"python", "json", "toml", "yaml"} else "opaque", ""
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError) as exc:
        return "blocked", f"{type(exc).__name__}: {exc}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _candidate_paths(root: Path) -> tuple[Path, ...]:
    candidates: set[Path] = set()
    for relative in REPOSITORY_BOUNDARY_FILES:
        path = root / relative
        if path.is_file():
            candidates.add(path)
    for relative in REPOSITORY_BOUNDARY_ROOTS:
        directory = root / relative
        if directory.is_dir():
            # Prune only the fixed non-source boundaries before descending.
            # Historical receipts and generated authority projections can be
            # large; enumerating them first would make a source-only check
            # depend on the size and availability of unrelated run history.
            for current, directories, files in os.walk(directory, followlinks=False):
                current_path = Path(current)
                directories[:] = [
                    name
                    for name in directories
                    if not _is_excluded(_normalise_relative(current_path / name, root) + "/")
                ]
                candidates.update(
                    current_path / name
                    for name in files
                    if not _is_excluded(_normalise_relative(current_path / name, root))
                )
    return tuple(sorted(candidates, key=lambda path: _normalise_relative(path, root)))


def build_provider_neutral_inventory(root: str | Path) -> dict[str, Any]:
    """Enumerate the fixed repository boundary before reading model bindings."""

    root_path = Path(root).resolve()
    rows: list[dict[str, Any]] = []
    gaps: list[dict[str, str]] = []
    for path in _candidate_paths(root_path):
        relative = _normalise_relative(path, root_path)
        if _is_excluded(relative):
            continue
        adapter = _adapter_for(relative)
        if adapter is None:
            gaps.append({"code": "unknown_inventory_adapter", "path": relative})
            rows.append(
                {
                    "item_id": f"inventory:{relative}",
                    "path": relative,
                    "adapter_id": "unknown",
                    "kind": "unresolved_surface",
                    "fingerprint": _sha256(path),
                    "terminal_disposition": "blocked:unsupported_adapter",
                }
            )
            continue
        parse_status, parse_error = _parse_surface(path, adapter)
        row: dict[str, Any] = {
            "item_id": f"inventory:{relative}",
            "path": relative,
            "adapter_id": adapter,
            "kind": "implementation" if adapter == "python" else "resource_or_contract",
            "fingerprint": _sha256(path),
            "parse_status": parse_status,
            "terminal_disposition": "admitted" if parse_status != "blocked" else "blocked:parse_error",
        }
        if parse_error:
            row["parse_error"] = parse_error
            gaps.append({"code": "inventory_parse_error", "path": relative, "detail": parse_error})
        rows.append(row)
    for relative in (*REPOSITORY_BOUNDARY_ROOTS, *REPOSITORY_BOUNDARY_FILES):
        path = root_path / relative
        if not path.exists():
            gaps.append({"code": "inventory_boundary_missing", "path": relative})
    rows.sort(key=lambda row: str(row["path"]))
    payload = {
        "schema_version": "researchguard.provider-neutral-inventory.v1",
        "boundary": {
            "roots": list(REPOSITORY_BOUNDARY_ROOTS),
            "root_files": list(REPOSITORY_BOUNDARY_FILES),
            "excluded_runtime_outputs": [*GENERATED_RUNTIME_PREFIXES, *GENERATED_RUNTIME_SUFFIXES],
        },
        "rows": rows,
        "gaps": gaps,
        "status": "ready" if not gaps and rows else "blocked",
        "ready": not gaps and bool(rows),
    }
    payload["counts"] = {
        "items": len(rows),
        "admitted": sum(row["terminal_disposition"] == "admitted" for row in rows),
        "blocked": sum(row["terminal_disposition"] != "admitted" for row in rows),
        "adapters": len({row["adapter_id"] for row in rows}),
    }
    canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["inventory_fingerprint"] = f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
    return payload


def _load_contract(root_path: Path) -> Mapping[str, Any]:
    try:
        return _object(json.loads((root_path / SOFTWARE_DNA_PATH).read_text(encoding="utf-8")), "software DNA contract")
    except (OSError, json.JSONDecodeError) as exc:
        raise SoftwareDnaError(str(exc)) from exc


def _all_models(contract: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    top = _rows(contract.get("models"), "models")
    by_id: dict[str, Mapping[str, Any]] = {str(row.get("model_id", "")): row for row in top}
    if len(by_id) != len(top) or any(not key for key in by_id):
        raise SoftwareDnaError("model identities are not unique")
    subtree_rows = _rows(contract.get("member_subtrees"), "member subtrees")
    seen_members: set[str] = set()
    for subtree in subtree_rows:
        member_id = str(subtree.get("member_model_id", ""))
        if member_id in seen_members:
            raise SoftwareDnaError(f"duplicate member subtree: {member_id}")
        seen_members.add(member_id)
        children = _rows(subtree.get("children"), f"{member_id} children")
        for child in children:
            child_id = str(child.get("model_id", ""))
            if not child_id or child_id in by_id:
                raise SoftwareDnaError(f"duplicate or empty recursive model id: {child_id}")
            by_id[child_id] = child
    if seen_members != set(MEMBER_MODEL_IDS):
        raise SoftwareDnaError("exactly four member subtrees are required")
    return tuple(by_id.values())


def _resolve_surface_owner(path: str, bindings: Sequence[Mapping[str, Any]], model_ids: set[str]) -> str:
    matches: list[tuple[int, Mapping[str, Any]]] = []
    for row in bindings:
        prefix = str(row.get("path_prefix", ""))
        owner = str(row.get("owner_id", ""))
        if owner not in model_ids:
            raise SoftwareDnaError(f"surface binding names unknown owner: {owner}")
        if prefix and not (path == prefix or path.startswith(prefix.rstrip("/") + "/")):
            continue
        matches.append((len(prefix), row))
    if not matches:
        raise SoftwareDnaError(f"no primary owner binding for inventory item: {path}")
    longest = max(length for length, _row in matches)
    winners = [row for length, row in matches if length == longest]
    if len(winners) != 1:
        raise SoftwareDnaError(f"ambiguous primary owner binding for inventory item: {path}")
    return str(winners[0]["owner_id"])


def _validate_transition(block_id: str, contract: Mapping[str, Any]) -> None:
    signature = _object(contract.get("signature"), f"{block_id} signature")
    for field in ("input", "state", "effect", "output", "completion"):
        _strings(signature.get(field), f"{block_id} signature {field}")
    transition = _object(contract.get("transition_contract"), f"{block_id} transition contract")
    for field in (
        "input",
        "pre_state",
        "expected_output",
        "post_state",
        "effect",
        "failure_class",
        "oracle",
    ):
        _strings(transition.get(field), f"{block_id} transition {field}")
    if not set(_strings(transition.get("input"), f"{block_id} transition input")).intersection(
        _strings(signature.get("input"), f"{block_id} signature input")
    ):
        raise SoftwareDnaError(f"{block_id} transition input is disconnected from its signature")


def _validate_block(root_path: Path, model: Mapping[str, Any], block: Mapping[str, Any], *, seen_code: list[tuple[str, str]], seen_tests: list[tuple[str, str]]) -> dict[str, Any]:
    model_id = str(model.get("model_id", ""))
    block_id = str(block.get("block_id", ""))
    if not block_id or not block_id.startswith(f"block:{model_id}:"):
        raise SoftwareDnaError(f"{model_id} has an invalid function-block identity")
    public_inputs = _strings(model.get("public_input_ids"), f"{model_id} public inputs")
    signature = _object(block.get("signature"), f"{block_id} signature")
    inputs = _strings(signature.get("input"), f"{block_id} input")
    if not set(inputs).intersection(public_inputs):
        raise SoftwareDnaError(f"{block_id} consumes no declared model input")
    _validate_transition(block_id, block)
    code = _bound_symbol(root_path, _object(block.get("code_owner"), f"{block_id} code owner"), f"{block_id} code owner")
    test = _test_binding(root_path, _object(block.get("test_binding"), f"{block_id} test binding"), f"{block_id} test binding")
    evidence_path = _evidence_binding(root_path, _object(block.get("evidence_binding"), f"{block_id} evidence binding"), f"{block_id} evidence binding")
    seen_code.append(code)
    seen_tests.append(test)
    bindings = _object(block.get("bindings"), f"{block_id} bindings")
    for field in ("intent_ids", "resource_ids", "topology_edge_ids", "public_surface_ids", "native_domain_ids", "external_interface_ids"):
        _strings(bindings.get(field), f"{block_id} {field}")
    return {
        "block_id": block_id,
        "model_id": model_id,
        "code": {"path": code[0], "symbol": code[1]},
        "test": {"path": test[0], "node_id": test[1]},
        "evidence_path": evidence_path,
        "binding_ids": [
            *[str(item) for item in bindings["intent_ids"]],
            *[str(item) for item in bindings["resource_ids"]],
            *[str(item) for item in bindings["topology_edge_ids"]],
            *[str(item) for item in bindings["public_surface_ids"]],
            *[str(item) for item in bindings["native_domain_ids"]],
            *[str(item) for item in bindings["external_interface_ids"]],
        ],
    }


def _build_indexes(models: Sequence[Mapping[str, Any]], blocks: Sequence[Mapping[str, Any]], inventory: Mapping[str, Any]) -> dict[str, Any]:
    model_by_id = {str(row["model_id"]): row for row in models}
    forward: dict[str, list[str]] = {}
    reverse: dict[str, list[str]] = {}
    edges: dict[str, set[str]] = {model_id: set() for model_id in model_by_id}
    for model in models:
        model_id = str(model["model_id"])
        parent = str(model.get("parent_model_id", ""))
        if parent:
            edges.setdefault(parent, set()).add(model_id)
            edges.setdefault(model_id, set()).add(parent)
    for block in blocks:
        owner = str(block["block_id"])
        model_id = str(block["model_id"])
        # A block is structurally owned by its model.  Keeping this edge in
        # both directions makes a root change reach all declared descendants,
        # while a leaf change remains local to its parent path.
        edges.setdefault(owner, set()).add(model_id)
        edges.setdefault(model_id, set()).add(owner)
        targets = [
            f"code:{block['code']['path']}#{block['code']['symbol']}",
            f"test:{block['test']['path']}::{block['test']['node_id']}",
            f"evidence:{block['evidence_path']}",
            *block["binding_ids"],
        ]
        forward[owner] = sorted(set(targets))
        for target in targets:
            reverse.setdefault(target, []).append(owner)
            edges.setdefault(owner, set()).add(target)
            edges.setdefault(target, set()).add(owner)
    owner_by_path = {str(row["path"]): str(row.get("owner_id", "")) for row in inventory.get("rows", []) if row.get("owner_id")}
    for path, owner in owner_by_path.items():
        item_id = f"inventory:{path}"
        reverse.setdefault(item_id, []).append(owner)
        edges.setdefault(item_id, set()).add(owner)
        edges.setdefault(owner, set()).add(item_id)
    for key in reverse:
        reverse[key] = sorted(set(reverse[key]))
    return {
        "forward": {key: values for key, values in sorted(forward.items())},
        "reverse": {key: values for key, values in sorted(reverse.items())},
        "known_ids": sorted(edges),
        "edges": {key: sorted(values) for key, values in sorted(edges.items())},
    }


def _flowguard_behavior_commitment_api() -> Any:
    """Load FlowGuard's public BCL APIs only when a BCL operation is requested.

    The software-DNA static contract deliberately remains usable with the
    source-only package.  Importing the optional BCL implementation here keeps
    that static check independent from whatever FlowGuard installation happens
    to be present, while every BCL operation still goes through FlowGuard's
    canonical dataclasses and parser.
    """

    try:
        from flowguard import behavior_commitment
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise SoftwareDnaError(f"flowguard behavior commitment API unavailable: {exc}") from exc
    return behavior_commitment


def _canonical_json_fingerprint(value: object) -> str:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(rendered.encode('utf-8')).hexdigest()}"


def _bcl_fingerprint(api: Any, ledger: Any) -> str:
    # FlowGuard intentionally returns the bare hexadecimal digest.  ResearchGuard
    # identities use the same sha256: prefix as its inventory and source rows.
    return f"sha256:{api.behavior_commitment_ledger_fingerprint(ledger)}"


def _canonical_bcl_envelope(value: str | Path | Mapping[str, Any]) -> tuple[Any, dict[str, Any], str]:
    """Load one exact current FlowGuard BCL envelope.

    FlowGuard's public ``from_mapping`` also accepts its historical direct
    payload shape.  ResearchGuard intentionally performs the envelope check
    before delegating to that parser, so a bare legacy object cannot become a
    current connection by accident.
    """

    api = _flowguard_behavior_commitment_api()
    path: Path | None = None
    if isinstance(value, (str, Path)):
        path = Path(value)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SoftwareDnaError(f"behavior commitment ledger is unreadable: {exc}") from exc
    elif isinstance(value, Mapping):
        raw = copy.deepcopy(dict(value))
    else:
        raise SoftwareDnaError("behavior commitment ledger must be a canonical envelope path or mapping")

    if not isinstance(raw, Mapping):
        raise SoftwareDnaError("behavior commitment ledger envelope must be an object")
    expected_fields = {"artifact_type", "schema_version", "format_version", "ledger"}
    actual_fields = set(raw)
    if "ledger" not in raw:
        raise SoftwareDnaError("behavior_ledger_bare_legacy_format: canonical envelope is required")
    if actual_fields != expected_fields:
        raise SoftwareDnaError("behavior_ledger_malformed: canonical envelope fields are not exact-current")
    if raw.get("artifact_type") != BCL_LEDGER_ARTIFACT_TYPE:
        raise SoftwareDnaError("behavior_ledger_artifact_type_invalid")
    if str(raw.get("schema_version")) != BCL_LEDGER_SCHEMA_VERSION:
        raise SoftwareDnaError("behavior_ledger_schema_invalid")
    if str(raw.get("format_version")) != BCL_LEDGER_FORMAT_VERSION:
        raise SoftwareDnaError("behavior_ledger_format_invalid")
    if not isinstance(raw.get("ledger"), Mapping):
        raise SoftwareDnaError("behavior_ledger_missing_nested_payload")

    try:
        # Use the official path reader for file input.  This keeps the source
        # path operation on exactly the same API as FlowGuard reverse joins.
        ledger = api.load_behavior_commitment_ledger(path) if path is not None else api.behavior_commitment_ledger_from_mapping(raw)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SoftwareDnaError(f"behavior_ledger_malformed: {exc}") from exc
    canonical = api.behavior_commitment_ledger_to_mapping(ledger)
    if canonical != dict(raw):
        raise SoftwareDnaError("behavior_ledger_noncanonical: envelope does not round-trip byte semantics")
    return ledger, canonical, _bcl_fingerprint(api, ledger)


def load_canonical_behavior_commitment_ledger(value: str | Path | Mapping[str, Any]) -> Any:
    """Return a FlowGuard ledger only when the exact current envelope parses."""

    ledger, _canonical, _fingerprint = _canonical_bcl_envelope(value)
    return ledger


def _software_dna_blocks(root_path: Path, contract: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    models = _all_models(contract)
    seen_code: list[tuple[str, str]] = []
    seen_tests: list[tuple[str, str]] = []
    blocks: list[Mapping[str, Any]] = []
    for model in models:
        for block in _rows(model.get("function_blocks"), f"{model.get('model_id')} function blocks"):
            blocks.append(
                _validate_block(
                    root_path,
                    model,
                    block,
                    seen_code=seen_code,
                    seen_tests=seen_tests,
                )
            )
    return tuple(blocks)


def _native_owner_snapshot(root_path: Path) -> tuple[tuple[str, ...], str]:
    path = root_path / NATIVE_OWNER_MANIFEST_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = _rows(raw.get("models"), "native owner manifest models")
    except (OSError, UnicodeError, json.JSONDecodeError, SoftwareDnaError) as exc:
        raise SoftwareDnaError(f"native_owner_manifest_invalid: {exc}") from exc
    owner_ids = tuple(str(row.get("model_id", "")) for row in rows)
    if len(owner_ids) != NATIVE_OWNER_COUNT or any(not item for item in owner_ids) or len(set(owner_ids)) != len(owner_ids):
        raise SoftwareDnaError(
            f"native_owner_count_invalid: expected {NATIVE_OWNER_COUNT} unique current owners, got {len(owner_ids)}"
        )
    return owner_ids, _sha256(path)


def _canonical_model_owner_id(raw_owner: object, model_ids: set[str]) -> str:
    text = str(raw_owner or "").strip().replace("\\", "/")
    if text.startswith("model:"):
        model_id = text.removeprefix("model:")
    elif text.startswith("models/software_dna/researchguard.json#"):
        model_id = text.split("#", 1)[1]
    elif text.startswith(".flowguard/models/owners/") and text.endswith("/model.py"):
        model_id = text.split("/", 4)[3]
    else:
        raise SoftwareDnaError("behavior_commitment_owner_noncanonical")
    if model_id not in model_ids:
        raise SoftwareDnaError(f"behavior_commitment_unknown_model_owner: {model_id}")
    return f"model:{model_id}"


def _source_ref_path_tokens(root_path: Path, source_ref: str) -> tuple[tuple[str, Path], ...]:
    tokens: list[tuple[str, Path]] = []
    for token in (part.strip() for part in str(source_ref).split(";") if part.strip()):
        path_text = token.split("#", 1)[0].strip().replace("\\", "/")
        if not path_text or Path(path_text).is_absolute() or path_text.startswith("../") or "/../" in f"/{path_text}/":
            raise SoftwareDnaError("behavior_commitment_source_foreign")
        path = (root_path / path_text).resolve()
        try:
            path.relative_to(root_path)
        except ValueError as exc:
            raise SoftwareDnaError("behavior_commitment_source_foreign") from exc
        if not path.is_file():
            raise SoftwareDnaError(f"behavior_commitment_source_missing: {path_text}")
        tokens.append((path_text, path))
    if not tokens:
        raise SoftwareDnaError("behavior_commitment_source_missing")
    return tuple(tokens)


def _source_content_fingerprint(paths: Sequence[tuple[str, Path]]) -> str:
    if len(paths) == 1:
        return _sha256(paths[0][1])
    return _canonical_json_fingerprint(
        [{"path": relative, "fingerprint": _sha256(path)} for relative, path in paths]
    )


def _candidate_lifecycle_envelope(api: Any) -> dict[str, dict[str, str]]:
    lanes = tuple(getattr(api, "BCL_LIFECYCLE_LANES", ()))
    required = str(getattr(api, "BCL_LIFECYCLE_REQUIRED", "required_and_covered"))
    not_applicable = str(getattr(api, "BCL_LIFECYCLE_NOT_APPLICABLE", "verified_not_applicable"))
    return {lane: {"status": not_applicable if lane == "ui" else required} for lane in lanes}


def _build_independent_behavior_inventory(
    api: Any,
    root_path: Path,
    blocks: Sequence[Mapping[str, Any]],
    inventory: Mapping[str, Any],
) -> Any:
    items: list[Any] = []
    item_cls = api.BehaviorInventoryItem
    for block in blocks:
        block_id = str(block["block_id"])
        code_path = str(block["code"]["path"])
        code_symbol = str(block["code"]["symbol"])
        code_file = root_path / code_path
        owner = f"model:{block['model_id']}"
        commitment_id = f"commitment:{block_id}"
        obligation_id = block_id
        intent_id = f"intent:{block_id}"
        items.append(
            item_cls(
                behavior_id=f"behavior:{block_id}",
                source_kind="implementation",
                source_ref=code_path,
                source_fingerprint=_sha256(code_file),
                public_surface=block_id,
                intent=f"Current implementation contract for {block_id}",
                success="the bound function returns its declared current contract result",
                errors=("native owner evidence is missing or fails closed",),
                recovery=("re-run the owning native check after source and evidence are current",),
                owner=owner,
                disposition=getattr(api, "BCL_BEHAVIOR_DISPOSITION_MODELED", "modeled"),
                intent_source_refs=(code_path,),
                function_id=f"function:{code_path}#{code_symbol}",
                route_id=f"route:{block_id}",
                obligation_ids=(obligation_id,),
                required_check_ids=(f"check:{block_id}",),
                test_refs=(f"test:{block['test']['path']}::{block['test']['node_id']}",),
                evidence_subject_ids=(f"evidence:{block['evidence_path']}",),
                oracle_ids=(f"oracle:{block_id}",),
                failure_case_ids=(f"failure:{block_id}",),
                recovery_case_ids=(f"recovery:{block_id}",),
                current_intent_fingerprint=_canonical_json_fingerprint({"intent": intent_id, "block": block_id}),
                lifecycle_envelope=_candidate_lifecycle_envelope(api),
                commitment_id=commitment_id,
                model_owner_id=owner,
                validation_boundary="ResearchGuard software-DNA source/model/code/test binding only",
                rationale="Independently enumerated from the provider-neutral inventory and the native 17-model contract.",
            )
        )
    return api.BehaviorInventory(
        inventory_id="researchguard-software-dna-behavior-inventory",
        project_boundary=root_path.as_posix(),
        current_revision=str(inventory.get("inventory_fingerprint", "")),
        discovery_owner="researchguard:provider-neutral-inventory",
        discovery_fingerprint=str(inventory.get("inventory_fingerprint", "")),
        discovery_evidence_ids=(f"software-dna-inventory:{inventory.get('inventory_fingerprint', '')}",),
        expected_behavior_ids=tuple(item.behavior_id for item in items),
        items=tuple(items),
        claim_boundary="Independent implementation behavior denominator only; it does not prove domain truth or current native execution.",
        metadata={"source": "provider-neutral-inventory", "model_boundary": "17"},
    )


def build_researchguard_behavior_commitment_candidate(root: str | Path) -> dict[str, Any]:
    """Build a private BCL candidate from the current 17-model DNA.

    The candidate is intentionally conservative: current native evidence is
    not fabricated.  It is suitable for a private qualification run and is
    expected to remain blocked until every obligation has a real current
    owner receipt.
    """

    root_path = Path(root).resolve()
    static = check_software_dna_contract(root_path)
    if not static.get("ready"):
        return {"status": "blocked", "ready": False, "gaps": [static.get("gap", {"code": "software_dna_contract_invalid"})]}
    try:
        api = _flowguard_behavior_commitment_api()
        contract = _load_contract(root_path)
        models = _all_models(contract)
        model_ids = {str(model["model_id"]) for model in models}
        blocks = _software_dna_blocks(root_path, contract)
        native_owner_ids, native_manifest_fingerprint = _native_owner_snapshot(root_path)
        inventory = static["inventory"]
        source_rows: list[Any] = []
        commitments: list[Any] = []
        evidence_cls = api.BehaviorEvidenceBinding
        source_cls = api.BehaviorSourceSurface
        commitment_cls = api.BehaviorCommitment
        for block in blocks:
            block_id = str(block["block_id"])
            commitment_id = f"commitment:{block_id}"
            intent_id = f"intent:{block_id}"
            owner = f"model:{block['model_id']}"
            code_path = str(block["code"]["path"])
            test_path = str(block["test"]["path"])
            evidence_path = str(block["evidence_path"])
            paths = (("code", code_path, "code"), ("test", test_path, "test"), ("evidence", evidence_path, "doc"))
            surface_ids: list[str] = []
            for kind, source_ref, surface_kind in paths:
                sid = f"surface:{kind}:{block_id}"
                surface_ids.append(sid)
                file_path = root_path / source_ref
                classification = (
                    getattr(api, "BCL_SOURCE_CLASSIFICATION_IMPLEMENTATION", "implementation")
                    if kind == "code"
                    else getattr(api, "BCL_SOURCE_CLASSIFICATION_TEST", "test")
                    if kind == "test"
                    else getattr(api, "BCL_SOURCE_CLASSIFICATION_GENERATED_EVIDENCE", "generated_evidence")
                )
                source_rows.append(
                    source_cls(
                        surface_id=sid,
                        surface_kind=surface_kind,
                        label=f"{kind} surface for {block_id}",
                        source_ref=source_ref,
                        source_system_id="researchguard-repository",
                        native_artifact_id=f"artifact:{kind}:{block_id}",
                        content_fingerprint=_sha256(file_path),
                        source_authority_role=getattr(api, "BCL_SOURCE_AUTHORITY_SUPPORTING", "supporting"),
                        source_classification=classification,
                        declared_semantics_fingerprint=_canonical_json_fingerprint({"block": block_id, "kind": kind}),
                        coverage_disposition=getattr(api, "BCL_DISPOSITION_MODELED", "modeled"),
                        commitment_ids=(commitment_id,),
                        business_intent_ids=(intent_id,),
                        freshness_state=getattr(api, "BCL_SOURCE_FRESHNESS_CURRENT", "current"),
                        validation_boundary="ResearchGuard software-DNA source binding only",
                        rationale="Bound to one native software-DNA function block.",
                        metadata={"live_source_identity": {"member_paths": [source_ref]}},
                    )
                )
            evidence = evidence_cls(
                model_obligation_ids=(block_id,),
                code_contract_ids=(f"code:{code_path}#{block['code']['symbol']}",),
                test_evidence_ids=(f"test:{test_path}::{block['test']['node_id']}",),
                evidence_state=getattr(api, "BCL_EVIDENCE_MISSING", "missing"),
                current=False,
                metadata={"native_evidence": []},
            )
            commitments.append(
                commitment_cls(
                    commitment_id=commitment_id,
                    business_intent_id=intent_id,
                    label=f"ResearchGuard software-DNA block {block_id}",
                    commitment_kind=getattr(api, "BCL_COMMITMENT_WORKFLOW", "workflow"),
                    behavior_plane="development_process",
                    actor_kind=getattr(api, "BCL_ACTOR_DEVELOPER", "developer"),
                    actor="ResearchGuard maintainer",
                    trigger=f"the native software-DNA contract evaluates {block_id}",
                    expected_result="the exact bound model/code/test/evidence chain is qualified",
                    failure_boundary="unknown, orphan, foreign, stale, malformed, or unproven evidence remains blocked",
                    preconditions=("current provider-neutral inventory", "current native model contract"),
                    expected_terminal="software-DNA qualification is ready or reports an explicit gap",
                    source_surface_ids=tuple(surface_ids),
                    source_refs=(code_path, test_path, evidence_path),
                    primary_owner_model_id=owner,
                    evidence=evidence,
                    validation_boundary="ResearchGuard software-DNA source/model/code/test binding only",
                    rationale="One real native function block maps to one real model owner and one explicit evidence obligation.",
                    metadata={"block_id": block_id, "native_owner_boundary": list(native_owner_ids)},
                )
            )
        behavior_inventory = _build_independent_behavior_inventory(api, root_path, blocks, inventory)
        base_ledger = api.BehaviorCommitmentLedger(
            ledger_id="researchguard-software-dna-bcl-candidate",
            project_boundary=root_path.as_posix(),
            current_revision=static["inventory"]["inventory_fingerprint"],
            commitments=tuple(commitments),
            source_surfaces=tuple(source_rows),
            subject_lane=getattr(api, "SUBJECT_NORMATIVE_TARGET", "normative_target"),
            expected_source_surface_ids=tuple(row.surface_id for row in source_rows),
            require_complete_source_inventory=True,
            independent_behavior_inventory=behavior_inventory,
            require_complete_behavior_inventory=True,
            expected_commitment_ids=tuple(item.commitment_id for item in commitments),
            expected_business_intent_ids=tuple(item.business_intent_id for item in commitments),
            claim_scope=getattr(api, "BCL_SCOPE_ROUTINE", "routine"),
            change_mode=getattr(api, "BCL_CHANGE_BOOTSTRAP_LEDGER", "bootstrap_ledger"),
            require_current_evidence=True,
            require_risk_gates_for_broad_claim=False,
            owner="model:researchguard-suite",
            validation_boundary="Current ResearchGuard provider-neutral software-DNA inventory and native 17-model contract",
            rationale="Private candidate only; no current native evidence is invented by this builder.",
            metadata={
                "connection_schema": BCL_CONNECTION_SCHEMA,
                "software_dna_contract_fingerprint": _sha256(root_path / SOFTWARE_DNA_PATH),
                "provider_neutral_inventory_fingerprint": str(inventory["inventory_fingerprint"]),
                "native_owner_manifest_fingerprint": native_manifest_fingerprint,
                "native_owner_ids": list(native_owner_ids),
                "software_dna_model_ids": sorted(model_ids),
                "software_dna_function_block_ids": sorted(str(item["block_id"]) for item in blocks),
                "native_evidence_status": "missing_until_real_owner_receipts_are_bound",
            },
        )
        live_audit = api.audit_behavior_commitment_source_inventory(base_ledger, root_path)
        source_by_id = {row.surface_id: row.to_dict() for row in base_ledger.source_surfaces}
        for identity in live_audit.surface_identities:
            row = source_by_id.get(identity.surface_id)
            if row is None:
                continue
            row["inventory_revision"] = live_audit.live_inventory_revision
            row["discovery_evidence_ids"] = [live_audit.live_discovery_evidence_id]
            row["metadata"] = {"live_source_identity": {"member_paths": [member.path for member in identity.members]}}
        final_surfaces = tuple(source_cls(**source_by_id[row.surface_id]) for row in base_ledger.source_surfaces)
        final_ledger = api.BehaviorCommitmentLedger(
            **{
                **base_ledger.to_dict(),
                "commitments": [item.to_dict() for item in base_ledger.commitments],
                "source_surfaces": [item.to_dict() for item in final_surfaces],
                "source_inventory_revision": live_audit.live_inventory_revision,
                "source_inventory_fingerprint": live_audit.live_inventory_fingerprint,
                "source_inventory_evidence_ids": [live_audit.live_discovery_evidence_id],
            }
        )
        envelope = api.behavior_commitment_ledger_to_mapping(final_ledger)
        return {
            "status": "candidate",
            "ready": False,
            "schema_version": BCL_CONNECTION_SCHEMA,
            "ledger": envelope,
            "ledger_fingerprint": _bcl_fingerprint(api, final_ledger),
            "counts": {
                "models": len(models),
                "function_blocks": len(blocks),
                "native_owner_count": len(native_owner_ids),
                "commitments": len(commitments),
                "source_surfaces": len(final_surfaces),
            },
            "gaps": [{"code": "current_native_evidence_missing", "message": "Candidate deliberately contains no fabricated native owner receipts."}],
            "claim_boundary": "Private BCL candidate only; current native evidence and reverse closure remain unproven.",
        }
    except (OSError, ValueError, TypeError, KeyError, SoftwareDnaError) as exc:
        return {
            "status": "blocked",
            "ready": False,
            "schema_version": BCL_CONNECTION_SCHEMA,
            "gaps": [{"code": "behavior_commitment_candidate_invalid", "message": str(exc)}],
        }


def _gap(code: str, message: str, **fields: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **fields}


def _native_evidence_records(evidence: Any) -> tuple[Mapping[str, Any], ...]:
    metadata = evidence.metadata if evidence is not None else {}
    raw = metadata.get("native_evidence", ()) if isinstance(metadata, Mapping) else ()
    if isinstance(raw, Mapping):
        rows: list[Mapping[str, Any]] = []
        for obligation_id, row in raw.items():
            if isinstance(row, Mapping):
                rows.append({"obligation_id": obligation_id, **dict(row)})
        return tuple(rows)
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return tuple(row for row in raw if isinstance(row, Mapping))
    return ()


def _qualify_native_evidence(root_path: Path, commitment: Any, block_id: str, native_owner_ids: set[str]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    evidence = commitment.evidence
    records = _native_evidence_records(evidence)
    matches = [row for row in records if str(row.get("obligation_id", "")) == block_id]
    if len(matches) != 1:
        gaps.append(_gap("behavior_commitment_evidence_missing", "each model obligation needs exactly one native evidence record", commitment_id=commitment.commitment_id, obligation_id=block_id))
        return gaps
    row = matches[0]
    native_owner = str(row.get("native_owner_id", ""))
    normalized_owner = native_owner.removeprefix("owner:").removeprefix("model:")
    if normalized_owner not in native_owner_ids:
        gaps.append(_gap("behavior_commitment_evidence_foreign_owner", "native evidence names an owner outside the current 10-owner manifest", commitment_id=commitment.commitment_id, obligation_id=block_id, native_owner_id=native_owner))
    if str(row.get("model_owner_id", row.get("model_id", ""))) not in {commitment.primary_owner_model_id, commitment.primary_owner_model_id.removeprefix("model:")}:
        gaps.append(_gap("behavior_commitment_evidence_model_mismatch", "native evidence model identity does not match the commitment's primary owner", commitment_id=commitment.commitment_id, obligation_id=block_id))
    if row.get("current") is not True or str(row.get("status", row.get("evidence_state", ""))) not in {"pass", "passed", "current_pass", "green"}:
        gaps.append(_gap("behavior_commitment_evidence_not_current", "native evidence must be explicitly current and passing", commitment_id=commitment.commitment_id, obligation_id=block_id))
    path_text = str(row.get("path", row.get("evidence_path", row.get("result_path", "")))).replace("\\", "/")
    if not path_text or Path(path_text).is_absolute() or path_text.startswith("../") or "/../" in f"/{path_text}/":
        gaps.append(_gap("behavior_commitment_evidence_foreign", "native evidence path is outside the ResearchGuard root", commitment_id=commitment.commitment_id, obligation_id=block_id))
        return gaps
    path = (root_path / path_text).resolve()
    try:
        path.relative_to(root_path)
    except ValueError:
        gaps.append(_gap("behavior_commitment_evidence_foreign", "native evidence path resolves outside the ResearchGuard root", commitment_id=commitment.commitment_id, obligation_id=block_id))
        return gaps
    if not path.is_file():
        gaps.append(_gap("behavior_commitment_evidence_missing", "native evidence file is missing", commitment_id=commitment.commitment_id, obligation_id=block_id, path=path_text))
        return gaps
    expected = str(row.get("fingerprint", row.get("content_fingerprint", "")))
    actual = _sha256(path)
    if expected != actual:
        gaps.append(_gap("behavior_commitment_evidence_tampered", "native evidence bytes do not match the recorded fingerprint", commitment_id=commitment.commitment_id, obligation_id=block_id, path=path_text))
    return gaps


def qualify_researchguard_behavior_commitment_ledger(
    root: str | Path,
    source: str | Path | Mapping[str, Any],
    *,
    indexes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Qualify one canonical BCL against the current 17-model DNA.

    This is a qualification report, not an alternate FlowGuard model.  The
    ten native FlowGuard owners are only evidence producers; the 17 Research-
    Guard model IDs remain the software-DNA ownership denominator.
    """

    root_path = Path(root).resolve()
    gaps: list[dict[str, Any]] = []
    static = check_software_dna_contract(root_path)
    if not static.get("ready"):
        gaps.append(_gap("software_dna_contract_invalid", "current 17-model software-DNA contract is not ready"))
        return {"schema_version": BCL_CONNECTION_SCHEMA, "status": "blocked", "ready": False, "gaps": gaps, "indexes": {}}
    try:
        api = _flowguard_behavior_commitment_api()
        ledger, canonical, ledger_fingerprint = _canonical_bcl_envelope(source)
        contract = _load_contract(root_path)
        models = _all_models(contract)
        model_ids = {str(model["model_id"]) for model in models}
        blocks = _software_dna_blocks(root_path, contract)
        block_by_id = {str(block["block_id"]): block for block in blocks}
        native_owner_ids, native_manifest_fingerprint = _native_owner_snapshot(root_path)
        metadata = ledger.metadata if isinstance(ledger.metadata, Mapping) else {}
        if str(metadata.get("connection_schema", "")) != BCL_CONNECTION_SCHEMA:
            gaps.append(_gap("behavior_ledger_connection_schema_missing", "ledger does not identify the ResearchGuard BCL connection schema"))
        if str(metadata.get("software_dna_contract_fingerprint", "")) != _sha256(root_path / SOFTWARE_DNA_PATH):
            gaps.append(_gap("software_dna_source_identity_stale", "ledger was built from a different software-DNA contract"))
        if str(metadata.get("provider_neutral_inventory_fingerprint", "")) != str(static["inventory"].get("inventory_fingerprint", "")):
            gaps.append(_gap("software_dna_inventory_identity_stale", "ledger was built from a different provider-neutral inventory"))
        if str(metadata.get("native_owner_manifest_fingerprint", "")) != native_manifest_fingerprint:
            gaps.append(_gap("native_owner_identity_stale", "ledger was built from a different 10-owner manifest"))
        recorded_models = tuple(str(item) for item in metadata.get("software_dna_model_ids", ()))
        if set(recorded_models) != model_ids or len(recorded_models) != len(model_ids):
            gaps.append(_gap("software_dna_model_identity_mismatch", "ledger model identity set is not the current 17-model set"))
        if len(models) != 17 or len(blocks) != 20:
            gaps.append(_gap("software_dna_denominator_count_mismatch", "ResearchGuard software-DNA denominator must remain 17 models and 20 function blocks"))
        commitments = tuple(ledger.commitments)
        commitment_ids = [str(item.commitment_id) for item in commitments]
        if len(commitments) != 20 or len(set(commitment_ids)) != len(commitment_ids):
            gaps.append(_gap("behavior_commitment_count_or_identity_mismatch", "BCL must contain one unique commitment for each of the 20 native function blocks"))
        obligation_to_commitment: dict[str, str] = {}
        seen_intents: set[str] = set()
        for commitment in commitments:
            cid = str(commitment.commitment_id)
            if not commitment.business_intent_id:
                gaps.append(_gap("behavior_commitment_intent_missing", "every commitment needs one business intent", commitment_id=cid))
            elif commitment.business_intent_id in seen_intents:
                gaps.append(_gap("behavior_commitment_duplicate_intent", "one business intent cannot close two commitments", commitment_id=cid, business_intent_id=commitment.business_intent_id))
            seen_intents.add(commitment.business_intent_id)
            try:
                owner = _canonical_model_owner_id(commitment.primary_owner_model_id, model_ids)
            except SoftwareDnaError as exc:
                gaps.append(_gap(str(exc).split(":", 1)[0], str(exc), commitment_id=cid, owner=commitment.primary_owner_model_id))
                owner = ""
            if owner and commitment.primary_owner_model_id != owner:
                gaps.append(_gap("behavior_commitment_owner_noncanonical", "primary owner must be stored in canonical model:<id> form", commitment_id=cid))
            if owner and (owner in commitment.supporting_model_ids or owner in commitment.child_model_ids):
                gaps.append(_gap("behavior_commitment_multiple_primary_owners", "primary owner cannot also be supporting or child owner", commitment_id=cid))
            evidence = commitment.evidence
            obligations = tuple(str(item) for item in evidence.model_obligation_ids)
            if not obligations:
                gaps.append(_gap("behavior_commitment_empty_obligation", "every commitment needs a real model obligation", commitment_id=cid))
            if len(obligations) != len(set(obligations)):
                gaps.append(_gap("behavior_commitment_duplicate_obligation", "one commitment repeats a model obligation", commitment_id=cid))
            for obligation in obligations:
                if obligation in obligation_to_commitment:
                    gaps.append(_gap("behavior_commitment_duplicate_obligation", "one model obligation cannot close multiple commitments", obligation_id=obligation, commitment_id=cid))
                obligation_to_commitment[obligation] = cid
                if obligation not in block_by_id:
                    gaps.append(_gap("behavior_commitment_unknown_obligation", "model obligation is not one of the current 20 native function blocks", commitment_id=cid, obligation_id=obligation))
            if len(commitment.source_surface_ids) == 0:
                gaps.append(_gap("behavior_commitment_source_missing", "commitment has no source surfaces", commitment_id=cid))
            expected_blocks = [block_by_id[item] for item in obligations if item in block_by_id]
            if len(expected_blocks) == 1:
                block = expected_blocks[0]
                expected_code = f"code:{block['code']['path']}#{block['code']['symbol']}"
                expected_test = f"test:{block['test']['path']}::{block['test']['node_id']}"
                if tuple(evidence.code_contract_ids) != (expected_code,):
                    gaps.append(_gap("behavior_commitment_code_binding_mismatch", "code contract does not bind the named model block", commitment_id=cid))
                if tuple(evidence.test_evidence_ids) != (expected_test,):
                    gaps.append(_gap("behavior_commitment_test_binding_mismatch", "test evidence does not bind the named model block", commitment_id=cid))
                gaps.extend(_qualify_native_evidence(root_path, commitment, obligations[0], set(native_owner_ids)))
        expected_obligations = set(block_by_id)
        if set(obligation_to_commitment) != expected_obligations:
            gaps.append(_gap("behavior_commitment_obligation_denominator_mismatch", "BCL obligations do not exactly cover the current 20 function blocks"))
        surface_by_id = {str(surface.surface_id): surface for surface in ledger.source_surfaces}
        for surface_id, surface in surface_by_id.items():
            if len(surface.commitment_ids) != 1:
                gaps.append(_gap("behavior_commitment_surface_mapping_invalid", "each source surface must map to one real commitment", surface_id=surface_id))
            try:
                live_paths = _source_ref_path_tokens(root_path, surface.source_ref)
                live_fingerprint = _source_content_fingerprint(live_paths)
                if surface.content_fingerprint != live_fingerprint:
                    gaps.append(_gap("behavior_commitment_source_tampered", "source surface fingerprint does not match current bytes", surface_id=surface_id))
            except SoftwareDnaError as exc:
                code = str(exc).split(":", 1)[0]
                gaps.append(_gap(code if code.startswith("behavior_commitment_source_") else "behavior_commitment_source_invalid", str(exc), surface_id=surface_id))
            if surface.freshness_state != getattr(api, "BCL_SOURCE_FRESHNESS_CURRENT", "current"):
                gaps.append(_gap("behavior_commitment_source_stale", "source surface is not marked current", surface_id=surface_id))
            for commitment_id in surface.commitment_ids:
                if commitment_id not in commitment_ids:
                    gaps.append(_gap("behavior_commitment_source_foreign", "source surface points to an unknown commitment", surface_id=surface_id, commitment_id=commitment_id))
                elif surface_id not in next(item for item in commitments if item.commitment_id == commitment_id).source_surface_ids:
                    gaps.append(_gap("behavior_commitment_source_reverse_missing", "source-to-commitment mapping is not bidirectional", surface_id=surface_id, commitment_id=commitment_id))
        for commitment in commitments:
            for surface_id in commitment.source_surface_ids:
                if surface_id not in surface_by_id:
                    gaps.append(_gap("behavior_commitment_source_foreign", "commitment points to an unknown source surface", commitment_id=commitment.commitment_id, surface_id=surface_id))

        try:
            official = api.review_behavior_commitment_ledger(ledger, project_root=root_path)
            official_dict = official.to_dict()
            for finding in official.findings:
                # Keep official FlowGuard findings visible, even when a local
                # exact identity check already reported the same underlying gap.
                gaps.append(_gap(finding.code, finding.message, commitment_id=finding.commitment_id, surface_id=finding.surface_id, authority="flowguard"))
        except (ValueError, TypeError, OSError, KeyError) as exc:
            official_dict = {"ok": False, "findings": [], "error": str(exc)}
            gaps.append(_gap("behavior_ledger_flowguard_review_failed", str(exc)))

        report = {
            "schema_version": BCL_CONNECTION_SCHEMA,
            "status": "ready" if not gaps else "blocked",
            "ready": not gaps,
            "ledger": {
                "ledger_id": ledger.ledger_id,
                "current_revision": ledger.current_revision,
                "fingerprint": ledger_fingerprint,
            },
            "counts": {
                "models": len(models),
                "function_blocks": len(blocks),
                "native_owner_count": len(native_owner_ids),
                "commitments": len(commitments),
                "source_surfaces": len(surface_by_id),
                "obligations": len(obligation_to_commitment),
            },
            "gaps": gaps,
            "flowguard_review": official_dict,
            "claim_boundary": "ResearchGuard software-DNA BCL connection only; it does not prove LogicGuard, SourceGuard, TraceGuard, or ExperimentGuard domain truth.",
            "canonical_envelope": canonical,
        }
        if not gaps:
            report["indexes"] = connect_behavior_commitment_indexes(indexes or static["indexes"], report)
        else:
            report["indexes"] = {}
        return report
    except (OSError, ValueError, TypeError, KeyError, SoftwareDnaError) as exc:
        message = str(exc)
        token = message.split(":", 1)[0]
        error_code = token if re.fullmatch(r"[a-z][a-z0-9_]+", token) and token.startswith(("behavior_", "software_dna_", "native_owner_")) else "behavior_ledger_invalid"
        return {
            "schema_version": BCL_CONNECTION_SCHEMA,
            "status": "blocked",
            "ready": False,
            "gaps": [_gap(error_code, message)],
            "indexes": {},
        }


def connect_behavior_commitment_indexes(indexes: Mapping[str, Any], qualification: Mapping[str, Any]) -> dict[str, Any]:
    """Add BCL edges only after a complete current qualification."""

    if qualification.get("ready") is not True:
        return {}
    result = copy.deepcopy(dict(indexes))
    forward = {str(key): list(value) for key, value in _object(result.get("forward"), "software DNA forward index").items()}
    reverse = {str(key): list(value) for key, value in _object(result.get("reverse"), "software DNA reverse index").items()}
    edges = {str(key): set(value) for key, value in _object(result.get("edges"), "software DNA index edges").items()}
    canonical = _object(qualification.get("canonical_envelope"), "qualified canonical BCL envelope")
    ledger = _object(canonical.get("ledger"), "qualified BCL payload")
    ledger_fp = str(_object(qualification.get("ledger"), "qualified BCL identity").get("fingerprint", ""))
    for commitment in _rows(ledger.get("commitments"), "qualified BCL commitments"):
        cid = str(commitment.get("commitment_id", ""))
        bcl_id = f"bcl:{cid}"
        targets = [str(commitment.get("primary_owner_model_id", "")), *[str(item) for item in commitment.get("source_surface_ids", ())]]
        evidence = _object(commitment.get("evidence"), f"{cid} evidence")
        targets.extend(str(item) for item in evidence.get("model_obligation_ids", ()))
        targets.extend(str(item) for item in evidence.get("code_contract_ids", ()))
        targets.extend(str(item) for item in evidence.get("test_evidence_ids", ()))
        forward[bcl_id] = sorted(set(targets))
        edges.setdefault(bcl_id, set())
        for target in forward[bcl_id]:
            edges.setdefault(target, set())
            edges[bcl_id].add(target)
            edges[target].add(bcl_id)
            reverse.setdefault(target, []).append(bcl_id)
    result["forward"] = {key: sorted(set(value)) for key, value in sorted(forward.items())}
    result["reverse"] = {key: sorted(set(value)) for key, value in sorted(reverse.items())}
    result["edges"] = {key: sorted(value) for key, value in sorted(edges.items())}
    result["known_ids"] = sorted(result["edges"])
    result["behavior_commitment_ledger"] = {"status": "ready", "fingerprint": ledger_fp}
    return result


def software_dna_affected_closure(
    indexes: Mapping[str, Any],
    changed_ids: Iterable[str],
    *,
    expected_bcl_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Close only declared affected edges; unknown identities block."""

    if expected_bcl_fingerprint is not None:
        observed_bcl = _object(indexes.get("behavior_commitment_ledger"), "software DNA behavior commitment ledger identity")
        observed_fingerprint = str(observed_bcl.get("fingerprint", ""))
        if observed_fingerprint != expected_bcl_fingerprint:
            return {
                "status": "blocked",
                "mode": "affected_only",
                "full_denominator_materialized": False,
                "gap": {"code": "behavior_ledger_replaced", "expected": expected_bcl_fingerprint, "observed": observed_fingerprint},
                "affected_ids": [],
            }

    graph = _object(indexes.get("edges"), "software DNA index edges")
    seeds = tuple(str(item) for item in changed_ids)
    unknown = sorted(set(seeds) - set(graph))
    if unknown:
        return {
            "status": "blocked",
            "mode": "affected_only",
            "full_denominator_materialized": False,
            "gap": {"code": "unknown_affected_identity", "ids": unknown},
            "affected_ids": [],
        }
    seen: set[str] = set(seeds)
    queue: deque[str] = deque(seeds)
    while queue:
        current = queue.popleft()
        neighbors = graph.get(current, ())
        if not isinstance(neighbors, Sequence) or isinstance(neighbors, (str, bytes)):
            return {"status": "blocked", "mode": "affected_only", "full_denominator_materialized": False, "gap": {"code": "malformed_affected_edge", "id": current}, "affected_ids": []}
        for neighbor in neighbors:
            target = str(neighbor)
            if target not in graph:
                return {"status": "blocked", "mode": "affected_only", "full_denominator_materialized": False, "gap": {"code": "dangling_affected_edge", "id": target}, "affected_ids": []}
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return {
        "status": "ready",
        "mode": "affected_only",
        "full_denominator_materialized": False,
        "seed_ids": list(seeds),
        "affected_ids": sorted(seen),
    }


def software_dna_reverse_trace(
    indexes: Mapping[str, Any],
    target_id: str,
    *,
    expected_bcl_fingerprint: str | None = None,
) -> dict[str, Any]:
    if expected_bcl_fingerprint is not None:
        observed_bcl = _object(indexes.get("behavior_commitment_ledger"), "software DNA behavior commitment ledger identity")
        observed_fingerprint = str(observed_bcl.get("fingerprint", ""))
        if observed_fingerprint != expected_bcl_fingerprint:
            return {
                "status": "blocked",
                "gap": {"code": "behavior_ledger_replaced", "expected": expected_bcl_fingerprint, "observed": observed_fingerprint},
                "owners": [],
            }
    reverse = _object(indexes.get("reverse"), "software DNA reverse index")
    if target_id not in reverse:
        return {"status": "blocked", "gap": {"code": "unknown_reverse_identity", "id": target_id}, "owners": []}
    return {"status": "ready", "target_id": target_id, "owners": list(reverse[target_id])}


def _readiness(statuses: Mapping[str, tuple[bool, str]]) -> dict[str, Any]:
    layers: list[dict[str, Any]] = []
    deepest = ""
    first_gap = ""
    prior_passed = True
    for layer in READINESS_LAYERS:
        passed, gap = statuses.get(layer, (False, "not_checked"))
        if not prior_passed:
            layers.append({"layer": layer, "status": "not_run", "gap": ""})
            continue
        if passed:
            layers.append({"layer": layer, "status": "pass", "gap": ""})
            deepest = layer
            continue
        first_gap = gap or layer
        layers.append({"layer": layer, "status": "blocked", "gap": first_gap})
        prior_passed = False
    return {
        "status": "ready" if not first_gap else "blocked",
        "layers": layers,
        "deepest_proven_layer": deepest,
        "first_gap": first_gap,
        "gap_count": sum(1 for _layer, (passed, _gap) in statuses.items() if not passed),
    }


def check_software_dna_contract(root: str | Path) -> dict[str, Any]:
    """Check recursive native DNA, independent inventory, and indexes."""

    root_path = Path(root).resolve()
    inventory: dict[str, Any] | None = None
    try:
        contract = _load_contract(root_path)
        if contract.get("schema_version") != SOFTWARE_DNA_SCHEMA:
            raise SoftwareDnaError("software DNA schema is not current")
        if contract.get("dna_id") != "software-dna:researchguard":
            raise SoftwareDnaError("software DNA identity is not ResearchGuard")
        if contract.get("system_model_id") != ROOT_MODEL_ID:
            raise SoftwareDnaError("software DNA has no single ResearchGuard suite root")
        canonical_boundary = _object(contract.get("canonical_boundary"), "canonical boundary")
        if canonical_boundary.get("model_and_bindings") != "native_repository_model_directory":
            raise SoftwareDnaError("canonical model/bindings must remain native source")
        if canonical_boundary.get("current_pointer") != "external_content_addressed_projection":
            raise SoftwareDnaError("canonical current pointer must remain external")
        if canonical_boundary.get("generated_outputs_in_denominator") is not False:
            raise SoftwareDnaError("generated canonical outputs may not enter the denominator")
        if canonical_boundary.get("self_fingerprint_cycle") != "blocked":
            raise SoftwareDnaError("self-fingerprint cycles must be blocked")
        if canonical_boundary.get("archive_self_authentication") != "external_receipt_only":
            raise SoftwareDnaError("an archive may not authenticate itself")
        if canonical_boundary.get("transport_evidence") != "content_addressed_external":
            raise SoftwareDnaError("transport evidence must remain external and content-addressed")

        denominator = _object(contract.get("denominator"), "denominator")
        included_roots = _strings(denominator.get("included_roots"), "included roots")
        if tuple(included_roots) != tuple(REPOSITORY_BOUNDARY_ROOTS):
            raise SoftwareDnaError("software DNA denominator roots do not match the provider boundary")
        included_files = _strings(denominator.get("included_root_files"), "included root files")
        if tuple(included_files) != tuple(REPOSITORY_BOUNDARY_FILES):
            raise SoftwareDnaError("software DNA root-file denominator is incomplete or foreign")
        excluded = _strings(denominator.get("excluded_runtime_outputs"), "excluded runtime outputs")
        if not all(
            any(
                item.rstrip("/") == prefix.rstrip("/")
                or item.startswith(prefix)
                or prefix.rstrip("/") in item
                for prefix in GENERATED_RUNTIME_PREFIXES + GENERATED_RUNTIME_SUFFIXES
            )
            for item in excluded
        ):
            raise SoftwareDnaError("runtime exclusions may not remove source authority")

        adapters = _rows(contract.get("external_target_adapters"), "external target adapters")
        adapter_ids = tuple(str(row.get("adapter_id", "")) for row in adapters)
        if tuple(sorted(adapter_ids)) != tuple(sorted(REQUIRED_TARGET_ADAPTERS)):
            raise SoftwareDnaError("provider-neutral external target adapters are incomplete")
        for row in adapters:
            _strings(row.get("selector_kinds"), f"adapter {row.get('adapter_id')} selectors")
            if not str(row.get("claim_boundary", "")):
                raise SoftwareDnaError("every target adapter needs a claim boundary")
        adapter_contract = _rows(contract.get("inventory_adapters"), "inventory adapters")
        adapter_contract_ids = tuple(str(row.get("adapter_id", "")) for row in adapter_contract)
        if tuple(sorted(adapter_contract_ids)) != tuple(sorted(REQUIRED_INVENTORY_ADAPTERS)):
            raise SoftwareDnaError("provider-neutral inventory adapters are incomplete")
        for row in adapter_contract:
            if not str(row.get("claim_boundary", "")) or not str(row.get("surface_kind", "")):
                raise SoftwareDnaError("every inventory adapter needs a kind and claim boundary")

        top_models = _rows(contract.get("models"), "models")
        top_by_id = {str(row.get("model_id", "")): row for row in top_models}
        if set(top_by_id) != {ROOT_MODEL_ID, *MEMBER_MODEL_IDS} or len(top_by_id) != len(top_models):
            raise SoftwareDnaError("software DNA must contain one root and exactly four member roots")
        root_model = top_by_id[ROOT_MODEL_ID]
        if str(root_model.get("parent_model_id", "")):
            raise SoftwareDnaError("the suite root cannot have a structural parent")
        child_ids = _strings(root_model.get("child_model_ids"), "root child model ids")
        if set(child_ids) != set(MEMBER_MODEL_IDS):
            raise SoftwareDnaError("the suite root must own exactly four member subtrees")
        for member_id in MEMBER_MODEL_IDS:
            if top_by_id[member_id].get("parent_model_id") != ROOT_MODEL_ID:
                raise SoftwareDnaError(f"{member_id} is not attached to the suite root")
            if not _strings(top_by_id[member_id].get("child_model_ids"), f"{member_id} child ids"):
                raise SoftwareDnaError(f"{member_id} must be recursively decomposed")
        models = _all_models(contract)
        model_by_id = {str(row["model_id"]): row for row in models}
        if len(model_by_id) != len(models):
            raise SoftwareDnaError("recursive model identities are not unique")
        roots = [row for row in models if not str(row.get("parent_model_id", ""))]
        if [str(row.get("model_id")) for row in roots] != [ROOT_MODEL_ID]:
            raise SoftwareDnaError("recursive model tree has more than one structural root")
        for member_id in MEMBER_MODEL_IDS:
            children = tuple(str(item) for item in top_by_id[member_id]["child_model_ids"])
            subtree = next(row for row in _rows(contract["member_subtrees"], "member subtrees") if row.get("member_model_id") == member_id)
            actual = tuple(str(child.get("model_id", "")) for child in _rows(subtree.get("children"), f"{member_id} children"))
            if actual != children:
                raise SoftwareDnaError(f"{member_id} recursive child index is not exact-current")
            for child_id in children:
                if model_by_id[child_id].get("parent_model_id") != member_id:
                    raise SoftwareDnaError(f"{child_id} has the wrong recursive parent")

        bindings = _rows(contract.get("surface_bindings"), "surface bindings")
        if not any(str(row.get("path_prefix", "")) == "" for row in bindings):
            raise SoftwareDnaError("surface bindings need one explicit repository-root rule")
        seen_prefixes: set[str] = set()
        for row in bindings:
            prefix = str(row.get("path_prefix", ""))
            if prefix in seen_prefixes:
                raise SoftwareDnaError(f"duplicate surface binding prefix: {prefix}")
            seen_prefixes.add(prefix)

        seen_code: list[tuple[str, str]] = []
        seen_tests: list[tuple[str, str]] = []
        blocks: list[dict[str, Any]] = []
        for model in models:
            for block in _rows(model.get("function_blocks"), f"{model.get('model_id')} function blocks"):
                blocks.append(_validate_block(root_path, model, block, seen_code=seen_code, seen_tests=seen_tests))
        duplicate_code = [item for item, count in Counter(seen_code).items() if count > 1]
        if duplicate_code:
            raise SoftwareDnaError(f"code symbols have duplicate primary owners: {duplicate_code!r}")
        duplicate_tests = [item for item, count in Counter(seen_tests).items() if count > 1]
        if duplicate_tests:
            raise SoftwareDnaError(f"tests have duplicate primary model owners: {duplicate_tests!r}")

        public_outputs = {str(model["model_id"]): _strings(model.get("public_output_ids"), f"{model['model_id']} public outputs") for model in models}
        public_inputs = {str(model["model_id"]): set(_strings(model.get("public_input_ids"), f"{model['model_id']} public inputs")) for model in models}
        interfaces = _rows(contract.get("child_interface_bindings"), "child interface bindings")
        expected_interfaces = {
            (child_id, output_id)
            for child_id, outputs in public_outputs.items()
            for output_id in outputs
            if child_id != ROOT_MODEL_ID
        }
        observed_interfaces: set[tuple[str, str]] = set()
        for row in interfaces:
            child_id = str(row.get("child_model_id", ""))
            output_id = str(row.get("child_output_id", ""))
            parent_id = str(row.get("parent_model_id", ""))
            parent_input = str(row.get("parent_input_id", ""))
            if child_id not in public_outputs or output_id not in public_outputs[child_id]:
                raise SoftwareDnaError("child interface binds an unknown child output")
            if parent_id not in public_inputs or parent_input not in public_inputs[parent_id]:
                raise SoftwareDnaError("child interface does not terminate at a declared parent input")
            if not str(row.get("disposition", "")):
                raise SoftwareDnaError("child output requires one parent disposition")
            observed_interfaces.add((child_id, output_id))
        if observed_interfaces != expected_interfaces or len(interfaces) != len(observed_interfaces):
            raise SoftwareDnaError("parent/member interfaces are not exhaustive and exact-current")

        inventory = build_provider_neutral_inventory(root_path)
        if not inventory["ready"]:
            raise SoftwareDnaError("provider-neutral denominator is blocked: " + ", ".join(gap["code"] for gap in inventory["gaps"][:4]))
        for row in inventory["rows"]:
            owner_id = _resolve_surface_owner(str(row["path"]), bindings, set(model_by_id))
            row["owner_id"] = owner_id
            row["terminal_disposition"] = "admitted:owned"
        indexes = _build_indexes(models, blocks, inventory)
        index_contract = _object(contract.get("index_contract"), "index contract")
        for field in ("forward_kinds", "reverse_kinds", "affected_closure_kinds"):
            expected = INDEX_KINDS if field != "affected_closure_kinds" else ("parents", "children", "readers", "writers", "consumers", "tests", "handoffs", "resources", "topology_dependents")
            if tuple(_strings(index_contract.get(field), f"index contract {field}")) != tuple(expected):
                raise SoftwareDnaError(f"index contract {field} is incomplete")
        if set(indexes["known_ids"]) != set(indexes["edges"]):
            raise SoftwareDnaError("affected/reverse index contains dangling ids")
        claim_boundary = str(contract.get("claim_boundary", ""))
        if not claim_boundary:
            raise SoftwareDnaError("software DNA requires an explicit claim boundary")
        statuses = {
            "evidence_qualification": (all(str(block["evidence_path"]) for block in blocks), "evidence_binding_missing"),
            "implementation_inventory": (bool(inventory["ready"]), "provider_neutral_denominator_blocked"),
            "traceability": (bool(indexes["forward"]) and bool(indexes["reverse"]), "binding_index_incomplete"),
            "independent_semantics": (set(top_by_id) == {ROOT_MODEL_ID, *MEMBER_MODEL_IDS}, "root_member_semantics_incomplete"),
            "model_code_test_binding": (len(blocks) == len(seen_code) == len(seen_tests), "model_code_test_binding_incomplete"),
            "resource_oracle_binding": (all(str(binding) for block in blocks for binding in block["binding_ids"]), "resource_oracle_binding_incomplete"),
            "static_blueprint_readiness": (bool(interfaces) and len(observed_interfaces) == len(expected_interfaces), "static_blueprint_incomplete"),
        }
        readiness = _readiness(statuses)
        report = {
            "schema_version": SOFTWARE_DNA_SCHEMA,
            "dna_id": contract["dna_id"],
            "status": "ready" if readiness["status"] == "ready" else "blocked",
            "ready": readiness["status"] == "ready",
            "contract_path": SOFTWARE_DNA_PATH.as_posix(),
            "system_model_id": ROOT_MODEL_ID,
            "member_model_ids": list(MEMBER_MODEL_IDS),
            "recursive_model_ids": sorted(model_by_id),
            "readiness": readiness,
            "inventory": inventory,
            "indexes": indexes,
            "counts": {
                "models": len(models),
                "top_level_models": len(top_models),
                "recursive_models": len(models) - len(top_models),
                "function_blocks": len(blocks),
                "code_bindings": len(seen_code),
                "test_bindings": len(seen_tests),
                "evidence_bindings": len(blocks),
                "child_interface_bindings": len(interfaces),
                "target_adapters": len(adapters),
                "inventory_adapters": len(adapter_contract),
                "denominator_roots": len(included_roots),
                "denominator_root_files": len(included_files),
                "denominator_items": inventory["counts"]["items"],
            },
            "claim_boundary": claim_boundary,
        }
        return report
    except (OSError, json.JSONDecodeError, SoftwareDnaError) as exc:
        return {
            "schema_version": SOFTWARE_DNA_SCHEMA,
            "dna_id": "software-dna:researchguard",
            "status": "blocked",
            "ready": False,
            "contract_path": SOFTWARE_DNA_PATH.as_posix(),
            "readiness": {
                "status": "blocked",
                "layers": [{"layer": layer, "status": "blocked", "gap": "software_dna_contract_invalid"} for layer in READINESS_LAYERS],
                "deepest_proven_layer": "",
                "first_gap": "software_dna_contract_invalid",
                "gap_count": 1,
            },
            "gap": {"code": "software_dna_contract_invalid", "message": str(exc)},
        }


__all__ = [
    "BCL_CONNECTION_SCHEMA",
    "INDEX_KINDS",
    "MEMBER_MODEL_IDS",
    "NATIVE_OWNER_COUNT",
    "NATIVE_OWNER_MANIFEST_PATH",
    "READINESS_LAYERS",
    "REPOSITORY_BOUNDARY_FILES",
    "REPOSITORY_BOUNDARY_ROOTS",
    "ROOT_MODEL_ID",
    "SOFTWARE_DNA_PATH",
    "SOFTWARE_DNA_SCHEMA",
    "SoftwareDnaError",
    "build_researchguard_behavior_commitment_candidate",
    "build_provider_neutral_inventory",
    "check_software_dna_contract",
    "connect_behavior_commitment_indexes",
    "load_canonical_behavior_commitment_ledger",
    "qualify_researchguard_behavior_commitment_ledger",
    "software_dna_affected_closure",
    "software_dna_reverse_trace",
]
