# ResearchGuard maintenance

<!-- BEGIN FLOWGUARD PROJECT RULES -->

## FlowGuard map and model maintenance

1. Start each session with `python -m flowguard read` before opening source.
2. Before changing behaviour or structure: `python -m flowguard target start "<goal>"`, edit the target, `python -m flowguard target check`, then `python -m flowguard target promote`; extend the existing owner (`python -m flowguard read --find WORDS`).
3. Open only the affected component's files (`python -m flowguard read --component ID`).
4. After editing, run `python -m flowguard change`, fix errors, and run the affected tests and models it selects.
5. Re-read each REVIEW component, update its description if behavior changed, then `python -m flowguard map confirm ID`.
6. At final release, freeze the source and run the full suite and `python -m flowguard release` once on that revision (same-SHA CI may provide this); report failures and unrun checks honestly.

Maintenance needs FlowGuard at or above the tag in the `test` extra of `pyproject.toml` (install with `python -m pip install -e ".[test]"`; the PyPI package named `flowguard` is a different project).
Raise that tag only when this repository starts using a newer FlowGuard feature; a FlowGuard release alone is no reason to change it or to release this repository.

<!-- END FLOWGUARD PROJECT RULES -->

Every completed action is committed and pushed to main. A release records the
exact tested commit and uses the maintainer-selected three-part version. Unless
the maintainer explicitly changes the policy, increment only the patch version.
