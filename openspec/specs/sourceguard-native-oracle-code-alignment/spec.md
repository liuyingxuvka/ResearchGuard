# sourceguard-native-oracle-code-alignment Specification

## Purpose
Keep one finding identity for SourceGuard's contentless-anchor block, so source depth fails visibly when an anchor carries no content.

## Requirements
### Requirement: A contentless anchor blocks object depth with one finding
SourceGuard source depth SHALL report `sourceguard_blocked:contentless-anchor` for a governed gap whose linked anchors carry no extracted text or normalized summary.

#### Scenario: Content-bearing anchor
- **WHEN** the observation's anchors carry content and pass the qualification thresholds
- **THEN** the object-depth rows SHALL pass without the contentless-anchor finding

#### Scenario: Contentless anchor
- **WHEN** the same anchors have their text and normalized summary removed
- **THEN** broad claim licensing SHALL be false and an object-depth row SHALL contain `sourceguard_blocked:contentless-anchor`

### Requirement: The retired finding is never emitted
SourceGuard depth MUST NOT emit `no_content_qualified_anchor` as an alternate finding for this condition.

#### Scenario: The self-model checks the code
- **WHEN** `python -m flowguard map models` runs the content-anchor self-model
- **THEN** its conformance SHALL read `src/researchguard/source/depth.py` and fail if the declared finding is missing or the retired finding is present

### Requirement: Other depth failures stay visible
The contentless-anchor finding SHALL coexist with SourceGuard's portfolio, lineage and target-unit findings, and a locator without content SHALL NOT become claim-usable evidence.

#### Scenario: Locator without content
- **WHEN** an anchor has a locator but no content
- **THEN** object depth SHALL remain failed and broad claim licensing SHALL remain false
