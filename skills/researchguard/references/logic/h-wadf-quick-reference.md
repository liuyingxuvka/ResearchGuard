# H-WADF Quick Reference

LogicGuard uses a Hierarchical Weighted Abstract Dialectical Framework:

```text
M = (V, E, H, T, A, W, S, Phi)
```

- `V`: logical nodes.
- `E`: argument edges.
- `H`: containment hierarchy.
- `T`: node types.
- `A`: assumptions.
- `W`: weights, credibility, importance.
- `S`: scopes and boundary conditions.
- `Phi`: acceptance functions.

Each node has separate `state` and `confidence`:

- `state`: `IN`, `OUT`, or `UNDECIDED`
- `confidence`: structural-strength heuristic in `[0, 1]`

Confidence is not probability.

`Evidence` nodes may carry `provenance`, a list of records saying where the material came from:
`provenance: [{origin_kind: external_source, source_id: <library source id>, locator: <node id in that source's model>, content_hash: "sha256:<hash of the cited text>", source_date: 2024-05-01}]`.
A record may supply `quote` instead of `content_hash`; the loader hashes the exact UTF-8 text,
including spaces and newlines. When both are supplied they must agree. A hash accepts the
existing optional `sha256:` prefix; missing both is an error. `quote` must be a non-empty
string and remains cited material, not a claim of factual truth. Provenance errors identify
the Evidence node, for example `Evidence node 'E_dates': content_hash must be a sha256 digest`.
`origin_kind` is one of `external_source`, `observed_event`, `user_attestation`, `test_result`, `human_observation`, `instrument_measurement`, `imported_record` (`ai_generated` and `derived` are not evidence). `source_reference` (for example a URL or DOI) may replace `source_id`.
`logic validate` warns about Evidence without provenance; `researchguard logic validate <model> --library-root <library>` also fails when a `source_id` is not in the library or a `locator` is not a node of that source's model, and warns when an Evidence node has no `source_id` + `locator` pair.

## Core Node Types

- `Claim`: assertion or conclusion.
- `Evidence`: data, result, citation, observation, figure, or simulation output.
- `Warrant`: bridge explaining why evidence supports a claim.
- `Assumption`: explicit or hidden dependency.
- `Rebuttal`: objection against a claim, premise, or evidence.
- `Undercutter`: objection against a warrant or inference bridge.
- `Qualifier` / `Limitation`: boundary condition.
- `Context`: background; not evidence unless connected by a warrant.
- `Definition`, `Method`, `Result`, `ArgumentBlock`, `Section`, `Document`.

## Core Edge Types

- `supports`
- `attacks`
- `undercuts`
- `qualifies`
- `depends_on`
- `refines`
- `contradicts`
- `contextualizes`
- `derives`
- `aggregates`

## Acceptance Conditions

Useful fields:

- `all_of: [A, B]`
- `any_of: [A, B]`
- `none_of: [R1]`
- `requires: [A1]`
- `requires_not_out: [A1]`
- `at_least_k: {k: 2, nodes: [E1, E2, E3]}`
- `threshold: 0.65`
- `no_undefeated_rebuttal: true`
- `scope_match: true`
- `warrant_required: true`

## Minimal Model Shape

```yaml
model:
  id: argument_audit
  title: "Argument audit"
  root_claim: C0

nodes:
  C0:
    type: Claim
    text: "Main conclusion."
    scope: "tested conditions"
  E1:
    type: Evidence
    text: "Observed result."
    confidence: 0.7
    scope: "tested conditions"
  W1:
    type: Warrant
    text: "Why E1 supports C0."
    confidence: 0.7

edges:
  - source: E1
    target: C0
    type: supports
    weight: 0.8
  - source: W1
    target: C0
    type: supports
    weight: 1.0

acceptance:
  C0:
    all_of: [E1, W1]
    threshold: 0.65
    scope_match: true
    warrant_required: true
```
