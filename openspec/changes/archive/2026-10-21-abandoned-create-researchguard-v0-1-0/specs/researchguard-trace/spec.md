## ADDED Requirements

### Requirement: TraceGuard remains the canonical inference owner
The trace member SHALL preserve TraceGuard's typed constrained HL-MRF/QP
compiler, OSQP solution, canonical inference receipt, storyline depth,
perturbation, causal-boundary, case-library, handoff, and claim-boundary
semantics.

#### Scenario: Trace workflow executes
- **WHEN** a valid trace purpose contract and model are supplied
- **THEN** `researchguard trace` executes the TraceGuard native owner and
  returns the canonical inference receipt

### Requirement: Case library is an internal route
Case-library operations SHALL remain an internal trace route and SHALL NOT be
an independent installed Skill ID.

#### Scenario: Case library is requested
- **WHEN** `$traceguard` receives a case-library task
- **THEN** it executes the internal library route under the same trace member
  and suite identity

### Requirement: One current support field
TraceGuard outputs SHALL use the current support semantics without a
`confidence` alias or dual-field output.

#### Scenario: Retired confidence field is supplied
- **WHEN** normal runtime receives the retired confidence field
- **THEN** it rejects the input and does not infer or emit support from it

### Requirement: No solver fallback
Solver failure, infeasibility, unacceptable residuals, or unapproved backend
SHALL remain a visible blocked result.

#### Scenario: OSQP result is unacceptable
- **WHEN** the canonical quality gates fail
- **THEN** TraceGuard returns blocked and does not run heuristic scoring
