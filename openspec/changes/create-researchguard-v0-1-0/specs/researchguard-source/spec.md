## ADDED Requirements

### Requirement: SourceGuard remains the discovery owner
The source member SHALL preserve SourceGuard's native belief-state search
planning, source observation, qualification, depth, portfolio, lineage,
handoff, receipt, and claim-boundary semantics.

#### Scenario: Source workflow executes
- **WHEN** a valid source model contract and model are supplied
- **THEN** `researchguard source` executes the SourceGuard native owner and
  returns its native receipt

### Requirement: Candidates remain non-evidence
The source member SHALL NOT promote a search result, candidate, utility score,
registry row, or handoff bundle into validated evidence or a final claim.

#### Scenario: Candidate is discovered
- **WHEN** a search action yields a candidate source
- **THEN** the result remains a candidate until an owning downstream Guard
  validates or models it

### Requirement: Current lifecycle only
The source member SHALL use one current lifecycle and output model without a
legacy status reader, compatibility wrapper, or secondary status projection.

#### Scenario: Retired status input is supplied
- **WHEN** an input uses a retired status shape
- **THEN** normal runtime rejects it and names direct migration as required
