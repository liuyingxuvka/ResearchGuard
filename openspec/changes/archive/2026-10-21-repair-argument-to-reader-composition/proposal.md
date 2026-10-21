## Why

ResearchGuard currently selects and delivers model nodes with a bounded
top-N-style path, can truncate candidate accounting, and can mix generic tool
language with domain propositions. That leaves the writer without a reliable
argument-unit handoff and permits local support edges to masquerade as support
for the whole target. The candidate change makes the existing native synthesis
owner accept a complete, reader-declared unit request and export only a closed,
traceable argument handoff.

## What Changes

- Remove candidate-accounting truncation and filter omitted material before
  body delivery while preserving complete internal dispositions.
- Add the typed `researchguard.logic.synthesis-request.v1` contract for ordered
  argument units, claim/support bindings, dependencies, positions, and source
  anchors.
- Validate required units, acyclic predecessor order, current model identity,
  support/warrant/boundary closure, and explicit budget/support-gap terminals.
- Audit contribution across parent, sibling, and downstream units instead of
  treating local Evidence-to-Claim edges as sufficient.
- Export domain propositions and mechanism references separately from generic
  trace/solver audit context; missing domain meaning remains a visible gap.
- **BREAKING**: callers must use the typed selection request; no implicit
  top-N fallback is a successful current path.

## Capabilities

### New Capabilities

- `argument-unit-synthesis`: Produce a complete ordered argument-unit handoff
  with evidence, warrants, boundaries, dependencies, and dispositions.
- `trace-domain-export`: Preserve domain propositions and mechanisms in typed
  Trace-to-LogicGuard output while isolating generic audit context.

### Modified Capabilities

- `researchguard-member-model-loops`: Require cross-unit contribution and
  current support/boundary closure for synthesized artifacts.

## Impact

Affected files are ResearchGuard native synthesis, delivery, structure-audit,
trace export/results, their typed CLI consumers, focused logic/trace tests, and
the candidate OpenSpec artifacts. LogicWriting remains the sole reader and
writer owner; the registered source checkout, installed package, model
authority, and release state remain outside this candidate change while A00 is
blocked.
