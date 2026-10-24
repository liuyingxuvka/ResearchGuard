"""Experiment elimination: observations eliminate contradicted hypotheses, misses are model misses, holdouts never eliminate."""
from dataclasses import dataclass
from itertools import combinations

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer

MODEL_ID = 'experiment_elimination'
PARENT = 'experimentguard'
COMPONENTS = ['experimentguard']
IMPLEMENTED_BY = {'Observe': 'src/researchguard/experiment/engine.py:observe_experiments',
                  'Recommend': 'src/researchguard/experiment/engine.py:recommend_experiments'}
TESTED_BY = {
    'contradicted_prediction_eliminates': ['tests/experiment/test_recommendation.py:test_real_observation_closes_only_with_independent_holdout',
                                           'tests/experiment/test_recommendation.py:test_eliminated_hypothesis_stays_eliminated_on_a_matrix_miss'],
    'unexpected_outcome_is_model_miss': ['tests/experiment/test_recommendation.py:test_zero_survivors_is_model_miss_and_never_closes'],
    'holdout_observation_never_eliminates': ['tests/experiment/test_recommendation.py:test_every_valid_holdout_counterexample_blocks_closure'],
    'recommendation_separates_every_separable_pair': ['tests/experiment/test_recommendation.py:test_recommends_all_tied_minimum_sets_deterministically',
                                                      'tests/experiment/test_recommendation.py:test_reports_indistinguishable_hypothesis_pairs'],
}


@dataclass(frozen=True)
class Trial:
    """A finite experiment spec and its observations: (experiment, outcome, construction|holdout)."""
    name: str
    predictions: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]
    observations: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True)
class State:
    trial: Trial | None = None
    statuses: tuple[tuple[str, str], ...] = ()
    selected: tuple[str, ...] = ()


def experiments(trial):
    return tuple(sorted({experiment for _, outcomes in trial.predictions for experiment, _ in outcomes}))


def separates(selected, pair, table):
    return any(table[pair[0]].get(item) is not None and table[pair[1]].get(item) is not None
               and table[pair[0]][item] != table[pair[1]][item] for item in selected)


class Observe:
    name = 'Observe'
    reads = ('trial',)
    writes = ('statuses', 'selected')
    mutation = ''

    def apply(self, trial, state):
        table = {name: dict(outcomes) for name, outcomes in trial.predictions}
        predicted = {(experiment, outcome) for outcomes in table.values() for experiment, outcome in outcomes.items()}
        construction = [(e, o) for e, o, role in trial.observations if role == 'construction' and (e, o) in predicted]
        holdouts = [(e, o) for e, o, role in trial.observations if role == 'holdout' and (e, o) in predicted]
        unexpected = [(e, o) for e, o, _ in trial.observations if (e, o) not in predicted]
        statuses = []
        for name in sorted(table):
            judged = construction + (holdouts if self.mutation == 'holdout_eliminates' else [])
            contradicted = [e for e, o in judged if table[name].get(e) is not None and table[name][e] != o]
            if contradicted and self.mutation != 'contradiction_ignored':
                status = 'eliminated'
            elif unexpected and self.mutation != 'model_miss_reported_consistent':
                status = 'model_miss'
            elif construction and all(table[name].get(e) == o for e, o in construction):
                status = 'consistent'
            else:
                status = 'underdetermined'
            statuses.append((name, status))
        pairs = tuple(combinations(sorted(table), 2))
        candidates = experiments(trial)
        selected = ()
        for size in range(1, len(candidates) + 1):
            found = [chosen for chosen in combinations(candidates, size) if all(separates(chosen, pair, table) for pair in pairs)]
            if found:
                selected = found[0]
                break
        if self.mutation == 'recommendation_leaves_separable_pair':
            selected = candidates[:1]
        result = State(trial, tuple(statuses), selected)
        yield FunctionResult(result, result, label=trial.name)


def rule(check):
    def invariant(state, trace):
        if state.trial is None:
            return InvariantResult.pass_()
        problem = check(state, state.trial, {name: dict(outcomes) for name, outcomes in state.trial.predictions})
        return InvariantResult.fail(problem) if problem else InvariantResult.pass_()
    return invariant


def predicted(table):
    return {(experiment, outcome) for outcomes in table.values() for experiment, outcome in outcomes.items()}


def contradiction_rule(state, trial, table):
    statuses = dict(state.statuses)
    for e, o, role in trial.observations:
        if role == 'construction' and (e, o) in predicted(table):
            wrong = [name for name in table if table[name].get(e) not in (None, o) and statuses.get(name) != 'eliminated']
            if wrong:
                return f'{wrong} contradicted by {e}={o} but not eliminated'


def miss_rule(state, trial, table):
    if any((e, o) not in predicted(table) for e, o, _ in trial.observations):
        wrong = [name for name, status in state.statuses if status not in ('eliminated', 'model_miss')]
        if wrong:
            return f'an unexpected outcome left {wrong} without model_miss'


def holdout_rule(state, trial, table):
    construction = [(e, o) for e, o, role in trial.observations if role == 'construction' and (e, o) in predicted(table)]
    for name, status in state.statuses:
        if status == 'eliminated' and not any(table[name].get(e) not in (None, o) for e, o in construction):
            return f'{name} eliminated by a holdout observation only'


def recommendation_rule(state, trial, table):
    candidates = experiments(trial)
    left = [pair for pair in combinations(sorted(table), 2) if separates(candidates, pair, table) and not separates(state.selected, pair, table)]
    return f'recommendation {state.selected} leaves separable pairs {left}' if left else None


INVARIANTS = (
    Invariant('contradicted_prediction_eliminates', 'A valid construction observation eliminates every hypothesis it contradicts.', rule(contradiction_rule)),
    Invariant('unexpected_outcome_is_model_miss', 'An outcome no hypothesis predicted makes the survivors model misses.', rule(miss_rule)),
    Invariant('holdout_observation_never_eliminates', 'Holdout observations never eliminate a hypothesis.', rule(holdout_rule)),
    Invariant('recommendation_separates_every_separable_pair', 'The recommended set separates every pair the candidates can separate.', rule(recommendation_rule)),
)
SPEC = (('h1', (('e1', 'up'), ('e2', 'hot'))), ('h2', (('e1', 'down'), ('e2', 'cold'))), ('h3', (('e1', 'up'), ('e2', 'cold'))))
CASES = (
    Trial('recommend', SPEC),
    Trial('eliminate', SPEC, (('e1', 'up', 'construction'),)),
    Trial('holdout', SPEC, (('e1', 'up', 'construction'), ('e2', 'cold', 'holdout'))),
    Trial('miss', SPEC, (('e1', 'sideways', 'construction'),)),
)
MUTATIONS = {
    'contradiction_ignored': 'contradicted_prediction_eliminates',
    'model_miss_reported_consistent': 'unexpected_outcome_is_model_miss',
    'holdout_eliminates': 'holdout_observation_never_eliminates',
    'recommendation_leaves_separable_pair': 'recommendation_separates_every_separable_pair',
}


def explorer(step):
    return Explorer(Workflow((step,)), (State(),), CASES, INVARIANTS, progress_steps=0)


def build_explorer():
    return explorer(Observe())


def broken_variants():
    result = {}
    for name in MUTATIONS:
        step = Observe()
        step.mutation = name
        result[name] = explorer(step)
    return result


def native_state(trial):
    """Run the real engine on the same finite spec and observations."""
    from researchguard.experiment import ExperimentObservation, ExperimentSpec, HypothesisPrediction, observe_experiments, recommend_experiments
    spec = ExperimentSpec(task_id='model', purpose='replay', coverage_ids=tuple(name for name, _ in trial.predictions) + experiments(trial),
                          assumptions=(), unknowns=(), iteration=0, max_iterations=4,
                          hypothesis_predictions=tuple(HypothesisPrediction(name, dict(outcomes)) for name, outcomes in trial.predictions),
                          candidate_experiment_ids=experiments(trial))
    selected = recommend_experiments(spec).selected_experiment_ids
    statuses = ()
    if trial.observations:
        rows = tuple(ExperimentObservation(experiment_id=e, observed_outcome=o, evidence_id=f'evidence:{index}', source_ref=f'source:{index}',
                                           observed_at='2026-07-31T12:00:00+00:00', role=role, status='valid')
                     for index, (e, o, role) in enumerate(trial.observations))
        statuses = tuple((row.hypothesis_id, row.status) for row in observe_experiments(spec, rows).hypothesis_dispositions)
    return State(trial, statuses, tuple(selected))


def conformance():
    from flowguard.conformance import ConformanceReport, ConformanceViolation
    from flowguard.replay import ReplayObservation
    observations, violations = [], []
    for trial in CASES:
        actual = native_state(trial)
        want = next(iter(Observe().apply(trial, State()))).new_state
        observations.append(ReplayObservation('Observe', actual.statuses, actual))
        if actual.selected != want.selected or (trial.observations and actual.statuses != want.statuses):
            violations.append(ConformanceViolation(step_index=1, rule_name='Observe',
                                                   message=f'{trial.name}: real {actual.statuses} {actual.selected} != model {want.statuses} {want.selected}'))
        for invariant in INVARIANTS:
            verdict = invariant.check(actual, ())
            if not verdict.ok:
                violations.append(ConformanceViolation(step_index=1, rule_name='Observe', message=f'{trial.name}: {invariant.name}: {verdict.message}'))
    return ConformanceReport(ok=not violations, violations=tuple(violations), replayed_steps=tuple(observations),
                             summary='The real recommender and observation engine run on the same finite specs as the model cases.')
