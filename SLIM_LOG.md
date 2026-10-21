# ResearchGuard slimming log — 2026-10-21

- Audit baseline: `d9210ed6c8e4dd18f5aa05397e96b5567c8e32b0` (`v0.5.9`).
- Working branch: `slim/2026-10`; action scope: RG-01–RG-61, one action per commit.
- User version override: target ResearchGuard `0.5.10`, prospective new FlowGuard `0.70.7`; historical baseline versions remain unchanged.
- Environment: external venv, Python 3.11.17; ResearchGuard is editable from this branch; ordinary FlowGuard is editable from the read-only audit baseline (`7232473`, version `0.70.6`).
- RG-01–RG-38 compatibility checks read the LogicWriting audit baseline (`f393004`); RG-39 onward uses the synchronized working LogicWriting only after its required boundary.
- No push, publication, global installation, or edits to other repositories are performed here. Explicit action removals override the older receipt/DNA preservation rule.

## Preparation

- An early smoke command ran before pip finished: modules were not yet installed, exit 1, no tests collected. Installation then completed; this is an environment-preparation error, not a product test failure. Full logs are external.
- Initial FlowGuard read and environment origins verified. Baseline checks follow below.

## Baseline results

- `python -m pytest` — exit 0, 556.712s; 896 passed, 13 skipped in 556.12s (tkinter available).
- `python -m pytest --collect-only` — exit 0, 4.672s; 909 tests collected.
- `python -m flowguard map check` — exit 0, 0.498s; 0 errors / 4 entrypoint warnings.
- `python -m flowguard release` — exit 0, 1.402s; 2 declared / 2 executed; verify PASS.
- `python scripts/check_prompt_bundles.py` — exit 0, 0.154s; pass.
- `researchguard logic validate examples/logic/scientific_causal_claim.yaml` — exit 0, 0.508s; validation: OK.
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py tests/e2e/test_production_reader_pipeline.py tests/contract/test_production_reader_native_lifecycle.py` — exit 0, 3.309s; 44 passed in 2.83s against the LogicWriting audit baseline.
- Baseline tracked size: 597 files, 12,835,053 bytes; source Python 79,850 lines, test Python 26,555 lines.
- Baseline copies remain tracked-source clean. Waiting for the coordinator’s FG-13 boundary before RG-01.

## Scheduling adaptation

The coordinator opened RG-01–RG-10 in parallel with FG-01–FG-13 under the user’s explicit parallel-work authorization: this repository uses isolated audit-baseline FlowGuard and LogicWriting, so there is no runtime dependency on the changing FlowGuard branch. Dependency versions are unchanged. Stop after RG-10 until the coordinator confirms all 98 FlowGuard actions; retain the RG-47/RG-48 barrier after LW-43.

## RG-01 — completed

Made the GUI-only import conditional, fixed direct pytest imports, and removed only the redundant suite/map test wrapper. Viewer behavior is unchanged. tkinter is available here: 9 passed; both collection forms report906.

- `python -m pytest tests/logic/test_library_viewer.py` — exit 0, 0.896s; `9 passed in 0.55s`
- `pytest --collect-only` — exit 0, 3.497s; `906 tests collected in 3.06s`
- `python -m pytest --collect-only` — exit 0, 3.769s; `906 tests collected in 3.28s`

## RG-02 — completed

Removed the explicit self-DNA command, duplicate DNA files and its test/runner-only machinery; the FlowGuard map, its component fingerprints and both registered native models remain. Focused51passed; collection884; map0errors (7warnings include expected interim STALE); retired self-dna exits2.

- `python -m pytest tests/test_root_cli.py tests/test_suite_checker_bounds.py tests/test_install_researchguard.py tests/test_suite_model_currentness.py tests/test_skill_suite.py tests/test_prompt_bundles.py` — exit 0, 15.395s; `51 passed in 15.03s`
- `python <external>/probe_rg02.py` — exit 0, 0.267s; `help current; self-dna unknown-command rc2; remaining literal-only references: ['scripts/check_prompt_bundles.py', 'tests/test_prompt_bundles.py', 'tests/test_skill_suite.py', 'tests/test_suite_model_currentness.py']`
- `python -m pytest --collect-only` — exit 0, 3.29s; `884 tests collected in 2.84s`
- `python -m flowguard map check` — exit 0, 0.521s; `check: 0 error(s), 7 warning(s), 0 info`

## RG-03 — completed

Removed only repeated target-purpose proof during model loading; retained contract snapshot/schema checks and create-time proof. The new grown-model regression failed before the fix (expected exit1) and tests/source then passed125; collection885/map0errors.

- `python -m pytest tests/source/test_cli.py::test_grown_model_still_loads_after_evidence_for_the_guarded_gap` — exit 1, 1.211s; `1 failed in 0.93s`
- `python -m pytest tests/source` — exit 0, 10.791s; `125 passed in 10.45s`
- `python -m pytest --collect-only` — exit 0, 3.437s; `885 tests collected in 2.97s`
- `python -m flowguard map check` — exit 0, 0.452s; `check: 0 error(s), 8 warning(s), 0 info`

## RG-04 — completed

logic depth now computes native depth without a contract and prints the real six-field gap summary (516bytes, blocked rc3); specifying only one old contract option remains an error rc1. The old two-option receipt path is untouched; focused28passed and baseline LW44passed; collection886.

- `python -m pytest tests/logic/test_cli.py tests/logic/test_dynamic_model_purpose_contract.py tests/logic/test_execution_depth.py` — exit 0, 23.394s; `28 passed in 22.60s`
- `python <external>/probe_rg04.py` — exit 0, 1.119s; `native gap summary rc3: 516 bytes;partial options rc1; warrant gap retained`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py tests/e2e/test_production_reader_pipeline.py tests/contract/test_production_reader_native_lifecycle.py` — exit 0, 2.087s; `============================== 44 passed in 1.82s ==============================`
- `python -m pytest --collect-only` — exit 0, 3.786s; `886 tests collected in 3.40s`

Coordinator update: independent cross-repository review confirmed that RG-11–RG-38 also use only the immutable audit dependency copies. The earlier pause after RG-10 is replaced by continuation through RG-38 under the user’s parallel-work authorization. Stop after RG-38 until current LogicWriting completes LW-59; RG-47/RG-48 still require LW-43. No dependency version or per-action verification rule changes.

## RG-05 — completed

Absent external depth now invokes the same native analysis in-process; supplied receipts retain their existing validation. sha256-prefixed selection identities accepted. The real warrant gap remains blocked_support_gap, while a complete model is ready. Focused32/LW44passed; collection887; checkpoint874passed13skipped in509.23s,2models pass,map0errors.

- `python -m pytest tests/logic/test_artifact_synthesis.py tests/logic/test_synthesis_contract.py tests/logic/test_synthesis_native_closure.py tests/logic/test_delivery_contract.py tests/logic/test_cli.py` — exit 0, 21.115s; `32 passed in 20.81s`
- `python <external>/probe_rg05.py` — exit 0, 0.313s; `blocked_support_gap False True`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py tests/e2e/test_production_reader_pipeline.py tests/contract/test_production_reader_native_lifecycle.py` — exit 0, 2.35s; `============================== 44 passed in 1.99s ==============================`
- `python -m pytest --collect-only` — exit 0, 3.59s; `887 tests collected in 3.01s`
- `python -m pytest` — exit 0, 509.924s; `874 passed, 13 skipped in 509.23s (0:08:29)`
- `python -m flowguard map models` — exit 0, 0.91s; `models: 2 passed, 0 failed`
- `python -m flowguard map check` — exit 0, 1.319s; `check: 0 error(s), 9 warning(s), 0 info`

## RG-06 — completed

Removed only six-key portable-header machinery; schema_version and native reference validation remain. Handwritten incident model loads with metadata.schema_version alone; trace154passed (125.79s),collection888,map0errors; no header machinery references in src/tests.

- `python -m pytest tests/trace` — exit 0, 126.508s; `154 passed in 125.79s (0:02:05)`
- `python <external>/probe_rg06.py` — exit 0, 0.947s; `bare metadata schema_version only accepted; real trace_count1; no header machinery residual`
- `python -m pytest --collect-only` — exit 0, 3.692s; `888 tests collected in 3.29s`
- `python -m flowguard map check` — exit 0, 0.569s; `check: 0 error(s), 10 warning(s), 0 info`
