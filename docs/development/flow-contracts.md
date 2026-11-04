# Flow and functional contracts

ResearchGuard uses one small native-backed flow for frozen iteration identity in
`.flowguard/flow/iteration_identity.py`. It compares accepted, stale and recovered
observations against the real identity owner. The model deliberately covers that
finite boundary, not every research workflow.

The other independent contracts are direct unit tests in `tests/flow_migration/`.
Their 50 rule identities, 55 original bad-observation controls, 74 existing production
test links and nine system route bindings are listed in `coverage.json`. The rule
predicates are independent expected assertions, with actual production fixture
checks beside them. Bad-observation controls test those assertions; they do not
claim to mutate every shipping implementation. The index is audit data for tests,
not another runtime registry or change route.

Three previously documented boundaries remain visible:

- Trace depth's evaluator and storyline-depth modules depend on each other. Deleting
  the old ownership metric does not remove that source dependency or justify a split.
- Trace library file operations remain covered by `tests/trace/test_traceguard.py`;
  a separate state model is not claimed.
- Optional desktop settings remain behind the viewer boundary covered by
  `tests/logic/test_library_viewer.py`; ordinary CLI use does not load the desktop app.

Changing production behavior still requires the affected production tests. Change
an executable flow first when changing its state, actions, guards or endings. Model
loading refreshes project modules; direct model API checks in tests use an isolated
command process so they do not replace pytest's already imported production objects.
