# ResearchGuard

**Current version:** `v0.1.0`  
**当前版本：** `v0.1.0`

ResearchGuard is one versioned research-quality guard suite with four direct
Codex entrypoints:

- `researchguard` routes cross-Guard or ambiguous research work.
- `logicguard` audits argument structure and claim support.
- `sourceguard` plans evidence and source discovery.
- `traceguard` reconstructs and stress-tests evidence-backed timelines and
  qualitative causal storylines.

All four entrypoints use one `researchguard` Python distribution, one suite
version, and one suite fingerprint. A selected member failure is terminal.
ResearchGuard does not retry through another member, silently downgrade, or
load legacy package formats.

The first release is `v0.1.0`.

## Codex-facing source intake contract

The CLI preservation step is not enough by itself. When concrete source
material is provided, Codex preserves it, reads it, writes a content-level model,
and verifies the model with `view-graph` or `view-snapshot`. If reading
or modeling is blocked, the source is reported as preserved with modeling
incomplete; generated prose is never promoted to evidence.

## Public Skill topology

- `$researchguard` is the family router.
- `$logicguard`, `$sourceguard`, and `$traceguard` remain complete direct
  entrypoints.
- LogicGuard's source library, structured-artifact audit, model deepening,
  artifact synthesis, and project library viewer are internal routes.
- TraceGuard's case library is an internal route.

All direct entries bind to the same native member owners used by the umbrella.
There are no legacy Skill IDs, command wrappers, aliases, dual readers, or
failure-triggered alternate routes.
