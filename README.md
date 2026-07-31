# ResearchGuard

**Current version:** `v0.4.0`
**当前版本：** `v0.4.0`

ResearchGuard is one versioned research-quality guard suite with five direct
Codex entrypoints:

- `researchguard` routes cross-Guard or ambiguous research work.
- `logicguard` audits argument structure and claim support.
- `sourceguard` plans evidence and source discovery.
- `traceguard` reconstructs and stress-tests evidence-backed timelines and
  qualitative causal storylines.
- `experimentguard` recommends minimum finite experiment sets that distinguish
  caller-declared hypotheses.

All five entrypoints use one `researchguard` Python distribution, one suite
version, and one suite fingerprint. A selected member failure is terminal.
ResearchGuard does not retry through another member, silently downgrade, or
load legacy package formats.

The first release was `v0.1.0`.

## Codex-facing source intake contract

The CLI preservation step is not enough by itself. When concrete source
material is provided, Codex preserves it, reads it, writes a content-level model,
and verifies the model with `view-graph` or `view-snapshot`. If reading
or modeling is blocked, the source is reported as preserved with modeling
incomplete; generated prose is never promoted to evidence.

## Public Skill topology

- `$researchguard` is the family router.
- `$logicguard`, `$sourceguard`, `$traceguard`, and `$experimentguard` remain complete direct
  entrypoints.
- LogicGuard's source library, structured-artifact audit, model deepening,
  artifact synthesis, and project library viewer are internal routes.
- TraceGuard's case library is an internal route.

SourceGuard now returns typed search-stop decisions; TraceGuard can expose a
deletion-minimal contradiction core; LogicGuard can expose deletion-minimal
support and attack sets with a conservative wording license. ExperimentGuard
is recommendation-only: it never executes an experiment or invents
probabilities.

All direct entries bind to the same native member owners used by the umbrella.
There are no legacy Skill IDs, command wrappers, aliases, dual readers, or
failure-triggered alternate routes.

In v0.4.0 the umbrella no longer accepts a caller-selected `--member`. It
requires one current admission row authored by each native member over the
same request, and routes only when exactly one member is applicable and clear
of its forbidden conditions. Each member's task-local loop now binds purpose,
coverage, assumptions, unknowns, iteration lineage, predictions, native
receipts, computed gap transitions, addressable next actions, and exact stop
reasons. LogicGuard, TraceGuard, and ExperimentGuard require independent
holdout evidence for predictive closure; SourceGuard preserves provider and
finite-action stop boundaries.
