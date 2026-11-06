"""research_verdict: one independent aspect of the question status."""
from dataclasses import dataclass
from pathlib import Path
import sys
from ._research_cases import native_summary_numbers
from ._research_cases import Hypothesis, Ablation, Question, excluded, accepted, unused, route_conflicts, rule, unknown_gap_hypotheses, consistent_tree, dangling_reference, unused_hypothesis, gap_hypotheses, copied_content, library_anchors, routes_contradict, every_ablation, trace_depth_agrees, verdict_routes, live_hypotheses, directions_rule, view_rule, candidate_rule, contested_rule, CASES, native_case, project, trace_depth_answers, REPO_ROOT, EVERGIVEN, native_crossref, native_ablations, native_verdict, native_views

@dataclass(frozen=True)
class SummaryQuestion(Question):
    summaries: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = ()

def summary_warnings(question):
    return tuple((f'summary_number_not_in_quote:{node}' for node, summary, source in getattr(question, 'summaries', ()) if any((number not in source for number in summary))))

def summary_numbers_rule(state, question):
    expected = summary_warnings(question)
    if sorted(state.summary_warnings) != sorted(expected):
        return f'summary warnings {state.summary_warnings} != {expected} (one warning per node, literal source tokens)'
SUMMARY_CASES = (SummaryQuestion('summary_matching', (), summaries=(('E', ('7,000', '2021'), ('7,000', '2021')),)), SummaryQuestion('summary_drift', (), summaries=(('E_series', ('3,500', '3,500', '2021'), ('7,000', '2021')),)), SummaryQuestion('summary_literal', (), summaries=(('E_literal', ('7000',), ('7,000',)),)), SummaryQuestion('summary_quote_only', (), summaries=(('E_pretrend', ('2', '2020', '2021'), ('2020', '2021')), ('E_series', ('3,500', '2021'), ('7,000', '2021')))))

@dataclass(frozen=True)
class State:
    question: Question | None = None
    disagreements: tuple[tuple[str, str, str], ...] = ()
    live_hypotheses: tuple[str, ...] = ()
    contested: bool = False
    license: str = ''
    directions: tuple[tuple[str, str, str, str], ...] = ()
    summary_warnings: tuple[str, ...] = ()

def expected_Status(question, state, mutation=''):
    wrong = mutation
    disagreements = () if wrong == 'skip_route_comparison' else route_conflicts(question)
    live = tuple((row.id for row in question.hypotheses if wrong == 'excluded_hypothesis_stays_live' and row.experiment == 'eliminated' or not excluded(row)))
    contested = bool(disagreements) and wrong != 'disagreement_not_contested'
    license = 'assert' if wrong == 'verdict_upgrades_license' and question.root_license else question.root_license
    directions = tuple(sorted(((anchor, route, row.id, direction) for row in question.hypotheses for anchor, route, direction in row.anchors if not (wrong == 'logic_direction_dropped' and route == 'logic'))))
    if wrong == 'reference_only_row_gets_a_direction' and question.name == 'reference_only':
        directions += (('', 'logic', question.hypotheses[0].id, 'support'),)
    warnings = () if wrong == 'summary_number_drift_passes' else summary_warnings(question)
    result = State(question, disagreements, live, contested, license, directions, warnings)
    return result
RULES = (rule(routes_contradict), rule(verdict_routes), rule(live_hypotheses), rule(directions_rule), rule(contested_rule), rule(summary_numbers_rule))
MUTATIONS = {'skip_route_comparison': 'routes_do_not_contradict_silently', 'verdict_upgrades_license': 'verdict_matches_the_routes', 'excluded_hypothesis_stays_live': 'live_hypotheses_follow_route_exclusions', 'logic_direction_dropped': 'evidence_directions_match_routes', 'disagreement_not_contested': 'contested_iff_disagreement', 'reference_only_row_gets_a_direction': 'evidence_directions_match_routes', 'summary_number_drift_passes': 'summary_numbers_come_from_the_source'}

def assert_native_contract():
    from researchguard.research import load_research, research_status
    observations, violations = ([], [])

    def observe(label, actual, want=True, state=None):
        if actual != want:
            violations.append(f'{label}: {actual!r} != {want!r}')
    from researchguard.logic.minimal_sets import license_model_claim
    for kind, value in native_verdict().items():
        observe(kind, value)
    tree = load_research(EVERGIVEN)
    status = research_status(tree)
    native_license = license_model_claim(tree.models['logic'], tree.index['root_claim']).wording_license
    projected = project(status, native_license)
    state = State(projected.question, projected.disagreements, projected.live_hypotheses, projected.contested, projected.license, projected.directions, tuple((warning for warning in status['warnings'] if warning.startswith('summary_number_not_in_quote:'))))
    observe('native_license', state.license, native_license, state)
    numbers = native_summary_numbers()
    for label, native in numbers.items():
        warnings = tuple((warning for warning in native['warnings'] if warning.startswith('summary_number_not_in_quote:')))
        question = SUMMARY_CASES[0] if label == 'baseline' else SUMMARY_CASES[3] if label == 'quote_only' else SUMMARY_CASES[1]
        actual = State(question, summary_warnings=warnings)
        verdict = RULES[-1](actual)
        observe(f'{label} summary warnings', tuple(sorted(warnings)), tuple(sorted(summary_warnings(question))), actual)
        if not verdict:
            violations.append('independent contract rejected the native observation')
    observe('summary warning preserves verdict', numbers['C2']['verdict'], numbers['baseline']['verdict'])
    observe('summary warning preserves status keys', set(numbers['C2']), set(numbers['baseline']))
    for invariant in RULES:
        verdict = invariant(state)
        if not verdict:
            violations.append(f"evergiven: {invariant.__name__}: {'independent contract rejected the native observation'}")
    assert not violations, violations
RULE_NAMES = ('routes_do_not_contradict_silently', 'verdict_matches_the_routes', 'live_hypotheses_follow_route_exclusions', 'evidence_directions_match_routes', 'contested_iff_disagreement', 'summary_numbers_come_from_the_source')
