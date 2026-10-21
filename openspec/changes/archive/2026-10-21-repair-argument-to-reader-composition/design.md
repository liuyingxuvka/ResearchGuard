## Context

See `proposal.md` and the Action List. The candidate starts from ResearchGuard
0.5.0 with existing native model/depth and trace owners. A00 author admission
is blocked by current FlowGuard/SkillGuard layout and surface-inventory gaps,
so this design is deliberately isolated from the registered source and
installed projection.

## Goals / Non-Goals

**Goals:**

- Make one typed selection request the only current synthesis entry path.
- Preserve every candidate disposition and selected unit's support, warrant,
  boundary, predecessor, and downstream contribution.
- Keep trace domain propositions separate from generic solver/audit wording.
- Provide deterministic focused checks and receipts suitable for later formal
  admission.

**Non-Goals:**

- No new writer, reader route, source-search provider, or alternate model
  authority.
- No compatibility fallback, implicit top-N success path, generated-contract
  rewrite, installed-skill update, or release publication.
- No claim that structural handoff proves final prose quality.

## Decisions

1. **Typed request at the native boundary.** `selection_request` is required
   and validated before traversal. This prevents callers from bypassing unit
   dependencies with a legacy goal/profile/max-items call.
2. **Unit-level closure over node-level ranking.** The provider traverses the
   requested unit claims and their native support/warrant/boundary graph, then
   records importance as metadata while using `editorial_prominence` and
   placement supplied by the reader plan.
3. **Complete ledger, filtered delivery.** Synthesis retains all candidate
   dispositions. Delivery filters `omit` before body materialization and keeps
   appendix/internal records separate.
4. **Cross-unit structure audit.** Parent, sibling, and downstream bindings are
   required for structural contribution; an evidence edge alone is local only.
5. **Typed trace export.** Domain proposition/mechanism fields remain the
   semantic payload. Solver status, safe wording, and tool-completeness notes
   stay in `audit_context`.

## Risks / Trade-offs

- [Existing callers still use the old signature] → update every current caller
  and reject the old form visibly; do not add a fallback.
- [Real models contain cycles or alternative support paths] → use visited-set
  traversal, preserve alternative paths, and report cycle/unknown IDs.
- [Reader plan contains a material support gap] → return a typed blocked
  terminal with exact unit and gap instead of manufacturing a handoff.
- [Candidate passes focused tests but lacks governance] → label all receipts as
  candidate-only and retain the A00 blocker in the final report.

## Migration Plan

Implement and test in this candidate copy, run the affected native tests and
contract validation, and record the exact source HEAD plus candidate diff. If
governance later admits the source, regenerate contracts through the governed
SkillGuard owner and replay the same tests. Rollback is deleting the candidate
copy; the registered source and installed projection remain unchanged.
