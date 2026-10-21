## ADDED Requirements

### Requirement: Important conclusions expose minimal support and attack sets

LogicGuard SHALL derive bounded subset-minimal support sets for a conclusion and subset-minimal attack sets that defeat its declared warrant or scope.

#### Scenario: A premise is redundant

- **WHEN** the conclusion remains licensed after one premise is removed
- **THEN** that premise SHALL NOT appear in the returned minimal support set

### Requirement: Final wording requires a license

The wording license SHALL bind conclusion id, supported scope, modality, assumptions, rebuttals, and prohibited stronger wording.

#### Scenario: Draft language exceeds the license

- **WHEN** final prose claims a stronger modality or broader scope than the license
- **THEN** delivery SHALL fail with an overclaim diagnostic and a bounded allowed rewrite

#### Scenario: No support set is current

- **WHEN** all support sets are stale, blocked, or incomplete
- **THEN** the license SHALL prohibit affirmative conclusion wording
