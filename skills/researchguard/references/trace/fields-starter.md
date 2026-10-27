## Complete synthetic starter

The same model is emitted by `researchguard trace create --output starter.yaml`. It has two dated events, two hypotheses and both support/opposition. The confounder remains unresolved deliberately: successful validation/evaluation is not proof that the filter caused recovery. This is invented teaching data, not externally verified evidence.

```yaml
metadata:
  schema_version: "researchguard.trace.model.v2"
  purpose: "Synthetic worked example: reconstruct a two-day device recovery and compare explanations."
  repository: "https://github.com/liuyingxuvka/ResearchGuard"
  skill: "TraceGuard"
  math_boundary: "Typed constrained HL-MRF/MAP structural support is not calibrated probability."
  cli: "researchguard trace validate starter.yaml"
  boundary: "All records below are invented teaching data. No external factual truth or causal certainty is asserted."
sources:
  - source_id: "example-source"
    title: "Synthetic maintenance notebook"
    source_type: "other"
    lineage_id: "example-notebook-lineage"
    independence_group: "example-notebook-origin"
    source_reliability: 0.8
    source_status: "stable_keep"
    notes: "Invented local notebook; its two entries are not independent sources."
evidence:
  - evidence_id: "example-change-note"
    source_id: "example-source"
    raw_text: "Synthetic notebook, 2024-01-01: a device filter was replaced."
    evidence_type: "maintenance_note"
    extraction_confidence: 0.9
    evidence_specificity: 0.8
    usable_as_trace_evidence: true
    limits:
      - "Synthetic teaching data; temporal order alone does not establish cause."
  - evidence_id: "example-recovery-note"
    source_id: "example-source"
    raw_text: "Synthetic notebook, 2024-01-02: output recovered after both a filter replacement and a routine restart; the notebook does not isolate their effects."
    evidence_type: "maintenance_note"
    extraction_confidence: 0.9
    evidence_specificity: 0.8
    usable_as_trace_evidence: true
    limits:
      - "Same notebook lineage; restart is an unresolved alternative explanation."
events:
  - event_id: "example-filter-change"
    evidence_ids:
      - "example-change-note"
    action: "Filter replaced in the synthetic device."
    time_interval:
      start: "2024-01-01"
      end: "2024-01-01"
      precision: "exact_date"
      confidence: 0.9
    extraction_confidence: 0.9
  - event_id: "example-output-recovery"
    evidence_ids:
      - "example-recovery-note"
    action: "Output recovered after replacement and a routine restart."
    time_interval:
      start: "2024-01-02"
      end: "2024-01-02"
      precision: "exact_date"
      confidence: 0.9
    extraction_confidence: 0.9
traces:
  - trace_id: "example-recovery-trace"
    title: "Synthetic filter-change and recovery sequence"
    event_ids:
      - "example-filter-change"
      - "example-output-recovery"
    claim: "The invented record places replacement before recovery; cause remains contested."
    notes: "Two dated events from one invented source, not independent causal confirmation."
storyline_hypotheses:
  - hypothesis_id: "example-filter-hypothesis"
    claim: "Filter replacement contributed to recovery in this synthetic device."
    trace_ids:
      - "example-recovery-trace"
    event_ids:
      - "example-filter-change"
      - "example-output-recovery"
    causal: true
    mechanism_ids:
      - "example-filter-mechanism"
    confounder_ids:
      - "example-restart-confounder"
  - hypothesis_id: "example-restart-hypothesis"
    claim: "The routine restart can explain the recorded recovery without isolating a filter effect."
    role: "alternative"
    trace_ids:
      - "example-recovery-trace"
    event_ids:
      - "example-output-recovery"
    bounded_non_causal: true
hypothesis_evidence_links:
  - link_id: "example-change-support"
    hypothesis_id: "example-filter-hypothesis"
    evidence_id: "example-change-note"
    polarity: "support"
    rationale: "The note establishes an antecedent intervention, not its isolated effect."
  - link_id: "example-restart-opposition"
    hypothesis_id: "example-filter-hypothesis"
    evidence_id: "example-recovery-note"
    polarity: "oppose"
    rationale: "A simultaneous restart prevents attributing recovery solely to the filter."
  - link_id: "example-alternative-support"
    hypothesis_id: "example-restart-hypothesis"
    evidence_id: "example-recovery-note"
    polarity: "support"
    rationale: "The record explicitly names a restart as an alternative explanation."
hypothesis_relations:
  - relation_id: "example-alternative-relation"
    left_hypothesis_id: "example-filter-hypothesis"
    right_hypothesis_id: "example-restart-hypothesis"
    relation: "alternative"
    evidence_ids:
      - "example-recovery-note"
causal_mechanisms:
  - mechanism_id: "example-filter-mechanism"
    hypothesis_id: "example-filter-hypothesis"
    description: "A clean filter could restore flow; the notebook does not measure this mechanism independently."
    evidence_ids:
      - "example-change-note"
    declared_relevance: 0.5
confounder_reviews:
  - confounder_id: "example-restart-confounder"
    hypothesis_id: "example-filter-hypothesis"
    description: "A concurrent restart could also restore output; no isolated comparison is available."
    status: "unresolved"
    evidence_ids:
      - "example-recovery-note"
causal_scopes:
  - scope_id: "example-device-scope"
    description: "Only the two invented notebook entries for one synthetic device."
    population: "One synthetic device"
    time_window: "2024-01-01 through 2024-01-02"
    boundary_conditions:
      - "No external source verification."
      - "Do not generalize to other devices or claim proven causality."
causal_candidates:
  - causal_id: "example-filter-causal-candidate"
    hypothesis_id: "example-filter-hypothesis"
    cause_event_ids:
      - "example-filter-change"
    effect_event_ids:
      - "example-output-recovery"
    mechanism_ids:
      - "example-filter-mechanism"
    confounder_ids:
      - "example-restart-confounder"
    alternative_hypothesis_ids:
      - "example-restart-hypothesis"
    scope_id: "example-device-scope"
evidence_ablations: []
scenario_perturbations: []
expected_sensitivities: []
```


`metadata.evidence_type_strength` optionally maps evidence type names to finite
strengths in 0..1. Types absent from the declaration use neutral 0.25.
For example: `evidence_type_strength: {paragraph: 0.6, table: 0.8}`.
These are the model author's explicit assumptions, not universal evidence rankings.
Case libraries can declare the same table in `case.yaml` metadata; build-model
preserves it in the generated model.
