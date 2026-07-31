## Why

LogicGuard, SourceGuard, TraceGuard, and the new ExperimentGuard already have native prediction, observation, depth, or recommendation owners. Their current workflows can still finish after one successful local result, leaving important model gaps for a later prose note rather than continuing the member's own task-local loop.

## What Changes

- **BREAKING** Make each member continue while its own native, addressable model/evidence gaps remain.
- Extend Logic, Source, and Trace iteration receipts with gap transitions, depth receipt identity, iteration, and terminal reason.
- Add real-result observation and revision iterations to ExperimentGuard while keeping it recommendation-only for execution.
- Keep ResearchGuard's exact-one-member router and explicit handoff boundaries; no automatic sibling invocation or aggregate understanding status.
- Add member-specific known-good and known-bad depth/iteration tests and update prompts.

## Capabilities

### New Capabilities
- `experimentguard-observation-iteration`: consume externally executed experiment results and revise the declared prediction matrix.

### Modified Capabilities
- `logicguard-task-iteration`: continue until important argument-depth gaps close.
- `sourceguard-search-iteration`: continue while an allowed search action can close an important gap.
- `traceguard-storyline-iteration`: continue while evidence can distinguish important storylines.
- `researchguard-routing`: preserve one-member routing and opaque member handoffs.

## Impact

- `src/researchguard/logic`, `source`, `trace`, and `experiment` schemas/engines/CLIs; member SKILL.md files; tests; generated local consumer projection.
- No central learner, cross-member receipt sharing, source execution, experiment execution, probability invention, or factual-truth claim.
