# ResearchGuard

ResearchGuard is one versioned research-quality guard suite with one agent
skill, `researchguard`, and four routes:

- `logic` (LogicGuard) audits argument structure and claim support.
- `source` (SourceGuard) plans evidence and source discovery.
- `trace` (TraceGuard) reconstructs and stress-tests evidence-backed timelines
  and qualitative causal storylines.
- `experiment` (ExperimentGuard) recommends finite experiment sets that distinguish
  caller-declared hypotheses, minimizing declared cost or experiment count.

All four routes use one `researchguard` Python distribution, one suite version
and one console: `researchguard logic|source|trace|experiment ...`. A selected
route's failure is terminal. ResearchGuard does not retry through another
route, silently downgrade, or load legacy package formats.

The first release was `v0.1.0`.

## Install

```bash
python -m pip install -e .
python scripts/install_skill.py --target "$CODEX_HOME/skills"   # or ~/.claude/skills
python scripts/install_skill.py --target "$CODEX_HOME/skills" --check
```

The first line installs the `researchguard` console; the second copies the
`researchguard` skill folder into the agent's skills directory and removes the
`logicguard`, `sourceguard`, `traceguard` and `experimentguard` folders that
older versions installed.

## Starting a model

Build only the routes and hypotheses the question needs. JSON status reports include raw input file digests and source-owned evidence locators, summaries and boundaries; compare the digests before reusing a saved report. `source add-anchor` adds source-owned anchors by command and writes compact YAML without defaults. Search readback names the gap and query, with declared searches first on equal scores. The source and trace field indexes load one step at a time.


For a research question, start from its folder: `researchguard status <folder>` reads the verdict,
open gaps and next actions (`--hypothesis <id>` for one hypothesis). A new question starts with
`research.yaml` (template in `skills/researchguard/references/research-tree.md`, "Start a question").

`researchguard source create --output source.yaml` and `researchguard trace create --output trace.yaml`
write complete synthetic teaching examples that validate directly. Source validation warns while
`example-` rows remain; replace them with retrieved material before using the model for a real claim.
Source gaps default to `discovered` only when `semantic_state` is omitted; retired `status` remains invalid.
The source and trace field sheets list current fields, defaults, allowed values and observation formats.
Logic Evidence provenance may use an exact-text `quote` to calculate its content hash; a supplied hash
must match, and validation errors name the affected node.

## Codex-facing source intake contract

The CLI preservation step is not enough by itself. When concrete source
material is provided, Codex preserves it, reads it, writes a content-level model,
and verifies the model with `view-graph` or `view-snapshot`. If reading
or modeling is blocked, the source is reported as preserved with modeling
incomplete; generated prose is never promoted to evidence.

## Skill layout

- `skills/researchguard/SKILL.md` is a route table; the agent loads only the
  chosen `references/routes/<route>.md`.
- LogicGuard's source library, structured-artifact audit, model deepening,
  artifact synthesis and project library viewer are sub-routes of the `logic`
  route; TraceGuard's case library is a sub-route of the `trace` route.

`researchguard source stop-decision` checks every executable search addressing an
open gap. An affordable critical search continues; a critical gap without one
stays blocked. Without blocking gaps, `--sufficient` stops even when optional
followups remain; those followups stay visible. Only cost is compared with budget.
`trace report` in Markdown or text shows dated events, ranked hypotheses and native
depth blockers; `trace gaps` includes those unresolved depth gaps. `trace compare`
also reports hypothesis and source/evidence/event/link inventory changes. Source reports
show source roles and lineage, anchor locators and each closed gap's declared closure basis.

Ordinary logic arguments use an internal unit/card inventory when no inventory or role
declarations are present. Explicit declarations, including empty ones, keep their checks.
Depth exposes `coverage_universe.implicit_inventory` and informational shared Evidence IDs;
real role, scope, competition and perturbation gaps still block closure.
See `examples/logic/plain_research_argument.yaml` for a complete synthetic example.

TraceGuard can expose a deletion-minimal contradiction core;
`researchguard logic minimal-sets` exposes deletion-minimal support and attack
sets with a conservative wording license. Candidates are split by the edge
entering the claim; when support is unavailable, the result names the native
blockers and their types instead of claiming an empty minimal attack core. ExperimentGuard is
recommendation-only: it never executes an experiment or invents probabilities.

Experiment specs may declare non-negative finite `cost_by_experiment` values.
With costs, select by total cost, then count and IDs (at most 16 candidates);
without them, keep count first. Unlisted costs default to 1. Alternatives omit
the selected set, and valid prior counterevidence keeps a hypothesis eliminated
even when a later observation misses the prediction matrix. Retired port fields
are ignored in old JSON inputs and omitted from current output.

TraceGuard solves storyline support from evidence first, then bounds causal
support beneath it. Declaring a causal candidate cannot improve a storyline's
support; unresolved or partly addressed confounders provide no positive support.
`trace depth` always checks applicable causal-declaration and opposing-evidence
removals for self-boosting support, and blocks closure if either check fails.
Its live alternatives exclude the leading hypothesis.
Competition remains comparison context, without turning opposition to one
hypothesis into extra absolute support for another.

Each route's task-local loop (predict, observe, revise) works on plain model
files and keeps purpose, coverage, assumptions, unknowns, predictions, computed
gap transitions, addressable next actions, and exact stop reasons. Trace predictions
require an existing hypothesis or trace and coverage, but may expect evidence or events not yet
in the baseline. An observation can append native source/evidence/event/link rows;
comparison computes the checked hypothesis's support and its declared expected direction. Native
depth gaps remain separate from prediction mismatches. A candidate must preserve
those new rows; accepting a revision with remaining depth gaps continues iteration.
A holdout claim or observation is optional; when given, it must be independent of the evidence
used to build the model. The loop never writes the model file, so rolling back
means restoring the previous file. SourceGuard preserves provider and
finite-action stop boundaries.
The routes share one current/candidate lifecycle kernel. Frozen predictions use v3
with `baseline_identity`; older predictions require `stale_prediction: re-freeze`.
A changed baseline must be frozen again.

The source, logic and trace loops compute gap transitions from the actual
baseline and candidate models through one shared set operation. Only resolved
gaps mean `progressed`; newly discovered gaps stay visible without claiming a
quality gain. `--prior-open-gap-id` controls stagnation, not the baseline.
Trace prediction mismatches remain rejection reasons, separate from native gap
transitions.

Trace-to-logic handoffs preserve each hypothesis id, signed evidence links,
evidence text and source provenance. Opposing evidence supports a rebuttal,
limiting evidence supports a limitation, and neither becomes direct support for
the the claim being checked. Import preserves the primary hypothesis as root without
inventing a warrant or relationships between hypotheses. Old trace-only bundles
and the result-only export API remain supported.

`source depth` includes observations already recorded in the model. A supplied
observation previews an additional cloned update; without any observations it
remains planning-only. Recorded depth never implies a provider ran in this call.

Source plans keep executable declared actions without generating duplicates for
the same gap. Generated gap queries use its description and at most two domain
hints, capped at 120 characters. `score-actions` and `plan --all-scores` share
the complete native candidate/scoring path; scoring weights are unchanged.

`source compare` compares versions of the same model using native semantic gap
state and qualification decisions, without restoring the retired gap status.
A self-comparison reports no changes.

## 一个研究文件夹

第一条命令是 `researchguard status <folder>`：查看结论、假设、证据、未关缺口和下一步；
`--hypothesis <id>` 只看一个假设，`--json` 输出数据，`--output <path>` 保存结果。
新问题先写 `research.yaml` 索引（模板在 "Start a question"），把各路线的原生模型放在同一文件夹，
共用假设、来源和锚点 id。格式见
[research-tree.md](skills/researchguard/references/research-tree.md)。


The optional desktop viewer requires the `viewer` extra
(`python -m pip install -e ".[viewer]"`) and Python with tkinter.
Core argument, source, trace and experiment commands do not require Pillow.
