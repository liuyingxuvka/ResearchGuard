"""research_verdict: one independent aspect of the question status."""

from dataclasses import dataclass

from pathlib import Path

import sys

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow

from flowguard.explorer import Explorer

from _research_cases import (Hypothesis, Ablation, Question, excluded, accepted, unused, route_conflicts, rule, unknown_gap_hypotheses, consistent_tree, dangling_reference, unused_hypothesis, gap_hypotheses, copied_content, library_anchors, routes_contradict, every_ablation, trace_depth_agrees, verdict_routes, live_hypotheses, directions_rule, view_rule, candidate_rule, contested_rule, CASES, native_case, project, trace_depth_answers, REPO_ROOT, EVERGIVEN, native_crossref, native_ablations, native_verdict, native_views)

MODEL_ID = 'research_verdict'

PARENT = 'research-tree'

IMPLEMENTED_BY = {'Disagreements': 'src/researchguard/research.py:route_disagreements', 'Verdict': 'src/researchguard/research.py:verdict_for_writers', 'Directions': 'src/researchguard/research.py:evidence_directions'}

USES = {
    'LoadModelFromDict': 'src/researchguard/logic/loader.py:load_model_from_dict',
    'LoadResearch': 'src/researchguard/research.py:load_research',
    'ResearchStatus': 'src/researchguard/research.py:research_status',
    'BeliefStateFromDict': 'src/researchguard/source/schema.py:BeliefState.from_dict',
    'HypothesisEvidenceLinkFromDict': 'src/researchguard/trace/schema.py:HypothesisEvidenceLink.from_dict',
    'TraceGuardModelFromDict': 'src/researchguard/trace/schema.py:TraceGuardModel.from_dict',
}

TESTED_BY = {'routes_do_not_contradict_silently': ['tests/test_research_verdict.py:test_opposite_anchor_directions_are_a_disagreement', 'tests/test_research_verdict.py:test_ruled_out_and_accepted_is_a_disagreement'], 'verdict_matches_the_routes': ['tests/test_research_verdict.py:test_verdict_matches_each_route_and_page_is_readable'], 'live_hypotheses_follow_route_exclusions': ['tests/test_research_verdict.py:test_live_hypotheses_follow_every_route'], 'evidence_directions_match_routes': ['tests/test_research_verdict.py:test_evidence_directions_cover_both_routes', 'tests/test_research_verdict.py:test_writer_surface_keys_are_pinned', 'tests/test_research_verdict.py:test_reference_only_evidence_has_no_direction'], 'contested_iff_disagreement': ['tests/test_research_verdict.py:test_live_hypotheses_follow_every_route', 'tests/test_research_verdict.py:test_verdict_matches_each_route_and_page_is_readable']}

@dataclass(frozen=True)
class State:
    question: Question | None = None
    disagreements: tuple[tuple[str, str, str], ...] = ()
    live_hypotheses: tuple[str, ...] = ()
    contested: bool = False
    license: str = ''
    directions: tuple[tuple[str, str, str, str], ...] = ()

class Status:
    name = 'Status'
    reads = ('question',)
    writes = ('question', 'disagreements', 'live_hypotheses', 'contested', 'license', 'directions')
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
        result = State(question, disagreements, live, contested, license, directions)
        yield FunctionResult(result, result, label=question.name)


INVARIANTS = (
    Invariant('routes_do_not_contradict_silently', 'Direct route disagreements are reported.', rule(routes_contradict)),
    Invariant('verdict_matches_the_routes', 'The verdict license equals the native root license.', rule(verdict_routes)),
    Invariant('live_hypotheses_follow_route_exclusions', 'Live hypotheses are those no route excludes, in index order.', rule(live_hypotheses)),
    Invariant('evidence_directions_match_routes', 'Each evidence direction row matches its route model, logic included.', rule(directions_rule)),
    Invariant('contested_iff_disagreement', 'The verdict is contested exactly when routes disagree.', rule(contested_rule)),
)

MUTATIONS = {'skip_route_comparison': 'routes_do_not_contradict_silently', 'verdict_upgrades_license': 'verdict_matches_the_routes', 'excluded_hypothesis_stays_live': 'live_hypotheses_follow_route_exclusions', 'logic_direction_dropped': 'evidence_directions_match_routes', 'disagreement_not_contested': 'contested_iff_disagreement', 'reference_only_row_gets_a_direction': 'evidence_directions_match_routes'}

def explorer(step):
    return Explorer(Workflow((step,)), (State(),), CASES, INVARIANTS, progress_steps=0)

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
    state = State(projected.question, projected.disagreements, projected.live_hypotheses, projected.contested, projected.license, projected.directions)
    observe('native_license', state.license, native_license, state)

    for invariant in INVARIANTS:
        verdict = invariant.check(state, ())
        if not verdict.ok:
            violations.append(ConformanceViolation(step_index=1, rule_name='Status', message=f'evergiven: {invariant.name}: {verdict.message}'))

    return ConformanceReport(ok=not violations, violations=tuple(violations), replayed_steps=tuple(observations),
                             summary='verdict: real functions and all unchanged rules replayed on the live Ever Given status.')
