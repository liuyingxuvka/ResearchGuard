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
