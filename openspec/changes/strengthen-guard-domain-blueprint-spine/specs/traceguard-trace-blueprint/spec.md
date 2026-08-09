## Purpose

Define a deterministic TraceGuard-owned investigation blueprint that makes source-to-evidence-to-event-to-trace-to-hypothesis interfaces explicit while retaining one canonical inference engine and bounded causal semantics.

## ADDED Requirements

### Requirement: TraceGuard projects one deterministic investigation hierarchy
TraceGuard SHALL deterministically project the current source, evidence, entity, event, temporal or stage, trace, storyline-hypothesis, and causal-boundary objects into one rooted investigation hierarchy. Every projected child MUST resolve to a current native object and every non-root projected object MUST have one declared containment parent or an explicit cross-link disposition.

#### Scenario: Current trace model produces a hierarchy
- **WHEN** a current TraceGuard model and its native identities are valid
- **THEN** TraceGuard produces the same rooted hierarchy for every permutation-equivalent input

#### Scenario: Projected child is absent from the native model
- **WHEN** a hierarchy relation refers to an event, evidence item, trace, or hypothesis absent from the current native model
- **THEN** TraceGuard blocks blueprint qualification and reports the unresolved identity

### Requirement: Trace layers communicate through typed interfaces
TraceGuard SHALL bind evidence-fact outputs to event inputs, event outputs to sequence or trace inputs, trace outputs to storyline-hypothesis inputs, and hypothesis outputs to bounded claims or handoffs. Every required parent input MUST be produced by a compatible child or external input, and every material child output MUST be consumed or explicitly dispositioned.

#### Scenario: Event evidence is consumed by a trace
- **WHEN** current evidence supports or limits an event and the event participates in a trace
- **THEN** the blueprint records both interface bindings and their native receipt references

#### Scenario: Required event lacks evidence
- **WHEN** a material event has no permitted evidence-fact input and no explicit unresolved disposition
- **THEN** TraceGuard keeps the event and all dependent trace and hypothesis claims incomplete

### Requirement: Blueprint projection consumes the canonical inference receipt
TraceGuard's blueprint check, hierarchy, impact, reverse trace, and export SHALL consume the same current canonical inference receipt and native object identities used by ordinary TraceGuard evaluation. The blueprint layer MUST NOT introduce a second score, solver, confidence authority, compatibility reader, retry path, or fallback inference engine.

#### Scenario: Canonical receipt is current
- **WHEN** a blueprint references a current canonical inference receipt for the same model fingerprint
- **THEN** TraceGuard may project the receipt's bounded results into the hierarchy without rescoring them

#### Scenario: Canonical solver fails or receipt is stale
- **WHEN** the canonical solver fails, is infeasible, or its receipt fingerprint does not match the model
- **THEN** blueprint qualification remains failed or stale and no alternate solver or heuristic result is selected

### Requirement: Trace objects carry stable source and transformation identities
Every source, evidence item, event, trace, and hypothesis used for closure SHALL carry or resolve to a stable object fingerprint, source revision, locator, and relevant normalizer or extractor identity. Derived projection identities MUST change when their consumed semantic content changes.

#### Scenario: Evidence content changes
- **WHEN** an evidence item's content fingerprint changes while its display identifier remains the same
- **THEN** TraceGuard treats the evidence and its consuming event, trace, hypothesis, causal candidate, and receipt as affected

#### Scenario: Display-only metadata changes
- **WHEN** metadata outside the declared semantic fingerprint changes
- **THEN** TraceGuard preserves current native results unless another declared dependency is affected

### Requirement: Trace impact and reverse trace preserve alternatives and claim boundaries
TraceGuard SHALL provide affected-only impact, reverse-trace, and deterministic export operations. Impact and reverse trace SHALL each consume exactly one current native blueprint qualification for the same model, stable-object material, authority, canonical receipt, and purpose replay. Failed, stale, unverified, or not-run qualification MUST atomically suppress ordinary affected/unaffected output and MUST keep reverse trace incomplete. Reverse trace SHALL connect a bounded narrative fragment or handoff to its projection, canonical receipt contributions, hypothesis or causal candidate, trace, events, evidence, and sources. Competing storylines, confounders, limitations, and non-causal boundaries MUST remain visible.

#### Scenario: One evidence item changes
- **WHEN** one evidence fingerprint changes
- **THEN** TraceGuard invalidates only its declared event, trace, hypothesis, causal, perturbation, depth, holdout, narrative, and handoff consumers

#### Scenario: Narrative fragment is reverse traced
- **WHEN** a caller traces a bounded narrative fragment
- **THEN** TraceGuard returns the exact hypothesis, trace, events, evidence, sources, solver receipt contributions, alternatives, and claim boundary supporting that fragment

#### Scenario: Blueprint round trip is stable
- **WHEN** a current trace blueprint is exported and reloaded without semantic changes
- **THEN** its hierarchy, interfaces, live alternatives, causal boundary, gaps, canonical receipt identity, and fingerprint remain identical

### Requirement: Causal language remains bounded
A complete trace blueprint SHALL NOT by itself license formal causal identification, structural causal model claims, do-calculus, calibrated treatment effects, or any stronger conclusion than the current TraceGuard native causal boundary.

#### Scenario: Chronology is mistaken for causality
- **WHEN** events are ordered in time but native mechanism, link evidence, confounder, alternative, scope, or counterfactual obligations remain open
- **THEN** TraceGuard preserves a non-causal or insufficient boundary despite hierarchy completeness
### Requirement: Trace denominator and native receipts are externally anchored current-owner evidence

Before TraceGuard models the task, one provider-neutral externally owned expected-target anchor SHALL freeze the original task/request identity, native target identity and revision, exact raw native-inventory locator and fingerprint, admission owner/producer, admission input/result identities, and immutable admission-receipt identity. Umbrella admission MAY produce the anchor from original task facts; direct member use MUST receive it externally and MUST remain unverified when it is absent or unavailable.

TraceGuard SHALL parse the complete stable-object denominator only from the exact bytes named by that anchor through its closed current adapter on initial check and serialized reload. Private target authority SHALL bind the anchor identity and exact material fingerprint. Production MUST NOT expose a public target-authority issuer, arbitrary locator route, inline target-material authoring helper, or trace-model/universe-to-target helper. Every model, interface, canonical-inference, purpose, depth, and owner receipt used for qualification MUST resolve from immutable producer bytes and bind its producer, request, input, result, model, checker, task, status, locator, and receipt fingerprint. Submitted model/universe rows, process memory, self-fingerprinted authority, caller-invented receipt ids, and receipt self-hashes cannot define the denominator or current evidence.

#### Scenario: Blueprint query has no current qualification
- **WHEN** impact or reverse trace receives failed, stale, unverified, or not-run target material, authority, canonical receipt, or purpose replay
- **THEN** TraceGuard returns the exact qualification gaps, no ordinary affected/unaffected set, and no complete reverse-trace terminal

#### Scenario: Unknown output cannot bypass a failed qualification
- **WHEN** reverse trace receives an unknown output id while its one current native qualification is failed, stale, unverified, or not run
- **THEN** TraceGuard returns an atomic rejected report before hypothesis, trace, event, evidence, source, hierarchy, causal, or receipt-contribution computation, with all ordinary terminal fields empty

#### Scenario: Trace universe and raw target bytes are coherently shrunk
- **WHEN** a caller removes the same sensitivity object from the trace model, universe, and raw target bytes, recomputes every caller-controlled identity, and retains the originally admitted expected-target anchor
- **THEN** exact anchor replay fails, TraceGuard preserves the incomplete reverse-trace boundary, and ordinary impact and reverse-trace output is suppressed

#### Scenario: Caller invents a TraceGuard receipt
- **WHEN** a coherent-looking interface, canonical-inference, purpose, depth, model, or owner receipt cannot be reopened from its declared immutable producer locator
- **THEN** TraceGuard rejects it as unresolved even when its caller-computed fingerprint is internally consistent

#### Scenario: Direct member has no external anchor
- **WHEN** TraceGuard is invoked directly without a provider-owned expected-target anchor
- **THEN** target qualification is unverified and TraceGuard does not treat the submitted stable-object list as its own target

#### Scenario: Native inventory material cannot be replayed
- **WHEN** the anchor or receipt locator is external, missing, changed, or not current-adapter/resolver parseable
- **THEN** TraceGuard preserves a failed or unverified target-or-receipt gap and never falls back to the submitted stable-object list or caller receipt metadata

#### Scenario: Alternate trace target has a new anchor
- **WHEN** a different native trace target is separately admitted under a new external expected-target anchor
- **THEN** TraceGuard may replay that exact target while rejecting any attempt to reuse the earlier anchor

### Requirement: The investigation blueprint remains member-domain DNA
The TraceGuard blueprint SHALL own temporal trace, storyline, alternative, evidence, bounded-causal, interface, and native closure semantics. It MAY be referenced by the ResearchGuard repository software-DNA subtree as semantic evidence, but it MUST NOT by itself claim complete repository code, test, intent, resource, topology, installation, or release coverage and MUST NOT become a competing whole-repository software blueprint.

#### Scenario: Native trace closure precedes its software binding
- **WHEN** an investigation blueprint has current native closure but its implementing surfaces, tests, sources, resources, or repository ownership bindings are incomplete
- **THEN** TraceGuard MAY retain its bounded domain result while ResearchGuard software-DNA readiness remains incomplete
