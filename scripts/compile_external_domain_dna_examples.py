"""Compile canonical external-object DNA examples from current member owners.

This developer compiler intentionally uses the repository's native admission
fixtures to freeze one current four-member portable composition.  The runtime
artifact remains self-contained; ordinary consumers never import test code.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
sys.path.insert(0, str(REPOSITORY / "tests"))

from admission_fixtures import (  # noqa: E402
    isolated_test_native_fixture_cache,
    native_owner_attestations,
)
from external_scope_authority_fixtures import signed_scope_authority  # noqa: E402
from researchguard.domain_dna import (  # noqa: E402
    EXTERNAL_DOMAIN_DNA_SPEC_SCHEMA,
    MATERIAL_INVENTORY_POLICY_ID,
    MEMBER_BEHAVIOR_IDS,
    MEMBER_IDS,
    MEMBER_NATIVE_ROUTES,
    _OUTPUT_VALIDATORS,
    _expected_claim_boundary,
    _portable_native_context,
    build_external_domain_parent_function_block,
)
from researchguard.routing import (  # noqa: E402
    export_portable_composition_bundle,
    qualify_portable_composition_bundle,
    select_member_request,
)
from test_portable_composition_bundle import (  # noqa: E402
    ARGV,
    INTENT,
    _facts,
    _four_member_plan,
)


PAPER_ROOT_ENV = "RESEARCHGUARD_EXTERNAL_DNA_PAPER_ROOT"
MODEL_PATH = REPOSITORY / "models" / "external_domain_dna" / "attention-is-all-you-need-v7.json"
NATIVE_BUNDLE_PATH = REPOSITORY / "models" / "external_domain_dna" / "canonical-native-composition.json"
TRUST_ROOTS_PATH = REPOSITORY / "models" / "external_domain_dna" / "canonical-native-trust-roots.json"
SCOPE_AUTHORITY_PATH = REPOSITORY / "models" / "external_domain_dna" / "attention-is-all-you-need-v7.authority.json"
SCOPE_AUTHORITY_TRUST_ROOTS_PATH = REPOSITORY / "models" / "external_domain_dna" / "canonical-scope-authority-trust-roots.json"


def _digest(value: object) -> str:
    body = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _paper_root() -> Path:
    """Resolve the caller-supplied external paper snapshot without a local fallback."""

    supplied = os.environ.get(PAPER_ROOT_ENV, "").strip()
    if not supplied:
        raise RuntimeError(
            f"{PAPER_ROOT_ENV} must name the frozen external paper material root"
        )
    root = Path(supplied).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeError(f"paper material root is unavailable: {root}")
    return root


def _artifact_id(relative_path: str) -> str:
    fixed = {
        "attention-is-all-you-need-v7.pdf": "artifact:paper-pdf",
        "attention-is-all-you-need-v7-source.tar": "artifact:paper-source-tar",
        "source/ms.tex": "artifact:ms-tex",
        "source/results.tex": "artifact:results-tex",
    }
    if relative_path in fixed:
        return fixed[relative_path]
    slug = re.sub(r"[^a-z0-9]+", "-", relative_path.lower()).strip("-")
    return "artifact:" + slug


def _native_bundle() -> bytes:
    prior_environment = {
        name: os.environ.get(name)
        for name in (
            "HOME",
            "USERPROFILE",
            "RESEARCHGUARD_TEST_FIXTURE_ROOT",
            "RESEARCHGUARD_TEST_FIXTURE_ROOT_RELATIVE",
        )
    }
    try:
        with isolated_test_native_fixture_cache():
            with tempfile.TemporaryDirectory(
                prefix="researchguard-external-domain-dna-compiler-"
            ) as temporary:
                fixture_root = Path(temporary).resolve()
                isolated_home = fixture_root / "home"
                isolated_home.mkdir()
                os.environ["HOME"] = str(isolated_home)
                os.environ["USERPROFILE"] = str(isolated_home)
                prior_cwd = Path.cwd()
                try:
                    # Execute against real files under an isolated working directory,
                    # but preserve stable relative locators in the signed model. Exact
                    # portable material bytes, rather than the exporter temp path, own
                    # later replay identity.
                    os.chdir(fixture_root)
                    os.environ["RESEARCHGUARD_TEST_FIXTURE_ROOT"] = "fixtures"
                    os.environ["RESEARCHGUARD_TEST_FIXTURE_ROOT_RELATIVE"] = "1"
                    plan = _four_member_plan()
                    ready = select_member_request(
                        _facts(plan),
                        ARGV,
                        business_intent_id=INTENT,
                        native_owner_attestations=native_owner_attestations(plan),
                    )
                    if getattr(ready, "status", "") != "composition_ready":
                        raise RuntimeError(
                            "current four-member native composition is not ready"
                        )
                    return export_portable_composition_bundle(ready)
                finally:
                    os.chdir(prior_cwd)
    finally:
        for name, value in prior_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _full_artifacts(old_target: dict[str, object]) -> list[dict[str, object]]:
    paper_root = _paper_root()
    result: list[dict[str, object]] = []
    target_url = str(old_target["official_url"])
    for path in sorted(item for item in paper_root.rglob("*") if item.is_file()):
        relative = path.relative_to(paper_root).as_posix()
        body = path.read_bytes()
        role = (
            "primary-paper-pdf"
            if relative.endswith(".pdf") and "/" not in relative
            else "primary-author-source-archive"
            if relative.endswith(".tar")
            else "modeled-author-source"
            if relative in {"source/ms.tex", "source/results.tex"}
            else "supporting-author-material"
        )
        result.append(
            {
                "artifact_id": _artifact_id(relative),
                "role": role,
                "official_url": target_url + "#material=" + relative,
                "relative_path": relative,
                "sha256": hashlib.sha256(body).hexdigest(),
                "byte_length": len(body),
                "embedded": False,
                "disposition": (
                    "modeled"
                    if relative in {"source/ms.tex", "source/results.tex"}
                    else "supporting_material"
                ),
            }
        )
    return result


def _binding_rows(
    member_id: str,
    owned: list[str],
    inputs: list[str],
) -> list[dict[str, str]]:
    rows = [
        {
            "binding_id": f"binding:{member_id}:input:{index}",
            "object_id": object_id,
            "direction": "input_to_model",
            "role": "declared_prerequisite",
        }
        for index, object_id in enumerate(sorted(set(inputs)), start=1)
    ]
    rows.extend(
        {
            "binding_id": f"binding:{member_id}:output:{index}",
            "object_id": object_id,
            "direction": "model_to_output",
            "role": "member_owned_output",
        }
        for index, object_id in enumerate(sorted(owned), start=1)
    )
    return rows


def _paper_scope_authority() -> dict[str, object]:
    """Freeze the paper scope from independent requirements, never candidate output."""

    target_id = "paper:arxiv-1706.03762v7"
    official_url = "https://arxiv.org/abs/1706.03762v7"
    artifacts = _full_artifacts({"official_url": official_url})
    artifact_ids = [str(item["artifact_id"]) for item in artifacts]
    structure_ids = [
        "structure:paper-root",
        "structure:abstract",
        "structure:results-table",
        "structure:results-prose",
    ]
    source_id = f"source:{target_id}"
    source_outputs = [
        "anchor:abstract-enfr-bleu-41.8",
        "anchor:results-prose-enfr-bleu-41.0",
        "anchor:results-table-enfr-bleu-41.8",
        "gap:enfr-bleu-conflict",
        source_id,
    ]
    trace_outputs = [
        "event:abstract-reports-41.8",
        "event:prose-reports-41.0",
        "event:table-reports-41.8",
        "gap:trace-cannot-resolve-author-intent",
        "storyline:enfr-bleu-discrepancy",
    ]
    logic_outputs = [
        "claim:abstract-enfr-bleu-41.8",
        "claim:enfr-bleu-conflict-exists",
        "claim:prose-enfr-bleu-41.0",
        "claim:table-enfr-bleu-41.8",
        "edge:abstract-supports-41.8",
        "edge:prose-conflicts-41.8",
        "edge:table-supports-41.8",
        "gap:authoritative-enfr-bleu-unresolved",
    ]
    experiment_outputs = [
        "experiment:check-version-history",
        "experiment:compare-frozen-locators",
        "gap:no-author-resolution-evidence",
        "hypothesis:reported-score-is-41.0",
        "hypothesis:reported-score-is-41.8",
    ]
    anchors = [
        {
            "anchor_id": "anchor:abstract-enfr-bleu-41.8",
            "claim_id": "claim:reported-enfr-bleu",
            "source_id": source_id,
            "role": "reported_value_in_abstract",
            "artifact_id": "artifact:ms-tex",
            "structure_node_id": "structure:abstract",
            "expected_structure_kind": "section",
            "selector": {
                "selector_kind": "line_pattern",
                "occurrence_id": "occurrence:attention-v7:abstract-enfr-bleu",
                "locator": "source/ms.tex:127",
                "fingerprint": "sha256:749738eb19495a2ab3588629199533e0b073614cd2428a5dabbf22714c4dbdbf",
                "parameters": {
                    "line_number": 127,
                    "value_pattern": "(?P<value>41\\.[08])",
                    "value_group": "value",
                },
            },
            "expected_value": "41.8",
        },
        {
            "anchor_id": "anchor:results-table-enfr-bleu-41.8",
            "claim_id": "claim:reported-enfr-bleu",
            "source_id": source_id,
            "role": "reported_value_in_results_table",
            "artifact_id": "artifact:results-tex",
            "structure_node_id": "structure:results-table",
            "expected_structure_kind": "table",
            "selector": {
                "selector_kind": "line_pattern",
                "occurrence_id": "occurrence:attention-v7:results-table-enfr-bleu",
                "locator": "source/results.tex:26",
                "fingerprint": "sha256:99e536ea4c447a538b6405230070167befbc4ffebbd7188eddfccc50b0c3b444",
                "parameters": {
                    "line_number": 26,
                    "value_pattern": "(?P<value>41\\.[08])",
                    "value_group": "value",
                },
            },
            "expected_value": "41.8",
        },
        {
            "anchor_id": "anchor:results-prose-enfr-bleu-41.0",
            "claim_id": "claim:reported-enfr-bleu",
            "source_id": source_id,
            "role": "reported_value_in_results_prose",
            "artifact_id": "artifact:results-tex",
            "structure_node_id": "structure:results-prose",
            "expected_structure_kind": "paragraph",
            "selector": {
                "selector_kind": "line_pattern",
                "occurrence_id": "occurrence:attention-v7:results-prose-enfr-bleu",
                "locator": "source/results.tex:39",
                "fingerprint": "sha256:f5911f7dae5150c266b2026df96e2125bd3567ca97bb73b3b872e0c71335cd18",
                "parameters": {
                    "line_number": 39,
                    "value_pattern": "(?P<value>41\\.[08])",
                    "value_group": "value",
                },
            },
            "expected_value": "41.0",
        },
    ]
    root_artifacts = [
        item
        for item in artifact_ids
        if item not in {"artifact:ms-tex", "artifact:results-tex"}
    ]
    non_anchor_outputs = sorted(
        set(source_outputs + trace_outputs + logic_outputs + experiment_outputs)
        - {str(item["anchor_id"]) for item in anchors}
    )
    structure_obligations = [
        {
            "node_id": "structure:paper-root",
            "parent_id": None,
            "kind": "paper",
            "semantic_role": "target_document_root",
            "locator": "source/ms.tex",
            "required_member_ids": list(MEMBER_IDS),
            "required_artifact_ids": root_artifacts,
            "required_bound_object_ids": non_anchor_outputs,
        },
        {
            "node_id": "structure:abstract",
            "parent_id": "structure:paper-root",
            "kind": "section",
            "semantic_role": "reported_value_abstract",
            "locator": "source/ms.tex:127",
            "required_member_ids": ["sourceguard", "traceguard", "logicguard"],
            "required_artifact_ids": ["artifact:ms-tex"],
            "required_bound_object_ids": ["anchor:abstract-enfr-bleu-41.8"],
        },
        {
            "node_id": "structure:results-table",
            "parent_id": "structure:paper-root",
            "kind": "table",
            "semantic_role": "reported_value_results_table",
            "locator": "source/results.tex:4-28",
            "required_member_ids": list(MEMBER_IDS),
            "required_artifact_ids": ["artifact:results-tex"],
            "required_bound_object_ids": ["anchor:results-table-enfr-bleu-41.8"],
        },
        {
            "node_id": "structure:results-prose",
            "parent_id": "structure:paper-root",
            "kind": "paragraph",
            "semantic_role": "reported_value_results_prose",
            "locator": "source/results.tex:39",
            "required_member_ids": list(MEMBER_IDS),
            "required_artifact_ids": ["artifact:results-tex"],
            "required_bound_object_ids": ["anchor:results-prose-enfr-bleu-41.0"],
        },
    ]
    external_inputs = sorted({target_id, *artifact_ids, *structure_ids})
    member_rows = [
        {
            "member_id": "sourceguard",
            "required_input_object_ids": external_inputs,
            "required_output_object_ids": source_outputs,
            "required_output_kinds": [
                {"kind": "source_role", "object_ids": [source_id]},
                {"kind": "claim_anchor", "object_ids": sorted(str(item["anchor_id"]) for item in anchors)},
                {"kind": "gap", "object_ids": ["gap:enfr-bleu-conflict"]},
            ],
        },
        {
            "member_id": "traceguard",
            "required_input_object_ids": source_outputs,
            "required_output_object_ids": trace_outputs,
            "required_output_kinds": [
                {"kind": "ordered_event", "object_ids": [item for item in trace_outputs if item.startswith("event:")]},
                {"kind": "storyline", "object_ids": ["storyline:enfr-bleu-discrepancy"]},
                {"kind": "gap", "object_ids": ["gap:trace-cannot-resolve-author-intent"]},
            ],
        },
        {
            "member_id": "logicguard",
            "required_input_object_ids": trace_outputs,
            "required_output_object_ids": logic_outputs,
            "required_output_kinds": [
                {"kind": "claim", "object_ids": [item for item in logic_outputs if item.startswith("claim:")]},
                {"kind": "argument_edge", "object_ids": [item for item in logic_outputs if item.startswith("edge:")]},
                {"kind": "gap", "object_ids": ["gap:authoritative-enfr-bleu-unresolved"]},
            ],
        },
        {
            "member_id": "experimentguard",
            "required_input_object_ids": logic_outputs,
            "required_output_object_ids": experiment_outputs,
            "required_output_kinds": [
                {"kind": "hypothesis", "object_ids": [item for item in experiment_outputs if item.startswith("hypothesis:")]},
                {"kind": "experiment", "object_ids": [item for item in experiment_outputs if item.startswith("experiment:")]},
                {"kind": "gap", "object_ids": ["gap:no-author-resolution-evidence"]},
            ],
        },
    ]
    handoffs = []
    for index, (member_id, outputs) in enumerate(
        zip(MEMBER_IDS, (source_outputs, trace_outputs, logic_outputs, experiment_outputs))
    ):
        consumers = [MEMBER_IDS[index + 1]] if index + 1 < len(MEMBER_IDS) else []
        handoffs.extend(
            {
                "object_id": object_id,
                "producer_member_id": member_id,
                "consumer_member_ids": consumers,
            }
            for object_id in outputs
        )
    request = {
        "target_id": target_id,
        "scope_id": "scope:attention-v7:reported-enfr-bleu-consistency",
        "purpose": "reported English-to-French BLEU occurrence consistency",
    }
    return {
        "authority_id": "scope-authority:attention-v7:reported-enfr-bleu-consistency",
        "authority_revision": "1",
        "provenance": {
            "origin_kind": "external_contract",
            "origin_id": "contract:attention-v7:reported-enfr-bleu-consistency",
            "issued_at": "2026-08-05T00:00:00Z",
            "request_fingerprint": _digest(request),
        },
        "target": {
            "target_id": target_id,
            "title": "Attention Is All You Need",
            "kind": "research-paper-and-author-source",
            "version": "arXiv:1706.03762v7",
            "official_url": official_url,
            "material_inventory_policy": {
                "policy_id": MATERIAL_INVENTORY_POLICY_ID,
                "root_kind": "closed-directory-tree",
                "include_regular_files": True,
                "symlink_policy": "reject",
                "excluded_relative_paths": [],
            },
            "source_authorities": [
                {
                    "source_id": source_id,
                    "role": "primary_author_source",
                    "coverage_ids": sorted({target_id, *artifact_ids, *structure_ids}),
                }
            ],
            "artifacts": artifacts,
        },
        "scope": {
            "scope_id": "scope:attention-v7:reported-enfr-bleu-consistency",
            "purpose": (
                "Reconstruct and check the paper's reported English-to-French BLEU "
                "occurrences without claiming complete semantic coverage of the paper."
            ),
            "scope_kind": "bounded_research_question",
            "completion_status": "complete_within_declared_scope",
            "whole_target_semantics_claimed": False,
            "included_question_ids": ["question:reported-enfr-bleu-consistency"],
            "included_structure_node_ids": [
                "structure:abstract",
                "structure:results-table",
                "structure:results-prose",
            ],
            "excluded_semantic_region_ids": [
                "semantic-region:attention-v7:claims-outside-reported-enfr-bleu"
            ],
            "expansion_frontier_ids": [
                "frontier:attention-v7:recursive-semantic-inventory"
            ],
            "structure_obligations": structure_obligations,
            "anchor_obligations": anchors,
            "member_obligations": member_rows,
            "cross_member_handoffs": handoffs,
            "scope_limits": [
                "The model licenses the existence of a textual conflict, not a correction to 41.8 or 41.0."
            ],
        },
    }


def compile_paper_spec(
    old: dict[str, object],
    native_bundle: bytes,
    authority_record: dict[str, object],
) -> dict[str, object]:
    spec = deepcopy(old)
    spec["schema_version"] = EXTERNAL_DOMAIN_DNA_SPEC_SCHEMA
    target = spec["target"]
    assert isinstance(target, dict)
    artifacts = _full_artifacts(target)
    target["artifacts"] = artifacts
    target["material_inventory_policy"] = {
        "policy_id": MATERIAL_INVENTORY_POLICY_ID,
        "root_kind": "closed-directory-tree",
        "include_regular_files": True,
        "symlink_policy": "reject",
        "excluded_relative_paths": [],
    }
    scope_id = "scope:attention-v7:reported-enfr-bleu-consistency"
    target["model_scope"] = {
        "scope_id": scope_id,
        "purpose": (
            "Reconstruct and check the paper's reported English-to-French BLEU "
            "occurrences without claiming complete semantic coverage of the paper."
        ),
        "scope_kind": "bounded_research_question",
        "included_question_ids": ["question:reported-enfr-bleu-consistency"],
        "included_structure_node_ids": [
            "structure:abstract",
            "structure:results-table",
            "structure:results-prose",
        ],
        "excluded_semantic_region_ids": [
            "semantic-region:attention-v7:claims-outside-reported-enfr-bleu"
        ],
        "expansion_frontier_ids": [
            "frontier:attention-v7:recursive-semantic-inventory"
        ],
        "completion_status": "complete_within_declared_scope",
        "whole_target_semantics_claimed": False,
    }
    structures = spec["structure_nodes"]
    assert isinstance(structures, list)
    semantic_roles = {
        "structure:paper-root": "target_document_root",
        "structure:abstract": "reported_value_abstract",
        "structure:results-table": "reported_value_results_table",
        "structure:results-prose": "reported_value_results_prose",
    }
    artifact_ids = [str(item["artifact_id"]) for item in artifacts]
    for node in structures:
        assert isinstance(node, dict)
        node["semantic_role"] = semantic_roles[str(node["node_id"])]
        node["artifact_ids"] = []
        node["bound_object_ids"] = []
    root, abstract, table, prose = structures
    root["artifact_ids"] = [
        item for item in artifact_ids if item not in {"artifact:ms-tex", "artifact:results-tex"}
    ]
    abstract["artifact_ids"] = ["artifact:ms-tex"]
    table["artifact_ids"] = ["artifact:results-tex"]
    prose["artifact_ids"] = ["artifact:results-tex"]

    target_id = str(target["target_id"])
    source_id = f"source:{target_id}"
    coverage_ids = sorted(
        {target_id, *artifact_ids, *(str(item["node_id"]) for item in structures)}
    )
    source_authority = {
        "source_id": source_id,
        "role": "primary_author_source",
        "coverage_ids": coverage_ids,
    }
    target["source_authorities"] = [source_authority]

    native_contexts, _qualification = _portable_native_context(native_bundle)
    models = spec["member_models"]
    assert isinstance(models, dict)
    for member_id in MEMBER_IDS:
        model = models[member_id]
        assert isinstance(model, dict)
        model["native_route"] = deepcopy(MEMBER_NATIVE_ROUTES[member_id])
        model["native_binding"] = deepcopy(native_contexts[member_id]["binding"])
    source = models["sourceguard"]
    trace = models["traceguard"]
    logic = models["logicguard"]
    experiment = models["experimentguard"]
    source_input = source["input"]
    trace_input = trace["input"]
    logic_input = logic["input"]
    experiment_input = experiment["input"]
    assert all(
        isinstance(item, dict)
        for item in (source_input, trace_input, logic_input, experiment_input)
    )
    source_input["source_roles"] = [source_authority]
    source_input["variance_gap_id"] = source_input.pop(
        "conflict_gap_id", source_input.get("variance_gap_id")
    )
    anchor_roles = {
        "anchor:abstract-enfr-bleu-41.8": (
            "reported_value_in_abstract",
            "occurrence:attention-v7:abstract-enfr-bleu",
        ),
        "anchor:results-table-enfr-bleu-41.8": (
            "reported_value_in_results_table",
            "occurrence:attention-v7:results-table-enfr-bleu",
        ),
        "anchor:results-prose-enfr-bleu-41.0": (
            "reported_value_in_results_prose",
            "occurrence:attention-v7:results-prose-enfr-bleu",
        ),
    }
    for request in source_input["extraction_requests"]:
        request["source_id"] = source_id
        role, occurrence_id = anchor_roles[str(request["anchor_id"])]
        request["role"] = role
        if "selector" not in request:
            request["selector"] = {
                "selector_kind": "line_pattern",
                "occurrence_id": occurrence_id,
                "locator": request.pop("locator"),
                "fingerprint": "sha256:" + str(request.pop("line_sha256")),
                "parameters": {
                    "line_number": request.pop("line_number"),
                    "value_pattern": request.pop("value_pattern"),
                    "value_group": request.pop("value_group"),
                },
            }
    extraction_structures = {
        "anchor:abstract-enfr-bleu-41.8": ("structure:abstract", "section"),
        "anchor:results-table-enfr-bleu-41.8": ("structure:results-table", "table"),
        "anchor:results-prose-enfr-bleu-41.0": ("structure:results-prose", "paragraph"),
    }
    for request in source_input["extraction_requests"]:
        node_id, kind = extraction_structures[str(request["anchor_id"])]
        request["structure_node_id"] = node_id
        request["expected_structure_kind"] = kind
    trace_input["uncertainty_gap_id"] = trace_input.pop(
        "conflict_gap_id", trace_input.get("uncertainty_gap_id")
    )
    logic_input["summary_claim_id"] = logic_input.pop(
        "conflict_claim_id", logic_input.get("summary_claim_id")
    )
    logic_input["uncertainty_gap_id"] = logic_input.pop(
        "conflict_gap_id", logic_input.get("uncertainty_gap_id")
    )
    experiment_input["uncertainty_gap_id"] = experiment_input.pop(
        "conflict_gap_id", experiment_input.get("uncertainty_gap_id")
    )

    # SourceGuard verifies semantic structure binding during extraction; anchor
    # ownership must therefore exist before member projection is derived.
    abstract["bound_object_ids"] = ["anchor:abstract-enfr-bleu-41.8"]
    table["bound_object_ids"] = ["anchor:results-table-enfr-bleu-41.8"]
    prose["bound_object_ids"] = ["anchor:results-prose-enfr-bleu-41.0"]

    outputs: dict[str, object] = {}
    context: dict[str, object] = {
        "target": target,
        "structure_nodes": structures,
        "material_root": _paper_root(),
        "member_outputs": outputs,
    }
    for member_id in MEMBER_IDS:
        model = models[member_id]
        route = MEMBER_NATIVE_ROUTES[member_id]["external_transition"]
        module_name, function_name = route.split(":", 1)
        module = __import__(module_name, fromlist=[function_name])
        evaluator = getattr(module, function_name)
        result = evaluator(
            model,
            {**context, "native_member_replay": native_contexts[member_id]},
        )
        model["output"] = result["output"]
        transition = result["transition_contract"]
        for field in (
            "pre_state", "post_state", "effect", "protected_failure", "claim_boundary"
        ):
            model[field] = transition[field]
        outputs[member_id] = result["output"]

    owned_by_member: dict[str, list[str]] = {}
    prior_owned: list[str] = []
    external_inputs = [target_id, *artifact_ids, *(str(item["node_id"]) for item in structures)]
    for member_id in MEMBER_IDS:
        model = models[member_id]
        created = sorted(set(_OUTPUT_VALIDATORS[member_id](model["output"])))
        owned_by_member[member_id] = created
        model["owned_object_ids"] = created
        model["bindings"] = _binding_rows(
            member_id,
            created,
            external_inputs if member_id == "sourceguard" else prior_owned,
        )
        model["scope_binding"] = {
            "scope_id": scope_id,
            "declared_complete_object_ids": created,
            "declared_input_object_ids": sorted(
                {
                    str(item["object_id"])
                    for item in model["bindings"]
                    if item["direction"] == "input_to_model"
                }
            ),
            "expansion_frontier_ids": list(
                target["model_scope"]["expansion_frontier_ids"]
            ),
            "completion_status": "complete_within_declared_scope",
        }
        good_id = f"test:{member_id}:external-object-known-good"
        bad_id = f"test:{member_id}:external-object-known-bad"
        oracle_id = f"oracle:{member_id}:external-object-transition"
        model["test_bindings"] = [
            {
                "test_id": good_id,
                "behavior_id": MEMBER_BEHAVIOR_IDS[member_id],
                "role": "known_good",
                "oracle_id": oracle_id,
            },
            {
                "test_id": bad_id,
                "behavior_id": MEMBER_BEHAVIOR_IDS[member_id],
                "role": "known_bad",
                "oracle_id": oracle_id,
            },
        ]
        model["oracle_binding"] = {
            "oracle_id": oracle_id,
            "owner_id": member_id,
            "checker_entrypoint": MEMBER_NATIVE_ROUTES[member_id]["external_transition"],
            "good_case_id": good_id,
            "bad_case_id": bad_id,
            "protected_failure": model["protected_failure"],
        }
        native_receipt_ids = model["native_binding"]["native_receipt_ids"]
        model["evidence_bindings"] = [
            {
                "evidence_id": f"evidence:{member_id}:{role}",
                "role": role,
                "subject_id": subject,
                "producer_entrypoint": producer,
                "status": "current",
            }
            for role, subject, producer in (
                ("model", str(model["model_id"]), MEMBER_NATIVE_ROUTES[member_id]["blueprint_checker"]),
                ("material", target_id, MEMBER_NATIVE_ROUTES[member_id]["external_transition"]),
                ("test", good_id, MEMBER_NATIVE_ROUTES[member_id]["external_transition"]),
                ("oracle", oracle_id, MEMBER_NATIVE_ROUTES[member_id]["external_transition"]),
                ("native_receipt", str(native_receipt_ids[0]), MEMBER_NATIVE_ROUTES[member_id]["owner_attestation"]),
            )
        ]
        prior_owned = created

    anchor_to_node = {
        "anchor:abstract-enfr-bleu-41.8": abstract,
        "anchor:results-table-enfr-bleu-41.8": table,
        "anchor:results-prose-enfr-bleu-41.0": prose,
    }
    all_owned = {item for rows in owned_by_member.values() for item in rows}
    anchored = set(anchor_to_node)
    root["bound_object_ids"] = sorted(all_owned - anchored)
    for anchor_id, node in anchor_to_node.items():
        node["bound_object_ids"] = [anchor_id]

    spec["dependency_edges"] = [
        {
            "edge_id": f"dependency:{left}:{right}",
            "from_id": str(models[left]["model_id"]),
            "to_id": str(models[right]["model_id"]),
            "relation": "member_native_handoff",
        }
        for left, right in zip(MEMBER_IDS, MEMBER_IDS[1:])
    ]
    spec["scope_authority_binding"] = {
        "authority_id": authority_record["authority"]["authority_id"],
        "authority_fingerprint": authority_record["authority_fingerprint"],
        "producer_descriptor_fingerprint": authority_record[
            "producer_descriptor_fingerprint"
        ],
    }
    spec["claim_boundary"] = _expected_claim_boundary(target_id, scope_id)
    spec["parent_function_block"] = build_external_domain_parent_function_block(spec)
    return spec


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    old = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    native_bundle = _native_bundle()
    authority_record = signed_scope_authority(_paper_scope_authority())
    spec = compile_paper_spec(old, native_bundle, authority_record)
    _write_json(MODEL_PATH, spec)
    _write_json(SCOPE_AUTHORITY_PATH, authority_record)
    NATIVE_BUNDLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    NATIVE_BUNDLE_PATH.write_bytes(native_bundle)
    trust_roots = qualify_portable_composition_bundle(native_bundle)[
        "required_trusted_producer_descriptor_fingerprints"
    ]
    _write_json(TRUST_ROOTS_PATH, trust_roots)
    _write_json(
        SCOPE_AUTHORITY_TRUST_ROOTS_PATH,
        [authority_record["producer_descriptor_fingerprint"]],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
