# TraceGuard Commands and Handoffs

Use only the installed `researchguard trace` path.

```powershell
researchguard trace validate <model.yaml>
researchguard trace evaluate <model.yaml> --pretty
researchguard trace depth <model.yaml> --pretty
researchguard trace diagnose <model.yaml> --pretty
researchguard trace gaps <model.yaml> --pretty
researchguard trace report <model.yaml> --format markdown
researchguard trace export-logicguard <model.yaml> --output <bundle.yaml>
researchguard trace create --purpose-contract <purpose.json> --output <model.yaml>
researchguard trace simulate --mode storyline-depth --model <model.yaml> --pretty
researchguard trace compare <before.yaml> <after.yaml> --pretty
researchguard trace iterate freeze --model <model.yaml> --prediction-id <id> --frozen-at <time> --target-kind <kind> --target-id <id> --expected-evidence <id> --weakens-when <condition> --output <prediction.json>
researchguard trace iterate compare --prediction <prediction.json> --observation <observation.json> --output <comparison.json>
researchguard trace iterate decide --comparison <comparison.json> --observation <observation.json> --candidate <candidate.yaml> --required-holdout-evidence <id> --output <revision.json>
researchguard trace library validate <case-library> --pretty
researchguard trace library build-model <case-library> <case-id> --output <model.yaml> --pretty
```

TraceGuard → LogicGuard includes trace/model-card/structure ids, validated and missing steps, alternatives, causal weakest link, conclusion-transfer status, downstream consumer, and safe/unsafe wording. TraceGuard → SourceGuard includes exact trace gap, evidence role/class, locator, counter/limiting need, and bridge need. Handoffs remain `awaiting_owner`; they never execute the sibling.
