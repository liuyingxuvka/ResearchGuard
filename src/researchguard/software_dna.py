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
import hashlib
import json
from collections import Counter, deque
from pathlib import Path
import tomllib
from typing import Any, Iterable, Mapping, Sequence


SOFTWARE_DNA_SCHEMA = "researchguard.software-dna-contract.v2"
SOFTWARE_DNA_PATH = Path("models/software_dna/researchguard.json")
ROOT_MODEL_ID = "researchguard-suite"
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
            candidates.update(path for path in directory.rglob("*") if path.is_file())
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


def software_dna_affected_closure(indexes: Mapping[str, Any], changed_ids: Iterable[str]) -> dict[str, Any]:
    """Close only declared affected edges; unknown identities block."""

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


def software_dna_reverse_trace(indexes: Mapping[str, Any], target_id: str) -> dict[str, Any]:
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
    "INDEX_KINDS",
    "MEMBER_MODEL_IDS",
    "READINESS_LAYERS",
    "REPOSITORY_BOUNDARY_FILES",
    "REPOSITORY_BOUNDARY_ROOTS",
    "ROOT_MODEL_ID",
    "SOFTWARE_DNA_PATH",
    "SOFTWARE_DNA_SCHEMA",
    "SoftwareDnaError",
    "build_provider_neutral_inventory",
    "check_software_dna_contract",
    "software_dna_affected_closure",
    "software_dna_reverse_trace",
]
