"""One research question: per-hypothesis route states and the question-level outputs that status derives from them."""
from dataclasses import dataclass
from pathlib import Path
import sys

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer

MODEL_ID = 'research_tree_crossref'
PARENT = 'research-tree'
COMPONENTS = ['research-tree', 'researchguard-suite', 'sourceguard', 'logic-argument']
IMPLEMENTED_BY = {'Check': 'src/researchguard/research.py:check_research_tree',
 'Status': 'src/researchguard/research.py:status_main',
 'Disagreements': 'src/researchguard/research.py:route_disagreements',
 'Ablations': 'src/researchguard/research.py:apply_ablations',
 'Verdict': 'src/researchguard/research.py:verdict_for_writers',
 'Directions': 'src/researchguard/research.py:evidence_directions',
 'HypothesisView': 'src/researchguard/research.py:hypothesis_view',
 'Compare': 'src/researchguard/research.py:compare_research_status'}
TESTED_BY = {'dangling_reference_is_an_error': ['tests/test_research_tree.py:test_dangling_references_and_invalid_native_models_are_errors',
                                                'tests/test_research_tree.py:test_missing_index_exits_2',
                                                'tests/test_research_tree.py:test_missing_index_names_the_template'],
 'consistent_tree_has_no_error': ['tests/test_research_tree.py:test_consistent_tree_has_no_errors',
                                  'tests/test_research_tree.py:test_checker_is_in_memory_and_source_is_optional',
                                  'tests/test_research_tree.py:test_shipped_evergiven_tree_has_consistent_shared_ids',
                                  'tests/test_research_tree.py:test_candidate_view_lists_only_changes'],
 'unused_hypothesis_is_only_a_warning': ['tests/test_research_tree.py:test_unused_hypothesis_is_only_a_warning'],
 'copied_content_matches_owner': ['tests/test_research_tree.py:test_copy_drift_is_an_error_for_each_copied_field',
                                  'tests/test_research_tree.py:test_one_observation_reaches_trace_and_logic_by_sync'],
 'library_anchors_are_resolved': ['tests/test_research_tree.py:test_library_anchored_evidence_gets_one_answer'],
 'routes_do_not_contradict_silently': ['tests/test_research_tree.py:test_opposite_anchor_directions_are_a_disagreement',
                                       'tests/test_research_tree.py:test_ruled_out_and_accepted_is_a_disagreement'],
 'every_ablation_is_caught_or_named': ['tests/test_research_tree.py:test_ablation_nobody_uses_is_named'],
 'verdict_matches_the_routes': ['tests/test_research_tree.py:test_verdict_matches_each_route_and_page_is_readable'],
 'live_hypotheses_follow_route_exclusions': ['tests/test_research_tree.py:test_live_hypotheses_follow_every_route'],
 'ablation_agrees_with_trace_depth': ['tests/test_research_tree.py:test_trace_ablation_agrees_with_trace_depth',
                                      'tests/test_research_tree.py:test_ablation_rows_name_side_effects'],
 'gap_names_known_hypotheses': ['tests/test_research_tree.py:test_gap_hypotheses_are_checked_and_grouped'],
 'evidence_directions_match_routes': ['tests/test_research_tree.py:test_evidence_directions_cover_both_routes',
                                      'tests/test_research_tree.py:test_writer_surface_keys_are_pinned'],
 'hypothesis_view_matches_status': ['tests/test_research_tree.py:test_hypothesis_view_lists_its_rows'],
 'candidate_view_shows_verdict_changes': ['tests/test_research_tree.py:test_candidate_view_shows_verdict_changes'],
 'contested_iff_disagreement': ['tests/test_research_tree.py:test_live_hypotheses_follow_every_route',
                                'tests/test_research_tree.py:test_verdict_matches_each_route_and_page_is_readable']}


@dataclass(frozen=True)
class Hypothesis:
    """One hypothesis row: its state in each route and the anchors each route reads for it."""
    id: str
    logic: str | None = None          # IN / OUT / UNDECIDED, None when the logic route does not list it
    trace_live: bool | None = None    # None when the trace route does not list it
    experiment: str | None = None     # consistent / eliminated / underdetermined / None
    anchors: tuple[tuple[str, str, str], ...] = ()   # direct evidence: (anchor, route, support|oppose|limit)


@dataclass(frozen=True)
class Ablation:
    """A declared anchor ablation: whether logic moved, and TraceGuard's own expected-sensitivity answer."""
    id: str
    hypothesis: str
    logic_moved: bool = False
    trace_check: bool = False          # TraceGuard's expected-sensitivity check (trace's own threshold; 0 for question rows)
    declared_by_trace: bool = False    # the ablation and its expected sensitivity are declared in trace.yaml
    projection_moved: bool | None = None   # a second measure (projection support difference); None = same as trace_check

    def second_measure(self):
        return self.trace_check if self.projection_moved is None else self.projection_moved


@dataclass(frozen=True)
class Question:
    """The inputs status reads: hypothesis rows, references, copies, ablations and the root claim."""
    name: str
    hypotheses: tuple[Hypothesis, ...]
    dangling: tuple[str, ...] = ()           # problem codes of references to missing anchors or sources
    drifted: tuple[str, ...] = ()            # problem codes of copied fields that differ from their owner
    library_anchors: tuple[str, ...] = ()    # anchors that resolve only through the source library
    ablations: tuple[Ablation, ...] = ()
    gap_hypotheses: tuple[tuple[str, tuple[str, ...]], ...] = ()   # (source gap id, hypothesis ids it names)
    searches: tuple[tuple[str, str], ...] = ()   # (next search action id, the gap it targets)
    candidate_verdict_changes: tuple[str, ...] = ()   # verdict keys whose value differs in a candidate folder
    root_license: str = ''                   # native wording license of the root claim


@dataclass(frozen=True)
class State:
    question: Question | None = None
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    disagreements: tuple[tuple[str, str, str], ...] = ()   # (hypothesis, kind, detail)
    ablations: tuple[tuple[str, tuple[str, ...]], ...] = ()  # (id, caught_by)
    live_hypotheses: tuple[str, ...] = ()
    contested: bool = False
    license: str = ''
    directions: tuple[tuple[str, str, str, str], ...] = ()   # evidence rows: (anchor, route, hypothesis, direction)
    gap_rows: tuple[tuple[str, tuple[str, ...]], ...] = ()   # open source gaps with the hypotheses they name
    next_rows: tuple[tuple[str, tuple[str, ...]], ...] = ()  # next searches with the hypotheses they would move
    views: tuple[tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...] = ()  # (hypothesis, gaps, next, ablations)
    changes: tuple[tuple[str, str], ...] = ()   # candidate comparison rows: (kind, id)


def excluded(row):
    return row.logic == 'OUT' or row.trace_live is False or row.experiment == 'eliminated'


def accepted(row):
    return row.logic == 'IN' or row.trace_live is True


def unused(row):
    return row.logic is None and row.trace_live is None and row.experiment is None


def route_conflicts(question):
    """Direct opposite anchor directions, and a hypothesis accepted by one route and excluded by another."""
    rows = []
    for row in question.hypotheses:
        seen = {}
        for anchor, route, direction in row.anchors:
            if direction == 'limit':
                continue
            seen.setdefault(anchor, {}).setdefault(route, set()).add(direction)
        for anchor, routes in sorted(seen.items()):
            if {frozenset(routes.get('trace', ())), frozenset(routes.get('logic', ()))} == {frozenset({'support'}), frozenset({'oppose'})}:
                rows.append((row.id, 'anchor', anchor))
        if accepted(row) and excluded(row):
            rows.append((row.id, 'status', ''))
    return tuple(rows)


class Status:
    """status: check references and copies, compare routes, run ablations and project the verdict."""
    name = 'Status'
    reads = ('question',)
    writes = ('errors', 'warnings', 'disagreements', 'ablations', 'live_hypotheses', 'contested', 'license')
    mutation = ''

    def apply(self, question, state):
        wrong = self.mutation
        errors = [code for code in question.dangling
                  if not (wrong == 'ignore_trace' and ':trace:' in code) and not (wrong == 'ignore_logic' and ':logic:' in code)]
        if wrong != 'ignore_copy_drift':
            errors.extend(question.drifted)
        if wrong == 'status_ignores_library':
            errors.extend(f'dangling_anchor:logic:{anchor}' for anchor in question.library_anchors)
        known = {row.id for row in question.hypotheses}
        if wrong != 'dangling_gap_hypothesis_accepted':
            errors.extend(f'unknown_hypothesis:source:{gap}:{name}' for gap, names in question.gap_hypotheses for name in names if name not in known)
        if wrong == 'consistent_as_error' and not errors:
            errors.append('invented_error')
        warnings = []
        for row in question.hypotheses:
            if unused(row):
                (errors if wrong == 'warning_as_error' else warnings).append(f'hypothesis_unused:{row.id}')
        disagreements = () if wrong == 'skip_route_comparison' else route_conflicts(question)
        warnings.extend(f'route_disagreement:{h}:{kind}:{detail}' for h, kind, detail in disagreements)
        ablations = []
        for row in question.ablations:
            trace = row.second_measure() if wrong == 'ablation_uses_a_second_sensitivity' else row.trace_check
            caught = tuple(route for route, moved in (('logic', row.logic_moved), ('trace', trace)) if moved)
            if not (wrong == 'drop_uncaught_ablations' and not caught):
                ablations.append((row.id, caught))
        ablations = tuple(ablations)
        warnings.extend(f'ablation_not_caught:{name}' for name, caught in ablations if not caught)
        live = tuple(row.id for row in question.hypotheses
                     if wrong == 'excluded_hypothesis_stays_live' and row.experiment == 'eliminated' or not excluded(row))
        contested = bool(disagreements) and wrong != 'disagreement_not_contested'
        license = 'assert' if wrong == 'verdict_upgrades_license' and question.root_license else question.root_license
        directions = tuple(sorted((anchor, route, row.id, direction) for row in question.hypotheses for anchor, route, direction in row.anchors
                                  if not (wrong == 'logic_direction_dropped' and route == 'logic')))
        names = dict(question.gap_hypotheses)
        gap_rows = tuple(question.gap_hypotheses)
        next_rows = tuple((action, names.get(gap, ())) for action, gap in question.searches)
        views = tuple((row.id,
                       () if wrong == 'hypothesis_view_drops_gaps' else tuple(gap for gap, named in gap_rows if row.id in named),
                       tuple(action for action, named in next_rows if row.id in named),
                       tuple(item.id for item in question.ablations if item.hypothesis == row.id))
                      for row in question.hypotheses)
        changes = () if wrong == 'candidate_ignores_verdict' else tuple(('verdict', key) for key in question.candidate_verdict_changes)
        result = State(question, tuple(sorted(set(errors))), tuple(sorted(set(warnings))), disagreements, ablations, live, contested, license,
                       directions, gap_rows, next_rows, views, changes)
        yield FunctionResult(result, result, label=question.name)


def rule(check):
    def invariant(state, trace):
        if state.question is None:
            return InvariantResult.pass_()
        problem = check(state, state.question)
        return InvariantResult.fail(problem) if problem else InvariantResult.pass_()
    return invariant


def unknown_gap_hypotheses(question):
    known = {row.id for row in question.hypotheses}
    return [f'unknown_hypothesis:source:{gap}:{name}' for gap, names in question.gap_hypotheses for name in names if name not in known]


def consistent_tree(state, question):
    if not question.dangling and not question.drifted and not unknown_gap_hypotheses(question) and state.errors:
        return f'consistent tree received errors {state.errors}'


def dangling_reference(state, question):
    missing = [code for code in question.dangling if code not in state.errors]
    return f'dangling references were not errors: {missing}' if missing else None


def unused_hypothesis(state, question):
    for row in question.hypotheses:
        if unused(row) and (f'hypothesis_unused:{row.id}' not in state.warnings or any(row.id in code for code in state.errors)):
            return f'unused hypothesis {row.id} must only warn'


def gap_hypotheses(state, question):
    missing = [code for code in unknown_gap_hypotheses(question) if code not in state.errors]
    return f'gaps name unknown hypotheses without an error: {missing}' if missing else None


def copied_content(state, question):
    missing = [code for code in question.drifted if code not in state.errors]
    return f'copy drift was not an error: {missing}' if missing else None


def library_anchors(state, question):
    wrong = [code for code in state.errors for anchor in question.library_anchors if code.endswith(f':{anchor}')]
    return f'library-resolved anchors reported as dangling: {wrong}' if wrong else None


def routes_contradict(state, question):
    silent = [row for row in route_conflicts(question) if row not in state.disagreements]
    return f'route disagreements not reported: {silent}' if silent else None


def every_ablation(state, question):
    rows = dict(state.ablations)
    for row in question.ablations:
        if row.id not in rows:
            return f'ablation {row.id} has no row'
        if not rows[row.id] and f'ablation_not_caught:{row.id}' not in state.warnings:
            return f'uncaught ablation {row.id} is not named'


def trace_depth_agrees(state, question):
    rows = dict(state.ablations)
    for row in question.ablations:
        if row.declared_by_trace and row.id in rows and ('trace' in rows[row.id]) != row.trace_check:
            return f'ablation {row.id}: trace in caught_by is {"trace" in rows[row.id]} but trace depth says {row.trace_check}'


def verdict_routes(state, question):
    if state.license != question.root_license:
        return f'verdict license {state.license!r} differs from the native license {question.root_license!r}'


def live_hypotheses(state, question):
    want = tuple(row.id for row in question.hypotheses if not excluded(row))
    if state.live_hypotheses != want:
        return f'live_hypotheses {state.live_hypotheses} != {want} (index order, no route excludes them)'


def directions_rule(state, question):
    want = {(anchor, route, row.id, direction) for row in question.hypotheses for anchor, route, direction in row.anchors}
    if question.name != 'native' and set(state.directions) != want:
        return f'evidence directions {sorted(set(state.directions) ^ want)} differ from the route models'
    bad = [row for row in state.directions if row[3] not in ('support', 'oppose', 'limit')]
    if bad:
        return f'unknown directions {bad}'


def view_rule(state, question):
    for hypothesis, gaps, actions, ablations in state.views:
        want = (tuple(gap for gap, named in state.gap_rows if hypothesis in named),
                tuple(action for action, named in state.next_rows if hypothesis in named),
                tuple(item.id for item in question.ablations if item.hypothesis == hypothesis))
        if (gaps, actions, ablations) != want:
            return f'view of {hypothesis} lists {(gaps, actions, ablations)}, the full status names it in {want}'


def candidate_rule(state, question):
    missing = [key for key in question.candidate_verdict_changes if ('verdict', key) not in state.changes]
    return f'candidate view hides verdict changes {missing}' if missing else None


def contested_rule(state, question):
    if state.contested != bool(state.disagreements):
        return f'contested={state.contested} with {len(state.disagreements)} disagreement(s)'


INVARIANTS = (
    Invariant('consistent_tree_has_no_error', 'A tree without dangling references or drift has no error.', rule(consistent_tree)),
    Invariant('dangling_reference_is_an_error', 'Every dangling reference is an error.', rule(dangling_reference)),
    Invariant('unused_hypothesis_is_only_a_warning', 'A hypothesis no route uses only warns.', rule(unused_hypothesis)),
    Invariant('gap_names_known_hypotheses', 'A source gap may name only hypotheses of the question.', rule(gap_hypotheses)),
    Invariant('copied_content_matches_owner', 'Copied values that differ from their SourceGuard owner are errors.', rule(copied_content)),
    Invariant('library_anchors_are_resolved', 'Anchors resolved through the source library are not dangling.', rule(library_anchors)),
    Invariant('routes_do_not_contradict_silently', 'Direct route disagreements are reported.', rule(routes_contradict)),
    Invariant('every_ablation_is_caught_or_named', 'Every declared ablation has a row and uncaught ones are named.', rule(every_ablation)),
    Invariant('ablation_agrees_with_trace_depth', 'A trace-declared ablation is caught by trace exactly when trace depth passes its expected sensitivity.', rule(trace_depth_agrees)),
    Invariant('verdict_matches_the_routes', 'The verdict license equals the native root license.', rule(verdict_routes)),
    Invariant('live_hypotheses_follow_route_exclusions', 'Live hypotheses are those no route excludes, in index order.', rule(live_hypotheses)),
    Invariant('evidence_directions_match_routes', 'Each evidence direction row matches its route model, logic included.', rule(directions_rule)),
    Invariant('hypothesis_view_matches_status', 'One hypothesis view lists exactly the gaps, next searches and ablations that name it.', rule(view_rule)),
    Invariant('candidate_view_shows_verdict_changes', 'Every verdict key that differs in the candidate has a change row.', rule(candidate_rule)),
    Invariant('contested_iff_disagreement', 'The verdict is contested exactly when routes disagree.', rule(contested_rule)),
)

H = Hypothesis
CASES = (
    Question('consistent', (H('h', 'UNDECIDED', True, 'consistent', (('a', 'trace', 'support'), ('a', 'logic', 'support'))),), root_license='withhold'),
    Question('trace', (H('h', None, True),), dangling=('dangling_anchor:trace:a',)),
    Question('logic', (H('h', 'UNDECIDED', True),), dangling=('dangling_anchor:logic:E:missing (source s)',), root_license='withhold'),
    Question('unused', (H('h', 'UNDECIDED', True), H('unused'))),
    Question('gaps', (H('h', 'UNDECIDED', True), H('h_alt')), gap_hypotheses=(('g_alt', ('h_alt',)), ('g_bad', ('h_missing',)))),
    Question('readback', (H('h_suez', 'UNDECIDED', False, None, (('anc-unctad-surge', 'trace', 'oppose'), ('anc-sca', 'logic', 'support'))),
                          H('h_demand', 'UNDECIDED', True, None, (('anc-unctad-surge', 'trace', 'support'), ('anc-unctad-surge', 'logic', 'support'),
                                                                  ('anc-limits', 'logic', 'limit'))),
                          H('h_yantian')),
             gap_hypotheses=(('gap-alt-yantian', ('h_yantian',)), ('gap-pre-trend', ('h_suez', 'h_demand'))),
             searches=(('act-yantian', 'gap-alt-yantian'), ('act-pre-trend', 'gap-pre-trend')),
             ablations=(Ablation('abl_no_unctad', 'h_demand', logic_moved=True),)),
    Question('candidate', (H('h_suez', 'UNDECIDED', False),), root_license='withhold',
             candidate_verdict_changes=('root_claim.reason', 'live_hypotheses')),
    Question('drift', (H('h', 'UNDECIDED', True),), drifted=('copy_drift:trace:a:raw_text',)),
    Question('library', (H('h', 'UNDECIDED'),), library_anchors=('n1',)),
    Question('anchor_disagreement', (H('h', 'UNDECIDED', True, None, (('a', 'trace', 'support'), ('a', 'logic', 'oppose'))),)),
    Question('status_disagreement', (H('h', 'IN', False, 'consistent'),), root_license='assert'),
    Question('ablation', (H('h', 'UNDECIDED', True),), ablations=(Ablation('caught', 'h', logic_moved=True), Ablation('unused', 'h'))),
    Question('trace_ablation', (H('h_demand', 'UNDECIDED', True), H('h_suez', 'UNDECIDED', False)), ablations=(
        Ablation('abl_no_unctad', 'h_demand', logic_moved=True, trace_check=True, declared_by_trace=True, projection_moved=False),
        Ablation('question_without_unctad', 'h_demand', logic_moved=True, trace_check=True, projection_moved=True))),
    Question('exclusions', (H('h_out', 'OUT', True), H('h_dead', 'UNDECIDED', False), H('h_gone', 'UNDECIDED', True, 'eliminated'),
                            H('h_live', 'UNDECIDED', True, 'consistent')), root_license='qualify'),
)

# Each known-bad variant is one step of status done wrong; every one must break a rule.
MUTATIONS = {
    'ignore_trace': 'dangling_reference_is_an_error',
    'ignore_logic': 'dangling_reference_is_an_error',
    'consistent_as_error': 'consistent_tree_has_no_error',
    'warning_as_error': 'unused_hypothesis_is_only_a_warning',
    'ignore_copy_drift': 'copied_content_matches_owner',
    'dangling_gap_hypothesis_accepted': 'gap_names_known_hypotheses',
    'status_ignores_library': 'library_anchors_are_resolved',
    'skip_route_comparison': 'routes_do_not_contradict_silently',
    'drop_uncaught_ablations': 'every_ablation_is_caught_or_named',
    'verdict_upgrades_license': 'verdict_matches_the_routes',
    'ablation_uses_a_second_sensitivity': 'ablation_agrees_with_trace_depth',
    'excluded_hypothesis_stays_live': 'live_hypotheses_follow_route_exclusions',
    'logic_direction_dropped': 'evidence_directions_match_routes',
    'candidate_ignores_verdict': 'candidate_view_shows_verdict_changes',
    'hypothesis_view_drops_gaps': 'hypothesis_view_matches_status',
    'disagreement_not_contested': 'contested_iff_disagreement',
}


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


def native_case(kind):
    from researchguard.source.schema import BeliefState
    from researchguard.trace.schema import TraceGuardModel
    from researchguard.logic.loader import load_model_from_dict
    source = BeliefState.from_dict({'sources': [{'source_id': 's'}], 'anchors': [
        {'anchor_id': 'a', 'source_id': 's', 'text': 'Observed text'}] if kind != 'trace' else []})
    trace = TraceGuardModel.from_dict({'metadata': {'schema_version': 'researchguard.trace.model.v2'},
        'sources': [{'source_id': 's', 'lineage_id': 's', 'independence_group': 's'}],
        'evidence': [{'evidence_id': 'a', 'source_id': 's', 'raw_text': 'Observed text'}],
        'storyline_hypotheses': [{'hypothesis_id': 'h', 'claim': 'Hypothesis'}]})
    logic = load_model_from_dict({'model': {'id': 'm'}, 'nodes': {
        'h': {'type': 'Claim', 'text': 'Hypothesis'}, 'E': {'type': 'Evidence', 'text': 'Observed text',
            'provenance': [{'origin_kind': 'external_source', 'source_id': 's',
                            'locator': 'missing' if kind == 'logic' else 'a', 'quote': 'Observed text'}]}}, 'edges': []})
    # The trace fault concerns only trace references, so omit the independent logic route.
    models = {'source': source, 'trace': trace}
    if kind == 'logic':
        models['logic'] = logic
    index = {'hypotheses': [{'id': 'h', 'text': 'Hypothesis'}], 'root_claim': 'h', 'models': {'source': 'source.yaml'}}
    if kind == 'unused':
        index['hypotheses'].append({'id': 'unused', 'text': 'Unused'})
    return index, models


def project(status, root_license, trace_depth=None, views=None):
    """Abstract state of a real research_status result, so the same rules run on the real outputs."""
    rows = []
    for row in status['hypotheses']:
        logic, trace, experiment = row.get('logic') or {}, row.get('trace') or {}, row.get('experiment') or {}
        rows.append(Hypothesis(row['id'], logic.get('state'), trace.get('live'),
                               experiment.get('status') if experiment.get('status') not in (None, 'not_listed') else None))
    trace_depth = trace_depth or {}
    ablations = tuple(Ablation(row['id'], row['hypothesis'], 'logic' in row['caught_by'],
                               trace_depth.get(row['id'], 'trace' in row['caught_by']), row['id'] in trace_depth)
                      for row in status['ablations'])
    question = Question('native', tuple(rows), ablations=ablations, root_license=root_license)
    verdict = status['verdict']
    directions = tuple(sorted((row['anchor'], item['route'], item['hypothesis'], item['direction'])
                              for row in status['evidence'] for item in row.get('directions', ())))
    gap_rows = tuple((row['id'], tuple(row.get('hypotheses', ()))) for row in status['open_gaps'] if row['route'] == 'source')
    next_rows = tuple((row['id'], tuple(row.get('hypotheses', ()))) for row in status['next'] if row['route'] == 'search')
    return State(question, tuple(status['errors']), tuple(status['warnings']),
                 tuple((row['hypothesis'], row['kind'], row['detail'] if row['kind'] == 'anchor' else '') for row in status['disagreements']),
                 tuple((row['id'], tuple(row['caught_by'])) for row in status['ablations']),
                 tuple(verdict['live_hypotheses']), verdict['contested'],
                 (verdict['root_claim'] or {}).get('wording_license', ''), directions, gap_rows, next_rows, tuple(views or ()))


def native_features():
    """Real-code obligations the abstract cases stand for; each value is True when the real code meets it."""
    from dataclasses import replace
    from tempfile import TemporaryDirectory
    import json
    from researchguard.research import ResearchTree, check_research_tree, route_disagreements, apply_ablations, verdict_for_writers
    from researchguard.logic.loader import load_model_from_dict
    from researchguard.logic.source_library import SourceLibrary
    from researchguard.source.schema import BeliefState
    from researchguard.source.handoff import export_traceguard_seed, sync_traceguard_seed
    from researchguard.trace.schema import TraceGuardModel, HypothesisEvidenceLink
    index, models = native_case('consistent')
    trace = models['trace']
    models['trace'] = replace(trace, evidence=(replace(trace.evidence[0], raw_text='Changed copied text'),))
    drift = 'copy_drift:trace:a:raw_text' in check_research_tree(index, models)['errors']
    export_traceguard_seed(models['source'])
    changed = json.loads(json.dumps(models['trace'].to_dict()))
    changed['evidence'][0]['supports'] = ['h']
    merged, _, updated, conflicts = sync_traceguard_seed(models['source'], changed)
    models['trace'] = TraceGuardModel.from_dict(merged)
    drift = drift and not conflicts and bool(updated['evidence']) and not any(error.startswith('copy_drift:') for error in check_research_tree(index, models)['errors'])
    logic = load_model_from_dict({'model': {'id': 'direction'}, 'nodes': {
        'h': {'type': 'Claim', 'text': 'Hypothesis'}, 'E': {'type': 'Evidence', 'text': 'Observed text',
        'provenance': [{'origin_kind': 'external_source', 'source_id': 's', 'locator': 'a', 'quote': 'Observed text'}]}},
        'edges': [{'source': 'E', 'target': 'h', 'type': 'attacks'}]})
    from researchguard.logic.trace_import import sync_trace_bundle
    from researchguard.logic.provenance import content_hash_for
    stale_logic = logic.to_dict()
    stale_logic['nodes']['E']['provenance'][0].update(quote='Outdated quote', content_hash=content_hash_for('Outdated quote'))
    bundle = {'schema': 'researchguard.trace.logic-handoff.v1', 'hypotheses': [
        {'hypothesis_id': 'h', 'claim': 'Hypothesis', 'role': 'primary', 'supporting_evidence_ids': ['a'],
         'opposing_evidence_ids': [], 'limiting_evidence_ids': []}],
        'evidence': [{'evidence_id': 'a', 'source_id': 's', 'text': 'Observed text', 'locator': ''}]}
    refreshed, _, updated_logic, logic_conflicts = sync_trace_bundle(bundle, stale_logic)
    refreshed_model = load_model_from_dict(refreshed)
    drift = drift and not logic_conflicts and updated_logic['nodes'] == ['E'] and not any(error.startswith('copy_drift:logic:') for error in check_research_tree(index, dict(models, logic=refreshed_model))['errors'])
    directional = dict(models, logic=logic, trace=replace(trace, hypothesis_evidence_links=(HypothesisEvidenceLink.from_dict({'link_id': 'l', 'hypothesis_id': 'h', 'evidence_id': 'a', 'polarity': 'support'}),)))
    disagreement = route_disagreements(directional, []) == [{'hypothesis': 'h', 'kind': 'anchor', 'detail': 'a'}]
    status_rows = [{'id': 'h', 'logic': {'state': 'IN'}, 'trace': {'live': False}, 'experiment': {'status': 'consistent'}}]
    disagreement = disagreement and [row['kind'] for row in route_disagreements({}, status_rows)] == ['status']
    ablation_index = dict(index, ablations=[{'id': 'unused', 'hypothesis': 'h', 'remove_anchors': ['a'], 'expect': 'weaken'}])
    outcomes, errors, warnings = apply_ablations(ablation_index, models, {})
    ablation = not errors and outcomes[0]['caught_by'] == [] and warnings == ['ablation_not_caught:unused']
    with TemporaryDirectory() as directory:
        root = Path(directory)
        paper = root / 'paper.txt'
        paper.write_text('Observed text')
        library = SourceLibrary(root / 'library')
        imported = library.import_source(paper, title='Paper')
        library.create_source_model(imported.source.source_id, evidence='Observed text')
        node = sorted(library.source_node_ids(imported.source.source_id))[0]
        source = BeliefState.from_dict({'sources': [{'source_id': imported.source.source_id}]})
        model = load_model_from_dict({'model': {'id': 'library'}, 'nodes': {'h': {'type': 'Claim', 'text': 'Hypothesis'},
            'E': {'type': 'Evidence', 'text': 'Observed text', 'provenance': [{'origin_kind': 'external_source', 'source_id': imported.source.source_id, 'locator': node, 'quote': 'Observed text'}]}}, 'edges': []})
        actual = check_research_tree(index, {'source': source, 'logic': model}, source_library=library)
        unresolved = check_research_tree(index, {'source': source, 'logic': model})
        library_ok = not actual['errors'] and any(error.startswith('dangling_anchor:logic:E:') for error in unresolved['errors'])
    # live_hypotheses and contested: the real verdict on rows each route excludes once.
    rows = [{'id': 'h_out', 'logic': {'state': 'OUT'}, 'trace': {'live': True}, 'experiment': {'status': 'consistent'}},
            {'id': 'h_dead', 'logic': {'state': 'UNDECIDED'}, 'trace': {'live': False}, 'experiment': {'status': 'consistent'}},
            {'id': 'h_gone', 'logic': {'state': 'UNDECIDED'}, 'trace': {'live': True}, 'experiment': {'status': 'eliminated'}},
            {'id': 'h_live', 'logic': {'state': 'UNDECIDED'}, 'trace': {'live': True}, 'experiment': {'status': 'consistent'}}]
    empty = ResearchTree(Path('research.yaml'), {'hypotheses': [{'id': row['id'], 'text': row['id']} for row in rows]})
    verdict = verdict_for_writers(empty, rows, [], [])
    contested_rows = route_disagreements({}, [dict(rows[0], logic={'state': 'IN'}, trace={'live': False})])
    live = verdict['live_hypotheses'] == ['h_live'] and verdict['contested'] is False \
        and verdict_for_writers(empty, rows, contested_rows, [])['contested'] is True
    gap_source = BeliefState.from_dict({'sources': [{'source_id': 's'}], 'anchors': [{'anchor_id': 'a', 'source_id': 's', 'text': 'Observed text'}],
                                        'gaps': [{'gap_id': 'g', 'hypothesis_ids': ['h', 'h_missing']}]})
    gap_errors = check_research_tree(index, dict(models, source=gap_source))['errors']
    gaps = 'unknown_hypothesis:source:g:h_missing' in gap_errors and 'unknown_hypothesis:source:g:h' not in gap_errors
    try:
        from researchguard.research import evidence_directions
    except ImportError:
        directions = False
    else:
        limited = load_model_from_dict({'model': {'id': 'limit'}, 'nodes': {
            'h': {'type': 'Claim', 'text': 'Hypothesis'}, 'x': {'type': 'Claim', 'text': 'Not a hypothesis'},
            'E': {'type': 'Evidence', 'text': 'Observed text', 'provenance': [{'origin_kind': 'external_source', 'source_id': 's', 'locator': 'a', 'quote': 'Observed text'}]}},
            'edges': [{'source': 'E', 'target': 'h', 'type': 'qualifies'}, {'source': 'E', 'target': 'x', 'type': 'supports'}]})
        rows = evidence_directions(dict(directional, logic=limited), ['h'])
        directions = sorted((row['route'], row['hypothesis'], row['direction'], row['node']) for row in rows) == [
            ('logic', 'h', 'limit', 'E'), ('trace', 'h', 'support', None)]
        rows = evidence_directions(directional, ['h'])
        directions = directions and sorted((row['route'], row['direction'], row['node']) for row in rows) == [('logic', 'oppose', 'E'), ('trace', 'support', None)]
    import copy
    from researchguard.research import compare_research_status, load_research, research_status
    current = research_status(load_research(Path(__file__).resolve().parents[2] / 'examples/research/evergiven'))
    candidate = copy.deepcopy(current)
    candidate['verdict']['root_claim']['reason'] = 'A different reason.'
    candidate['verdict']['live_hypotheses'] = ['h_demand']
    rows = {(row['kind'], row['id']) for row in compare_research_status(current, candidate)['changes']}
    compare = {('verdict', 'root_claim.reason'), ('verdict', 'live_hypotheses')} <= rows \
        and compare_research_status(current, copy.deepcopy(current))['changes'] == []
    return {'drift': drift, 'gaps': gaps, 'directions': directions, 'compare': compare, 'library': library_ok, 'disagreement': disagreement, 'ablation': ablation, 'live': live}


def evergiven_state():
    from tempfile import TemporaryDirectory
    import json
    from researchguard.research import status_main, load_research
    from researchguard.logic.minimal_sets import license_model_claim
    folder = Path(__file__).resolve().parents[2] / 'examples/research/evergiven'
    with TemporaryDirectory() as directory:
        output = Path(directory) / 'status.json'
        exit_code = status_main([str(folder), '--json', '--output', str(output)])
        status = json.loads(output.read_text())
    tree = load_research(folder)
    native_license = license_model_claim(tree.models['logic'], tree.index['root_claim']).wording_license
    try:
        from researchguard.research import hypothesis_view
    except ImportError:
        return exit_code, status, None
    views = []
    for row in status['hypotheses']:
        view = hypothesis_view(status, row['id'])
        views.append((row['id'], tuple(item['id'] for item in view['open_gaps']), tuple(item['id'] for item in view['next'] if item['route'] == 'search'),
                      tuple(item['id'] for item in view['ablations'] if item['hypothesis'] == row['id'])))
    return exit_code, status, project(status, native_license, trace_depth_answers(tree.models['trace']), views)


def trace_depth_answers(trace):
    """TraceGuard's own depth verdict for each trace-declared ablation's expected sensitivity."""
    from researchguard.trace.evaluator import evaluate_model
    depth = evaluate_model(trace, include_storyline_depth=True).storyline_depth
    mismatched = set(depth.sensitivity_mismatch_ids)
    return {row.perturbation_id: row.sensitivity_id not in mismatched for row in trace.expected_sensitivities
            if row.target_kind == 'hypothesis' and row.expected_direction == 'decrease'}


def conformance():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
    from flowguard.conformance import ConformanceReport, ConformanceViolation
    from flowguard.replay import ReplayObservation
    from researchguard.research import check_research_tree
    observations, violations = [], []
    model = {case.name: next(iter(Status().apply(case, State()))).new_state for case in CASES}
    for kind in ('consistent', 'trace', 'logic', 'unused'):
        index, models = native_case(kind)
        result = check_research_tree(index, models)
        actual = (tuple(result['errors']), tuple(result['warnings']))
        want = (model[kind].errors, model[kind].warnings)
        observations.append(ReplayObservation('Status', actual, model[kind]))
        if actual != want:
            violations.append(ConformanceViolation(step_index=1, rule_name='Status', message=f'{kind}: {actual!r} != {want!r}'))
    for kind, satisfied in native_features().items():
        observations.append(ReplayObservation('Status', satisfied, State()))
        if not satisfied:
            violations.append(ConformanceViolation(step_index=1, rule_name='Status', message=f'{kind}: native obligation failed'))
    exit_code, status, state = evergiven_state()
    if state is None:
        violations.append(ConformanceViolation(step_index=1, rule_name='Status', message='evergiven: hypothesis_view and evidence directions are not implemented'))
        return ConformanceReport(ok=False, violations=tuple(violations), replayed_steps=tuple(observations), summary='hypothesis readback missing')
    observations.append(ReplayObservation('Status', exit_code, state))
    if exit_code:
        violations.append(ConformanceViolation(step_index=1, rule_name='Status', message=f'evergiven: status exited {exit_code}'))
    for invariant in INVARIANTS:
        verdict = invariant.check(state, ())
        if not verdict.ok:
            violations.append(ConformanceViolation(step_index=1, rule_name='Status', message=f'evergiven: {invariant.name}: {verdict.message}'))
    if not (status['ablations'] and all(row['caught_by'] for row in status['ablations'])):
        violations.append(ConformanceViolation(step_index=1, rule_name='Status', message='evergiven: a declared ablation is not caught by its route'))
    return ConformanceReport(ok=not violations, violations=tuple(violations), replayed_steps=tuple(observations),
                             summary='Real checker, route comparison, ablations and verdict replayed on small trees and the Ever Given folder; the same rules run on the projected real status.')
