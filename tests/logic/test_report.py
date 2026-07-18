from __future__ import annotations

from researchguard.logic import generate_markdown_report, load_model, model_to_outline


def test_report_contains_required_sections() -> None:
    model = load_model("examples/logic/engineering_efficiency_argument.yaml")
    report = generate_markdown_report(model)
    for heading in [
        "Executive Summary",
        "Root Claim Status",
        "Support Structure",
        "Attack / Rebuttal Structure",
        "Fragility Analysis",
        "Counterexample Traces",
        "Suggested Repairs",
        "Suggested Rewrite",
    ]:
        assert heading in report


def test_outline_uses_hierarchy() -> None:
    model = load_model("examples/logic/engineering_efficiency_argument.yaml")
    outline = model_to_outline(model)
    assert "D0 (Document)" in outline
    assert "B_results (ArgumentBlock)" in outline
    assert "Root Claim" in outline
