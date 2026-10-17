# SourceGuard Commands

Use only the installed `researchguard source` path.

```powershell
researchguard source create --model-contract <contract.json> --output <model.yaml>
researchguard source validate <model.yaml> --model-contract <contract.json> --pretty
researchguard source plan <model.yaml> --model-contract <contract.json> --limit 5 --pretty
researchguard source score-actions <model.yaml> --model-contract <contract.json> --pretty
researchguard source frontier <model.yaml> --model-contract <contract.json> --pretty
researchguard source depth <model.yaml> --model-contract <contract.json> --pretty
researchguard source depth <model.yaml> --model-contract <contract.json> --observation <observation.yaml> --output <receipt.json> --updated-model-output <updated.yaml> --updated-model-contract-output <updated.contract.json> --pretty
researchguard source add-observation <model.yaml> --model-contract <contract.json> --observation <observation.yaml> --output <updated.yaml> --output-model-contract <updated.contract.json> --pretty
researchguard source search-iteration freeze <model.yaml> --model-contract <contract.json> --action-id <id> --expected-gap-reduction <none|partial|closed> --expected-independent-lineage <true|false> --expected-counterevidence <true|false> --expected-cost <0..1> --output <prediction.json>
researchguard source search-iteration run <model.yaml> --model-contract <contract.json> --prediction <prediction.json> --observation <observation.yaml> --actual-cost <0..1> --decision <accept|reject> --candidate-output <candidate.yaml> --candidate-model-contract-output <candidate.contract.json> --receipt-output <receipt.json>
researchguard source search-iteration rollback <baseline.yaml> --model-contract <contract.json> --accepted-receipt <receipt.json> --output <restored.yaml> --output-model-contract <restored.contract.json> --receipt-output <rollback.json>
researchguard source report <model.yaml> --model-contract <contract.json> --format markdown
researchguard source export-traceguard <model.yaml> --model-contract <contract.json> --output <seed.yaml>
researchguard source export-logicguard <model.yaml> --model-contract <contract.json> --output <candidates.yaml>
```


## Read one result cheaply

For routine planning, call `plan_next_actions(model, limit=3)` once and use
`render_text(plan)` on that same PlanResult. The text retains selected actions,
open gaps and the mathematical boundary. Keep the full scored candidate JSON as
an on-demand artifact; do not paste it into every turn or recompute a plan just
to change its display. The existing CLI text view is:

```text
researchguard source report <model.yaml> --model-contract <contract.json> --format txt
```

A short view does not remove a critical gap or license stronger claim use.
