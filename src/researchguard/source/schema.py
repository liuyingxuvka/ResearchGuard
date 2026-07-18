"""
Purpose: Define SourceGuard belief-state, source, anchor, gap, action, observation, and planning schemas.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source validate <model.yaml> --model-contract <model.contract.json>
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


class SchemaError(ValueError):
    """Raised when a SourceGuard model violates the declared schema."""


SOURCEGUARD_MODEL_CONTRACT_SCHEMA_VERSION = "researchguard.source.model_guard_contract.v2"

# This is a catalog of SourceGuard-native observations, not a list of failures
# that every target model must claim to prevent.  A target-authored failure id
# maps to exactly one of these capabilities and supplies its own good/bad case.
SOURCEGUARD_NATIVE_ORACLE_CATALOG: dict[str, dict[str, str]] = {
    "oracle:sourceguard:source-qualification": {
        "mutation_id": "make-all-anchors-unusable",
        "finding_code": "sourceguard_blocked:unqualified-candidate-promotion",
    },
    "oracle:sourceguard:direct-primary": {
        "mutation_id": "remove-direct-source",
        "finding_code": "sourceguard_blocked:missing-direct-primary",
    },
    "oracle:sourceguard:independent": {
        "mutation_id": "remove-independent-source",
        "finding_code": "sourceguard_blocked:missing-independent-source",
    },
    "oracle:sourceguard:counter-limiting": {
        "mutation_id": "remove-limiting-source",
        "finding_code": "sourceguard_blocked:missing-counter-limiting",
    },
    "oracle:sourceguard:lineage-independence": {
        "mutation_id": "collapse-source-lineages",
        "finding_code": "sourceguard_blocked:false-lineage-independence",
    },
    "oracle:sourceguard:content-anchor": {
        "mutation_id": "remove-anchor-content",
        "finding_code": "sourceguard_blocked:contentless-anchor",
    },
    "oracle:sourceguard:target-unit-reconciliation": {
        "mutation_id": "shrink-target-unit-inventory",
        "finding_code": "sourceguard_blocked:target-unit-universe-shrink",
    },
}
SOURCEGUARD_NATIVE_ORACLE_CATALOG_FINGERPRINT = hashlib.sha256(
    json.dumps(
        SOURCEGUARD_NATIVE_ORACLE_CATALOG,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest().upper()


SOURCE_TYPES = {
    "web_page",
    "paper",
    "book",
    "pdf_report",
    "report",
    "video",
    "audio",
    "image",
    "dataset",
    "database_record",
    "government_record",
    "procurement_record",
    "patent",
    "map",
    "local_file",
    "internal_document",
    "interview",
    "social_post",
    "unknown",
}

SOURCE_STATUSES = {
    "candidate",
    "saved",
    "rejected",
    "duplicate",
    "inaccessible",
    "permission_gated",
    "promoted_traceguard",
    "promoted_logicguard",
    "unknown",
}

SOURCE_ROLES = {
    "primary_source",
    "official_claim",
    "independent_report",
    "limiting_evidence",
    "counter_evidence",
    "expert_analysis",
    "method_source",
    "validation_evidence",
    "bridge_evidence",
    "historical_background",
    "hypothesis_source",
    "visual_evidence",
    "audio_evidence",
    "context_only",
    "unknown",
}

SOURCE_DEPTH_CLAIM_SCOPES = {"bounded", "broad"}
SOURCE_PORTFOLIO_CLASSES = {"direct_or_primary", "independent", "counter_or_limiting"}
SOURCE_DEPTH_NATIVE_POLICY_ORIGIN = "sourceguard-native-depth-v2"

ACCESS_STATUSES = {"public", "local", "internal", "permission_gated", "unavailable", "unknown"}

ANCHOR_TYPES = {
    "paragraph",
    "page",
    "section",
    "table",
    "figure",
    "image",
    "image_region",
    "video_segment",
    "audio_segment",
    "transcript_segment",
    "citation",
    "footnote",
    "index_entry",
    "map_location",
    "dataset_row",
    "metadata",
    "unknown",
}

MODALITIES = {
    "text",
    "pdf_page",
    "book_page",
    "image",
    "video",
    "audio",
    "table",
    "chart",
    "map",
    "mixed",
    "unknown",
}

LEAD_STATUSES = {
    "open",
    "supported_incomplete",
    "candidate",
    "contradicted",
    "access_gap",
    "closed",
    "downgraded",
    "unknown",
}

GAP_TYPES = {
    "missing_primary_source",
    "missing_independent_source",
    "missing_date",
    "missing_location",
    "missing_execution_evidence",
    "weak_signal_only",
    "one_sided_support",
    "contradiction",
    "permission_gap",
    "stale_source",
    "duplicate_source_cluster",
    "missing_counterevidence",
    "missing_visual_anchor",
    "missing_audio_anchor",
    "missing_book_page",
    "missing_pdf_page",
    "missing_baseline",
    "missing_structural_source_support",
    "missing_bridge_evidence",
    "missing_numeric_provenance",
    "missing_conclusion_recovery_source",
    "unclear_entity",
    "unclear_scope",
    "unknown",
}

SEMANTIC_GAP_STATES = {
    "discovered",
    "observed",
    "qualified",
    "claim_usable",
    "contradicted",
    "blocked",
    "closed",
}

ACTION_TYPES = {
    "text_search",
    "exact_phrase_search",
    "entity_expand",
    "citation_backward",
    "citation_forward",
    "source_domain_search",
    "image_search",
    "reverse_image_search",
    "video_search",
    "audio_transcript_search",
    "book_index_search",
    "report_page_search",
    "pdf_page_search",
    "local_file_search",
    "internal_source_search",
    "map_location_search",
    "counterevidence_search",
    "primary_source_search",
    "followup_from_anchor",
    "unknown",
}

ACTION_STATUSES = {"proposed", "selected", "executed", "blocked", "completed", "rejected", "unknown"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clamp01(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return float(default)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return float(default)
    if numeric < 0.0:
        return 0.0
    if numeric > 1.0:
        return 1.0
    return numeric


def require_mapping(value: Any, label: str = "model root") -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaError(f"{label} must be a mapping")
    return value


def require_choice(value: Any, allowed: set[str], field_name: str, default: str = "unknown") -> str:
    if value is None or value == "":
        value = default
    if not isinstance(value, str):
        raise SchemaError(f"{field_name} must be a string")
    if value not in allowed:
        raise SchemaError(f"{field_name} has invalid value {value!r}")
    return value


def as_string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return bool(value)


def list_of_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        raise SchemaError("expected a list of strings")
    return [str(item) for item in value]


def list_of_mappings(value: Any, field_name: str) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SchemaError(f"{field_name} must be a list")
    return [require_mapping(item, field_name) for item in value]


def to_plain(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_plain(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): to_plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [to_plain(item) for item in value]
    if isinstance(value, list):
        return [to_plain(item) for item in value]
    return value


@dataclass
class SourceRecord:
    source_id: str
    title: str = ""
    source_type: str = "unknown"
    url: str = ""
    source_status: str = "candidate"
    source_reliability: float = 0.0
    source_role: str = "unknown"
    lineage_id: str = ""
    source_date: str = ""
    coverage_period: str = ""
    language: str = ""
    country: str = ""
    access_status: str = "unknown"
    can_support_structural_use: str = ""
    cannot_support_structural_use: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceRecord":
        data = require_mapping(data, "source")
        source_id = as_string(data.get("source_id"))
        if not source_id:
            raise SchemaError("source.source_id is required")
        return cls(
            source_id=source_id,
            title=as_string(data.get("title")),
            source_type=require_choice(data.get("source_type"), SOURCE_TYPES, "source.source_type"),
            url=as_string(data.get("url")),
            source_status=require_choice(
                data.get("source_status", "candidate"), SOURCE_STATUSES, "source.source_status", "candidate"
            ),
            source_reliability=clamp01(data.get("source_reliability"), 0.0),
            source_role=require_choice(data.get("source_role"), SOURCE_ROLES, "source.source_role"),
            lineage_id=as_string(data.get("lineage_id")),
            source_date=as_string(data.get("source_date")),
            coverage_period=as_string(data.get("coverage_period")),
            language=as_string(data.get("language")),
            country=as_string(data.get("country")),
            access_status=require_choice(data.get("access_status"), ACCESS_STATUSES, "source.access_status"),
            can_support_structural_use=as_string(data.get("can_support_structural_use")),
            cannot_support_structural_use=as_string(data.get("cannot_support_structural_use")),
            notes=as_string(data.get("notes")),
        )


@dataclass
class EvidenceAnchor:
    anchor_id: str
    source_id: str
    anchor_type: str = "unknown"
    locator: str = ""
    text: str = ""
    normalized_summary: str = ""
    modality: str = "unknown"
    observed_at: str = ""
    extraction_confidence: float = 0.0
    specificity: float = 0.0
    supports: list[str] = field(default_factory=list)
    limits: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    usable_for_trace: bool = False
    usable_for_claim: bool = False
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EvidenceAnchor":
        data = require_mapping(data, "anchor")
        anchor_id = as_string(data.get("anchor_id"))
        source_id = as_string(data.get("source_id"))
        if not anchor_id:
            raise SchemaError("anchor.anchor_id is required")
        if not source_id:
            raise SchemaError("anchor.source_id is required")
        return cls(
            anchor_id=anchor_id,
            source_id=source_id,
            anchor_type=require_choice(data.get("anchor_type"), ANCHOR_TYPES, "anchor.anchor_type"),
            locator=as_string(data.get("locator")),
            text=as_string(data.get("text")),
            normalized_summary=as_string(data.get("normalized_summary")),
            modality=require_choice(data.get("modality"), MODALITIES, "anchor.modality"),
            observed_at=as_string(data.get("observed_at")),
            extraction_confidence=clamp01(data.get("extraction_confidence"), 0.0),
            specificity=clamp01(data.get("specificity"), 0.0),
            supports=list_of_strings(data.get("supports")),
            limits=list_of_strings(data.get("limits")),
            warnings=list_of_strings(data.get("warnings")),
            usable_for_trace=as_bool(data.get("usable_for_trace"), False),
            usable_for_claim=as_bool(data.get("usable_for_claim"), False),
            notes=as_string(data.get("notes")),
        )


@dataclass
class Lead:
    lead_id: str
    question: str = ""
    hypothesis: str = ""
    importance: float = 0.5
    status: str = "open"
    related_entities: list[str] = field(default_factory=list)
    related_sources: list[str] = field(default_factory=list)
    related_anchors: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Lead":
        data = require_mapping(data, "lead")
        lead_id = as_string(data.get("lead_id"))
        if not lead_id:
            raise SchemaError("lead.lead_id is required")
        return cls(
            lead_id=lead_id,
            question=as_string(data.get("question")),
            hypothesis=as_string(data.get("hypothesis")),
            importance=clamp01(data.get("importance"), 0.5),
            status=require_choice(data.get("status", "open"), LEAD_STATUSES, "lead.status", "open"),
            related_entities=list_of_strings(data.get("related_entities")),
            related_sources=list_of_strings(data.get("related_sources")),
            related_anchors=list_of_strings(data.get("related_anchors")),
            gaps=list_of_strings(data.get("gaps")),
            notes=as_string(data.get("notes")),
        )


@dataclass
class GapQualification:
    anchor_id: str = ""
    source_id: str = ""
    observation_id: str = ""
    locator_present: bool = False
    source_accessible: bool = False
    source_reliability: float = 0.0
    extraction_confidence: float = 0.0
    specificity: float = 0.0
    supports_gap: bool = False
    role_match: bool = False
    modality_match: bool = False
    target_match: bool = False
    usable_for_claim: bool = False
    decision: str = "not_evaluated"
    reasons: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "GapQualification":
        data = require_mapping(data or {}, "gap.qualification")
        return cls(
            anchor_id=as_string(data.get("anchor_id")),
            source_id=as_string(data.get("source_id")),
            observation_id=as_string(data.get("observation_id")),
            locator_present=as_bool(data.get("locator_present"), False),
            source_accessible=as_bool(data.get("source_accessible"), False),
            source_reliability=clamp01(data.get("source_reliability"), 0.0),
            extraction_confidence=clamp01(data.get("extraction_confidence"), 0.0),
            specificity=clamp01(data.get("specificity"), 0.0),
            supports_gap=as_bool(data.get("supports_gap"), False),
            role_match=as_bool(data.get("role_match"), False),
            modality_match=as_bool(data.get("modality_match"), False),
            target_match=as_bool(data.get("target_match"), False),
            usable_for_claim=as_bool(data.get("usable_for_claim"), False),
            decision=as_string(data.get("decision"), "not_evaluated"),
            reasons=list_of_strings(data.get("reasons")),
        )


@dataclass
class GapClosureBasis:
    anchor_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    observation_ids: list[str] = field(default_factory=list)
    thresholds: dict[str, float] = field(default_factory=dict)
    target_match: str = ""
    claim_use_decision: str = ""
    qualified: bool = False

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "GapClosureBasis":
        data = require_mapping(data or {}, "gap.closure_basis")
        raw_thresholds = data.get("thresholds") or {}
        if not isinstance(raw_thresholds, Mapping):
            raise SchemaError("gap.closure_basis.thresholds must be a mapping")
        return cls(
            anchor_ids=list_of_strings(data.get("anchor_ids")),
            source_ids=list_of_strings(data.get("source_ids")),
            observation_ids=list_of_strings(data.get("observation_ids")),
            thresholds={str(key): clamp01(value, 0.0) for key, value in raw_thresholds.items()},
            target_match=as_string(data.get("target_match")),
            claim_use_decision=as_string(data.get("claim_use_decision")),
            qualified=as_bool(data.get("qualified"), False),
        )

    def is_complete(self) -> bool:
        required_thresholds = {"source_reliability", "extraction_confidence", "specificity"}
        return bool(
            self.qualified
            and self.anchor_ids
            and self.source_ids
            and self.observation_ids
            and required_thresholds <= set(self.thresholds)
            and self.target_match
            and self.claim_use_decision
        )


@dataclass
class Gap:
    gap_id: str
    lead_id: str = ""
    gap_type: str = "unknown"
    description: str = ""
    importance: float = 0.5
    blocking: bool = False
    suggested_source_roles: list[str] = field(default_factory=list)
    suggested_modalities: list[str] = field(default_factory=list)
    structure_unit_id: str = ""
    parent_goal: str = ""
    unit_job: str = ""
    contribution_type: str = ""
    downstream_consumer: str = ""
    structural_role_needed: str = ""
    can_support_structural_use: str = ""
    cannot_support_structural_use: str = ""
    allowed_wording: str = ""
    unsafe_wording: str = ""
    semantic_state: str = "discovered"
    qualification: GapQualification = field(default_factory=GapQualification)
    closure_basis: GapClosureBasis = field(default_factory=GapClosureBasis)
    review_required: bool = False
    requires_claim_usability: bool = True
    notes: str = ""

    def __post_init__(self) -> None:
        if self.semantic_state == "closed" and not self.closure_basis.is_complete():
            raise SchemaError(
                "gap.semantic_state=closed requires a complete current closure_basis"
            )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Gap":
        data = require_mapping(data, "gap")
        gap_id = as_string(data.get("gap_id"))
        if not gap_id:
            raise SchemaError("gap.gap_id is required")
        roles = list_of_strings(data.get("suggested_source_roles"))
        invalid_roles = [role for role in roles if role not in SOURCE_ROLES]
        if invalid_roles:
            raise SchemaError(f"gap.suggested_source_roles has invalid values {invalid_roles!r}")
        modalities = list_of_strings(data.get("suggested_modalities"))
        invalid_modalities = [modality for modality in modalities if modality not in MODALITIES]
        if invalid_modalities:
            raise SchemaError(f"gap.suggested_modalities has invalid values {invalid_modalities!r}")
        if "status" in data:
            raise SchemaError(
                "gap.status is retired; migrate the record directly to semantic_state"
            )
        if "semantic_state" not in data:
            raise SchemaError("gap.semantic_state is required")
        semantic_state = require_choice(
            data.get("semantic_state"),
            SEMANTIC_GAP_STATES,
            "gap.semantic_state",
        )
        qualification = GapQualification.from_dict(data.get("qualification"))
        closure_basis = GapClosureBasis.from_dict(data.get("closure_basis"))
        review_required = as_bool(data.get("review_required"), False)
        notes = as_string(data.get("notes"))
        if semantic_state == "closed" and not closure_basis.is_complete():
            raise SchemaError(
                "gap.semantic_state=closed requires a complete current closure_basis"
            )
        return cls(
            gap_id=gap_id,
            lead_id=as_string(data.get("lead_id")),
            gap_type=require_choice(data.get("gap_type"), GAP_TYPES, "gap.gap_type"),
            description=as_string(data.get("description")),
            importance=clamp01(data.get("importance"), 0.5),
            blocking=as_bool(data.get("blocking"), False),
            suggested_source_roles=roles,
            suggested_modalities=modalities,
            structure_unit_id=as_string(data.get("structure_unit_id")),
            parent_goal=as_string(data.get("parent_goal")),
            unit_job=as_string(data.get("unit_job")),
            contribution_type=as_string(data.get("contribution_type")),
            downstream_consumer=as_string(data.get("downstream_consumer")),
            structural_role_needed=as_string(data.get("structural_role_needed")),
            can_support_structural_use=as_string(data.get("can_support_structural_use")),
            cannot_support_structural_use=as_string(data.get("cannot_support_structural_use")),
            allowed_wording=as_string(data.get("allowed_wording")),
            unsafe_wording=as_string(data.get("unsafe_wording")),
            semantic_state=semantic_state,
            qualification=qualification,
            closure_basis=closure_basis,
            review_required=review_required,
            requires_claim_usability=as_bool(data.get("requires_claim_usability"), True),
            notes=notes,
        )


@dataclass
class SearchAction:
    action_id: str
    action_type: str = "unknown"
    query: str = ""
    target_lead_id: str = ""
    target_gap_id: str = ""
    expected_source_role: str = "unknown"
    expected_modality: str = "unknown"
    source_policy: str = "public_only"
    cost: float = 0.3
    permission_risk: float = 0.0
    status: str = "proposed"
    parameters: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SearchAction":
        data = require_mapping(data, "action")
        action_id = as_string(data.get("action_id"))
        if not action_id:
            raise SchemaError("action.action_id is required")
        parameters = data.get("parameters") or {}
        if not isinstance(parameters, Mapping):
            raise SchemaError("action.parameters must be a mapping")
        return cls(
            action_id=action_id,
            action_type=require_choice(data.get("action_type"), ACTION_TYPES, "action.action_type"),
            query=as_string(data.get("query")),
            target_lead_id=as_string(data.get("target_lead_id")),
            target_gap_id=as_string(data.get("target_gap_id")),
            expected_source_role=require_choice(
                data.get("expected_source_role"), SOURCE_ROLES, "action.expected_source_role"
            ),
            expected_modality=require_choice(data.get("expected_modality"), MODALITIES, "action.expected_modality"),
            source_policy=as_string(data.get("source_policy"), "public_only"),
            cost=clamp01(data.get("cost"), 0.3),
            permission_risk=clamp01(data.get("permission_risk"), 0.0),
            status=require_choice(data.get("status", "proposed"), ACTION_STATUSES, "action.status", "proposed"),
            parameters=dict(parameters),
            notes=as_string(data.get("notes")),
        )


@dataclass
class Observation:
    observation_id: str
    action_id: str = ""
    observed_sources: list[SourceRecord] = field(default_factory=list)
    observed_anchors: list[EvidenceAnchor] = field(default_factory=list)
    new_entities: list[str] = field(default_factory=list)
    new_leads: list[Lead] = field(default_factory=list)
    new_gaps: list[Gap] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Observation":
        data = require_mapping(data, "observation")
        observation_id = as_string(data.get("observation_id"))
        if not observation_id:
            raise SchemaError("observation.observation_id is required")
        return cls(
            observation_id=observation_id,
            action_id=as_string(data.get("action_id")),
            observed_sources=[SourceRecord.from_dict(item) for item in list_of_mappings(data.get("observed_sources"), "observation.observed_sources")],
            observed_anchors=[EvidenceAnchor.from_dict(item) for item in list_of_mappings(data.get("observed_anchors"), "observation.observed_anchors")],
            new_entities=list_of_strings(data.get("new_entities")),
            new_leads=[Lead.from_dict(item) for item in list_of_mappings(data.get("new_leads"), "observation.new_leads")],
            new_gaps=[Gap.from_dict(item) for item in list_of_mappings(data.get("new_gaps"), "observation.new_gaps")],
            contradictions=list_of_strings(data.get("contradictions")),
            notes=as_string(data.get("notes")),
        )


@dataclass
class SourceDepthPolicy:
    requested_claim_scope: str = "bounded"
    important_threshold: float = 0.6
    required_portfolio_classes: list[str] = field(default_factory=list)
    required_source_roles: list[str] = field(default_factory=list)
    minimum_independent_lineages: int = 2
    target_unit_inventory_ids: list[str] = field(default_factory=list)
    required_target_unit_ids: list[str] = field(default_factory=list)
    excluded_target_unit_ids: list[str] = field(default_factory=list)
    target_unit_exclusion_reasons: dict[str, str] = field(default_factory=dict)
    require_explicit_lineage: bool = True
    require_anchor_content: bool = True
    per_gap_portfolio_required: bool = True
    coverage_floors: dict[str, float] = field(default_factory=dict)
    policy_origin: str = SOURCE_DEPTH_NATIVE_POLICY_ORIGIN

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "SourceDepthPolicy":
        data = require_mapping(data or {}, "depth_policy")
        requested_scope = require_choice(
            data.get("requested_claim_scope", "bounded"),
            SOURCE_DEPTH_CLAIM_SCOPES,
            "depth_policy.requested_claim_scope",
            "bounded",
        )
        classes = list_of_strings(data.get("required_portfolio_classes"))
        invalid_classes = sorted(set(classes) - SOURCE_PORTFOLIO_CLASSES)
        if invalid_classes:
            raise SchemaError(f"depth_policy.required_portfolio_classes has invalid values {invalid_classes!r}")
        roles = list_of_strings(data.get("required_source_roles"))
        invalid_roles = sorted(set(roles) - SOURCE_ROLES)
        if invalid_roles:
            raise SchemaError(f"depth_policy.required_source_roles has invalid values {invalid_roles!r}")
        raw_floors = data.get("coverage_floors") or {}
        if not isinstance(raw_floors, Mapping):
            raise SchemaError("depth_policy.coverage_floors must be a mapping")
        try:
            minimum_lineages = int(data.get("minimum_independent_lineages", 2))
        except (TypeError, ValueError) as exc:
            raise SchemaError("depth_policy.minimum_independent_lineages must be an integer") from exc
        if minimum_lineages < 1:
            raise SchemaError("depth_policy.minimum_independent_lineages must be at least 1")
        raw_exclusion_reasons = data.get("target_unit_exclusion_reasons") or {}
        if not isinstance(raw_exclusion_reasons, Mapping):
            raise SchemaError("depth_policy.target_unit_exclusion_reasons must be a mapping")
        exclusion_reasons = {
            str(key).strip(): (value.strip() if isinstance(value, str) else "")
            for key, value in raw_exclusion_reasons.items()
            if str(key).strip()
        }
        return cls(
            requested_claim_scope=requested_scope,
            important_threshold=min(clamp01(data.get("important_threshold"), 0.6), 0.6),
            required_portfolio_classes=classes,
            required_source_roles=roles,
            minimum_independent_lineages=max(2, minimum_lineages),
            target_unit_inventory_ids=list_of_strings(data.get("target_unit_inventory_ids")),
            required_target_unit_ids=list_of_strings(data.get("required_target_unit_ids")),
            excluded_target_unit_ids=list_of_strings(data.get("excluded_target_unit_ids")),
            target_unit_exclusion_reasons=exclusion_reasons,
            require_explicit_lineage=as_bool(data.get("require_explicit_lineage"), True),
            require_anchor_content=as_bool(data.get("require_anchor_content"), True),
            per_gap_portfolio_required=as_bool(data.get("per_gap_portfolio_required"), True),
            coverage_floors={str(key): clamp01(value, 1.0) for key, value in raw_floors.items()},
            policy_origin=SOURCE_DEPTH_NATIVE_POLICY_ORIGIN,
        )


@dataclass
class SourceCoverageDimension:
    dimension_id: str
    universe_ids: list[str] = field(default_factory=list)
    critical_ids: list[str] = field(default_factory=list)
    selected_ids: list[str] = field(default_factory=list)
    qualified_ids: list[str] = field(default_factory=list)
    covered_ids: list[str] = field(default_factory=list)
    available_count: int = 0
    eligible_count: int = 0
    selected_count: int = 0
    qualified_count: int = 0
    closed_count: int = 0
    coverage_ratio: float = 0.0
    coverage_floor: float = 1.0
    floor_origin: str = SOURCE_DEPTH_NATIVE_POLICY_ORIGIN
    critical_uncovered_ids: list[str] = field(default_factory=list)
    status: str = "fail"
    findings: list[str] = field(default_factory=list)


@dataclass
class SourceObjectDepthRow:
    gap_id: str
    target_unit_id: str = ""
    required_portfolio_classes: list[str] = field(default_factory=list)
    covered_portfolio_classes: list[str] = field(default_factory=list)
    selected_source_ids: list[str] = field(default_factory=list)
    qualified_source_ids: list[str] = field(default_factory=list)
    anchor_ids: list[str] = field(default_factory=list)
    explicit_lineage_ids: list[str] = field(default_factory=list)
    required_lineage_count: int = 0
    obligation_evidence: list[dict[str, Any]] = field(default_factory=list)
    status: str = "fail"
    findings: list[str] = field(default_factory=list)


@dataclass
class SourceCoverageUniverse:
    owner_id: str = "researchguard.source.semantic-gap-depth"
    policy_origin: str = SOURCE_DEPTH_NATIVE_POLICY_ORIGIN
    requested_claim_scope: str = "bounded"
    covered_claim_scope: str = "planning_only"
    universe_fingerprint: str = ""
    declared_target_unit_ids: list[str] = field(default_factory=list)
    discovered_target_unit_ids: list[str] = field(default_factory=list)
    required_target_unit_ids: list[str] = field(default_factory=list)
    excluded_target_unit_ids: list[str] = field(default_factory=list)
    target_unit_exclusion_reasons: dict[str, str] = field(default_factory=dict)
    target_unit_reconciliation_status: str = "not_run"
    dimensions: list[SourceCoverageDimension] = field(default_factory=list)
    object_depth_rows: list[SourceObjectDepthRow] = field(default_factory=list)
    critical_uncovered_ids: list[str] = field(default_factory=list)
    adequacy_status: str = "not_run"
    findings: list[str] = field(default_factory=list)


@dataclass
class SourceGuardProofCase:
    case_id: str
    observation_path: str
    expected_native_status: str
    mutation_id: str = ""
    expected_native_finding: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], field_name: str) -> "SourceGuardProofCase":
        data = require_mapping(data, field_name)
        allowed = {
            "case_id",
            "observation_path",
            "expected_native_status",
            "mutation_id",
            "expected_native_finding",
        }
        unknown = sorted(set(data).difference(allowed))
        if unknown:
            raise SchemaError(f"{field_name} contains unknown fields {unknown!r}")
        return cls(
            case_id=as_string(data.get("case_id")),
            observation_path=as_string(data.get("observation_path")),
            expected_native_status=as_string(data.get("expected_native_status")),
            mutation_id=as_string(data.get("mutation_id")),
            expected_native_finding=as_string(data.get("expected_native_finding")),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "case_id": self.case_id,
            "observation_path": self.observation_path,
            "expected_native_status": self.expected_native_status,
            "mutation_id": self.mutation_id,
            "expected_native_finding": self.expected_native_finding,
        }


@dataclass
class SourceGuardPreventedFailure:
    failure_id: str
    title: str
    block_when: str
    oracle_id: str
    known_good: SourceGuardProofCase
    known_bad: SourceGuardProofCase

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceGuardPreventedFailure":
        data = require_mapping(data, "guard_contract.prevented_failures")
        allowed = {"failure_id", "title", "block_when", "oracle_id", "known_good", "known_bad"}
        unknown = sorted(set(data).difference(allowed))
        if unknown:
            raise SchemaError(
                f"guard_contract.prevented_failures contains unknown fields {unknown!r}"
            )
        return cls(
            failure_id=as_string(data.get("failure_id")),
            title=as_string(data.get("title")),
            block_when=as_string(data.get("block_when")),
            oracle_id=as_string(data.get("oracle_id")),
            known_good=SourceGuardProofCase.from_dict(
                data.get("known_good") or {},
                "guard_contract.prevented_failures.known_good",
            ),
            known_bad=SourceGuardProofCase.from_dict(
                data.get("known_bad") or {},
                "guard_contract.prevented_failures.known_bad",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_id": self.failure_id,
            "title": self.title,
            "block_when": self.block_when,
            "oracle_id": self.oracle_id,
            "known_good": self.known_good.to_dict(),
            "known_bad": self.known_bad.to_dict(),
        }


@dataclass
class SourceGuardModelContract:
    model_id: str
    purpose: str
    prevented_failures: list[SourceGuardPreventedFailure]
    external_universe: dict[str, list[str]]
    claim_boundary: str
    native_oracle_catalog_fingerprint: str = SOURCEGUARD_NATIVE_ORACLE_CATALOG_FINGERPRINT
    purpose_frozen: bool = True
    purpose_freeze_sequence: int = 1
    candidate_construction_sequence: int = 2
    schema_version: str = SOURCEGUARD_MODEL_CONTRACT_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "SourceGuardModelContract":
        if data is None:
            raise SchemaError("guard_contract is required before candidate construction")
        data = require_mapping(data, "guard_contract")
        allowed = {
            "schema_version",
            "model_id",
            "purpose",
            "prevented_failures",
            "external_universe",
            "claim_boundary",
            "native_oracle_catalog_fingerprint",
            "purpose_frozen",
            "purpose_freeze_sequence",
            "candidate_construction_sequence",
        }
        unknown = sorted(set(data).difference(allowed))
        if unknown:
            raise SchemaError(f"guard_contract contains unknown fields {unknown!r}")
        external = require_mapping(data.get("external_universe") or {}, "guard_contract.external_universe")
        external_allowed = {"gap_ids", "target_unit_ids"}
        external_unknown = sorted(set(external).difference(external_allowed))
        if external_unknown:
            raise SchemaError(
                f"guard_contract.external_universe contains unknown fields {external_unknown!r}"
            )
        return cls(
            schema_version=as_string(data.get("schema_version")),
            model_id=as_string(data.get("model_id")),
            purpose=as_string(data.get("purpose")),
            prevented_failures=[
                SourceGuardPreventedFailure.from_dict(item)
                for item in list_of_mappings(
                    data.get("prevented_failures"),
                    "guard_contract.prevented_failures",
                )
            ],
            external_universe={
                "gap_ids": list_of_strings(external.get("gap_ids")),
                "target_unit_ids": list_of_strings(external.get("target_unit_ids")),
            },
            claim_boundary=as_string(data.get("claim_boundary")),
            native_oracle_catalog_fingerprint=as_string(
                data.get("native_oracle_catalog_fingerprint")
            ),
            purpose_frozen=as_bool(data.get("purpose_frozen"), False),
            purpose_freeze_sequence=int(data.get("purpose_freeze_sequence", 0)),
            candidate_construction_sequence=int(data.get("candidate_construction_sequence", 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "purpose": self.purpose,
            "prevented_failures": [item.to_dict() for item in self.prevented_failures],
            "external_universe": {
                "gap_ids": list(self.external_universe.get("gap_ids", [])),
                "target_unit_ids": list(self.external_universe.get("target_unit_ids", [])),
            },
            "claim_boundary": self.claim_boundary,
            "native_oracle_catalog_fingerprint": self.native_oracle_catalog_fingerprint,
            "purpose_frozen": self.purpose_frozen,
            "purpose_freeze_sequence": self.purpose_freeze_sequence,
            "candidate_construction_sequence": self.candidate_construction_sequence,
        }


@dataclass
class BeliefState:
    guard_contract: SourceGuardModelContract | None = None
    candidate_contract_fingerprint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    leads: list[Lead] = field(default_factory=list)
    sources: list[SourceRecord] = field(default_factory=list)
    anchors: list[EvidenceAnchor] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    actions: list[SearchAction] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    graph_edges: list[dict[str, Any]] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    depth_policy: SourceDepthPolicy = field(default_factory=SourceDepthPolicy)
    generated_at: str = field(default_factory=utc_now)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BeliefState":
        data = require_mapping(data, "model root")
        metadata = data.get("metadata") or {}
        if not isinstance(metadata, Mapping):
            raise SchemaError("metadata must be a mapping")
        weights = data.get("weights") or {}
        if not isinstance(weights, Mapping):
            raise SchemaError("weights must be a mapping")
        graph_edges = data.get("graph_edges") or []
        if not isinstance(graph_edges, list):
            raise SchemaError("graph_edges must be a list")
        state = cls(
            guard_contract=SourceGuardModelContract.from_dict(data.get("guard_contract")),
            candidate_contract_fingerprint=as_string(data.get("candidate_contract_fingerprint")),
            metadata=dict(metadata),
            leads=[Lead.from_dict(item) for item in list_of_mappings(data.get("leads"), "leads")],
            sources=[SourceRecord.from_dict(item) for item in list_of_mappings(data.get("sources"), "sources")],
            anchors=[EvidenceAnchor.from_dict(item) for item in list_of_mappings(data.get("anchors"), "anchors")],
            gaps=[Gap.from_dict(item) for item in list_of_mappings(data.get("gaps"), "gaps")],
            actions=[SearchAction.from_dict(item) for item in list_of_mappings(data.get("actions"), "actions")],
            observations=[Observation.from_dict(item) for item in list_of_mappings(data.get("observations"), "observations")],
            graph_edges=[dict(require_mapping(item, "graph_edge")) for item in graph_edges],
            weights={str(key): float(value) for key, value in weights.items()},
            depth_policy=SourceDepthPolicy.from_dict(data.get("depth_policy")),
            generated_at=as_string(data.get("generated_at"), utc_now()),
        )
        validate_model_guard_binding(state)
        return state

    def source_by_id(self) -> dict[str, SourceRecord]:
        return {source.source_id: source for source in self.sources}

    def gap_by_id(self) -> dict[str, Gap]:
        return {gap.gap_id: gap for gap in self.gaps}

    def lead_by_id(self) -> dict[str, Lead]:
        return {lead.lead_id: lead for lead in self.leads}

    def action_by_id(self) -> dict[str, SearchAction]:
        return {action.action_id: action for action in self.actions}


def sourceguard_model_contract_fingerprint(contract: SourceGuardModelContract) -> str:
    payload = json.dumps(
        contract.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def build_sourceguard_model_contract(
    *,
    model_id: str,
    purpose: str,
    prevented_failures: list[SourceGuardPreventedFailure],
    gap_ids: list[str],
    target_unit_ids: list[str],
    claim_boundary: str,
    purpose_freeze_sequence: int = 1,
    candidate_construction_sequence: int = 2,
) -> SourceGuardModelContract:
    return SourceGuardModelContract(
        model_id=model_id,
        purpose=purpose,
        prevented_failures=list(prevented_failures),
        external_universe={
            "gap_ids": sorted(set(gap_ids)),
            "target_unit_ids": sorted(set(target_unit_ids)),
        },
        claim_boundary=claim_boundary,
        purpose_frozen=True,
        purpose_freeze_sequence=purpose_freeze_sequence,
        candidate_construction_sequence=candidate_construction_sequence,
    )


def bind_sourceguard_model_contract(
    state: BeliefState,
    *,
    contract: SourceGuardModelContract,
) -> BeliefState:
    state.guard_contract = contract
    state.candidate_contract_fingerprint = sourceguard_model_contract_fingerprint(contract)
    validate_model_guard_binding(state)
    return state


def validate_model_guard_binding(state: BeliefState) -> None:
    contract = state.guard_contract
    if contract is None:
        raise SchemaError("guard_contract is required before SourceGuard model execution")
    if contract.schema_version != SOURCEGUARD_MODEL_CONTRACT_SCHEMA_VERSION:
        raise SchemaError("guard_contract.schema_version is not current")
    if not contract.model_id or not contract.purpose or not contract.claim_boundary:
        raise SchemaError("guard_contract model_id, purpose, and claim_boundary are required")
    if (
        contract.native_oracle_catalog_fingerprint
        != SOURCEGUARD_NATIVE_ORACLE_CATALOG_FINGERPRINT
    ):
        raise SchemaError("guard_contract native oracle catalog fingerprint is stale or foreign")
    if not contract.prevented_failures:
        raise SchemaError("guard_contract requires one or more prevented failures")
    failure_ids: set[str] = set()
    case_ids: set[str] = set()
    for failure in contract.prevented_failures:
        if not failure.failure_id or failure.failure_id in failure_ids:
            raise SchemaError("guard_contract prevented failure ids must be non-empty and unique")
        failure_ids.add(failure.failure_id)
        if not failure.title or not failure.block_when:
            raise SchemaError(f"guard_contract prevented failure is incomplete: {failure.failure_id}")
        oracle = SOURCEGUARD_NATIVE_ORACLE_CATALOG.get(failure.oracle_id)
        if oracle is None:
            raise SchemaError(f"guard_contract maps an unsupported native oracle: {failure.oracle_id}")
        good = failure.known_good
        bad = failure.known_bad
        if any(not case.case_id or case.case_id in case_ids for case in (good, bad)):
            raise SchemaError("guard_contract proof case ids must be non-empty and unique")
        case_ids.update((good.case_id, bad.case_id))
        if not good.observation_path or good.expected_native_status != "pass":
            raise SchemaError(f"guard_contract known-good is incomplete: {failure.failure_id}")
        if good.mutation_id or good.expected_native_finding:
            raise SchemaError("guard_contract known-good cannot carry a bad-case mutation or finding")
        if (
            not bad.observation_path
            or bad.expected_native_status != "blocked"
            or bad.mutation_id != oracle["mutation_id"]
            or not bad.expected_native_finding
        ):
            raise SchemaError(f"guard_contract known-bad is incomplete or unmapped: {failure.failure_id}")
    if not contract.purpose_frozen:
        raise SchemaError("guard_contract purpose must be frozen before candidate construction")
    if contract.purpose_freeze_sequence < 1 or (
        contract.candidate_construction_sequence <= contract.purpose_freeze_sequence
    ):
        raise SchemaError("candidate construction must occur after the frozen purpose contract")
    declared_gaps = contract.external_universe.get("gap_ids", [])
    actual_gaps = sorted({gap.gap_id for gap in state.gaps})
    if declared_gaps != actual_gaps:
        raise SchemaError("guard_contract gap universe does not match the candidate model")
    declared_units = contract.external_universe.get("target_unit_ids", [])
    actual_units = sorted({gap.structure_unit_id for gap in state.gaps if gap.structure_unit_id})
    if declared_units != actual_units:
        raise SchemaError("guard_contract target-unit universe does not match the candidate model")
    expected_fingerprint = sourceguard_model_contract_fingerprint(contract)
    if state.candidate_contract_fingerprint != expected_fingerprint:
        raise SchemaError("candidate_contract_fingerprint does not match the frozen guard_contract")


@dataclass
class ScoredAction:
    action_id: str
    total_score: float
    gap_closure_value: float
    information_gain: float
    counterevidence_value: float
    new_lead_value: float
    source_independence_value: float
    multimodal_anchor_value: float
    freshness_value: float
    source_authority_value: float
    search_cost: float
    redundancy_penalty: float
    permission_risk: float
    reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "total_score",
            "gap_closure_value",
            "information_gain",
            "counterevidence_value",
            "new_lead_value",
            "source_independence_value",
            "multimodal_anchor_value",
            "freshness_value",
            "source_authority_value",
            "search_cost",
            "redundancy_penalty",
            "permission_risk",
        ):
            setattr(self, field_name, clamp01(getattr(self, field_name), 0.0))


@dataclass
class PlanResult:
    ok: bool
    selected_actions: list[SearchAction] = field(default_factory=list)
    scored_actions: list[ScoredAction] = field(default_factory=list)
    open_gaps: list[Gap] = field(default_factory=list)
    blocked_gaps: list[Gap] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_step_summary: str = ""
    boundary: str = (
        "SourceGuard ranks search-action value under an approximate POMDP-style belief model; "
        "scores are not truth, evidence validity, or final claim confidence."
    )


@dataclass
class GapTransition:
    gap_id: str
    before_semantic_state: str
    after_semantic_state: str
    observation_ids: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class ReplanComparison:
    before_action_ids: list[str] = field(default_factory=list)
    after_action_ids: list[str] = field(default_factory=list)
    added_action_ids: list[str] = field(default_factory=list)
    removed_action_ids: list[str] = field(default_factory=list)
    reprioritized_actions: list[dict[str, Any]] = field(default_factory=list)
    before_open_gap_ids: list[str] = field(default_factory=list)
    after_open_gap_ids: list[str] = field(default_factory=list)
    remaining_gap_ids: list[str] = field(default_factory=list)


@dataclass
class SourceDepthReceipt:
    receipt_version: str
    model_fingerprint: str
    result_model_fingerprint: str
    provider_status: str
    observation_status: str
    planning_depth_completed: bool
    observation_depth_completed: bool
    observations_used: list[str] = field(default_factory=list)
    gap_transitions: list[GapTransition] = field(default_factory=list)
    qualifications: list[GapQualification] = field(default_factory=list)
    closure_bases: dict[str, GapClosureBasis] = field(default_factory=dict)
    replan_comparison: ReplanComparison = field(default_factory=ReplanComparison)
    unresolved_gap_ids: list[str] = field(default_factory=list)
    coverage_universe: SourceCoverageUniverse = field(default_factory=SourceCoverageUniverse)
    requested_claim_scope: str = "bounded"
    covered_claim_scope: str = "planning_only"
    adequacy_status: str = "not_run"
    critical_uncovered_ids: list[str] = field(default_factory=list)
    native_obligation_evidence: list[dict[str, Any]] = field(default_factory=list)
    broad_claim_licensed: bool = False
    status: str = "planning_only"
    claim_boundary: str = (
        "This receipt proves only native SourceGuard planning and supplied-observation processing. "
        "It does not prove source truth, extraction authenticity, validated events, or final argument support."
    )
