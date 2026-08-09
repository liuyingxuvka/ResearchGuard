from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

import pytest

from admission_fixtures import attach_trace_receipts, self_resign_target_authority
from target_material_fixtures import (
    expected_target_anchor_from_material,
    trace_expected_target_anchor,
)
import researchguard.target_authority as target_authority_transport
import researchguard.trace.blueprint as blueprint_module

from researchguard.trace.blueprint import (
    TraceTargetUniverse,
    check_blueprint,
    export_blueprint,
    impact_blueprint as _impact_blueprint,
    project_hierarchy,
    reverse_trace_output,
    _hierarchy_gaps,
)
from researchguard.trace.blueprint import (
    _build_trace_interface_receipt_material as issue_trace_interface_receipt,
    _bind_trace_target_authority as issue_trace_target_authority,
)
from researchguard.trace.evaluator import evaluate_model
from researchguard.trace.purpose_contract import bind_task_guard_purpose, canonical_candidate_fingerprint
from researchguard.trace.loader import read_model_data
from researchguard.trace.schema import (
    TraceGuardModel,
    TraceInterfaceBinding,
    semantic_object_fingerprint,
    trace_interface_endpoint_fingerprint,
)


def _sha(value: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _payload() -> dict[str, object]:
    return {
        "metadata": {
            "schema_version": "researchguard.trace.model.v2",
            "model_instance_id": "blueprint-test",
            "purpose": "Test one current TraceGuard blueprint.",
            "repository": "https://example.invalid/researchguard",
            "skill": "TraceGuard",
            "math_boundary": "One canonical constrained inference receipt only.",
            "cli": "researchguard trace blueprint check model.yaml universe.json",
            "boundary": "Chronology and structural closure do not prove formal causality.",
        },
        "sources": [
            {"source_id": "s1", "title": "Source 1", "url": "https://example.invalid/s1", "source_type": "report", "lineage_id": "l1", "independence_group": "g1", "source_reliability": 0.9, "source_status": "stable_keep"},
            {"source_id": "s2", "title": "Source 2", "url": "https://example.invalid/s2", "source_type": "report", "lineage_id": "l2", "independence_group": "g2", "source_reliability": 0.8, "source_status": "stable_keep"},
        ],
        "evidence": [
            {"evidence_id": "e1", "source_id": "s1", "raw_text": "first event", "locator": "page:1", "evidence_type": "event", "extraction_confidence": 0.9, "evidence_specificity": 0.9, "usable_as_trace_evidence": True, "limits": ["observational"]},
            {"evidence_id": "e2", "source_id": "s2", "raw_text": "competing event", "locator": "page:2", "evidence_type": "event", "extraction_confidence": 0.8, "evidence_specificity": 0.8, "usable_as_trace_evidence": True, "warnings": ["limited sample"]},
        ],
        "entities": [
            {"mention_id": "entity:actor", "evidence_id": "e1", "raw_name": "Actor", "normalized_name": "actor", "entity_type": "organization"}
        ],
        "locations": [
            {"location_id": "location:site", "raw_text": "Site", "normalized_name": "site", "location_role": "project_site"}
        ],
        "events": [
            {"event_id": "event:1", "evidence_ids": ["e1"], "actor_ids": ["entity:actor"], "action": "started", "location_ids": ["location:site"], "event_type": "start", "stage_hint": "start"},
            {"event_id": "event:2", "evidence_ids": ["e2"], "action": "paused", "event_type": "pause", "stage_hint": "pause"},
        ],
        "traces": [
            {"trace_id": "trace:1", "title": "Primary", "event_ids": ["event:1"], "entity_ids": ["entity:actor"], "location_ids": ["location:site"], "current_stage": "start"},
            {"trace_id": "trace:2", "title": "Alternative", "event_ids": ["event:2"], "current_stage": "pause"},
        ],
        "storyline_hypotheses": [
            {"hypothesis_id": "h1", "claim": "primary storyline", "trace_ids": ["trace:1"], "mechanism_ids": ["mechanism:1"], "confounder_ids": ["confounder:1"], "causal": True, "bounded_claim_ids": ["claim:1"], "handoff_ids": ["handoff:1"]},
            {"hypothesis_id": "h2", "claim": "competing storyline", "role": "alternative", "trace_ids": ["trace:2"], "bounded_non_causal": True, "bounded_claim_ids": ["claim:2"], "handoff_ids": ["handoff:2"]},
        ],
        "hypothesis_evidence_links": [
            {"link_id": "link:1", "hypothesis_id": "h1", "evidence_id": "e1", "polarity": "support"},
            {"link_id": "link:2", "hypothesis_id": "h2", "evidence_id": "e2", "polarity": "support"},
        ],
        "hypothesis_relations": [
            {"relation_id": "relation:alternatives", "left_hypothesis_id": "h1", "right_hypothesis_id": "h2", "relation": "competes_with", "evidence_ids": ["e1", "e2"]}
        ],
        "causal_mechanisms": [
            {"mechanism_id": "mechanism:1", "hypothesis_id": "h1", "description": "declared mechanism", "evidence_ids": ["e1"]}
        ],
        "confounder_reviews": [
            {"confounder_id": "confounder:1", "hypothesis_id": "h1", "description": "possible confounder", "status": "unresolved", "evidence_ids": ["e1"]}
        ],
        "causal_scopes": [
            {"scope_id": "scope:1", "description": "site scope", "location_ids": ["location:site"], "boundary_conditions": ["observational only"]}
        ],
        "causal_candidates": [
            {"causal_id": "causal:1", "hypothesis_id": "h1", "cause_event_ids": ["event:1"], "effect_event_ids": ["event:2"], "mechanism_ids": ["mechanism:1"], "confounder_ids": ["confounder:1"], "alternative_hypothesis_ids": ["h2"], "scope_id": "scope:1"}
        ],
        "evidence_ablations": [
            {"ablation_id": "ablation:e1", "hypothesis_id": "h1", "trace_id": "trace:1", "description": "remove e1", "remove_evidence_ids": ["e1"]}
        ],
        "scenario_perturbations": [
            {"perturbation_id": "perturb:event1", "hypothesis_id": "h1", "trace_id": "trace:1", "description": "remove event", "remove_event_ids": ["event:1"]}
        ],
        "expected_sensitivities": [
            {"sensitivity_id": "sensitivity:1", "perturbation_id": "perturb:event1", "target_kind": "hypothesis", "target_id": "h1", "expected_direction": "decrease"}
        ],
    }


def _current_model(payload: dict[str, object] | None = None) -> TraceGuardModel:
    model = TraceGuardModel.from_dict(payload or _payload())

    def identify(row, **fields):
        current = replace(row, **fields)
        return replace(current, object_fingerprint=semantic_object_fingerprint(current))

    sources = tuple(
        identify(
            row,
            source_revision=f"revision:{row.source_id}",
            content_fingerprint=_sha(row.source_id),
            locator=row.url or "",
            provider_id="provider:test",
            provider_revision="provider-revision:1",
            retrieval_request_fingerprint=_sha("request:" + row.source_id),
        )
        for row in model.sources
    )
    evidence = tuple(
        identify(
            row,
            source_revision=f"revision:{row.source_id}",
            content_fingerprint=_sha(row.normalized_summary or row.raw_text),
            normalizer_id="normalizer:test",
            normalizer_revision="normalizer-revision:1",
            normalizer_fingerprint=_sha("normalizer"),
            extractor_id="extractor:test",
            extractor_revision="extractor-revision:1",
            extractor_fingerprint=_sha("extractor"),
        )
        for row in model.evidence
    )
    events = tuple(
        identify(
            row,
            extractor_id="extractor:event",
            extractor_revision="event-extractor-revision:1",
            extractor_fingerprint=_sha("event-extractor"),
        )
        for row in model.events
    )
    traces = tuple(
        identify(
            row,
            normalizer_id="normalizer:trace",
            normalizer_revision="trace-normalizer-revision:1",
            normalizer_fingerprint=_sha("trace-normalizer"),
        )
        for row in model.traces
    )
    hypotheses = tuple(
        identify(
            row,
            normalizer_id="normalizer:hypothesis",
            normalizer_revision="hypothesis-normalizer-revision:1",
            normalizer_fingerprint=_sha("hypothesis-normalizer"),
        )
        for row in model.storyline_hypotheses
    )
    current = replace(
        model,
        sources=sources,
        evidence=evidence,
        events=events,
        traces=traces,
        storyline_hypotheses=hypotheses,
    )
    pairs = [
        ("source", "s1", "evidence_fact", "e1"),
        ("source", "s2", "evidence_fact", "e2"),
        ("evidence_fact", "e1", "event", "event:1"),
        ("evidence_fact", "e2", "event", "event:2"),
        ("event", "event:1", "trace", "trace:1"),
        ("event", "event:2", "trace", "trace:2"),
        ("trace", "trace:1", "hypothesis", "h1"),
        ("trace", "trace:2", "hypothesis", "h2"),
        ("hypothesis", "h1", "bounded_claim", "claim:1"),
        ("hypothesis", "h1", "handoff", "handoff:1"),
        ("hypothesis", "h2", "bounded_claim", "claim:2"),
        ("hypothesis", "h2", "handoff", "handoff:2"),
    ]
    bindings = []
    for producer_kind, producer_id, consumer_kind, consumer_id in pairs:
        binding = TraceInterfaceBinding(
            binding_id=f"interface:{producer_id}->{consumer_id}",
            producer_kind=producer_kind,
            producer_id=producer_id,
            consumer_kind=consumer_kind,
            consumer_id=consumer_id,
            payload_schema_id=f"trace-payload:{producer_kind}-to-{consumer_kind}:v1",
            producer_object_fingerprint=trace_interface_endpoint_fingerprint(
                current, producer_kind, producer_id
            ),
            consumer_object_fingerprint=trace_interface_endpoint_fingerprint(
                current, consumer_kind, consumer_id
            ),
            receipt_refs=(),
        )
        bindings.append(
            replace(
                binding,
                receipt_refs=(issue_trace_interface_receipt(current, binding),),
            )
        )
    return replace(current, interface_bindings=tuple(bindings))


def _raw_universe() -> TraceTargetUniverse:
    return TraceTargetUniverse(
        universe_id="universe:blueprint-test",
        required_source_ids=("s1", "s2"),
        required_evidence_ids=("e1", "e2"),
        required_entity_ids=("entity:actor",),
        required_entity_resolution_ids=(),
        required_location_ids=("location:site",),
        required_event_ids=("event:1", "event:2"),
        required_trace_ids=("trace:1", "trace:2"),
        required_stage_ids=("stage:trace:1:start", "stage:trace:2:pause"),
        required_hypothesis_ids=("h1", "h2"),
        required_hypothesis_evidence_link_ids=("link:1", "link:2"),
        required_hypothesis_relation_ids=("relation:alternatives",),
        required_causal_boundary_ids=("causal-boundary:h1", "causal-boundary:h2"),
        required_causal_candidate_ids=("causal:1",),
        required_causal_mechanism_ids=("mechanism:1",),
        required_confounder_review_ids=("confounder:1",),
        required_causal_scope_ids=("scope:1",),
        required_evidence_ablation_ids=("ablation:e1",),
        required_scenario_perturbation_ids=("perturb:event1",),
        required_sensitivity_ids=("sensitivity:1",),
        required_interface_binding_ids=tuple(item.binding_id for item in _current_model().interface_bindings),
        required_bounded_claim_ids=("claim:1", "claim:2"),
        required_handoff_ids=("handoff:1", "handoff:2"),
        known_good_case_ids=("case:complete",),
        known_bad_case_ids=("case:foreign-interface",),
    )


def _universe() -> TraceTargetUniverse:
    universe = _raw_universe()
    model = _current_model()
    model = replace(
        model,
        metadata={
            **model.metadata,
            "guard_purpose_contract": {
                "selected_failure_ids": ["missing-event-evidence"],
            },
        },
    )
    universe = issue_trace_target_authority(
        model,
        universe,
        expected_target_anchor=trace_expected_target_anchor(model, universe),
    )
    return attach_trace_receipts(model, _receipt(model), universe)


def _receipt(model: TraceGuardModel):
    return evaluate_model(model, include_storyline_depth=False).inference_receipt


def _qualified_universe(model: TraceGuardModel) -> TraceTargetUniverse:
    unsigned = _raw_universe()
    universe = issue_trace_target_authority(
        model,
        unsigned,
        expected_target_anchor=trace_expected_target_anchor(model, unsigned),
    )
    return attach_trace_receipts(model, _receipt(model), universe)


def _purpose_bound_model(
    model: TraceGuardModel,
    root: Path,
    *,
    model_instance_id: str = "blueprint-test",
) -> tuple[TraceGuardModel, Path]:
    repository = Path(__file__).resolve().parents[2]
    examples = repository / "examples" / "trace"
    good_source = examples / "project_radar_hydrogen_trace.yaml"
    bad_source = examples / "invalid_source_example.yaml"
    good_path = root / good_source.name
    bad_path = root / bad_source.name
    good_path.write_bytes(good_source.read_bytes())
    bad_path.write_bytes(bad_source.read_bytes())
    contract = {
        "schema_version": "researchguard.trace.task_model_purpose.v1",
        "contract_kind": "task_model_instance",
        "contract_id": "researchguard.trace.test.blueprint-purpose.v1",
        "model_instance_id": model_instance_id,
        "target_skill_id": "traceguard",
        "enforcement": "enforced",
        "purpose": "Prevent unusable event evidence from closing the trace blueprint.",
        "claim_boundary": "Native trace structure and bounded inference only.",
        "selected_failure_ids": ["missing-event-evidence"],
        "known_good": {
            "case_id": "case:complete",
            "native_oracle_id": "oracle:traceguard:known-good",
            "model_path": good_path.name,
            "model_sha256": canonical_candidate_fingerprint(read_model_data(good_path)),
        },
        "known_bad_cases": [
            {
                "case_id": "case:foreign-interface",
                "failure_id": "missing-event-evidence",
                "prevents": "Unusable event evidence closes a storyline.",
                "native_oracle_id": "oracle:traceguard:missing-event-evidence",
                "model_path": bad_path.name,
                "model_sha256": canonical_candidate_fingerprint(read_model_data(bad_path)),
            }
        ],
        "declaration_sequence": 1,
    }
    contract_path = root / "blueprint-purpose.json"
    candidate_path = root / "blueprint-model.yaml"
    contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
    bound = bind_task_guard_purpose(
        model.to_dict(), contract_path=contract_path, candidate_path=candidate_path
    )
    candidate_path.write_text(json.dumps(bound, indent=2), encoding="utf-8")
    return TraceGuardModel.from_dict(bound), candidate_path


def test_fresh_process_accepts_independently_authored_alternate_trace_target(
    tmp_path: Path,
) -> None:
    payload = _payload()
    payload["metadata"] = {
        **dict(payload["metadata"]),
        "model_instance_id": "blueprint-alternate",
    }
    model, candidate_path = _purpose_bound_model(
        _current_model(payload),
        tmp_path,
        model_instance_id="blueprint-alternate",
    )
    universe = _qualified_universe(model)
    receipt = _receipt(model)
    assert check_blueprint(
        model,
        receipt,
        universe,
        candidate_path=str(candidate_path),
    ).status == "complete"
    context_path = tmp_path / "alternate-trace-context.json"
    context_path.write_text(
        json.dumps(
            {
                "model": model.to_dict(),
                "universe": universe.to_dict(),
                "candidate_path": str(candidate_path),
            }
        ),
        encoding="utf-8",
    )
    child = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            """
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd() / 'tests'))
from target_material_fixtures import install_test_expected_target_producer
install_test_expected_target_producer()
from admission_fixtures import install_test_native_receipt_producers
install_test_native_receipt_producers()
from researchguard.trace.blueprint import TraceTargetUniverse, check_blueprint, reverse_trace_output
from researchguard.trace.evaluator import evaluate_model
from researchguard.trace.schema import TraceGuardModel

context = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
model = TraceGuardModel.from_dict(context['model'])
universe = TraceTargetUniverse.from_dict(context['universe'])
receipt = evaluate_model(model, include_storyline_depth=False).inference_receipt
result = check_blueprint(model, receipt, universe, candidate_path=context['candidate_path'])
trace = reverse_trace_output(
    model,
    receipt,
    'claim:1',
    universe,
    candidate_path=context['candidate_path'],
)
authority = universe.target_authority
print(json.dumps({
    'status': result.status,
    'trace_status': trace['trace_status'],
    'trace_output_id': trace['output_id'],
    'target_id': authority.target_id,
    'request_id': authority.request_id,
    'target_revision': authority.target_revision,
    'target_fingerprint': authority.target_fingerprint,
}))
""",
            str(context_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(child.stdout)
    assert result["status"] == "complete"
    assert result["trace_status"] == "complete"
    assert result["trace_output_id"] == "claim:1"
    assert result["target_id"] == "blueprint-alternate"
    assert result["request_id"].startswith("request:")
    assert result["target_revision"] == result["target_fingerprint"]


def test_trace_queries_each_consume_one_blueprint_qualification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, candidate_path = _purpose_bound_model(_current_model(), tmp_path)
    universe = _universe()
    receipt = _receipt(model)
    original = blueprint_module.check_blueprint
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(blueprint_module, "check_blueprint", counted)
    blueprint_module.impact_blueprint(
        model,
        receipt,
        ("e1",),
        universe,
        candidate_path=str(candidate_path),
    )
    assert calls == 1
    blueprint_module.reverse_trace_output(
        model,
        receipt,
        "claim:1",
        universe,
        candidate_path=str(candidate_path),
    )
    assert calls == 2


def impact_blueprint(
    model: TraceGuardModel,
    receipt: object,
    changed_ids: tuple[str, ...] | list[str],
    universe: TraceTargetUniverse | None = None,
) -> dict[str, object]:
    """Run impact tests only after one current native TraceGuard replay."""

    with TemporaryDirectory(prefix="researchguard-trace-impact-") as root:
        bound, candidate_path = _purpose_bound_model(model, Path(root))
        current_receipt = _receipt(bound)
        base = universe or _universe()
        unsigned = replace(base, target_authority=None, native_receipt_refs=())
        current_universe = issue_trace_target_authority(
            bound,
            unsigned,
            expected_target_anchor=trace_expected_target_anchor(bound, unsigned),
        )
        current_universe = attach_trace_receipts(
            bound, current_receipt, current_universe
        )
        return _impact_blueprint(
            bound,
            current_receipt,
            changed_ids,
            current_universe,
            candidate_path=str(candidate_path),
        )


def test_trace_impact_without_current_qualification_is_atomically_blocked() -> None:
    model = _current_model()
    result = _impact_blueprint(
        model,
        _receipt(model),
        ("e1",),
        _universe(),
    )
    assert result["query_status"] == "blocked"
    assert result["qualification_status"] == "incomplete"
    assert result["target_authority_status"] == "current"
    assert result["target_material_status"] == "current"
    assert {item["code"] for item in result["qualification_gaps"]} >= {
        "native-purpose-replay-not-run"
    }
    assert result["affected_evidence_ids"] == []
    assert result["partial_result_suppressed"] is True
    trace = reverse_trace_output(
        model,
        _receipt(model),
        "claim:missing",
        _universe(),
    )
    assert trace["query_status"] == "blocked"
    assert trace["qualification_status"] == "incomplete"
    assert trace["output_id"] == ""
    assert trace["hierarchy_nodes"] == []
    assert trace["partial_result_suppressed"] is True


def test_current_blueprint_has_deterministic_complete_hierarchy(tmp_path: Path) -> None:
    model, candidate_path = _purpose_bound_model(_current_model(), tmp_path)
    receipt = _receipt(model)
    result = check_blueprint(
        model, receipt, _qualified_universe(model), candidate_path=str(candidate_path)
    )
    assert result.status == "complete"


def test_failure_class_denominator_must_exactly_match_native_purpose(
    tmp_path: Path,
) -> None:
    model, candidate_path = _purpose_bound_model(_current_model(), tmp_path)
    unsigned = replace(_universe(), target_authority=None)
    universe = issue_trace_target_authority(
        model,
        unsigned,
        expected_target_anchor=trace_expected_target_anchor(
            model,
            unsigned,
            failure_class_ids=("different-failure-class",),
        ),
    )
    result = check_blueprint(
        model,
        _receipt(model),
        universe,
        candidate_path=str(candidate_path),
    )
    assert result.status == "incomplete"
    assert "native-failure-class-denominator-mismatch" in {
        item.code for item in result.gaps
    }
    kinds = {item.kind for item in result.hierarchy}
    assert {"entity", "location", "causal_boundary", "causal_candidate", "causal_mechanism", "confounder"} <= kinds
    by_id = {item.projection_id: item for item in result.hierarchy}
    assert all(
        item.depth == by_id[item.parent_projection_id].depth + 1
        for item in result.hierarchy
        if item.parent_projection_id
    )
    permuted = replace(
        model,
        sources=tuple(reversed(model.sources)),
        evidence=tuple(reversed(model.evidence)),
        events=tuple(reversed(model.events)),
        traces=tuple(reversed(model.traces)),
        storyline_hypotheses=tuple(reversed(model.storyline_hypotheses)),
    )
    assert project_hierarchy(permuted) == project_hierarchy(model)


def test_serialized_trace_authority_replays_without_process_registry(
    tmp_path: Path,
) -> None:
    model, candidate_path = _purpose_bound_model(_current_model(), tmp_path)
    universe = TraceTargetUniverse.from_dict(
        json.loads(json.dumps(_qualified_universe(model).to_dict()))
    )
    assert check_blueprint(
        model,
        _receipt(model),
        universe,
        candidate_path=str(candidate_path),
    ).status == "complete"
    assert not hasattr(target_authority_transport, "_FROZEN_NATIVE_RESULTS")


def test_external_trace_target_material_remains_unverified() -> None:
    model = _current_model()
    current_universe = _universe()
    current_anchor = current_universe.target_authority.expected_target_anchor
    universe = replace(current_universe, target_authority=None)
    external_anchor = expected_target_anchor_from_material(
        member_id="traceguard",
        task_id=current_anchor.task_id,
        target_request_fingerprint=current_anchor.target_request_fingerprint,
        target_id=current_anchor.target_id,
        target_revision=current_anchor.target_revision,
        material_locator="https://example.invalid/trace-target.json",
        material_fingerprint=current_anchor.material_fingerprint,
        admission_request_scope="external-unavailable",
    )
    unverified = issue_trace_target_authority(
        model,
        universe,
        expected_target_anchor=external_anchor,
    )
    result = check_blueprint(model, _receipt(model), unverified)
    assert unverified.target_authority.status == "unverified"
    assert any(item.code == "native-target-material-unverified" for item in result.gaps)
    trace = reverse_trace_output(
        model,
        _receipt(model),
        "claim:missing",
        unverified,
    )
    assert trace["query_status"] == "blocked"
    assert trace["target_material_status"] == "unverified"
    assert trace["output_id"] == ""
    assert trace["sources"] == []
    assert trace["partial_result_suppressed"] is True


def test_simultaneous_trace_model_universe_authority_shrink_cannot_self_sign_complete() -> None:
    current = _current_model()
    universe = _universe()
    authority = universe.target_authority
    assert authority is not None
    shrunk_model = replace(current, expected_sensitivities=())
    resigned = self_resign_target_authority(
        authority,
        (
            item
            for item in authority.items
            if not (item.kind == "sensitivity" and item.object_id == "sensitivity:1")
        ),
    )
    shrunk_universe = replace(
        universe,
        required_sensitivity_ids=(),
        target_authority=resigned,
    )
    result = check_blueprint(shrunk_model, _receipt(shrunk_model), shrunk_universe)
    assert result.status == "incomplete"
    assert any(item.code == "native-target-denominator-mismatch" for item in result.gaps)


def test_fresh_process_first_issue_replays_original_trace_target_material(
    tmp_path: Path,
) -> None:
    full_universe = _universe()
    shrunk_model = replace(_current_model(), expected_sensitivities=())
    shrunk_model = replace(
        shrunk_model,
        interface_bindings=tuple(
            replace(
                binding,
                receipt_refs=(issue_trace_interface_receipt(shrunk_model, binding),),
            )
            for binding in shrunk_model.interface_bindings
        ),
    )
    shrunk_model, candidate_path = _purpose_bound_model(shrunk_model, tmp_path)
    assert full_universe.target_authority is not None
    assert full_universe.target_authority.native_attestation is not None
    shrunk_universe = replace(
        full_universe,
        required_sensitivity_ids=(),
        target_authority=None,
    )
    context_path = tmp_path / "trace-child-context.json"
    context_path.write_text(
        json.dumps(
            {
                "model": shrunk_model.to_dict(),
                "universe": shrunk_universe.to_dict(),
                "candidate_path": str(candidate_path),
                "expected_target_anchor": full_universe.target_authority.expected_target_anchor.to_dict(),
            }
        ),
        encoding="utf-8",
    )
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd() / 'tests'))
from target_material_fixtures import install_test_expected_target_producer
install_test_expected_target_producer()
from admission_fixtures import install_test_native_receipt_producers
install_test_native_receipt_producers()
from researchguard.trace.blueprint import TraceTargetUniverse, check_blueprint, _bind_trace_target_authority as issue_trace_target_authority
from researchguard.trace.evaluator import evaluate_model
from researchguard.trace.schema import TraceGuardModel
from researchguard.target_authority import ExpectedTargetAnchor

context = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
model = TraceGuardModel.from_dict(context['model'])
universe = TraceTargetUniverse.from_dict(context['universe'])
universe = issue_trace_target_authority(
    model,
    universe,
    expected_target_anchor=ExpectedTargetAnchor.from_dict(context['expected_target_anchor']),
)
receipt = evaluate_model(model, include_storyline_depth=False).inference_receipt
result = check_blueprint(model, receipt, universe, candidate_path=context['candidate_path'])
print(json.dumps({'status': result.status, 'gaps': [[gap.code, gap.object_id] for gap in result.gaps]}))
""",
            str(context_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(child.stdout)
    assert payload["status"] == "incomplete"
    assert ["target-authority-omitted-sensitivity", "sensitivity:1"] in payload["gaps"]


@pytest.mark.parametrize(
    ("field", "missing_id", "kind"),
    [
        ("required_entity_ids", "entity:missing", "entity"),
        ("required_entity_resolution_ids", "entity-resolution:missing", "entity-resolution"),
        ("required_location_ids", "location:missing", "location"),
        ("required_hypothesis_evidence_link_ids", "link:missing", "hypothesis-evidence-link"),
        ("required_causal_candidate_ids", "causal:missing", "causal-candidate"),
        ("required_interface_binding_ids", "interface:missing", "interface-binding"),
    ],
)
def test_full_universe_denominator_rejects_omitted_stable_objects(
    field: str, missing_id: str, kind: str
) -> None:
    universe = _universe()
    universe = replace(universe, **{field: (*getattr(universe, field), missing_id)})
    result = check_blueprint(_current_model(), _receipt(_current_model()), universe)
    assert any(item.code == f"omitted-universe-{kind}" and item.object_id == missing_id for item in result.gaps)


@pytest.mark.parametrize(
    ("collection", "row", "gap_code"),
    [
        (
            "sources",
            {"source_id": "source:unused", "title": "unused", "lineage_id": "unused", "independence_group": "unused", "source_status": "stable_keep"},
            "unconsumed-source-output",
        ),
        (
            "entities",
            {"mention_id": "entity:unused", "evidence_id": None, "raw_name": "Unused", "normalized_name": "unused"},
            "unconsumed-entity-output",
        ),
        (
            "locations",
            {"location_id": "location:unused", "raw_text": "Unused", "normalized_name": "unused"},
            "unconsumed-location-output",
        ),
        (
            "causal_mechanisms",
            {"mechanism_id": "mechanism:unused", "hypothesis_id": "h1", "description": "unused"},
            "unconsumed-causal-mechanism-output",
        ),
    ],
)
def test_unconsumed_full_model_outputs_require_explicit_disposition(
    collection: str, row: dict[str, object], gap_code: str
) -> None:
    payload = _payload()
    payload[collection].append(row)
    model = _current_model(payload)
    result = check_blueprint(model, _receipt(model), _universe())
    assert any(item.code == gap_code for item in result.gaps)


def test_projected_hierarchy_rejects_depth_jump_and_foreign_cross_link() -> None:
    hierarchy = list(project_hierarchy(_current_model()))
    index = next(index for index, item in enumerate(hierarchy) if item.parent_projection_id)
    hierarchy[index] = replace(
        hierarchy[index],
        depth=hierarchy[index].depth + 2,
        cross_link_parent_ids=(*hierarchy[index].cross_link_parent_ids, "foreign:projection"),
    )
    codes = {item.code for item in _hierarchy_gaps(tuple(hierarchy))}
    assert "hierarchy-depth-jump" in codes
    assert "foreign-hierarchy-cross-link" in codes


@pytest.mark.parametrize("field", ["root", "interface"])
def test_trace_blueprint_loaders_reject_unknown_fields(field: str) -> None:
    if field == "root":
        raw = _universe().to_dict()
        raw["future"] = True
        with pytest.raises(ValueError, match="unknown fields"):
            TraceTargetUniverse.from_dict(raw)
    else:
        raw = _current_model().to_dict()
        raw["interface_bindings"][0]["future"] = True
        with pytest.raises(Exception, match="unknown current-schema fields"):
            TraceGuardModel.from_dict(raw)


def test_native_purpose_is_not_replaced_by_arbitrary_case_ids() -> None:
    model = _current_model()
    result = check_blueprint(model, _receipt(model), _universe())
    assert result.status == "incomplete"
    assert any(item.code == "native-purpose-replay-not-run" for item in result.gaps)


def test_invalid_reference_missing_input_and_unconsumed_event_remain_visible() -> None:
    model = _current_model()
    receipt = _receipt(model)
    event = replace(model.events[0], evidence_ids=[], unresolved_input_disposition="")
    orphan = replace(model.events[1], unconsumed_output_disposition="")
    broken = replace(model, events=(event, orphan), traces=(replace(model.traces[1], event_ids=[]), model.traces[0]))
    result = check_blueprint(broken, receipt, _universe())
    codes = {item.code for item in result.gaps}
    assert "missing-evidence-input" in codes
    assert "unconsumed-event-output" in codes
    invalid = replace(model, events=(replace(model.events[0], evidence_ids=["missing:evidence"]), model.events[1]))
    invalid_result = check_blueprint(invalid, receipt, _universe())
    assert any(item.code == "invalid-native-reference" for item in invalid_result.gaps)


def test_receipt_and_consumer_freshness_fail_closed_without_second_solver() -> None:
    model = _current_model()
    receipt = _receipt(model)
    changed_evidence = replace(model.evidence[0], raw_text="changed", content_fingerprint=_sha("changed"))
    changed_evidence = replace(changed_evidence, object_fingerprint=semantic_object_fingerprint(changed_evidence))
    stale_model = replace(model, evidence=(changed_evidence, model.evidence[1]))
    assert check_blueprint(stale_model, receipt, _universe()).status == "stale"
    binding = replace(model.interface_bindings[0], consumer_object_fingerprint=_sha("wrong-consumer"))
    stale_interface = replace(model, interface_bindings=(binding, *model.interface_bindings[1:]))
    assert any(item.code == "stale-interface-consumer" for item in check_blueprint(stale_interface, receipt, _universe()).gaps)


def test_extra_current_interface_is_rejected_as_foreign_dependency() -> None:
    model = _current_model()
    extra = TraceInterfaceBinding(
        binding_id="interface:s1->e2:foreign",
        producer_kind="source",
        producer_id="s1",
        consumer_kind="evidence_fact",
        consumer_id="e2",
        payload_schema_id="trace-payload:source-to-evidence_fact:v1",
        producer_object_fingerprint=trace_interface_endpoint_fingerprint(model, "source", "s1"),
        consumer_object_fingerprint=trace_interface_endpoint_fingerprint(model, "evidence_fact", "e2"),
        receipt_refs=(),
    )
    extra = replace(extra, receipt_refs=(issue_trace_interface_receipt(model, extra),))
    foreign = replace(model, interface_bindings=(*model.interface_bindings, extra))
    result = check_blueprint(foreign, _receipt(foreign), _universe())
    assert any(item.code == "unexpected-interface" and item.object_id == extra.binding_id for item in result.gaps)


def test_full_impact_closure_keeps_alternative_and_mixed_unknown_blocker() -> None:
    model = _current_model()
    receipt = _receipt(model)
    impact = impact_blueprint(model, receipt, (model.evidence[0].content_fingerprint, "foreign:unowned"), _universe())
    assert impact["affected_evidence_ids"] == []
    assert impact["affected_event_ids"] == []
    assert impact["affected_trace_ids"] == []
    assert impact["affected_hypothesis_ids"] == []
    assert impact["affected_causal_candidate_ids"] == []
    assert impact["affected_perturbation_ids"] == []
    assert impact["unknown_dependency_ids"] == ["foreign:unowned"]
    assert impact["unknown_ownership"] is True
    assert impact["partial_result_suppressed"] is True
    shared_transform = impact_blueprint(model, receipt, (model.evidence[0].normalizer_fingerprint,), _universe())
    assert shared_transform["affected_evidence_ids"] == ["e1", "e2"]
    entity_impact = impact_blueprint(model, receipt, ("entity:actor", "location:site"), _universe())
    assert entity_impact["affected_event_ids"] == ["event:1"]
    assert entity_impact["affected_causal_scope_ids"] == ["scope:1"]


def test_reverse_trace_contains_retrieval_transform_causal_and_alternative_boundaries(
    tmp_path: Path,
) -> None:
    model, candidate_path = _purpose_bound_model(_current_model(), tmp_path)
    receipt = _receipt(model)
    trace = reverse_trace_output(
        model,
        receipt,
        "claim:1",
        _qualified_universe(model),
        candidate_path=str(candidate_path),
    )
    assert trace["sources"][0]["retrieval_locator"] == "https://example.invalid/s1"
    assert trace["sources"][0]["provider_id"] == "provider:test"
    assert trace["evidence"][0]["normalizer_id"] == "normalizer:test"
    assert trace["evidence"][0]["extractor_id"] == "extractor:test"
    assert trace["alternatives"][0]["hypothesis_id"] == "h2"
    assert trace["confounders"][0]["confounder_id"] == "confounder:1"
    assert trace["causal_boundary"]["formal_causal_identification_licensed"] is False
    assert trace["formal_causal_identification_licensed"] is False
    assert "unread source bytes" in trace["terminal_capability_boundary"]
    with pytest.raises(ValueError, match="must resolve to exactly one hypothesis"):
        reverse_trace_output(
            model,
            receipt,
            "claim:missing",
            _qualified_universe(model),
            candidate_path=str(candidate_path),
        )


def test_export_round_trip_preserves_current_model_and_fingerprint() -> None:
    model = _current_model()
    receipt = _receipt(model)
    exported = export_blueprint(model, receipt, _universe())
    reloaded = TraceGuardModel.from_dict(exported["model"])
    replay = _receipt(reloaded)
    assert export_blueprint(reloaded, replay, TraceTargetUniverse.from_dict(exported["target_universe"])) == exported


def test_grouped_blueprint_cli_and_no_flat_fallback(tmp_path, capsys) -> None:
    from researchguard.trace.cli import main
    from researchguard.trace.loader import dump_yaml

    model, _bound_path = _purpose_bound_model(_current_model(), tmp_path)
    model_path = tmp_path / "trace.yaml"
    universe_path = tmp_path / "universe.json"
    model_path.write_text(dump_yaml(model.to_dict()), encoding="utf-8")
    # The purpose bundle is relative to the candidate directory, so the bound
    # model remains current when written under another filename in that directory.
    universe_path.write_text(
        json.dumps(_qualified_universe(model).to_dict()), encoding="utf-8"
    )
    assert main(["blueprint", "check", str(model_path), str(universe_path)]) == 0
    check_payload = json.loads(capsys.readouterr().out)
    assert check_payload["status"] == "complete"

    assert main(
        [
            "blueprint",
            "impact",
            str(model_path),
            model.evidence[0].content_fingerprint,
            "--universe",
            str(universe_path),
        ]
    ) == 0
    impact_payload = json.loads(capsys.readouterr().out)
    assert impact_payload["affected_evidence_ids"] == ["e1"]
    assert impact_payload["affected_hypothesis_ids"] == ["h1", "h2"]

    assert main(
        [
            "blueprint",
            "impact",
            str(model_path),
            model.evidence[0].content_fingerprint,
            "foreign:unowned",
            "--universe",
            str(universe_path),
        ]
    ) == 3
    blocked_payload = json.loads(capsys.readouterr().out)
    assert blocked_payload["unknown_dependency_ids"] == ["foreign:unowned"]
    assert blocked_payload["partial_result_suppressed"] is True
    assert blocked_payload["affected_evidence_ids"] == []

    assert main(
        [
            "blueprint",
            "trace",
            str(model_path),
            "claim:1",
            "--universe",
            str(universe_path),
        ]
    ) == 0
    trace_payload = json.loads(capsys.readouterr().out)
    assert trace_payload["canonical_receipt"]["receipt_id"]
    assert trace_payload["terminal_capability_boundary"]

    assert main(["blueprint", "export", str(model_path), str(universe_path)]) == 0
    export_payload = json.loads(capsys.readouterr().out)
    assert export_payload["check"]["status"] == "complete"
    with pytest.raises(SystemExit) as exc:
        main(["blueprint-check", str(model_path), str(universe_path)])
    assert exc.value.code == 2


def test_trace_blueprint_cannot_clear_its_own_required_denominator(tmp_path: Path) -> None:
    model, candidate_path = _purpose_bound_model(_current_model(), tmp_path)
    universe = _universe()
    shrunk = replace(
        universe,
        **{
            name: ()
            for name in universe.__dataclass_fields__
            if name.startswith("required_")
        },
    )
    assert check_blueprint(
        model,
        _receipt(model),
        shrunk,
        candidate_path=str(candidate_path),
    ).status != "complete"


def test_required_trace_interfaces_need_current_native_receipt_bindings() -> None:
    model = _current_model()
    missing = replace(
        model,
        interface_bindings=tuple(replace(item, receipt_refs=()) for item in model.interface_bindings),
    )
    result = check_blueprint(missing, _receipt(missing), _universe())
    assert result.status == "incomplete"
    assert any(item.code == "missing-interface-native-receipt" for item in result.gaps)


def test_trace_reverse_blocks_stale_canonical_receipt(tmp_path: Path) -> None:
    model, candidate_path = _purpose_bound_model(_current_model(), tmp_path)
    receipt = _receipt(model)
    changed = replace(model.evidence[0], raw_text="changed", content_fingerprint=_sha("changed"))
    changed = replace(changed, object_fingerprint=semantic_object_fingerprint(changed))
    stale_model = replace(model, evidence=(changed, model.evidence[1]))
    trace = reverse_trace_output(
        stale_model,
        receipt,
        "claim:missing",
        _universe(),
        candidate_path=str(candidate_path),
    )
    assert trace["qualification_status"] == "stale"
    assert trace["trace_status"] == "incomplete"
    assert trace["trace_gaps"]
    assert trace["output_id"] == ""
    assert trace["trace_ids"] == []
    assert trace["partial_result_suppressed"] is True
