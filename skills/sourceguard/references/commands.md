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
