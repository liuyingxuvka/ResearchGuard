from __future__ import annotations

from researchguard.logic import generate_markdown_report, load_model


def test_report_contains_required_sections() -> None:
    model = load_model("examples/logic/engineering_efficiency_argument.yaml")
    report = generate_markdown_report(model)
    for heading in [
        "Executive Summary",
        "Root Claim Status",
        "Support Structure",
        "Attack Structure",
        "Fragility Analysis",
        "Counterexample Traces",
        "Suggested Repairs",
        "Suggested Rewrite",
    ]:
        assert heading in report




def test_report_groups_full_attack_chains_and_shares_native_unresolved_items():
    import re
    from researchguard.logic.execution_depth import build_native_depth_analysis
    model = load_model('examples/research/evergiven/logic.yaml')
    report = generate_markdown_report(model)
    assert not re.search(r'[0-9a-f]{64}', report)
    support = report.split('## Support Structure')[1].split('## Attack Structure')[0]
    assert 'R_pretrend' not in support
    attack = report.split('## Attack Structure')[1].split('## Missing Warrants')[0]
    assert 'E_pretrend -> R_pretrend -> h_suez' in attack
    depth = build_native_depth_analysis(model)
    unresolved = set(depth.tournament.unresolved_competitor_ids)
    unresolved.update(item for row in depth.tournament.candidates for item in row.unresolved_objection_ids)
    assert f"Unresolved competitors: {', '.join(sorted(unresolved)) or 'None'}" in report
