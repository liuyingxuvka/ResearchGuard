# Canonical external-domain DNA examples

`attention-is-all-you-need-v7.json` is a bounded-scope model, not a claim that every meaning in the paper has been modeled. It inventories all 25 files in the frozen material root and deeply models one question: why the English-to-French BLEU value appears as both 41.8 and 41.0. Its `model_scope` keeps the rest of the paper as an explicit excluded semantic region and exposes a recursive expansion frontier.

`attention-is-all-you-need-v7.authority.json` is the independently produced signed scope denominator for that candidate. It freezes the target/version/material inventory, structure semantic roles, three distinct source occurrences, all four members' required input/output kinds, every handoff, the LogicGuard scope limit, exclusions, and expansion frontier. The candidate carries only its binding to this record; candidate outputs do not generate or rewrite the authority. The private fixture key exists only under `tests/`, never in runtime or packaged resources.

`canonical-native-composition.json` carries the exact current SourceGuard, TraceGuard, LogicGuard, and ExperimentGuard envelopes, target authorities, owner attestations, behavior manifests, native receipts, and four closed native-material records. Those records preserve LogicGuard's purpose contract/candidate/good-bad cases, SourceGuard's contract/observations, TraceGuard's task contract/good-bad models, and ExperimentGuard's frozen spec, so replay does not depend on the compiler's temporary directory. `canonical-native-trust-roots.json` and `canonical-scope-authority-trust-roots.json` are separate producer-descriptor trust sets for the canonical fixtures. Supplying either trust string is an explicit caller decision; a bundle never authorizes its own keys.

The portable verifier proves that `(member_id, receipt_id)` is unique inside this supplied bundle and that each carried reference matches its carried signed bytes. It does not prove cross-bundle non-equivocation. That stronger statement requires a shared immutable authority or transparency log outside all independently isolated bundles.

Regenerate the canonical author fixture only from an explicitly supplied frozen
material root; the compiler has no machine-local fallback:

```powershell
$env:RESEARCHGUARD_EXTERNAL_DNA_PAPER_ROOT = "<frozen-root>"
python scripts/compile_external_domain_dna_examples.py
```

The four files above are the single canonical source for this example.  They
are deliberately kept under `models/external_domain_dna`; no second copy is
installed as `researchguard.resources.external_domain_dna`, and the
ResearchGuard console has no public `domain-dna` build/inspect or generic
export/materialization route.  Native tests and the compiler use the
domain-DNA module directly, so all validation remains tied to the current
source tree and its explicit frozen material root.

Bundle-only inspection proves at most self-consistency. A carried scope authority is still untrusted until the caller explicitly supplies its exact authority fingerprint or producer-descriptor fingerprint. `dna_qualified` additionally requires the complete authority-derived current material root, every trusted artifact hash, native-member producer trust, scope-authority trust, and complete authority-obligation coverage.
