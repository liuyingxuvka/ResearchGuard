"""Shared-id reference constraints with known-bad mutations and native replay."""
from dataclasses import dataclass
from pathlib import Path
import sys

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer

MODEL_ID = 'research_tree_crossref'
PARENT = 'research-tree'
COMPONENTS = ['research-tree']
IMPLEMENTED_BY = {'Check': 'src/researchguard/research.py:check_research_tree'}
TESTED_BY = {
    'dangling_reference_is_an_error': ['tests/test_research_tree.py:test_dangling_references_and_invalid_native_models_are_errors'],
    'consistent_tree_has_no_error': ['tests/test_research_tree.py:test_consistent_tree_has_no_errors'],
    'unused_hypothesis_is_only_a_warning': ['tests/test_research_tree.py:test_unused_hypothesis_is_only_a_warning'],
}


@dataclass(frozen=True)
class Case:
    kind: str


@dataclass(frozen=True)
class State:
    kind: str = ''
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


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
    return Explorer(Workflow((step,)), (State(),), CASES, INVARIANTS, progress_steps=0)


def build_explorer():
    return explorer(Check())


def broken_variants():
    result = {}
    for name in ('ignore_trace', 'ignore_logic', 'consistent_as_error', 'warning_as_error'):
        step = Check()
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
    return ConformanceReport(ok=not violations, violations=tuple(violations), replayed_steps=tuple(observations),
                             summary='Real in-memory cross-reference checker replayed for consistent, trace, logic and unused-id trees.')
