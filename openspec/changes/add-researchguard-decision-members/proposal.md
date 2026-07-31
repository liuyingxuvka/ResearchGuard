## Why

ResearchGuard currently coordinates source discovery, trace reconstruction, and logical support, but each member stops before a distinct decision boundary: SourceGuard lacks a typed stop decision, TraceGuard lacks a deletion-minimal contradiction core, and LogicGuard lacks minimal support sets plus an explicit wording license. A separate experiment-design decision is also absent and should be admitted only if it remains independent of the existing three members and neighboring Guard families.

## What Changes

- Add SourceGuard stop decisions with visible `continue`, `stop_satisfied`, `blocked`, `exhausted`, and `downgrade` terminals.
- Add TraceGuard bounded deletion-minimal contradiction cores without turning it into a general constraint solver or temporal-network engine.
- Add LogicGuard minimal support/attack sets and an explicit wording license that prevents unsupported final prose.
- Admit ExperimentGuard as the fourth native ResearchGuard member only for observation/intervention recommendation across declared hypotheses, outcomes, cost, and risk; it never executes experiments.
- Extend the ResearchGuard router, CLI, installer, suite model, checks, tests, and clean consumer projection from exactly three to exactly four members.
- Remove retired field names directly; add no compatibility reader, alias, or fallback.

## Capabilities

### New Capabilities

- `source-search-stop-decision`: Defines typed search continuation and terminal decisions.
- `trace-minimal-contradiction-core`: Defines bounded deletion-minimal contradiction explanations.
- `logic-minimal-sets-wording-license`: Defines minimal support/attack sets and final-wording authorization.
- `experimentguard-observation-design`: Defines non-executing next-observation and intervention recommendations.
- `researchguard-four-member-suite`: Defines the exact four-member inventory, routing, installation, and validation contract.

## Impact

Affected surfaces: member prompts and references, `src/researchguard` runtimes, CLI/router/report schemas, FlowGuard suite model, SkillGuard contract sources, tests, installer/currentness, README, package version, and release metadata.
