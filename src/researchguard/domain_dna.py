"""Portable, target-owned domain DNA for an external object or workflow.

The artifact is deliberately independent from repository self-DNA.  It carries
four member-owned semantic projections, their hierarchy and dependency graph,
and enough stable identifiers for affected-only and reverse queries.  Source
bytes are referenced and fingerprinted, never copied into the bundle by this
module.
"""

from __future__ import annotations

import base64
from functools import lru_cache
import hashlib
import importlib
import json
from pathlib import Path
import re
from typing import Iterable, Literal, Mapping, Sequence

from .external_scope_authority import (
    ExternalScopeAuthorityError,
    validate_external_scope_authority_record,
)


EXTERNAL_DOMAIN_DNA_SPEC_SCHEMA = "researchguard.external-domain-dna-spec.v3"
EXTERNAL_DOMAIN_DNA_SCHEMA = "researchguard.external-domain-dna.v3"
EXTERNAL_DOMAIN_MEMBER_EVIDENCE_SCHEMA = (
    "researchguard.external-domain-member-evidence.v3"
)
EXTERNAL_DOMAIN_PARENT_FUNCTION_BLOCK_SCHEMA = (
    "researchguard.external-domain-parent-function-block.v1"
)
EXTERNAL_DOMAIN_NATIVE_COMPOSITION_SCHEMA = (
    "researchguard.external-domain-native-composition.v1"
)
MATERIAL_INVENTORY_POLICY_ID = "researchguard.closed-material-tree.v1"
MEMBER_IDS = ("sourceguard", "traceguard", "logicguard", "experimentguard")
MEMBER_BEHAVIOR_IDS = {
    "sourceguard": "sourceguard.information-blueprint-qualification",
    "traceguard": "traceguard.investigation-reconstruction",
    "logicguard": "logicguard.argument-artifact-qualification",
    "experimentguard": "experimentguard.finite-discriminating-recommendation",
}
MEMBER_NATIVE_ROUTES = {
    "sourceguard": {
        "blueprint_checker": "researchguard.source.blueprint:check_blueprint",
        "owner_attestation": "researchguard.source.owner_attestation:replay_native_owner_attestation",
        "external_transition": "researchguard.source.owner_attestation:evaluate_external_object_transition",
    },
    "traceguard": {
        "blueprint_checker": "researchguard.trace.blueprint:check_blueprint",
        "owner_attestation": "researchguard.trace.owner_attestation:replay_native_owner_attestation",
        "external_transition": "researchguard.trace.owner_attestation:evaluate_external_object_transition",
    },
    "logicguard": {
        "blueprint_checker": "researchguard.logic.blueprint:check_blueprint",
        "owner_attestation": "researchguard.logic.owner_attestation:replay_native_owner_attestation",
        "external_transition": "researchguard.logic.owner_attestation:evaluate_external_object_transition",
    },
    "experimentguard": {
        "blueprint_checker": "researchguard.experiment.blueprint:check_blueprint",
        "owner_attestation": "researchguard.experiment.owner_attestation:replay_native_owner_attestation",
        "external_transition": "researchguard.experiment.owner_attestation:evaluate_external_object_transition",
    },
}
NATIVE_BINDING_FIELDS = {
    "envelope_id",
    "envelope_fingerprint",
    "native_model_id",
    "model_fingerprint",
    "expected_target_anchor_id",
    "expected_target_anchor_fingerprint",
    "behavior_manifest_id",
    "behavior_manifest_fingerprint",
    "domain_behavior_id",
    "native_receipt_ids",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ExternalDomainDnaError(ValueError):
    """One exact, user-visible external-domain-DNA contract failure."""


def _canonical(value: object) -> object:
    return json.loads(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    )


def _digest(value: object) -> str:
    body = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _mapping(value: object, fields: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ExternalDomainDnaError(f"{label} is not exact-current")
    return value


def _rows(value: object, label: str) -> Sequence[Mapping[str, object]]:
    if not isinstance(value, list) or any(not isinstance(row, Mapping) for row in value):
        raise ExternalDomainDnaError(f"{label} must be an array of objects")
    return value  # type: ignore[return-value]


def _text(value: object, label: str) -> str:
    result = str(value).strip()
    if not result:
        raise ExternalDomainDnaError(f"{label} is required")
    return result


def _string_ids(value: object, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ExternalDomainDnaError(f"{label} must be an array")
    result = tuple(_text(item, label) for item in value)
    if len(result) != len(set(result)):
        raise ExternalDomainDnaError(f"{label} must contain unique ids")
    if not result and not allow_empty:
        raise ExternalDomainDnaError(f"{label} must not be empty")
    return result


def _register(values: dict[str, str], object_id: str, owner: str) -> None:
    prior = values.get(object_id)
    if prior is not None:
        raise ExternalDomainDnaError(
            f"object id {object_id!r} has duplicate owners {prior!r} and {owner!r}"
        )
    values[object_id] = owner


@lru_cache(maxsize=8)
def _compute_portable_native_context(
    bundle: bytes,
    trusted_producer_descriptor_fingerprints: tuple[str, ...],
) -> tuple[dict[str, dict[str, object]], Mapping[str, object]]:
    """Replay the four real member blueprints and expose only bound identities.

    The portable-composition qualifier is the one semantic admission path.  It
    reconstructs each full MemberModelEnvelope, validates the expected-target
    authority, owner attestation, behavior manifest and native receipts, and
    invokes the member-owned behavior replay (which invokes the current native
    blueprint checker).  External-domain projection runs only after that path.
    """

    from .model_envelope import MemberModelEnvelope
    from .routing import qualify_portable_composition_bundle

    qualified = qualify_portable_composition_bundle(
        bundle,
        trusted_producer_descriptor_fingerprints=(
            trusted_producer_descriptor_fingerprints
        ),
    )
    if qualified.get("status") == "handoff_blocked":
        first_gap = qualified.get("first_gap")
        detail = (
            str(first_gap.get("detail", ""))
            if isinstance(first_gap, Mapping)
            else "portable composition was blocked"
        )
        raise ExternalDomainDnaError(
            "member-native portable composition failed: " + detail
        )
    try:
        raw = json.loads(bundle.decode("utf-8"))
        envelope_rows = raw["portable_member_envelopes"]
        if not isinstance(envelope_rows, list):
            raise ValueError("portable member envelope denominator is invalid")
        envelopes = tuple(
            MemberModelEnvelope.from_dict(item)
            for item in envelope_rows
            if isinstance(item, Mapping)
        )
    except (KeyError, TypeError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ExternalDomainDnaError(
            "member-native portable composition cannot be reopened"
        ) from exc
    if {item.member_id for item in envelopes} != set(MEMBER_IDS) or len(envelopes) != len(
        MEMBER_IDS
    ):
        raise ExternalDomainDnaError(
            "member-native portable composition must carry exactly four members"
        )
    result_by_member = {
        str(item.get("member_id", "")): item
        for item in qualified.get("member_object_dna_results", [])
        if isinstance(item, Mapping)
    }
    contexts: dict[str, dict[str, object]] = {}
    for envelope in envelopes:
        member_result = result_by_member.get(envelope.member_id)
        if not isinstance(member_result, Mapping) or member_result.get("status") not in {
            "self_consistent",
            "licensed",
        }:
            raise ExternalDomainDnaError(
                f"{envelope.member_id} native blueprint replay is not current"
            )
        manifest = envelope.behavior_manifest
        if MEMBER_BEHAVIOR_IDS[envelope.member_id] not in set(
            manifest.domain_behavior_denominator_ids
        ):
            raise ExternalDomainDnaError(
                f"{envelope.member_id} native behavior denominator is incomplete"
            )
        binding = {
            "envelope_id": envelope.envelope_id,
            "envelope_fingerprint": envelope.envelope_fingerprint,
            "native_model_id": envelope.native_model_id,
            "model_fingerprint": envelope.model_fingerprint,
            "expected_target_anchor_id": envelope.expected_target_anchor_id,
            "expected_target_anchor_fingerprint": (
                envelope.expected_target_anchor_fingerprint
            ),
            "behavior_manifest_id": manifest.expected_id,
            "behavior_manifest_fingerprint": manifest.expected_fingerprint,
            "domain_behavior_id": MEMBER_BEHAVIOR_IDS[envelope.member_id],
            "native_receipt_ids": sorted(
                item.receipt_id for item in envelope.native_receipt_refs
            ),
        }
        contexts[envelope.member_id] = {
            "member_id": envelope.member_id,
            "status": "passed",
            "qualification_level": str(member_result["status"]),
            "blueprint_replay": "passed",
            "binding": binding,
            "portable_result_fingerprint": _digest(
                {"binding": binding, "blueprint_replay": "passed"}
            ),
        }
    return contexts, qualified


def _portable_native_context(
    bundle: bytes,
    *,
    trusted_producer_descriptor_fingerprints: Sequence[str] = (),
) -> tuple[dict[str, dict[str, object]], Mapping[str, object]]:
    """Reuse an immutable exact bundle/trust replay inside one process."""

    trusted = tuple(sorted(str(item).strip() for item in trusted_producer_descriptor_fingerprints))
    contexts, qualified = _compute_portable_native_context(bundle, trusted)
    # Never expose the cached objects themselves to a caller.  The cache is a
    # bounded process-local replay memo, not writable authority.
    return _canonical(contexts), _canonical(qualified)  # type: ignore[return-value]


def derive_external_domain_native_bindings(bundle: bytes) -> dict[str, dict[str, object]]:
    """Derive exact spec bindings from one self-consistent portable composition."""

    contexts, _qualified = _portable_native_context(bundle)
    return {
        member_id: dict(contexts[member_id]["binding"])  # type: ignore[arg-type]
        for member_id in MEMBER_IDS
    }


def _validate_gaps(value: object, label: str) -> tuple[str, ...]:
    result: list[str] = []
    for row in _rows(value, label):
        gap = _mapping(row, {"gap_id", "code", "detail"}, label)
        result.append(_text(gap["gap_id"], f"{label} gap id"))
        _text(gap["code"], f"{label} gap code")
        _text(gap["detail"], f"{label} gap detail")
    if len(result) != len(set(result)):
        raise ExternalDomainDnaError(f"{label} gap ids must be unique")
    return tuple(result)


def _validate_source_output(value: object) -> tuple[str, ...]:
    output = _mapping(
        value,
        {"source_roles", "claim_anchors", "unavailable_source_ids", "gaps"},
        "SourceGuard output",
    )
    created: list[str] = []
    for row in _rows(output["source_roles"], "SourceGuard source roles"):
        role = _mapping(row, {"source_id", "role", "coverage_ids"}, "source role")
        created.append(_text(role["source_id"], "source role source id"))
        _text(role["role"], "source role")
        _string_ids(role["coverage_ids"], "source role coverage ids")
    for row in _rows(output["claim_anchors"], "SourceGuard claim anchors"):
        anchor = _mapping(
            row,
            {"anchor_id", "claim_id", "source_id", "locator", "value", "status"},
            "claim anchor",
        )
        created.append(_text(anchor["anchor_id"], "claim anchor id"))
        for field in ("claim_id", "source_id", "locator", "value", "status"):
            _text(anchor[field], f"claim anchor {field}")
    _string_ids(
        output["unavailable_source_ids"],
        "SourceGuard unavailable source ids",
        allow_empty=True,
    )
    created.extend(_validate_gaps(output["gaps"], "SourceGuard gaps"))
    return tuple(created)


def _validate_trace_output(value: object) -> tuple[str, ...]:
    output = _mapping(value, {"ordered_events", "storylines", "gaps"}, "TraceGuard output")
    created: list[str] = []
    for row in _rows(output["ordered_events"], "TraceGuard ordered events"):
        event = _mapping(
            row,
            {"event_id", "stage", "predecessor_ids", "evidence_ids", "output_ids"},
            "trace event",
        )
        created.append(_text(event["event_id"], "trace event id"))
        _text(event["stage"], "trace event stage")
        for field in ("predecessor_ids", "evidence_ids", "output_ids"):
            _string_ids(event[field], f"trace event {field}", allow_empty=True)
    for row in _rows(output["storylines"], "TraceGuard storylines"):
        storyline = _mapping(
            row,
            {"storyline_id", "event_ids", "status", "unresolved_gap_ids"},
            "trace storyline",
        )
        created.append(_text(storyline["storyline_id"], "trace storyline id"))
        _string_ids(storyline["event_ids"], "trace storyline event ids")
        _text(storyline["status"], "trace storyline status")
        _string_ids(
            storyline["unresolved_gap_ids"],
            "trace storyline unresolved gap ids",
            allow_empty=True,
        )
    created.extend(_validate_gaps(output["gaps"], "TraceGuard gaps"))
    return tuple(created)


def _validate_logic_output(value: object) -> tuple[str, ...]:
    output = _mapping(
        value, {"claims", "argument_edges", "scope_limits", "gaps"}, "LogicGuard output"
    )
    created: list[str] = []
    for row in _rows(output["claims"], "LogicGuard claims"):
        claim = _mapping(
            row,
            {"claim_id", "text", "status", "premise_ids", "evidence_ids", "scope"},
            "logic claim",
        )
        created.append(_text(claim["claim_id"], "logic claim id"))
        for field in ("text", "status", "scope"):
            _text(claim[field], f"logic claim {field}")
        for field in ("premise_ids", "evidence_ids"):
            _string_ids(claim[field], f"logic claim {field}", allow_empty=True)
    for row in _rows(output["argument_edges"], "LogicGuard argument edges"):
        edge = _mapping(
            row,
            {"edge_id", "from_claim_id", "to_claim_id", "relation"},
            "logic argument edge",
        )
        created.append(_text(edge["edge_id"], "logic argument edge id"))
        for field in ("from_claim_id", "to_claim_id", "relation"):
            _text(edge[field], f"logic argument edge {field}")
    if not isinstance(output["scope_limits"], list) or not output["scope_limits"] or any(
        not str(item).strip() for item in output["scope_limits"]
    ):
        raise ExternalDomainDnaError("LogicGuard scope limits must be a non-empty text array")
    created.extend(_validate_gaps(output["gaps"], "LogicGuard gaps"))
    return tuple(created)


def _validate_experiment_output(value: object) -> tuple[str, ...]:
    output = _mapping(
        value,
        {"hypotheses", "experiments", "recommendation", "gaps"},
        "ExperimentGuard output",
    )
    created: list[str] = []
    for row in _rows(output["hypotheses"], "ExperimentGuard hypotheses"):
        hypothesis = _mapping(
            row, {"hypothesis_id", "text", "predictions"}, "experiment hypothesis"
        )
        created.append(_text(hypothesis["hypothesis_id"], "hypothesis id"))
        _text(hypothesis["text"], "hypothesis text")
        if not isinstance(hypothesis["predictions"], Mapping):
            raise ExternalDomainDnaError("hypothesis predictions must be an object")
    for row in _rows(output["experiments"], "ExperimentGuard experiments"):
        experiment = _mapping(
            row,
            {
                "experiment_id",
                "purpose",
                "input_ids",
                "output_ids",
                "observed_outcomes",
                "locator",
                "status",
            },
            "experiment",
        )
        created.append(_text(experiment["experiment_id"], "experiment id"))
        for field in ("purpose", "locator", "status"):
            _text(experiment[field], f"experiment {field}")
        for field in ("input_ids", "output_ids"):
            _string_ids(experiment[field], f"experiment {field}", allow_empty=True)
        if not isinstance(experiment["observed_outcomes"], Mapping):
            raise ExternalDomainDnaError("experiment observed outcomes must be an object")
    recommendation = _mapping(
        output["recommendation"],
        {
            "selected_experiment_ids",
            "alternative_minimal_sets",
            "unresolved_hypothesis_pairs",
            "reason",
        },
        "ExperimentGuard recommendation",
    )
    _string_ids(
        recommendation["selected_experiment_ids"],
        "selected experiment ids",
        allow_empty=True,
    )
    if not isinstance(recommendation["alternative_minimal_sets"], list) or any(
        not isinstance(item, list) for item in recommendation["alternative_minimal_sets"]
    ):
        raise ExternalDomainDnaError("alternative minimal sets must be an array of arrays")
    if not isinstance(recommendation["unresolved_hypothesis_pairs"], list) or any(
        not isinstance(item, list) or len(item) != 2
        for item in recommendation["unresolved_hypothesis_pairs"]
    ):
        raise ExternalDomainDnaError("unresolved hypothesis pairs must contain pairs")
    _text(recommendation["reason"], "recommendation reason")
    created.extend(_validate_gaps(output["gaps"], "ExperimentGuard gaps"))
    return tuple(created)


_OUTPUT_VALIDATORS = {
    "sourceguard": _validate_source_output,
    "traceguard": _validate_trace_output,
    "logicguard": _validate_logic_output,
    "experimentguard": _validate_experiment_output,
}

_MEMBER_DNA_EVALUATORS = {
    member_id: route["external_transition"]
    for member_id, route in MEMBER_NATIVE_ROUTES.items()
}


def _replay_member_projection(
    member_id: str,
    model: Mapping[str, object],
    context: Mapping[str, object],
) -> tuple[dict[str, object], Mapping[str, object]]:
    """Ask the fixed member owner to derive output from inputs and upstream state."""

    module_name, function_name = _MEMBER_DNA_EVALUATORS[member_id].split(":", 1)
    try:
        owner_module = importlib.import_module(module_name)
        evaluator = getattr(owner_module, function_name)
        bad_case_builder = getattr(owner_module, "build_external_object_bad_case")
        checker_version = _text(
            getattr(owner_module, "EXTERNAL_OBJECT_CHECKER_VERSION", ""),
            f"{member_id} external-object checker version",
        )
        result = evaluator(model, context)
    except (AttributeError, ImportError, OSError, TypeError, ValueError) as exc:
        raise ExternalDomainDnaError(
            f"{member_id} member-native external transition failed: {exc}"
        ) from exc
    if not isinstance(result, Mapping) or set(result) != {
        "output",
        "native_result",
        "transition_contract",
    }:
        raise ExternalDomainDnaError(f"{member_id} DNA evaluator returned no native result")
    derived_output = result["output"]
    native_result = result["native_result"]
    transition_contract = result["transition_contract"]
    if (
        not isinstance(derived_output, Mapping)
        or not isinstance(native_result, Mapping)
        or not isinstance(transition_contract, Mapping)
        or set(transition_contract)
        != {
            "pre_state",
            "post_state",
            "effect",
            "protected_failure",
            "claim_boundary",
        }
    ):
        raise ExternalDomainDnaError(f"{member_id} DNA evaluator result is invalid")
    if _canonical(derived_output) != _canonical(model["output"]):
        raise ExternalDomainDnaError(
            f"{member_id} candidate output differs from native derivation"
        )
    created = _OUTPUT_VALIDATORS[member_id](derived_output)
    consumed = _string_ids(
        native_result.get("consumed_upstream_object_ids"),
        f"{member_id} consumed upstream object ids",
    )
    declared_inputs = {
        str(item["object_id"])
        for item in _rows(model["bindings"], f"{member_id} bindings")
        if item.get("direction") == "input_to_model"
    }
    if set(consumed) != declared_inputs or len(consumed) != len(declared_inputs):
        missing = sorted(declared_inputs - set(consumed))
        unexpected = sorted(set(consumed) - declared_inputs)
        raise ExternalDomainDnaError(
            f"{member_id} native transition did not consume its exact declared inputs; "
            f"missing={missing}, unexpected={unexpected}"
        )
    owned = _string_ids(model["owned_object_ids"], f"{member_id} native owned ids")
    if not set(created).issubset(owned):
        raise ExternalDomainDnaError(
            f"{member_id} native output escapes its owned object denominator"
        )
    for field in (
        "pre_state",
        "post_state",
        "effect",
        "protected_failure",
        "claim_boundary",
    ):
        if _canonical(model[field]) != _canonical(transition_contract[field]):
            raise ExternalDomainDnaError(
                f"{member_id} candidate {field} differs from native derivation"
            )
    transition = {
        "input": model["input"],
        "pre_state": transition_contract["pre_state"],
        "permitted_output": derived_output,
        "post_state": transition_contract["post_state"],
        "effect": transition_contract["effect"],
        "protected_failure": transition_contract["protected_failure"],
    }
    try:
        bad_model, bad_context = bad_case_builder(model, context)
    except (OSError, TypeError, ValueError) as exc:
        raise ExternalDomainDnaError(
            f"{member_id} target-native bad-case construction failed: {exc}"
        ) from exc
    if not isinstance(bad_model, Mapping) or not isinstance(bad_context, Mapping):
        raise ExternalDomainDnaError(
            f"{member_id} target-native bad case is not an executable model/context pair"
        )
    target = context.get("target")
    bad_target = bad_context.get("target")
    if (
        not isinstance(target, Mapping)
        or not isinstance(bad_target, Mapping)
        or str(target.get("target_id", "")) != str(bad_target.get("target_id", ""))
    ):
        raise ExternalDomainDnaError(
            f"{member_id} target-native bad case changed the external target"
        )
    bad_failure: dict[str, str] | None = None
    try:
        bad_case_builder_result = evaluator(bad_model, bad_context)
    except (OSError, TypeError, ValueError) as exc:
        bad_failure = {
            "exception_type": type(exc).__name__,
            "detail": str(exc),
        }
    if bad_failure is None:
        raise ExternalDomainDnaError(
            f"{member_id} target-native known-bad transition was accepted: "
            f"{_digest(bad_case_builder_result)}"
        )
    oracle_binding = model["oracle_binding"]
    assert isinstance(oracle_binding, Mapping)
    target_subject_fingerprint = _digest(
        {
            "target": context.get("target"),
            "structure_nodes": context.get("structure_nodes"),
        }
    )
    capability_fixture_replay_fingerprint = _text(
        context.get("native_member_replay", {}).get("portable_result_fingerprint")
        if isinstance(context.get("native_member_replay"), Mapping)
        else "",
        f"{member_id} capability fixture replay fingerprint",
    )
    target_native_good_case_fingerprint = _digest(
        {
            "case_id": oracle_binding["good_case_id"],
            "checker_entrypoint": _MEMBER_DNA_EVALUATORS[member_id],
            "target_subject_fingerprint": target_subject_fingerprint,
            "model_id": model["model_id"],
            "native_binding": model["native_binding"],
            "input": model["input"],
            "upstream_member_outputs": context.get("member_outputs"),
            "result": result,
        }
    )
    target_native_bad_case_fingerprint = _digest(
        {
            "case_id": oracle_binding["bad_case_id"],
            "checker_entrypoint": _MEMBER_DNA_EVALUATORS[member_id],
            "target_subject_fingerprint": target_subject_fingerprint,
            "model_id": bad_model.get("model_id"),
            "native_binding": bad_model.get("native_binding"),
            "input": bad_model.get("input"),
            "upstream_member_outputs": bad_context.get("member_outputs"),
            "failure": bad_failure,
        }
    )
    target_native_oracle_fingerprint = _digest(
        {
            "oracle_binding": oracle_binding,
            "good_case_fingerprint": target_native_good_case_fingerprint,
            "bad_case_fingerprint": target_native_bad_case_fingerprint,
            "bad_case_status": "rejected",
        }
    )
    model_fingerprint = _digest(model)
    evidence_core = {
        "schema_version": EXTERNAL_DOMAIN_MEMBER_EVIDENCE_SCHEMA,
        "member_id": member_id,
        "checker_entrypoint": _MEMBER_DNA_EVALUATORS[member_id],
        "checker_version": checker_version,
        "blueprint_checker_entrypoint": MEMBER_NATIVE_ROUTES[member_id]["blueprint_checker"],
        "owner_attestation_entrypoint": MEMBER_NATIVE_ROUTES[member_id]["owner_attestation"],
        "behavior_id": str(model["behavior_id"]),
        "model_id": str(model["model_id"]),
        "model_fingerprint": model_fingerprint,
        "transition_fingerprint": _digest(transition),
        "native_result_fingerprint": _digest(native_result),
        "test_binding_fingerprint": _digest(model["test_bindings"]),
        "oracle_binding_fingerprint": _digest(model["oracle_binding"]),
        "evidence_binding_fingerprint": _digest(model["evidence_bindings"]),
        "created_object_ids": sorted(set(created)),
        "consumed_upstream_object_ids": sorted(consumed),
        "capability_fixture_replay_fingerprint": capability_fixture_replay_fingerprint,
        "target_subject_fingerprint": target_subject_fingerprint,
        "target_native_good_case_fingerprint": target_native_good_case_fingerprint,
        "target_native_bad_case_fingerprint": target_native_bad_case_fingerprint,
        "target_native_oracle_fingerprint": target_native_oracle_fingerprint,
        "target_native_replay_status": "passed_good_and_rejected_bad",
        "status": "passed",
        "claim_boundary": str(model["claim_boundary"]),
    }
    return (
        {**evidence_core, "evidence_fingerprint": _digest(evidence_core)},
        derived_output,
    )


def _replay_member_set(
    member_models: Mapping[str, object],
    *,
    target: Mapping[str, object],
    structure_nodes: Sequence[Mapping[str, object]],
    material_root: Path | None,
    native_contexts: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    outputs: dict[str, Mapping[str, object]] = {}
    evidence: dict[str, dict[str, object]] = {}
    context: dict[str, object] = {
        "target": target,
        "structure_nodes": structure_nodes,
        "material_root": material_root,
        "member_outputs": outputs,
    }
    for member_id in MEMBER_IDS:
        model = member_models[member_id]
        if not isinstance(model, Mapping):
            raise ExternalDomainDnaError(f"{member_id} model is invalid")
        native_context = native_contexts.get(member_id)
        if not isinstance(native_context, Mapping):
            raise ExternalDomainDnaError(
                f"{member_id} current member-native replay evidence is missing"
            )
        member_context = {**context, "native_member_replay": native_context}
        member_evidence, derived_output = _replay_member_projection(
            member_id, model, member_context
        )
        evidence[member_id] = member_evidence
        outputs[member_id] = derived_output
    return evidence


def _expected_claim_boundary(target_id: str, scope_id: str) -> str:
    return (
        f"This external-domain DNA binds {target_id} within declared scope {scope_id} "
        "to a closed material inventory, "
        "structure graph, four member-native transitions, executable parent mappings, "
        "and code, material, test, oracle, and evidence relations. It proves deterministic "
        "model consistency and closure only for that declared scope; a complete file inventory "
        "does not imply complete whole-target semantics. External authenticity requires exact "
        "current-material replay and trusted whole-artifact identities. It does not establish factual truth, "
        "undocumented causality or intent, execute experiments, or replace the four "
        "native member owners."
    )


def _locator_contains(container: str, locator: str) -> bool:
    """Return whether one structure locator contains one exact occurrence locator."""

    normalized_container = container.replace("\\", "/")
    normalized_locator = locator.replace("\\", "/")
    if normalized_container == normalized_locator:
        return True
    container_match = re.fullmatch(r"(.+):(\d+)-(\d+)", normalized_container)
    locator_match = re.fullmatch(r"(.+):(\d+)", normalized_locator)
    if container_match and locator_match and container_match.group(1) == locator_match.group(1):
        line = int(locator_match.group(2))
        return int(container_match.group(2)) <= line <= int(container_match.group(3))
    return False


def _request_selector(request: Mapping[str, object]) -> Mapping[str, object]:
    return _mapping(
        request.get("selector"),
        {"selector_kind", "occurrence_id", "locator", "fingerprint", "parameters"},
        "SourceGuard extraction selector",
    )


def _derive_parent_function_block(
    target: Mapping[str, object],
    structure_nodes: Sequence[Mapping[str, object]],
    member_models: Mapping[str, object],
) -> dict[str, object]:
    """Derive the only allowed executable ResearchGuard composition parent."""

    target_id = str(target["target_id"])
    external_ids = {
        target_id,
        *(str(item["artifact_id"]) for item in _rows(target["artifacts"], "target artifacts")),
        *(str(item["node_id"]) for item in structure_nodes),
    }
    produced_by: dict[str, str] = {}
    consumed_by: dict[str, list[str]] = {}
    input_bindings: list[dict[str, str]] = []
    output_bindings: list[dict[str, str]] = []
    for member_id in MEMBER_IDS:
        model = member_models[member_id]
        if not isinstance(model, Mapping):
            raise ExternalDomainDnaError(f"{member_id} parent model is invalid")
        for object_id in _string_ids(model["owned_object_ids"], f"{member_id} owned ids"):
            produced_by[object_id] = member_id
        for raw in _rows(model["bindings"], f"{member_id} bindings"):
            binding = {key: str(raw[key]) for key in ("binding_id", "object_id", "direction", "role")}
            if binding["direction"] == "input_to_model":
                input_bindings.append({**binding, "member_id": member_id})
                consumed_by.setdefault(binding["object_id"], []).append(member_id)
            else:
                output_bindings.append({**binding, "member_id": member_id})
    external_consumers: dict[str, list[str]] = {object_id: [] for object_id in external_ids}
    for binding in input_bindings:
        if binding["object_id"] in external_consumers:
            external_consumers[binding["object_id"]].append(binding["member_id"])
    input_fields = [
        {
            "field_id": f"parent-input:{object_id}",
            "object_id": object_id,
            "owner_id": "target-boundary",
            "consumer_member_ids": sorted(set(external_consumers[object_id])),
        }
        for object_id in sorted(external_ids)
    ]
    state_fields = []
    effect_fields = []
    for member_id in MEMBER_IDS:
        model = member_models[member_id]
        assert isinstance(model, Mapping)
        state_fields.append(
            {
                "field_id": f"parent-state:{member_id}",
                "owner_id": member_id,
                "child_model_id": str(model["model_id"]),
                "pre_state_fingerprint": _digest(model["pre_state"]),
                "post_state_fingerprint": _digest(model["post_state"]),
            }
        )
        for index, effect in enumerate(_string_ids(model["effect"], f"{member_id} effects"), start=1):
            effect_fields.append(
                {
                    "effect_id": f"parent-effect:{member_id}:{index}",
                    "owner_id": member_id,
                    "effect": effect,
                }
            )
    output_fields = []
    output_dispositions = []
    handoffs = []
    output_binding_by_object = {row["object_id"]: row for row in output_bindings}
    for object_id in sorted(produced_by):
        owner = produced_by[object_id]
        consumers = sorted(set(consumed_by.get(object_id, [])))
        disposition = "consumed_and_exposed" if consumers else "exposed"
        output_fields.append(
            {
                "field_id": f"parent-output:{object_id}",
                "object_id": object_id,
                "owner_id": owner,
                "consumer_member_ids": consumers,
                "disposition": disposition,
            }
        )
        output_binding = output_binding_by_object.get(object_id)
        if output_binding is None:
            raise ExternalDomainDnaError(f"parent output {object_id!r} has no model-to-output binding")
        output_dispositions.append(
            {
                "disposition_id": f"parent-disposition:{object_id}",
                "child_model_id": str(member_models[owner]["model_id"]),  # type: ignore[index]
                "child_output_id": output_binding["binding_id"],
                "object_id": object_id,
                "owner_id": owner,
                "consumer_member_ids": consumers,
                "disposition": disposition,
            }
        )
        for consumer in consumers:
            input_binding = next(
                row for row in input_bindings
                if row["object_id"] == object_id and row["member_id"] == consumer
            )
            handoffs.append(
                {
                    "handoff_id": f"parent-handoff:{object_id}:{consumer}",
                    "object_id": object_id,
                    "producer_member_id": owner,
                    "producer_output_id": output_binding["binding_id"],
                    "consumer_member_id": consumer,
                    "consumer_input_id": input_binding["binding_id"],
                }
            )
    child_input_mappings = [
        {
            "mapping_id": f"parent-mapping:{row['binding_id']}",
            "child_model_id": str(member_models[row["member_id"]]["model_id"]),  # type: ignore[index]
            "child_input_id": row["binding_id"],
            "source_object_id": row["object_id"],
            "source_owner_id": produced_by.get(row["object_id"], "target-boundary"),
        }
        for row in sorted(input_bindings, key=lambda item: item["binding_id"])
    ]
    return {
        "schema_version": EXTERNAL_DOMAIN_PARENT_FUNCTION_BLOCK_SCHEMA,
        "block_id": f"function-block:{target_id}",
        "signature": "Input x State -> Set(Output x State)",
        "child_model_ids": [str(member_models[item]["model_id"]) for item in MEMBER_IDS],  # type: ignore[index]
        "input_fields": input_fields,
        "state_fields": state_fields,
        "output_fields": output_fields,
        "effect_fields": effect_fields,
        "child_input_mappings": child_input_mappings,
        "child_output_dispositions": output_dispositions,
        "handoffs": sorted(handoffs, key=lambda item: item["handoff_id"]),
        "claim_boundaries": [
            {"owner_id": item, "claim_boundary": str(member_models[item]["claim_boundary"])}  # type: ignore[index]
            for item in MEMBER_IDS
        ],
    }


def build_external_domain_parent_function_block(
    spec: Mapping[str, object],
) -> dict[str, object]:
    """Public deterministic builder used before final spec admission."""

    target = spec.get("target")
    structures = spec.get("structure_nodes")
    models = spec.get("member_models")
    if not isinstance(target, Mapping) or not isinstance(structures, list) or not isinstance(models, Mapping):
        raise ExternalDomainDnaError("parent FunctionBlock inputs are incomplete")
    if any(not isinstance(item, Mapping) for item in structures):
        raise ExternalDomainDnaError("parent FunctionBlock structure is invalid")
    return _derive_parent_function_block(target, structures, models)  # type: ignore[arg-type]


def _validate_spec(raw: object) -> Mapping[str, object]:
    spec = _mapping(
        raw,
        {
            "schema_version",
            "target",
            "structure_nodes",
            "member_models",
            "parent_function_block",
            "dependency_edges",
            "scope_authority_binding",
            "claim_boundary",
        },
        "external domain DNA spec",
    )
    if spec["schema_version"] != EXTERNAL_DOMAIN_DNA_SPEC_SCHEMA:
        raise ExternalDomainDnaError("external domain DNA spec schema is not current")
    authority_binding = _mapping(
        spec["scope_authority_binding"],
        {
            "authority_id",
            "authority_fingerprint",
            "producer_descriptor_fingerprint",
        },
        "external scope authority binding",
    )
    _text(authority_binding["authority_id"], "external scope authority id")
    for field in ("authority_fingerprint", "producer_descriptor_fingerprint"):
        identity = _text(authority_binding[field], f"external scope authority {field}")
        if not identity.startswith("sha256:") or not _SHA256.fullmatch(identity[7:]):
            raise ExternalDomainDnaError(
                f"external scope authority {field} is not a sha256 identity"
            )
    _text(spec["claim_boundary"], "external domain DNA claim boundary")
    target = _mapping(
        spec["target"],
        {
            "target_id", "title", "kind", "version", "official_url",
            "material_inventory_policy", "model_scope", "source_authorities", "artifacts",
        },
        "external target",
    )
    object_owners: dict[str, str] = {}
    target_id = _text(target["target_id"], "target id")
    _register(object_owners, target_id, "target")
    for field in ("title", "kind", "version", "official_url"):
        _text(target[field], f"target {field}")
    policy = _mapping(
        target["material_inventory_policy"],
        {
            "policy_id", "root_kind", "include_regular_files", "symlink_policy",
            "excluded_relative_paths",
        },
        "material inventory policy",
    )
    if policy["policy_id"] != MATERIAL_INVENTORY_POLICY_ID:
        raise ExternalDomainDnaError("material inventory policy is not current")
    if policy["root_kind"] != "closed-directory-tree" or policy["include_regular_files"] is not True:
        raise ExternalDomainDnaError("material inventory must close one complete directory tree")
    if policy["symlink_policy"] != "reject":
        raise ExternalDomainDnaError("material inventory symlink policy must reject")
    exclusions = _string_ids(
        policy["excluded_relative_paths"], "material inventory exclusions", allow_empty=True
    )
    if exclusions:
        raise ExternalDomainDnaError("current material inventory accepts no caller exclusions")
    model_scope = _mapping(
        target["model_scope"],
        {
            "scope_id",
            "purpose",
            "scope_kind",
            "included_question_ids",
            "included_structure_node_ids",
            "excluded_semantic_region_ids",
            "expansion_frontier_ids",
            "completion_status",
            "whole_target_semantics_claimed",
        },
        "external target model scope",
    )
    scope_id = _text(model_scope["scope_id"], "model scope id")
    _register(object_owners, scope_id, "target model scope")
    _text(model_scope["purpose"], "model scope purpose")
    _string_ids(model_scope["included_question_ids"], "model scope question ids")
    included_structure_ids = set(
        _string_ids(
            model_scope["included_structure_node_ids"],
            "model scope included structure ids",
        )
    )
    excluded_semantic_ids = _string_ids(
        model_scope["excluded_semantic_region_ids"],
        "model scope excluded semantic ids",
        allow_empty=True,
    )
    frontier_ids = _string_ids(
        model_scope["expansion_frontier_ids"],
        "model scope expansion frontier ids",
        allow_empty=True,
    )
    for object_id in (*excluded_semantic_ids, *frontier_ids):
        _register(object_owners, object_id, "target scope frontier")
    if model_scope["scope_kind"] == "bounded_research_question":
        if (
            model_scope["completion_status"] != "complete_within_declared_scope"
            or model_scope["whole_target_semantics_claimed"] is not False
            or not excluded_semantic_ids
            or not frontier_ids
        ):
            raise ExternalDomainDnaError(
                "bounded target scope must preserve its semantic exclusions and expansion frontier"
            )
    elif model_scope["scope_kind"] == "whole_target_semantics":
        if (
            model_scope["completion_status"] != "complete_whole_target"
            or model_scope["whole_target_semantics_claimed"] is not True
            or excluded_semantic_ids
            or frontier_ids
        ):
            raise ExternalDomainDnaError("whole-target semantic scope is internally inconsistent")
    else:
        raise ExternalDomainDnaError("model scope kind is not current")
    artifacts = _rows(target["artifacts"], "target artifacts")
    if not artifacts:
        raise ExternalDomainDnaError("target artifacts must not be empty")
    artifact_paths: set[str] = set()
    for row in artifacts:
        artifact = _mapping(
            row,
            {
                "artifact_id",
                "role",
                "official_url",
                "relative_path",
                "sha256",
                "byte_length",
                "embedded",
                "disposition",
            },
            "target artifact",
        )
        artifact_id = _text(artifact["artifact_id"], "artifact id")
        _register(object_owners, artifact_id, "target artifact")
        for field in ("role", "official_url", "relative_path"):
            _text(artifact[field], f"artifact {field}")
        relative_path = str(artifact["relative_path"]).replace("\\", "/")
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts or relative_path in artifact_paths:
            raise ExternalDomainDnaError("artifact relative paths must be unique and non-escaping")
        artifact_paths.add(relative_path)
        if not _SHA256.fullmatch(str(artifact["sha256"])):
            raise ExternalDomainDnaError("artifact sha256 must be 64 lowercase hex characters")
        if not isinstance(artifact["byte_length"], int) or artifact["byte_length"] < 1:
            raise ExternalDomainDnaError("artifact byte length must be positive")
        if not isinstance(artifact["embedded"], bool):
            raise ExternalDomainDnaError("artifact embedded must be boolean")
        if artifact["embedded"] is not False:
            raise ExternalDomainDnaError("external target bytes must not be embedded")
        if artifact["disposition"] not in {"modeled", "supporting_material"}:
            raise ExternalDomainDnaError("artifact disposition is not current")

    structure = _rows(spec["structure_nodes"], "structure nodes")
    if not structure:
        raise ExternalDomainDnaError("structure nodes must not be empty")
    parents: dict[str, str | None] = {}
    for row in structure:
        node = _mapping(
            row,
            {
                "node_id", "parent_id", "kind", "label", "locator", "member_ids",
                "semantic_role", "artifact_ids", "bound_object_ids",
            },
            "structure node",
        )
        node_id = _text(node["node_id"], "structure node id")
        _register(object_owners, node_id, "structure node")
        parent = node["parent_id"]
        parents[node_id] = None if parent is None else _text(parent, "structure parent id")
        for field in ("kind", "label", "locator", "semantic_role"):
            _text(node[field], f"structure node {field}")
        members = _string_ids(node["member_ids"], "structure member ids")
        if not set(members).issubset(MEMBER_IDS):
            raise ExternalDomainDnaError("structure node names an unknown member")
        _string_ids(node["artifact_ids"], "structure artifact ids", allow_empty=True)
        _string_ids(node["bound_object_ids"], "structure bound object ids", allow_empty=True)
    roots = [node_id for node_id, parent_id in parents.items() if parent_id is None]
    if len(roots) != 1:
        raise ExternalDomainDnaError("structure hierarchy requires exactly one root")
    if any(parent_id is not None and parent_id not in parents for parent_id in parents.values()):
        raise ExternalDomainDnaError("structure hierarchy has an unknown parent")
    if not included_structure_ids.issubset(parents):
        raise ExternalDomainDnaError("model scope includes an unknown structure node")
    if model_scope["scope_kind"] == "whole_target_semantics" and included_structure_ids != set(parents):
        raise ExternalDomainDnaError("whole-target semantics requires the complete structure denominator")

    source_authorities = _rows(target["source_authorities"], "target source authorities")
    if len(source_authorities) != 1:
        raise ExternalDomainDnaError("target requires exactly one current source authority")
    source_authority = _mapping(
        source_authorities[0], {"source_id", "role", "coverage_ids"}, "source authority"
    )
    expected_source_id = f"source:{target_id}"
    if source_authority["source_id"] != expected_source_id:
        raise ExternalDomainDnaError("source authority id is not derived from the target identity")
    kind = str(target["kind"]).lower()
    expected_role = (
        "primary_author_source"
        if "paper" in kind or "research" in kind
        else "primary_workflow_material"
        if "workflow" in kind or "test" in kind
        else "primary_target_material"
    )
    if source_authority["role"] != expected_role:
        raise ExternalDomainDnaError("source authority role does not match target kind")
    expected_coverage = {
        target_id,
        *(str(item["artifact_id"]) for item in artifacts),
        *parents,
    }
    if set(_string_ids(source_authority["coverage_ids"], "source authority coverage")) != expected_coverage:
        raise ExternalDomainDnaError("source authority coverage is not denominator-complete")

    member_models = _mapping(spec["member_models"], set(MEMBER_IDS), "member models")
    for member_id in MEMBER_IDS:
        model = _mapping(
            member_models[member_id],
            {
                "model_id",
                "member_id",
                "behavior_id",
                "native_route",
                "native_binding",
                "scope_binding",
                "input",
                "pre_state",
                "output",
                "post_state",
                "effect",
                "protected_failure",
                "owned_object_ids",
                "bindings",
                "test_bindings",
                "oracle_binding",
                "evidence_bindings",
                "claim_boundary",
            },
            f"{member_id} model",
        )
        if model["member_id"] != member_id:
            raise ExternalDomainDnaError(f"{member_id} model has a foreign member id")
        if model["behavior_id"] != MEMBER_BEHAVIOR_IDS[member_id]:
            raise ExternalDomainDnaError(f"{member_id} model has a foreign behavior id")
        native_route = _mapping(
            model["native_route"],
            {"blueprint_checker", "owner_attestation", "external_transition"},
            f"{member_id} native route",
        )
        if _canonical(native_route) != _canonical(MEMBER_NATIVE_ROUTES[member_id]):
            raise ExternalDomainDnaError(f"{member_id} native route is stale or foreign")
        native_binding = _mapping(
            model["native_binding"], NATIVE_BINDING_FIELDS, f"{member_id} native binding"
        )
        for field in (
            "envelope_id",
            "native_model_id",
            "expected_target_anchor_id",
            "behavior_manifest_id",
        ):
            _text(native_binding[field], f"{member_id} native binding {field}")
        for field in (
            "envelope_fingerprint",
            "model_fingerprint",
            "expected_target_anchor_fingerprint",
            "behavior_manifest_fingerprint",
        ):
            identity = _text(native_binding[field], f"{member_id} native binding {field}")
            if not identity.startswith("sha256:") or not _SHA256.fullmatch(identity[7:]):
                raise ExternalDomainDnaError(
                    f"{member_id} native binding {field} is not a sha256 identity"
                )
        if native_binding["domain_behavior_id"] != MEMBER_BEHAVIOR_IDS[member_id]:
            raise ExternalDomainDnaError(
                f"{member_id} native binding behavior is stale or foreign"
            )
        native_receipt_ids = _string_ids(
            native_binding["native_receipt_ids"],
            f"{member_id} native receipt ids",
        )
        if len(native_receipt_ids) != 1:
            raise ExternalDomainDnaError(
                f"{member_id} external-object DNA requires one exact current native receipt"
            )
        for native_receipt_id in native_receipt_ids:
            _register(object_owners, native_receipt_id, f"{member_id} native receipt")
        for route_role, entrypoint in MEMBER_NATIVE_ROUTES[member_id].items():
            _register(object_owners, entrypoint, f"{member_id} code:{route_role}")
        model_id = _text(model["model_id"], f"{member_id} model id")
        _register(object_owners, model_id, f"{member_id} model")
        for field in ("input", "pre_state", "output", "post_state"):
            if not isinstance(model[field], Mapping) or not model[field]:
                raise ExternalDomainDnaError(f"{member_id} {field} must be a non-empty object")
        effects = _string_ids(model["effect"], f"{member_id} effects")
        _text(model["protected_failure"], f"{member_id} protected failure")
        _text(model["claim_boundary"], f"{member_id} claim boundary")
        owned = _string_ids(model["owned_object_ids"], f"{member_id} owned object ids")
        for object_id in owned:
            _register(object_owners, object_id, member_id)
        created = _OUTPUT_VALIDATORS[member_id](model["output"])
        if set(created) != set(owned) or len(created) != len(owned):
            raise ExternalDomainDnaError(
                f"{member_id} output and owned-object denominator differ"
            )
        binding_ids: set[str] = set()
        output_binding_ids: set[str] = set()
        output_binding_objects: list[str] = []
        for row in _rows(model["bindings"], f"{member_id} bindings"):
            binding = _mapping(
                row,
                {"binding_id", "object_id", "direction", "role"},
                f"{member_id} binding",
            )
            binding_id = _text(binding["binding_id"], f"{member_id} binding id")
            if binding_id in binding_ids:
                raise ExternalDomainDnaError(f"{member_id} binding ids must be unique")
            binding_ids.add(binding_id)
            _text(binding["object_id"], f"{member_id} binding object id")
            if binding["direction"] not in {"input_to_model", "model_to_output"}:
                raise ExternalDomainDnaError(f"{member_id} binding direction is invalid")
            _text(binding["role"], f"{member_id} binding role")
            if binding["direction"] == "model_to_output":
                output_binding_ids.add(binding_id)
                output_binding_objects.append(str(binding["object_id"]))
        if set(output_binding_objects) != set(owned) or len(output_binding_objects) != len(owned):
            raise ExternalDomainDnaError(f"{member_id} output binding denominator is incomplete")
        scope_binding = _mapping(
            model["scope_binding"],
            {
                "scope_id",
                "declared_complete_object_ids",
                "declared_input_object_ids",
                "expansion_frontier_ids",
                "completion_status",
            },
            f"{member_id} scope binding",
        )
        declared_inputs = {
            str(row["object_id"])
            for row in _rows(model["bindings"], f"{member_id} bindings")
            if row["direction"] == "input_to_model"
        }
        expected_member_completion = (
            "complete_whole_target"
            if model_scope["scope_kind"] == "whole_target_semantics"
            else "complete_within_declared_scope"
        )
        if (
            scope_binding["scope_id"] != scope_id
            or set(
                _string_ids(
                    scope_binding["declared_complete_object_ids"],
                    f"{member_id} declared complete object ids",
                )
            )
            != set(owned)
            or set(
                _string_ids(
                    scope_binding["declared_input_object_ids"],
                    f"{member_id} declared input object ids",
                )
            )
            != declared_inputs
            or set(
                _string_ids(
                    scope_binding["expansion_frontier_ids"],
                    f"{member_id} expansion frontier ids",
                    allow_empty=True,
                )
            )
            != set(frontier_ids)
            or scope_binding["completion_status"] != expected_member_completion
        ):
            raise ExternalDomainDnaError(
                f"{member_id} declared scope/object denominator is incomplete or foreign"
            )
        test_rows = _rows(model["test_bindings"], f"{member_id} test bindings")
        if len(test_rows) < 2:
            raise ExternalDomainDnaError(f"{member_id} requires native good and bad test bindings")
        test_roles: set[str] = set()
        test_ids: set[str] = set()
        oracle_ids: set[str] = set()
        for row in test_rows:
            test = _mapping(
                row, {"test_id", "behavior_id", "role", "oracle_id"}, f"{member_id} test binding"
            )
            test_id = _text(test["test_id"], f"{member_id} test id")
            if test_id in test_ids:
                raise ExternalDomainDnaError(f"{member_id} test ids must be unique")
            test_ids.add(test_id)
            _register(object_owners, test_id, f"{member_id} test")
            if test["behavior_id"] != model["behavior_id"]:
                raise ExternalDomainDnaError(f"{member_id} test binds another behavior")
            if test["role"] not in {"known_good", "known_bad"}:
                raise ExternalDomainDnaError(f"{member_id} test role is invalid")
            test_roles.add(str(test["role"]))
            oracle_ids.add(_text(test["oracle_id"], f"{member_id} test oracle id"))
        if test_roles != {"known_good", "known_bad"} or len(oracle_ids) != 1:
            raise ExternalDomainDnaError(f"{member_id} test role/oracle coverage is incomplete")
        expected_good_case_id = f"test:{member_id}:external-object-known-good"
        expected_bad_case_id = f"test:{member_id}:external-object-known-bad"
        expected_oracle_id = f"oracle:{member_id}:external-object-transition"
        expected_test_rows = [
            {
                "test_id": expected_good_case_id,
                "behavior_id": MEMBER_BEHAVIOR_IDS[member_id],
                "role": "known_good",
                "oracle_id": expected_oracle_id,
            },
            {
                "test_id": expected_bad_case_id,
                "behavior_id": MEMBER_BEHAVIOR_IDS[member_id],
                "role": "known_bad",
                "oracle_id": expected_oracle_id,
            },
        ]
        if _canonical(test_rows) != _canonical(expected_test_rows):
            raise ExternalDomainDnaError(
                f"{member_id} target-native test identities are stale or foreign"
            )
        oracle = _mapping(
            model["oracle_binding"],
            {
                "oracle_id", "owner_id", "checker_entrypoint", "good_case_id",
                "bad_case_id", "protected_failure",
            },
            f"{member_id} oracle binding",
        )
        if (
            oracle["owner_id"] != member_id
            or oracle["checker_entrypoint"] != MEMBER_NATIVE_ROUTES[member_id]["external_transition"]
            or oracle["oracle_id"] not in oracle_ids
            or oracle["good_case_id"] not in test_ids
            or oracle["bad_case_id"] not in test_ids
            or oracle["protected_failure"] != model["protected_failure"]
        ):
            raise ExternalDomainDnaError(f"{member_id} oracle binding is stale or foreign")
        expected_oracle = {
            "oracle_id": expected_oracle_id,
            "owner_id": member_id,
            "checker_entrypoint": MEMBER_NATIVE_ROUTES[member_id]["external_transition"],
            "good_case_id": expected_good_case_id,
            "bad_case_id": expected_bad_case_id,
            "protected_failure": model["protected_failure"],
        }
        if _canonical(oracle) != _canonical(expected_oracle):
            raise ExternalDomainDnaError(
                f"{member_id} target-native oracle identity is stale or foreign"
            )
        _register(object_owners, str(oracle["oracle_id"]), f"{member_id} oracle")
        evidence_rows = _rows(model["evidence_bindings"], f"{member_id} evidence bindings")
        evidence_roles: set[str] = set()
        evidence_ids: set[str] = set()
        for row in evidence_rows:
            evidence = _mapping(
                row,
                {"evidence_id", "role", "subject_id", "producer_entrypoint", "status"},
                f"{member_id} evidence binding",
            )
            evidence_id = _text(evidence["evidence_id"], f"{member_id} evidence id")
            if evidence_id in evidence_ids:
                raise ExternalDomainDnaError(f"{member_id} evidence ids must be unique")
            evidence_ids.add(evidence_id)
            _register(object_owners, evidence_id, f"{member_id} evidence")
            evidence_roles.add(_text(evidence["role"], f"{member_id} evidence role"))
            _text(evidence["subject_id"], f"{member_id} evidence subject")
            _text(evidence["producer_entrypoint"], f"{member_id} evidence producer")
            if evidence["status"] not in {"current", "not_run"}:
                raise ExternalDomainDnaError(f"{member_id} evidence status is invalid")
        if evidence_roles != {"model", "material", "test", "oracle", "native_receipt"}:
            raise ExternalDomainDnaError(f"{member_id} evidence role denominator is incomplete")
        expected_evidence_rows = [
            {
                "evidence_id": f"evidence:{member_id}:model",
                "role": "model",
                "subject_id": model_id,
                "producer_entrypoint": MEMBER_NATIVE_ROUTES[member_id]["blueprint_checker"],
                "status": "current",
            },
            {
                "evidence_id": f"evidence:{member_id}:material",
                "role": "material",
                "subject_id": target_id,
                "producer_entrypoint": MEMBER_NATIVE_ROUTES[member_id]["external_transition"],
                "status": "current",
            },
            {
                "evidence_id": f"evidence:{member_id}:test",
                "role": "test",
                "subject_id": expected_good_case_id,
                "producer_entrypoint": MEMBER_NATIVE_ROUTES[member_id]["external_transition"],
                "status": "current",
            },
            {
                "evidence_id": f"evidence:{member_id}:oracle",
                "role": "oracle",
                "subject_id": expected_oracle_id,
                "producer_entrypoint": MEMBER_NATIVE_ROUTES[member_id]["external_transition"],
                "status": "current",
            },
            {
                "evidence_id": f"evidence:{member_id}:native_receipt",
                "role": "native_receipt",
                "subject_id": native_receipt_ids[0],
                "producer_entrypoint": MEMBER_NATIVE_ROUTES[member_id]["owner_attestation"],
                "status": "current",
            },
        ]
        if _canonical(evidence_rows) != _canonical(expected_evidence_rows):
            raise ExternalDomainDnaError(
                f"{member_id} model/material/test/oracle/native-receipt evidence is stale or foreign"
            )

    source_model = member_models["sourceguard"]
    assert isinstance(source_model, Mapping)
    source_input = source_model["input"]
    source_output = source_model["output"]
    if not isinstance(source_input, Mapping) or not isinstance(source_output, Mapping):
        raise ExternalDomainDnaError("SourceGuard source authority projection is invalid")
    if (
        _canonical(source_input.get("source_roles")) != _canonical(source_authorities)
        or _canonical(source_output.get("source_roles")) != _canonical(source_authorities)
    ):
        raise ExternalDomainDnaError("SourceGuard roles/coverage differ from target authority")

    artifact_ids = {str(item["artifact_id"]) for item in artifacts}
    all_owned_ids = {
        str(item)
        for member_id in MEMBER_IDS
        for item in member_models[member_id]["owned_object_ids"]  # type: ignore[index]
    }
    structure_artifact_ids: set[str] = set()
    structure_bound_ids: set[str] = set()
    for row in structure:
        node_artifacts = set(_string_ids(row["artifact_ids"], "structure artifact ids", allow_empty=True))
        node_objects = set(_string_ids(row["bound_object_ids"], "structure bound ids", allow_empty=True))
        if not node_artifacts.issubset(artifact_ids):
            raise ExternalDomainDnaError("structure binds an unknown artifact")
        if not node_objects.issubset(all_owned_ids):
            raise ExternalDomainDnaError("structure binds an unknown member object")
        structure_artifact_ids.update(node_artifacts)
        structure_bound_ids.update(node_objects)
    if structure_artifact_ids != artifact_ids:
        raise ExternalDomainDnaError("structure-to-artifact denominator is incomplete")
    if structure_bound_ids != all_owned_ids:
        raise ExternalDomainDnaError("structure-to-member-object denominator is incomplete")

    extraction_requests = source_input.get("extraction_requests")
    if not isinstance(extraction_requests, list):
        raise ExternalDomainDnaError("SourceGuard extraction denominator is invalid")
    structures_by_object = {
        str(object_id): row
        for row in structure
        for object_id in row["bound_object_ids"]  # type: ignore[index]
    }
    for request in extraction_requests:
        if not isinstance(request, Mapping):
            raise ExternalDomainDnaError("SourceGuard extraction request is invalid")
        anchor_id = str(request.get("anchor_id", ""))
        if str(request.get("source_id", "")) != expected_source_id:
            raise ExternalDomainDnaError(
                "SourceGuard extraction source id is outside target source authorities"
            )
        selector = _request_selector(request)
        node = structures_by_object.get(anchor_id)
        if node is None or not _locator_contains(
            str(node["locator"]), str(selector["locator"])
        ):
            raise ExternalDomainDnaError("SourceGuard anchor locator is rebound from its structure object")

    required_external_inputs = {target_id, *artifact_ids, *parents}
    bound_external_inputs = {
        str(row["object_id"])
        for member_id in MEMBER_IDS
        for row in _rows(member_models[member_id]["bindings"], f"{member_id} bindings")  # type: ignore[index]
        if row["direction"] == "input_to_model" and str(row["object_id"]) in required_external_inputs
    }
    if bound_external_inputs != required_external_inputs:
        missing = sorted(required_external_inputs - bound_external_inputs)
        raise ExternalDomainDnaError(
            "external input denominator is not consumed: " + ",".join(missing)
        )

    expected_parent = _derive_parent_function_block(target, structure, member_models)
    parent = _mapping(
        spec["parent_function_block"], set(expected_parent), "parent FunctionBlock"
    )
    if _canonical(parent) != _canonical(expected_parent):
        raise ExternalDomainDnaError("parent FunctionBlock mappings/dispositions are not exhaustive")
    parent_block_id = str(parent["block_id"])
    _register(object_owners, parent_block_id, "researchguard parent FunctionBlock")

    expected_claim_boundary = _expected_claim_boundary(target_id, scope_id)
    if spec["claim_boundary"] != expected_claim_boundary:
        raise ExternalDomainDnaError("top-level external DNA claim boundary is overbroad or stale")

    expected_dependency_edges = [
        {
            "edge_id": f"dependency:{left}:{right}",
            "from_id": str(member_models[left]["model_id"]),  # type: ignore[index]
            "to_id": str(member_models[right]["model_id"]),  # type: ignore[index]
            "relation": "member_native_handoff",
        }
        for left, right in zip(MEMBER_IDS, MEMBER_IDS[1:])
    ]
    if _canonical(spec["dependency_edges"]) != _canonical(expected_dependency_edges):
        raise ExternalDomainDnaError("member dependency denominator is not exact-current")

    graph_edges: list[tuple[str, str, str]] = []
    graph_edges.append(("parent-admission", target_id, parent_block_id))
    graph_edges.append(("target-model-scope", target_id, scope_id))
    for input_field in _rows(parent["input_fields"], "parent input fields"):
        source_object_id = _text(input_field["object_id"], "parent input object id")
        graph_edges.append(
            (
                f"parent-input:{source_object_id}",
                source_object_id,
                parent_block_id,
            )
        )
    for object_id in excluded_semantic_ids:
        graph_edges.append((f"scope-exclusion:{object_id}", scope_id, object_id))
    for object_id in frontier_ids:
        graph_edges.append((f"scope-frontier:{object_id}", scope_id, object_id))
    for member_id in MEMBER_IDS:
        graph_edges.append(
            (
                f"parent-child:{member_id}",
                parent_block_id,
                str(member_models[member_id]["model_id"]),  # type: ignore[index]
            )
        )
        graph_edges.append(
            (
                f"scope-member:{member_id}",
                scope_id,
                str(member_models[member_id]["model_id"]),  # type: ignore[index]
            )
        )
    root_id = roots[0]
    graph_edges.append(("target-structure-root", target_id, root_id))
    for artifact in artifacts:
        artifact_id = str(artifact["artifact_id"])
        graph_edges.append((f"target-artifact:{artifact_id}", target_id, artifact_id))
    for child_id, parent_id in parents.items():
        if parent_id is not None:
            graph_edges.append((f"hierarchy:{child_id}", parent_id, child_id))
    for row in structure:
        node_id = str(row["node_id"])
        for artifact_id in _string_ids(row["artifact_ids"], "structure artifact ids", allow_empty=True):
            graph_edges.append(
                (f"artifact-structure:{artifact_id}:{node_id}", artifact_id, node_id)
            )
        for member_id in _string_ids(row["member_ids"], "structure member ids"):
            graph_edges.append(
                (
                    f"structure-member:{node_id}:{member_id}",
                    node_id,
                    str(member_models[member_id]["model_id"]),  # type: ignore[index]
                )
            )
        for object_id in _string_ids(row["bound_object_ids"], "structure bound ids", allow_empty=True):
            graph_edges.append(
                (f"structure-object:{node_id}:{object_id}", node_id, object_id)
            )
    for member_id in MEMBER_IDS:
        model = member_models[member_id]
        assert isinstance(model, Mapping)
        model_id = str(model["model_id"])
        native_route = model["native_route"]
        assert isinstance(native_route, Mapping)
        for route_role in ("blueprint_checker", "owner_attestation", "external_transition"):
            entrypoint = str(native_route[route_role])
            graph_edges.append(
                (f"code-model:{member_id}:{route_role}", entrypoint, model_id)
            )
        oracle = model["oracle_binding"]
        assert isinstance(oracle, Mapping)
        oracle_id = str(oracle["oracle_id"])
        for test in _rows(model["test_bindings"], f"{member_id} test bindings"):
            test_id = str(test["test_id"])
            graph_edges.append(
                (f"oracle-test:{member_id}:{test_id}", oracle_id, test_id)
            )
            graph_edges.append(
                (f"test-model:{member_id}:{test_id}", test_id, model_id)
            )
        for evidence in _rows(model["evidence_bindings"], f"{member_id} evidence bindings"):
            evidence_id = str(evidence["evidence_id"])
            graph_edges.append(
                (f"evidence-model:{member_id}:{evidence_id}", evidence_id, model_id)
            )
            producer_id = str(evidence["producer_entrypoint"])
            subject_id = str(evidence["subject_id"])
            graph_edges.append(
                (
                    f"evidence-producer:{member_id}:{evidence_id}",
                    producer_id,
                    evidence_id,
                )
            )
            graph_edges.append(
                (
                    f"evidence-subject:{member_id}:{evidence_id}",
                    evidence_id,
                    subject_id,
                )
            )
        for row in _rows(model["bindings"], f"{member_id} bindings"):
            object_id = str(row["object_id"])
            if object_id not in object_owners:
                raise ExternalDomainDnaError(
                    f"{member_id} binding refers to unknown object {object_id!r}"
                )
            if row["direction"] == "input_to_model":
                graph_edges.append((str(row["binding_id"]), object_id, model_id))
            else:
                graph_edges.append((str(row["binding_id"]), model_id, object_id))
    dependency_ids: set[str] = set()
    for row in _rows(spec["dependency_edges"], "dependency edges"):
        edge = _mapping(
            row, {"edge_id", "from_id", "to_id", "relation"}, "dependency edge"
        )
        edge_id = _text(edge["edge_id"], "dependency edge id")
        if edge_id in dependency_ids:
            raise ExternalDomainDnaError("dependency edge ids must be unique")
        dependency_ids.add(edge_id)
        source = _text(edge["from_id"], "dependency source id")
        target_id = _text(edge["to_id"], "dependency target id")
        if source not in object_owners or target_id not in object_owners:
            raise ExternalDomainDnaError(
                f"dependency edge {edge_id!r} refers to an unknown object"
            )
        if source == target_id:
            raise ExternalDomainDnaError("dependency edge cannot be a self edge")
        _text(edge["relation"], "dependency relation")
        graph_edges.append((edge_id, source, target_id))
    if len({edge_id for edge_id, _, _ in graph_edges}) != len(graph_edges):
        raise ExternalDomainDnaError("all hierarchy, binding, and dependency edge ids must be unique")

    adjacency: dict[str, set[str]] = {item: set() for item in object_owners}
    indegree = {item: 0 for item in object_owners}
    for _, source, target_id in graph_edges:
        if target_id not in adjacency[source]:
            adjacency[source].add(target_id)
            indegree[target_id] += 1
    queue = sorted(item for item, count in indegree.items() if count == 0)
    visited: list[str] = []
    while queue:
        current = queue.pop(0)
        visited.append(current)
        for dependent in sorted(adjacency[current]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)
                queue.sort()
    if len(visited) != len(object_owners):
        raise ExternalDomainDnaError("external domain DNA dependency graph is cyclic")
    return spec


def _member_output_kinds(member_id: str, output: Mapping[str, object]) -> dict[str, set[str]]:
    """Project member-owned object ids into authority-comparable semantic kinds."""

    if member_id == "sourceguard":
        return {
            "source_role": {
                str(item["source_id"])
                for item in _rows(output["source_roles"], "SourceGuard source roles")
            },
            "claim_anchor": {
                str(item["anchor_id"])
                for item in _rows(output["claim_anchors"], "SourceGuard claim anchors")
            },
            "gap": {
                str(item["gap_id"])
                for item in _rows(output["gaps"], "SourceGuard gaps")
            },
        }
    if member_id == "traceguard":
        return {
            "ordered_event": {
                str(item["event_id"])
                for item in _rows(output["ordered_events"], "TraceGuard ordered events")
            },
            "storyline": {
                str(item["storyline_id"])
                for item in _rows(output["storylines"], "TraceGuard storylines")
            },
            "gap": {
                str(item["gap_id"])
                for item in _rows(output["gaps"], "TraceGuard gaps")
            },
        }
    if member_id == "logicguard":
        return {
            "claim": {
                str(item["claim_id"])
                for item in _rows(output["claims"], "LogicGuard claims")
            },
            "argument_edge": {
                str(item["edge_id"])
                for item in _rows(output["argument_edges"], "LogicGuard argument edges")
            },
            "gap": {
                str(item["gap_id"])
                for item in _rows(output["gaps"], "LogicGuard gaps")
            },
        }
    return {
        "hypothesis": {
            str(item["hypothesis_id"])
            for item in _rows(output["hypotheses"], "ExperimentGuard hypotheses")
        },
        "experiment": {
            str(item["experiment_id"])
            for item in _rows(output["experiments"], "ExperimentGuard experiments")
        },
        "gap": {
            str(item["gap_id"])
            for item in _rows(output["gaps"], "ExperimentGuard gaps")
        },
    }


def _authority_ledger_row(
    *,
    obligation_id: str,
    kind: str,
    required: Iterable[str],
    produced: Iterable[str] = (),
    consumed: Iterable[str] = (),
    disposed: Iterable[str] = (),
    mismatch_details: Iterable[str] = (),
) -> dict[str, object]:
    required_ids = set(str(item) for item in required)
    produced_ids = set(str(item) for item in produced)
    consumed_ids = set(str(item) for item in consumed)
    disposed_ids = set(str(item) for item in disposed)
    observed = produced_ids | consumed_ids | disposed_ids
    missing = required_ids - observed
    unexpected = observed - required_ids
    details = sorted(set(str(item) for item in mismatch_details if str(item)))
    return {
        "obligation_id": obligation_id,
        "kind": kind,
        "required_object_ids": sorted(required_ids),
        "produced_object_ids": sorted(produced_ids),
        "consumed_object_ids": sorted(consumed_ids),
        "disposed_object_ids": sorted(disposed_ids),
        "missing_object_ids": sorted(missing),
        "unexpected_object_ids": sorted(unexpected),
        "mismatch_details": details,
        "status": "satisfied" if not missing and not unexpected and not details else "unsatisfied",
    }


def _decode_scope_authority_record(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        try:
            return json.loads(bytes(value).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ExternalScopeAuthorityError(
                f"external scope authority is not valid JSON: {exc}"
            ) from exc
    return value


def _portable_scope_authority_evaluation(
    evaluation: Mapping[str, object],
) -> dict[str, object]:
    """Remove the already embedded authority body from its derived evaluation."""

    return {
        key: value
        for key, value in evaluation.items()
        if key != "authority"
    }


def _evaluate_scope_authority(
    spec: Mapping[str, object],
    record_value: object,
    *,
    trusted_authority_fingerprints: Iterable[str] = (),
    trusted_producer_descriptor_fingerprints: Iterable[str] = (),
) -> dict[str, object]:
    """Compare candidate scope/output/parent coverage with an independent denominator."""

    if record_value is None:
        return {
            "authority_status": "missing",
            "authority_licensed": False,
            "coverage_complete": False,
            "authority_fingerprint": "",
            "producer_descriptor_fingerprint": "",
            "authority_id": "",
            "obligation_ledger": [],
            "gaps": [
                {
                    "code": "scope-authority-missing",
                    "detail": (
                        "candidate DNA has no independently produced signed scope authority"
                    ),
                    "object_ids": [],
                }
            ],
            "authority": None,
        }
    try:
        validated = validate_external_scope_authority_record(
            _decode_scope_authority_record(record_value)
        )
    except (ExternalScopeAuthorityError, TypeError, ValueError) as exc:
        return {
            "authority_status": "invalid",
            "authority_licensed": False,
            "coverage_complete": False,
            "authority_fingerprint": "",
            "producer_descriptor_fingerprint": "",
            "authority_id": "",
            "obligation_ledger": [],
            "gaps": [
                {
                    "code": "scope-authority-invalid",
                    "detail": str(exc),
                    "object_ids": [],
                }
            ],
            "authority": None,
        }

    authority = validated["authority"]
    assert isinstance(authority, Mapping)
    authority_target = authority["target"]
    authority_scope = authority["scope"]
    assert isinstance(authority_target, Mapping) and isinstance(authority_scope, Mapping)
    authority_fingerprint = str(validated["authority_fingerprint"])
    descriptor_fingerprint = str(validated["producer_descriptor_fingerprint"])
    trusted_authorities = {
        str(item).strip() for item in trusted_authority_fingerprints if str(item).strip()
    }
    trusted_producers = {
        str(item).strip()
        for item in trusted_producer_descriptor_fingerprints
        if str(item).strip()
    }
    licensed = (
        authority_fingerprint in trusted_authorities
        or descriptor_fingerprint in trusted_producers
    )

    target = spec["target"]
    member_models = spec["member_models"]
    structures = spec["structure_nodes"]
    parent = spec["parent_function_block"]
    binding = spec["scope_authority_binding"]
    assert (
        isinstance(target, Mapping)
        and isinstance(member_models, Mapping)
        and isinstance(structures, list)
        and isinstance(parent, Mapping)
        and isinstance(binding, Mapping)
    )
    ledger: list[dict[str, object]] = []
    gaps: list[dict[str, object]] = []

    def compare_exact(obligation_id: str, kind: str, expected: object, actual: object) -> None:
        expected_id = f"expected:{obligation_id}"
        actual_id = f"actual:{obligation_id}"
        mismatch = [] if _canonical(expected) == _canonical(actual) else [
            f"{obligation_id} differs from independent authority"
        ]
        ledger.append(
            _authority_ledger_row(
                obligation_id=obligation_id,
                kind=kind,
                required=[expected_id],
                produced=[expected_id] if not mismatch else [actual_id],
                mismatch_details=mismatch,
            )
        )

    expected_binding = {
        "authority_id": authority["authority_id"],
        "authority_fingerprint": authority_fingerprint,
        "producer_descriptor_fingerprint": descriptor_fingerprint,
    }
    compare_exact("scope-authority-binding", "authority_binding", expected_binding, binding)

    candidate_target_projection = {
        key: target[key]
        for key in (
            "target_id",
            "title",
            "kind",
            "version",
            "official_url",
            "material_inventory_policy",
            "source_authorities",
            "artifacts",
        )
    }
    compare_exact(
        "target-and-material-inventory",
        "target_material_inventory",
        authority_target,
        candidate_target_projection,
    )
    model_scope = target["model_scope"]
    assert isinstance(model_scope, Mapping)
    scope_projection = {
        key: authority_scope[key]
        for key in (
            "scope_id",
            "purpose",
            "scope_kind",
            "included_question_ids",
            "included_structure_node_ids",
            "excluded_semantic_region_ids",
            "expansion_frontier_ids",
            "completion_status",
            "whole_target_semantics_claimed",
        )
    }
    compare_exact("declared-scope", "scope", scope_projection, model_scope)

    expected_structures = {
        str(row["node_id"]): row
        for row in _rows(
            authority_scope["structure_obligations"], "scope authority structures"
        )
    }
    actual_structures = {
        str(row["node_id"]): {
            "node_id": row["node_id"],
            "parent_id": row["parent_id"],
            "kind": row["kind"],
            "semantic_role": row["semantic_role"],
            "locator": row["locator"],
            "required_member_ids": row["member_ids"],
            "required_artifact_ids": row["artifact_ids"],
            "required_bound_object_ids": row["bound_object_ids"],
        }
        for row in structures
        if isinstance(row, Mapping)
    }
    structure_ids = set(expected_structures)
    actual_structure_ids = set(actual_structures)
    structure_mismatches = [
        item
        for item in sorted(structure_ids & actual_structure_ids)
        if _canonical(expected_structures[item]) != _canonical(actual_structures[item])
    ]
    ledger.append(
        _authority_ledger_row(
            obligation_id="structure-obligation-denominator",
            kind="structure",
            required=structure_ids,
            produced=actual_structure_ids,
            mismatch_details=[f"structure obligation differs: {item}" for item in structure_mismatches],
        )
    )

    source_model = member_models["sourceguard"]
    assert isinstance(source_model, Mapping)
    source_input = source_model["input"]
    assert isinstance(source_input, Mapping)
    actual_anchors = {
        str(row["anchor_id"]): {
            "anchor_id": row["anchor_id"],
            "claim_id": row["claim_id"],
            "source_id": row["source_id"],
            "role": row["role"],
            "artifact_id": row["artifact_id"],
            "structure_node_id": row["structure_node_id"],
            "expected_structure_kind": row["expected_structure_kind"],
            "selector": row["selector"],
            "expected_value": row["expected_value"],
        }
        for row in _rows(source_input["extraction_requests"], "SourceGuard extraction requests")
    }
    expected_anchors = {
        str(row["anchor_id"]): row
        for row in _rows(authority_scope["anchor_obligations"], "scope authority anchors")
    }
    anchor_ids = set(expected_anchors)
    actual_anchor_ids = set(actual_anchors)
    anchor_mismatches = [
        item
        for item in sorted(anchor_ids & actual_anchor_ids)
        if _canonical(expected_anchors[item]) != _canonical(actual_anchors[item])
    ]
    occurrence_ids = [
        str(row["selector"]["occurrence_id"])
        for row in actual_anchors.values()
        if isinstance(row.get("selector"), Mapping)
    ]
    duplicate_occurrences = sorted(
        {item for item in occurrence_ids if occurrence_ids.count(item) > 1}
    )
    ledger.append(
        _authority_ledger_row(
            obligation_id="semantic-anchor-denominator",
            kind="anchor",
            required=anchor_ids,
            produced=actual_anchor_ids,
            mismatch_details=[
                *(f"anchor obligation differs: {item}" for item in anchor_mismatches),
                *(f"duplicate occurrence binding: {item}" for item in duplicate_occurrences),
            ],
        )
    )

    actual_handoffs: dict[str, dict[str, object]] = {}
    produced_by: dict[str, str] = {}
    consumed_by: dict[str, set[str]] = {}
    expected_members = {
        str(row["member_id"]): row
        for row in _rows(authority_scope["member_obligations"], "scope authority members")
    }
    for member_id in MEMBER_IDS:
        model = member_models[member_id]
        assert isinstance(model, Mapping)
        output = model["output"]
        assert isinstance(output, Mapping)
        actual_kinds = _member_output_kinds(member_id, output)
        actual_outputs = set(str(item) for item in model["owned_object_ids"])  # type: ignore[union-attr]
        actual_inputs = {
            str(row["object_id"])
            for row in _rows(model["bindings"], f"{member_id} bindings")
            if row["direction"] == "input_to_model"
        }
        for object_id in actual_outputs:
            produced_by[object_id] = member_id
        for object_id in actual_inputs:
            consumed_by.setdefault(object_id, set()).add(member_id)
        expected_member = expected_members.get(member_id)
        if expected_member is None:
            expected_member = {
                "member_id": member_id,
                "required_input_object_ids": [],
                "required_output_object_ids": [],
                "required_output_kinds": [],
            }
        ledger.append(
            _authority_ledger_row(
                obligation_id=f"member-inputs:{member_id}",
                kind="member_input",
                required=expected_member["required_input_object_ids"],  # type: ignore[arg-type]
                consumed=actual_inputs,
            )
        )
        ledger.append(
            _authority_ledger_row(
                obligation_id=f"member-outputs:{member_id}",
                kind="member_output",
                required=expected_member["required_output_object_ids"],  # type: ignore[arg-type]
                produced=actual_outputs,
            )
        )
        expected_kinds = {
            str(row["kind"]): set(str(item) for item in row["object_ids"])  # type: ignore[index]
            for row in _rows(
                expected_member["required_output_kinds"],
                f"scope authority {member_id} output kinds",
            )
        }
        kind_names = set(expected_kinds) | set(actual_kinds)
        for kind_name in sorted(kind_names):
            ledger.append(
                _authority_ledger_row(
                    obligation_id=f"member-output-kind:{member_id}:{kind_name}",
                    kind="member_output_kind",
                    required=expected_kinds.get(kind_name, set()),
                    produced=actual_kinds.get(kind_name, set()),
                )
            )

    for object_id, producer in produced_by.items():
        actual_handoffs[object_id] = {
            "object_id": object_id,
            "producer_member_id": producer,
            "consumer_member_ids": sorted(consumed_by.get(object_id, set())),
        }
    expected_handoffs = {
        str(row["object_id"]): row
        for row in _rows(authority_scope["cross_member_handoffs"], "scope authority handoffs")
    }
    handoff_ids = set(expected_handoffs)
    actual_handoff_ids = set(actual_handoffs)
    handoff_mismatches = [
        item
        for item in sorted(handoff_ids & actual_handoff_ids)
        if _canonical(expected_handoffs[item]) != _canonical(actual_handoffs[item])
    ]
    ledger.append(
        _authority_ledger_row(
            obligation_id="cross-member-handoff-denominator",
            kind="handoff",
            required=handoff_ids,
            disposed=actual_handoff_ids,
            mismatch_details=[f"handoff obligation differs: {item}" for item in handoff_mismatches],
        )
    )

    logic_model = member_models["logicguard"]
    assert isinstance(logic_model, Mapping) and isinstance(logic_model["output"], Mapping)
    compare_exact(
        "logic-scope-limits",
        "scope_limit",
        authority_scope["scope_limits"],
        logic_model["output"]["scope_limits"],  # type: ignore[index]
    )

    authority_external_inputs = {
        str(authority_target["target_id"]),
        *(str(row["artifact_id"]) for row in _rows(authority_target["artifacts"], "authority artifacts")),
        *expected_structures,
    }
    actual_parent_inputs = {
        str(row["object_id"])
        for row in _rows(parent["input_fields"], "parent input fields")
    }
    ledger.append(
        _authority_ledger_row(
            obligation_id="authority-derived-parent-input-interface",
            kind="parent_input",
            required=authority_external_inputs,
            consumed=actual_parent_inputs,
        )
    )
    authority_outputs = {
        str(item)
        for row in _rows(authority_scope["member_obligations"], "authority member obligations")
        for item in row["required_output_object_ids"]  # type: ignore[index]
    }
    actual_parent_outputs = {
        str(row["object_id"])
        for row in _rows(parent["output_fields"], "parent output fields")
    }
    actual_dispositions = {
        str(row["object_id"])
        for row in _rows(parent["child_output_dispositions"], "parent dispositions")
    }
    ledger.append(
        _authority_ledger_row(
            obligation_id="authority-derived-parent-output-interface",
            kind="parent_output",
            required=authority_outputs,
            produced=actual_parent_outputs,
        )
    )
    ledger.append(
        _authority_ledger_row(
            obligation_id="authority-derived-parent-dispositions",
            kind="parent_disposition",
            required=authority_outputs,
            disposed=actual_dispositions,
        )
    )

    for row in ledger:
        if row["status"] != "satisfied":
            missing = list(row["missing_object_ids"])
            unexpected = list(row["unexpected_object_ids"])
            code = (
                "authority-required-but-missing"
                if missing or row["mismatch_details"]
                else "authority-unexpected-candidate-object"
            )
            gaps.append(
                {
                    "code": code,
                    "detail": (
                        f"{row['obligation_id']} is not covered by the candidate; "
                        f"missing={','.join(missing) or '-'}; "
                        f"unexpected={','.join(unexpected) or '-'}; "
                        f"mismatch={';'.join(row['mismatch_details']) or '-'}"
                    ),
                    "object_ids": sorted(set(missing) | set(unexpected)),
                }
            )
    return {
        "authority_status": "valid",
        "authority_licensed": licensed,
        "coverage_complete": not gaps,
        "authority_fingerprint": authority_fingerprint,
        "producer_descriptor_fingerprint": descriptor_fingerprint,
        "authority_id": str(authority["authority_id"]),
        "obligation_ledger": ledger,
        "gaps": gaps,
        "authority": authority,
    }


def _verify_target_materials(
    target: Mapping[str, object], resolved_root: Path
) -> list[dict[str, object]]:
    """Reopen and verify the complete declared material denominator."""

    if not resolved_root.is_dir() or resolved_root.is_symlink():
        raise ExternalDomainDnaError("material root must be one real directory")
    declared_rows = _rows(target["artifacts"], "target artifacts")
    declared_by_path = {
        str(row["relative_path"]).replace("\\", "/"): row
        for row in declared_rows
    }
    observed_by_path: dict[str, Path] = {}
    for candidate in sorted(resolved_root.rglob("*")):
        if candidate.is_symlink():
            raise ExternalDomainDnaError(
                "material inventory rejects symlinks: "
                + candidate.relative_to(resolved_root).as_posix()
            )
        if candidate.is_file():
            observed_by_path[candidate.relative_to(resolved_root).as_posix()] = candidate
    if set(observed_by_path) != set(declared_by_path):
        missing = sorted(set(observed_by_path) - set(declared_by_path))
        foreign = sorted(set(declared_by_path) - set(observed_by_path))
        detail = ";".join(
            part for part in (
                "undeclared=" + ",".join(missing) if missing else "",
                "unavailable=" + ",".join(foreign) if foreign else "",
            ) if part
        )
        raise ExternalDomainDnaError(
            "material inventory denominator differs from the closed directory tree: " + detail
        )
    material_results: list[dict[str, object]] = []
    for relative_path, row in sorted(declared_by_path.items()):
        candidate = observed_by_path[relative_path].resolve()
        if candidate != resolved_root and resolved_root not in candidate.parents:
            raise ExternalDomainDnaError("artifact relative path escapes material root")
        if not candidate.is_file():
            raise ExternalDomainDnaError(
                f"artifact material is unavailable: {row['relative_path']}"
            )
        body = candidate.read_bytes()
        actual = hashlib.sha256(body).hexdigest()
        if actual != row["sha256"] or len(body) != row["byte_length"]:
            raise ExternalDomainDnaError(
                f"artifact material changed: {row['artifact_id']}"
            )
        material_results.append(
            {
                "artifact_id": str(row["artifact_id"]),
                "status": "verified_at_export",
                "detail": "local bytes matched declared length and sha256",
            }
        )
    return material_results


def export_external_domain_dna(
    spec: Mapping[str, object],
    *,
    native_composition_bundle: bytes,
    scope_authority_record: bytes | Mapping[str, object] | None = None,
    material_root: Path | None = None,
) -> bytes:
    """Export one target model only after all four native blueprints replay."""

    canonical_spec = _canonical(spec)
    if not isinstance(canonical_spec, Mapping):
        raise ExternalDomainDnaError("external domain DNA spec must be an object")
    validated = _validate_spec(canonical_spec)
    target = validated["target"]
    assert isinstance(target, Mapping)
    resolved_root = material_root.resolve() if material_root is not None else None
    material_results = (
        _verify_target_materials(target, resolved_root)
        if resolved_root is not None
        else [
            {
                "artifact_id": str(row["artifact_id"]),
                "status": "not_run",
                "detail": "export did not receive a material root",
            }
            for row in _rows(target["artifacts"], "target artifacts")
        ]
    )
    member_models = validated["member_models"]
    if not isinstance(member_models, Mapping):
        raise ExternalDomainDnaError("external domain member models are invalid")
    native_contexts, native_qualification = _portable_native_context(
        native_composition_bundle
    )
    for member_id in MEMBER_IDS:
        model = member_models[member_id]
        if not isinstance(model, Mapping) or _canonical(model["native_binding"]) != _canonical(
            native_contexts[member_id]["binding"]
        ):
            raise ExternalDomainDnaError(
                f"{member_id} external model is not bound to the replayed native envelope"
            )
    native_member_evidence = _replay_member_set(
        member_models,
        target=target,
        structure_nodes=validated["structure_nodes"],  # type: ignore[arg-type]
        material_root=resolved_root,
        native_contexts=native_contexts,
    )
    native_composition = {
        "schema_version": EXTERNAL_DOMAIN_NATIVE_COMPOSITION_SCHEMA,
        "bundle_fingerprint": str(native_qualification["bundle_fingerprint"]),
        "member_binding_fingerprint": _digest(
            {
                member_id: native_contexts[member_id]["binding"]
                for member_id in MEMBER_IDS
            }
        ),
        "bundle_b64": base64.b64encode(native_composition_bundle).decode("ascii"),
    }
    authority_record = _decode_scope_authority_record(scope_authority_record)
    authority_evaluation = _evaluate_scope_authority(validated, authority_record)
    core = {
        "schema_version": EXTERNAL_DOMAIN_DNA_SCHEMA,
        "target": validated["target"],
        "structure_nodes": validated["structure_nodes"],
        "member_models": validated["member_models"],
        "parent_function_block": validated["parent_function_block"],
        "dependency_edges": validated["dependency_edges"],
        "scope_authority_binding": validated["scope_authority_binding"],
        "material_verification": material_results,
        "native_composition": native_composition,
        "native_member_evidence": native_member_evidence,
        "target_scope_authority_record": authority_record,
        "scope_obligation_evaluation": _portable_scope_authority_evaluation(
            authority_evaluation
        ),
        "claim_boundary": validated["claim_boundary"],
    }
    fingerprint = _digest(core)
    artifact = {
        "schema_version": EXTERNAL_DOMAIN_DNA_SCHEMA,
        "dna_id": "external-domain-dna:" + fingerprint.removeprefix("sha256:"),
        "dna_fingerprint": fingerprint,
        **core,
    }
    return json.dumps(
        artifact, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _parse_bundle(bundle: bytes) -> tuple[Mapping[str, object], Mapping[str, object]]:
    try:
        raw = json.loads(bundle.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ExternalDomainDnaError(f"external domain DNA is not valid JSON: {exc}") from exc
    artifact = _mapping(
        raw,
        {
            "schema_version",
            "dna_id",
            "dna_fingerprint",
            "target",
            "structure_nodes",
            "member_models",
            "parent_function_block",
            "dependency_edges",
            "scope_authority_binding",
            "material_verification",
            "native_composition",
            "native_member_evidence",
            "target_scope_authority_record",
            "scope_obligation_evaluation",
            "claim_boundary",
        },
        "external domain DNA",
    )
    if artifact["schema_version"] != EXTERNAL_DOMAIN_DNA_SCHEMA:
        raise ExternalDomainDnaError("external domain DNA schema is not current")
    core = {
        key: artifact[key]
        for key in artifact
        if key not in {"dna_id", "dna_fingerprint"}
    }
    expected = _digest(core)
    if artifact["dna_fingerprint"] != expected or artifact["dna_id"] != (
        "external-domain-dna:" + expected.removeprefix("sha256:")
    ):
        raise ExternalDomainDnaError("external domain DNA identity is stale or forged")
    spec = {
        "schema_version": EXTERNAL_DOMAIN_DNA_SPEC_SCHEMA,
        "target": artifact["target"],
        "structure_nodes": artifact["structure_nodes"],
        "member_models": artifact["member_models"],
        "parent_function_block": artifact["parent_function_block"],
        "dependency_edges": artifact["dependency_edges"],
        "scope_authority_binding": artifact["scope_authority_binding"],
        "claim_boundary": artifact["claim_boundary"],
    }
    validated = _validate_spec(spec)
    expected_authority_evaluation = _evaluate_scope_authority(
        validated, artifact["target_scope_authority_record"]
    )
    if _canonical(artifact["scope_obligation_evaluation"]) != _canonical(
        _portable_scope_authority_evaluation(expected_authority_evaluation)
    ):
        raise ExternalDomainDnaError(
            "scope authority obligation evaluation is stale or forged"
        )
    native_composition = _mapping(
        artifact["native_composition"],
        {
            "schema_version",
            "bundle_fingerprint",
            "member_binding_fingerprint",
            "bundle_b64",
        },
        "external domain native composition",
    )
    if native_composition["schema_version"] != EXTERNAL_DOMAIN_NATIVE_COMPOSITION_SCHEMA:
        raise ExternalDomainDnaError("external domain native composition schema is stale")
    for field in ("bundle_fingerprint", "member_binding_fingerprint"):
        identity = _text(native_composition[field], f"native composition {field}")
        if not identity.startswith("sha256:") or not _SHA256.fullmatch(identity[7:]):
            raise ExternalDomainDnaError(f"native composition {field} is invalid")
    try:
        native_bundle = base64.b64decode(
            str(native_composition["bundle_b64"]).encode("ascii"), validate=True
        )
    except (UnicodeError, ValueError) as exc:
        raise ExternalDomainDnaError("native composition bundle is not canonical base64") from exc
    native_contexts, native_qualification = _portable_native_context(native_bundle)
    if native_qualification.get("bundle_fingerprint") != native_composition["bundle_fingerprint"]:
        raise ExternalDomainDnaError("native composition bundle fingerprint is rebound")
    expected_bindings = {
        member_id: native_contexts[member_id]["binding"] for member_id in MEMBER_IDS
    }
    if _digest(expected_bindings) != native_composition["member_binding_fingerprint"]:
        raise ExternalDomainDnaError("native composition member bindings are rebound")
    member_models = validated["member_models"]
    assert isinstance(member_models, Mapping)
    for member_id in MEMBER_IDS:
        model = member_models[member_id]
        if not isinstance(model, Mapping) or _canonical(model["native_binding"]) != _canonical(
            expected_bindings[member_id]
        ):
            raise ExternalDomainDnaError(
                f"{member_id} external model is not bound to the embedded native envelope"
            )
    verification = _rows(artifact["material_verification"], "material verification")
    evidence = _mapping(
        artifact["native_member_evidence"],
        set(MEMBER_IDS),
        "native member evidence",
    )
    for member_id in MEMBER_IDS:
        member_evidence = _mapping(
            evidence[member_id],
            {
                "schema_version",
                "member_id",
                "checker_entrypoint",
                "checker_version",
                "blueprint_checker_entrypoint",
                "owner_attestation_entrypoint",
                "behavior_id",
                "model_id",
                "model_fingerprint",
                "transition_fingerprint",
                "native_result_fingerprint",
                "test_binding_fingerprint",
                "oracle_binding_fingerprint",
                "evidence_binding_fingerprint",
                "created_object_ids",
                "consumed_upstream_object_ids",
                "capability_fixture_replay_fingerprint",
                "target_subject_fingerprint",
                "target_native_good_case_fingerprint",
                "target_native_bad_case_fingerprint",
                "target_native_oracle_fingerprint",
                "target_native_replay_status",
                "status",
                "claim_boundary",
                "evidence_fingerprint",
            },
            f"{member_id} native member evidence",
        )
        if (
            member_evidence["schema_version"] != EXTERNAL_DOMAIN_MEMBER_EVIDENCE_SCHEMA
            or member_evidence["member_id"] != member_id
            or member_evidence["checker_entrypoint"]
            != MEMBER_NATIVE_ROUTES[member_id]["external_transition"]
            or member_evidence["blueprint_checker_entrypoint"]
            != MEMBER_NATIVE_ROUTES[member_id]["blueprint_checker"]
            or member_evidence["owner_attestation_entrypoint"]
            != MEMBER_NATIVE_ROUTES[member_id]["owner_attestation"]
            or member_evidence["target_native_replay_status"]
            != "passed_good_and_rejected_bad"
            or member_evidence["status"] != "passed"
        ):
            raise ExternalDomainDnaError(
                f"{member_id} native member evidence is stale or foreign"
            )
        for field in (
            "model_fingerprint",
            "transition_fingerprint",
            "native_result_fingerprint",
            "test_binding_fingerprint",
            "oracle_binding_fingerprint",
            "evidence_binding_fingerprint",
            "capability_fixture_replay_fingerprint",
            "target_subject_fingerprint",
            "target_native_good_case_fingerprint",
            "target_native_bad_case_fingerprint",
            "target_native_oracle_fingerprint",
            "evidence_fingerprint",
        ):
            identity = _text(
                member_evidence[field], f"{member_id} native evidence {field}"
            )
            if not identity.startswith("sha256:") or not _SHA256.fullmatch(identity[7:]):
                raise ExternalDomainDnaError(
                    f"{member_id} native evidence {field} is not a sha256 identity"
                )
        _string_ids(
            member_evidence["created_object_ids"],
            f"{member_id} native evidence created object ids",
        )
        _string_ids(
            member_evidence["consumed_upstream_object_ids"],
            f"{member_id} native evidence consumed upstream object ids",
        )
        evidence_core = {
            key: value
            for key, value in member_evidence.items()
            if key != "evidence_fingerprint"
        }
        if member_evidence["evidence_fingerprint"] != _digest(evidence_core):
            raise ExternalDomainDnaError(
                f"{member_id} native member evidence fingerprint is stale or forged"
            )
    target = validated["target"]
    assert isinstance(target, Mapping)
    artifact_ids = {
        str(item["artifact_id"])
        for item in _rows(target["artifacts"], "target artifacts")
    }
    result_ids: set[str] = set()
    for row in verification:
        item = _mapping(row, {"artifact_id", "status", "detail"}, "material verification")
        result_ids.add(_text(item["artifact_id"], "verified artifact id"))
        if item["status"] not in {"verified_at_export", "not_run"}:
            raise ExternalDomainDnaError("material verification status is invalid")
        _text(item["detail"], "material verification detail")
    if result_ids != artifact_ids or len(result_ids) != len(verification):
        raise ExternalDomainDnaError("material verification denominator is incomplete")
    return artifact, validated


def qualify_external_domain_dna(
    bundle: bytes,
    *,
    trusted_artifact_sha256: Iterable[str] = (),
    trusted_producer_descriptor_fingerprints: Sequence[str] = (),
    trusted_scope_authority_fingerprints: Iterable[str] = (),
    trusted_scope_authority_producer_descriptor_fingerprints: Iterable[str] = (),
    material_root: Path | None = None,
) -> dict[str, object]:
    """Qualify candidate DNA against native replay and independent scope authority."""

    try:
        artifact, spec = _parse_bundle(bundle)
    except ExternalDomainDnaError as exc:
        return {
            "status": "dna_blocked",
            "dna_fingerprint": "",
            "target_id": "",
            "external_material_authenticity": "failed",
            "capability_fixture_replay_status": "not_admitted",
            "target_native_replay_status": "not_run",
            "validation_states": {
                "material_inventory_verified": False,
                "member_native_replay_verified": False,
                "candidate_internal_consistency": False,
                "scope_authority_licensed": False,
                "scope_obligation_coverage": False,
                "dna_qualified": False,
            },
            "first_gap": {"code": "external-domain-dna-invalid", "detail": str(exc)},
            "claim_boundary": "No external-object claim is licensed.",
        }
    target = spec["target"]
    member_models = spec["member_models"]
    assert isinstance(target, Mapping) and isinstance(member_models, Mapping)
    native_evidence = artifact["native_member_evidence"]
    assert isinstance(native_evidence, Mapping)
    resolved_root = material_root.resolve() if material_root is not None else None
    authority_evaluation = _evaluate_scope_authority(
        spec,
        artifact["target_scope_authority_record"],
        trusted_authority_fingerprints=trusted_scope_authority_fingerprints,
        trusted_producer_descriptor_fingerprints=(
            trusted_scope_authority_producer_descriptor_fingerprints
        ),
    )
    authority = authority_evaluation["authority"]
    authority_target = target
    if isinstance(authority, Mapping) and isinstance(authority.get("target"), Mapping):
        authority_target = authority["target"]  # type: ignore[assignment]
    try:
        native_composition = artifact["native_composition"]
        assert isinstance(native_composition, Mapping)
        native_bundle = base64.b64decode(
            str(native_composition["bundle_b64"]).encode("ascii"), validate=True
        )
        native_contexts, native_qualification = _portable_native_context(
            native_bundle,
            trusted_producer_descriptor_fingerprints=(
                trusted_producer_descriptor_fingerprints
            ),
        )
        if resolved_root is not None:
            _verify_target_materials(authority_target, resolved_root)
        replayed_member_set = _replay_member_set(
            member_models,
            target=target,
            structure_nodes=spec["structure_nodes"],  # type: ignore[arg-type]
            material_root=resolved_root,
            native_contexts=native_contexts,
        )
    except (ExternalDomainDnaError, ImportError, OSError, TypeError, ValueError) as exc:
        return {
            "status": "dna_blocked",
            "dna_fingerprint": artifact["dna_fingerprint"],
            "target_id": target["target_id"],
            "external_material_authenticity": "failed",
            "native_member_evidence_status": "failed",
            "capability_fixture_replay_status": "failed_or_untrusted",
            "target_native_replay_status": "failed",
            "validation_states": {
                "material_inventory_verified": False,
                "member_native_replay_verified": False,
                "candidate_internal_consistency": True,
                "scope_authority_licensed": bool(
                    authority_evaluation["authority_licensed"]
                ),
                "scope_obligation_coverage": bool(
                    authority_evaluation["coverage_complete"]
                ),
                "dna_qualified": False,
            },
            "first_gap": {
                "code": "external-domain-native-replay-failed",
                "detail": str(exc),
            },
            "claim_boundary": "No external-object claim is licensed.",
        }
    for member_id in MEMBER_IDS:
        if replayed_member_set[member_id] != native_evidence.get(member_id):
            return {
                "status": "dna_blocked",
                "dna_fingerprint": artifact["dna_fingerprint"],
                "target_id": target["target_id"],
                "external_material_authenticity": "failed",
                "native_member_evidence_status": "failed",
                "capability_fixture_replay_status": "passed",
                "target_native_replay_status": "evidence_mismatch",
                "validation_states": {
                    "material_inventory_verified": False,
                    "member_native_replay_verified": False,
                    "candidate_internal_consistency": True,
                    "scope_authority_licensed": bool(
                        authority_evaluation["authority_licensed"]
                    ),
                    "scope_obligation_coverage": bool(
                        authority_evaluation["coverage_complete"]
                    ),
                    "dna_qualified": False,
                },
                "first_gap": {
                    "code": "external-domain-native-evidence-mismatch",
                    "detail": member_id,
                },
                "claim_boundary": "No external-object claim is licensed.",
            }
    artifact_rows = _rows(authority_target["artifacts"], "target artifacts")
    declared_hashes = {str(row["sha256"]) for row in artifact_rows}
    trusted = {str(item).removeprefix("sha256:") for item in trusted_artifact_sha256}
    material_identity_trusted = bool(declared_hashes) and declared_hashes.issubset(trusted)
    anchor_extraction_replayed = resolved_root is not None
    producer_authenticity = str(native_qualification["producer_authenticity"])
    material_inventory_verified = (
        material_identity_trusted
        and anchor_extraction_replayed
        and authority_evaluation["authority_status"] == "valid"
    )
    external_trust = (
        "licensed"
        if material_inventory_verified
        and producer_authenticity == "licensed"
        else (
            "material_identity_trusted_but_anchor_extraction_unlicensed"
            if material_identity_trusted and not anchor_extraction_replayed
            else (
                "member_producer_authenticity_not_licensed"
                if material_identity_trusted and anchor_extraction_replayed
                else "not_licensed"
            )
        )
    )
    member_native_replay_verified = True
    scope_authority_licensed = bool(authority_evaluation["authority_licensed"])
    scope_obligation_coverage = bool(authority_evaluation["coverage_complete"])
    dna_qualified = bool(
        material_inventory_verified
        and member_native_replay_verified
        and producer_authenticity == "licensed"
        and scope_authority_licensed
        and scope_obligation_coverage
    )
    status = (
        "dna_qualified"
        if dna_qualified
        else "candidate_model"
        if not scope_obligation_coverage
        else "dna_self_consistent"
    )
    first_gap: dict[str, object] | None = None
    authority_gaps = authority_evaluation["gaps"]
    if isinstance(authority_gaps, list) and authority_gaps:
        first = authority_gaps[0]
        if isinstance(first, Mapping):
            first_gap = {"code": str(first["code"]), "detail": str(first["detail"])}
    elif not scope_authority_licensed:
        first_gap = {
            "code": "scope-authority-trust-not-licensed",
            "detail": (
                "the signed scope authority is portable but the caller did not trust "
                "its exact authority or producer descriptor fingerprint"
            ),
        }
    elif external_trust != "licensed":
        first_gap = (
            {
                "code": "external-anchor-extraction-not-replayed",
                "detail": (
                    "trusted whole-artifact hashes do not prove the bundle's local "
                    "anchor lines or extracted values; current material replay was not run"
                ),
            }
            if material_identity_trusted and not anchor_extraction_replayed
            else (
                {
                    "code": "member-producer-trust-not-licensed",
                    "detail": (
                        "member-native blueprint replay is self-consistent, but its "
                        "producer descriptors were not supplied as external trust roots"
                    ),
                }
                if material_identity_trusted and anchor_extraction_replayed
                else {
                    "code": "external-artifact-trust-not-licensed",
                    "detail": "bundle consistency does not independently authenticate source bytes",
                }
            )
        )
    verification = artifact["material_verification"]
    assert isinstance(verification, list)
    model_scope = target["model_scope"]
    assert isinstance(model_scope, Mapping)
    return {
        "status": status,
        "dna_id": artifact["dna_id"],
        "dna_fingerprint": artifact["dna_fingerprint"],
        "target_id": target["target_id"],
        "target_title": target["title"],
        "target_version": target["version"],
        "external_material_authenticity": external_trust,
        "member_producer_authenticity": producer_authenticity,
        "scope_authority": {
            "status": authority_evaluation["authority_status"],
            "authority_id": authority_evaluation["authority_id"],
            "authority_fingerprint": authority_evaluation["authority_fingerprint"],
            "producer_descriptor_fingerprint": authority_evaluation[
                "producer_descriptor_fingerprint"
            ],
            "licensed": scope_authority_licensed,
        },
        "validation_states": {
            "material_inventory_verified": material_inventory_verified,
            "member_native_replay_verified": member_native_replay_verified,
            "candidate_internal_consistency": True,
            "scope_authority_licensed": scope_authority_licensed,
            "scope_obligation_coverage": scope_obligation_coverage,
            "dna_qualified": dna_qualified,
        },
        "scope_obligation_summary": {
            "obligation_count": len(authority_evaluation["obligation_ledger"]),  # type: ignore[arg-type]
            "satisfied_count": sum(
                1
                for row in authority_evaluation["obligation_ledger"]  # type: ignore[union-attr]
                if isinstance(row, Mapping) and row.get("status") == "satisfied"
            ),
            "unsatisfied_count": sum(
                1
                for row in authority_evaluation["obligation_ledger"]  # type: ignore[union-attr]
                if isinstance(row, Mapping) and row.get("status") != "satisfied"
            ),
            "gap_count": len(authority_evaluation["gaps"]),  # type: ignore[arg-type]
        },
        "native_composition_status": native_qualification["status"],
        "capability_fixture_replay_status": "passed",
        "target_native_replay_status": "passed_good_and_rejected_bad",
        "model_scope": {
            "scope_id": model_scope["scope_id"],
            "purpose": model_scope["purpose"],
            "scope_kind": model_scope["scope_kind"],
            "completion_status": model_scope["completion_status"],
            "whole_target_semantics_claimed": model_scope[
                "whole_target_semantics_claimed"
            ],
            "expansion_frontier_ids": model_scope["expansion_frontier_ids"],
        },
        "whole_target_semantics_status": (
            "claimed_and_scope_checked"
            if model_scope["whole_target_semantics_claimed"] is True
            else "not_claimed"
        ),
        "recursive_deepening_available": bool(model_scope["expansion_frontier_ids"]),
        "native_member_evidence_status": (
            "native_semantics_replayed"
            if anchor_extraction_replayed
            else "portable_semantics_replayed_anchor_extraction_unlicensed"
        ),
        "anchor_material_replay_status": (
            "replayed_from_current_material"
            if anchor_extraction_replayed
            else "not_run"
        ),
        "export_material_status": (
            "verified_at_export"
            if verification and all(item.get("status") == "verified_at_export" for item in verification)
            else "not_run"
        ),
        "member_summaries": [
            {
                "member_id": member_id,
                "model_id": member_models[member_id]["model_id"],  # type: ignore[index]
                "behavior_id": member_models[member_id]["behavior_id"],  # type: ignore[index]
                "owned_object_count": len(member_models[member_id]["owned_object_ids"]),  # type: ignore[index,arg-type]
                "gap_count": len(member_models[member_id]["output"]["gaps"]),  # type: ignore[index,arg-type]
                "native_evidence_fingerprint": native_evidence[member_id]["evidence_fingerprint"],  # type: ignore[index]
            }
            for member_id in MEMBER_IDS
        ],
        "structure_node_count": len(spec["structure_nodes"]),  # type: ignore[arg-type]
        "dependency_edge_count": len(spec["dependency_edges"]),  # type: ignore[arg-type]
        "first_gap": first_gap,
        "claim_boundary": spec["claim_boundary"],
        "available_queries": {
            "member": "member_id",
            "behavior": "behavior_id",
            "object": "object_id",
            "impact": "changed_object_id",
            "reverse": "output_object_id",
            "scope": "scope_id",
        },
    }


def _graph(
    spec: Mapping[str, object], artifact: Mapping[str, object] | None = None
) -> tuple[set[str], list[dict[str, str]]]:
    target = spec["target"]
    member_models = spec["member_models"]
    parent = spec["parent_function_block"]
    assert isinstance(target, Mapping) and isinstance(member_models, Mapping) and isinstance(parent, Mapping)
    target_id = str(target["target_id"])
    model_scope = target["model_scope"]
    assert isinstance(model_scope, Mapping)
    scope_id = str(model_scope["scope_id"])
    objects = {target_id, str(parent["block_id"]), scope_id}
    excluded_semantic_ids = [
        str(item) for item in model_scope["excluded_semantic_region_ids"]  # type: ignore[union-attr]
    ]
    frontier_ids = [
        str(item) for item in model_scope["expansion_frontier_ids"]  # type: ignore[union-attr]
    ]
    objects.update(excluded_semantic_ids)
    objects.update(frontier_ids)
    artifacts = _rows(target["artifacts"], "target artifacts")
    objects.update(str(row["artifact_id"]) for row in artifacts)
    edges: list[dict[str, str]] = []
    edges.append(
        {
            "edge_id": "parent-admission", "from_id": target_id,
            "to_id": str(parent["block_id"]), "relation": "admits_parent_function_block",
        }
    )
    edges.append(
        {
            "edge_id": "target-model-scope", "from_id": target_id,
            "to_id": scope_id, "relation": "declares_bounded_model_scope",
        }
    )
    for input_field in _rows(parent["input_fields"], "parent input fields"):
        source_object_id = str(input_field["object_id"])
        objects.add(source_object_id)
        edges.append(
            {
                "edge_id": f"parent-input:{source_object_id}",
                "from_id": source_object_id,
                "to_id": str(parent["block_id"]),
                "relation": "parent_consumes_external_input",
            }
        )
    for object_id in excluded_semantic_ids:
        edges.append(
            {
                "edge_id": f"scope-exclusion:{object_id}", "from_id": scope_id,
                "to_id": object_id, "relation": "preserves_semantic_exclusion",
            }
        )
    for object_id in frontier_ids:
        edges.append(
            {
                "edge_id": f"scope-frontier:{object_id}", "from_id": scope_id,
                "to_id": object_id, "relation": "opens_recursive_deepening_frontier",
            }
        )
    structures = _rows(spec["structure_nodes"], "structure nodes")
    roots = [str(row["node_id"]) for row in structures if row["parent_id"] is None]
    edges.append(
        {
            "edge_id": "target-structure-root", "from_id": target_id,
            "to_id": roots[0], "relation": "owns_structure_root",
        }
    )
    for artifact in artifacts:
        artifact_id = str(artifact["artifact_id"])
        edges.append(
            {
                "edge_id": f"target-artifact:{artifact_id}", "from_id": target_id,
                "to_id": artifact_id, "relation": "owns_material",
            }
        )
    for row in structures:
        node_id = str(row["node_id"])
        objects.add(node_id)
        if row["parent_id"] is not None:
            edges.append(
                {
                    "edge_id": f"hierarchy:{node_id}",
                    "from_id": str(row["parent_id"]),
                    "to_id": node_id,
                    "relation": "parent_contains_child",
                }
            )
        for artifact_id in row["artifact_ids"]:  # type: ignore[index]
            edges.append(
                {
                    "edge_id": f"artifact-structure:{artifact_id}:{node_id}",
                    "from_id": str(artifact_id), "to_id": node_id,
                    "relation": "material_realizes_structure",
                }
            )
        for member_id in row["member_ids"]:  # type: ignore[index]
            model_id = str(member_models[str(member_id)]["model_id"])  # type: ignore[index]
            edges.append(
                {
                    "edge_id": f"structure-member:{node_id}:{member_id}",
                    "from_id": node_id, "to_id": model_id,
                    "relation": "structure_requires_member",
                }
            )
        for object_id in row["bound_object_ids"]:  # type: ignore[index]
            edges.append(
                {
                    "edge_id": f"structure-object:{node_id}:{object_id}",
                    "from_id": node_id, "to_id": str(object_id),
                    "relation": "structure_binds_member_object",
                }
            )
    for member_id in MEMBER_IDS:
        model = member_models[member_id]
        assert isinstance(model, Mapping)
        model_id = str(model["model_id"])
        objects.add(model_id)
        edges.append(
            {
                "edge_id": f"parent-child:{member_id}",
                "from_id": str(parent["block_id"]), "to_id": model_id,
                "relation": "parent_executes_child",
            }
        )
        edges.append(
            {
                "edge_id": f"scope-member:{member_id}", "from_id": scope_id,
                "to_id": model_id, "relation": "bounds_member_object_denominator",
            }
        )
        objects.update(str(item) for item in model["owned_object_ids"])  # type: ignore[union-attr]
        native_route = model["native_route"]
        assert isinstance(native_route, Mapping)
        for route_role in ("blueprint_checker", "owner_attestation", "external_transition"):
            entrypoint = str(native_route[route_role])
            objects.add(entrypoint)
            edges.append(
                {
                    "edge_id": f"code-model:{member_id}:{route_role}",
                    "from_id": entrypoint, "to_id": model_id,
                    "relation": f"code_{route_role}",
                }
            )
        oracle = model["oracle_binding"]
        assert isinstance(oracle, Mapping)
        oracle_id = str(oracle["oracle_id"])
        objects.add(oracle_id)
        for test in _rows(model["test_bindings"], f"{member_id} test bindings"):
            test_id = str(test["test_id"])
            objects.add(test_id)
            edges.extend(
                (
                    {
                        "edge_id": f"oracle-test:{member_id}:{test_id}",
                        "from_id": oracle_id, "to_id": test_id,
                        "relation": "oracle_decides_test",
                    },
                    {
                        "edge_id": f"test-model:{member_id}:{test_id}",
                        "from_id": test_id, "to_id": model_id,
                        "relation": "test_validates_model",
                    },
                )
            )
        for evidence in _rows(model["evidence_bindings"], f"{member_id} evidence bindings"):
            evidence_id = str(evidence["evidence_id"])
            objects.add(evidence_id)
            producer_id = str(evidence["producer_entrypoint"])
            subject_id = str(evidence["subject_id"])
            objects.add(producer_id)
            objects.add(subject_id)
            edges.append(
                {
                    "edge_id": f"evidence-model:{member_id}:{evidence_id}",
                    "from_id": evidence_id, "to_id": model_id,
                    "relation": "evidence_supports_model",
                }
            )
            edges.extend(
                (
                    {
                        "edge_id": f"evidence-producer:{member_id}:{evidence_id}",
                        "from_id": producer_id,
                        "to_id": evidence_id,
                        "relation": "evidence_produced_by_current_route",
                    },
                    {
                        "edge_id": f"evidence-subject:{member_id}:{evidence_id}",
                        "from_id": evidence_id,
                        "to_id": subject_id,
                        "relation": "evidence_binds_subject",
                    },
                )
            )
        for row in _rows(model["bindings"], f"{member_id} bindings"):
            if row["direction"] == "input_to_model":
                source, target_id = str(row["object_id"]), model_id
            else:
                source, target_id = model_id, str(row["object_id"])
            edges.append(
                {
                    "edge_id": str(row["binding_id"]),
                    "from_id": source,
                    "to_id": target_id,
                    "relation": str(row["role"]),
                }
            )
    edges.extend(
        {
            "edge_id": str(row["edge_id"]),
            "from_id": str(row["from_id"]),
            "to_id": str(row["to_id"]),
            "relation": str(row["relation"]),
        }
        for row in _rows(spec["dependency_edges"], "dependency edges")
    )
    if artifact is not None:
        evaluation = artifact.get("scope_obligation_evaluation")
        if isinstance(evaluation, Mapping):
            authority_id = str(evaluation.get("authority_id", "")).strip()
            if authority_id:
                objects.add(authority_id)
                edges.append(
                    {
                        "edge_id": "target-scope-authority",
                        "from_id": target_id,
                        "to_id": authority_id,
                        "relation": "bounded_by_independent_scope_authority",
                    }
                )
                gap_index = 0
                gaps = evaluation.get("gaps")
                if isinstance(gaps, list):
                    for gap in gaps:
                        if not isinstance(gap, Mapping):
                            continue
                        object_ids = gap.get("object_ids")
                        if not isinstance(object_ids, list):
                            continue
                        for object_id_raw in object_ids:
                            object_id = str(object_id_raw)
                            objects.add(object_id)
                            gap_index += 1
                            edges.append(
                                {
                                    "edge_id": f"authority-gap:{gap_index}",
                                    "from_id": authority_id,
                                    "to_id": object_id,
                                    "relation": "authority_required_but_missing",
                                }
                            )
    return objects, sorted(edges, key=lambda item: item["edge_id"])


def external_domain_dna_impact(bundle: bytes, changed_ids: Iterable[str]) -> dict[str, object]:
    """Return the exact downstream closure for known changed object ids."""

    artifact, spec = _parse_bundle(bundle)
    objects, edges = _graph(spec, artifact)
    changed = tuple(sorted(set(str(item) for item in changed_ids)))
    unknown = tuple(item for item in changed if item not in objects)
    if unknown:
        return {
            "status": "impact_blocked",
            "dna_fingerprint": artifact["dna_fingerprint"],
            "changed_ids": list(changed),
            "affected_object_ids": [],
            "unaffected_object_ids": [],
            "unknown_object_ids": list(unknown),
            "partial_result_suppressed": True,
            "claim_boundary": spec["claim_boundary"],
        }
    adjacency: dict[str, set[str]] = {item: set() for item in objects}
    validation_sources: dict[str, set[str]] = {item: set() for item in objects}
    for edge in edges:
        adjacency[edge["from_id"]].add(edge["to_id"])
        if edge["relation"] in {
            "code_blueprint_checker", "code_owner_attestation", "code_external_transition",
            "oracle_decides_test", "test_validates_model", "evidence_supports_model",
        }:
            validation_sources[edge["to_id"]].add(edge["from_id"])
    affected = set(changed)
    frontier = list(changed)
    while frontier:
        current = frontier.pop(0)
        for dependent in sorted(adjacency[current] | validation_sources[current]):
            if dependent not in affected:
                affected.add(dependent)
                frontier.append(dependent)
    return {
        "status": "impact_complete",
        "dna_fingerprint": artifact["dna_fingerprint"],
        "changed_ids": list(changed),
        "affected_object_ids": sorted(affected),
        "unaffected_object_ids": sorted(objects - affected),
        "unknown_object_ids": [],
        "partial_result_suppressed": False,
        "authority_required_but_missing": [
            item
            for gap in artifact["scope_obligation_evaluation"].get("gaps", [])  # type: ignore[union-attr]
            if isinstance(gap, Mapping) and gap.get("code") == "authority-required-but-missing"
            for item in gap.get("object_ids", [])
        ],
        "claim_boundary": spec["claim_boundary"],
    }


def external_domain_dna_reverse(bundle: bytes, output_id: str) -> dict[str, object]:
    """Trace one known output backwards to all declared prerequisites."""

    artifact, spec = _parse_bundle(bundle)
    objects, edges = _graph(spec, artifact)
    authority_missing = {
        str(item)
        for gap in artifact["scope_obligation_evaluation"].get("gaps", [])  # type: ignore[union-attr]
        if isinstance(gap, Mapping) and gap.get("code") == "authority-required-but-missing"
        for item in gap.get("object_ids", [])
    }
    if output_id not in objects:
        if output_id in authority_missing:
            authority_id = str(
                artifact["scope_obligation_evaluation"].get("authority_id", "")  # type: ignore[union-attr]
            )
            target = spec["target"]
            assert isinstance(target, Mapping)
            return {
                "status": "reverse_incomplete",
                "dna_fingerprint": artifact["dna_fingerprint"],
                "output_id": output_id,
                "upstream_object_ids": [
                    item
                    for item in (str(target["target_id"]), authority_id, output_id)
                    if item
                ],
                "edges": [],
                "partial_result_suppressed": False,
                "first_gap": {
                    "code": "authority-required-but-missing",
                    "detail": output_id,
                },
                "claim_boundary": spec["claim_boundary"],
            }
        return {
            "status": "reverse_blocked",
            "dna_fingerprint": artifact["dna_fingerprint"],
            "output_id": output_id,
            "upstream_object_ids": [],
            "edges": [],
            "partial_result_suppressed": True,
            "first_gap": {"code": "external-domain-object-unknown", "detail": output_id},
            "claim_boundary": spec["claim_boundary"],
        }
    incoming: dict[str, list[dict[str, str]]] = {item: [] for item in objects}
    for edge in edges:
        incoming[edge["to_id"]].append(edge)
    upstream = {output_id}
    used_edges: dict[str, dict[str, str]] = {}
    frontier = [output_id]
    while frontier:
        current = frontier.pop(0)
        for edge in sorted(incoming[current], key=lambda item: item["edge_id"]):
            used_edges[edge["edge_id"]] = edge
            source = edge["from_id"]
            if source not in upstream:
                upstream.add(source)
                frontier.append(source)
    return {
        "status": "reverse_incomplete" if output_id in authority_missing else "reverse_complete",
        "dna_fingerprint": artifact["dna_fingerprint"],
        "output_id": output_id,
        "upstream_object_ids": sorted(upstream),
        "edges": [used_edges[key] for key in sorted(used_edges)],
        "partial_result_suppressed": False,
        "first_gap": (
            {
                "code": "authority-required-but-missing",
                "detail": output_id,
            }
            if output_id in authority_missing
            else None
        ),
        "claim_boundary": spec["claim_boundary"],
    }


def project_external_domain_dna(
    bundle: bytes,
    *,
    trusted_artifact_sha256: Iterable[str] = (),
    trusted_producer_descriptor_fingerprints: Sequence[str] = (),
    trusted_scope_authority_fingerprints: Iterable[str] = (),
    trusted_scope_authority_producer_descriptor_fingerprints: Iterable[str] = (),
    material_root: Path | None = None,
    query_kind: Literal["member", "behavior", "object", "impact", "reverse", "scope"] | None = None,
    object_id: str = "",
) -> dict[str, object]:
    """Keep default output compact and expose at most one explicit drill-down."""

    summary = qualify_external_domain_dna(
        bundle,
        trusted_artifact_sha256=trusted_artifact_sha256,
        trusted_producer_descriptor_fingerprints=(
            trusted_producer_descriptor_fingerprints
        ),
        trusted_scope_authority_fingerprints=trusted_scope_authority_fingerprints,
        trusted_scope_authority_producer_descriptor_fingerprints=(
            trusted_scope_authority_producer_descriptor_fingerprints
        ),
        material_root=material_root,
    )
    if summary["status"] == "dna_blocked" or query_kind is None:
        return summary
    artifact, spec = _parse_bundle(bundle)
    detail: object | None = None
    if query_kind == "member":
        member_models = spec["member_models"]
        assert isinstance(member_models, Mapping)
        detail = member_models.get(object_id)
    elif query_kind == "behavior":
        member_models = spec["member_models"]
        assert isinstance(member_models, Mapping)
        detail = next(
            (
                model
                for model in member_models.values()
                if isinstance(model, Mapping)
                and model.get("behavior_id") == object_id
            ),
            None,
        )
    elif query_kind == "object":
        objects, edges = _graph(spec, artifact)
        if object_id in objects:
            detail = {
                "object_id": object_id,
                "incoming_edges": [item for item in edges if item["to_id"] == object_id],
                "outgoing_edges": [item for item in edges if item["from_id"] == object_id],
            }
    elif query_kind == "scope":
        target = spec["target"]
        assert isinstance(target, Mapping)
        model_scope = target["model_scope"]
        if isinstance(model_scope, Mapping) and model_scope.get("scope_id") == object_id:
            detail = model_scope
    elif query_kind == "impact":
        detail = external_domain_dna_impact(bundle, [object_id])
    elif query_kind == "reverse":
        detail = external_domain_dna_reverse(bundle, object_id)
    result = dict(summary)
    result.update(
        {
            "query_kind": query_kind,
            "object_id": object_id,
            "query_status": "found" if detail is not None else "not_found",
            "detail": detail,
            "dna_fingerprint": artifact["dna_fingerprint"],
        }
    )
    return result


__all__ = [
    "EXTERNAL_DOMAIN_DNA_SCHEMA",
    "EXTERNAL_DOMAIN_DNA_SPEC_SCHEMA",
    "EXTERNAL_DOMAIN_MEMBER_EVIDENCE_SCHEMA",
    "ExternalDomainDnaError",
    "build_external_domain_parent_function_block",
    "derive_external_domain_native_bindings",
    "export_external_domain_dna",
    "external_domain_dna_impact",
    "external_domain_dna_reverse",
    "project_external_domain_dna",
    "qualify_external_domain_dna",
]
