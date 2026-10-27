"""research_ablations: one independent aspect of the question status."""

from dataclasses import dataclass

from pathlib import Path

import sys

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow

from flowguard.explorer import Explorer

from _research_cases import (Hypothesis, Ablation, Question, excluded, accepted, unused, route_conflicts, rule, unknown_gap_hypotheses, consistent_tree, dangling_reference, unused_hypothesis, gap_hypotheses, copied_content, library_anchors, routes_contradict, every_ablation, trace_depth_agrees, verdict_routes, live_hypotheses, directions_rule, view_rule, candidate_rule, contested_rule, CASES, native_case, project, trace_depth_answers, REPO_ROOT, EVERGIVEN, native_crossref, native_ablations, native_verdict, native_views)

MODEL_ID = 'research_ablations'

PARENT = 'research-tree'

IMPLEMENTED_BY = {'Ablations': 'src/researchguard/research.py:apply_ablations'}

USES = {'Sensitivity': 'src/researchguard/trace/storyline_depth.py:expected_sensitivity_matches'}

TESTED_BY = {'every_ablation_is_caught_or_named': ['tests/test_research_ablations.py:test_ablation_nobody_uses_is_named'], 'ablation_agrees_with_trace_depth': ['tests/test_research_ablations.py:test_trace_ablation_agrees_with_trace_depth', 'tests/test_research_ablations.py:test_ablation_rows_name_side_effects']}

@dataclass(frozen=True)
class State:
    question: Question | None = None
    ablations: tuple[tuple[str, tuple[str, ...]], ...] = ()
    warnings: tuple[str, ...] = ()

class Status:
    name = 'Status'
    reads = ('question',)
    writes = ('question', 'ablations', 'warnings')
    mutation = ''

    def apply(self, question, state):
        wrong = self.mutation
        ablations = []
        for row in question.ablations:
            trace = row.second_measure() if wrong == 'ablation_uses_a_second_sensitivity' else row.trace_check
            caught = tuple(route for route, moved in (('logic', row.logic_moved), ('trace', trace)) if moved)
            if not (wrong == 'drop_uncaught_ablations' and not caught): ablations.append((row.id, caught))
        warnings = tuple(sorted(set(f'ablation_not_caught:{name}' for name, caught in ablations if not caught)))
        result = State(question, tuple(ablations), warnings)
        yield FunctionResult(result, result, label=question.name)


INVARIANTS = (
    Invariant('every_ablation_is_caught_or_named', 'Every declared ablation has a row and uncaught ones are named.', rule(every_ablation)),
    Invariant('ablation_agrees_with_trace_depth', 'A trace-declared ablation is caught by trace exactly when trace depth passes its expected sensitivity.', rule(trace_depth_agrees)),
)

MUTATIONS = {'drop_uncaught_ablations': 'every_ablation_is_caught_or_named', 'ablation_uses_a_second_sensitivity': 'ablation_agrees_with_trace_depth'}

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
    for kind, value in native_ablations().items(): observe(kind, value)
    tree = load_research(EVERGIVEN)
    status = research_status(tree)
    projected = project(status, '', trace_depth_answers(tree.models['trace']))
    state = State(projected.question, projected.ablations, tuple(w for w in projected.warnings if w.startswith('ablation_not_caught:')))
    observe('declared_ablations', bool(status['ablations']) and all(row['caught_by'] for row in status['ablations']), state=state)

    for invariant in INVARIANTS:
        verdict = invariant.check(state, ())
        if not verdict.ok:
            violations.append(ConformanceViolation(step_index=1, rule_name='Status', message=f'evergiven: {invariant.name}: {verdict.message}'))

    return ConformanceReport(ok=not violations, violations=tuple(violations), replayed_steps=tuple(observations),
                             summary='ablations: real functions and all unchanged rules replayed on the live Ever Given status.')
