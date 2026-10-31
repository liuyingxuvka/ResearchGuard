# ResearchGuard maintenance

<!-- BEGIN FLOWGUARD PROJECT RULES -->

## FlowGuard map and model maintenance

1. At the start of a session and after any loss of context, run `python -m flowguard status` before anything else.
2. Before changing behaviour or structure: store only the owner's request once as received with `python -m flowguard req add <file|-> --id <id>` (reuse its ID if already stored) and never edit the stored copy, locate the owner model with `python -m flowguard read --find WORDS` (or a path:function) and extend it (a separate aspect gets its own model), run `python -m flowguard target start "<goal>" --request <id>` and `python -m flowguard target add <model>`, edit the copy in .flowguard/target/, in .flowguard/target/PLAN.txt, name changed rules that show NO GAP and functions the change must reach (`changes: <model>.<rule> by <id> "<quote>"` with a verbatim quote or `changes: <model>.<rule> because "<reason>"`, and `touch: <path>:<qualified name>`), run `python -m flowguard target check` until it shows no ERROR and each changed model shows EXPECTED GAP, `moved rules only`, `no rule change` or NO GAP with a line for every changed rule that shows NO GAP, change the code, then run `python -m flowguard target promote` and the map confirm it prints, and paste its owner block, when printed, unchanged into your final message.
3. Open only the affected component's files (`python -m flowguard read --component ID`).
4. After editing, run `python -m flowguard change` and fix errors; for `port changed ... -> verify X`, run `python -m flowguard target add X` and make X receive the value; open each place a `consumes`, `produces`, `mentions` or `nothing produces` line names; restore what a `promises: -...` line lists or give the reason in the commit message; then run the affected tests and models it selects. Models, tests and code grow together: split a model or a test file that grows too big (map check warns at the soft limit and refuses at the hard one), keep them in correspondence where it makes functional sense, and give a reason where a model has no test or no code yet.
5. Re-read each REVIEW component, update its description if behavior changed, then `python -m flowguard map confirm ID`.
6. At final release, freeze the source and run the full suite and `python -m flowguard release` once on that revision (same-SHA CI may provide this); report failures and unrun checks honestly.

Maintenance needs FlowGuard at or above the tag in the `test` extra of `pyproject.toml` (install with `python -m pip install -e ".[test]"`; the PyPI package named `flowguard` is a different project).
Raise that tag only when this repository starts using a newer FlowGuard feature; a FlowGuard release alone is no reason to change it or to release this repository.

<!-- END FLOWGUARD PROJECT RULES -->

Every completed action is committed and pushed to main. A release records the
exact tested commit and uses the maintainer-selected three-part version. Unless
the maintainer explicitly changes the policy, increment only the patch version.
