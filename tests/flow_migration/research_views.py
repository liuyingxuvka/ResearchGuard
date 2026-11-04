"""research_views: one independent aspect of the question status."""
from dataclasses import dataclass
from pathlib import Path
import sys
from ._research_cases import native_sync
from ._research_cases import Hypothesis, Ablation, Question, excluded, accepted, unused, route_conflicts, rule, unknown_gap_hypotheses, consistent_tree, dangling_reference, unused_hypothesis, gap_hypotheses, copied_content, library_anchors, routes_contradict, every_ablation, trace_depth_agrees, verdict_routes, live_hypotheses, directions_rule, view_rule, candidate_rule, contested_rule, CASES, native_case, project, trace_depth_answers, REPO_ROOT, EVERGIVEN, native_crossref, native_ablations, native_verdict, native_views

@dataclass(frozen=True)
class SyncQuestion(Question):
    new_anchor: str = ''
    new_source: str = ''
    conflict: bool = False
    unverifiable: bool = False

def _sync_changes(question):
    if not question.new_anchor or question.conflict:
        return ()
    warned = (('warnings', f'unverifiable_source:{question.new_source}'),) if question.new_source and question.unverifiable else ()
    return ((('source', question.new_source),) if question.new_source else ()) + (('evidence', question.new_anchor),) + warned

def sync_rule(state, question):
    if isinstance(question, SyncQuestion):
        want = _sync_changes(question)
        if state.changes != want:
            return f'sync changed {state.changes}, expected only {want}'

@dataclass(frozen=True)
class State:
    question: Question | None = None
    gap_rows: tuple[tuple[str, tuple[str, ...]], ...] = ()
    next_rows: tuple[tuple[str, tuple[str, ...]], ...] = ()
    views: tuple[tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...] = ()
    changes: tuple[tuple[str, str], ...] = ()

def expected_Status(question, state, mutation=''):
    wrong = mutation
    names = dict(question.gap_hypotheses)
    gap_rows = tuple(question.gap_hypotheses)
    next_rows = tuple(((action, names.get(gap, ())) for action, gap in question.searches))
    views = tuple(((row.id, () if wrong == 'hypothesis_view_drops_gaps' else tuple((gap for gap, named in gap_rows if row.id in named)), tuple((action for action, named in next_rows if row.id in named)), tuple((item.id for item in question.ablations if item.hypothesis == row.id))) for row in question.hypotheses))
    changes = () if wrong == 'candidate_ignores_verdict' else tuple((('verdict', key) for key in question.candidate_verdict_changes))
    if isinstance(question, SyncQuestion):
        changes = _sync_changes(question)
        if wrong == 'sync_rewrites_unrelated_logic':
            changes += (('verdict', 'root_claim.reason'),)
        if wrong == 'candidate_hides_unverifiable_source':
            changes = tuple((row for row in changes if row[0] != 'warnings'))
    result = State(question, gap_rows, next_rows, views, changes)
    return result
RULES = (rule(view_rule), rule(candidate_rule), rule(sync_rule))
MUTATIONS = {'candidate_ignores_verdict': 'candidate_view_shows_verdict_changes', 'hypothesis_view_drops_gaps': 'hypothesis_view_matches_status', 'sync_rewrites_unrelated_logic': 'sync_changes_only_the_new_anchor', 'candidate_hides_unverifiable_source': 'sync_changes_only_the_new_anchor'}

def assert_native_contract():
    from researchguard.research import load_research, research_status
    observations, violations = ([], [])

    def observe(label, actual, want=True, state=None):
        if actual != want:
            violations.append(f'{label}: {actual!r} != {want!r}')
    from researchguard.research import hypothesis_view
    tree = load_research(EVERGIVEN)
    status = research_status(tree)
    for kind, value in native_views(status).items():
        observe(kind, value)
    for label, row in native_sync().items():
        question = SyncQuestion(label, (), new_anchor=row['new_anchor'], new_source=row['new_source'], conflict=row['conflict'], unverifiable=row['unverifiable'])
        actual = State(question, changes=tuple(((change['kind'], change['id'].split(' ', 1)[0]) for change in row['changes'])))
        want_exit = 1 if question.conflict else 0
        observe(f"sync {label}: exit {(row['output'] if row['exit'] != want_exit else '')}", row['exit'], want_exit, actual)
        observe(f'sync {label}: preserved bytes', row['preserved'], True, actual)
        want_changes = [(kind, identifier, 'added') for kind, identifier in _sync_changes(question)]
        observe(f'sync {label}: candidate changes', [(change['kind'], change['id'].split(' ', 1)[0], change.get('change')) for change in row['changes']], want_changes, actual)
        verdict = RULES[-1](actual)
        if not verdict:
            violations.append('independent contract rejected the native observation')
    views = []
    for row in status['hypotheses']:
        item = hypothesis_view(status, row['id'])
        views.append((row['id'], tuple((x['id'] for x in item['open_gaps'])), tuple((x['id'] for x in item['next'] if x['route'] == 'search')), tuple((x['id'] for x in item['ablations'] if x['hypothesis'] == row['id']))))
    projected = project(status, '', views=views)
    state = State(projected.question, projected.gap_rows, projected.next_rows, projected.views, projected.changes)
    observe('native_hypotheses', len(state.views), len(status['hypotheses']), state)
    for invariant in RULES:
        verdict = invariant(state)
        if not verdict:
            violations.append(f"evergiven: {invariant.__name__}: {'independent contract rejected the native observation'}")
    assert not violations, violations
RULE_NAMES = ('hypothesis_view_matches_status', 'candidate_view_shows_verdict_changes', 'sync_changes_only_the_new_anchor')
