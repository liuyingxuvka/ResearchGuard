# One research folder is the model of one question

A research folder joins the native source, trace, logic and experiment models by
shared ids. The index is the question model, not a second reasoning engine.

## Start a question

Write this file first, then build the route models and list them in `models`.
Changing a question later follows "Current and candidate": copy, sync, compare, replace.

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
library: ../personal-library
search: {budget: 3, scope_sufficient: false}
ablations:
  - {id: without_anchor, remove_anchors: [anchor_main], hypothesis: h_main, expect: weaken}
```

All paths are relative to `research.yaml`. Routes, `library`, `search` and
`ablations` are optional. Observations require an experiment model; a listed logic
model requires its root Claim. Hypothesis ids are shared by logic Claims, trace
hypotheses and experiment predictions. Source ids and evidence anchor ids keep
their SourceGuard identities. Every route's native loader still validates it.
A SourceGuard gap may name the hypotheses it would move (`hypothesis_ids`);
`status` checks them (`unknown_hypothesis:source:<gap>:<id>`) and adds
`hypotheses` to each open source gap and next search.

`researchguard status <folder> [--json] [--output <path>] [--candidate <copy> | --hypothesis <id>]`
reads the index (or its explicit path). Default output is a compact verdict-first
page; JSON retains complete results. It writes only an explicit `--output`.
Exit 0 means no errors, 1 means model or reference errors, and 2 means an unreadable
index. Warnings do not change exit 0. A missing library is `library_missing:<path>`.
The library uses the same provenance resolver as `logic validate --library-root`.
A library project is a reading list, not a second research-question container.

## Who owns what

SourceGuard owns anchor `text`, `source_id`, `locator` and source `title`, `url`,
`source_date`, `lineage_id`. The shared ownership table maps these to trace
`evidence[].raw_text` (text or normalized summary), source records, and logic
Evidence provenance: `quote` or its native `content_hash`, `source_reference`,
`source_date`. `status` compares present, nonempty copies exactly. It reports
`copy_drift:trace:<id>:<field>` or `copy_drift:logic:<node>:<field>` when a copy
differs. Missing optional provenance is not invented or treated as a drift.
Without a source model, source/anchor checking is skipped with
`source_model_not_listed`; dangling ids and invalid native models stay errors.

`--into` synchronization refreshes only these owned fields and lists identities
under `updated`. It preserves trace links, reliability and other local work,
logic author summaries, unrelated provenance and all existing edges. `conflicts`
means a real identity clash (a different source or an incompatible node type),
not a changed quote. Old handoff bundles without optional source metadata remain
readable; absence does not erase existing provenance.

## When routes disagree

Direct evidence supporting a hypothesis in one route and opposing it in another
produces `route_disagreement:<hypothesis>:anchor:<anchor>`. Indirect argument
chains and `limit` links are not compared. An explicitly rejected hypothesis
(logic OUT, trace not live or experiment eliminated) conflicting with logic IN or
trace live produces a status disagreement. UNDECIDED and experiment consistent
are neutral. `disagreements` lists these warnings; correct the erroneous route or
retain the disagreement as an explicit writing risk.

## Known-bad: ablations

Declare unique `id`, `remove_anchors`, `hypothesis` and `expect: weaken|eliminate`.
Anchors must exist in the source model and hypotheses in the index. Evidence-only
trace ablations with a decreasing hypothesis sensitivity join this same list;
duplicate ids are errors. Evaluators run on disposable in-memory copies. Logic
catches `weaken` by lower confidence or state; trace catches it by TraceGuard's own
expected-sensitivity check (a fall in the snapshot score, at trace's declared
threshold; 0 for question rows), so `status` and `trace depth` agree. OUT or not
live catches `eliminate`. `caught_by` names the reacting routes; an empty list gives
`ablation_not_caught:<id>`. `effects` lists other hypotheses whose trace `live` or
logic `state` flips. No model files are changed; observations are not ablated.

## Current and candidate

The research folder is the current model; a candidate copy is the target:

1. Copy the folder as the candidate.
2. Sync new evidence into the copy (each `--output` inside the copy, and the
   copy's `research.yaml` points at the new files).
3. Run `researchguard status <current> --candidate <copy>` to see before and after.
4. Accept by replacing the current folder with the copy (git keeps history);
   otherwise delete the copy. The kernel never replaces a model for you.

`changes` rows are `{kind, id, before, after}` or `{kind, id, change}` with kind
`hypothesis` (only changed fields, route to field to value), `verdict` (one row
per changed `search`, `root_claim.id`, `root_claim.wording_license`,
`root_claim.reason`, `live_hypotheses`, `contested`, `errors`), `ablation`
(changed `caught_by` or `effects`, added or removed), `disagreement`, `evidence`,
`errors`, `warnings`. The page prints one change per line with two decimals,
e.g. `- h_suez: logic confidence 0.25 → 0.40`; equal folders show `no changes`.
JSON contains `current`, `candidate`, `changes`; exit 1 follows the candidate.

All four native predict-observe-revise loops use `researchguard.iteration`: one
canonical `baseline_identity`, gap lineage and terminal selection. Source models
exclude generation/update timestamps from identity; other routes use their loaded
native model dictionaries. Frozen prediction schemas are v3; older predictions
fail `stale_prediction: re-freeze`. A changed baseline must be frozen again.
Candidates need a new path and changed model content. Common terminal reasons
are `continue_iteration`, `model_closed_for_task`, `progress_stalled`,
`iteration_limit`, `external_input_required`, `scope_excluded`; SourceGuard also
uses `provider_access_required`, `finite_action_exhausted`. These do not change
native domain rules about evidence, protected scope or holdout independence.

## Verdict for writers

The JSON report includes `input_digests`, the raw SHA-256 hashes of every file read. Writers compare them with current files to check whether a saved report is still current.

Writers, including LogicWriting, read `verdict` from
`researchguard status <folder> --json --output research-status.json`, and these
pinned keys that tie the report to its folder: `question`, `hypotheses[].id` /
`text`, `models` (route to `{path, status}`), `evidence[].anchor` and
`evidence[].directions`:

- `search`: the native stop decision with the index's budget/sufficiency, or
  `not_run` without source and `search`. Native values are `continue_search`,
  `stop_sufficient`, `blocked_unresolved_critical`.
- `root_claim`: null, or exactly `id`, `wording_license`, `reason` from native
  argument licensing (`assert`, `qualify`, `withhold`). It never upgrades wording.
- `live_hypotheses`: index-order ids not explicitly excluded by any route.
- `contested`: whether route disagreements exist; it is a risk, not a new gate.
- `errors`: the number of errors in this status result.

## Evidence directions

Each `evidence[]` row keeps `used_by` and adds `directions`: rows `{route,
hypothesis, direction, node}` with `direction` `support`, `oppose` or `limit`,
sorted by route and hypothesis. Trace uses link polarity and storyline evidence
lists (`node: null`). Logic uses only the direct edges of the Evidence node whose
provenance names the anchor, when the edge targets a hypothesis: `supports`,
`attacks`/`contradicts`/`undercuts`, `qualifies`. Indirect chains carry no
direction. Route disagreements compare the same rows (`limit` is not compared).

## Read one hypothesis

`researchguard status <folder> --hypothesis <id>` prints Routes (logic state and
confidence, trace rank/support/live, experiment status; `not in logic` /
`not in trace`), Evidence (support, oppose, limit), Ablations (its own and those
whose `effects` name it), Disagreements, Open gaps and Next (searches whose gap
names it; experiments that predict for it), all taken from the same status. With
`--json` the keys are `id`, `text`, `routes`, `evidence`, `ablations`,
`disagreements`, `open_gaps`, `next`. An unknown id prints
`unknown_hypothesis:<id>` and exits 2. Empty sections print `- none`.

## Synchronize new evidence

```sh
researchguard source export-traceguard source.yaml --into trace.yaml --output trace-next.yaml
researchguard trace export-logicguard trace-next.yaml --output bundle.yaml
researchguard logic import-handoff bundle.yaml --into logic.yaml --output logic-next.yaml
```

Run these inside the candidate copy. Every output must differ from the
input/`--into` path. Sync reports `added`, `updated`, `conflicts`; a second
unchanged sync has empty lists. Source anchors usable for claims or traces export
as usable evidence; AI still owns the links. Point the copy's `research.yaml` at
the outputs, then compare with `status <current> --candidate <copy>`. Route
results remain scoped to their own declared evidence and do not establish truth.
