# Task-Local Trace Iteration

Use the existing independent task loop when later evidence or a future event should test a frozen prediction: predict, observe, revise, so the trace model grows with the investigation. The loop writes comparison and decision artifacts; it never rewrites a model. Save any candidate separately.

## Freeze before observing

Freeze the target storyline or hypothesis, expected evidence footprint or future event, and expected order when material before the observation timestamp. The target and every `--coverage-id` (evidence, event, source, trace or hypothesis ID) must already exist in the baseline. `--expected-evidence` and `--expected-event` may name future records absent from that baseline; a later observation must supply their IDs or typed new records. The prediction remembers the baseline file's sha256, so changing that file makes the prediction stale.

`--expected-direction weaken|strengthen|unchanged` is optional. Omission adds no direction-mismatch requirement. `--weakens-when` is an optional explanatory remark. Task ID, purpose, coverage, assumptions, unknowns and iteration controls remain optional; the iteration bound defaults to 8. Neither a direction expectation nor a remark licenses factual future prediction.

## Observe and compare

Use the observation v2 fields in [fields.md](fields.md#evidence-batch-observation-v2). Existing evidence, event and source IDs may be listed directly. Four optional lists, each defaulting to `[]`, add typed TraceGuard rows: `new_sources`, `new_evidence`, `new_events`, and `new_links` (hypothesis-evidence links). IDs in each new-record collection must be unique within that collection and absent from its corresponding baseline collection, even for identical rows. To refer to an existing record, list its ID instead of adding it again.

Comparison appends those rows in memory, rebinds the combined model through the native schema and reference validator, and runs the canonical evaluator and depth route. Observation references must resolve in that combined model. Expected IDs are matched against both the explicit ID lists and new rows; `event_order` may use IDs from `event_ids` or `new_events`.

The reported target `support_before` and `support_after` determine `observed_direction`: a change below −0.01 is `weaken`, above +0.01 is `strengthen`, and otherwise `unchanged`. A supplied expectation is checked against that result. Missing expected IDs, order contradictions, reported contradictions, invalid/access-gap quality, and a missing passing future holdout check remain prediction mismatches. An observation must be later than the frozen prediction; stale baseline fingerprints still stop comparison.

Native depth gaps are separately reported as `open_depth_gap_ids`; they are not prediction mismatches. They remain visible in `open_gap_ids` together with mismatch IDs. An introduced gap describes the evidence boundary, not quality improvement. A missing future event, provider, or external observation stays explicitly unavailable; do not invent a source or event to fill it.

## Revise and decide

Create a distinct candidate v2 file and run `iterate decide` against the comparison and construction observation. Its path and content must differ from the baseline. The four new-record lists in that construction observation are immutable: each row must remain present with the same typed contents in the candidate. Older baseline record contents may be revised, and additional links may be added. All explicitly observed construction IDs must still resolve; canonical schema, reference and evaluation checks continue to apply.

Account for actual comparison mismatch IDs with `--address-mismatch`; unknown or unaddressed IDs reject the candidate. Construction quality must be `valid`. An optional holdout must have a different observation ID and disjoint evidence IDs, counting both listed IDs and `new_evidence` IDs on each side. Its explicitly referenced records must exist in the candidate, and its quality must be valid. When supplying a holdout, name at least one `--required-holdout-evidence` ID in its `evidence_ids`; missing required IDs reject acceptance. Internal perturbation is not factual future prediction; a `future_event` expectation also requires the comparison observation's `future_holdout_status` to be `pass`.

A canonically valid candidate can be `accepted` while native depth gaps remain: it becomes the effective candidate and normally returns `continue_iteration`. Acceptance alone does not close the task. Only an accepted candidate with no remaining native gaps can return `model_closed_for_task`; external-input, iteration-limit and progress-stalled stops remain explicit. Rejection or `--rollback` retains the baseline as effective. Never overwrite the baseline or change solver, rules, thresholds, templates, defaults, or another Guard; keep or restore the previous model file for rollback (for example from git).

Native gap transitions compare the actual baseline model's open depth gaps with the observed or candidate model's. Only resolved gaps set `progressed`; introduced gaps do not. On the next round pass `--iteration <n>` and previous `open_gap_ids` as `--prior-open-gap-id`. Prior IDs detect stagnation and never substitute for a native baseline. Prediction mismatch IDs remain in `unaddressed_mismatch_ids` and rejection reasons; they never enter native `gap_transitions`. Keep the exact non-closure terminal and next action visible. Every result keeps `factual_future_prediction_licensed` false.
