## Why

SourceGuard's target-model purpose gate declares the content-anchor oracle with
the blocking finding `sourceguard_blocked:contentless-anchor`, but the native
depth owner emits `no_content_qualified_anchor` for the same bad case. Because
the identities differ, a valid content-anchor contract cannot close its native
known-bad proof even though the depth check correctly blocks broad closure.

## What Changes

- Make the SourceGuard depth owner emit the catalog-declared blocking finding
  for a critical gap with no content-qualified anchor.
- Preserve the existing fail-closed depth behavior and all other portfolio,
  lineage, target-unit, and claim-boundary semantics.
- Add regression evidence that the declared content-anchor oracle passes its
  good case and observes its exact blocking code in the bad case.
- Model and verify the code-identity invariant with FlowGuard before release.

## Capabilities

### New Capabilities

- `sourceguard-native-oracle-code-alignment`: Requires every declared
  SourceGuard native oracle used by a target purpose proof to expose the exact
  blocking finding produced by its owning native depth path.

### Modified Capabilities

None.

## Impact

- Affected runtime: `researchguard.source.depth` content-anchor finding output.
- Affected contract surface: the existing SourceGuard native oracle catalog;
  its declared identifier and fingerprint remain unchanged.
- Affected evidence: SourceGuard semantic-depth tests, target-purpose proof
  regression tests, and the FlowGuard child model for oracle/depth alignment.
- No new dependency, compatibility reader, alias, alternate route, or fallback
  behavior is introduced.
