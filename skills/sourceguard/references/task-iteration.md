# Task-Local Search Iteration

Use this existing loop when one selected search action should predict its result before a real observation arrives: predict, observe, revise, so the source model grows with the research.

Freeze the selected action and its expected gap reduction, lineage independence, counterevidence and cost before the observation (`search-iteration freeze`). The action and every `--protect-gap` gap must exist in the model; the prediction remembers the model's fingerprint, so a prediction made against an older model is reported as stale. Task id, purpose, coverage, assumptions, unknowns and the iteration bound are optional.

After a real observation, `search-iteration run` creates candidate v2 through the native update/replan path and writes it to `--candidate-output`; the baseline file is never changed. Keep observation validity separate from prediction error. Acceptance requires an explicit decision, unchanged utility weights, a completed native depth check that passes the requested claim scope, and preserved protected gaps. `accepted` means the candidate file becomes your current model; otherwise keep the baseline. Roll back by keeping or restoring the previous model file (for example from git).

A new gap records information discovered by the observation; it is not by itself a quality gain. If a provider or external source is missing, preserve that status and the named gap instead of fabricating a source or observation. On the next round pass `--iteration <n>` and the previous `open_gap_ids` as `--prior-open-gap-id`.

The loop may change only this task's belief state, observations, gaps, leads, and action ordering. It cannot tune global weights, thresholds, defaults, templates, or another Guard. Caller-supplied gap transitions and self-reported understanding are not closure evidence.