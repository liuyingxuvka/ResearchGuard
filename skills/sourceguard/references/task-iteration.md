# Task-Local Search Iteration

Use this existing loop when one selected search action should predict its result before a real observation arrives.

Freeze task id, purpose, coverage and fingerprint, assumptions, unknowns, iteration bound, predecessor receipt, selected action, expected gap reduction, expected lineage independence, expected counterevidence, expected cost, protected gaps, prediction, and falsifier. The prediction precedes the observation and binds the exact baseline plus model contract.

After a real observation, create candidate v2 through the native cloned-baseline update/replan path. Keep observation validity separate from prediction error. Acceptance requires an explicit decision, unchanged utility weights, current contract bindings, native depth receipts for baseline/candidate/observation, and preserved protected gaps. Never overwrite baseline, prediction, observation, candidate, contract, or receipt; rollback writes a new baseline-equivalent projection.

The loop may change only this task's belief state, observations, gaps, leads, and action ordering. It cannot tune global weights, thresholds, defaults, templates, or another Guard. Caller-supplied gap transitions and self-reported understanding are not closure evidence.
