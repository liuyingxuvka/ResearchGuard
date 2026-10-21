# TraceGuard Commands and Handoffs

Use only the installed `researchguard trace` path.

```powershell
researchguard trace validate <model.yaml>
researchguard trace evaluate <model.yaml> --output <evaluation.json>
researchguard trace depth <model.yaml> --output <depth.json>
researchguard trace diagnose <model.yaml> --pretty
researchguard trace gaps <model.yaml> --pretty
researchguard trace report <model.yaml> --format markdown
researchguard trace export-logicguard <model.yaml> --output <bundle.yaml>
researchguard trace create --output <model.yaml>
researchguard trace simulate --mode storyline-depth --model <model.yaml> --pretty
researchguard trace compare <before.yaml> <after.yaml> --pretty
researchguard trace iterate freeze --model <model.yaml> --prediction-id <id> --frozen-at <time> --target-kind <kind> --target-id <id> --expected-evidence <id> --weakens-when <condition> --task-id <task> --purpose <purpose> --coverage-id <id> --iteration 0 --max-iterations 4 --output <prediction.json>
researchguard trace iterate compare --prediction <prediction.json> --observation <observation.json> --output <comparison.json>
researchguard trace iterate decide --comparison <comparison.json> --observation <observation.json> --holdout-observation <holdout.json> --candidate <candidate.yaml> --required-holdout-evidence <id> --output <revision.json>
researchguard trace library validate <case-library> --pretty
researchguard trace library build-model <case-library> <case-id> --output <model.yaml> --pretty
```

Read results with `trace report --format markdown` (3–5 KB). `evaluate` and `depth` with `--output` print a short summary and write the full JSON to the file.

TraceGuard → LogicGuard includes trace/model-card/structure ids, validated and missing steps, alternatives, causal weakest link, conclusion-transfer status, downstream consumer, and safe/unsafe wording. TraceGuard → SourceGuard includes exact trace gap, evidence role/class, locator, counter/limiting need, and bridge need. Handoffs remain `awaiting_owner`; they never execute the sibling.


## One evaluation, several views

The public `evaluate_model` default keeps `include_storyline_depth=True`.
Run the required solve and critical perturbations once for the current model;
reuse that current result for summary, weaknesses and gap reporting. The command
list above is a menu, not a sequence to rerun every solve for one unchanged model.

Only an explicitly bounded evidence-chain task may use the existing
`evaluate_model(model, include_storyline_depth=False)` API. That result cannot
claim broad, causal, robust, predictive or closed storyline coverage. Native why,
causal, what-if and robustness requests keep their required depth and all critical
perturbations. Full JSON remains available on demand.
