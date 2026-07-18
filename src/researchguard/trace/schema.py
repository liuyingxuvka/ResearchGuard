"""TraceGuard data model.

Purpose: Define portable local schema objects for source-backed evidence-to-trace models.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: TraceGuard
Math boundary: Schema only; PSL/HL-MRF-style scoring is implemented in evaluator modules.
CLI: researchguard trace validate <model.yaml>
Boundary: Dataclasses validate structure; they do not establish factual truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SCHEMA_ID = "researchguard.trace.model.v2"
SOURCE_STATUSES = {"stable_keep", "need_auth_or_permission", "invalid_or_empty", "unknown"}
ENTITY_RESOLUTION_RELATIONS = {"same_as", "possible_same_as", "different", "unknown"}
EVIDENCE_POLARITIES = {"support", "oppose", "limit"}
HYPOTHESIS_RELATIONS = {"alternative", "competes_with", "subsumes", "compatible_with"}
CAUSAL_STATUSES = {"supported", "contested", "insufficient", "not_requested"}
CONFOUNDER_STATUSES = {"addressed", "partially_addressed", "unresolved", "not_applicable"}
PERTURBATION_DIRECTIONS = {"increase", "decrease", "stable", "unknown"}
TIME_PRECISIONS = {"exact_date", "month", "quarter", "year", "interval", "relative", "unknown"}
LOCATION_ROLES = {
    "project_site",
    "company_headquarter",
    "funding_agency_location",
    "tender_authority_location",
    "patent_office_country",
    "partner_country",
    "manufacturing_site",
    "deployment_site",
    "unknown",
}
VALIDATION_STATUSES = {
    "source_only",
    "weak_signal",
    "candidate",
    "validated",
    "contradicted",
    "insufficient",
    "unknown",
}


class SchemaError(ValueError):
    """Raised when a TraceGuard model violates local schema constraints."""


def clamp01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def require01(value: Any, field_name: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise SchemaError(f"{field_name} must be a number in [0, 1]") from exc
    if numeric < 0 or numeric > 1:
        raise SchemaError(f"{field_name} must be in [0, 1], got {numeric}")
    return numeric


def list_of_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SchemaError("expected a list of strings")
    return value


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    title: str
    url: str | None = None
    source_type: str = "other"
    lineage_id: str = ""
    independence_group: str = ""
    derived_from_source_ids: list[str] = field(default_factory=list)
    source_reliability: float = 0.5
    source_status: str = "unknown"
    cleaning_category: str | None = None
    source_date: str | None = None
    coverage_period: str | None = None
    fetched_at: str | None = None
    language: str | None = None
    country: str | None = None
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceRecord":
        if data.get("source_status", "unknown") not in SOURCE_STATUSES:
            raise SchemaError(f"invalid source_status for {data.get('source_id')}")
        if not data.get("lineage_id"):
            raise SchemaError(f"source {data.get('source_id')} requires lineage_id")
        if not data.get("independence_group"):
            raise SchemaError(
                f"source {data.get('source_id')} requires independence_group"
            )
        return cls(
            source_id=str(data["source_id"]),
            title=str(data.get("title", "")),
            url=data.get("url"),
            source_type=str(data.get("source_type", "other")),
            lineage_id=str(data["lineage_id"]),
            independence_group=str(data["independence_group"]),
            derived_from_source_ids=list_of_strings(
                data.get("derived_from_source_ids", [])
            ),
            source_reliability=require01(data.get("source_reliability", 0.5), "source_reliability"),
            source_status=str(data.get("source_status", "unknown")),
            cleaning_category=data.get("cleaning_category"),
            source_date=data.get("source_date"),
            coverage_period=data.get("coverage_period"),
            fetched_at=data.get("fetched_at"),
            language=data.get("language"),
            country=data.get("country"),
            notes=data.get("notes"),
        )


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    source_id: str
    raw_text: str
    normalized_summary: str | None = None
    evidence_type: str = "unknown"
    extraction_confidence: float = 0.5
    evidence_specificity: float = 0.5
    locator: str | None = None
    language: str | None = None
    observed_at: str | None = None
    source_date: str | None = None
    coverage_period: str | None = None
    supports: list[str] = field(default_factory=list)
    limits: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    usable_as_trace_evidence: bool | None = None
    usable_as_project_evidence: bool | None = None
    importance: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvidenceItem":
        return cls(
            evidence_id=str(data["evidence_id"]),
            source_id=str(data["source_id"]),
            raw_text=str(data.get("raw_text", "")),
            normalized_summary=data.get("normalized_summary"),
            evidence_type=str(data.get("evidence_type", "unknown")),
            extraction_confidence=require01(data.get("extraction_confidence", 0.5), "extraction_confidence"),
            evidence_specificity=require01(data.get("evidence_specificity", 0.5), "evidence_specificity"),
            importance=require01(data.get("importance", 0.5), "evidence.importance"),
            locator=data.get("locator"),
            language=data.get("language"),
            observed_at=data.get("observed_at"),
            source_date=data.get("source_date"),
            coverage_period=data.get("coverage_period"),
            supports=list_of_strings(data.get("supports", [])),
            limits=list_of_strings(data.get("limits", [])),
            warnings=list_of_strings(data.get("warnings", [])),
            usable_as_trace_evidence=data.get("usable_as_trace_evidence", data.get("usable_as_project_evidence")),
            usable_as_project_evidence=data.get("usable_as_project_evidence"),
        )


@dataclass(frozen=True)
class EntityMention:
    mention_id: str
    evidence_id: str | None
    raw_name: str
    normalized_name: str
    entity_type: str = "unknown"
    aliases: list[str] = field(default_factory=list)
    country: str | None = None
    role: str | None = None
    confidence: float = 0.5
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntityMention":
        return cls(
            mention_id=str(data["mention_id"]),
            evidence_id=data.get("evidence_id"),
            raw_name=str(data.get("raw_name", "")),
            normalized_name=str(data.get("normalized_name", data.get("raw_name", ""))).lower(),
            entity_type=str(data.get("entity_type", "unknown")),
            aliases=list_of_strings(data.get("aliases", [])),
            country=data.get("country"),
            role=data.get("role"),
            confidence=require01(data.get("confidence", 0.5), "entity.confidence"),
            notes=data.get("notes"),
        )


@dataclass(frozen=True)
class EntityResolution:
    left_id: str
    right_id: str
    relation: str
    score: float
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntityResolution":
        relation = str(data.get("relation", "unknown"))
        if relation not in ENTITY_RESOLUTION_RELATIONS:
            raise SchemaError(f"invalid entity resolution relation {relation}")
        return cls(
            left_id=str(data["left_id"]),
            right_id=str(data["right_id"]),
            relation=relation,
            score=require01(data.get("score", 0.0), "entity_resolution.score"),
            reasons=list_of_strings(data.get("reasons", [])),
            blockers=list_of_strings(data.get("blockers", [])),
        )


@dataclass(frozen=True)
class TimeInterval:
    start: str | None = None
    end: str | None = None
    precision: str = "unknown"
    relation_hint: str | None = None
    text: str | None = None
    confidence: float = 0.0

    @classmethod
    def from_any(cls, data: dict[str, Any] | None) -> "TimeInterval | None":
        if data is None:
            return None
        precision = str(data.get("precision", "unknown"))
        if precision not in TIME_PRECISIONS:
            raise SchemaError(f"invalid time precision {precision}")
        return cls(
            start=data.get("start"),
            end=data.get("end"),
            precision=precision,
            relation_hint=data.get("relation_hint"),
            text=data.get("text"),
            confidence=require01(data.get("confidence", 0.0), "time.confidence"),
        )


@dataclass(frozen=True)
class LocationMention:
    location_id: str
    raw_text: str
    normalized_name: str
    country: str | None = None
    region: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_role: str = "unknown"
    geocoding_precision: str | None = None
    confidence: float = 0.5
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LocationMention":
        role = str(data.get("location_role", "unknown"))
        if role not in LOCATION_ROLES:
            raise SchemaError(f"invalid location_role {role}")
        return cls(
            location_id=str(data["location_id"]),
            raw_text=str(data.get("raw_text", "")),
            normalized_name=str(data.get("normalized_name", data.get("raw_text", ""))).lower(),
            country=data.get("country"),
            region=data.get("region"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            location_role=role,
            geocoding_precision=data.get("geocoding_precision"),
            confidence=require01(data.get("confidence", 0.5), "location.confidence"),
            notes=data.get("notes"),
        )


@dataclass(frozen=True)
class EventCandidate:
    event_id: str
    evidence_ids: list[str]
    actor_ids: list[str] = field(default_factory=list)
    action: str = ""
    object_ids: list[str] = field(default_factory=list)
    event_type: str = "unknown"
    time_interval: TimeInterval | None = None
    location_ids: list[str] = field(default_factory=list)
    technology_ids: list[str] = field(default_factory=list)
    trace_hint: str | None = None
    project_hint: str | None = None
    stage_hint: str | None = None
    extraction_confidence: float = 0.5
    extraction_notes: str | None = None
    importance: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventCandidate":
        if "confidence" in data:
            raise SchemaError(
                "event confidence is retired in schema v2; use "
                "event.extraction_confidence for extraction provenance"
            )
        return cls(
            event_id=str(data["event_id"]),
            evidence_ids=list_of_strings(data.get("evidence_ids", [])),
            actor_ids=list_of_strings(data.get("actor_ids", [])),
            action=str(data.get("action", "")),
            object_ids=list_of_strings(data.get("object_ids", [])),
            event_type=str(data.get("event_type", "unknown")),
            time_interval=TimeInterval.from_any(data.get("time_interval")),
            location_ids=list_of_strings(data.get("location_ids", [])),
            technology_ids=list_of_strings(data.get("technology_ids", [])),
            trace_hint=data.get("trace_hint", data.get("project_hint")),
            project_hint=data.get("project_hint"),
            stage_hint=data.get("stage_hint"),
            extraction_confidence=require01(
                data.get("extraction_confidence", 0.5),
                "event.extraction_confidence",
            ),
            importance=require01(data.get("importance", 0.5), "event.importance"),
            extraction_notes=data.get("extraction_notes"),
        )


@dataclass(frozen=True)
class TraceCandidate:
    trace_id: str
    title: str
    trace_type: str = "storyline"
    event_ids: list[str] = field(default_factory=list)
    entity_ids: list[str] = field(default_factory=list)
    location_ids: list[str] = field(default_factory=list)
    current_stage: str = "unknown"
    claim: str | None = None
    structure_unit_id: str | None = None
    source_unit_id: str | None = None
    destination_unit_id: str | None = None
    trace_layer: str | None = None
    weakest_link: str | None = None
    conclusion_transfer_status: str | None = None
    downstream_consumer: str | None = None
    notes: str | None = None
    importance: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TraceCandidate":
        forbidden = {
            "validation_status",
            "confidence",
            "allowed_wording",
            "unsafe_wording",
        } & set(data)
        if forbidden:
            raise SchemaError(
                "trace inference outputs are forbidden in schema v2 input: "
                + ", ".join(sorted(forbidden))
            )
        return cls(
            trace_id=str(data["trace_id"]),
            title=str(data.get("title", data["trace_id"])),
            trace_type=str(data.get("trace_type", "storyline")),
            event_ids=list_of_strings(data.get("event_ids", [])),
            entity_ids=list_of_strings(data.get("entity_ids", [])),
            location_ids=list_of_strings(data.get("location_ids", [])),
            current_stage=str(data.get("current_stage", "unknown")),
            importance=require01(data.get("importance", 0.5), "trace.importance"),
            claim=data.get("claim"),
            structure_unit_id=data.get("structure_unit_id"),
            source_unit_id=data.get("source_unit_id"),
            destination_unit_id=data.get("destination_unit_id"),
            trace_layer=data.get("trace_layer"),
            weakest_link=data.get("weakest_link"),
            conclusion_transfer_status=data.get("conclusion_transfer_status"),
            downstream_consumer=data.get("downstream_consumer"),
            notes=data.get("notes"),
        )


@dataclass(frozen=True)
class StorylineHypothesis:
    hypothesis_id: str
    claim: str
    role: str = "primary"
    trace_ids: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    contradicting_evidence_ids: list[str] = field(default_factory=list)
    alternative_to: list[str] = field(default_factory=list)
    mechanism_ids: list[str] = field(default_factory=list)
    confounder_ids: list[str] = field(default_factory=list)
    importance: float = 0.5
    uncertainty: float = 0.5
    causal: bool = False
    bounded_non_causal: bool = False
    alternative_out_of_scope_reason: str | None = None
    downstream_consumers: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StorylineHypothesis":
        forbidden = {
            "evidence_ids",
            "contradicting_evidence_ids",
            "alternative_to",
            "support",
            "score",
            "rank",
            "status",
            "causal_support",
            "causal_status",
        } & set(data)
        if forbidden:
            raise SchemaError(
                "schema v2 requires typed hypothesis_evidence_links and "
                "hypothesis_relations instead of "
                + ", ".join(sorted(forbidden))
            )
        return cls(
            hypothesis_id=str(data["hypothesis_id"]),
            claim=str(data.get("claim", "")),
            role=str(data.get("role", "primary")),
            trace_ids=list_of_strings(data.get("trace_ids", [])),
            event_ids=list_of_strings(data.get("event_ids", [])),
            evidence_ids=[],
            contradicting_evidence_ids=[],
            alternative_to=[],
            mechanism_ids=list_of_strings(data.get("mechanism_ids", [])),
            confounder_ids=list_of_strings(data.get("confounder_ids", [])),
            importance=require01(data.get("importance", 0.5), "hypothesis.importance"),
            uncertainty=require01(data.get("uncertainty", 0.5), "hypothesis.uncertainty"),
            causal=bool(data.get("causal", False)),
            bounded_non_causal=bool(data.get("bounded_non_causal", False)),
            alternative_out_of_scope_reason=data.get("alternative_out_of_scope_reason"),
            downstream_consumers=list_of_strings(data.get("downstream_consumers", [])),
        )


@dataclass(frozen=True)
class CausalMechanism:
    mechanism_id: str
    hypothesis_id: str
    description: str
    evidence_ids: list[str] = field(default_factory=list)
    declared_relevance: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CausalMechanism":
        if "confidence" in data:
            raise SchemaError(
                "mechanism confidence is an inferred output; use declared_relevance "
                "only to declare factor relevance"
            )
        return cls(
            mechanism_id=str(data["mechanism_id"]),
            hypothesis_id=str(data["hypothesis_id"]),
            description=str(data.get("description", "")),
            evidence_ids=list_of_strings(data.get("evidence_ids", [])),
            declared_relevance=require01(
                data.get("declared_relevance", 0.5),
                "mechanism.declared_relevance",
            ),
        )


@dataclass(frozen=True)
class ConfounderReview:
    confounder_id: str
    hypothesis_id: str
    description: str
    status: str = "unresolved"
    evidence_ids: list[str] = field(default_factory=list)
    importance: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConfounderReview":
        status = str(data.get("status", "unresolved"))
        if status not in CONFOUNDER_STATUSES:
            raise SchemaError(f"invalid confounder status {status}")
        return cls(
            confounder_id=str(data["confounder_id"]),
            hypothesis_id=str(data["hypothesis_id"]),
            description=str(data.get("description", "")),
            status=status,
            evidence_ids=list_of_strings(data.get("evidence_ids", [])),
            importance=require01(data.get("importance", 0.5), "confounder.importance"),
        )


@dataclass(frozen=True)
class HypothesisEvidenceLink:
    link_id: str
    hypothesis_id: str
    evidence_id: str
    polarity: str
    declared_relevance: float = 1.0
    rationale: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HypothesisEvidenceLink":
        polarity = str(data.get("polarity", "support"))
        if polarity not in EVIDENCE_POLARITIES:
            raise SchemaError(f"invalid hypothesis evidence polarity {polarity}")
        return cls(
            link_id=str(data["link_id"]),
            hypothesis_id=str(data["hypothesis_id"]),
            evidence_id=str(data["evidence_id"]),
            polarity=polarity,
            declared_relevance=require01(
                data.get("declared_relevance", 1.0),
                "hypothesis_evidence_link.declared_relevance",
            ),
            rationale=data.get("rationale"),
        )


@dataclass(frozen=True)
class HypothesisRelation:
    relation_id: str
    left_hypothesis_id: str
    right_hypothesis_id: str
    relation: str
    evidence_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HypothesisRelation":
        relation = str(data.get("relation", "alternative"))
        if relation not in HYPOTHESIS_RELATIONS:
            raise SchemaError(f"invalid hypothesis relation {relation}")
        return cls(
            relation_id=str(data["relation_id"]),
            left_hypothesis_id=str(data["left_hypothesis_id"]),
            right_hypothesis_id=str(data["right_hypothesis_id"]),
            relation=relation,
            evidence_ids=list_of_strings(data.get("evidence_ids", [])),
        )


@dataclass(frozen=True)
class CausalScope:
    scope_id: str
    description: str
    population: str | None = None
    time_window: str | None = None
    location_ids: list[str] = field(default_factory=list)
    boundary_conditions: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CausalScope":
        return cls(
            scope_id=str(data["scope_id"]),
            description=str(data.get("description", "")),
            population=data.get("population"),
            time_window=data.get("time_window"),
            location_ids=list_of_strings(data.get("location_ids", [])),
            boundary_conditions=list_of_strings(
                data.get("boundary_conditions", [])
            ),
        )


@dataclass(frozen=True)
class CausalCandidate:
    causal_id: str
    hypothesis_id: str
    cause_event_ids: list[str]
    effect_event_ids: list[str]
    mechanism_ids: list[str] = field(default_factory=list)
    confounder_ids: list[str] = field(default_factory=list)
    alternative_hypothesis_ids: list[str] = field(default_factory=list)
    scope_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CausalCandidate":
        forbidden = {
            "support",
            "confidence",
            "status",
            "causal_support",
            "causal_status",
        } & set(data)
        if forbidden:
            raise SchemaError(
                "causal inference outputs are forbidden in schema v2 input: "
                + ", ".join(sorted(forbidden))
            )
        return cls(
            causal_id=str(data["causal_id"]),
            hypothesis_id=str(data["hypothesis_id"]),
            cause_event_ids=list_of_strings(data.get("cause_event_ids", [])),
            effect_event_ids=list_of_strings(data.get("effect_event_ids", [])),
            mechanism_ids=list_of_strings(data.get("mechanism_ids", [])),
            confounder_ids=list_of_strings(data.get("confounder_ids", [])),
            alternative_hypothesis_ids=list_of_strings(
                data.get("alternative_hypothesis_ids", [])
            ),
            scope_id=data.get("scope_id"),
        )


@dataclass(frozen=True)
class EvidenceAblation:
    ablation_id: str
    hypothesis_id: str | None
    trace_id: str | None
    description: str
    remove_evidence_ids: list[str] = field(default_factory=list)
    remove_event_ids: list[str] = field(default_factory=list)
    importance: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvidenceAblation":
        hypothesis_id = data.get("hypothesis_id")
        trace_id = data.get("trace_id")
        if not hypothesis_id and not trace_id:
            raise SchemaError("evidence ablation requires hypothesis_id or trace_id")
        return cls(
            ablation_id=str(data["ablation_id"]),
            hypothesis_id=None if hypothesis_id is None else str(hypothesis_id),
            trace_id=None if trace_id is None else str(trace_id),
            description=str(data.get("description", "")),
            remove_evidence_ids=list_of_strings(data.get("remove_evidence_ids", [])),
            remove_event_ids=list_of_strings(data.get("remove_event_ids", [])),
            importance=require01(data.get("importance", 0.5), "ablation.importance"),
        )


@dataclass(frozen=True)
class ScenarioPerturbation:
    perturbation_id: str
    hypothesis_id: str | None
    trace_id: str | None
    description: str
    remove_evidence_ids: list[str] = field(default_factory=list)
    remove_event_ids: list[str] = field(default_factory=list)
    add_evidence_ids: list[str] = field(default_factory=list)
    add_event_ids: list[str] = field(default_factory=list)
    importance: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScenarioPerturbation":
        hypothesis_id = data.get("hypothesis_id")
        trace_id = data.get("trace_id")
        if not hypothesis_id and not trace_id:
            raise SchemaError(
                "scenario perturbation requires hypothesis_id or trace_id"
            )
        return cls(
            perturbation_id=str(data["perturbation_id"]),
            hypothesis_id=None if hypothesis_id is None else str(hypothesis_id),
            trace_id=None if trace_id is None else str(trace_id),
            description=str(data.get("description", "")),
            remove_evidence_ids=list_of_strings(data.get("remove_evidence_ids", [])),
            remove_event_ids=list_of_strings(data.get("remove_event_ids", [])),
            add_evidence_ids=list_of_strings(data.get("add_evidence_ids", [])),
            add_event_ids=list_of_strings(data.get("add_event_ids", [])),
            importance=require01(
                data.get("importance", 0.5),
                "scenario_perturbation.importance",
            ),
        )


@dataclass(frozen=True)
class ExpectedSensitivity:
    sensitivity_id: str
    perturbation_id: str
    target_kind: str
    target_id: str
    expected_direction: str
    minimum_absolute_change: float = 0.0
    rationale: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExpectedSensitivity":
        direction = str(data.get("expected_direction", "unknown"))
        if direction not in PERTURBATION_DIRECTIONS:
            raise SchemaError(f"invalid expected sensitivity direction {direction}")
        minimum_change = require01(
            data.get("minimum_absolute_change", 0.0),
            "expected_sensitivity.minimum_absolute_change",
        )
        return cls(
            sensitivity_id=str(data["sensitivity_id"]),
            perturbation_id=str(data["perturbation_id"]),
            target_kind=str(data.get("target_kind", "hypothesis")),
            target_id=str(data["target_id"]),
            expected_direction=direction,
            minimum_absolute_change=minimum_change,
            rationale=data.get("rationale"),
        )


@dataclass(frozen=True)
class TraceGuardModel:
    metadata: dict[str, Any]
    sources: tuple[SourceRecord, ...] = ()
    evidence: tuple[EvidenceItem, ...] = ()
    entities: tuple[EntityMention, ...] = ()
    entity_resolutions: tuple[EntityResolution, ...] = ()
    locations: tuple[LocationMention, ...] = ()
    events: tuple[EventCandidate, ...] = ()
    traces: tuple[TraceCandidate, ...] = ()
    storyline_hypotheses: tuple[StorylineHypothesis, ...] = ()
    hypothesis_evidence_links: tuple[HypothesisEvidenceLink, ...] = ()
    hypothesis_relations: tuple[HypothesisRelation, ...] = ()
    causal_mechanisms: tuple[CausalMechanism, ...] = ()
    confounder_reviews: tuple[ConfounderReview, ...] = ()
    causal_scopes: tuple[CausalScope, ...] = ()
    causal_candidates: tuple[CausalCandidate, ...] = ()
    evidence_ablations: tuple[EvidenceAblation, ...] = ()
    scenario_perturbations: tuple[ScenarioPerturbation, ...] = ()
    expected_sensitivities: tuple[ExpectedSensitivity, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TraceGuardModel":
        if not isinstance(data, dict):
            raise SchemaError("model root must be a mapping")
        metadata = dict(data.get("metadata", {}))
        if metadata.get("schema_version") != SCHEMA_ID:
            raise SchemaError(
                f"metadata.schema_version must equal {SCHEMA_ID}; "
                "legacy schema readers are not available"
            )
        allowed_roots = {
            "metadata",
            "sources",
            "evidence",
            "entities",
            "entity_resolutions",
            "locations",
            "events",
            "traces",
            "storyline_hypotheses",
            "hypothesis_evidence_links",
            "hypothesis_relations",
            "causal_mechanisms",
            "confounder_reviews",
            "causal_scopes",
            "causal_candidates",
            "evidence_ablations",
            "scenario_perturbations",
            "expected_sensitivities",
        }
        retired = {
            "predicates",
            "storyline_interventions",
            "counterfactual_outcomes",
        } & set(data)
        if retired:
            raise SchemaError(
                "retired schema fields are forbidden: " + ", ".join(sorted(retired))
            )
        unknown = set(data) - allowed_roots
        if unknown:
            raise SchemaError(
                "unknown schema-v2 root fields are forbidden: "
                + ", ".join(sorted(unknown))
            )
        hypotheses = tuple(
            StorylineHypothesis.from_dict(item)
            for item in data.get("storyline_hypotheses", [])
        )
        links = tuple(
            HypothesisEvidenceLink.from_dict(item)
            for item in data.get("hypothesis_evidence_links", [])
        )
        relations = tuple(
            HypothesisRelation.from_dict(item)
            for item in data.get("hypothesis_relations", [])
        )
        support_by_hypothesis: dict[str, list[str]] = {}
        opposition_by_hypothesis: dict[str, list[str]] = {}
        alternatives_by_hypothesis: dict[str, list[str]] = {}
        for link in links:
            target = (
                support_by_hypothesis
                if link.polarity == "support"
                else opposition_by_hypothesis
            )
            target.setdefault(link.hypothesis_id, []).append(link.evidence_id)
        for relation in relations:
            if relation.relation in {"alternative", "competes_with"}:
                alternatives_by_hypothesis.setdefault(
                    relation.left_hypothesis_id, []
                ).append(relation.right_hypothesis_id)
                alternatives_by_hypothesis.setdefault(
                    relation.right_hypothesis_id, []
                ).append(relation.left_hypothesis_id)
        hypotheses = tuple(
            cls._bind_hypothesis_derivations(
                hypothesis,
                support_by_hypothesis.get(hypothesis.hypothesis_id, []),
                opposition_by_hypothesis.get(hypothesis.hypothesis_id, []),
                alternatives_by_hypothesis.get(hypothesis.hypothesis_id, []),
            )
            for hypothesis in hypotheses
        )
        return cls(
            metadata=metadata,
            sources=tuple(SourceRecord.from_dict(item) for item in data.get("sources", [])),
            evidence=tuple(EvidenceItem.from_dict(item) for item in data.get("evidence", [])),
            entities=tuple(EntityMention.from_dict(item) for item in data.get("entities", [])),
            entity_resolutions=tuple(EntityResolution.from_dict(item) for item in data.get("entity_resolutions", [])),
            locations=tuple(LocationMention.from_dict(item) for item in data.get("locations", [])),
            events=tuple(EventCandidate.from_dict(item) for item in data.get("events", [])),
            traces=tuple(TraceCandidate.from_dict(item) for item in data.get("traces", [])),
            storyline_hypotheses=hypotheses,
            hypothesis_evidence_links=links,
            hypothesis_relations=relations,
            causal_mechanisms=tuple(
                CausalMechanism.from_dict(item)
                for item in data.get("causal_mechanisms", [])
            ),
            confounder_reviews=tuple(
                ConfounderReview.from_dict(item)
                for item in data.get("confounder_reviews", [])
            ),
            causal_scopes=tuple(
                CausalScope.from_dict(item)
                for item in data.get("causal_scopes", [])
            ),
            causal_candidates=tuple(
                CausalCandidate.from_dict(item)
                for item in data.get("causal_candidates", [])
            ),
            evidence_ablations=tuple(
                EvidenceAblation.from_dict(item)
                for item in data.get("evidence_ablations", [])
            ),
            scenario_perturbations=tuple(
                ScenarioPerturbation.from_dict(item)
                for item in data.get("scenario_perturbations", [])
            ),
            expected_sensitivities=tuple(
                ExpectedSensitivity.from_dict(item)
                for item in data.get("expected_sensitivities", [])
            ),
        )

    @staticmethod
    def _bind_hypothesis_derivations(
        hypothesis: StorylineHypothesis,
        evidence_ids: list[str],
        contradicting_evidence_ids: list[str],
        alternative_to: list[str],
    ) -> StorylineHypothesis:
        from dataclasses import replace

        return replace(
            hypothesis,
            evidence_ids=sorted(set(evidence_ids)),
            contradicting_evidence_ids=sorted(set(contradicting_evidence_ids)),
            alternative_to=sorted(set(alternative_to)),
        )

    def source_by_id(self) -> dict[str, SourceRecord]:
        return {item.source_id: item for item in self.sources}

    def evidence_by_id(self) -> dict[str, EvidenceItem]:
        return {item.evidence_id: item for item in self.evidence}

    def event_by_id(self) -> dict[str, EventCandidate]:
        return {item.event_id: item for item in self.events}

    def location_by_id(self) -> dict[str, LocationMention]:
        return {item.location_id: item for item in self.locations}

    def entity_by_id(self) -> dict[str, EntityMention]:
        return {item.mention_id: item for item in self.entities}
