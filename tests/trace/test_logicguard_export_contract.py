from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path

import pytest

from researchguard.trace.evaluator import evaluate_model
from researchguard.trace.export_logicguard import (
    LOGICGUARD_HANDOFF_SCHEMA,
    logicguard_bundle,
    validate_logicguard_bundle,
)
from researchguard.trace.loader import load_model
from researchguard.trace.schema import CausalCandidate, CausalMechanism


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples" / "trace"


def test_export_is_versioned_complete_and_pure():
    result = evaluate_model(load_model(EXAMPLES / "patent_as_weak_signal.yaml"), include_storyline_depth=False)
    before = copy.deepcopy(result.to_dict())

    first = logicguard_bundle(result)
    second = logicguard_bundle(result)

    assert first == second
    assert result.to_dict() == before
    assert first["schema"] == LOGICGUARD_HANDOFF_SCHEMA
    assert first["schema_id"] == LOGICGUARD_HANDOFF_SCHEMA
    assert first["metadata"]["source_model_fingerprint"]
    claim = first["claims"][0]
    assert claim["limitation"] == "Patent evidence is technology background unless linked to explicit deployment evidence."
    assert "HL-MRF" not in claim["limitation"]
    assert claim["native_causal_license"] == "bounded_non_causal"
    assert claim["domain_gaps"] == ["missing_domain_proposition", "missing_domain_mechanism"]
    validate_logicguard_bundle(first)


def test_current_consumer_rejects_unversioned_and_legacy_warrant_shapes():
    result = evaluate_model(load_model(EXAMPLES / "patent_as_weak_signal.yaml"), include_storyline_depth=False)
    bundle = logicguard_bundle(result)

    old = copy.deepcopy(bundle)
    old["schema"] = "researchguard.trace.logic-handoff.legacy"
    with pytest.raises(ValueError, match="schema"):
        validate_logicguard_bundle(old)

    old = copy.deepcopy(bundle)
    old["claims"][0]["warrant"] = "legacy solver wording"
    with pytest.raises(ValueError, match="legacy claim.warrant"):
        validate_logicguard_bundle(old)


def test_multiple_linked_hypotheses_without_selection_are_explicitly_ambiguous():
    model = load_model(EXAMPLES / "project_radar_hydrogen_trace.yaml")
    trace = model.traces[0]
    ambiguous = replace(model, traces=(replace(trace, claim=None),))
    result = evaluate_model(ambiguous, include_storyline_depth=False)
    projected = result.traces[0]

    assert projected.domain_proposition == ""
    assert "ambiguous_domain_proposition" in projected.domain_gaps
    assert len(projected.domain_candidate_propositions) == 2


def test_scalar_metadata_refs_are_not_iterated_as_characters():
    model = load_model(EXAMPLES / "structural_thesis_trace.yaml")
    trace_id = model.traces[0].trace_id
    changed = replace(
        model,
        metadata={
            **model.metadata,
            "trace_assumption_refs": {trace_id: "ASSUMPTION-ONE"},
        },
    )
    projected = evaluate_model(changed, include_storyline_depth=False).traces[0]

    assert projected.domain_assumption_refs == ()
    assert "domain_assumption:metadata_scalar_not_collection" in projected.domain_gaps
    assert not any(ref in {"A", "S", "U", "M", "P", "T", "I", "O", "N"} for ref in projected.domain_assumption_refs)


def test_native_causal_license_requires_typed_mechanism_and_candidate():
    model = load_model(EXAMPLES / "project_radar_hydrogen_trace.yaml")
    hypothesis = replace(
        model.storyline_hypotheses[0],
        mechanism_ids=["mechanism:funding-to-implementation"],
        causal=True,
        bounded_non_causal=False,
    )
    changed = replace(
        model,
        storyline_hypotheses=(hypothesis, model.storyline_hypotheses[1]),
        causal_mechanisms=(
            CausalMechanism(
                "mechanism:funding-to-implementation",
                hypothesis.hypothesis_id,
                "Funding enables the implementation pathway.",
                ["ev_funding"],
            ),
        ),
        causal_candidates=(
            CausalCandidate(
                "causal:funding-to-implementation",
                hypothesis.hypothesis_id,
                ["event_funding"],
                ["event_tender"],
                ["mechanism:funding-to-implementation"],
                [],
                [],
                None,
            ),
        ),
    )
    result = evaluate_model(changed, include_storyline_depth=False)
    projected = result.traces[0]
    claim = logicguard_bundle(result)["claims"][0]

    assert projected.domain_mechanism_refs == ("mechanism:funding-to-implementation",)
    assert projected.native_causal_license == "causal_assertion_licensed"
    assert claim["native_causal_license"] == "causal_assertion_licensed"


EVERGIVEN = Path(__file__).parent / "fixtures/evergiven/tr_v2b.yaml"


def test_export_keeps_polarity_per_hypothesis() -> None:
    model = load_model(EVERGIVEN)
    result = evaluate_model(model, include_storyline_depth=False)
    before_model, before_result = copy.deepcopy(model), copy.deepcopy(result.to_dict())
    bundle = logicguard_bundle(result, model=model)
    assert bundle["claims"] == logicguard_bundle(result)["claims"]
    assert bundle["schema"] == LOGICGUARD_HANDOFF_SCHEMA
    hypotheses = {item["hypothesis_id"]: item for item in bundle["hypotheses"]}
    suez = hypotheses["h_suez"]
    opposing = {"anc-unctad-surge", "anc-transpacific"}
    assert opposing <= set(suez["opposing_evidence_ids"])
    assert not opposing & set(suez["supporting_evidence_ids"])
    native = {item.hypothesis_id: item for item in result.inference.hypothesis_projections}
    assert suez["rank"] == native["h_suez"].rank
    assert suez["support"] == pytest.approx(native["h_suez"].support)
    assert suez["causal_status"] == native["h_suez"].causal_status
    evidence = {item["evidence_id"]: item for item in bundle["evidence"]}
    for evidence_id in opposing:
        assert evidence[evidence_id]["text"] == model.evidence_by_id()[evidence_id].raw_text
        assert evidence[evidence_id]["source_id"] == model.evidence_by_id()[evidence_id].source_id
    assert validate_logicguard_bundle(bundle) == bundle
    assert logicguard_bundle(result, model=model) == bundle
    assert model == before_model and result.to_dict() == before_result


@pytest.mark.parametrize("mutation", ["hypothesis_shape", "evidence_shape", "missing_evidence", "invalid_support"])
def test_new_handoff_fields_reject_wrong_shapes_and_missing_refs(mutation) -> None:
    model = load_model(EVERGIVEN)
    bundle = logicguard_bundle(evaluate_model(model, include_storyline_depth=False), model=model)
    if mutation == "hypothesis_shape":
        bundle["hypotheses"][0]["opposing_evidence_ids"] = "anc-unctad-surge"
    elif mutation == "evidence_shape":
        bundle["evidence"][0]["text"] = None
    elif mutation == "missing_evidence":
        bundle["hypotheses"][0]["supporting_evidence_ids"] = ["missing-anchor"]
    else:
        bundle["hypotheses"][0]["support"] = float("nan")
    with pytest.raises(ValueError):
        validate_logicguard_bundle(bundle)


def test_both_polarities_and_contradicting_ids_are_retained(caplog) -> None:
    from researchguard.trace.schema import HypothesisEvidenceLink
    from researchguard.logic.trace_import import model_dict_from_trace_bundle
    model = load_model(EVERGIVEN)
    primary = next(item for item in model.storyline_hypotheses if item.hypothesis_id == "h_suez")
    changed = replace(model, storyline_hypotheses=tuple(
        replace(item, contradicting_evidence_ids=["anc-sca-dates"]) if item == primary else item
        for item in model.storyline_hypotheses), hypothesis_evidence_links=model.hypothesis_evidence_links + (
            HypothesisEvidenceLink("dual-sign-test", "h_suez", "anc-transpacific", "support"),
            HypothesisEvidenceLink("limit-path-test", "h_suez", "anc-sca-dates", "limit"),
        ))
    bundle = logicguard_bundle(evaluate_model(changed, include_storyline_depth=False), model=changed)
    hypothesis = next(item for item in bundle["hypotheses"] if item["hypothesis_id"] == "h_suez")
    assert {"anc-sca-dates", "anc-transpacific"} <= set(hypothesis["opposing_evidence_ids"])
    assert "anc-transpacific" in hypothesis["supporting_evidence_ids"]
    imported = model_dict_from_trace_bundle(bundle)
    edges = imported["edges"]
    assert {"source": "anc-transpacific", "target": "h_suez", "type": "supports"} in edges
    rebuttals = {edge["source"] for edge in edges if edge["target"] == "h_suez" and edge["type"] == "attacks"}
    assert any(edge["source"] == "anc-transpacific" and edge["target"] in rebuttals for edge in edges)
    assert "both supports and opposes" in caplog.text
    limitations = {edge["source"] for edge in edges if edge["target"] == "h_suez" and edge["type"] == "qualifies"}
    assert limitations and all(imported["nodes"][item]["type"] == "Limitation" for item in limitations)
    assert any(edge["source"] == "anc-sca-dates" and edge["target"] in limitations for edge in edges)
    no_primary = copy.deepcopy(bundle)
    for item in no_primary["hypotheses"]:
        item["role"] = "alternative"
    assert model_dict_from_trace_bundle(no_primary)["model"]["root_claim"] == bundle["hypotheses"][0]["hypothesis_id"]


def test_trace_only_model_keeps_legacy_import_path_with_empty_hypotheses() -> None:
    from researchguard.logic.trace_import import model_dict_from_trace_bundle
    model = load_model(EXAMPLES / "incident_response_storyline.yaml")
    bundle = logicguard_bundle(evaluate_model(model, include_storyline_depth=False), model=model)
    assert bundle["hypotheses"] == []
    assert validate_logicguard_bundle(bundle) == bundle
    assert model_dict_from_trace_bundle(bundle)["model"]["root_claim"] == "claim_trace_metadata_incident"


def test_existing_empty_evidence_remains_visible_in_negative_export() -> None:
    model = load_model(EXAMPLES / "invalid_source_example.yaml")
    bundle = logicguard_bundle(evaluate_model(model, include_storyline_depth=False), model=model)
    assert bundle["hypotheses"] == []
    assert any(item["evidence_id"] == "ev_invalid" and item["text"] == "" for item in bundle["evidence"])
    assert validate_logicguard_bundle(bundle) == bundle
