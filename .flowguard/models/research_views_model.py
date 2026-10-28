"""research_views: one independent aspect of the question status."""

from dataclasses import dataclass

from pathlib import Path

import sys

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow

from flowguard.explorer import Explorer

from _research_cases import (Hypothesis, Ablation, Question, excluded, accepted, unused, route_conflicts, rule, unknown_gap_hypotheses, consistent_tree, dangling_reference, unused_hypothesis, gap_hypotheses, copied_content, library_anchors, routes_contradict, every_ablation, trace_depth_agrees, verdict_routes, live_hypotheses, directions_rule, view_rule, candidate_rule, contested_rule, CASES, native_case, project, trace_depth_answers, REPO_ROOT, EVERGIVEN, native_crossref, native_ablations, native_verdict, native_views)

MODEL_ID = 'research_views'

PARENT = 'research-tree'

IMPLEMENTED_BY = {'HypothesisView': 'src/researchguard/research.py:hypothesis_view', 'Compare': 'src/researchguard/research.py:compare_research_status'}

USES = {}

TESTED_BY = {'hypothesis_view_matches_status': ['tests/test_research_views.py:test_hypothesis_view_lists_its_rows'], 'candidate_view_shows_verdict_changes': ['tests/test_research_views.py:test_candidate_view_shows_verdict_changes']}

@dataclass(frozen=True)
class State:
    question: Question | None = None
    gap_rows: tuple[tuple[str, tuple[str, ...]], ...] = ()
    next_rows: tuple[tuple[str, tuple[str, ...]], ...] = ()
    views: tuple[tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...] = ()
    changes: tuple[tuple[str, str], ...] = ()

class Status:
    name = 'Status'
    reads = ('question',)
    writes = ('question', 'gap_rows', 'next_rows', 'views', 'changes')
    mutation = ''

    def apply(self, question, state):
        wrong = self.mutation
        names = dict(question.gap_hypotheses)
        gap_rows = tuple(question.gap_hypotheses)
        next_rows = tuple((action, names.get(gap, ())) for action, gap in question.searches)
        views = tuple((row.id,
                       () if wrong == 'hypothesis_view_drops_gaps' else tuple(gap for gap, named in gap_rows if row.id in named),
                       tuple(action for action, named in next_rows if row.id in named),
                       tuple(item.id for item in question.ablations if item.hypothesis == row.id))
                      for row in question.hypotheses)
        changes = () if wrong == 'candidate_ignores_verdict' else tuple(('verdict', key) for key in question.candidate_verdict_changes)
        result = State(question, gap_rows, next_rows, views, changes)
        yield FunctionResult(result, result, label=question.name)


INVARIANTS = (
    Invariant('hypothesis_view_matches_status', 'One hypothesis view lists exactly the gaps, next searches and ablations that name it.', rule(view_rule)),
    Invariant('candidate_view_shows_verdict_changes', 'Every verdict key that differs in the candidate has a change row.', rule(candidate_rule)),
)

MUTATIONS = {'candidate_ignores_verdict': 'candidate_view_shows_verdict_changes', 'hypothesis_view_drops_gaps': 'hypothesis_view_matches_status'}

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
    from researchguard.research import hypothesis_view
    tree = load_research(EVERGIVEN)
    status = research_status(tree)
    for kind, value in native_views(status).items(): observe(kind, value)
    views = []
    for row in status['hypotheses']:
        item = hypothesis_view(status, row['id'])
        views.append((row['id'], tuple(x['id'] for x in item['open_gaps']), tuple(x['id'] for x in item['next'] if x['route'] == 'search'),
                      tuple(x['id'] for x in item['ablations'] if x['hypothesis'] == row['id'])))
    projected = project(status, '', views=views)
    state = State(projected.question, projected.gap_rows, projected.next_rows, projected.views, projected.changes)
    observe('native_hypotheses', len(state.views), len(status['hypotheses']), state)

    for invariant in INVARIANTS:
        verdict = invariant.check(state, ())
        if not verdict.ok:
            violations.append(ConformanceViolation(step_index=1, rule_name='Status', message=f'evergiven: {invariant.name}: {verdict.message}'))

    return ConformanceReport(ok=not violations, violations=tuple(violations), replayed_steps=tuple(observations),
                             summary='views: real functions and all unchanged rules replayed on the live Ever Given status.')
