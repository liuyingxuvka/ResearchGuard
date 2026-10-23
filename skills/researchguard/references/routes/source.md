# SourceGuard

## Purpose
Find sources; qualify anchors. Utility ranks search value, not truth/probability.

## Use when
Retrieval, provenance/lineage, source roles, semantic fit, counter/limiting, numeric/bridge evidence or claim use.

## Do not use
Trace reconstruction/argument licensing: use typed handoffs; no silent Guard calls.

## Order
Freeze claim/strength/roles/artifact/gaps. New model only: replace teaching rows. Validate, plan, retrieve, record real material:

```text
researchguard source create --output model.yaml
researchguard source validate model.yaml
researchguard source plan model.yaml --limit 3
researchguard source add-observation model.yaml --observation observation.yaml --output updated.yaml
researchguard source depth updated.yaml
researchguard source stop-decision updated.yaml --budget <remaining>
```

## Fields
See `references/source/fields.md`: claim in `leads[].question`, strength in `depth_policy.requested_claim_scope` (bounded/broad). Absent gap state defaults to discovered; retired status fails; closed needs complete current closure_basis.

## Stops
- `continue_iteration` / `continue_search`: take the selected action; repeat with real observations.
- `model_closed_for_task`: report native task closure within scope; understanding cannot close.
- `progress_stalled`: stop unchanged work; request new evidence/action.
- `iteration_limit`: stop; report gaps.
- `external_input_required` / `provider_access_required`: obtain named input/access; keep gap.
- `finite_action_exhausted`: report exhausted actions/unresolved scope.
- `blocked_unresolved_critical`: obtain critical search/budget; no claim promotion.
- `stop_sufficient`: stop search; `not_run`: correct inputs.
Compare cost with budget; utility ranks. Keep optional followups.

## Hard rules
Separate observations, candidates and immutable refs. Candidates, locators, utility and aggregates alone are not evidence. Keep missing/stale/planning-only/bounded/skipped/inaccessible/provider-unavailable work visible. Never invent retrieval/OCR/multimodal work. Recorded observations in depth do not imply fresh retrieval. Broad closure requires current depth, complete target/gap universes, per-gap direct/independent/counter coverage, lineage, content anchors and no critical gap.

## References
- `route:source-model`: always → `references/source/source-model-protocol.md`.
- `trigger:fields`: model/observation → `references/source/fields.md`.
- `trigger:retrieval-workflow`: retrieval/qualification/update/export → `references/source/retrieval-workflow.md`.
- `trigger:task-iteration`: predict before observation; miss/open gap → `references/source/task-iteration.md`.
- `trigger:broad-depth-closure`: broad/complete/deep/final/high-impact/closure → `references/source/broad-depth-and-closure.md`.
- `trigger:commands`: CLI construction → `references/source/commands.md`.
- `trigger:safe-output`: reader use/downgrade/access-gap/handoff → `references/source/safe-output.md`.
