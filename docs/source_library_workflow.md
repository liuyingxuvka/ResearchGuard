# Source Library Workflow

LogicGuard owns argument licensing and a source library for preserving,
modeling, linking, and reusing research material. Source-library operations are
an internal LogicGuard route reached through:

```powershell
researchguard logic intake ...
researchguard logic library ...
```

## Preservation and completion are different

Default CLI intake preserves the supplied material, creates or reuses its
source record, and builds a deterministic shallow navigation model. This is a
safe first step, but it is not a claim that the source has been understood.

For Codex-facing intake, Codex must read the source and write a
content-level shallow model covering the central question, claim, method, evidence or
result, warrant or mechanism, and limitation when those elements are
available. It must then inspect that model with `view-graph` or
`view-snapshot`.

If the material can be preserved but cannot be read or modeled, report it as
**preserved with modeling incomplete** and name the blocker. Never convert
generated prose into source evidence.

## Current authority

The source library stores one canonical source record and one current model.
`added_at`, `source_date`, and `coverage_period` have distinct meanings:

- `added_at` records library accession time;
- `source_date` records when the source itself is dated;
- `coverage_period` records the factual period covered.

When bilingual display is required, both `en` and `zh-CN` values must be saved
explicitly. A missing requested translation is a visible modeling gap; the
runtime does not substitute another language.

## Gap-ledger route

```text
gap found
-> search current source-library records
-> preserve and model new material only when needed
-> deepen or link the relevant source node
-> re-evaluate the affected claim
```

A gap is closed only by current modeled and linked evidence, not by a search
suggestion or an author-side validation receipt.
