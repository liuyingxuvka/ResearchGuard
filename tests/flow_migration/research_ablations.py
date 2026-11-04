"""research_ablations: one independent aspect of the question status."""
from dataclasses import dataclass
from pathlib import Path
import sys
from ._research_cases import Hypothesis, Ablation, Question, excluded, accepted, unused, route_conflicts, rule, unknown_gap_hypotheses, consistent_tree, dangling_reference, unused_hypothesis, gap_hypotheses, copied_content, library_anchors, routes_contradict, every_ablation, trace_depth_agrees, verdict_routes, live_hypotheses, directions_rule, view_rule, candidate_rule, contested_rule, CASES, native_case, project, trace_depth_answers, REPO_ROOT, EVERGIVEN, native_crossref, native_ablations, native_verdict, native_views

@dataclass(frozen=True)
class State:
    question: Question | None = None
    ablations: tuple[tuple[str, tuple[str, ...]], ...] = ()
    warnings: tuple[str, ...] = ()

def expected_Status(question, state, mutation=''):
    wrong = mutation
    ablations = []
    for row in question.ablations:
        trace = row.second_measure() if wrong == 'ablation_uses_a_second_sensitivity' else row.trace_check
        caught = tuple((route for route, moved in (('logic', row.logic_moved), ('trace', trace)) if moved))
        if not (wrong == 'drop_uncaught_ablations' and (not caught)):
            ablations.append((row.id, caught))
    warnings = tuple(sorted(set((f'ablation_not_caught:{name}' for name, caught in ablations if not caught))))
    result = State(question, tuple(ablations), warnings)
    return result
RULES = (rule(every_ablation), rule(trace_depth_agrees))
MUTATIONS = {'drop_uncaught_ablations': 'every_ablation_is_caught_or_named', 'ablation_uses_a_second_sensitivity': 'ablation_agrees_with_trace_depth'}

def assert_native_contract():
    from researchguard.research import load_research, research_status
    observations, violations = ([], [])

    def observe(label, actual, want=True, state=None):
        if actual != want:
            violations.append(f'{label}: {actual!r} != {want!r}')
    for kind, value in native_ablations().items():
        observe(kind, value)
    tree = load_research(EVERGIVEN)
    status = research_status(tree)
    projected = project(status, '', trace_depth_answers(tree.models['trace']))
    state = State(projected.question, projected.ablations, tuple((w for w in projected.warnings if w.startswith('ablation_not_caught:'))))
    observe('declared_ablations', bool(status['ablations']) and all((row['caught_by'] for row in status['ablations'])), state=state)
    for invariant in RULES:
        verdict = invariant(state)
        if not verdict:
            violations.append(f"evergiven: {invariant.__name__}: {'independent contract rejected the native observation'}")
    assert not violations, violations
RULE_NAMES = ('every_ablation_is_caught_or_named', 'ablation_agrees_with_trace_depth')
