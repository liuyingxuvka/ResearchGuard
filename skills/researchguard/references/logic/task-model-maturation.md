# Task-Local Model Maturation

This is the existing LogicGuard task loop, not a separate route or understanding level: predict, observe, revise, so the model grows with the research.

1. `argument-iteration freeze` records the expected state of one claim under one perturbation before you look (`--expected-state`, `--mode`, `--root`, `--node`). Every named claim and node, including each `--coverage-id`, must exist in the model; the prediction remembers the model's content digest, so a prediction made against an older model is reported as stale.
2. `argument-iteration run` replays the perturbation on the baseline (and on `--candidate` when you revised the model), compares the result with the prediction, re-checks every `--protect-claim` claim and, when given, every `--holdout-claim` claim, and adds the native depth gaps. It loads models exactly like `logic validate`.
3. Revise while an addressable gap or a prediction mismatch remains. On the next round pass `--iteration <n>` and the previous `open_gap_ids` as `--prior-open-gap-id`, so an unchanged gap set stops as `progress_stalled`.

The loop never writes model files. `accepted` means the candidate file becomes your current model; `rejected` or `continue_iteration` means you keep the baseline. Roll back by keeping or restoring the previous model file (for example from git).

The loop may change only the current task model. It must not tune LogicGuard evaluators, thresholds, defaults, or another Guard. Close only when the prediction, native depth, protected claims and any holdout claims all pass; otherwise stop with `progress_stalled`, `iteration_limit`, or `external_input_required` and keep the open gaps visible. Evidence nodes may carry `provenance` (see `h-wadf-quick-reference.md`).

Gap transitions compare the actual baseline model's native open gaps with the
candidate's. Only resolved gaps set `progressed`; introduced gaps do not. The
prior-open ids are used only to detect stagnation, never as the baseline.
