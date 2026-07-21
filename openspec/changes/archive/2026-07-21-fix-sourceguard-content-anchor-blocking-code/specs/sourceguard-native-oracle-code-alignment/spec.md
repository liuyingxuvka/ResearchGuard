## ADDED Requirements

### Requirement: Content-anchor bad cases expose the declared native finding
The SourceGuard target-purpose gate SHALL observe
`sourceguard_blocked:contentless-anchor` when the content-anchor oracle removes
all extracted text and normalized summaries from anchors needed by a governed
gap.

#### Scenario: Content-bearing known-good case
- **WHEN** a target purpose contract selects the content-anchor oracle and its supplied observation contains a content-qualified anchor
- **THEN** the known-good proof completes without the content-anchor blocking finding

#### Scenario: Contentless known-bad case
- **WHEN** the same target purpose contract executes its declared `remove-anchor-content` bad-case mutation
- **THEN** the native depth result contains exactly `sourceguard_blocked:contentless-anchor` for the affected object-depth row and the target-purpose proof records the bad case as blocked

### Requirement: Content-anchor finding has one current identity
The current SourceGuard depth path MUST NOT emit or accept
`no_content_qualified_anchor` as an alternate success or compatibility finding
for the content-anchor oracle.

#### Scenario: Current receipt is inspected
- **WHEN** a contentless anchor blocks object depth
- **THEN** the receipt uses the catalog-declared finding and contains no retired alternate finding for that condition

### Requirement: Unrelated depth semantics remain unchanged
The correction SHALL preserve SourceGuard's existing portfolio, lineage,
target-unit, adequacy, and broad-claim gates, and SHALL NOT promote a
contentless or locator-only anchor into claim-usable evidence.

#### Scenario: Locator exists without content
- **WHEN** an anchor has a locator but no extracted text or normalized content summary
- **THEN** object depth remains failed and broad claim licensing remains false

#### Scenario: Content finding coexists with other depth failures
- **WHEN** the same governed gap also lacks required portfolio classes or independent lineages
- **THEN** those native failures remain visible alongside the single current content-anchor finding
