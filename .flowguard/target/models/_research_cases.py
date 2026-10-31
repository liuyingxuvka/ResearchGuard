"""Shared finite questions, unchanged rule predicates and live native fixtures."""

from dataclasses import dataclass

from pathlib import Path

import sys

from flowguard import InvariantResult

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

H = Hypothesis

CASES = (
    Question('consistent', (H('h', 'UNDECIDED', True, 'consistent', (('a', 'trace', 'support'), ('a', 'logic', 'support'))),), root_license='withhold'),
    Question('reference_only', (H('h', 'UNDECIDED', None, None, (('a', 'logic', 'support'),)),), root_license='withhold'),
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
    if kind == 'reference_only':
        raw = logic.to_dict()
        raw['nodes']['E_reference'] = {'type': 'Evidence', 'text': 'A reference-only supporting sentence',
            'provenance': [{'origin_kind': 'external_source', 'source_reference': 'Named publication',
                            'quote': 'A reference-only supporting sentence'}]}
        raw['edges'] = [{'source': 'E', 'target': 'h', 'type': 'supports'},
                        {'source': 'E_reference', 'target': 'h', 'type': 'supports'}]
        logic = load_model_from_dict(raw)
    # The trace fault concerns only trace references, so omit the independent logic route.
    models = {'source': source, 'trace': trace}
    if kind in ('logic', 'reference_only'):
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

def trace_depth_answers(trace):
    """TraceGuard's own depth verdict for each trace-declared ablation's expected sensitivity."""
    from researchguard.trace.evaluator import evaluate_model
    depth = evaluate_model(trace, include_storyline_depth=True).storyline_depth
    mismatched = set(depth.sensitivity_mismatch_ids)
    return {row.perturbation_id: row.sensitivity_id not in mismatched for row in trace.expected_sensitivities
            if row.target_kind == 'hypothesis' and row.expected_direction == 'decrease'}

REPO_ROOT = next(parent for parent in Path(__file__).resolve().parents
                 if (parent / 'pyproject.toml').is_file() and (parent / 'examples/research/evergiven').is_dir())
EVERGIVEN = REPO_ROOT / 'examples/research/evergiven'


def native_crossref():
    from dataclasses import replace
    from tempfile import TemporaryDirectory
    import json
    from researchguard.research import ResearchTree, check_research_tree, route_disagreements, apply_ablations, verdict_for_writers
    from researchguard.logic.loader import load_model_from_dict
    from researchguard.logic.source_library import SourceLibrary
    from researchguard.source.schema import BeliefState
    from researchguard.source.handoff import export_traceguard_seed, sync_traceguard_seed
    from researchguard.trace.schema import TraceGuardModel, HypothesisEvidenceLink
    from researchguard.logic.trace_import import sync_trace_bundle
    from researchguard.logic.provenance import content_hash_for
    import copy
    from researchguard.research import compare_research_status, load_research, research_status
    index, models = native_case('consistent')
    trace = models['trace']
    models['trace'] = replace(trace, evidence=(replace(trace.evidence[0], raw_text='Changed copied text'),))
    drift = 'copy_drift:trace:a:raw_text' in check_research_tree(index, models)['errors']
    export_traceguard_seed(models['source'])
    changed = json.loads(json.dumps(models['trace'].to_dict()))
    changed['evidence'][0]['supports'] = ['h']
    merged, _, updated, conflicts = sync_traceguard_seed(models['source'], changed)
    models['trace'] = TraceGuardModel.from_dict(merged)
    drift = drift and (not conflicts) and bool(updated['evidence']) and (not any((error.startswith('copy_drift:') for error in check_research_tree(index, models)['errors'])))
    logic = load_model_from_dict({'model': {'id': 'direction'}, 'nodes': {'h': {'type': 'Claim', 'text': 'Hypothesis'}, 'E': {'type': 'Evidence', 'text': 'Observed text', 'provenance': [{'origin_kind': 'external_source', 'source_id': 's', 'locator': 'a', 'quote': 'Observed text'}]}}, 'edges': [{'source': 'E', 'target': 'h', 'type': 'attacks'}]})
    from researchguard.logic.trace_import import sync_trace_bundle
    from researchguard.logic.provenance import content_hash_for
    stale_logic = logic.to_dict()
    stale_logic['nodes']['E']['provenance'][0].update(quote='Outdated quote', content_hash=content_hash_for('Outdated quote'))
    bundle = {'schema': 'researchguard.trace.logic-handoff.v1', 'hypotheses': [{'hypothesis_id': 'h', 'claim': 'Hypothesis', 'role': 'primary', 'supporting_evidence_ids': ['a'], 'opposing_evidence_ids': [], 'limiting_evidence_ids': []}], 'evidence': [{'evidence_id': 'a', 'source_id': 's', 'text': 'Observed text', 'locator': ''}]}
    refreshed, _, updated_logic, logic_conflicts = sync_trace_bundle(bundle, stale_logic)
    refreshed_model = load_model_from_dict(refreshed)
    drift = drift and (not logic_conflicts) and (updated_logic['nodes'] == ['E']) and (not any((error.startswith('copy_drift:logic:') for error in check_research_tree(index, dict(models, logic=refreshed_model))['errors'])))
    with TemporaryDirectory() as directory:
        root = Path(directory)
        paper = root / 'paper.txt'
        paper.write_text('Observed text')
        library = SourceLibrary(root / 'library')
        imported = library.import_source(paper, title='Paper')
        library.create_source_model(imported.source.source_id, evidence='Observed text')
        node = sorted(library.source_node_ids(imported.source.source_id))[0]
        source = BeliefState.from_dict({'sources': [{'source_id': imported.source.source_id}]})
        model = load_model_from_dict({'model': {'id': 'library'}, 'nodes': {'h': {'type': 'Claim', 'text': 'Hypothesis'}, 'E': {'type': 'Evidence', 'text': 'Observed text', 'provenance': [{'origin_kind': 'external_source', 'source_id': imported.source.source_id, 'locator': node, 'quote': 'Observed text'}]}}, 'edges': []})
        actual = check_research_tree(index, {'source': source, 'logic': model}, source_library=library)
        unresolved = check_research_tree(index, {'source': source, 'logic': model})
        library_ok = not actual['errors'] and any((error.startswith('dangling_anchor:logic:E:') for error in unresolved['errors']))
    gap_source = BeliefState.from_dict({'sources': [{'source_id': 's'}], 'anchors': [{'anchor_id': 'a', 'source_id': 's', 'text': 'Observed text'}], 'gaps': [{'gap_id': 'g', 'hypothesis_ids': ['h', 'h_missing']}]})
    gap_errors = check_research_tree(index, dict(models, source=gap_source))['errors']
    gaps = 'unknown_hypothesis:source:g:h_missing' in gap_errors and 'unknown_hypothesis:source:g:h' not in gap_errors
    return {'drift': drift, 'gaps': gaps, 'library': library_ok}

def native_verdict():
    from dataclasses import replace
    from tempfile import TemporaryDirectory
    import json
    from researchguard.research import ResearchTree, check_research_tree, route_disagreements, apply_ablations, verdict_for_writers
    from researchguard.logic.loader import load_model_from_dict
    from researchguard.logic.source_library import SourceLibrary
    from researchguard.source.schema import BeliefState
    from researchguard.source.handoff import export_traceguard_seed, sync_traceguard_seed
    from researchguard.trace.schema import TraceGuardModel, HypothesisEvidenceLink
    from researchguard.logic.trace_import import sync_trace_bundle
    from researchguard.logic.provenance import content_hash_for
    import copy
    from researchguard.research import compare_research_status, load_research, research_status
    index, models = native_case('consistent')
    trace = models['trace']
    logic = load_model_from_dict({'model': {'id': 'direction'}, 'nodes': {'h': {'type': 'Claim', 'text': 'Hypothesis'}, 'E': {'type': 'Evidence', 'text': 'Observed text', 'provenance': [{'origin_kind': 'external_source', 'source_id': 's', 'locator': 'a', 'quote': 'Observed text'}]}}, 'edges': [{'source': 'E', 'target': 'h', 'type': 'attacks'}]})
    directional = dict(models, logic=logic, trace=replace(trace, hypothesis_evidence_links=(HypothesisEvidenceLink.from_dict({'link_id': 'l', 'hypothesis_id': 'h', 'evidence_id': 'a', 'polarity': 'support'}),)))
    disagreement = route_disagreements(directional, []) == [{'hypothesis': 'h', 'kind': 'anchor', 'detail': 'a'}]
    status_rows = [{'id': 'h', 'logic': {'state': 'IN'}, 'trace': {'live': False}, 'experiment': {'status': 'consistent'}}]
    disagreement = disagreement and [row['kind'] for row in route_disagreements({}, status_rows)] == ['status']
    rows = [{'id': 'h_out', 'logic': {'state': 'OUT'}, 'trace': {'live': True}, 'experiment': {'status': 'consistent'}}, {'id': 'h_dead', 'logic': {'state': 'UNDECIDED'}, 'trace': {'live': False}, 'experiment': {'status': 'consistent'}}, {'id': 'h_gone', 'logic': {'state': 'UNDECIDED'}, 'trace': {'live': True}, 'experiment': {'status': 'eliminated'}}, {'id': 'h_live', 'logic': {'state': 'UNDECIDED'}, 'trace': {'live': True}, 'experiment': {'status': 'consistent'}}]
    empty = ResearchTree(Path('research.yaml'), {'hypotheses': [{'id': row['id'], 'text': row['id']} for row in rows]})
    verdict = verdict_for_writers(empty, rows, [], [])
    contested_rows = route_disagreements({}, [dict(rows[0], logic={'state': 'IN'}, trace={'live': False})])
    live = verdict['live_hypotheses'] == ['h_live'] and verdict['contested'] is False and (verdict_for_writers(empty, rows, contested_rows, [])['contested'] is True)
    try:
        from researchguard.research import evidence_directions
    except ImportError:
        directions = False
    else:
        limited = load_model_from_dict({'model': {'id': 'limit'}, 'nodes': {'h': {'type': 'Claim', 'text': 'Hypothesis'}, 'x': {'type': 'Claim', 'text': 'Not a hypothesis'}, 'E': {'type': 'Evidence', 'text': 'Observed text', 'provenance': [{'origin_kind': 'external_source', 'source_id': 's', 'locator': 'a', 'quote': 'Observed text'}]}}, 'edges': [{'source': 'E', 'target': 'h', 'type': 'qualifies'}, {'source': 'E', 'target': 'x', 'type': 'supports'}]})
        rows = evidence_directions(dict(directional, logic=limited), ['h'])
        directions = sorted(((row['route'], row['hypothesis'], row['direction'], row['node']) for row in rows)) == [('logic', 'h', 'limit', 'E'), ('trace', 'h', 'support', None)]
        rows = evidence_directions(directional, ['h'])
        directions = directions and sorted(((row['route'], row['direction'], row['node']) for row in rows)) == [('logic', 'oppose', 'E'), ('trace', 'support', None)]
    _, reference_models = native_case('reference_only')
    reference_rows = evidence_directions(reference_models, ['h'])
    reference_only = {(row['anchor'], row['node']) for row in reference_rows} == {('a', 'E')}
    return {'disagreement': disagreement, 'live': live, 'directions': directions, 'reference_only': reference_only}

def native_ablations():
    from dataclasses import replace
    from tempfile import TemporaryDirectory
    import json
    from researchguard.research import ResearchTree, check_research_tree, route_disagreements, apply_ablations, verdict_for_writers
    from researchguard.logic.loader import load_model_from_dict
    from researchguard.logic.source_library import SourceLibrary
    from researchguard.source.schema import BeliefState
    from researchguard.source.handoff import export_traceguard_seed, sync_traceguard_seed
    from researchguard.trace.schema import TraceGuardModel, HypothesisEvidenceLink
    from researchguard.logic.trace_import import sync_trace_bundle
    from researchguard.logic.provenance import content_hash_for
    import copy
    from researchguard.research import compare_research_status, load_research, research_status
    index, models = native_case('consistent')
    trace = models['trace']
    ablation_index = dict(index, ablations=[{'id': 'unused', 'hypothesis': 'h', 'remove_anchors': ['a'], 'expect': 'weaken'}])
    outcomes, errors, warnings = apply_ablations(ablation_index, models, {})
    ablation = not errors and outcomes[0]['caught_by'] == [] and (warnings == ['ablation_not_caught:unused'])
    return {'ablation': ablation}

def native_views(status):
    from dataclasses import replace
    from tempfile import TemporaryDirectory
    import json
    from researchguard.research import ResearchTree, check_research_tree, route_disagreements, apply_ablations, verdict_for_writers
    from researchguard.logic.loader import load_model_from_dict
    from researchguard.logic.source_library import SourceLibrary
    from researchguard.source.schema import BeliefState
    from researchguard.source.handoff import export_traceguard_seed, sync_traceguard_seed
    from researchguard.trace.schema import TraceGuardModel, HypothesisEvidenceLink
    from researchguard.logic.trace_import import sync_trace_bundle
    from researchguard.logic.provenance import content_hash_for
    import copy
    from researchguard.research import compare_research_status, load_research, research_status
    current = status
    candidate = copy.deepcopy(current)
    candidate['verdict']['root_claim']['reason'] = 'A different reason.'
    candidate['verdict']['live_hypotheses'] = ['h_demand']
    rows = {(row['kind'], row['id']) for row in compare_research_status(current, candidate)['changes']}
    compare = {('verdict', 'root_claim.reason'), ('verdict', 'live_hypotheses')} <= rows and compare_research_status(current, copy.deepcopy(current))['changes'] == []
    return {'compare': compare}

def native_sync():
    """Replay real sync on an already-synced folder, one added anchor and a true conflict."""
    import contextlib
    import io
    import shutil
    from tempfile import TemporaryDirectory
    import yaml
    from researchguard.cli import main
    from researchguard.research import load_research, research_status, compare_research_status
    from researchguard.source.loader import load_model as load_source
    from researchguard.source.handoff import sync_traceguard_seed
    from researchguard.trace.loader import load_model as load_trace
    from researchguard.trace.evaluator import evaluate_model
    from researchguard.trace.export_logicguard import logicguard_bundle
    from researchguard.logic.trace_import import sync_trace_bundle

    def bytes_in(folder):
        return {str(path.relative_to(folder)): path.read_bytes() for path in folder.rglob('*') if path.is_file()}

    with TemporaryDirectory() as directory:
        root = Path(directory)
        baseline = root / 'baseline'
        shutil.copytree(EVERGIVEN, baseline)
        # Establish the precondition with the old, existing native member APIs.
        trace_path, logic_path = baseline / 'trace.yaml', baseline / 'logic.yaml'
        trace, _, _, conflicts = sync_traceguard_seed(load_source(baseline / 'source.yaml'), yaml.safe_load(trace_path.read_text()))
        assert not conflicts, conflicts
        trace_path.write_text(yaml.safe_dump(trace, sort_keys=False, allow_unicode=True))
        trace_model = load_trace(trace_path)
        bundle = logicguard_bundle(evaluate_model(trace_model), model=trace_model)
        logic, _, _, conflicts = sync_trace_bundle(bundle, yaml.safe_load(logic_path.read_text()))
        assert not conflicts, conflicts
        logic_path.write_text(yaml.safe_dump(logic, sort_keys=False, allow_unicode=True))
        baseline_status = research_status(load_research(baseline))
        results = {}
        for label in ('unchanged', 'added_anchor', 'conflict'):
            folder = root / label
            shutil.copytree(baseline, folder)
            if label == 'added_anchor':
                with contextlib.redirect_stdout(io.StringIO()):
                    added = main(['source', 'add-anchor', str(folder / 'source.yaml'), '--source-id', 'src-lloyds',
                                  '--anchor-id', 'anc-lloyds', '--quote', 'The Suez blockage alone doubled Asia-Europe spot rates in April 2021.',
                                  '--locator', "Lloyd's List, April 2021", '--output', str(folder / 'source.yaml')])
                assert added == 0, added
            if label == 'conflict':
                trace_path = folder / 'trace.yaml'
                trace = yaml.safe_load(trace_path.read_text())
                evidence = trace['evidence'][0]
                evidence['source_id'] = next(row['source_id'] for row in trace['sources'] if row['source_id'] != evidence['source_id'])
                trace_path.write_text(yaml.safe_dump(trace, sort_keys=False))
            before = bytes_in(folder)
            current = research_status(load_research(folder)) if label == 'conflict' else baseline_status
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = main(['sync', str(folder)])
            after = bytes_in(folder)
            preserved = before == after if label != 'added_anchor' else (
                set(before) == set(after) and all(after[name] == value for name, value in before.items()
                                                if name not in ('trace.yaml', 'logic.yaml')))
            changes = compare_research_status(current, research_status(load_research(folder)))['changes']
            results[label] = {'exit': result, 'output': output.getvalue().strip(), 'preserved': preserved,
                              'new_anchor': 'anc-lloyds' if label == 'added_anchor' else '',
                              'conflict': label == 'conflict', 'changes': changes}
            if result == 2:
                # Preserve the real missing-command evidence; do not simulate success.
                break
        return results
