# ExperimentGuard

Recommend finite sets that distinguish caller-declared hypotheses structurally.

## Use / do not use

Use for at least two hypotheses predicting outcomes for a finite inventory.
Do not execute experiments, invent outcomes/probabilities, decide causal truth,
discover sources, reconstruct timelines or license arguments; hand off to that owner.

## Command order

Freeze the spec before observing:

```text
researchguard experiment recommend <spec.json>
researchguard experiment observe <spec.json> <observations.json>
```

Apply real observations; explicitly update the next spec's iteration/prior gaps.
Never rewrite the frozen matrix after seeing a result.

## Fields and examples

Require unique hypothesis/candidate IDs and every hypothesis's prediction for
every candidate. Do not guess comparable declarations. Minimal spec:

```json
{"hypothesis_predictions": [
  {"hypothesis_id": "h1", "outcomes_by_experiment": {"e1": "up"}},
  {"hypothesis_id": "h2", "outcomes_by_experiment": {"e1": "down"}}],
 "candidate_experiment_ids": ["e1"]}
```

Optional: `task_id`, `purpose`, `coverage_ids`, `assumptions`, `unknowns`,
`iteration` (0), `max_iterations` (1), `prior_open_gap_ids` ([]),
`maximum_experiment_count` (unset).

Optional `cost_by_experiment` maps candidate IDs to nonnegative finite numbers,
excluding booleans; unknown IDs are rejected. Absence keeps minimum cardinality.
An explicit `{}` enables cost mode: omitted candidate costs default to 1, and at
most 16 candidates are allowed. Within `maximum_experiment_count`, choose by
sum cost, then count, then IDs. Without costs, retain count then IDs and existing
limits. `alternative_minimal_sets` excludes the selected set.

Observations are a list or `{"observations": [...]}`. Required: `experiment_id`,
`observed_outcome` (nonempty when valid), `evidence_id`, `source_ref`, `observed_at`,
`role` (`construction` or `holdout`). `status` defaults to `valid`; also accepts
`invalid`, `not_run`. Legacy port keys are ignored on input and no longer emitted.

## Hard rules and stops

Every selected/tied set must distinguish all declared pairs within the bound;
retain unresolved pairs. Invalid/not-run observations create gaps. Holdout is
optional; every supplied valid counterexample blocks closure. Valid construction
counterevidence keeps a hypothesis `eliminated` even when another observation
misses the matrix; otherwise that miss gives `model_miss`. Zero survivors require
a visible, unapplied matrix-revision candidate and never close. A sibling is not a retry.

`model_closed_for_task` needs one consistent hypothesis, no gaps or holdout conflicts.
For `iteration_limit`, report the bound; `progress_stalled`, stop with unchanged
gaps; `external_input_required`, obtain the named observation. Otherwise continue
the concrete next experiment, retaining gap lineage, dispositions and terminal reason.

The loop uses the shared identity, terminal and gap-lineage kernel; see [Current and candidate](../research-tree.md#current-and-candidate). Native experiment, evidence and holdout rules remain unchanged.
