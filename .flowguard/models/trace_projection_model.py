"""Trace projection: live and rank follow support, links never inflate support, and sensitivity reads snapshot scores."""
from dataclasses import dataclass, replace
from pathlib import Path

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer

MODEL_ID = 'trace_projection'
PARENT = 'traceguard'
COMPONENTS = ['traceguard']
IMPLEMENTED_BY = {'Project': 'src/researchguard/trace/inference/projection.py:project_hypotheses',
                  'Evaluate': 'src/researchguard/trace/evaluator.py:evaluate_model',
                  'Sensitivity': 'src/researchguard/trace/storyline_depth.py:expected_sensitivity_matches'}
TESTED_BY = {
    'live_within_margin_of_best': ['tests/trace/test_inference_kernel.py:test_live_hypotheses_lie_within_the_margin_of_the_best',
                                   'tests/trace/test_storyline_depth.py:test_live_alternatives_exclude_the_leader'],
    'rank_follows_support': ['tests/trace/test_inference_kernel.py:test_better_supported_alternative_ranks_first',
                             'tests/trace/test_inference_kernel.py:test_live_hypotheses_lie_within_the_margin_of_the_best'],
    'causal_and_oppose_links_never_raise_support': ['tests/trace/test_inference_kernel.py:test_causal_declaration_never_raises_storyline_support',
                                                    'tests/trace/test_inference_kernel.py:test_opposition_lowers_support'],
    'expected_sensitivity_uses_snapshot_score': ['tests/trace/test_storyline_depth.py:test_expected_sensitivity_must_match_same_engine_support_effect'],
}
MARGIN = 0.12


@dataclass(frozen=True)
class Story:
    """Inputs of one projection: solved support per hypothesis, support without oppose or causal links, one sensitivity."""
    name: str
    support: tuple[tuple[str, float], ...]
    without_links: tuple[tuple[str, float], ...] = ()   # support the same hypothesis gets with its oppose/causal links removed
    score_delta: float = 0.0       # snapshot score change under the declared perturbation
    support_delta: float = 0.0     # projection support change under the same perturbation
    minimum: float = 0.05          # the sensitivity's declared minimum absolute decrease
    margin: float = MARGIN


@dataclass(frozen=True)
class State:
    story: Story | None = None
    support: tuple[tuple[str, float], ...] = ()
    ranks: tuple[tuple[str, int], ...] = ()
    live: tuple[str, ...] = ()
    sensitivity_matched: bool = False


class Project:
    name = 'Project'
    reads = ('story',)
    writes = ('support', 'ranks', 'live', 'sensitivity_matched')
    mutation = ''

    def apply(self, story, state):
        support = dict(story.support)
        if self.mutation == 'oppose_link_raises_support':
            support = {key: value + 0.1 if key in dict(story.without_links) else value for key, value in support.items()}
        order = sorted(support, key=(lambda key: key) if self.mutation == 'rank_ignores_support' else (lambda key: (-support[key], key)))
        best = max(support.values(), default=0.0)
        live = tuple(key for key in order if self.mutation == 'live_ignores_margin' or best - support[key] <= story.margin)
        delta = story.support_delta if self.mutation == 'sensitivity_on_projection_support' else story.score_delta
        matched = delta < 0 and abs(delta) >= story.minimum
        result = State(story, tuple(sorted(support.items())), tuple((key, index + 1) for index, key in enumerate(order)), live, matched)
        yield FunctionResult(result, result, label=story.name)


def rule(check):
    def invariant(state, trace):
        if state.story is None:
            return InvariantResult.pass_()
        problem = check(state, state.story)
        return InvariantResult.fail(problem) if problem else InvariantResult.pass_()
    return invariant


def live_rule(state, story):
    support = dict(state.support)
    best = max(support.values(), default=0.0)
    want = {key for key, value in support.items() if best - value <= story.margin + 1e-9}
    if set(state.live) != want:
        return f'live {sorted(state.live)} != within margin {sorted(want)}'


def rank_rule(state, story):
    support = dict(state.support)
    ordered = [key for key, _ in sorted(state.ranks, key=lambda row: row[1])]
    if ordered != sorted(support, key=lambda key: (-support[key], key)):
        return f'rank order {ordered} does not follow support'


def links_rule(state, story):
    support = dict(state.support)
    raised = [key for key, without in story.without_links if support.get(key, 0.0) > without + 0.001]
    return f'oppose or causal links raised support of {raised}' if raised else None


def sensitivity_rule(state, story):
    want = story.score_delta < 0 and abs(story.score_delta) >= story.minimum
    if state.sensitivity_matched != want:
        return f'sensitivity matched={state.sensitivity_matched}; the snapshot score change {story.score_delta} says {want}'


INVARIANTS = (
    Invariant('live_within_margin_of_best', 'A hypothesis is live exactly when its support is within the margin of the best.', rule(live_rule)),
    Invariant('rank_follows_support', 'Ranks follow support, ties by id.', rule(rank_rule)),
    Invariant('causal_and_oppose_links_never_raise_support', 'Causal declarations and oppose links never raise support.', rule(links_rule)),
    Invariant('expected_sensitivity_uses_snapshot_score', 'An expected decrease is judged on the snapshot score change and its declared minimum.', rule(sensitivity_rule)),
)
CASES = (
    Story('spread', (('h_a', 0.3), ('h_b', 0.5), ('h_c', 0.6)), without_links=(('h_b', 0.55), ('h_c', 0.6)),
          score_delta=-0.06, support_delta=-0.01),
    Story('close_call', (('h_a', 0.45), ('h_b', 0.41)), without_links=(('h_a', 0.45),), score_delta=-0.04, support_delta=-0.08),
)
MUTATIONS = {
    'live_ignores_margin': 'live_within_margin_of_best',
    'rank_ignores_support': 'rank_follows_support',
    'oppose_link_raises_support': 'causal_and_oppose_links_never_raise_support',
    'sensitivity_on_projection_support': 'expected_sensitivity_uses_snapshot_score',
}


def explorer(step):
    return Explorer(Workflow((step,)), (State(),), CASES, INVARIANTS, progress_steps=0)


def build_explorer():
    return explorer(Project())


def broken_variants():
    result = {}
    for name in MUTATIONS:
        step = Project()
        step.mutation = name
        result[name] = explorer(step)
    return result


def native_states():
    """Project real evaluations of the Ever Given trace models into the abstract state."""
    from researchguard.trace.evaluator import evaluate_model
    from researchguard.trace.inference.policy import InferencePolicy
    from researchguard.trace.loader import load_model
    from researchguard.trace.storyline_depth import PerturbationPlanItem, expected_sensitivity_matches, run_single_perturbation
    root = Path(__file__).resolve().parents[2]
    margin = InferencePolicy().alternative_live_margin
    states = []
    for path in (root / 'examples/research/evergiven/trace.yaml', root / 'tests/trace/fixtures/evergiven/tr_v2b.yaml',
                 root / 'tests/trace/fixtures/evergiven/tr_v1.yaml'):
        model = load_model(path)
        result = evaluate_model(model)
        rows = result.inference.hypothesis_projections
        plain = replace(model, causal_candidates=(),
                        hypothesis_evidence_links=tuple(link for link in model.hypothesis_evidence_links if link.polarity != 'oppose'))
        without = {row.hypothesis_id: row.support for row in evaluate_model(plain).inference.hypothesis_projections}
        story = Story(path.stem, tuple((row.hypothesis_id, row.support) for row in rows), tuple(without.items()), margin=margin)
        states.append(State(story, tuple(sorted((row.hypothesis_id, row.support) for row in rows)),
                            tuple((row.hypothesis_id, row.rank) for row in rows), tuple(row.hypothesis_id for row in rows if row.live)))
    model = load_model(root / 'examples/research/evergiven/trace.yaml')
    baseline = evaluate_model(model, include_storyline_depth=True)
    plan = PerturbationPlanItem(perturbation_id='expected_sensitivity:sens_no_unctad', kind='expected_sensitivity', target_hypothesis_id='h_demand',
                                declared_perturbation_id='abl_no_unctad', expected_sensitivity_id='sens_no_unctad')
    effect, _, perturbed = run_single_perturbation(model, baseline, plan)
    score = effect.deltas['h_demand']['score']['delta']
    support = {row.hypothesis_id: row.support for row in perturbed.inference.hypothesis_projections}['h_demand'] - \
        {row.hypothesis_id: row.support for row in baseline.inference.hypothesis_projections}['h_demand']
    for minimum in (0.05, 0.0):
        sensitivities = tuple(replace(row, minimum_absolute_change=minimum) if row.sensitivity_id == 'sens_no_unctad' else row
                              for row in model.expected_sensitivities)
        matched = expected_sensitivity_matches(replace(model, expected_sensitivities=sensitivities), effect)
        story = Story(f'sensitivity_{minimum}', (), score_delta=score, support_delta=support, minimum=minimum)
        states.append(State(story, sensitivity_matched=matched))
    return states


def conformance():
    from flowguard.conformance import ConformanceReport, ConformanceViolation
    from flowguard.replay import ReplayObservation
    observations, violations = [], []
    for state in native_states():
        observations.append(ReplayObservation('Project', state.story.name, state))
        for invariant in INVARIANTS:
            verdict = invariant.check(state, ())
            if not verdict.ok:
                violations.append(ConformanceViolation(step_index=1, rule_name='Project', message=f'{state.story.name}: {invariant.name}: {verdict.message}'))
    return ConformanceReport(ok=not violations, violations=tuple(violations), replayed_steps=tuple(observations),
                             summary='Real trace evaluations (Ever Given example and fixtures) and the real expected-sensitivity check projected onto the rules.')
