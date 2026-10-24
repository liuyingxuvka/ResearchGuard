"""Shared-id reference constraints with known-bad mutations and native replay."""
from dataclasses import dataclass
from pathlib import Path
import sys

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer

MODEL_ID = 'research_tree_crossref'
PARENT = 'system'
COMPONENTS = ['research-tree', 'researchguard-suite', 'sourceguard', 'logic-argument']
IMPLEMENTED_BY = {'Check': 'src/researchguard/research.py:check_research_tree',
 'Status': 'src/researchguard/research.py:status_main',
 'CopyCheck': 'src/researchguard/ownership.py:copied_content_problems',
 'SourceSync': 'src/researchguard/source/handoff.py:sync_traceguard_seed',
 'LogicSync': 'src/researchguard/logic/trace_import.py:sync_trace_bundle',
 'Disagreements': 'src/researchguard/research.py:route_disagreements',
 'Ablations': 'src/researchguard/research.py:apply_ablations',
 'Verdict': 'src/researchguard/research.py:verdict_for_writers'}
TESTED_BY = {'dangling_reference_is_an_error': ['tests/test_research_tree.py:test_dangling_references_and_invalid_native_models_are_errors'],
 'consistent_tree_has_no_error': ['tests/test_research_tree.py:test_consistent_tree_has_no_errors'],
 'unused_hypothesis_is_only_a_warning': ['tests/test_research_tree.py:test_unused_hypothesis_is_only_a_warning'],
 'copied_content_matches_owner': ['tests/test_research_tree.py:test_copy_drift_is_an_error_for_each_copied_field'],
 'library_anchors_are_resolved': ['tests/test_research_tree.py:test_library_anchored_evidence_gets_one_answer'],
 'routes_do_not_contradict_silently': ['tests/test_research_tree.py:test_opposite_anchor_directions_are_a_disagreement'],
 'every_ablation_is_caught_or_named': ['tests/test_research_tree.py:test_ablation_nobody_uses_is_named'],
 'verdict_matches_the_routes': ['tests/test_research_tree.py:test_verdict_matches_each_route_and_page_is_readable']}


@dataclass(frozen=True)
class Case:
    kind: str


@dataclass(frozen=True)
class State:
    kind: str = ''
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    satisfied: bool = True


def expected(kind):
    if kind == 'trace':
        return ('dangling_anchor:trace:a',), ()
    if kind == 'logic':
        return ('dangling_anchor:logic:E:missing (source s)',), ()
    if kind == 'unused':
        return (), ('hypothesis_unused:unused',)
    return (), ()


class Check:
    name = 'Check'
    reads = ()
    writes = ('kind', 'errors', 'warnings')
    mutation = ''

    def apply(self, case, state):
        if case.kind in FEATURES:
            yield FunctionResult(case.kind, State(case.kind, satisfied=self.mutation != FEATURES[case.kind][1]), label=case.kind)
            return
        errors, warnings = expected(case.kind)
        if self.mutation == f'ignore_{case.kind}':
            errors = ()
        if self.mutation == 'consistent_as_error' and case.kind == 'consistent':
            errors = ('invented_error',)
        if self.mutation == 'warning_as_error' and warnings:
            errors, warnings = warnings, ()
        yield FunctionResult((errors, warnings), State(case.kind, errors, warnings), label=case.kind)


def dangling(state, trace):
    if state.kind in ('trace', 'logic') and not state.errors:
        return InvariantResult.fail('dangling anchor was not an error')
    return InvariantResult.pass_()


def consistent(state, trace):
    if state.kind == 'consistent' and state.errors:
        return InvariantResult.fail('consistent tree received an error')
    return InvariantResult.pass_()


def warning(state, trace):
    if state.kind == 'unused' and (state.errors or not state.warnings):
        return InvariantResult.fail('unused hypothesis must be a warning only')
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant('dangling_reference_is_an_error', 'all dangling references are errors', dangling),
    Invariant('consistent_tree_has_no_error', 'consistent shared ids have no errors', consistent),
    Invariant('unused_hypothesis_is_only_a_warning', 'unused index hypotheses only warn', warning),
)
CASES = tuple(Case(kind) for kind in ('consistent', 'trace', 'logic', 'unused'))


def explorer(step):
    return Explorer(Workflow((step,)), (State(),), CASES + tuple(Case(kind) for kind in FEATURES), INVARIANTS, progress_steps=0)


def build_explorer():
    return explorer(Check())


def broken_variants():
    result = {}
    for name in ('ignore_trace', 'ignore_logic', 'consistent_as_error', 'warning_as_error'):
        step = Check()
        step.mutation = name
        result[name] = explorer(step)
    for _, mutation, _ in FEATURES.values():
        step = Check()
        step.mutation = mutation
        result[mutation] = explorer(step)
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


FEATURES = {
    'drift': ('copied_content_matches_owner', 'ignore_copy_drift', 'tests/test_research_tree.py:test_copy_drift_is_an_error_for_each_copied_field'),
    'library': ('library_anchors_are_resolved', 'status_ignores_library', 'tests/test_research_tree.py:test_library_anchored_evidence_gets_one_answer'),
    'disagreement': ('routes_do_not_contradict_silently', 'skip_route_comparison', 'tests/test_research_tree.py:test_opposite_anchor_directions_are_a_disagreement'),
    'ablation': ('every_ablation_is_caught_or_named', 'drop_uncaught_ablations', 'tests/test_research_tree.py:test_ablation_nobody_uses_is_named'),
    'verdict': ('verdict_matches_the_routes', 'verdict_upgrades_license', 'tests/test_research_tree.py:test_verdict_matches_each_route_and_page_is_readable'),
}


def feature_rule(kind):
    def check(state, trace):
        if state.kind == kind and not state.satisfied:
            return InvariantResult.fail(FEATURES[kind][0])
        return InvariantResult.pass_()
    return check


INVARIANTS += (
    Invariant('copied_content_matches_owner', 'Copied values match their SourceGuard owner.', feature_rule('drift')),
    Invariant('library_anchors_are_resolved', 'Native library provenance is accepted consistently.', feature_rule('library')),
    Invariant('routes_do_not_contradict_silently', 'Direct route disagreements stay visible.', feature_rule('disagreement')),
    Invariant('every_ablation_is_caught_or_named', 'Uncaught known-bad ablations are named.', feature_rule('ablation')),
    Invariant('verdict_matches_the_routes', 'The verdict never upgrades native results.', feature_rule('verdict')),
)


def native_features():
    from dataclasses import replace
    from tempfile import TemporaryDirectory
    from researchguard.research import check_research_tree, route_disagreements, apply_ablations, load_research, research_status
    from researchguard.logic.loader import load_model_from_dict
    from researchguard.logic.source_library import SourceLibrary
    from researchguard.source.schema import BeliefState
    from researchguard.source.handoff import export_traceguard_seed, sync_traceguard_seed
    from researchguard.trace.schema import TraceGuardModel, HypothesisEvidenceLink
    from researchguard.logic.model import Edge
    index, models = native_case('consistent')
    trace = models['trace']
    models['trace'] = replace(trace, evidence=(replace(trace.evidence[0], raw_text='Changed copied text'),))
    drift = 'copy_drift:trace:a:raw_text' in check_research_tree(index, models)['errors']
    seed = export_traceguard_seed(models['source'])
    import json
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
    project = Path(__file__).resolve().parents[2] / 'examples/research/evergiven'
    from researchguard.research import status_main
    with TemporaryDirectory() as directory:
        output = Path(directory) / 'status.json'
        exit_code = status_main([str(project), '--json', '--output', str(output)])
        status = json.loads(output.read_text())
    if exit_code:
        return {'drift': drift, 'library': library_ok, 'disagreement': disagreement, 'ablation': ablation, 'verdict': False}
    verdict = status['verdict']
    verdict_ok = verdict['root_claim']['wording_license'] == 'withhold' and verdict['search'] == 'continue_search' and not verdict['contested'] and verdict['errors'] == 0
    ablation = ablation and bool(status['ablations']) and all(row['caught_by'] for row in status['ablations'])
    return {'drift': drift, 'library': library_ok, 'disagreement': disagreement, 'ablation': ablation, 'verdict': verdict_ok}


def conformance():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
    from flowguard.conformance import ConformanceReport, ConformanceViolation
    from flowguard.replay import ReplayObservation
    from researchguard.research import check_research_tree
    observations, violations = [], []
    for case in CASES:
        index, models = native_case(case.kind)
        result = check_research_tree(index, models)
        actual = (tuple(result['errors']), tuple(result['warnings']))
        want = expected(case.kind)
        observations.append(ReplayObservation('Check', actual, State(case.kind, *actual)))
        if actual != want:
            violations.append(ConformanceViolation(step_index=1, rule_name='Check', message=f'{case.kind}: {actual!r} != {want!r}'))
    for kind, satisfied in native_features().items():
        observations.append(ReplayObservation('Check', satisfied, State(kind, satisfied=satisfied)))
        if not satisfied:
            violations.append(ConformanceViolation(step_index=1, rule_name='Check', message=f'{kind}: native obligation failed'))
    return ConformanceReport(ok=not violations, violations=tuple(violations), replayed_steps=tuple(observations),
                             summary='Real in-memory cross-reference checker replayed for consistent, trace, logic and unused-id trees.')
