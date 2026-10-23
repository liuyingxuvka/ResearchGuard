# TraceGuard fields and worked starter

Use this sheet when creating a trace model or a v2 evidence-batch observation. Validate a model with `researchguard trace validate model.yaml`; evaluate its structural support with `researchguard trace evaluate model.yaml`. A successful command does not establish external truth, calibrated probability, or a causal license.

## Model envelope and conventions

`metadata.schema_version` is required and must be `researchguard.trace.model.v2`. Other metadata entries are descriptive. Each list below is optional at the root and defaults to `[]`; meaningful reconstruction needs actual evidence, events and a nonempty trace. References must resolve to IDs in the same model. Empty lists are not evidence of a completed reconstruction.

In the tables, **required** means the row must supply the field. All other cells give the omission default. IDs and narrative text are strings; `*_ids`, `supports`, `limits`, `warnings`, `boundary_conditions` and `downstream_consumers` are lists of strings. Scores named `source_reliability`, `extraction_confidence`, `evidence_specificity`, `importance`, `uncertainty`, `declared_relevance`, and time `confidence` must be in `[0,1]`; they are declarations or extraction provenance, not calibrated probabilities. `minimum_absolute_change` is also in `[0,1]`. Quote ISO dates so YAML keeps strings. Optional fingerprint fields are empty by default; when supplied use `sha256:` followed by a 64-character digest.

## sources

`lineage_id` and `independence_group` must also be nonempty. Shared lineage does not become independent corroboration by using two evidence IDs. `source_status`: `stable_keep`, `need_auth_or_permission`, `invalid_or_empty`, `unknown`. `source_type` is free text here, not the separate SourceGuard type enum.

| Field | Required / omission default |
| --- | --- |
| `source_id` | **required** |
| `title` | `""` |
| `url` | `null` |
| `source_type` | `"other"` |
| `lineage_id` | **required** |
| `independence_group` | **required** |
| `derived_from_source_ids` | `[]` |
| `source_reliability` | `0.5` |
| `source_status` | `"unknown"` |
| `cleaning_category` | `null` |
| `source_date` | `null` |
| `coverage_period` | `null` |
| `fetched_at` | `null` |
| `language` | `null` |
| `country` | `null` |
| `notes` | `null` |
| `object_fingerprint` | `null` |
| `source_revision` | `""` |
| `content_fingerprint` | `null` |
| `locator` | `""` |
| `provider_id` | `""` |
| `provider_revision` | `""` |
| `retrieval_request_fingerprint` | `null` |
| `unconsumed_output_disposition` | `""` |

## evidence

`usable_as_trace_evidence` falls back to `usable_as_project_evidence` when omitted; if both are omitted it is `null`. `supports` and `limits` are narrative strings, not typed hypothesis links. Use the separate links list for polarity. `evidence_type` is free text.

| Field | Required / omission default |
| --- | --- |
| `evidence_id` | **required** |
| `source_id` | **required** |
| `raw_text` | `""` |
| `normalized_summary` | `null` |
| `evidence_type` | `"unknown"` |
| `extraction_confidence` | `0.5` |
| `evidence_specificity` | `0.5` |
| `importance` | `0.5` |
| `locator` | `null` |
| `language` | `null` |
| `observed_at` | `null` |
| `source_date` | `null` |
| `coverage_period` | `null` |
| `supports` | `[]` |
| `limits` | `[]` |
| `warnings` | `[]` |
| `usable_as_trace_evidence` | `usable_as_project_evidence` |
| `usable_as_project_evidence` | `null` |
| `object_fingerprint` | `null` |
| `source_revision` | `""` |
| `content_fingerprint` | `null` |
| `normalizer_id` | `""` |
| `normalizer_revision` | `""` |
| `normalizer_fingerprint` | `null` |
| `extractor_id` | `""` |
| `extractor_revision` | `""` |
| `extractor_fingerprint` | `null` |
| `unconsumed_output_disposition` | `""` |

## events

`evidence_ids` defaults to `[]` but should name the evidence actually grounding the event. `actor_ids`, `object_ids` and `technology_ids` refer to optional root `entities`; `location_ids` refers to optional root `locations`. `trace_hint` falls back to `project_hint`. Old event `confidence` is forbidden: use `extraction_confidence`. Nested `time_interval` is described below.

| Field | Required / omission default |
| --- | --- |
| `event_id` | **required** |
| `evidence_ids` | `[]` |
| `actor_ids` | `[]` |
| `action` | `""` |
| `object_ids` | `[]` |
| `event_type` | `"unknown"` |
| `time_interval` | `null` |
| `location_ids` | `[]` |
| `technology_ids` | `[]` |
| `trace_hint` | `project_hint` |
| `project_hint` | `null` |
| `stage_hint` | `null` |
| `extraction_confidence` | `0.5` |
| `importance` | `0.5` |
| `extraction_notes` | `null` |
| `object_fingerprint` | `null` |
| `extractor_id` | `""` |
| `extractor_revision` | `""` |
| `extractor_fingerprint` | `null` |
| `unresolved_input_disposition` | `""` |
| `unconsumed_output_disposition` | `""` |

## traces

`title` defaults to its `trace_id`. Input `validation_status`, `confidence`, `allowed_wording`, and `unsafe_wording` are forbidden inferred outputs. `trace_type` and `current_stage` are free text.

| Field | Required / omission default |
| --- | --- |
| `trace_id` | **required** |
| `title` | `trace_id` |
| `trace_type` | `"storyline"` |
| `event_ids` | `[]` |
| `entity_ids` | `[]` |
| `location_ids` | `[]` |
| `current_stage` | `"unknown"` |
| `importance` | `0.5` |
| `claim` | `null` |
| `structure_unit_id` | `null` |
| `source_unit_id` | `null` |
| `destination_unit_id` | `null` |
| `trace_layer` | `null` |
| `weakest_link` | `null` |
| `conclusion_transfer_status` | `null` |
| `downstream_consumer` | `null` |
| `notes` | `null` |
| `object_fingerprint` | `null` |
| `normalizer_id` | `""` |
| `normalizer_revision` | `""` |
| `normalizer_fingerprint` | `null` |
| `unresolved_input_disposition` | `""` |
| `unconsumed_output_disposition` | `""` |

## storyline_hypotheses

`role` is free text (for example `primary` or `alternative`). Input `evidence_ids`, `contradicting_evidence_ids`, and `alternative_to` are forbidden: use typed links/relations. Also do not prefill `support`, `score`, `rank`, `status`, `causal_support`, or `causal_status`. `bounded_non_causal: true` declares a bounded noncausal reading; it does not validate the hypothesis.

| Field | Required / omission default |
| --- | --- |
| `hypothesis_id` | **required** |
| `claim` | `""` |
| `role` | `"primary"` |
| `trace_ids` | `[]` |
| `event_ids` | `[]` |
| `mechanism_ids` | `[]` |
| `confounder_ids` | `[]` |
| `importance` | `0.5` |
| `uncertainty` | `0.5` |
| `causal` | `false` |
| `bounded_non_causal` | `false` |
| `alternative_out_of_scope_reason` | `null` |
| `downstream_consumers` | `[]` |
| `bounded_claim_ids` | `[]` |
| `handoff_ids` | `[]` |
| `object_fingerprint` | `null` |
| `normalizer_id` | `""` |
| `normalizer_revision` | `""` |
| `normalizer_fingerprint` | `null` |
| `unresolved_input_disposition` | `""` |
| `unconsumed_output_disposition` | `""` |

## hypothesis_evidence_links

`polarity`: `support`, `oppose`, `limit`; omission defaults to `support`. `declared_relevance` defaults to `1.0`. IDs must name an existing hypothesis and evidence item.

| Field | Required / omission default |
| --- | --- |
| `link_id` | **required** |
| `hypothesis_id` | **required** |
| `evidence_id` | **required** |
| `polarity` | `"support"` |
| `declared_relevance` | `1.0` |
| `rationale` | `null` |
| `unconsumed_output_disposition` | `""` |

## hypothesis_relations

`relation`: `alternative`, `competes_with`, `subsumes`, `compatible_with`; omission defaults to `alternative`. Both hypothesis endpoints and any evidence references must exist.

| Field | Required / omission default |
| --- | --- |
| `relation_id` | **required** |
| `left_hypothesis_id` | **required** |
| `right_hypothesis_id` | **required** |
| `relation` | `"alternative"` |
| `evidence_ids` | `[]` |
| `unconsumed_output_disposition` | `""` |

## causal_mechanisms

`confidence` is forbidden as an inferred output; use `declared_relevance` to declare factor relevance. A proposed mechanism alone does not establish causality.

| Field | Required / omission default |
| --- | --- |
| `mechanism_id` | **required** |
| `hypothesis_id` | **required** |
| `description` | `""` |
| `evidence_ids` | `[]` |
| `declared_relevance` | `0.5` |
| `unconsumed_output_disposition` | `""` |

## confounder_reviews

`status`: `addressed`, `partially_addressed`, `unresolved`, `not_applicable`; default `unresolved`. Keep unresolved alternatives visible.

| Field | Required / omission default |
| --- | --- |
| `confounder_id` | **required** |
| `hypothesis_id` | **required** |
| `description` | `""` |
| `status` | `"unresolved"` |
| `evidence_ids` | `[]` |
| `importance` | `0.5` |
| `unconsumed_output_disposition` | `""` |

## causal_scopes

State the population, time window and boundary conditions over which the candidate is being examined. Empty scope text does not license generalization.

| Field | Required / omission default |
| --- | --- |
| `scope_id` | **required** |
| `description` | `""` |
| `population` | `null` |
| `time_window` | `null` |
| `location_ids` | `[]` |
| `boundary_conditions` | `[]` |
| `unconsumed_output_disposition` | `""` |

## causal_candidates

`cause_event_ids` and `effect_event_ids` default to `[]` but a useful candidate names real cause/effect events. Mechanism, confounder, alternative and scope references must exist. Input `support`, `confidence`, `status`, `causal_support`, and `causal_status` are forbidden inferred outputs.

| Field | Required / omission default |
| --- | --- |
| `causal_id` | **required** |
| `hypothesis_id` | **required** |
| `cause_event_ids` | `[]` |
| `effect_event_ids` | `[]` |
| `mechanism_ids` | `[]` |
| `confounder_ids` | `[]` |
| `alternative_hypothesis_ids` | `[]` |
| `scope_id` | `null` |
| `unconsumed_output_disposition` | `""` |

## evidence_ablations

At least one of `hypothesis_id` or `trace_id` must be nonempty. Removed evidence and event IDs must exist; this declares a stress case, not an already executed result.

| Field | Required / omission default |
| --- | --- |
| `ablation_id` | **required** |
| `hypothesis_id` | `null` |
| `trace_id` | `null` |
| `description` | `""` |
| `remove_evidence_ids` | `[]` |
| `remove_event_ids` | `[]` |
| `importance` | `0.5` |
| `unconsumed_output_disposition` | `""` |

## scenario_perturbations

At least one of `hypothesis_id` or `trace_id` must be nonempty. Added/removed evidence and event IDs must exist in the model.

| Field | Required / omission default |
| --- | --- |
| `perturbation_id` | **required** |
| `hypothesis_id` | `null` |
| `trace_id` | `null` |
| `description` | `""` |
| `remove_evidence_ids` | `[]` |
| `remove_event_ids` | `[]` |
| `add_evidence_ids` | `[]` |
| `add_event_ids` | `[]` |
| `importance` | `0.5` |
| `unconsumed_output_disposition` | `""` |

## expected_sensitivities

`perturbation_id` refers to an evidence ablation or scenario perturbation. `expected_direction`: `increase`, `decrease`, `stable`, `unknown`; default `unknown`. `target_kind` defaults to `hypothesis`; use an existing hypothesis or trace target. The expectation is checked against a real perturbation run, not treated as an observed outcome.

| Field | Required / omission default |
| --- | --- |
| `sensitivity_id` | **required** |
| `perturbation_id` | **required** |
| `target_kind` | `"hypothesis"` |
| `target_id` | **required** |
| `expected_direction` | `"unknown"` |
| `minimum_absolute_change` | `0.0` |
| `rationale` | `null` |
| `unconsumed_output_disposition` | `""` |

## Nested time interval and additional enums

An event's `time_interval` defaults to `null`. If present: `start: null`, `end: null`, `precision: unknown`, `relation_hint: null`, `text: null`, `confidence: 0.0`. `precision` allows exactly `exact_date`, `month`, `quarter`, `year`, `interval`, `relative`, `unknown`. Use quoted dates such as `"2024-01-01"`; missing or uncertain dates should remain visible.

Optional model lists `entities`, `entity_resolutions`, `locations`, and `interface_bindings` also default to `[]`. They are not needed by the starter below. An entity-resolution `relation` allows `same_as`, `possible_same_as`, `different`, `unknown`. A location's `location_role` allows `project_site`, `company_headquarter`, `funding_agency_location`, `tender_authority_location`, `patent_office_country`, `partner_country`, `manufacturing_site`, `deployment_site`, `unknown`. Interface `disposition` allows `consumed`, `unresolved`, `excluded`; receipt status allows `current`, `stale`, `failed`, `not_run`. Do not fabricate a current receipt to fill a model.

Evaluated trace `validation_status` may be `source_only`, `weak_signal`, `candidate`, `validated`, `contradicted`, `insufficient`, `unknown`; evaluated causal status may be `supported`, `contested`, `insufficient`, `not_requested`. These are **outputs**, not values to prefill into trace/hypothesis/causal-candidate inputs.

## Evidence-batch observation v2

This separate observation JSON records a real batch for task-local prediction comparison. It neither retrieves evidence nor licenses factual future prediction. All fifteen serialized fields are shown below; the four new-record lists are optional and omission preserves ID-only observations.

| Field | Required / omission default |
| --- | --- |
| `schema_version` | required: `researchguard.trace.evidence_batch_observation.v2` |
| `observation_id` | required, nonempty |
| `observed_at` | required ISO-8601 timestamp with timezone |
| `quality_status` | required: `valid`, `invalid`, `access_gap` |
| `evidence_ids` | `[]` |
| `event_ids` | `[]` |
| `event_order` | `[]`; only IDs in `event_ids` or `new_events` |
| `contradiction_ids` | `[]` |
| `source_refs` | `[]` |
| `future_holdout_status` | `"not_run"`; descriptive string, not a factual future-prediction license |
| `external_input_ids` | `[]` |
| `new_sources` | `[]`; native `SourceRecord` rows, as in model `sources` |
| `new_evidence` | `[]`; native `EvidenceItem` rows, as in model `evidence` |
| `new_events` | `[]`; native `EventCandidate` rows, as in model `events` |
| `new_links` | `[]`; native `HypothesisEvidenceLink` rows, as in model `hypothesis_evidence_links` |

Each new list contains mappings using the corresponding model-row fields above. Comparison appends them to the baseline in memory and applies native schema and cross-reference validation. Each typed collection rejects an ID already in that baseline collection or repeated among its new rows, even with identical contents. Refer to an existing record by ID instead of submitting it as new. Evidence, event and source IDs must resolve in the combined model; a candidate must also retain the construction observation's four new-record lists unchanged. Older baseline records may be revised and additional links added, subject to native checks.

`event_order` is ordered; other ID collections are deduplicated in input order. Expected evidence/event IDs frozen before observation may be absent from the baseline and supplied later by listed IDs or new rows. The prediction target and coverage IDs must already exist at freeze time. The optional freeze argument `--expected-direction` accepts `weaken`, `strengthen`, or `unchanged`; omission imposes no direction check. `--weakens-when` is an optional remark. Comparison derives direction from canonical target support: below −0.01 is weakening, above +0.01 strengthening, otherwise unchanged. Native `open_depth_gap_ids` are separate from prediction mismatches; an accepted candidate with gaps normally continues iteration and does not claim task closure. See [task-iteration.md](task-iteration.md) for holdout, mismatch, rollback and bounded-stop rules.

A valid quality declaration is not external verification of the contents. This synthetic ID-only example references the worked model below; replace it with actual batch observations.

```json
{
  "schema_version": "researchguard.trace.evidence_batch_observation.v2",
  "observation_id": "example-observation",
  "observed_at": "2024-01-03T12:00:00Z",
  "quality_status": "valid",
  "evidence_ids": ["example-change-note", "example-recovery-note"],
  "event_ids": ["example-filter-change", "example-output-recovery"],
  "event_order": ["example-filter-change", "example-output-recovery"],
  "contradiction_ids": [],
  "source_refs": ["example-source"],
  "future_holdout_status": "not_run",
  "external_input_ids": [],
  "new_sources": [],
  "new_evidence": [],
  "new_events": [],
  "new_links": []
}
```

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
