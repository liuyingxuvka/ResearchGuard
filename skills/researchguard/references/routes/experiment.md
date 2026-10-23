# ExperimentGuard

Recommend finite experiment sets that distinguish caller-declared hypotheses.
Discrimination is structural and recommendation-only.

## Use / do not use

Use when at least two explicit hypotheses predict outcomes for a finite inventory.
Do not execute experiments, invent outcomes/probabilities, decide causal truth,
discover sources, reconstruct timelines or license arguments. Hand off to that owner.

## Command order

Freeze the spec before observing, then run:

```text
researchguard experiment recommend <spec.json>
researchguard experiment observe <spec.json> <observations.json>
```

Apply real observations and update the next spec's iteration/prior gaps explicitly;
never rewrite the frozen prediction matrix after seeing a result.

## Fields and examples

A spec needs unique hypothesis IDs, candidate IDs and each hypothesis's predicted
outcome for every candidate. Minimal spec:

```json
{"hypothesis_predictions": [
  {"hypothesis_id": "h1", "outcomes_by_experiment": {"e1": "up"}},
  {"hypothesis_id": "h2", "outcomes_by_experiment": {"e1": "down"}}],
 "candidate_experiment_ids": ["e1"]}
```

Optional task fields: `task_id`, `purpose`, `coverage_ids`, `assumptions`, `unknowns`,
`iteration` (0), `max_iterations` (1), `prior_open_gap_ids` ([]), and
`maximum_experiment_count` (unset). Require comparable declarations; never guess them.

Observations are a list or `{"observations": [...]}`. Required row fields:
`experiment_id`, `observed_outcome` (nonempty when valid), `evidence_id`, `source_ref`,
`observed_at`, `role` (`construction` or `holdout`). `status` defaults to `valid`;
values: `valid`, `invalid`, `not_run`. Optional `observation_port_id` and
`outcome_port_id` default to empty strings.

```json
{"observations": [{"experiment_id": "e1", "observed_outcome": "up",
 "evidence_id": "measurement-1", "source_ref": "lab-notebook:page-1",
 "observed_at": "2026-10-21T12:00:00Z", "role": "construction"}]}
```

## Hard rules and stops

Every selected/tied set must distinguish all declared pairs within the finite bound.
Return the deterministic minimum-cardinality recommendation and unresolved pairs.
Invalid/not-run observations create gaps. Holdout evidence is optional; any supplied
counterexample keeps closure blocked. Zero survivors require a visible matrix-revision
candidate and a new iteration, never silent success. A sibling is never a retry.

`model_closed_for_task` closes only a uniquely consistent hypothesis without gaps or
holdout counterexamples. For `iteration_limit`, report the bound; for
`progress_stalled`, stop with the unchanged gaps; for `external_input_required`,
obtain the named external observation. Otherwise continue the concrete next experiment
recommendation and retain gap lineage, dispositions and terminal reason.
