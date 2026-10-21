## ADDED Requirements

### Requirement: ExperimentGuard recommends but never executes

ExperimentGuard SHALL compare declared observation or intervention candidates across explicit hypotheses, possible outcomes, cost, and risk and SHALL return a recommendation-only receipt.

#### Scenario: One candidate best separates hypotheses

- **WHEN** one candidate produces the strongest exact outcome partition within declared risk and cost limits
- **THEN** ExperimentGuard SHALL recommend that candidate with its partition and decision rationale

#### Scenario: Execution is requested

- **WHEN** a request asks the member to run, schedule, or actuate the experiment
- **THEN** ExperimentGuard SHALL block and hand off the recommendation without causing the side effect

### Requirement: Probabilities are never invented

ExperimentGuard SHALL use only caller-supplied calibrated likelihoods and otherwise SHALL use exact set-based outcome partitions.

#### Scenario: Likelihoods are absent

- **WHEN** the caller supplies outcome sets but no calibrated likelihoods
- **THEN** ExperimentGuard SHALL use set-based discrimination and SHALL NOT synthesize probabilities

### Requirement: Neighboring owner boundaries remain explicit

ExperimentGuard SHALL declare forbidden conditions for source discovery, trace reconstruction, logical support, physical diagnosis, and software-test selection.

#### Scenario: The request is source discovery or trace reconstruction

- **WHEN** the requested outcome belongs to SourceGuard, TraceGuard, LogicGuard, PhysicsGuard, or FlowGuard test selection
- **THEN** ExperimentGuard SHALL return `not_applicable` with the owning route
