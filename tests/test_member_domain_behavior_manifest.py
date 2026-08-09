from __future__ import annotations

from copy import deepcopy
import json

from admission_fixtures import composition, native_owner_attestations, task_facts
from researchguard.model_envelope import (
    BehaviorTransitionCase,
    MemberModelEnvelope,
    build_behavior_transition_case,
    replay_behavior_transition_oracle,
)
from researchguard.routing import (
    RouteComposition,
    export_portable_composition_bundle,
    replay_composition_behavior_oracle,
    select_member_request,
)


ARGV = ["plan", "domain-behavior-manifest.json"]
INTENT = "intent:domain-behavior-manifest"

EXPECTED_DOMAIN_BEHAVIORS = {
    "sourceguard": {
        "sourceguard.information-blueprint-qualification",
    },
    "traceguard": {
        "traceguard.investigation-reconstruction",
    },
    "logicguard": {
        "logicguard.argument-artifact-qualification",
    },
    "experimentguard": {
        "experimentguard.finite-discriminating-recommendation",
    },
}


def _ready_composition() -> RouteComposition:
    plan = composition(
        ("sourceguard", ("source.primary.discovery",)),
        ("traceguard", ("trace.primary.reconstruction",)),
        ("logicguard", ("logic.primary.general-argument",)),
        ("experimentguard", ("experiment.primary.discriminating-set",)),
    )
    facts = task_facts(
        argv=ARGV,
        intent=INTENT,
        primary_kind="source.primary_discovery",
        additional_primary_kinds=(
            "trace.temporal_reconstruction",
            "logic.argument_structure",
            "experiment.discriminating_set",
        ),
        context_kinds=(
            "experiment.explicit_hypotheses",
            "experiment.finite_candidates",
            "experiment.predicted_outcomes",
        ),
        composition=plan,
    )
    ready = select_member_request(
        facts,
        ARGV,
        business_intent_id=INTENT,
        native_owner_attestations=native_owner_attestations(plan),
    )
    assert isinstance(ready, RouteComposition)
    assert ready.status == "composition_ready"
    return ready


def _bad_transition(case) -> dict[str, object]:
    candidate = deepcopy(case.transition_payload)
    mutation_path = str(case.oracle["bad_case"]["mutation_path"])
    section, field = mutation_path.split(".", 1)
    assert isinstance(candidate[section], dict)
    candidate[section][field] = {"foreign": True}
    return candidate


def test_each_member_carries_native_domain_behaviors_and_executable_oracles() -> None:
    ready = _ready_composition()
    envelopes = {
        item.member_id: item
        for item in (
            MemberModelEnvelope.from_dict(raw)
            for raw in ready.portable_member_envelopes
        )
    }
    assert set(envelopes) == set(EXPECTED_DOMAIN_BEHAVIORS)
    for member_id, envelope in envelopes.items():
        manifest = envelope.behavior_manifest
        assert set(manifest.domain_behavior_denominator_ids) == EXPECTED_DOMAIN_BEHAVIORS[member_id]
        assert {
            item.behavior_id for item in manifest.domain_behavior_cases
        } == EXPECTED_DOMAIN_BEHAVIORS[member_id]
        assert set(manifest.integrity_case_ids).isdisjoint(
            manifest.domain_behavior_denominator_ids
        )
        assert manifest.integrity_cases
        assert all(
            receipt.behavior_manifest_fingerprint == manifest.expected_fingerprint
            for receipt in envelope.native_receipt_refs
        )
        for case in manifest.domain_behavior_cases:
            good = replay_behavior_transition_oracle(
                envelope, case, case.transition_payload
            )
            assert good["status"] == "passed"
            bad = replay_behavior_transition_oracle(
                envelope, case, _bad_transition(case)
            )
            assert bad == {
                "status": "blocked",
                "behavior_id": case.behavior_id,
                "transition_fingerprint": bad["transition_fingerprint"],
                "failure": case.protected_failure,
            }
            rebound_transition = _bad_transition(case)
            forged = build_behavior_transition_case(
                case_id=case.case_id,
                behavior_id=case.behavior_id,
                input=rebound_transition["input"],
                pre_state=rebound_transition["pre_state"],
                permitted_output=rebound_transition["permitted_output"],
                post_state=rebound_transition["post_state"],
                effect=rebound_transition["effect"],
                protected_failure=case.protected_failure,
                owner=str(case.oracle["owner"]),
                checker_entrypoint=str(case.oracle["entrypoint"]),
                checker_id=str(case.oracle["checker_id"]),
                checker_version=str(case.oracle["checker_version"]),
                result_fingerprint=str(case.oracle["result_fingerprint"]),
                native_receipt_id=str(case.oracle["native_receipt_id"]),
                bad_mutation_path=str(case.oracle["bad_case"]["mutation_path"]),
                bad_mutation_operator=str(case.oracle["bad_case"]["mutation_operator"]),
                failure_class_id=str(case.oracle["bad_case"]["failure_class_id"]),
                good_native_evidence=case.oracle["good_case"]["native_evidence"],
                bad_native_evidence=case.oracle["bad_case"]["native_evidence"],
            )
            # The attacker has rebound the case and good-oracle fingerprints.
            assert BehaviorTransitionCase.from_dict(forged.to_dict()) == forged
            semantic_rejection = replay_behavior_transition_oracle(
                envelope, case, forged.transition_payload
            )
            assert semantic_rejection["status"] == "blocked"
            assert semantic_rejection["failure"] == case.protected_failure


def test_researchguard_umbrella_behaviors_have_good_and_bad_oracles() -> None:
    ready = _ready_composition()
    raw = json.loads(export_portable_composition_bundle(ready))
    cases = raw["behavior_transition_cases"]
    assert {item["behavior_id"] for item in cases} == {
        "researchguard.composition.qualification",
        "researchguard.composition.impact",
        "researchguard.composition.reverse-trace",
        "researchguard.portable-bundle.handoff",
    }
    for case in cases:
        transition = {
            key: deepcopy(case[key])
            for key in (
                "input",
                "pre_state",
                "permitted_output",
                "post_state",
                "effect",
            )
        }
        assert replay_composition_behavior_oracle(case, transition)["status"] == "passed"
        transition["input"] = {"foreign": True}
        rejected = replay_composition_behavior_oracle(case, transition)
        assert rejected["status"] == "blocked"
        assert rejected["failure"] == case["protected_failure"]
