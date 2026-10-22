# Task-Local Trace Iteration

Use the existing independent task loop when later evidence or a future event should test a frozen prediction: predict, observe, revise, so the trace model grows with the investigation.

Freeze the target storyline or hypothesis, the expected evidence footprint or future event, the expected order when material, and a falsifier (`--weakens-when`) before the observation timestamp. The target, every `--expected-evidence` and `--expected-event` id, and every `--coverage-id` (evidence, event, source, trace or hypothesis id) must exist in the model; the prediction remembers the model file's sha256, so a prediction made against a changed model is reported as stale. Task id, purpose, coverage, assumptions, unknowns and the iteration bound are optional. An observation lists evidence, event and source ids; each must already exist in the model.

An introduced gap is a finding about the evidence boundary, not proof of quality improvement. A missing future event, provider, or external observation stays explicitly unavailable with its current gap; no synthetic event or source may fill it.

Compare prediction and observation, create a distinct candidate v2 file, run the same canonical TraceGuard evaluator and native depth route, then accept, reject, or roll back. The candidate may not change the evidence, events or sources the construction observation used. Never overwrite v1 or change solver, rules, thresholds, templates, defaults, or another Guard; roll back by keeping or restoring the previous model file (for example from git).

A holdout observation is optional. When given, it must be a different observation with disjoint evidence ids, and its evidence must exist in the candidate. Internal perturbation is not factual future prediction; a future-event prediction needs an observation whose `future_holdout_status` is `pass`.

Native comparison and perturbation—not caller prose—produce input, resolved, persisted, and introduced gaps. Continue while predictive or coverage gaps remain; on the next round pass `--iteration <n>` and the previous `open_gap_ids` as `--prior-open-gap-id`. Close only as `model_closed_for_task`; otherwise keep the exact non-closure terminal and next action visible.

Gap transitions compare the actual baseline model's native open gaps with the
candidate's. Only resolved gaps set `progressed`; introduced gaps do not. The
prior-open ids are used only to detect stagnation, never as the baseline.
Prediction mismatch ids remain in `unaddressed_mismatch_ids` and rejection
reasons; they are not native gap ids and never enter `gap_transitions`.
