# ResearchGuard

ResearchGuard is one versioned research-quality guard suite with one agent
skill, `researchguard`, and four routes:

- `logic` (LogicGuard) audits argument structure and claim support.
- `source` (SourceGuard) plans evidence and source discovery.
- `trace` (TraceGuard) reconstructs and stress-tests evidence-backed timelines
  and qualitative causal storylines.
- `experiment` (ExperimentGuard) recommends minimum finite experiment sets that
  distinguish caller-declared hypotheses.

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

`researchguard source stop-decision` checks every executable search targeting an
open gap. An affordable critical search continues; a critical gap without one
stays blocked. Without blocking gaps, `--sufficient` stops even when optional
followups remain; those followups stay visible. Only cost is compared with budget.
TraceGuard can expose a deletion-minimal contradiction core;
`researchguard logic minimal-sets` exposes deletion-minimal support and attack
sets with a conservative wording license. Candidates are split by the edge
entering the claim; when support is unavailable, the result names the native
blockers and their types instead of claiming an empty minimal attack core. ExperimentGuard is
recommendation-only: it never executes an experiment or invents probabilities.

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
gap transitions, addressable next actions, and exact stop reasons. Every id a
prediction names must exist in the model when it is frozen. A holdout claim or
observation is optional; when given, it must be independent of the evidence
used to build the model. The loop never writes the model file, so rolling back
means restoring the previous file. SourceGuard preserves provider and
finite-action stop boundaries.

The source, logic and trace loops compute gap transitions from the actual
baseline and candidate models through one shared set operation. Only resolved
gaps mean `progressed`; newly discovered gaps stay visible without claiming a
quality gain. `--prior-open-gap-id` controls stagnation, not the baseline.
Trace prediction mismatches remain rejection reasons, separate from native gap
transitions.

Trace-to-logic handoffs preserve each hypothesis id, signed evidence links,
evidence text and source provenance. Opposing evidence supports a rebuttal,
limiting evidence supports a limitation, and neither becomes direct support for
the target claim. Import preserves the primary hypothesis as root without
inventing a warrant or relationships between hypotheses. Old trace-only bundles
and the result-only export API remain supported.

`source depth` includes observations already recorded in the model. A supplied
observation previews an additional cloned update; without any observations it
remains planning-only. Recorded depth never implies a provider ran in this call.

Source plans keep executable declared actions without generating duplicates for
the same gap. Generated gap queries use its description and at most two domain
hints, capped at 120 characters. `score-actions` and `plan --all-scores` share
the complete native candidate/scoring path; scoring weights are unchanged.
