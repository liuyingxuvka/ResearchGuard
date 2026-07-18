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
