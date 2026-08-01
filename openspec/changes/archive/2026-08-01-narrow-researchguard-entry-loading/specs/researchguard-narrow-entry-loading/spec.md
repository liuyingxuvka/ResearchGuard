## Purpose

Provide a small, evidence-bound ResearchGuard entrance that selects the minimum sufficient native member set without loading unrelated skills while retaining every selected member's deepest current closure behavior.

## ADDED Requirements

### Requirement: Admission is derived from source-bound task facts
The ResearchGuard umbrella SHALL accept only the current task-facts schema. Each fact MUST have a stable id, a typed kind, a primary-action or context role, and a non-empty source span. Callers MUST NOT set member applicability directly. Every current member SHALL derive positive, required, forbidden, first-action, and reference-loading results from its own current admission contract.

#### Scenario: Source-bound facts select one member
- **WHEN** one primary-action fact matches one member's positive and required conditions and every forbidden condition has an exact non-present disposition
- **THEN** the derived admission set admits that member and preserves the matching fact and condition identities

#### Scenario: Placeholder fact evidence is rejected
- **WHEN** a task fact lacks a non-empty quoted source span, stable source identity, valid offsets, or a current fact kind
- **THEN** admission blocks before any member executes

#### Scenario: Generic forbidden clearance is rejected
- **WHEN** a member lacks a disposition for any declared forbidden condition or supplies only one generic clearance statement
- **THEN** that member is blocked rather than treated as forbidden-clear

### Requirement: Routing selects the minimum sufficient member set
The umbrella SHALL find the smallest applicable member set whose derived coverage includes every source-bound primary responsibility. If one member can cover all responsibilities independently, the umbrella SHALL select only that member. A direct member request SHALL bypass the umbrella and reach the same native owner. Zero coverage, equal-cardinality ambiguity, stale facts, recursion, unknown conditions, and over-selection MUST remain visible blocked results with no lexical, list-order, alias, `run all`, or retry fallback.

#### Scenario: Direct request bypasses umbrella
- **WHEN** a caller invokes a clear LogicGuard, SourceGuard, TraceGuard, or ExperimentGuard command directly
- **THEN** only that member's native owner executes and no umbrella admission or sibling skill is loaded

#### Scenario: One member is independently sufficient
- **WHEN** one applicable member covers every primary responsibility
- **THEN** admission selects only that member and rejects any caller-supplied larger member set as over-selection

#### Scenario: Multiple responsibilities need multiple owners
- **WHEN** no single member covers every primary responsibility but one unique smallest set does
- **THEN** the umbrella requires an explicit declarative composition for exactly that set

#### Scenario: Zero or equal-minimum ambiguity is visible
- **WHEN** no applicable set covers the responsibilities or several distinct sets have the same minimum cardinality
- **THEN** the umbrella returns a typed blocked result and executes no member

### Requirement: Multi-member composition is explicit and bounded
A necessary multi-member composition SHALL declare exactly one step per derived member, contiguous order, earlier-step dependencies, per-step responsibility condition ids, input and output handoff ids, handoff fields, exactly one producing owner per field, and one overall claim boundary. Responsibilities and fields MUST NOT have multiple owners. Every non-first step MUST receive at least one handoff from a declared earlier dependency. The umbrella SHALL emit composition-planning evidence only and SHALL NOT claim native member execution or completion.

#### Scenario: Necessary pair is accepted
- **WHEN** SourceGuard and TraceGuard are the unique minimum sufficient set and the composition declares exact responsibilities, order, handoff, field ownership, and claim boundary
- **THEN** the umbrella emits `composition_ready` for those two members in declared order without eagerly loading the other members

#### Scenario: Responsibility or field ownership conflicts
- **WHEN** two steps claim one responsibility or one field has zero or multiple owners
- **THEN** composition blocks before any native member executes

#### Scenario: Order or handoff is missing
- **WHEN** a non-first step lacks an earlier dependency, corresponding input handoff, or producing-step field owner
- **THEN** composition blocks and exposes the missing relation

### Requirement: Initial loading is narrow and deepening is conditional
Each member SHALL expose a small entry shell and a target-owned reference map. The entry shell MUST name the first native action, claim boundary, non-use boundary, deepening triggers, terminal reasons, and the reference required for each trigger. The system SHALL load only the selected member and the references whose declared triggers are present.

#### Scenario: Narrow task does not load deep material
- **WHEN** a selected member can complete the requested bounded first action without a deepening trigger
- **THEN** unrelated member skills and untriggered deep, command, template, or maintenance references remain unloaded

#### Scenario: Deep task retains full capability
- **WHEN** a broad, predictive, high-impact, model-miss, contradictory, repeated-failure, or explicitly deep request leaves an addressable native gap
- **THEN** the selected member loads the owning deep reference and continues its existing predict-validate-revise loop until native closure or an explicit non-closure terminal

#### Scenario: Self-report cannot close the task
- **WHEN** the AI states that it understands the task but the selected member still has a current native gap
- **THEN** the result remains open, blocked, stalled, limited, externally dependent, or scope-excluded according to the member's existing terminal contract

### Requirement: Prompt loading is machine checked
ResearchGuard SHALL maintain a target-owned prompt-bundle and load-graph contract covering the umbrella, every member entry, generated admission index, and conditional references. The checker MUST reject missing references, untriggered mandatory loads, trigger-to-reference gaps, duplicate authority, eager sibling loading, stale generated indexes, and entry bundles that exceed their declared budgets.

#### Scenario: Selected path has bounded first read
- **WHEN** a prompt bundle is evaluated for the umbrella or one direct member
- **THEN** the result reports the exact always-loaded and conditionally loaded files, byte totals, limits, and headroom without representing the byte proxy as provider token billing

#### Scenario: Known-bad load graph fails
- **WHEN** a selected member path includes another member skill or a reference without its declared trigger
- **THEN** the target-owned checker fails with the offending path and ownership relation

### Requirement: Maintained identities remain synchronized
The patch release SHALL keep package, module, executable suite model, JSON model, consumer skill, native check, SkillGuard contract-source, compiled-contract, and check-manifest identities synchronized at version `0.4.1`. Author-side SkillGuard artifacts SHALL remain outside consumer runtime behavior.

#### Scenario: Affected validation is current
- **WHEN** the change is ready for handoff
- **THEN** the focused routing, prompt-bundle, suite-model, member-contract, and contract-compilation checks pass against the same current source identity
