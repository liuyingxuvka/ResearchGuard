# Task-Local Model Maturation

This is the existing LogicGuard task loop, not a separate route or understanding level.

Freeze task id, purpose, explicit coverage and fingerprint, assumptions, unknowns, iteration bound, and predecessor receipt on later iterations. For every important covered node, record a concrete prediction and falsifier before the observation or perturbation. Native depth analysis, simulation, and current source/trace receipts—not caller prose—produce input, resolved, persisted, and introduced gaps.

Revise while an addressable gap or predictive weakness remains. Every iteration returns one addressable next action. Candidate acceptance must preserve protected claims and pass a separately declared holdout claim that is neither the root nor a protected claim. Keep accepted revisions immutable; rollback appends a compensating revision instead of rewriting history.

Use the native `argument-iteration freeze`, `run`, and `rollback` commands from `commands.md`. The loop may change only the current task model. It must not tune LogicGuard evaluators, thresholds, templates, defaults, or another Guard.

Close only when current native depth, prediction, protected-claim checks, independent holdout, and covered-gap reconciliation all pass. Otherwise return `progress_stalled`, `iteration_limit`, `external_input_required`, or `scope_excluded` with open gaps visible.
