## ADDED Requirements

### Requirement: Exact entrypoint routing
ResearchGuard SHALL route an umbrella request exactly once to one declared
member or to an explicit multi-member orchestration plan.

#### Scenario: Single-member intent
- **WHEN** an umbrella request matches exactly one declared member intent
- **THEN** routing selects that member's sole primary path

#### Scenario: Ambiguous intent
- **WHEN** the request cannot be resolved without materially changing the
  outcome
- **THEN** routing returns a typed gap or focused question and executes no
  member

### Requirement: Direct and umbrella parity
Direct member invocation and umbrella dispatch for the same intent SHALL bind
the same native owner, primary path, request identity, version, and suite
fingerprint.

#### Scenario: Equivalent logic request
- **WHEN** the same LogicGuard request is invoked directly and through the
  umbrella
- **THEN** both resolve to the identical logic owner and machine path

### Requirement: Terminal selected-route failure
A member failure SHALL be returned as the terminal result of that selected
route.

#### Scenario: Selected member fails
- **WHEN** the selected member reports failed, blocked, stale, timeout,
  unsupported, or unavailable
- **THEN** ResearchGuard returns that state and does not select another member

### Requirement: Explicit typed handoffs
Cross-member continuation SHALL require a typed handoff consumed by the
umbrella or an explicit outer owner.

#### Scenario: Member identifies a sibling need
- **WHEN** a member discovers work owned by another member
- **THEN** it emits a typed handoff and does not execute the sibling itself

### Requirement: Recursion prevention
ResearchGuard SHALL reject nested umbrella redispatch of an already routed
member request.

#### Scenario: Routed request re-enters umbrella
- **WHEN** a member or consumer sends an active routed request back to
  `researchguard run`
- **THEN** the runtime returns a recursion error without executing a second path
