# researchguard-narrow-entry-loading Specification

## Purpose
Keep the always-loaded ResearchGuard entry small: one `researchguard` skill whose SKILL.md is a route table, and each route's workflow loaded only when that route is chosen.

## Requirements
### Requirement: One skill entry with a route table
ResearchGuard SHALL ship exactly one agent skill, `researchguard`, whose SKILL.md lists the four routes `logic`, `source`, `trace` and `experiment` with the route file to load for each.

#### Scenario: An argument needs checking
- **WHEN** an agent is asked to check whether a conclusion is supported
- **THEN** it SHALL choose the `logic` route in the table and load only `references/routes/logic.md`

### Requirement: The entry starts from the question model
The SKILL.md SHALL begin with `## Start from the model`: read an existing research folder with `researchguard status <folder>` (or one hypothesis with `--hypothesis <id>`), or write `research.yaml` first for a new question, before choosing a route.

#### Scenario: A research folder already exists
- **WHEN** an agent receives a request about a question that has a research folder
- **THEN** it SHALL run `researchguard status <folder>` and take the route that Next names

### Requirement: Each route is one file plus its own references
Each former member skill SHALL be one file `references/routes/<route>.md`, and its references SHALL live under `references/<route>/`; a route file loads its references only when their trigger fires.

#### Scenario: A route needs its commands
- **WHEN** the `source` route reaches its `trigger:commands` condition
- **THEN** the agent SHALL load `references/source/commands.md` and no other route's files

### Requirement: Short description
The skill description SHALL stay at or below 300 characters, say what the skill is for, and name the sibling skill to use instead.

#### Scenario: The description grows
- **WHEN** the description exceeds 300 characters
- **THEN** `tests/test_skill_suite.py` SHALL fail

### Requirement: Reinstall removes retired skill folders
The installer SHALL replace the installed `researchguard` copy and remove the retired `logicguard`, `sourceguard`, `traceguard` and `experimentguard` folders.

#### Scenario: Reinstall over the old five-skill layout
- **WHEN** `python scripts/install_skill.py --target <skills directory>` runs where the old member folders exist
- **THEN** only `researchguard` SHALL remain of them and `--check` SHALL print `installed skills are current`

### Requirement: The console is unchanged
The console SHALL keep `researchguard logic|source|trace|experiment ...`, and a route's failure SHALL stay visible without a retry through another route.

#### Scenario: A route fails
- **WHEN** `researchguard source ...` returns a non-pass result
- **THEN** the result SHALL be reported as is and no other route SHALL run automatically

#### Scenario: A source or trace model needs field names
- **WHEN** the selected route reaches `trigger:fields` before writing a model or observation
- **THEN** the agent SHALL load that route's field sheet with current fields, defaults and allowed values
