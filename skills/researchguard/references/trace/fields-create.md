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

