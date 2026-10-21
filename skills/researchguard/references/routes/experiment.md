# ExperimentGuard

## Purpose

ExperimentGuard turns explicit hypotheses, candidate experiments, and predicted
outcomes into a recommendation-only discriminating set.

## Route Scope

Own deterministic minimum-set recommendation for caller-declared hypotheses. Do
not execute experiments, decide causal truth, or replace another member.

## Local Material Routing

Native recommendations use the experiment spec only.

## Route Acceptance Map

- Require unique hypothesis IDs, a finite experiment inventory, and explicit
  comparable predictions.
- Task-local iteration may add a task id, an iteration bound and the previous
  open gaps; every other loop field is optional.
- Missing declarations, valid observations, or holdout evidence remain visible
  as unresolved; never guess them.
- A sibling member is never a retry.

## Use When

Use this route when at least two concrete hypotheses need one or more declared
experiments that distinguish them.

## Do Not Use When

Do not execute an experiment, invent outcomes or probabilities, infer causal
truth, search for sources, reconstruct a timeline, or license an argument.
Use the matching ResearchGuard route for those requests.

## Required Inputs

Require unique hypothesis IDs, a finite candidate inventory, and a declared
outcome for each hypothesis/experiment relationship used for discrimination.
Missing declarations stay visible. Minimal spec (all other fields are optional):

```json
{
  "hypothesis_predictions": [
    {"hypothesis_id": "h1", "outcomes_by_experiment": {"e1": "up", "e2": "up"}},
    {"hypothesis_id": "h2", "outcomes_by_experiment": {"e1": "down", "e2": "up"}},
    {"hypothesis_id": "h3", "outcomes_by_experiment": {"e1": "up", "e2": "down"}}
  ],
  "candidate_experiment_ids": ["e1", "e2"]
}
```

## Required Workflow

1. Freeze hypotheses, candidate experiments, and predictions.
2. Validate explicit, comparable predictions.
3. Find every minimum-cardinality set distinguishing each hypothesis pair.
4. Return the deterministic first recommendation, tied sets, and unresolved
   pairs.
5. State the claim boundary and keep the result recommendation-only.

## Hard Gates

- Never invent hypotheses, outcomes, probabilities, results, or evidence.
- Every selected or tied set must distinguish every declared pair within the
  finite bound; unresolved pairs remain visible.
- `invalid` and `not_run` observations create gaps. A holdout observation is
  optional; a holdout that contradicts the one survivor keeps the task open.
- Zero survivors are a prediction-matrix miss requiring an immutable revision
  candidate and new iteration, never a silent rewrite or success.
- Recommendation status proves only finite-prediction discrimination.

## Conditional Task-Local Experiment Iteration

Trigger the loop for a larger task, a real observation, a matrix miss, an
addressable gap, or requested predictive closure. Freeze the hypotheses,
candidate experiments and predicted outcomes in the spec before observing. Each
observation carries an evidence ID, source, time, construction or holdout role,
and `valid`, `invalid`, or `not_run` status. Invalid and not-run evidence create
visible gaps.

With valid observations, compute dispositions and rebuild the minimum set.
Zero survivors emit an immutable revision candidate and require a new iteration.
One survivor closes unless a holdout observation contradicts it. Record gap
lineage, next experiments and terminal reason; on the next round put the open
gaps into `prior_open_gap_ids`. Continue to `model_closed_for_task`, or stop
with `iteration_limit`, `progress_stalled`, or `external_input_required`.

## Local Route

Use `researchguard experiment recommend <spec.json>`; apply observations with
`researchguard experiment observe <spec.json> <observations.json>`. Never invoke
a sibling after failure.

## Output Requirements

Return the native result, evidence and claim boundary, blockers and next action.
Include full JSON only when it is needed or requested.
