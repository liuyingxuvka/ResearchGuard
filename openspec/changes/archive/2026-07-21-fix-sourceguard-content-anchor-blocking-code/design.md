## Context

SourceGuard executes every target-authored purpose contract against native
good and bad cases before a model can be used. The content-anchor catalog row
owns the stable oracle identity and declares the bad-case mutation
`remove-anchor-content` together with the blocking finding
`sourceguard_blocked:contentless-anchor`. The native depth evaluator already
detects that condition, but labels it `no_content_qualified_anchor`; the proof
runner compares exact strings and therefore rejects the otherwise correct bad
case.

The affected behavior belongs to the existing SourceGuard evidence-discovery
path. The suite router, other Guard members, observation schema, and public
entrypoints do not own this decision.

## Goals / Non-Goals

**Goals:**

- Restore exact identity between the catalog-declared content-anchor oracle and
  the finding emitted by the native depth owner.
- Preserve fail-closed behavior for contentless anchors and every unrelated
  depth obligation.
- Prove the observed failure and its same-class locator-only case through the
  target-purpose gate and an executable FlowGuard model.
- Release the repair as one direct current behavior with no legacy alternate.

**Non-Goals:**

- Rename other SourceGuard findings or redesign the oracle catalog.
- Add a translation table, compatibility reader, alias, or dual emission.
- Change how anchor text, normalized summaries, portfolios, lineages, or target
  units are qualified.
- Claim that a content-qualified anchor is factually true or downstream-valid.

## Decisions

### The native depth owner emits the catalog-declared code

Change the content-anchor branch in the depth evaluator to emit
`sourceguard_blocked:contentless-anchor` directly. The catalog is the frozen
contract surface consumed by target-model purpose proofs, while the old depth
string is an implementation-local label with no independent owner.

Changing the catalog to match the old string was rejected because it would
move the contract to follow a drifted implementation and invalidate every
catalog-fingerprint-bound SourceGuard model. Emitting both strings was rejected
because it creates a compatibility chain and leaves two authorities for one
condition.

### Replace the old finding rather than alias it

The old `no_content_qualified_anchor` output is removed from the current depth
path and from current tests. A repository residual scan will prove there is no
remaining runtime or test expectation for it.

### Test through the owning proof path

The regression test constructs a content-anchor purpose contract whose known
bad case uses `remove-anchor-content`, supplies the same content-bearing
observation for the good and bad paths, and requires the exact catalog finding
only in the bad path. This covers the public model-loading gate, not merely the
private row-building helper. The existing locator-only semantic-depth test is
updated to assert the same canonical finding.

### Add a narrow FlowGuard child model

The model is a child of SourceGuard's existing evidence-discovery owner and
represents one block as `Input x State -> Set(Output x State)`. It covers the
aligned good case and the previously observed drifted bad implementation, with
the invariant that a blocked contentless anchor carries exactly the declared
finding and never the retired alternate. It does not duplicate SourceGuard's
qualification algorithm.

## Risks / Trade-offs

- [Consumers inspected the old internal string] -> This is a direct correction
  to the already-declared current contract; release notes name the replacement,
  and no compatibility alias is retained.
- [A one-line code fix could leave the proof path untested] -> Exercise the
  complete target-purpose proof in addition to the focused depth assertion.
- [A local model could overclaim production correctness] -> Keep the FlowGuard
  claim limited to code-identity behavior and require native SourceGuard tests,
  full suite tests, package checks, and release identity separately.

## Migration Plan

1. Add the failing end-to-end regression and FlowGuard known-bad case.
2. Replace the depth finding with the catalog-declared current finding.
3. Remove all source/test residuals of the retired finding.
4. Run focused SourceGuard checks, FlowGuard checks, then one frozen full suite.
5. Bump to the next patch version and publish a source-only GitHub Release.

Rollback is the normal Git revert of this isolated change before release. After
release, correction uses a new patch release; no runtime fallback is added.
