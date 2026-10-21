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

## RG-29 — completed

Source契约可选：缺省直接运行模型并正常观察更新，嵌入/显式旧契约仍校验一致，旧iteration侧车可选但原循环和native判断不变。99pass、真实create/validate/含旧嵌入契约示例plan无侧车均0、唯一可选文档说明/提示词通过；收集567/map0error。

- `python -m pytest tests/source tests/logic_template_packs` — exit 0, 7.107s; `99 passed in 6.74s`
- `python <external>/probe_rg29.py` — exit 0, 0.729s; `model-only CLI works; optional contract is documented once`
- `python scripts/check_prompt_bundles.py` — exit 0, 0.043s; `pass`
- `python -m pytest --collect-only` — exit 0, 3.324s; `567 tests collected in 2.89s`
- `python -m flowguard map check` — exit 0, 0.719s; `check: 0 error(s), 11 warning(s), 0 info`

## RG-30 — completed

删Trace目的契约及封存包/专测/两个CLI选项；保schema_version、旧guard_purpose元数据忽略、求解器、深度、案例写回。Trace105pass/LW44pass，真实创建与案例构建0、旧选项2且不写文件；精确移除预告author→trace无用依赖后map0error。完整检查点560pass（tkinter可用无skip）/双模型通过，收集560。

- `python -m flowguard map check` — exit 1, 0.628s; `check: 1 error(s), 11 warning(s), 0 info`
- `python -m pytest tests/trace` — exit 0, 45.809s; `105 passed in 45.42s`
- `python <external>/probe_rg30.py` — exit 0, 0.997s; `retired contract source/options/pack residues absent; native create/library build remain`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py tests/e2e/test_production_reader_pipeline.py tests/contract/test_production_reader_native_lifecycle.py` — exit 0, 2.008s; `============================== 44 passed in 1.75s ==============================`
- `python -m pytest --collect-only` — exit 0, 2.337s; `560 tests collected in 1.96s`
- `python -m flowguard map check` — exit 0, 0.289s; `check: 0 error(s), 11 warning(s), 0 info`
- `python -m pytest` — exit 0, 160.769s; `560 passed in 160.32s (0:02:40)`
- `python -m flowguard map models` — exit 0, 1.532s; `models: 2 passed, 0 failed`
- `python -m flowguard map check` — exit 0, 0.306s; `check: 0 error(s), 11 warning(s), 0 info`

## RG-31 — completed

仅删Trace义务内容/哈希重复字段及生成器和专测，effects/object_depth_rows/扰动计划/原生缺口保留。104pass，两个真实evaluate输出31543/66634字节且oktrue/closurePASS；指定残留为空、收集559/map0error。

- `python -m pytest tests/trace` — exit 0, 43.853s; `104 passed in 43.45s`
- `python <external>/probe_rg31.py` — exit 0, 2.154s; `Trace obligation-content copies absent; native effects/coverage/gaps remain`
- `python -m pytest --collect-only` — exit 0, 6.221s; `559 tests collected in 5.20s`
- `python -m flowguard map check` — exit 0, 0.517s; `check: 0 error(s), 11 warning(s), 0 info`

## RG-32 — completed

仅删指定锁文字/源码/退役清单测试和重复zero-residual脚本，去旧路径过滤；实际技能入口/内部路由/retired projection拒绝/CLI行为、GUI元信息功能与历史CHANGELOG保留。17pass（tkinter可用），活跃skillguard残留为空，收集548/map0error。

- `python -m pytest tests/test_skill_suite.py tests/logic/test_library_viewer.py tests/contract` — exit 0, 1.671s; `17 passed in 1.34s`
- `python -c import subprocess;p=subprocess.run(["rg","-n","-i","skillguard","scripts","tests","src/researchguard","skills"],capture_output=True,text=True);print(p.stdout,end="");assert p.returncode==1;print("SkillGuard active residuals absent; historical CHANGELOG retained")` — exit 0, 0.054s; `SkillGuard active residuals absent; historical CHANGELOG retained`
- `python -m pytest --collect-only` — exit 0, 2.757s; `548 tests collected in 2.32s`
- `python -m flowguard map check` — exit 0, 0.581s; `check: 0 error(s), 11 warning(s), 0 info`

## RG-33 — completed

套件模型删版本自证/包身份工作流/8退役组合场景及无人读model-definition，保7现行场景、4原生类与坏变体/conformance。2模型pass，7场景实数，活跃旧版本仅pyproject/init；548收集/map0error。一次外部-c扫描因__file__缺失启动失败，原expected0/exit1完整保留，改直接脚本后扫描0；不属于产品失败。

- `python -m flowguard map models` — exit 0, 1.63s; `models: 2 passed, 0 failed`
- `python -c import ast;from pathlib import Path;p=Path(".flowguard/models/researchguard_suite_model.py");m=ast.parse(p.read_text());rows=[n for n in ast.walk(m) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="Scenario"];assert len(rows)==7;print("7 retained direct/failure/handoff/reentry/loading scenarios");exec(compile(Path("<external>/probe_rg33.py").read_text(),"external/probe_rg33.py","exec"))` — exit 1, 0.087s; `7 retained direct/failure/handoff/reentry/loading scenarios`
- `python -c import ast;from pathlib import Path;m=ast.parse(Path(".flowguard/models/researchguard_suite_model.py").read_text());rows=[n for n in ast.walk(m) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="Scenario"];assert len(rows)==7;print("7 retained direct/failure/handoff/reentry/loading scenarios")` — exit 0, 0.042s; `7 retained direct/failure/handoff/reentry/loading scenarios`
- `python <external>/probe_rg33.py` — exit 0, 0.154s; `version authority scans passed; truthful journal preserved`
- `python -m pytest --collect-only` — exit 0, 5.003s; `548 tests collected in 3.17s`
- `python -m flowguard map check` — exit 0, 0.291s; `check: 0 error(s), 11 warning(s), 0 info`

## RG-34 — completed

删明确授权无人读取的存档/迁移/资源副本/旧参考及5空壳模块，保真正viewer图标、技能推理协议和simulator函数。41pass，4图标hash前后全同、双模型通过、547收集/map0error。原目录探针因ignored __pycache__多一项exit1，保原始列举/期望；不清理此缓存，限定排除后git ls-files恰2模型且活跃残留为空。

- `python <external>/probe_rg34_assets.py before` — exit 0, 0.032s; `4 duplicate icon copies exactly match retained native viewer assets`
- `python -m pytest tests/trace/test_traceguard.py tests/logic/test_report.py` — exit 0, 23.47s; `41 passed in 23.10s`
- `python <external>/probe_rg34_assets.py after` — exit 0, 0.05s; `4 native viewer icons remain byte-identical; only duplicate resources removed`
- `python <external>/probe_rg34.py` — exit 1, 0.038s; `AssertionError: {'researchguard_suite_model.py', '__pycache__', 'sourceguard_content_anchor_oracle_model.py'}`
- `python <external>/probe_rg34_product_inventory.py` — exit 0, 0.066s; `unused directories/active references absent; true inference reference and simulator functions retained`
- `python -m flowguard map models` — exit 0, 1.659s; `models: 2 passed, 0 failed`
- `python -m pytest --collect-only` — exit 0, 2.967s; `547 tests collected in 2.35s`
- `python -m flowguard map check` — exit 0, 0.345s; `check: 0 error(s), 11 warning(s), 0 info`

## RG-35 — completed

预算manifest仅移到scripts并改两个消费者路径/说明，内容不变，同名顶层researchguard目录移除。checker pass/5pass、旧路径残留为空、收集547；完整检查点547pass（tkinter可用）、双模型通过、map0error11阶段性WARN。

- `python scripts/check_prompt_bundles.py` — exit 0, 0.048s; `pass`
- `python -m pytest tests/test_prompt_bundles.py` — exit 0, 0.263s; `5 passed in 0.02s`
- `python -c from pathlib import Path;import subprocess;assert not Path("researchguard").exists();p=subprocess.run(["rg","-n",r"\"researchguard\" / \"prompt_bundle_manifest.json\"","scripts","tests"],capture_output=True,text=True);print(p.stdout,end="");assert p.returncode==1;print("same-name root namespace directory absent; manifest content retained")` — exit 0, 0.046s; `same-name root namespace directory absent; manifest content retained`
- `python -m pytest --collect-only` — exit 0, 2.529s; `547 tests collected in 2.14s`
- `python -m pytest` — exit 0, 107.683s; `547 passed in 107.22s (0:01:47)`
- `python -m flowguard map models` — exit 0, 1.975s; `models: 2 passed, 0 failed`
- `python -m flowguard map check` — exit 0, 0.497s; `check: 0 error(s), 11 warning(s), 0 info`

## RG-36 — completed

Windows冒烟改6个现存功能测试文件，删不存在VERSION的push触发但保存在时一致性检查；FG唯一test extra来源、精确SHA CI/publisher门和Linux全量保持。53pass、双workflow YAML解析通过、VERSION仅条件检查2行，收集547。

- `python -m pytest tests/test_install_skill.py tests/test_root_cli.py tests/logic/test_cli.py tests/source/test_cli.py tests/trace/test_inference_kernel.py tests/experiment/test_recommendation.py` — exit 0, 29.606s; `53 passed in 28.92s`
- `python -c import yaml;from pathlib import Path;[yaml.safe_load(Path(p).read_text()) for p in (".github/workflows/ci.yml",".github/workflows/publish-release.yml")];s=Path(".github/workflows/publish-release.yml").read_text();rows=[l.strip() for l in s.splitlines() if "VERSION" in l];print("yaml ok");print("\n".join(rows));assert len(rows)==2 and any("if Path(\"VERSION\").exists():" in l for l in rows)` — exit 0, 0.073s; `assert Path("VERSION").read_text(encoding="utf-8").strip() == version, "VERSION differs from pyproject"`
- `python -m pytest --collect-only` — exit 0, 3.781s; `547 tests collected in 3.18s`

## RG-37 — completed

仅收窄两个suite组件的tests到真正归属，成员tests/files/depends/fingerprints不改。真实planner change显示direct sourceguard与18 of69（不再全选）；双模型通过，map0error且无test_missing。

- `python -m flowguard change src/researchguard/source/planner.py` — exit 0, 1.076s; `ARCH WARN duplicate_code sourceguard: 2 identical bodies (216 AST nodes) in ['sourceguard', 'suite-orchestration']: src/researchguard/source/template_packs.py:verify_template_instance, src/researchguard/trace/template_packs.py:verify_template_instance`
- `python -m flowguard map models` — exit 0, 3.627s; `models: 2 passed, 0 failed`
- `python -m flowguard map check` — exit 0, 0.64s; `check: 0 error(s), 11 warning(s), 0 info`

## RG-38 — completed

按现状更新7组件描述并由FlowGuard confirm写指纹，未手改指纹/债务/flows。地图0error4entrypoint警告且无stale，描述残留为空；完整547pass（tkinter可用）、双模型通过；本地release明确2declared/2executed verifyPASS（其自身不跑pytest，已单独跑过）。满足根预授权，随后39–54仅用exactLW43只读快照。

- `python -m flowguard map confirm researchguard-suite suite-orchestration logicguard sourceguard traceguard experimentguard author-tools` — exit 0, 0.205s; `confirmed 7 component(s)`
- `python -m flowguard map check` — exit 0, 0.567s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -c import subprocess;p=subprocess.run(["rg","-n","admission|blueprint|DNA|receipt and target",".flowguard/map.json"],capture_output=True,text=True);print(p.stdout,end="");assert p.returncode==1;print("component descriptions match current ownership; old authority/blueprint descriptions absent")` — exit 0, 0.045s; `component descriptions match current ownership; old authority/blueprint descriptions absent`
- `python -m pytest` — exit 0, 143.145s; `547 passed in 142.64s (0:02:22)`
- `python -m flowguard map models` — exit 0, 2.575s; `models: 2 passed, 0 failed`
- `python -m flowguard release` — exit 0, 2.616s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`

## RG-39 — completed

删3套无CLI模板包/夹具/封存脚本与包数据，只留viewer真实assets；build_artifact_map/synthesize本体保留。173pass、exports、2模型pass、509收集；精确删预告author3无用依赖并confirm4组件后map0error4warnings/releasePASS。LW43只读快照353文件hash与当前RG/FG源码origin已核实；无遗留模板命名空间缓存需清理。

- `python <external>/probe_consumer_origin.py` — exit 0, 0.086s; `}`
- `python -m flowguard map check` — exit 1, 1.396s; `check: 1 error(s), 8 warning(s), 0 info`
- `python -m flowguard map confirm author-tools logicguard sourceguard suite-orchestration` — exit 0, 0.135s; `confirmed 4 component(s)`
- `python -m pytest tests/source tests/trace tests/test_prompt_bundles.py tests/test_skill_suite.py` — exit 0, 48.806s; `173 passed in 48.45s`
- `python <external>/check_exports.py` — exit 0, 0.638s; `exports ok`
- `python -c import subprocess;p=subprocess.run(["rg","-n","-i","template.pack|reseal|logic_template_packs","src","scripts","tests","skills","docs","README.md","pyproject.toml",".github"],capture_output=True,text=True);print(p.stdout,end="");assert p.returncode==1;print("template/reseal active residues absent; real core functions and viewer asset package-data retained")` — exit 0, 0.056s; `template/reseal active residues absent; real core functions and viewer asset package-data retained`
- `python -m pytest --collect-only` — exit 0, 3.438s; `509 tests collected in 3.02s`
- `python -m flowguard map check` — exit 0, 0.301s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 1.755s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`
- `python -m flowguard map models` — exit 0, 1.26s; `models: 2 passed, 0 failed`

## RG-40 — completed

删12 ModelMesh模块/专测/夹具/overlay分支和122退役导出，保普通身份类型、native depth receipt路径及技能通用模型卡方法。26pass/exports/strict residual；LW43 exact快照10全部passed0skip且native reader bridge实际ready，差1计数已记录。完整415pass、双模型pass、map0error4warn、本地releasePASS。

- `python -m flowguard map confirm logicguard suite-orchestration` — exit 0, 0.855s; `confirmed 2 component(s)`
- `python -m pytest tests/logic/test_synthesis_contract.py tests/logic/test_synthesis_native_closure.py tests/logic/test_public_api.py tests/logic/test_cli.py` — exit 0, 33.754s; `26 passed in 32.95s`
- `python <external>/check_exports.py` — exit 0, 0.966s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-40-lw43-junit.xml --basetemp <external>/RG-40-lw43-temp` — exit 0, 0.698s; `============================== 10 passed in 0.38s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-40-lw43-junit.xml` — exit 0, 0.46s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -c import subprocess;p=subprocess.run(["rg","-n","-i","-g","*.py","mesh","src/researchguard"],capture_output=True,text=True);print(p.stdout,end="");assert p.returncode==1;p=subprocess.run(["rg","-n","mesh_|model_mesh|native_mesh|MeshId|ModelMesh","tests","scripts","skills",".flowguard","pyproject.toml",".github"],capture_output=True,text=True);print(p.stdout,end="");assert p.returncode==1;print("ModelMesh code/API residues absent; generic skill modeling wording retained")` — exit 0, 0.071s; `ModelMesh code/API residues absent; generic skill modeling wording retained`
- `python -m pytest --collect-only` — exit 0, 6.666s; `415 tests collected in 6.03s`
- `python -m flowguard map check` — exit 0, 1.271s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m pytest` — exit 0, 79.993s; `415 passed in 79.48s (0:01:19)`
- `python -m flowguard map models` — exit 0, 1.476s; `models: 2 passed, 0 failed`
- `python -m flowguard map check` — exit 0, 0.282s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 1.765s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`

## RG-41 — completed

Removed the explicitly retired ModelStore/overlay/rollback stack and receipt fields. The plain-file prediction loop keeps identical native binding, simulation, claim protection, gap lineage and stopping functions; old prediction digest matches and changed models still reject stale predictions. Optional metadata/holdouts work, real native gaps remain visible, CLI leaves baseline/candidate bytes untouched. Logic tests 159 passed; collection 363; fixed LW43 consumer 10 passed with actual native ready/PASSED and no skip (historical 11-case count adapted); exports/map/release passed.

- `python <external>/probe_rg41_old_digest.py` — exit 0, 0.414s; `old ModelStore digest equals direct canonical model digest; pre-change frozen prediction saved externally sha256:5699042f513204a03f8b943799e1d008594747e825eca757bca1ae7686cce655`
- `python -m pytest tests/logic` — exit 0, 18.616s; `159 passed in 18.12s`
- `python <external>/probe_rg41.py` — exit 0, 1.783s; `old store residues absent; native CLI/bad flags/model bytes verified`
- `python <external>/check_exports.py` — exit 0, 0.486s; `exports ok`
- `python -m pytest --collect-only` — exit 0, 2.159s; `363 tests collected in 1.67s`
- `python -m flowguard map confirm logicguard suite-orchestration` — exit 0, 0.416s; `confirmed 2 component(s)`
- `python -m flowguard map check` — exit 0, 0.338s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 1.77s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-41-lw43-junit.xml --basetemp <external>/RG-41-lw43-temp` — exit 0, 0.786s; `============================== 10 passed in 0.43s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-41-lw43-junit.xml` — exit 0, 0.077s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`

## RG-42 — completed

Source search iteration now returns a result without receipt bindings, accepts optional task metadata, and has no rollback command. Actual native create/freeze/observe/accept closes the qualified example, writes a separate candidate and leaves baseline bytes unchanged. Four native obligation/protected-gap/weight/error/stale-binding functions retain identical ASTs. 82 focused tests passed; collection 363; fixed LW43 actual native bridge passed, 10 cases and 0 skips; exports/map/release passed.

- `python -m pytest tests/source tests/test_prompt_bundles.py tests/test_skill_suite.py` — exit 0, 5.826s; `82 passed in 5.50s`
- `python <external>/probe_rg42.py` — exit 0, 0.893s; `researchguard source search-iteration: error: argument iteration_command: invalid choice: 'rollback' (choose from 'freeze', 'run')`
- `python <external>/check_exports.py` — exit 0, 0.522s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-42-lw43-junit.xml --basetemp <external>/RG-42-lw43-temp` — exit 0, 0.829s; `============================== 10 passed in 0.38s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-42-lw43-junit.xml` — exit 0, 0.056s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 2.062s; `363 tests collected in 1.66s`
- `python -m flowguard map confirm sourceguard suite-orchestration` — exit 0, 0.269s; `confirmed 2 component(s)`
- `python -m flowguard map check` — exit 0, 0.279s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 2.067s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`

## RG-43 — completed

Trace iteration drops detached snapshot/observation/result fingerprints and handwritten bindings. Known target and observed evidence/event/source IDs are checked natively; construction data in a candidate must match the baseline directly. Holdout is optional, with independence enforced when supplied. Timestamp/event-order validation, native gaps and exact baseline-byte stale checks remain. 101 focused tests passed; collection 364; fixed LW43 native ready/PASSED 10 passed 0 skipped; exports/map/release passed.

- `python <external>/probe_rg43.py` — exit 0, 1.678s; `only 2 omitted-key assertions remain`
- `python <external>/check_exports.py` — exit 0, 0.766s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-43-lw43-junit.xml --basetemp <external>/RG-43-lw43-temp` — exit 0, 0.905s; `============================== 10 passed in 0.38s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-43-lw43-junit.xml` — exit 0, 0.043s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 2.661s; `364 tests collected in 2.12s`
- `python -m flowguard map confirm suite-orchestration traceguard` — exit 0, 0.284s; `confirmed 2 component(s)`
- `python -m flowguard map check` — exit 0, 0.429s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m pytest tests/trace tests/test_prompt_bundles.py tests/test_skill_suite.py` — exit 0, 43.674s; `101 passed in 43.26s`
- `python -m flowguard release` — exit 0, 2.021s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`

## RG-44 — completed

Experiment iteration returns a result with optional holdout observations and no receipt/evidence hashes. Native actual minimal-spec CLI closes one survivor without a holdout (1961 bytes); contradictory holdouts, duplicate evidence IDs, zero-survivor matrix misses and finite stopping checks remain in 21 passing tests. Minimum-set search and functional matrix fingerprint ASTs unchanged. Prompt check passed, collection 364, exports/map/release passed; fixed LW43 actual native compatibility 10 passed 0 skipped.

- `python -m pytest tests/experiment` — exit 0, 0.501s; `21 passed in 0.18s`
- `python scripts/check_prompt_bundles.py` — exit 0, 0.045s; `pass`
- `python scripts/check_prompt_bundles.py --json` — exit 0, 0.043s; `}`
- `python <external>/check_exports.py` — exit 0, 0.534s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-44-lw43-junit.xml --basetemp <external>/RG-44-lw43-temp` — exit 0, 0.817s; `============================== 10 passed in 0.35s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-44-lw43-junit.xml` — exit 0, 0.058s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 3.831s; `364 tests collected in 3.21s`
- `python -m flowguard map confirm experimentguard suite-orchestration` — exit 0, 0.208s; `confirmed 2 component(s)`
- `python -m flowguard map check` — exit 0, 0.264s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 2.656s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`
- `python <external>/probe_rg44.py` — exit 0, 0.208s; `tests/experiment/test_recommendation.py:216:    assert "receipt_fingerprint" not in result.to_dict()`

## RG-45 — completed

Deleted the explicitly retired SourceGuard contract code/options/fixtures and sidecars; old YAML contract blocks are ignored while native planning, graph checks, qualification and contentless-anchor rejection remain. Initial finite run: 111 passed and one test retained an obsolete CLI flag; removed that flag per action and exact failed case passed. Final prescribed complete checkpoint: 355 passed (Tk available), collection 355, both models passed; actual old-model validate/native plan/retired-option rejection, fixed LW43 native 10 passed without skip, exports/map/release passed. Journal paths normalized to portable placeholders without changing historical facts.

- `python <external>/probe_rg45.py` — exit 0, 0.675s; `old model with contract block loads; plain model plan works; retired flag rejects; only 2 approved names remain`
- `python <external>/check_exports.py` — exit 0, 1.666s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-45-lw43-junit.xml --basetemp <external>/RG-45-lw43-temp` — exit 0, 0.639s; `============================== 10 passed in 0.33s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-45-lw43-junit.xml` — exit 0, 0.051s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 3.296s; `355 tests collected in 2.79s`
- `python -m flowguard map confirm sourceguard suite-orchestration` — exit 0, 1.196s; `confirmed 2 component(s)`
- `python -m flowguard map check` — exit 0, 0.717s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m pytest tests/source tests/test_prompt_bundles.py tests/test_skill_suite.py tests/trace/test_traceguard.py` — exit 1, 45.459s; `1 failed, 111 passed in 45.12s`
- `python -m flowguard release` — exit 0, 3.466s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`
- `python -m flowguard map models` — exit 0, 2.919s; `models: 2 passed, 0 failed`
- `python -m pytest tests/source/test_task_iteration.py::test_cli_freeze_rejects_old_shape_and_emits_v2` — exit 0, 0.783s; `1 passed in 0.31s`
- `python -m pytest` — exit 0, 102.096s; `355 passed in 101.64s (0:01:41)`

## RG-46 — completed

Removed only duplicate per-obligation/source-anchor evidence hashes and the dedicated copy test. Exact native broad-analysis result compares identical after omitting those deleted keys (36198 to 14591 JSON chars); CLI examples 8477/11214 bytes, content/lineage/coverage/gaps unchanged. Source tests 63 passed, collection 354; exports, fixed LW43 actual bridge 10 passed no skips, map and local release passed (both models executed).

- `python <external>/capture_rg46_before.py` — exit 0, 0.3s; `captured exact broad native result before removal pass 36198`
- `python -m pytest tests/source` — exit 0, 10.705s; `63 passed in 9.92s`
- `python <external>/probe_rg46.py` — exit 0, 2.168s; `real CLI output bytes 11214 status planning_only`
- `python <external>/check_exports.py` — exit 0, 1.673s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-46-lw43-junit.xml --basetemp <external>/RG-46-lw43-temp` — exit 0, 1.343s; `============================== 10 passed in 0.70s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-46-lw43-junit.xml` — exit 0, 0.075s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 3.827s; `354 tests collected in 3.25s`
- `python -m flowguard map confirm sourceguard` — exit 0, 0.27s; `confirmed 1 component(s)`
- `python -m flowguard map check` — exit 0, 0.353s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 5.33s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`

## RG-47 — completed

After verifying immutable LW43 source origin, all 353 hashes and absence of retired depth/suite consumers, removed the external depth receipt/purpose-contract chain and duplicate obligation hashes. Synthesis always computes current native depth in process: actual missing warrant still blocks, external depth request key now rejects, retired CLI flags reject. Logic tests 143 passed (Tk available), collection 338; fixed LW43 real native bridge actually ready/PASSED with 10 passed and zero skips; exports/map/release passed.

- `python <external>/probe_consumer_origin.py` — exit 0, 0.105s; `}`
- `python -c import subprocess;p=subprocess.run(["rg","-n","-g","*.py","guard-contract|native_depth_receipt|suite_fingerprint|researchguard\\.suite","<LW43-snapshot>"],capture_output=True,text=True);print(p.stdout,end="");assert p.returncode==1;print("LW43 committed snapshot has no retired depth/suite consumer chain")` — exit 0, 0.044s; `LW43 committed snapshot has no retired depth/suite consumer chain`
- `python -m pytest tests/logic` — exit 0, 25.328s; `143 passed in 24.86s`
- `python <external>/check_exports.py` — exit 0, 0.606s; `exports ok`
- `python <external>/probe_rg47.py` — exit 0, 3.136s; `LW43 retirement precondition exact regex passed; no external depth admission; actual native warrant gap remains`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-47-lw43-junit.xml --basetemp <external>/RG-47-lw43-temp` — exit 0, 1.582s; `============================== 10 passed in 0.80s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-47-lw43-junit.xml` — exit 0, 0.21s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 6.926s; `338 tests collected in 4.67s`
- `python -m flowguard map confirm logicguard researchguard-suite suite-orchestration` — exit 0, 0.926s; `confirmed 3 component(s)`
- `python -m flowguard map check` — exit 0, 0.36s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 5.174s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`

## RG-48 — completed

Retired the caller-free suite fingerprint module after exact consumer preconditions passed. Package version/constants and native member CLI/version output remain. 19 focused suite/install/contract tests passed; complete checkpoint 338 passed with Tk available; both models passed, fixed LW43 native bridge actual ready/PASSED 10 passed zero skips; active residual scan, exports/map/local release passed.

- `python -c import subprocess;p=subprocess.run(["rg","-n",r"suite_fingerprint|suite_identity|governed_file_manifest|researchguard\.suite\b","src","tests","scripts",".flowguard/models"],capture_output=True,text=True);print(p.stdout,end="");assert p.returncode==0 and all(x.startswith("src/researchguard/suite.py:") for x in p.stdout.splitlines());p=subprocess.run(["rg","-n","-g","*.py",r"guard-contract|native_depth_receipt|suite_fingerprint|researchguard\.suite","<LW43-snapshot>"],capture_output=True,text=True);assert p.returncode==1;print("only retired suite module self references; no immutable LW43 callers")` — exit 0, 0.073s; `only retired suite module self references; no immutable LW43 callers`
- `python -m pytest tests/test_root_cli.py tests/test_skill_suite.py tests/test_prompt_bundles.py tests/test_install_skill.py tests/contract` — exit 0, 3.651s; `19 passed in 2.59s`
- `python -c import subprocess;p=subprocess.run(["rg","-n","-i",r"suite_fingerprint|suite_identity|governed_file_manifest|researchguard\.suite\b|suite fingerprint","src","tests","scripts","skills","docs","README.md",".flowguard/models","pyproject.toml",".github"],capture_output=True,text=True);print(p.stdout,end="");assert p.returncode==1;print("retired suite fingerprint surface absent")` — exit 0, 0.145s; `retired suite fingerprint surface absent`
- `python <external>/check_exports.py` — exit 0, 1.825s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-48-lw43-junit.xml --basetemp <external>/RG-48-lw43-temp` — exit 0, 1.04s; `============================== 10 passed in 0.54s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-48-lw43-junit.xml` — exit 0, 0.076s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 2.998s; `338 tests collected in 2.47s`
- `python -m flowguard map confirm researchguard-suite` — exit 0, 0.146s; `confirmed 1 component(s)`
- `python -m flowguard map check` — exit 0, 0.317s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 4.637s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`
- `python -m pytest` — exit 0, 77.397s; `338 passed in 76.81s (0:01:16)`
- `python -m flowguard map models` — exit 0, 1.905s; `models: 2 passed, 0 failed`

## RG-49 — completed

Added the read-only model adapter and stop-decision CLI, which passes the native top action score/cost, blocking gaps and caller budget to the unchanged stop owner. Actual CLI shows continue at budget 1, blocked critical at 0.1, sufficient for the empty model and missing-budget exit 2. 65 source tests passed; collection 340; fixed LW43 native bridge 10 passed no skips, exports/map/release passed.

- `python -m pytest tests/source` — exit 0, 4.563s; `65 passed in 4.24s`
- `python <external>/probe_rg49.py` — exit 0, 0.735s; `researchguard source stop-decision: error: the following arguments are required: --budget`
- `python <external>/check_exports.py` — exit 0, 0.473s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-49-lw43-junit.xml --basetemp <external>/RG-49-lw43-temp` — exit 0, 0.546s; `============================== 10 passed in 0.28s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-49-lw43-junit.xml` — exit 0, 0.047s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 2.022s; `340 tests collected in 1.63s`
- `python -m flowguard map confirm sourceguard suite-orchestration` — exit 0, 0.221s; `confirmed 2 component(s)`
- `python -m flowguard map check` — exit 0, 0.356s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 1.76s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`

## RG-50 — completed

Added minimal-sets CLI and a model-native evaluator adapter; existing minimization/license algorithms and simulator are unchanged. Actual deck claim returns assert with deletion-minimal E1/L1/W1, unsupported causal claim withholds, non-Claim and missing claim reject. Root CLI still lazily imports only one researchguard module. Logic tests 145 passed (Tk available), collection 342; prompt, exports, fixed LW43 native 10 passed no skip, map/release passed.

- `python -m pytest tests/logic` — exit 0, 33.768s; `145 passed in 33.36s`
- `python <external>/probe_rg50.py` — exit 0, 1.351s; `root import RG module lines 1 ['import time:       879 |       4751 | researchguard.cli']`
- `python scripts/check_prompt_bundles.py` — exit 0, 0.064s; `pass`
- `python <external>/check_exports.py` — exit 0, 0.511s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-50-lw43-junit.xml --basetemp <external>/RG-50-lw43-temp` — exit 0, 0.801s; `============================== 10 passed in 0.36s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-50-lw43-junit.xml` — exit 0, 0.088s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 3.459s; `342 tests collected in 2.72s`
- `python -m flowguard map confirm logicguard suite-orchestration` — exit 0, 0.343s; `confirmed 2 component(s)`
- `python -m flowguard map check` — exit 0, 0.245s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 2.262s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`

## RG-51 — completed

Default Trace evaluation solves once without storyline depth; trace depth, storyline-depth simulation and iteration retain explicit native depth. Fifteen depth tests opt in; final focused run 93 passed after correcting an external script fence-selection error that initially appended prose to the new test (original collection failure retained). Actual CLI evaluate output is 15897 saved/12907 printed bytes with depth null; explicit depth PASS and validate NOT_RUN. Two example timings saved as observations only (cold-start order not a speed guarantee). Collection 343; exports, fixed LW43 native 10 passed no skip, map/release passed.

- `python -m pytest tests/trace` — exit 2, 1.313s; `1 error in 0.88s`
- `python -m pytest tests/trace` — exit 0, 42.072s; `93 passed in 41.63s`
- `python <external>/probe_rg51.py` — exit 0, 4.802s; `native depth, task iteration and report owners unchanged`
- `python <external>/check_exports.py` — exit 0, 0.507s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-51-lw43-junit.xml --basetemp <external>/RG-51-lw43-temp` — exit 0, 0.64s; `============================== 10 passed in 0.31s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-51-lw43-junit.xml` — exit 0, 0.063s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 2.28s; `343 tests collected in 1.81s`
- `python -m flowguard map confirm traceguard suite-orchestration` — exit 0, 0.272s; `confirmed 2 component(s)`
- `python -m flowguard map check` — exit 0, 0.328s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 2.08s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`

## RG-52 — completed

Evidence provenance gains an optional locator and native format/origin validation. validate --library-root resolves real source and source-model node IDs; absent provenance/anchor warns, an explicit wrong binding fails. Source-node inventory is read-only and creates no directory. 147 Logic tests passed including real temporary-library bound/unknown-source/wrong-node/unanchored variants; all six current YAML examples validate with visible warnings, missing library rejects. Collection 345; fixed LW43 native 10 passed no skips; exports/map/release passed.

- `python -m pytest tests/logic` — exit 0, 25.2s; `147 passed in 24.63s`
- `python <external>/probe_rg52.py` — exit 0, 2.339s; `existing boundary rejects Evidence node 'E' requires at least one non-ai_generated evidentiary provenance record`
- `python <external>/check_exports.py` — exit 0, 0.428s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-52-lw43-junit.xml --basetemp <external>/RG-52-lw43-temp` — exit 0, 0.544s; `============================== 10 passed in 0.28s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-52-lw43-junit.xml` — exit 0, 0.075s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 2.616s; `345 tests collected in 2.02s`
- `python -m flowguard map confirm logicguard suite-orchestration` — exit 0, 0.406s; `confirmed 2 component(s)`
- `python -m flowguard map check` — exit 0, 0.41s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 2.017s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`

## RG-53 — completed

Prediction freezes now reject unknown coverage IDs in each native model namespace, and Trace freezes reject unknown expected evidence/event IDs. Runtime coverage and candidate deletion checks remain unchanged. 27 loop tests passed; real CLI valid Logic coverage succeeds while wrong Logic/Source/Trace coverage and Trace expected evidence/event typos reject with specific messages. Collection 345; fixed LW43 actual native bridge 10 passed no skips; exports/map/release passed.

- `python -m pytest tests/logic/test_task_iteration.py tests/source/test_task_iteration.py tests/trace/test_task_iteration.py` — exit 0, 3.362s; `27 passed in 2.99s`
- `python <external>/probe_rg53.py` — exit 0, 1.696s; `trace 2 {"ok": false, "error": "expected evidence or event ids are missing from the model: event_typo"}`
- `python <external>/check_exports.py` — exit 0, 0.557s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-53-lw43-junit.xml --basetemp <external>/RG-53-lw43-temp` — exit 0, 0.714s; `============================== 10 passed in 0.29s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-53-lw43-junit.xml` — exit 0, 0.07s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 2.123s; `345 tests collected in 1.75s`
- `python -m flowguard map confirm logicguard sourceguard traceguard` — exit 0, 0.44s; `confirmed 3 component(s)`
- `python -m flowguard map check` — exit 0, 0.285s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 1.893s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`

## RG-54 — completed

Consolidated one researchguard skill and four routes, moving 29 domain files with their complete bodies verified against the predecessor apart from declared path/route edits. Installer removes retired members (symlink removal leaves its external target intact), copies one skill and detects main/nested byte drift even at identical size+mtime; cf077 byte-exact/common_funny comparison AST and existing same-stat/type-mismatch negative retained rather than the shallow reference block. Five prompt bytes exactly 2150/5603/5260/5029/3999; 31 skill files. 18 focused tests and complete checkpoint 344 passed; collection 344; fixed LW43 native bridge actual ready/PASSED 10 passed zero skips; active residue, exports/map/release passed. STOP at the authorized RG54 cross-repo boundary pending FG98/new-FG grant; no RG55 source edit yet.

- `python -c import pathlib,subprocess;r=pathlib.Path("<external-root>/results/ResearchGuard");p=subprocess.run(["rg","-n","-g","*.md","-g","*.py","-g","*.yaml","-g","*.json",r"\$(logicguard|sourceguard|traceguard|experimentguard)\b|skills/(logicguard|sourceguard|traceguard|experimentguard)","<LW43-snapshot>"],capture_output=True,text=True);(r/"RG-54-consumer-skill-raw.log").write_text(p.stdout);active=[x for x in p.stdout.splitlines() if not any(part in x for part in ["/CHANGELOG.md:","/openspec/","/docs/history/","/SLIM_LOG.md:"])];(r/"RG-54-consumer-skill-active.log").write_text("\n".join(active));print("raw hits",len(p.stdout.splitlines()),"active skill-loading hits",len(active));print("\n".join(active));assert p.returncode in [0,1]` — exit 0, 0.07s; `raw hits 0 active skill-loading hits 0`
- `python scripts/check_prompt_bundles.py` — exit 0, 0.142s; `pass`
- `python scripts/check_prompt_bundles.py --json` — exit 0, 0.076s; `}`
- `python -m pytest tests/test_skill_suite.py tests/test_prompt_bundles.py tests/test_install_skill.py tests/test_root_cli.py tests/contract` — exit 0, 3.033s; `18 passed in 2.52s`
- `python <external>/probe_rg54.py` — exit 0, 1.198s; `active old-skill residue absent; truthful root SLIM_LOG history excluded by root journal rule: 2 hits; raw/journal/active logs retained`
- `python <external>/check_exports.py` — exit 0, 0.974s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-54-lw43-junit.xml --basetemp <external>/RG-54-lw43-temp` — exit 0, 1.042s; `============================== 10 passed in 0.53s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-54-lw43-junit.xml` — exit 0, 0.148s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 3.577s; `344 tests collected in 2.91s`
- `python -m flowguard map confirm author-tools` — exit 0, 0.169s; `confirmed 1 component(s)`
- `python -m flowguard map check` — exit 0, 0.293s; `check: 0 error(s), 4 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 2.892s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`
- `python -m pytest` — exit 0, 71.114s; `344 passed in 70.49s (0:01:10)`

## RG-55 — completed

Replaced retired suite model behavior with one skill/four routes, native console/installer replay and current skill/member facts; content-anchor model now checks the native finding identity. Three actual mutants fail and exact original product bytes restore before positive replay. 38 focused tests, collection344, LW43 actual native10 passed no skip; oldFG0.70.6 and privately installed exact FG98/0.70.7 both pass two models and release. Old non-Python-anchor warning and new unmatched-route-invariant bad-variant warning are recorded as non-gating; no new-FG check skipped.

- `python <external>/setup_newfg.py` — exit 0, 11.952s; `private new FlowGuard installed from exact committed archive bc8c519be928cfc18292a7c66b47ece27b10d31a snapshot <workspace>/consumer-snapshots/FlowGuard-FG98-bc8c519be928 python <workspace>/venvs/researchguard-newfg/bin/python`
- `python -m flowguard map models` — exit 0, 1.976s; `models: 2 passed, 0 failed`
- `python-newfg -c import flowguard,researchguard,importlib.metadata as m;print("FlowGuard",flowguard.__version__,flowguard.__file__,m.version("flowguard"));print("ResearchGuard",researchguard.__version__,researchguard.__file__);assert flowguard.__version__==m.version("flowguard")=="0.70.7"` — exit 0, 0.097s; `ResearchGuard 0.5.9 <workspace>/repos/ResearchGuard/src/researchguard/__init__.py`
- `python <external>/probe_rg55.py` — exit 0, 10.366s; `3 actual native/code-fact mutants rejected; exact predecessor bytes restored, no live product mutation remains`
- `python -m pytest tests/contract/test_privacy_scan.py tests/source/test_semantic_gap_depth.py tests/test_install_skill.py tests/test_prompt_bundles.py tests/test_root_cli.py tests/test_skill_suite.py` — exit 0, 3.071s; `38 passed in 2.68s`
- `python <external>/check_exports.py` — exit 0, 0.727s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-55-lw43-junit.xml --basetemp <external>/RG-55-lw43-temp` — exit 0, 0.721s; `============================== 10 passed in 0.34s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-55-lw43-junit.xml` — exit 0, 0.213s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 2.458s; `344 tests collected in 1.99s`
- `python -m flowguard map check` — exit 0, 0.477s; `check: 0 error(s), 3 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 4.423s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`
- `python-newfg -m flowguard map models` — exit 0, 4.078s; `models: 2 passed, 0 failed`
- `python-newfg -m flowguard release` — exit 0, 8.76s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`

## RG-56 — completed

OpenSpec1.14.1 installed only in an external private prefix, then performed actual skip-specs archives: 2 retired changes removed, 2 completed and 3 abandoned archived, and 3 current specs rewritten. Official CLI list has no active changes; strict specs validation 3 passed. All 23 protected original archive/config/OpenSpec-skill files byte-identical. Collection344, fixed LW43 native10 passed zero skips, exports/map/release passed; no global install.

- `npm install --prefix <external>/openspec-runtime --cache <external>/npm-cache --no-audit --no-fund @fission-ai/openspec@1.14.1` — exit 0, 7.965s; `npm notice`
- `python <external>/edit_rg56.py` — exit 0, 1.342s; `2 retired changes deleted;2 complete+3 abandoned archived;3 native specs rewritten; original archive/config/6 OpenSpec skills byte-preserved 23`
- `<external>/openspec-runtime/node_modules/.bin/openspec list` — exit 0, 0.413s; `No active changes found.`
- `<external>/openspec-runtime/node_modules/.bin/openspec validate --specs --strict` — exit 0, 0.422s; `Totals: 3 passed, 0 failed (3 items)`
- `python -c import hashlib,json,pathlib,subprocess;r=pathlib.Path("<external-root>/results/ResearchGuard");b=json.loads((r/"RG-56-protected-before.json").read_text());assert all(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==v for p,v in b.items());assert len(list(pathlib.Path(".codex/skills").glob("openspec-*")))==6;p=subprocess.run(["rg","-n","-i","--glob","!archive/**","skillguard","openspec"],capture_output=True,text=True);active=[x for x in p.stdout.splitlines() if not x.startswith("openspec/changes/archive/")];print("preserved files",len(b),"archived dirs",len(list(pathlib.Path("openspec/changes/archive").iterdir())),"active retired hits",active);assert not active` — exit 0, 0.077s; `preserved files 23 archived dirs 8 active retired hits []`
- `python <external>/check_exports.py` — exit 0, 0.494s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-56-lw43-junit.xml --basetemp <external>/RG-56-lw43-temp` — exit 0, 0.716s; `============================== 10 passed in 0.41s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-56-lw43-junit.xml` — exit 0, 0.049s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 2.085s; `344 tests collected in 1.65s`
- `python -m flowguard map check` — exit 0, 4.214s; `check: 0 error(s), 3 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 2.791s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`

## RG-57 — completed

User override applied: release version is0.5.10, with native package/pyproject/CLI and both private-env distribution metadata equal. CHANGELOG lists RG01–57; FlowGuard minimum v0.70.6 and historical TraceGuard0.6.0 documentation retained. Raw/active/journal version scans verify only two active version authorities. Full checkpoint344 passed; two oldFG models and both old/newFG release passed; fixed LW43 native bridge10 passed zero skips, collection344, exports/map passed.

- `uv pip install --python python --no-deps -e .` — exit 0, 3.055s; ` + researchguard==0.5.10 (from file://<workspace>/repos/ResearchGuard)`
- `uv pip install --python python-newfg --no-deps -e .` — exit 0, 1.577s; ` + researchguard==0.5.10 (from file://<workspace>/repos/ResearchGuard)`
- `python -c import importlib.metadata as m,subprocess,researchguard,pathlib;assert researchguard.__version__==m.version("researchguard")=="0.5.10";assert subprocess.check_output(["researchguard","--version"],text=True).strip()=="researchguard 0.5.10";print(researchguard.__version__,m.version("researchguard"));p=pathlib.Path("CHANGELOG.md");assert p.read_text().splitlines()[2].startswith("## v0.5.10 - ");print("\n".join(p.read_text().splitlines()[:7]));assert "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git@v0.70.6" in pathlib.Path("pyproject.toml").read_text()` — exit 0, 0.15s; `- One `researchguard` skill with a route table (logic, source, trace, experiment) replaces the five skill entries;`
- `python <external>/check_exports.py` — exit 0, 1.259s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-57-lw43-junit.xml --basetemp <external>/RG-57-lw43-temp` — exit 0, 1.031s; `============================== 10 passed in 0.53s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-57-lw43-junit.xml` — exit 0, 0.062s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 4.507s; `344 tests collected in 3.46s`
- `python -m flowguard map confirm researchguard-suite` — exit 0, 0.175s; `confirmed 1 component(s)`
- `python -m flowguard map check` — exit 0, 0.294s; `check: 0 error(s), 3 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 3.496s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`
- `python <external>/probe_versions.py RG-57` — exit 0, 0.106s; `user0.5.10 authority only; retained historical TraceGuard0.6.0; journal exclusion limited to root SLIM_LOG`
- `python-newfg -m flowguard release` — exit 0, 12.597s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`
- `python -m flowguard read --component researchguard-suite` — exit 0, 7.911s; `  used by: logicguard, suite-orchestration`
- `python -m pytest` — exit 0, 88.277s; `344 passed in 87.69s (0:01:27)`
- `python -m flowguard map models` — exit 0, 3.554s; `models: 2 passed, 0 failed`

## RG-58 — completed

Recorded the maintainer-selected three-part version and patch-only increment policy, preserving the first sentence and all earlier maintenance paragraphs. Explicit user policy supersedes the handoff behavior-to-minor rule; version remains0.5.10. FlowGuard change selects0 of49 tests for AGENTS.md; collection344, fixed LW43 native10 passed zero skips, exports/map/release passed.

- `python -c import pathlib,subprocess;p=pathlib.Path("AGENTS.md");old=subprocess.check_output(["git","show","HEAD:AGENTS.md"],text=True);new=p.read_text();assert new.split("Every completed action")[0]==old.split("Every completed action")[0];assert "Every completed action is committed and pushed to main." in new;assert "increment only the patch version." in new and "minor version" not in new;print("\n".join(new.splitlines()[-3:]));assert new.count("Use the FlowGuard living map in")==1` — exit 0, 0.057s; `the maintainer explicitly changes the policy, increment only the patch version.`
- `python -m flowguard change` — exit 0, 0.367s; `tests to run (0 of 49): -`
- `python <external>/check_exports.py` — exit 0, 0.845s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-58-lw43-junit.xml --basetemp <external>/RG-58-lw43-temp` — exit 0, 1.699s; `============================== 10 passed in 0.90s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-58-lw43-junit.xml` — exit 0, 0.247s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 4.669s; `344 tests collected in 3.85s`
- `python -m flowguard map check` — exit 0, 0.4s; `check: 0 error(s), 3 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 4.023s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`

## RG-59 — completed

Real CLI stop-decision now starts from paper citation search and from an actual add-observation grown starter model. Continued search, budget blocking and sufficient stopping all verified. Source65 passed; stop5 passed; collection344; fixed LW43 native10 actually passed zero skips; exports/map/release and portable prompt checks passed. Installed command documentation describes native inputs and states without unavailable example paths.

- `python -m pytest tests/source/test_stop_decision.py` — exit 0, 1.568s; `5 passed in 1.09s`
- `python -m pytest tests/source` — exit 0, 7.289s; `65 passed in 6.94s`
- `python <external>/probe_rg59.py` — exit 0, 1.563s; `real native growing-model stop confirmed, no observation-as-model surrogate`
- `python -m flowguard change` — exit 0, 0.348s; `run: python -m pytest -q tests/source/test_stop_decision.py`
- `python scripts/check_prompt_bundles.py` — exit 0, 0.05s; `pass`
- `python <external>/check_exports.py` — exit 0, 5.85s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-59-lw43-junit.xml --basetemp <external>/RG-59-lw43-temp` — exit 0, 4.459s; `============================== 10 passed in 2.08s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-59-lw43-junit.xml` — exit 0, 0.1s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 2.203s; `344 tests collected in 1.69s`
- `python -m flowguard map check` — exit 0, 0.397s; `check: 0 error(s), 3 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 4.062s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`

## RG-60 — completed

Completed CHANGELOG RG58–60 checkpoint under user target0.5.10 and maintainer patch-only version policy. Full344 passed; collection344; fixed LW43 native10 actual passed zero skips; exports and old/new real FG map0errors3warnings/models2passed/release PASS. No optional newFG skip, no tag or publication.

- `python <external>/edit_rg60.py` — exit 0, 0.087s; `changelog RG58..60; maintainer patch-only override retained`
- `python -c from pathlib import Path;import researchguard; s=Path("CHANGELOG.md").read_text(); assert s.splitlines()[2].startswith("## v0.5.10 - "); assert s.splitlines()[4].endswith("RG-57, RG-58, RG-59, RG-60."); assert researchguard.__version__=="0.5.10"; assert "patch-only version policy" in s; print("version0.5.10; all60 Done; maintainer patch-only policy")` — exit 0, 0.047s; `version0.5.10; all60 Done; maintainer patch-only policy`
- `python -m flowguard change` — exit 0, 0.633s; `tests to run (0 of 49): -`
- `python <external>/check_exports.py` — exit 0, 0.86s; `exports ok`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-60-lw43-junit.xml --basetemp <external>/RG-60-lw43-temp` — exit 0, 1.298s; `============================== 10 passed in 0.69s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-60-lw43-junit.xml` — exit 0, 0.098s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python -m pytest --collect-only` — exit 0, 2.896s; `344 tests collected in 2.34s`
- `python -m flowguard map check` — exit 0, 0.334s; `check: 0 error(s), 3 warning(s), 0 info`
- `python -m flowguard release` — exit 0, 2.974s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`
- `python -m pytest` — exit 0, 80.272s; `344 passed in 79.79s (0:01:19)`
- `python -m flowguard map models` — exit 0, 1.92s; `models: 2 passed, 0 failed`
- `python-newfg -m flowguard map check` — exit 0, 16.901s; `check: 0 error(s), 3 warning(s), 0 info`
- `python-newfg -m flowguard map models` — exit 0, 2.601s; `models: 2 passed, 0 failed`
- `python-newfg -m flowguard release` — exit 0, 3.058s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`

## Final section5 verification

All 61 ordered actions were handled; no action was skipped. The final RG61 product tree passed 344 tests and collected 344. The single full RG61 run also serves section5 on the same source. Fixed read-only LW43 compatibility executed 10 tests, zero skips, including the real native provider-to-reader ready bridge; original consumer hashes and source origins were verified. Old private FlowGuard0.70.6 and actually installed private FlowGuard0.70.7 both passed map, two executable models and release checks. No global installation, push, merge, tag or publication was performed; source freezes for root cross-review after the final commit.

The one-skill/four-route package, deterministic prompt entry bytes, all exports, native CLI smoke and failure exit codes, retained source bytes, residual/version scans and three strict OpenSpec specs passed. Three known map warnings remain. The new FlowGuard reports a non-gating missing known-bad variant for route_matches_member; both required model variants and three actual code-fact mutations were exercised and rejected. The final residual probe initially used a case-insensitive search beyond the documented command, matching ordinary Local Material Routing headings; corrected to the exact case-sensitive command, with original failure/raw output retained externally. No product change resulted.

Measured source Python lines: 33882 (baseline 79850); test Python lines: 7925 (baseline 26555); tracked files: 318 (baseline 597); tracked bytes before this final journal: 2536614 (baseline 12835053). Final committed bytes including the journal are recorded externally. One skill contains 31 files with a 268-character description.

## RG-61 — completed

Added the real open-gap CLI sufficiency=False assertion without changing native source. Positive stop5 passed; an actual always-sufficient native mutation failed exactly the target test (1 failed,4 passed), then source bytes restored. Final same-tree full344 passed/344 collected; fixed LW43 native10 actually passed zero skips; old/new real FG map0errors3warnings/models2passed/release PASS; section5 CLI/prompt/exports/residual/version/OpenSpec checks passed. Initial overbroad external residual probe failure retained and corrected; no product change or duplicate full rerun. Version0.5.10 and patch-only user policy preserved; all61 complete, ready to freeze for root XR.

- `python <external>/edit_rg61.py` — exit 0, 0.095s; `stop-decision sufficiency checked; patch-only changelog policy retained`
- `python -m pytest tests/source/test_stop_decision.py` — exit 0, 2.231s; `5 passed in 1.19s`
- `python <external>/probe_rg61.py` — exit 0, 0.883s; `always-sufficient bad variant rejected, source bytes restored exactly`
- `python -m flowguard change` — exit 0, 7.138s; `run: python -m pytest -q tests/source/test_stop_decision.py`
- `python -m pytest` — exit 0, 87.777s; `344 passed in 86.89s (0:01:26)`
- `python -m pytest --collect-only` — exit 0, 4.868s; `344 tests collected in 3.84s`
- `python -m flowguard release` — exit 0, 4.872s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`
- `python -m flowguard map models` — exit 0, 3.174s; `models: 2 passed, 0 failed`
- `python -m flowguard map check` — exit 0, 0.582s; `check: 0 error(s), 3 warning(s), 0 info`
- `python -m flowguard change src/researchguard/source/planner.py` — exit 0, 1.011s; `ARCH WARN duplicate_code experimentguard: 4 identical bodies (58 AST nodes) in ['experimentguard', 'logicguard', 'sourceguard', 'traceguard']: src/researchguard/experiment/__init__.py:__getattr__, src/researchguard/logic/__init__.py:__getattr__, src/researchguard/source/__init__.py:__getattr__, src/researchguard/trace/__init__.py:__getattr__`
- `python scripts/check_prompt_bundles.py` — exit 0, 0.068s; `pass`
- `python scripts/check_prompt_bundles.py --json` — exit 0, 0.099s; `}`
- `python <external>/check_exports.py` — exit 0, 0.518s; `exports ok`
- `python <external>/probe_consumer_origin.py` — exit 0, 0.121s; `}`
- `python -m pytest -p no:cacheprovider tests/contract/test_researchguard_handoff.py --junitxml <external>/RG-61-section5-lw43.xml --basetemp <external>/RG-61-section5-lw43-temp` — exit 0, 1.359s; `============================== 10 passed in 0.76s ==============================`
- `python <external>/verify_lw_junit.py <external>/RG-61-section5-lw43.xml` — exit 0, 0.071s; `10 actual PASSED, 0 skipped; real native provider-to-reader bridge PASSED/ready, not version-skipped`
- `python <external>/final_smoke.py` — exit 0, 15.639s; `all section5 native CLI smoke assertions passed; exact expected failure exits preserved`
- `python <external>/final_residual_measure.py` — exit 1, 0.202s; `AssertionError: ['skills/researchguard/references/routes/experiment.md:13:## Local Material Routing', 'skills/researchguard/references/routes/trace.md:18:## Local Material Routing', 'skills/researchguard/references/routes/source.md:13:## Local Material Routing', 'skills/researchguard/references/routes/logic.md:24:## Local Material Routing', 'src/researchguard/trace/inference/engine.py:530:    # public console for routing, schema checks, or ``--help`` remains bounded.', 'src/researchguard/logic/gap_ledger.py:1:"""Gap-ledger routing for LogicGuard diagnostics and simulations."""']`
- `python <external>/final_residual_measure.py` — exit 0, 0.167s; `all61 changelog and maintainer patch-only policy verified`
- `python <external>/probe_versions.py final-section5` — exit 0, 0.089s; `user0.5.10 authority only; retained historical TraceGuard0.6.0; journal exclusion limited to root SLIM_LOG`
- `<external>/openspec-runtime/node_modules/.bin/openspec list` — exit 0, 0.375s; `No active changes found.`
- `<external>/openspec-runtime/node_modules/.bin/openspec validate --specs --strict` — exit 0, 0.394s; `Totals: 3 passed, 0 failed (3 items)`
- `python-newfg -m flowguard map check` — exit 0, 4.226s; `check: 0 error(s), 3 warning(s), 0 info`
- `python-newfg -m flowguard map models` — exit 0, 2.2s; `models: 2 passed, 0 failed`
- `python-newfg -m flowguard release` — exit 0, 2.394s; `verify: PASS (map, lint and models only; tests not run; run python -m pytest -q separately)`
- `git diff --check` — exit 0, 0.005s; `(no output)`
