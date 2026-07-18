## Why

LogicGuard, SourceGuard, and TraceGuard currently ship as separate repositories,
Python distributions, CLIs, versions, installations, and SkillGuard maintenance
units even though research and writing workflows must coordinate them as one
family. This permits version drift, duplicate routing surfaces, and retired
compatibility paths to remain executable.

ResearchGuard v0.1.0 establishes one current authority: a single public
distribution and atomic skill suite with four precise Codex entrypoints. Each
member remains independently callable because it owns a complete semantic
workflow, while ambiguous or cross-Guard work has one explicit orchestrator.

## What Changes

- Create the `researchguard` Python distribution at version `0.1.0`.
- Create one `researchguard` CLI with `run`, `logic`, `source`, and `trace`
  commands.
- Ship four first-class Codex skills in one atomic suite:
  `$researchguard`, `$logicguard`, `$sourceguard`, and `$traceguard`.
- Preserve LogicGuard, SourceGuard, and TraceGuard as distinct native semantic
  owners with their existing mathematical and claim boundaries.
- Fold the five LogicGuard satellite Skill IDs and `traceguard-library` into
  internal routes of their owning member.
- Bind every installed member and native receipt to the same suite version and
  content fingerprint.
- Require direct invocation and umbrella dispatch for the same intent to reach
  the same native owner and primary path.
- Make a selected member failure terminal. Cross-Guard continuation requires an
  explicit typed handoff owned by `$researchguard` or an outer workflow.
- **BREAKING** Remove the `logicguard`, `sourceguard`, and `traceguard` Python
  distributions and console scripts from normal runtime.
- **BREAKING** Remove old Skill IDs, forwarding stubs, import aliases, route
  fallbacks, locale fallbacks, legacy status readers/projections, dual output
  fields, and compatibility wrappers from normal runtime.
- Migrate Logic Writing and other active consumers directly to
  `researchguard.logic`, `researchguard.source`, or `researchguard.trace` while
  preserving native owner identities.
- Keep the old public repositories unchanged until v0.1.0 is released and all
  active consumers pass; only then make them private.

## Capabilities

### New Capabilities

- `researchguard-suite`: Atomic versioning, installation, discovery,
  fingerprinting, validation, and release for the four-member suite.
- `researchguard-routing`: Exact umbrella routing, direct-member parity, typed
  cross-Guard handoffs, terminal failure behavior, and recursion prevention.
- `researchguard-logic`: LogicGuard argument, source-library,
  structured-artifact, deepening, synthesis, and viewer routes under the one
  current runtime.
- `researchguard-source`: SourceGuard evidence-discovery planning, observation,
  depth, handoff, and closure under the one current runtime.
- `researchguard-trace`: TraceGuard canonical inference, storyline depth,
  perturbation, case-library, handoff, and closure under the one current
  runtime.
- `researchguard-migration`: Direct-to-current migration, residual-zero
  enforcement, consumer migration, and old-repository retirement gates.

### Modified Capabilities

None. This is a new repository and version line.

## Impact

- New public repository: ResearchGuard.
- New package and CLI: `researchguard`.
- New skill suite: `researchguard`, `logicguard`, `sourceguard`, `traceguard`.
- Source migrations from the current LogicGuard, SourceGuard, and TraceGuard
  repositories.
- Consumer changes in Logic Writing, global maintainer routing, installation
  projections, and any repository that imports the old packages or calls their
  old CLIs.
- GitHub release `v0.1.0`, followed by privacy changes for the three retired
  repositories only after remote and consumer closure.
