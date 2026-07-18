from __future__ import annotations

from researchguard.logic import diagnose_model, evaluate_model, load_model


def _codes(example: str) -> set[str]:
    model = load_model(f"examples/logic/{example}")
    report = diagnose_model(model, evaluate_model(model))
    return {finding.code for finding in report.findings}


def test_missing_warrant_hidden_assumption_and_undercut_diagnostics() -> None:
    codes = _codes("engineering_efficiency_argument.yaml")
    assert "missing_warrant" in codes
    assert "hidden_assumption" in codes
    assert "undercut_warrant" in codes


def test_causal_overclaim_diagnostic() -> None:
    codes = _codes("scientific_causal_claim.yaml")
    assert "causal_overclaim" in codes
    assert "unanswered_rebuttal" in codes


def test_context_and_definition_drift_diagnostics() -> None:
    codes = _codes("literature_review_argument.yaml")
    assert "context_as_evidence_error" in codes
    assert "definition_drift" in codes


def test_policy_overclaiming_and_scope_diagnostics() -> None:
    codes = _codes("policy_argument.yaml")
    assert "overclaiming" in codes
    assert "scope_mismatch" in codes
