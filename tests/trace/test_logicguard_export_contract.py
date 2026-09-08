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
    assert first["metadata"]["native_inference_receipt_id"]
    assert first["metadata"]["native_inference_receipt"]["receipt_id"]
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
