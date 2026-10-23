# One research folder

For a question that spans routes, keep native models side by side and add:

```yaml
schema: researchguard.research.v1
question: Which explanation fits the observations?
root_claim: h_main
hypotheses:
  - {id: h_main, text: Main explanation}
  - {id: h_other, text: Alternative explanation}
models:
  source: source.yaml
  trace: trace.yaml
  logic: logic.yaml
  experiment: experiment.json
  experiment_observations: [observations.json]
```

All paths are relative to `research.yaml`. Each route and observations are optional;
observations require an experiment model. A listed logic model requires a root Claim.
Run `researchguard status <folder>` (or the index path); `--json` gives the same
information as data, and `--output <path>` explicitly saves it. Otherwise nothing
is written. Exit 0 means no reference errors, 1 means model/reference errors,
and 2 means the index could not be read. Warnings can remain at exit 0.

Use the same hypothesis id for a logic Claim, trace storyline hypothesis and
experiment hypothesis. SourceGuard owns source ids, roles, lineage and anchors.
Trace source ids equal SourceGuard source ids; trace evidence ids equal anchor ids.
Logic Evidence provenance uses that source id and anchor id as `locator`.
Experiment observations use the anchor id as `evidence_id` and source id as
`source_ref`. Each route's native loader still validates its own model.

Status projects each route's own evaluation, source search plan, trace depth and
experiment recommendations or observations. It does not strengthen their claims.
Without a source model, source/anchor checking is skipped with
`source_model_not_listed`; unused hypotheses and hypotheses missing from logic are
warnings. Handoff commands remain in the individual route references.
