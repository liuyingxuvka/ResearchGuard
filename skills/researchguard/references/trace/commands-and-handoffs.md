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
researchguard trace iterate freeze --model <model.yaml> --prediction-id <id> --frozen-at <time> --target-kind <kind> --target-id <id> --expected-evidence <id> --weakens-when <condition> [--iteration <n> --prior-open-gap-id <gap>] --output <prediction.json>
researchguard trace iterate compare --prediction <prediction.json> --observation <observation.json> --output <comparison.json>
researchguard trace iterate decide --comparison <comparison.json> --observation <observation.json> --candidate <candidate.yaml> [--holdout-observation <holdout.json> --required-holdout-evidence <id>] --output <revision.json>
researchguard trace library validate <case-library> --pretty
researchguard trace library build-model <case-library> <case-id> --output <model.yaml> --pretty
```

Read results with `trace report --format markdown` (2–4 KB). `evaluate` and `depth` with `--output` print a short summary and write the full JSON to the file.

TraceGuard → LogicGuard includes trace/model-card/structure ids, validated and missing steps, alternatives, causal weakest link, conclusion-transfer status, downstream consumer, and safe/unsafe wording. TraceGuard → SourceGuard includes exact trace gap, evidence role/class, locator, counter/limiting need, and bridge need. Handoffs remain `awaiting_owner`; they never execute the sibling.


## One evaluation, several views

`evaluate` (and the `evaluate_model` API) solves the model once and does not run
storyline depth. Run `trace depth` once for the current model when the wording is
broad, causal, robust, predictive or closed; it runs every critical perturbation.
Reuse each result for summary, weaknesses and gap reporting. The command list above
is a menu, not a sequence to rerun for one unchanged model. Full JSON remains
available on demand.

`export-logicguard` retains the v1 `claims` fields and adds per-hypothesis
`hypotheses` and evidence text/source/locator records. `logic import-handoff`
uses hypothesis ids as Claim ids and the first primary hypothesis as root.
Support links stay direct; opposing evidence supports a Rebuttal that attacks
the hypothesis; limiting evidence supports a Limitation that qualifies it.
Evidence provenance retains the source id, anchor id as locator, content hash,
and human locator text. No hypothesis-to-hypothesis edge or warrant is invented.
A dual-sign evidence link keeps both paths and logs the conflict. An old bundle,
or a trace-only bundle with no hypotheses, keeps the existing trace-claim path.
Import reads the bundle only; it never invokes SourceGuard or opens its files.
