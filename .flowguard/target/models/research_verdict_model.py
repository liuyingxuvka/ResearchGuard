"""research_verdict: one independent aspect of the question status."""

from dataclasses import dataclass

from pathlib import Path

import sys

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow

from flowguard.explorer import Explorer

from _research_cases import native_summary_numbers

from _research_cases import (Hypothesis, Ablation, Question, excluded, accepted, unused, route_conflicts, rule, unknown_gap_hypotheses, consistent_tree, dangling_reference, unused_hypothesis, gap_hypotheses, copied_content, library_anchors, routes_contradict, every_ablation, trace_depth_agrees, verdict_routes, live_hypotheses, directions_rule, view_rule, candidate_rule, contested_rule, CASES, native_case, project, trace_depth_answers, REPO_ROOT, EVERGIVEN, native_crossref, native_ablations, native_verdict, native_views)

MODEL_ID = 'research_verdict'

PARENT = 'research-tree'

IMPLEMENTED_BY = {'Disagreements': 'src/researchguard/research.py:route_disagreements', 'Verdict': 'src/researchguard/research.py:verdict_for_writers', 'Directions': 'src/researchguard/research.py:evidence_directions', 'SummaryWarnings': 'src/researchguard/research.py:research_status'}

USES = {
    'LoadModelFromDict': 'src/researchguard/logic/loader.py:load_model_from_dict',
    'LoadResearch': 'src/researchguard/research.py:load_research',
    'ResearchStatus': 'src/researchguard/research.py:research_status',
    'BeliefStateFromDict': 'src/researchguard/source/schema.py:BeliefState.from_dict',
    'HypothesisEvidenceLinkFromDict': 'src/researchguard/trace/schema.py:HypothesisEvidenceLink.from_dict',
    'TraceGuardModelFromDict': 'src/researchguard/trace/schema.py:TraceGuardModel.from_dict',
}

TESTED_BY = {'routes_do_not_contradict_silently': ['tests/test_research_verdict.py:test_opposite_anchor_directions_are_a_disagreement', 'tests/test_research_verdict.py:test_ruled_out_and_accepted_is_a_disagreement'], 'verdict_matches_the_routes': ['tests/test_research_verdict.py:test_verdict_matches_each_route_and_page_is_readable'], 'live_hypotheses_follow_route_exclusions': ['tests/test_research_verdict.py:test_live_hypotheses_follow_every_route'], 'evidence_directions_match_routes': ['tests/test_research_verdict.py:test_evidence_directions_cover_both_routes', 'tests/test_research_verdict.py:test_writer_surface_keys_are_pinned', 'tests/test_research_verdict.py:test_reference_only_evidence_has_no_direction'], 'contested_iff_disagreement': ['tests/test_research_verdict.py:test_live_hypotheses_follow_every_route', 'tests/test_research_verdict.py:test_verdict_matches_each_route_and_page_is_readable'], 'summary_numbers_come_from_the_source': ['tests/test_research_verdict.py:test_summary_number_not_in_quote_warns']}

@dataclass(frozen=True)
class SummaryQuestion(Question):
    # Literal tokens from the summary and its own quotes/matched anchors, never converted values.
    summaries: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = ()

def summary_warnings(question):
    return tuple(f'summary_number_not_in_quote:{node}' for node, summary, source in getattr(question, 'summaries', ())
                 if any(number not in source for number in summary))

def summary_numbers_rule(state, question):
    expected = summary_warnings(question)
    if state.summary_warnings != expected:
        return f'summary warnings {state.summary_warnings} != {expected} (one warning per node, literal source tokens)'

SUMMARY_CASES = (
    SummaryQuestion('summary_matching', (), summaries=(('E', ('7,000', '2021'), ('7,000', '2021')),)),
    SummaryQuestion('summary_drift', (), summaries=(('E_series', ('3,500', '3,500', '2021'), ('7,000', '2021')),)),
    SummaryQuestion('summary_literal', (), summaries=(('E_literal', ('7000',), ('7,000',)),)),
)

@dataclass(frozen=True)
class State:
    question: Question | None = None
    disagreements: tuple[tuple[str, str, str], ...] = ()
    live_hypotheses: tuple[str, ...] = ()
    contested: bool = False
    license: str = ''
    directions: tuple[tuple[str, str, str, str], ...] = ()
    summary_warnings: tuple[str, ...] = ()

class Status:
    name = 'Status'
    reads = ('question',)
    writes = ('question', 'disagreements', 'live_hypotheses', 'contested', 'license', 'directions', 'summary_warnings')
    mutation = ''

    def apply(self, question, state):
        wrong = self.mutation
        disagreements = () if wrong == 'skip_route_comparison' else route_conflicts(question)
        live = tuple(row.id for row in question.hypotheses
                     if wrong == 'excluded_hypothesis_stays_live' and row.experiment == 'eliminated' or not excluded(row))
        contested = bool(disagreements) and wrong != 'disagreement_not_contested'
        license = 'assert' if wrong == 'verdict_upgrades_license' and question.root_license else question.root_license
        directions = tuple(sorted((anchor, route, row.id, direction) for row in question.hypotheses for anchor, route, direction in row.anchors
                                  if not (wrong == 'logic_direction_dropped' and route == 'logic')))
        if wrong == 'reference_only_row_gets_a_direction' and question.name == 'reference_only':
            directions += (('', 'logic', question.hypotheses[0].id, 'support'),)
        warnings = () if wrong == 'summary_number_drift_passes' else summary_warnings(question)
        result = State(question, disagreements, live, contested, license, directions, warnings)
        yield FunctionResult(result, result, label=question.name)


INVARIANTS = (
    Invariant('routes_do_not_contradict_silently', 'Direct route disagreements are reported.', rule(routes_contradict)),
    Invariant('verdict_matches_the_routes', 'The verdict license equals the native root license.', rule(verdict_routes)),
    Invariant('live_hypotheses_follow_route_exclusions', 'Live hypotheses are those no route excludes, in index order.', rule(live_hypotheses)),
    Invariant('evidence_directions_match_routes', 'Each evidence direction row matches its route model, logic included.', rule(directions_rule)),
    Invariant('contested_iff_disagreement', 'The verdict is contested exactly when routes disagree.', rule(contested_rule)),
    Invariant('summary_numbers_come_from_the_source', 'A literal number absent from the evidence quote and matched anchor is warned once per node.', rule(summary_numbers_rule)),
)

MUTATIONS = {'skip_route_comparison': 'routes_do_not_contradict_silently', 'verdict_upgrades_license': 'verdict_matches_the_routes', 'excluded_hypothesis_stays_live': 'live_hypotheses_follow_route_exclusions', 'logic_direction_dropped': 'evidence_directions_match_routes', 'disagreement_not_contested': 'contested_iff_disagreement', 'reference_only_row_gets_a_direction': 'evidence_directions_match_routes', 'summary_number_drift_passes': 'summary_numbers_come_from_the_source'}

def explorer(step):
    return Explorer(Workflow((step,)), (State(),), CASES + SUMMARY_CASES, INVARIANTS, progress_steps=0)

def build_explorer():
    return explorer(Status())

def broken_variants():
    result = {}
    for name in MUTATIONS:
        step = Status()
        step.mutation = name
        result[name] = explorer(step)
    return result

def conformance():
    sys.path.insert(0, str(REPO_ROOT / 'src'))
    from flowguard.conformance import ConformanceReport, ConformanceViolation
    from flowguard.replay import ReplayObservation
    from researchguard.research import load_research, research_status
    observations, violations = [], []
    def observe(label, actual, want=True, state=None):
        observations.append(ReplayObservation('Status', actual, state or State()))
        if actual != want:
            violations.append(ConformanceViolation(step_index=1, rule_name='Status', message=f'{label}: {actual!r} != {want!r}'))
    from researchguard.logic.minimal_sets import license_model_claim
    for kind, value in native_verdict().items(): observe(kind, value)
    tree = load_research(EVERGIVEN)
    status = research_status(tree)
    native_license = license_model_claim(tree.models['logic'], tree.index['root_claim']).wording_license
    projected = project(status, native_license)
    state = State(projected.question, projected.disagreements, projected.live_hypotheses, projected.contested, projected.license, projected.directions,
                  tuple(warning for warning in status['warnings'] if warning.startswith('summary_number_not_in_quote:')))
    observe('native_license', state.license, native_license, state)
    numbers = native_summary_numbers()
    for label, native in numbers.items():
        warnings = tuple(warning for warning in native['warnings'] if warning.startswith('summary_number_not_in_quote:'))
        question = SUMMARY_CASES[0] if label == 'baseline' else SUMMARY_CASES[1]
        actual = State(question, summary_warnings=warnings)
        verdict = INVARIANTS[-1].check(actual, ())
        observe(f'{label} summary warnings', warnings, summary_warnings(question), actual)
        if not verdict.ok:
            violations.append(ConformanceViolation(step_index=1, rule_name='summary_numbers_come_from_the_source', message=verdict.message))
    observe('summary warning preserves verdict', numbers['C2']['verdict'], numbers['baseline']['verdict'])
    observe('summary warning preserves status keys', set(numbers['C2']), set(numbers['baseline']))

    for invariant in INVARIANTS:
        verdict = invariant.check(state, ())
        if not verdict.ok:
            violations.append(ConformanceViolation(step_index=1, rule_name='Status', message=f'evergiven: {invariant.name}: {verdict.message}'))

    return ConformanceReport(ok=not violations, violations=tuple(violations), replayed_steps=tuple(observations),
                             summary='verdict: real functions and all unchanged rules replayed on the live Ever Given status.')
