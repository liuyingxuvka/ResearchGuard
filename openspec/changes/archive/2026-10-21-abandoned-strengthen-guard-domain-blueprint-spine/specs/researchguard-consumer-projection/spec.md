## ADDED Requirements

### Requirement: The suite installer uses the current SkillGuard projection and installation authority

The ResearchGuard repository installer SHALL remain the order and suite-transaction owner for the five-member suite while delegating each member's file selection and release identity to the current SkillGuard consumer-distribution authority and delegating member preparation, verification, activation, receipt, backup, recovery, and rollback to the current SkillGuard target-installation authority. ResearchGuard SHALL own one process-held total suite mutation lock spanning Python package replacement, all five delegated activations, suite-manifest replacement, terminal verification, and in-process restoration. That lock MUST NOT become a second per-member target-installation algorithm. The installer MUST NOT raw-copy or directly swap skill directories, generate a second release or member transaction identity, retain a compatibility reader, or require SkillGuard at ordinary consumer runtime.

#### Scenario: A current five-member projection is prepared

- **WHEN** installation prepares ResearchGuard, LogicGuard, SourceGuard, TraceGuard, and ExperimentGuard from frozen current author sources and compiled contracts
- **THEN** each staged tree is prepared and reverified by the current target-installation API from the current consumer-distribution plan
- **AND** each staged tree contains its exact generated `consumer-release.json`
- **AND** no staged tree contains `.skillguard`, author contracts, receipts, execution-owner state, FlowGuard evidence, or private author paths

### Requirement: Ordered suite activation and later failure restore every changed domain

All five consumer trees SHALL be completely prepared and independently reverified before any activation begins. A staging failure MUST leave the entire prior installation unchanged. Before Python package mutation, the suite owner SHALL freeze the exact prior ResearchGuard distribution inventory and bytes and the prior suite-manifest bytes or exact absence. Each activation SHALL be owned by one SkillGuard target transaction. If a later activation returns failure, raises an ordinary exception, returns a malformed successful identity, or any later manifest, currentness, console, or smoke check fails, the suite owner MUST keep the total lock while attempting every applicable restoration domain: invoke SkillGuard rollback for every earlier activation in reverse order, restore the exact prior Python distribution, and restore the exact prior suite manifest. Each domain and each rollback call SHALL be isolated so one returned failure or exception does not prevent the remaining attempts. A returned consumer rollback success is accepted only when its skill id, transaction id, and restored terminal status identify the exact requested rollback. Package and manifest restoration require exact current inventory and byte comparison. A malformed successful current activation SHALL also be rolled back when its returned transaction pointer is usable. Any unverified restoration MUST return `cleanup_unconfirmed`. The result MUST NOT claim that five separately committed transactions form one crash-atomic filesystem transaction. A process interruption, unusable current pointer, or residual mixed set remains visibly blocked until the package, current five-member set, and suite manifest are restored or reactivated.

#### Scenario: A concurrent suite installer already holds the lock

- **WHEN** a second ResearchGuard installation begins while the total suite mutation lock is held
- **THEN** the second installer blocks before package, consumer, or manifest mutation
- **AND** it does not wait, retry, or select an alternate installation path

#### Scenario: A member projection fails during staging

- **WHEN** one member consumer projection cannot be built after one or more earlier members were staged
- **THEN** the installer removes only its temporary stage
- **AND** every previously installed current member and retired surface remains byte-for-byte in place
- **AND** no partial new member is activated

#### Scenario: A later member activation returns failure

- **WHEN** all five staged projections are current, one or more earlier members activate, and a later member activation returns failure
- **THEN** the suite owner rolls back every earlier committed member in reverse order through SkillGuard
- **AND** any rollback residual is part of the blocked result
- **AND** explicitly retired skill surfaces are not silently deleted or accepted

#### Scenario: Final currentness fails after every member activated

- **WHEN** the Python package and all five consumers changed but suite-manifest, console, or installed-currentness verification then fails
- **THEN** the suite owner attempts consumer rollback in reverse order, exact package restoration, and exact manifest restoration while still holding the total lock
- **AND** one restoration failure does not suppress the other attempts
- **AND** any unverified domain makes the terminal `cleanup_unconfirmed`

### Requirement: Installed currentness is identity-based and read-only

The installed-currentness check SHALL use SkillGuard's public static target verification on each active consumer tree and compare its complete member set, skill identity, and release identity with the frozen source plan. A missing, invalid, mismatched, or stale `consumer-release.json` MUST block currentness. The check MUST NOT launch member semantic checks, rebuild a projection, activate or roll back a transaction, repair an installation, or treat a raw file copy as current.

#### Scenario: An installed release manifest is missing or stale

- **WHEN** any installed member lacks a valid generated release manifest or its release id differs from the current source plan
- **THEN** installed currentness is `blocked`
- **AND** the finding names the affected member and identity boundary
- **AND** no semantic validation owner is launched

### Requirement: Repository self-DNA authority remains outside consumer projections

Installed consumer skill trees SHALL contain only their governed consumer prompts, references, agents, assets, and generated consumer release identity. Author-side implementation denominators, canonical software-DNA exports, current pointers, model revisions, activation records, architecture-reduction findings, validation receipts, and release-publication evidence MUST remain outside every consumer tree. A consumer's member-domain blueprint guidance MUST NOT be presented as the canonical self-DNA of the ResearchGuard source repository.

#### Scenario: A canonical self-DNA artifact enters a staged consumer

- **WHEN** a staged member tree contains an author-side repository inventory, canonical export, current pointer, revision, receipt, or reduction report
- **THEN** projection verification fails before activation and identifies the author/consumer boundary violation

### Requirement: Suite provenance does not impersonate SkillGuard receipt currentness

The suite manifest SHALL record the exact five source release ids and the transaction, receipt-hash, and HEAD-generation pointers returned by successful SkillGuard activations. ResearchGuard MAY validate their returned shape and cross-field identity during activation, but MUST NOT parse SkillGuard's private journal or claim that its suite manifest independently proves those pointers remain current. The read-only currentness result SHALL state that static consumer projection, Python package, Git, tag, release, and SkillGuard receipt currentness are separate claim domains.

#### Scenario: A plausible transaction string is not receipt proof

- **GIVEN** a suite manifest contains a transaction-like string and arbitrary receipt-like text
- **WHEN** the value does not match the current target-installation pointer shape
- **THEN** the suite manifest is blocked
- **AND** even a well-shaped stored pointer is described only as recorded provenance unless SkillGuard itself provides a current public receipt audit

### Requirement: Installation paths and package currentness are explicit

Before wheel installation or consumer activation, the installer SHALL require one absolute `CODEX_HOME` that is neither a link nor a reparse point, its canonical active-skill child, and non-escaping ResearchGuard manifest and suite-lock roots. The `pyproject.toml` package version and the source package `__version__` SHALL be identical before source validation or package mutation. Manifest replacement, manifest restoration, and package-file restoration SHALL use unique exclusive temporary files in their validated roots. Retired skill residuals SHALL block before Python package replacement and SHALL be checked again before activation. Read-only package currentness SHALL compare every successfully observed inventory including an empty inventory, report whether import resolved to repository source or an installed distribution, and require exactly one materialized `researchguard` console entrypoint.

#### Scenario: An empty installed package directory is observed

- **WHEN** distribution metadata resolves but the imported package inventory is empty while the source package is not
- **THEN** installed currentness is `blocked`
- **AND** the empty inventory is not treated as an unavailable optional comparison
