# SourceGuard Commands

Use only the installed `researchguard source` path.

```powershell
researchguard source create --output <model.yaml>
researchguard source validate <model.yaml> --pretty
researchguard source plan <model.yaml> --limit 5 --pretty
researchguard source score-actions <model.yaml> --pretty
researchguard source frontier <model.yaml> --pretty
researchguard source stop-decision <model.yaml> --budget <remaining budget> [--sufficient] --pretty
researchguard source depth <model.yaml> --pretty
researchguard source depth <model.yaml> --observation <observation.yaml> --output <depth.json> --updated-model-output <updated.yaml> --pretty
researchguard source add-observation <model.yaml> --observation <observation.yaml> --output <updated.yaml> --pretty
researchguard source search-iteration freeze <model.yaml> --action-id <id> --expected-gap-reduction <none|partial|closed> --expected-independent-lineage <true|false> --expected-counterevidence <true|false> --expected-cost <0..1> [--protect-gap <gap>] [--iteration <n> --prior-open-gap-id <gap>] --output <prediction.json>
researchguard source search-iteration run <model.yaml> --prediction <prediction.json> --observation <observation.yaml> --actual-cost <0..1> --decision <accept|reject> --candidate-output <candidate.yaml> --output <result.json>
researchguard source compare <before.yaml> <after.yaml> --pretty
researchguard source report <model.yaml> --format markdown
researchguard source export-traceguard <model.yaml> --output <seed.yaml>
```

`stop-decision` considers every executable declared or generated action addressing
an open gap (including blocked and permission gaps). An affordable critical
search continues, chosen by native utility, then declared action and id on ties;
otherwise a critical gap stays blocked, with a missing-action or over-budget
reason. With no critical gap, `--sufficient` or no open gap returns
`stop_sufficient`; without that declaration it continues only for an affordable
optional search. `optional_followups` lists each optional gap and its best
candidate, even when search stops. Cost is compared only with budget, never
with utility. Invalid inputs return `not_run`.

## Read one result cheaply

Choose one CLI view for a routine read. For native JSON with selected actions,
open gaps and the mathematical boundary, run:

```text
researchguard source plan <model.yaml> --limit 3
```

For a short text view, use this command instead:

```text
researchguard source report <model.yaml> --format txt
```

Each command computes its own view; do not run both merely to change display.
Use `plan --all-scores` only when the full scored candidate JSON is needed and
retain that output as an on-demand artifact instead of pasting it every turn.

A short view does not remove a critical gap or license stronger claim use.

`source depth` reads recorded observations without changing the input file;
`--observation` previews one more on a clone. `observations_used` lists both;
provider and observation statuses still describe this call, not a new retrieval.

An executable declared action (`proposed` or `selected`) suppresses automatic
actions for that gap. Generated gap queries omit the lead question, use at most
two domain hints, and end at a word boundary within 120 characters.
`score-actions` uses the complete `plan --all-scores` scoring path, without a
candidate cap; declared queries and native scoring weights are preserved.

`source compare` reports shared-gap changes in type, semantic state, review,
blocking, importance, description and `qualification_decision`; comparing a
model to itself returns no changes. Comparison does not license evidence.

Markdown and text reports list source ids, titles, roles and lineage with anchor ids
and locators. Each closed gap names the anchors and sources in its current
`closure_basis`; these are declared qualification records, not new retrieval or truth.


To bring new observations downstream, use
`researchguard source export-traceguard <source.yaml> --into <trace.yaml> --output <new-trace.yaml>`,
then `researchguard trace export-logicguard <new-trace.yaml> --output <bundle.yaml>` and
`researchguard logic import-handoff <bundle.yaml> --into <logic.yaml> --output <new-logic.yaml>`.
Sync adds missing ids and refreshes owner-controlled copied fields in existing records.
It reports `added`, `updated` and `conflicts`; typed links and hand-built non-owned content stay unchanged.
Identity conflicts are reported rather than overwritten. Repeating a successful sync is idempotent.
`--output` must differ from `--into`; no input is overwritten. Source anchors usable
for claims or traces are exported as usable trace evidence; AI still owns links.
