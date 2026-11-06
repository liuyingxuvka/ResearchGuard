"""Trace projection: live and rank follow support, links never inflate support, and sensitivity reads snapshot scores."""
from dataclasses import dataclass, replace
from pathlib import Path
MARGIN = 0.12

@dataclass(frozen=True)
class Story:
    """Inputs of one projection: solved support per hypothesis, support without oppose or causal links, one sensitivity."""
    name: str
    support: tuple[tuple[str, float], ...]
    without_links: tuple[tuple[str, float], ...] = ()
    score_delta: float = 0.0
    support_delta: float = 0.0
    minimum: float = 0.05
    margin: float = MARGIN

@dataclass(frozen=True)
class State:
    story: Story | None = None
    support: tuple[tuple[str, float], ...] = ()
    ranks: tuple[tuple[str, int], ...] = ()
    live: tuple[str, ...] = ()
    sensitivity_matched: bool = False

def expected_Project(story, state, mutation=''):
    support = dict(story.support)
    if mutation == 'oppose_link_raises_support':
        support = {key: value + 0.1 if key in dict(story.without_links) else value for key, value in support.items()}
    order = sorted(support, key=(lambda key: key) if mutation == 'rank_ignores_support' else lambda key: (-support[key], key))
    best = max(support.values(), default=0.0)
    live = tuple((key for key in order if mutation == 'live_ignores_margin' or best - support[key] <= story.margin))
    delta = story.support_delta if mutation == 'sensitivity_on_projection_support' else story.score_delta
    matched = delta < 0 and abs(delta) >= story.minimum
    result = State(story, tuple(sorted(support.items())), tuple(((key, index + 1) for index, key in enumerate(order))), live, matched)
    return result

def rule(check):

    def invariant(state):
        if state.story is None:
            return True
        problem = check(state, state.story)
        return False if problem else True
    return invariant

def live_rule(state, story):
    support = dict(state.support)
    best = max(support.values(), default=0.0)
    want = {key for key, value in support.items() if best - value <= story.margin + 1e-09}
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
RULES = (rule(live_rule), rule(rank_rule), rule(links_rule), rule(sensitivity_rule))
CASES = (Story('spread', (('h_a', 0.3), ('h_b', 0.5), ('h_c', 0.6)), without_links=(('h_b', 0.55), ('h_c', 0.6)), score_delta=-0.06, support_delta=-0.01), Story('close_call', (('h_a', 0.45), ('h_b', 0.41)), without_links=(('h_a', 0.45),), score_delta=-0.04, support_delta=-0.08))
MUTATIONS = {'live_ignores_margin': 'live_within_margin_of_best', 'rank_ignores_support': 'rank_follows_support', 'oppose_link_raises_support': 'causal_and_oppose_links_never_raise_support', 'sensitivity_on_projection_support': 'expected_sensitivity_uses_snapshot_score'}

def native_states():
    """Project real evaluations of the Ever Given trace models into the abstract state."""
    from researchguard.trace.evaluator import evaluate_model
    from researchguard.trace.inference.policy import InferencePolicy
    from researchguard.trace.loader import load_model
    from researchguard.trace.storyline_depth import PerturbationPlanItem, expected_sensitivity_matches, run_single_perturbation
    root = Path(__file__).resolve().parents[2]
    margin = InferencePolicy().alternative_live_margin
    states = []
    for path in (root / 'examples/research/evergiven/trace.yaml', root / 'tests/trace/fixtures/evergiven/tr_v2b.yaml', root / 'tests/trace/fixtures/evergiven/tr_v1.yaml'):
        model = load_model(path)
        result = evaluate_model(model)
        rows = result.inference.hypothesis_projections
        plain = replace(model, causal_candidates=(), hypothesis_evidence_links=tuple((link for link in model.hypothesis_evidence_links if link.polarity != 'oppose')))
        without = {row.hypothesis_id: row.support for row in evaluate_model(plain).inference.hypothesis_projections}
        story = Story(path.stem, tuple(((row.hypothesis_id, row.support) for row in rows)), tuple(without.items()), margin=margin)
        states.append(State(story, tuple(sorted(((row.hypothesis_id, row.support) for row in rows))), tuple(((row.hypothesis_id, row.rank) for row in rows)), tuple((row.hypothesis_id for row in rows if row.live))))
    model = load_model(root / 'examples/research/evergiven/trace.yaml')
    baseline = evaluate_model(model, include_storyline_depth=True)
    plan = PerturbationPlanItem(perturbation_id='expected_sensitivity:sens_no_unctad', kind='expected_sensitivity', target_hypothesis_id='h_demand', declared_perturbation_id='abl_no_unctad', expected_sensitivity_id='sens_no_unctad')
    effect, _, perturbed = run_single_perturbation(model, baseline, plan)
    score = effect.deltas['h_demand']['score']['delta']
    support = {row.hypothesis_id: row.support for row in perturbed.inference.hypothesis_projections}['h_demand'] - {row.hypothesis_id: row.support for row in baseline.inference.hypothesis_projections}['h_demand']
    for minimum in (0.05, 0.0):
        sensitivities = tuple((replace(row, minimum_absolute_change=minimum) if row.sensitivity_id == 'sens_no_unctad' else row for row in model.expected_sensitivities))
        matched = expected_sensitivity_matches(replace(model, expected_sensitivities=sensitivities), effect)
        story = Story(f'sensitivity_{minimum}', (), score_delta=score, support_delta=support, minimum=minimum)
        states.append(State(story, sensitivity_matched=matched))
    return states

def assert_native_contract():
    observations, violations = ([], [])
    for state in native_states():
        for invariant in RULES:
            verdict = invariant(state)
            if not verdict:
                violations.append(f"{state.story.name}: {invariant.__name__}: {'independent contract rejected the native observation'}")
    assert not violations, violations
RULE_NAMES = ('live_within_margin_of_best', 'rank_follows_support', 'causal_and_oppose_links_never_raise_support', 'expected_sensitivity_uses_snapshot_score')
