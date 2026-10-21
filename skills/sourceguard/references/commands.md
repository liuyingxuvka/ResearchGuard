# SourceGuard Commands

Use only the installed `researchguard source` path.

```powershell
researchguard source create --output <model.yaml>
researchguard source validate <model.yaml> --pretty
researchguard source plan <model.yaml> --limit 5 --pretty
researchguard source score-actions <model.yaml> --pretty
researchguard source frontier <model.yaml> --pretty
researchguard source depth <model.yaml> --pretty
researchguard source depth <model.yaml> --observation <observation.yaml> --output <receipt.json> --updated-model-output <updated.yaml> --pretty
researchguard source add-observation <model.yaml> --observation <observation.yaml> --output <updated.yaml> --pretty
researchguard source search-iteration freeze <model.yaml> --action-id <id> --expected-gap-reduction <none|partial|closed> --expected-independent-lineage <true|false> --expected-counterevidence <true|false> --expected-cost <0..1> --task-id <task> --purpose <purpose> --coverage-id <id> --iteration 0 --max-iterations 4 --output <prediction.json>
researchguard source search-iteration run <model.yaml> --prediction <prediction.json> --observation <observation.yaml> --actual-cost <0..1> --decision <accept|reject> --candidate-output <candidate.yaml> --receipt-output <receipt.json>
researchguard source search-iteration rollback <baseline.yaml> --accepted-receipt <receipt.json> --output <restored.yaml> --receipt-output <rollback.json>
researchguard source report <model.yaml> --format markdown
researchguard source export-traceguard <model.yaml> --output <seed.yaml>
researchguard source export-logicguard <model.yaml> --output <candidates.yaml>
```


## Read one result cheaply

For routine planning, call `plan_next_actions(model, limit=3)` once and use
`render_text(plan)` on that same PlanResult. The text retains selected actions,
open gaps and the mathematical boundary. Keep the full scored candidate JSON as
an on-demand artifact; do not paste it into every turn or recompute a plan just
to change its display. The existing CLI text view is:

```text
researchguard source report <model.yaml> --format txt
```

A short view does not remove a critical gap or license stronger claim use.
