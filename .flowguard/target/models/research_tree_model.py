"""research_tree_crossref: one independent aspect of the question status."""

from dataclasses import dataclass
import hashlib

from pathlib import Path

import sys

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow

from flowguard.explorer import Explorer

from _research_cases import native_unanchored

from _research_cases import (Hypothesis, Ablation, Question, excluded, accepted, unused, route_conflicts, rule, unknown_gap_hypotheses, consistent_tree, dangling_reference, unused_hypothesis, gap_hypotheses, copied_content, library_anchors, routes_contradict, every_ablation, trace_depth_agrees, verdict_routes, live_hypotheses, directions_rule, view_rule, candidate_rule, contested_rule, CASES, native_case, project, trace_depth_answers, REPO_ROOT, EVERGIVEN, native_crossref, native_ablations, native_verdict, native_views)

QUESTION_FILES = ('research.yaml', 'source.yaml', 'trace.yaml', 'logic.yaml')

MODEL_ID = 'research_tree_crossref'

PARENT = 'research-tree'

COMPONENTS = ['research-tree', 'researchguard-suite']

IMPLEMENTED_BY = {'LibrarySources': 'src/researchguard/research.py:_ResearchLibrary.list_sources', 'LibraryNodes': 'src/researchguard/research.py:_ResearchLibrary.source_node_ids', 'Load': 'src/researchguard/research.py:load_research', 'Check': 'src/researchguard/research.py:check_research_tree', 'Status': 'src/researchguard/research.py:status_main', 'CopyCheck': 'src/researchguard/ownership.py:copied_content_problems'}

USES = {
    'SourceSync': 'src/researchguard/source/handoff.py:sync_traceguard_seed',
    'LogicSync': 'src/researchguard/logic/trace_import.py:sync_trace_bundle',
    'LoadModelFromDict': 'src/researchguard/logic/loader.py:load_model_from_dict',
    'SourceLibrary': 'src/researchguard/logic/source_library.py:SourceLibrary',
    'SourceLibraryCreateSourceModel': 'src/researchguard/logic/source_library.py:SourceLibrary.create_source_model',
    'SourceLibraryImportSource': 'src/researchguard/logic/source_library.py:SourceLibrary.import_source',
    'SourceLibrarySourceIndexPath': 'src/researchguard/logic/source_library.py:SourceLibrary.source_index_path',
    'SourceLibrarySourceModelPath': 'src/researchguard/logic/source_library.py:SourceLibrary.source_model_path',
    'SourceLibrarySourceNodeIds': 'src/researchguard/logic/source_library.py:SourceLibrary.source_node_ids',
    'BeliefStateFromDict': 'src/researchguard/source/schema.py:BeliefState.from_dict',
    'TraceGuardModelFromDict': 'src/researchguard/trace/schema.py:TraceGuardModel.from_dict',
}

TESTED_BY = {'status_names_its_inputs': ['tests/test_research_tree_crossref.py:test_status_reports_input_digests'], 'consistent_tree_has_no_error': ['tests/test_research_tree_crossref.py:test_consistent_tree_has_no_errors', 'tests/test_research_tree_crossref.py:test_checker_is_in_memory_and_source_is_optional', 'tests/test_research_tree_crossref.py:test_shipped_evergiven_tree_has_consistent_shared_ids', 'tests/test_research_tree_crossref.py:test_candidate_view_lists_only_changes'], 'dangling_reference_is_an_error': ['tests/test_research_tree_crossref.py:test_dangling_references_and_invalid_native_models_are_errors', 'tests/test_research_tree_crossref.py:test_missing_index_exits_2', 'tests/test_research_tree_crossref.py:test_missing_index_names_the_template'], 'unused_hypothesis_is_only_a_warning': ['tests/test_research_tree_crossref.py:test_unused_hypothesis_is_only_a_warning'], 'gap_names_known_hypotheses': ['tests/test_research_tree_crossref.py:test_gap_hypotheses_are_checked_and_grouped'], 'copied_content_matches_owner': ['tests/test_research_tree_crossref.py:test_copy_drift_is_an_error_for_each_copied_field', 'tests/test_research_tree_crossref.py:test_one_observation_reaches_trace_and_logic_by_sync'], 'library_anchors_are_resolved': ['tests/test_research_tree_crossref.py:test_library_anchored_evidence_gets_one_answer'], 'unanchored_evidence_is_an_error': ['tests/test_research_tree_crossref.py:test_unanchored_logic_evidence_is_an_error_with_a_source_model', 'tests/test_research_tree_crossref.py:test_unanchored_logic_evidence_is_listed_without_a_source_model']}

UNANCHORED_ERROR = 'evidence_not_in_source:logic:E_reference (its provenance names no source_id; add the anchor with researchguard source add-anchor, then run researchguard sync <folder>)'
UNANCHORED_CASES = (
    Question('unanchored_source', (Hypothesis('h', 'UNDECIDED'),), dangling=(UNANCHORED_ERROR,)),
    Question('unanchored_no_source', (Hypothesis('h', 'UNDECIDED'),)),
)

@dataclass(frozen=True)
class State:
    question: Question | None = None
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()

class Status:
    name = 'Status'
    reads = ('question',)
    writes = ('question', 'errors', 'warnings', 'inputs')
    mutation = ''

    def apply(self, question, state):
        wrong = self.mutation
        errors = [code for code in question.dangling
                  if not (wrong == 'ignore_trace' and ':trace:' in code) and not (wrong == 'ignore_logic' and ':logic:' in code)
                  and not (wrong == 'unanchored_evidence_passes' and code.startswith('evidence_not_in_source:logic:'))]
        if wrong != 'ignore_copy_drift': errors.extend(question.drifted)
        if wrong == 'status_ignores_library': errors.extend(f'dangling_anchor:logic:{anchor}' for anchor in question.library_anchors)
        known = {row.id for row in question.hypotheses}
        if wrong != 'dangling_gap_hypothesis_accepted':
            errors.extend(f'unknown_hypothesis:source:{gap}:{name}' for gap, names in question.gap_hypotheses for name in names if name not in known)
        if wrong == 'consistent_as_error' and not errors: errors.append('invented_error')
        warnings = []
        for row in question.hypotheses:
            if unused(row): (errors if wrong == 'warning_as_error' else warnings).append(f'hypothesis_unused:{row.id}')
        inputs = tuple(path for path in QUESTION_FILES if wrong != 'digest_omits_a_model' or path != 'trace.yaml')
        result = State(question, tuple(sorted(set(errors))), tuple(sorted(set(warnings))), inputs)
        yield FunctionResult(result, result, label=question.name)


def status_inputs(state, question):
    return '' if state.inputs == QUESTION_FILES else 'status must name every input file exactly once'

def unanchored_rule(state, question):
    if question.name == 'unanchored_source' and UNANCHORED_ERROR not in state.errors:
        return 'logic evidence without a source_id must be an error when a source model is listed'
    if question.name == 'unanchored_no_source' and any(code.startswith('evidence_not_in_source:') for code in state.errors):
        return 'without a source model, unanchored evidence is informational, not an error'

INVARIANTS = (
    Invariant('status_names_its_inputs', 'A status names every input file it read.', rule(status_inputs)),
    Invariant('consistent_tree_has_no_error', 'A tree without dangling references or drift has no error.', rule(consistent_tree)),
    Invariant('dangling_reference_is_an_error', 'Every dangling reference is an error.', rule(dangling_reference)),
    Invariant('unused_hypothesis_is_only_a_warning', 'A hypothesis no route uses only warns.', rule(unused_hypothesis)),
    Invariant('gap_names_known_hypotheses', 'A source gap may name only hypotheses of the question.', rule(gap_hypotheses)),
    Invariant('copied_content_matches_owner', 'Copied values that differ from their SourceGuard owner are errors.', rule(copied_content)),
    Invariant('library_anchors_are_resolved', 'Anchors resolved through the source library are not dangling.', rule(library_anchors)),
    Invariant('unanchored_evidence_is_an_error', 'When the folder lists a source model, logic evidence without a source anchor is an error; without a source model it is informational.', rule(unanchored_rule)),
)

MUTATIONS = {'digest_omits_a_model': 'status_names_its_inputs', 'ignore_trace': 'dangling_reference_is_an_error', 'ignore_logic': 'dangling_reference_is_an_error', 'consistent_as_error': 'consistent_tree_has_no_error', 'warning_as_error': 'unused_hypothesis_is_only_a_warning', 'ignore_copy_drift': 'copied_content_matches_owner', 'dangling_gap_hypothesis_accepted': 'gap_names_known_hypotheses', 'status_ignores_library': 'library_anchors_are_resolved', 'unanchored_evidence_passes': 'unanchored_evidence_is_an_error'}

def explorer(step):
    return Explorer(Workflow((step,)), (State(),), CASES + UNANCHORED_CASES, INVARIANTS, progress_steps=0)

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
    from researchguard.research import check_research_tree, status_main
    from tempfile import TemporaryDirectory
    import json
    modeled = {q.name: next(iter(Status().apply(q, State()))).new_state for q in CASES}
    for kind in ('consistent', 'trace', 'logic', 'unused'):
        index, models = native_case(kind)
        actual = check_research_tree(index, models)
        observe(kind, (tuple(actual['errors']), tuple(w for w in actual['warnings'] if w.startswith('hypothesis_unused:'))),
                (modeled[kind].errors, modeled[kind].warnings), modeled[kind])
    for kind, value in native_crossref().items(): observe(kind, value)
    unanchored = native_unanchored()
    observe('unanchored source errors', unanchored['with_source']['errors'], [UNANCHORED_ERROR])
    observe('unanchored without source errors', unanchored['without_source']['errors'], [])
    observe('unanchored without source info', 'evidence_unanchored:logic:E_reference' in unanchored['without_source']['info'])
    observe('anchored normal errors', unanchored['normal']['errors'], [])
    with TemporaryDirectory() as directory:
        output = Path(directory) / 'status.json'
        code = status_main([str(EVERGIVEN), '--json', '--output', str(output)])
        status = json.loads(output.read_text())
    observe('status_exit', code, 0)
    expected_paths = ('exp-obs1.json', 'experiment.json', 'logic.yaml', 'research.yaml', 'source.yaml', 'trace.yaml')
    expected_digests = [{'path': path, 'sha256': hashlib.sha256((EVERGIVEN / path).read_bytes()).hexdigest()} for path in expected_paths]
    observe('status_names_its_inputs', status.get('input_digests'), expected_digests)
    projected = project(status, '')
    state = State(projected.question, projected.errors, tuple(w for w in projected.warnings if w.startswith('hypothesis_unused:')), QUESTION_FILES)
    observe('live_crossref', not state.errors, state=state)

    for invariant in INVARIANTS:
        verdict = invariant.check(state, ())
        if not verdict.ok:
            violations.append(ConformanceViolation(step_index=1, rule_name='Status', message=f'evergiven: {invariant.name}: {verdict.message}'))

    from researchguard.research import _ResearchLibrary
    from researchguard.logic.source_library import SourceLibrary
    with TemporaryDirectory() as directory:
        root = Path(directory)
        paper = root / 'paper.txt'
        paper.write_text('Observed text')
        library = SourceLibrary(root / 'library')
        source = library.import_source(paper, title='Paper').source
        library.create_source_model(source.source_id, evidence='Observed text')
        paths = []
        tracked = _ResearchLibrary(library.root, paths)
        tracked.list_sources()
        tracked.source_node_ids(source.source_id)
        observe('status_library_inputs', set(paths), {library.source_index_path, library.source_model_path(source.source_id)})
    return ConformanceReport(ok=not violations, violations=tuple(violations), replayed_steps=tuple(observations),
                             summary='crossref: real functions and all unchanged rules replayed on the live Ever Given status.')
