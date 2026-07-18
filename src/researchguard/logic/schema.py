"""Shared schema constants for LogicGuard models."""

from __future__ import annotations

# One current durable authority.  Direct YAML/JSON authoring may omit these
# markers, but every ModelStore artifact must declare the exact current value.
SCHEMA_VERSION = "researchguard.logic.model-store.v1"
MODEL_SNAPSHOT_SCHEMA = "researchguard.logic.model-snapshot.v1"
MANIFEST_SCHEMA = "researchguard.logic.model-store-manifest.v2"
JOURNAL_SCHEMA = "researchguard.logic.model-store-journal.v1"
EVALUATION_OVERLAY_SCHEMA = "researchguard.logic.evaluation-overlay.v1"
RECEIPT_SCHEMA = "researchguard.logic.model-store-receipt.v1"

# Product-runtime ModelMesh is additive to, and never an alias for, the P0
# ModelStore schema above.  Every P1 durable artifact declares both its exact
# artifact schema and this one current mesh schema version.
MESH_SCHEMA_VERSION = "researchguard.logic.model-mesh.v1"
MESH_MANIFEST_SCHEMA = "researchguard.logic.model-mesh-manifest.v1"
MESH_SNAPSHOT_SCHEMA = "researchguard.logic.model-mesh-snapshot.v1"
MESH_INDEX_SHARD_SCHEMA = "researchguard.logic.model-mesh-index-shard.v1"
MESH_JOURNAL_SCHEMA = "researchguard.logic.model-mesh-journal.v1"
MESH_RECEIPT_SCHEMA = "researchguard.logic.model-mesh-receipt.v1"
MESH_EVALUATION_OVERLAY_SCHEMA = "researchguard.logic.model-mesh-evaluation-overlay.v1"
MESH_OVERLAY_CATALOG_MANIFEST_SCHEMA = "researchguard.logic.model-mesh-overlay-catalog-manifest.v1"
MESH_OVERLAY_CATALOG_SNAPSHOT_SCHEMA = "researchguard.logic.model-mesh-overlay-catalog-snapshot.v1"
MESH_OVERLAY_DEPENDENCY_SHARD_SCHEMA = "researchguard.logic.model-mesh-overlay-dependency-shard.v1"
MESH_INVALIDATION_RECEIPT_SCHEMA = "researchguard.logic.model-mesh-invalidation-receipt.v1"
MESH_SIMULATION_RECEIPT_SCHEMA = "researchguard.logic.model-mesh-simulation-receipt.v1"
MESH_SCALE_RECEIPT_SCHEMA = "researchguard.logic.model-mesh-scale-receipt.v1"

STATE_IN = "IN"
STATE_OUT = "OUT"
STATE_UNDECIDED = "UNDECIDED"
STATES = {STATE_IN, STATE_OUT, STATE_UNDECIDED}

NODE_TYPES = {
    "Document",
    "Section",
    "ArgumentBlock",
    "Claim",
    "Premise",
    "Evidence",
    "Warrant",
    "Assumption",
    "Rebuttal",
    "Undercutter",
    "Qualifier",
    "Context",
    "Definition",
    "Method",
    "Result",
    "Limitation",
}

EDGE_TYPES = {
    "supports",
    "attacks",
    "undercuts",
    "qualifies",
    "depends_on",
    "refines",
    "contradicts",
    "contextualizes",
    "derives",
    "aggregates",
}

SUPPORT_EDGE_TYPES = {"supports", "depends_on", "refines", "derives", "aggregates"}
ATTACK_EDGE_TYPES = {"attacks", "contradicts"}
UNDERCUT_EDGE_TYPES = {"undercuts"}
SCOPE_EDGE_TYPES = {"qualifies", "contextualizes"}

ACCEPTANCE_KEYS = {
    "all_of",
    "any_of",
    "none_of",
    "at_least_k",
    "requires",
    "requires_not_out",
    "unless",
    "threshold",
    "no_undefeated_rebuttal",
    "scope_match",
    "warrant_required",
    "local_quality_factor",
}

DIAGNOSTIC_SEVERITIES = {"info", "warning", "error", "critical"}
