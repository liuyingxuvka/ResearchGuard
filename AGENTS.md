# ResearchGuard maintenance

<!-- BEGIN FLOWGUARD PROJECT RULES -->

## FlowGuard map and model maintenance

1. Start each session with `python -m flowguard read` before opening source.
2. Before changing behaviour or structure: locate the owner model with `python -m flowguard read --find WORDS` (or a path:function) and extend it (a separate aspect gets its own model), run `python -m flowguard target start "<goal>"` and `python -m flowguard target add <model>`, edit the copy in .flowguard/target/, run `python -m flowguard target check` until it shows EXPECTED GAP and no ERROR, change the code, then run `python -m flowguard target promote` and the map confirm it prints.
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
