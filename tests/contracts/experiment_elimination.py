"""Experiment elimination: observations eliminate contradicted hypotheses, misses are model misses, holdouts never eliminate."""
from dataclasses import dataclass
from itertools import combinations

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
    return any((table[pair[0]].get(item) is not None and table[pair[1]].get(item) is not None and (table[pair[0]][item] != table[pair[1]][item]) for item in selected))

def expected_Observe(trial, state, mutation=''):
    table = {name: dict(outcomes) for name, outcomes in trial.predictions}
    predicted = {(experiment, outcome) for outcomes in table.values() for experiment, outcome in outcomes.items()}
    construction = [(e, o) for e, o, role in trial.observations if role == 'construction' and (e, o) in predicted]
    holdouts = [(e, o) for e, o, role in trial.observations if role == 'holdout' and (e, o) in predicted]
    unexpected = [(e, o) for e, o, _ in trial.observations if (e, o) not in predicted]
    statuses = []
    for name in sorted(table):
        judged = construction + (holdouts if mutation == 'holdout_eliminates' else [])
        contradicted = [e for e, o in judged if table[name].get(e) is not None and table[name][e] != o]
        if contradicted and mutation != 'contradiction_ignored':
            status = 'eliminated'
        elif unexpected and mutation != 'model_miss_reported_consistent':
            status = 'model_miss'
        elif construction and all((table[name].get(e) == o for e, o in construction)):
            status = 'consistent'
        else:
            status = 'underdetermined'
        statuses.append((name, status))
    pairs = tuple(combinations(sorted(table), 2))
    candidates = experiments(trial)
    selected = ()
    for size in range(1, len(candidates) + 1):
        found = [chosen for chosen in combinations(candidates, size) if all((separates(chosen, pair, table) for pair in pairs))]
        if found:
            selected = found[0]
            break
    if mutation == 'recommendation_leaves_separable_pair':
        selected = candidates[:1]
    result = State(trial, tuple(statuses), selected)
    return result

def rule(check):

    def invariant(state):
        if state.trial is None:
            return True
        problem = check(state, state.trial, {name: dict(outcomes) for name, outcomes in state.trial.predictions})
        return False if problem else True
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
    if any(((e, o) not in predicted(table) for e, o, _ in trial.observations)):
        wrong = [name for name, status in state.statuses if status not in ('eliminated', 'model_miss')]
        if wrong:
            return f'an unexpected outcome left {wrong} without model_miss'

def holdout_rule(state, trial, table):
    construction = [(e, o) for e, o, role in trial.observations if role == 'construction' and (e, o) in predicted(table)]
    for name, status in state.statuses:
        if status == 'eliminated' and (not any((table[name].get(e) not in (None, o) for e, o in construction))):
            return f'{name} eliminated by a holdout observation only'

def recommendation_rule(state, trial, table):
    candidates = experiments(trial)
    left = [pair for pair in combinations(sorted(table), 2) if separates(candidates, pair, table) and (not separates(state.selected, pair, table))]
    return f'recommendation {state.selected} leaves separable pairs {left}' if left else None
RULES = (rule(contradiction_rule), rule(miss_rule), rule(holdout_rule), rule(recommendation_rule))
SPEC = (('h1', (('e1', 'up'), ('e2', 'hot'))), ('h2', (('e1', 'down'), ('e2', 'cold'))), ('h3', (('e1', 'up'), ('e2', 'cold'))))
CASES = (Trial('recommend', SPEC), Trial('eliminate', SPEC, (('e1', 'up', 'construction'),)), Trial('holdout', SPEC, (('e1', 'up', 'construction'), ('e2', 'cold', 'holdout'))), Trial('miss', SPEC, (('e1', 'sideways', 'construction'),)))
MUTATIONS = {'contradiction_ignored': 'contradicted_prediction_eliminates', 'model_miss_reported_consistent': 'unexpected_outcome_is_model_miss', 'holdout_eliminates': 'holdout_observation_never_eliminates', 'recommendation_leaves_separable_pair': 'recommendation_separates_every_separable_pair'}

def native_state(trial):
    """Run the real engine on the same finite spec and observations."""
    from researchguard.experiment import ExperimentObservation, ExperimentSpec, HypothesisPrediction, observe_experiments, recommend_experiments
    spec = ExperimentSpec(task_id='model', purpose='replay', coverage_ids=tuple((name for name, _ in trial.predictions)) + experiments(trial), assumptions=(), unknowns=(), iteration=0, max_iterations=4, hypothesis_predictions=tuple((HypothesisPrediction(name, dict(outcomes)) for name, outcomes in trial.predictions)), candidate_experiment_ids=experiments(trial))
    selected = recommend_experiments(spec).selected_experiment_ids
    statuses = ()
    if trial.observations:
        rows = tuple((ExperimentObservation(experiment_id=e, observed_outcome=o, evidence_id=f'evidence:{index}', source_ref=f'source:{index}', observed_at='2026-07-31T12:00:00+00:00', role=role, status='valid') for index, (e, o, role) in enumerate(trial.observations)))
        statuses = tuple(((row.hypothesis_id, row.status) for row in observe_experiments(spec, rows).hypothesis_dispositions))
    return State(trial, statuses, tuple(selected))

def assert_native_contract():
    observations, violations = ([], [])
    for trial in CASES:
        actual = native_state(trial)
        want = expected_Observe(trial, State())
        if actual.selected != want.selected or (trial.observations and actual.statuses != want.statuses):
            violations.append(f'{trial.name}: real {actual.statuses} {actual.selected} != model {want.statuses} {want.selected}')
        for invariant in RULES:
            verdict = invariant(actual)
            if not verdict:
                violations.append(f"{trial.name}: {invariant.__name__}: {'independent contract rejected the native observation'}")
    assert not violations, violations
RULE_NAMES = ('contradicted_prediction_eliminates', 'unexpected_outcome_is_model_miss', 'holdout_observation_never_eliminates', 'recommendation_separates_every_separable_pair')
