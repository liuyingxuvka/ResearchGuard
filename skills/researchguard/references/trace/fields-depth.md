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

`perturbation_id` refers to an evidence ablation or scenario perturbation. `expected_direction`: `increase`, `decrease`, `stable`, `unknown`; default `unknown`. `target_kind` defaults to `hypothesis`; use an existing hypothesis or trace id. The expectation is checked against a real perturbation run, not treated as an observed outcome.

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

Optional model lists `entities`, `entity_resolutions`, and `locations` also default to `[]`. They are not needed by the starter below. An entity-resolution `relation` allows `same_as`, `possible_same_as`, `different`, `unknown`. A location's `location_role` allows `project_site`, `company_headquarter`, `funding_agency_location`, `tender_authority_location`, `patent_office_country`, `partner_country`, `manufacturing_site`, `deployment_site`, `unknown`.

Evaluated trace `validation_status` may be `source_only`, `weak_signal`, `candidate`, `validated`, `contradicted`, `insufficient`, `unknown`; evaluated causal status may be `supported`, `contested`, `insufficient`, `not_requested`. These are **outputs**, not values to prefill into trace/hypothesis/causal-candidate inputs.

