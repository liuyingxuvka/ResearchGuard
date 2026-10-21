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

## RG-07 — completed

Removed the export-time exact suite-version gate and five example metadata version pins; old model version0.5.8 is preserved as information in both exports. Kept native schema identifiers and package version. Source125passed; collection888; realexport0; map0errors.

- `python -m pytest tests/source` — exit 0, 14.322s; `125 passed in 13.86s`
- `python <external>/probe_rg07.py` — exit 0, 0.501s; `old release export accepted; example metadata version pins removed; native schema identifiers unchanged`
- `python -m pytest --collect-only` — exit 0, 4.175s; `888 tests collected in 3.64s`
- `python -m flowguard map check` — exit 0, 1.455s; `check: 0 error(s), 10 warning(s), 0 info`

## RG-08 — completed

SourceGuard exports actual TraceGuard v2 sources/evidence and moves source gaps/warnings into metadata notes; no invented events or traces. New cross-engine test failed against old schema, then source126passed and all5 exported examples loaded (schema_ok true,trace_count0,okfalse as honest starter state); collection889.

- `python -m pytest tests/source/test_handoff.py::test_traceguard_seed_loads_as_a_traceguard_model` — exit 1, 0.934s; `1 failed in 0.48s`
- `python -m pytest tests/source` — exit 0, 11.984s; `126 passed in 11.68s`
- `python <external>/probe_rg08.py` — exit 0, 4.159s; `structural_source_gap: validTraceGuardV2; schema_ok=true;trace_count0;ok=false;rc0`
- `python -m pytest --collect-only` — exit 0, 3.544s; `889 tests collected in 3.00s`

## RG-09 — completed

Added a small TraceGuard export bundle→starter LogicGuard model converter and CLI, retaining evidence/support and limitation/qualifies edges. Realexport/import/validate succeeds while missing_warrant remains; SourceGuard seed rejects rc1. CLI9passed,collection890,map0errors; no change to TraceGuard export claims/handoffs.

- `python -m pytest tests/logic/test_cli.py` — exit 0, 29.046s; `9 passed in 28.73s`
- `python <external>/probe_rg09.py` — exit 0, 3.338s; `Trace export→logic import→validateOK; missing_warrant preserved; SourceGuard seed rejected rc1`
- `python -m pytest --collect-only` — exit 0, 5.124s; `890 tests collected in 4.50s`
- `python -m flowguard map check` — exit 0, 0.996s; `check: 0 error(s), 10 warning(s), 0 info`

## RG-10 — completed

Added evaluate/depth --output while preserving complete JSON and old no-output behavior; removed only exported storyline_depth duplicate. Targeted164passed; nativefile195043bytes,summary968bytes (longer owned output path),depthsummary8keys,export11218bytes. Collection891; checkpoint878passed13skipped in473.54s,2models pass,map0errors.

- `python -m pytest tests/trace tests/logic/test_cli.py` — exit 0, 126.066s; `164 passed in 125.14s (0:02:05)`
- `python <external>/probe_rg10.py` — exit 0, 4.239s; `{"depth": {"file_bytes": 152706, "stdout_bytes": 326, "summary_keys": ["broad_claim_licensed", "closure_status", "covered_claim_scope", "critical_uncovered_ids", "live_alternative_ids", "output", "unresolved_gaps", "untested_high_impact"]}, "evaluate": {"file_bytes": 195043, "stdout_bytes": 968, "summary_keys": ["contradictions", "gaps", "ok", "output", "traces"]}, "export": {"file_bytes": 11218, "storyline_depth_present": false}}`
- `python -m pytest --collect-only` — exit 0, 3.648s; `891 tests collected in 3.20s`
- `python -m pytest` — exit 0, 474.062s; `878 passed, 13 skipped in 473.54s (0:07:53)`
- `python -m flowguard map models` — exit 0, 0.946s; `models: 2 passed, 0 failed`
- `python -m flowguard map check` — exit 0, 0.611s; `check: 0 error(s), 10 warning(s), 0 info`

## RG-11 — completed

Source plan默认只省略scored_actions，--all-scores恢复完整评分；127项Source测试与原生选项对照通过，默认8449字节/完整28413字节，选中行动一致。

- `python -m pytest tests/source` — exit 0, 14.475s; `127 passed in 13.97s`
- `python <external>/probe_rg11.py` — exit 0, 0.903s; `default_bytes 8449 all_scores_bytes 28413 same native selected actions`
- `python -m pytest --collect-only` — exit 0, 3.523s; `892 tests collected in 3.10s`

## RG-12 — completed

安装器复用只读FG基线的标准库复制/比对逻辑，五技能支持软链接目标；10项测试及系统Python安装/check通过，移除清单预告的唯一无用依赖后地图0错误；收集867。

- `python -m pytest tests/test_install_skill.py tests/test_prompt_bundles.py` — exit 0, 1.16s; `10 passed in 0.70s`
- `python -m flowguard map check` — exit 1, 0.618s; `check: 1 error(s), 10 warning(s), 0 info`
- `python <external>/probe_rg12.py` — exit 0, 0.163s; `standard-library install/check and active residual scan passed`
- `python -m flowguard map check` — exit 0, 0.562s; `check: 0 error(s), 10 warning(s), 0 info`
- `python -m pytest --collect-only` — exit 0, 4.166s; `867 tests collected in 3.59s`

## RG-13 — completed

失败评估追加evaluation_failed开放缺口并返回ok:false/CLI2；成功写回及append_unique_by_id不变。39项Trace测试、真实失败CLI与868项收集通过。

- `python -m pytest tests/trace/test_traceguard.py` — exit 0, 50.129s; `39 passed in 49.57s`
- `python <external>/probe_rg13.py` — exit 0, 2.393s; `rc 2`
- `python -m pytest --collect-only` — exit 0, 7.69s; `868 tests collected in 6.83s`

## RG-14 — completed

Experiment recommend补默认非领域循环字段，坏输入给JSON/CLI2，删除同义iterate；原最小集合和holdout/schema验证不动。66项实验测试、最小spec选e1及缺字段错误探针通过，收集869。

- `python -m pytest tests/experiment` — exit 0, 19.436s; `66 passed in 18.92s`
- `python <external>/probe_rg14.py` — exit 0, 0.953s; `rc 2`
- `python -m pytest --collect-only` — exit 0, 6.135s; `869 tests collected in 5.36s`

## RG-15 — completed

仅删两次无universe必blocked的蓝图impact调用和两个空affected_object_ids字段；缺口转移和native_depth_receipt保留。针对性10pass/收集869；完整检查点856pass13skip，双模型通过，map0error10阶段性WARN。

- `python -m pytest tests/trace/test_task_iteration.py` — exit 0, 2.889s; `10 passed in 2.51s`
- `python <external>/probe_rg15.py` — exit 0, 0.032s; `no misleading impact fields or blueprint calls; native transitions/receipts retained`
- `python -m pytest --collect-only` — exit 0, 3.52s; `869 tests collected in 3.10s`
- `python -m pytest` — exit 0, 422.451s; `856 passed, 13 skipped in 421.66s (0:07:01)`
- `python -m flowguard map models` — exit 0, 1.451s; `models: 2 passed, 0 failed`
- `python -m flowguard map check` — exit 0, 0.877s; `check: 0 error(s), 10 warning(s), 0 info`

## RG-16 — completed

目的契约可选，显式提供仍走原绑定路径。47测试通过；真实无契约空starter schema_ok/trace0/okfalse，案例模型trace1/oktrue且深度BLOCKED仍可见；收集870。

- `python -m pytest tests/trace/test_traceguard.py tests/trace/test_guard_model_purpose_contract.py` — exit 0, 61.447s; `47 passed in 60.91s (0:01:00)`
- `python <external>/probe_rg16.py` — exit 0, 2.457s; `contract-free starter and library model are honest and valid`
- `python -m pytest --collect-only` — exit 0, 5.48s; `870 tests collected in 4.90s`

## RG-17 — completed

移除精确版本测试和CI固定FG断言，FG唯一git test-extra与publisher一致性门保留。28pass/收集866；产品活跃版本命中完全符合清单，原始/journal/active扫描分别外存。按根统一规则仅额外排除SLIM_LOG.md，保留其真实历史版本/命令。

- `python -m pytest tests/logic/test_public_api.py tests/test_suite_routing.py` — exit 0, 36.03s; `28 passed in 35.44s`
- `python <external>/probe_rg17.py` — exit 0, 0.32s; `version authority scans passed; truthful journal preserved`
- `python -m pytest --collect-only` — exit 0, 5.218s; `866 tests collected in 4.57s`

## RG-18 — completed

提示词检查器仅保留字节预算、引用声明和禁止急切加载；删除清单明确的术语锁定/索引重复测试，预算反例仍保。checker pass，10pass，收集861且无routing/render/self_dna残留。

- `python scripts/check_prompt_bundles.py` — exit 0, 0.066s; `pass`
- `python -m pytest tests/test_prompt_bundles.py tests/test_skill_suite.py` — exit 0, 2.53s; `10 passed in 2.05s`
- `python -m pytest --collect-only` — exit 0, 4.242s; `861 tests collected in 3.76s`
- `python -c from pathlib import Path; s=Path("scripts/check_prompt_bundles.py").read_text(); assert not any(x in s for x in ("routing","render_member_admission_index","conditional_blueprint_boundaries","self_dna")); print("checker only retains budget, declared references and eager-member-load limits")` — exit 0, 0.046s; `checker only retains budget, declared references and eager-member-load limits`

## RG-19 — completed

伞形技能按清单改为成员路由和顺序交接，删三参考；失败结果可见且不可换成员重试。入口1738字节，预算/引用检查和10项技能测试通过，伞形references为0。

- `python scripts/check_prompt_bundles.py --json` — exit 0, 0.044s; `}`
- `python -m pytest tests/test_prompt_bundles.py tests/test_skill_suite.py` — exit 0, 2.079s; `10 passed in 1.77s`
- `python -c from pathlib import Path; p=Path("skills/researchguard/references"); assert not p.exists() or not list(p.iterdir()); print("0 umbrella references")` — exit 0, 0.031s; `0 umbrella references`

## RG-20 — completed

LogicGuard技能仅删清单指定蓝图/模板/目的契约说明，保推理与来源/结构指导，修11个示例路径并补revision-store更严格provenance/holdout说明。入口5942字节；14pass、四真实示例CLI0、指定残留为空；完整检查点848pass13skip、双模型通过、map0error10阶段性WARN。

- `python scripts/check_prompt_bundles.py --json` — exit 0, 0.053s; `}`
- `python -m pytest tests/test_prompt_bundles.py tests/test_skill_suite.py tests/logic/test_diagram_semantics_guidance.py tests/logic/test_ai_modeled_source_intake_guidance.py` — exit 0, 2.624s; `14 passed in 2.28s`
- `python <external>/probe_rg20.py` — exit 0, 2.351s; `LogicGuard guidance residuals clean and four real example commands passed`
- `python -m pytest` — exit 0, 437.788s; `848 passed, 13 skipped in 437.21s (0:07:17)`
- `python -m flowguard map models` — exit 0, 1.429s; `models: 2 passed, 0 failed`
- `python -m flowguard map check` — exit 0, 0.923s; `check: 0 error(s), 10 warning(s), 0 info`

Coordinator scheduling update: independent review permits RG-39–RG-54 after a real committed LW-43 snapshot instead of waiting for LW-59. Still stop at RG-38 and wait for the coordinator’s explicit grant and read-only snapshot, then stop at RG-54 for current FlowGuard. RG-47/RG-48 compatibility must prove actual native PASSED/ready and source origin; skipped tests selected by the interim self-reported version are not compatibility evidence.

## RG-21 — completed

SourceGuard删信息蓝图/模板/目的证明和手填每义务哈希说明，保真实source depth/源角色/独立性和契约可用性；仅删术语字符串锁定测试。入口5744字节，136pass，收集860，指定残留为空。

- `python scripts/check_prompt_bundles.py --json` — exit 0, 0.173s; `}`
- `python -m pytest tests/test_prompt_bundles.py tests/test_skill_suite.py tests/source` — exit 0, 14.89s; `136 passed in 14.21s`
- `python -m pytest --collect-only` — exit 0, 4.492s; `860 tests collected in 4.00s`
- `python -c import subprocess; p=subprocess.run(["rg","-n","-i","issuer|DNA|FlowGuard-owned|blueprint|template pack|purpose proof","skills/sourceguard"],capture_output=True,text=True); print(p.stdout,end=""); assert p.returncode==1; print("SourceGuard removed-boundary terms absent")` — exit 0, 0.05s; `SourceGuard removed-boundary terms absent`

## RG-22 — completed

Trace技能去蓝图/模板/目的契约说明，保数学推理、事件/解释/结果边界及案例保存未评估声明；命令改短摘要/output，补真实required holdout。入口5557字节，10pass，指定残留为空，decide原生help中holdout声明2处。

- `python scripts/check_prompt_bundles.py --json` — exit 0, 0.053s; `}`
- `python -m pytest tests/test_prompt_bundles.py tests/test_skill_suite.py` — exit 0, 2.089s; `10 passed in 1.78s`
- `python -c import subprocess,sys; p=subprocess.run(["rg","-n","-i","issuer|DNA|FlowGuard-owned|blueprint|template pack|purpose-contract|purpose contract|library-depth|guard_model","skills/traceguard"],capture_output=True,text=True);print(p.stdout,end="");assert p.returncode==1;p=subprocess.run([sys.executable,"-m","researchguard","trace","iterate","decide","--help"],capture_output=True,text=True);assert p.returncode==0;assert p.stdout.count("--holdout-observation")==2;print("removed terms absent; native decide help declares holdout twice")` — exit 0, 0.434s; `removed terms absent; native decide help declares holdout twice`

## RG-23 — completed

Experiment技能删蓝图说明，新增原样可执行最小spec并记observe；holdout和零幸存者Hard Gates及现循环指导保留，降低四成员预算。入口4633字节，真实示例推荐e1/e2，22pass/收集859，JSON/残留/目录检查通过。

- `python <external>/probe_rg23.py` — exit 0, 0.437s; `JSON valid; exact skill example recommended both experiments; residual and directories clean`
- `python scripts/check_prompt_bundles.py --json` — exit 0, 0.074s; `}`
- `python -m pytest tests/test_prompt_bundles.py tests/test_skill_suite.py tests/logic/test_dynamic_model_purpose_contract.py` — exit 0, 2.936s; `22 passed in 2.55s`
- `python -m pytest --collect-only` — exit 0, 5.515s; `859 tests collected in 5.03s`

## RG-24 — completed

删除run及逐成员预绑定证明，保_member_main懒加载/版本格式和未知命令JSON；8+26测试通过，真实run返回unknown-command/2，importtime不加载routing，logic validate通过，LW44pass，收集852、双模型通过/map0error。

- `python -m pytest tests/test_root_cli.py tests/test_skill_suite.py` — exit 0, 2.205s; `8 passed in 1.66s`
- `python <external>/probe_rg24.py` — exit 0, 2.913s; `validation: OK`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py tests/e2e/test_production_reader_pipeline.py tests/contract/test_production_reader_native_lifecycle.py` — exit 0, 4.55s; `============================== 44 passed in 2.77s ==============================`
- `python -m pytest --collect-only` — exit 0, 3.883s; `852 tests collected in 3.45s`
- `python -m flowguard map models` — exit 0, 1.015s; `models: 2 passed, 0 failed`
- `python -m flowguard map check` — exit 0, 0.575s; `check: 0 error(s), 10 warning(s), 0 info`
- `python -m pytest tests/test_member_model_envelope.py` — exit 0, 74.678s; `26 passed in 74.03s (0:01:14)`

Coordinator grant: after all RG-38 purpose checks pass, continue RG-39–RG-54 against the exact committed read-only LW-43 snapshot (`0d55ca52a9e0`), with external JUnit and no pytest/bytecode cache writes to that snapshot. RG-47/RG-48 require actual native PASSED/ready and verified source origin, not version-selected skips. Stop after RG-54 until the current FlowGuard FG-98 grant. The RG-01–RG-38 immutable baseline dependencies are unchanged.

## RG-25 — completed

删除四CLI蓝图组及route-depth/library-depth，仅删三个CLI入口测试和两个声明包检查器及其测试；深度/import-handoff/案例存储保留。239pass、LW44pass、收集834、四help零残留；全量821pass13skip，双模型通过，map0error10阶段性WARN。

- `python <external>/probe_rg25.py` — exit 0, 1.662s; `only intentionally deferred guard_model_contract docstring remains`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py tests/e2e/test_production_reader_pipeline.py tests/contract/test_production_reader_native_lifecycle.py` — exit 0, 5.223s; `============================== 44 passed in 4.60s ==============================`
- `python -m pytest --collect-only` — exit 0, 7.816s; `834 tests collected in 6.88s`
- `python -m flowguard map check` — exit 0, 2.034s; `check: 0 error(s), 10 warning(s), 0 info`
- `python -m pytest tests/logic/test_cli.py tests/logic/test_artifact_inventory.py tests/source/test_blueprint_graph.py tests/trace/test_blueprint_hierarchy.py tests/trace/test_traceguard.py tests/experiment tests/test_root_cli.py` — exit 0, 138.107s; `239 passed in 137.30s (0:02:17)`
- `python -m pytest` — exit 0, 407.622s; `821 passed, 13 skipped in 406.86s (0:06:46)`
- `python -m flowguard map models` — exit 0, 1.471s; `models: 2 passed, 0 failed`
- `python -m flowguard map check` — exit 0, 0.54s; `check: 0 error(s), 10 warning(s), 0 info`

## RG-SUP-01 — completed (separate coordinator-authorized fix)

Cross-repository review found that the RG-12 copied installer used shallow stat comparisons. An independent temporary-directory probe confirmed that a one-byte same-size change with restored mtime was falsely called current (CLI 0); the new assertion failed before the fix. Compare every existing common file with `read_bytes()` instead, keep the directory traversal and existing diagnostics, and report common-funny type/stat mismatches and read errors. No manifest or receipt owner is added.

- Before fix: real CLI incorrectly returned current/0; targeted regression failed (expected exit 1).
- After fix: `python -m pytest tests/test_install_skill.py` — exit 0, 2 passed; existing test includes equal-stat byte drift, ordinary drift and file/directory mismatch.
- Real CLI now returns 1 with `logicguard: differs: SKILL.md`; equal bytes still pass.
- Same-process probe: equal bytes pass; same-stat changed bytes fail; restored bytes pass; type mismatch fails.
- System Python installation/check remains current/0.
- `python -m flowguard map check` — exit 0, 0 errors / 10 interim warnings; component description/confirmation remains scheduled at RG-38.

Full command logs, actual return codes, pre/post installer content hashes and independent-review evidence are external.

## RG-26 — completed

仅删来源分支receipt门/解析器与请求中该字段必填，保分支身份、锚点、模型/来源库绑定检查及native_evidence_ref数据兼容、现native_depth。24pass、LW44pass、收集834，指定收据门残留为空。

- `python -m pytest tests/logic/test_synthesis_contract.py tests/logic/test_artifact_synthesis.py tests/logic/test_synthesis_native_closure.py tests/logic/test_delivery_contract.py` — exit 0, 0.784s; `24 passed in 0.51s`
- `python -c import subprocess;p=subprocess.run(["rg","-n","native_receipts|_native_evidence_reference_gaps|native_evidence_missing","src/researchguard/logic/synthesis.py","src/researchguard/logic/synthesis_contract.py"],capture_output=True,text=True);print(p.stdout,end="");assert p.returncode==1;print("receipt gate removed; data/native-depth/source binding paths retained")` — exit 0, 0.036s; `receipt gate removed; data/native-depth/source binding paths retained`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py tests/e2e/test_production_reader_pipeline.py tests/contract/test_production_reader_native_lifecycle.py` — exit 0, 2.163s; `============================== 44 passed in 1.85s ==============================`
- `python -m pytest --collect-only` — exit 0, 3.342s; `834 tests collected in 2.89s`

## RG-27 — completed

按授权删无CLI外部领域DNA/签名范围与6份测试密钥夹具/编译器及其专测，删其懒导出和Windows点名测试；root retired-command拒绝仍保。26pass、exports ok、收集805、map0error；指定残留仅两行未知命令测试变量，models目录已无。

- `python -c import subprocess;from pathlib import Path;p=subprocess.run(["rg","-n","domain_dna|external_scope_authority|external_domain","src/researchguard","scripts","tests",".github","skills","pyproject.toml","README.md","AGENTS.md"],capture_output=True,text=True);print(p.stdout,end="");rows=p.stdout.splitlines();assert rows and all(r.startswith("tests/test_root_cli.py:") and "domain_dna" in r for r in rows);assert not Path("models").exists();print("only retired-command rejection variables remain; models directory removed")` — exit 0, 0.052s; `only retired-command rejection variables remain; models directory removed`
- `python -m pytest tests/test_suite_routing.py tests/test_root_cli.py` — exit 0, 20.313s; `26 passed in 19.92s`
- `python <external>/check_exports.py` — exit 0, 0.774s; `exports ok`
- `python -m pytest --collect-only` — exit 0, 3.454s; `805 tests collected in 3.01s`
- `python -m flowguard map check` — exit 0, 0.794s; `check: 0 error(s), 10 warning(s), 0 info`

## RG-28 — completed

按明确授权删证明传输层及4成员蓝图/专测/自动测试密钥夹具；保suite_fingerprint/identity、原生最小实验集/holdout、结构分析及Trace求解。直接owner重播模型通过，exports ok；原生67pass、模板16pass、LW44pass、收集566；仅2预期catalog指纹重封存，6条实际无用依赖精确删后map0error11阶段性WARN，指定残留仅3条注释/退后测试名。

- `python -c from pathlib import Path; files=list(Path("src").rglob("*.py"));[compile(p.read_text(),str(p),"exec") for p in files];print("compiled source",len(files),"without writing bytecode")` — exit 0, 0.453s; `compiled source 133 without writing bytecode`
- `python <external>/check_exports.py` — exit 0, 0.679s; `exports ok`
- `python scripts/reseal_member_catalogs.py` — exit 0, 0.727s; `ResearchGuard member catalogs resealed; logic=1 source=1 trace=1 source_examples=0`
- `python -m flowguard map check` — exit 1, 0.968s; `check: 2 error(s), 11 warning(s), 0 info`
- `python -m flowguard map check` — exit 0, 0.481s; `check: 0 error(s), 11 warning(s), 0 info`
- `python -m pytest tests/experiment tests/test_root_cli.py tests/logic/test_structured_artifact.py tests/logic/test_citation_matrix.py tests/trace/test_storyline_depth.py tests/test_prompt_bundles.py tests/test_skill_suite.py` — exit 0, 14.046s; `67 passed in 13.69s`
- `python -m pytest tests/logic_template_packs` — exit 0, 1.695s; `16 passed in 1.39s`
- `python -m flowguard map models` — exit 0, 1.405s; `models: 2 passed, 0 failed`
- `python -c import subprocess;p=subprocess.run(["rg","-n","-g","*.py",r"routing|model_envelope|native_receipts|target_authority|owner_attestation|artifact_inventory import|from \.blueprint|admission_fixtures","src/researchguard","tests","scripts",".flowguard/models"],capture_output=True,text=True);print(p.stdout,end="");rows=p.stdout.splitlines();assert len(rows)==3,rows;assert all(any(x in r for x in ("public console for routing","Gap-ledger routing","test_public_depth_requires_explicit_target_authority")) for r in rows);print("only three explicitly deferred comments/test-name references remain")` — exit 0, 0.05s; `only three explicitly deferred comments/test-name references remain`
- `python <external>/probe_rg23.py` — exit 0, 0.12s; `JSON valid; exact skill example recommended both experiments; residual and directories clean`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py tests/e2e/test_production_reader_pipeline.py tests/contract/test_production_reader_native_lifecycle.py` — exit 0, 2.506s; `============================== 44 passed in 2.22s ==============================`
- `python -m pytest --collect-only` — exit 0, 2.63s; `566 tests collected in 2.18s`
