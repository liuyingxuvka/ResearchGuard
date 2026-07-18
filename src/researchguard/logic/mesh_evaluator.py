"""Cross-model SCC coordinator over independent P0 LogicGuard models."""

from __future__ import annotations

import hashlib
import inspect
from collections import defaultdict
from typing import Any, Iterable, Mapping

from .evaluator import evaluate_model
from .execution_depth import _build_native_depth_analysis
from .identity import QualifiedModelRef, QualifiedNodeRef
from .mesh_materialization import MaterializedMesh
from .mesh_overlay import (
    EvidenceContributionRecord,
    MeshDependencyKey,
    MeshDepthBinding,
    MeshEvaluationOverlay,
    MeshNodeResult,
    OverlayDependencyBinding,
)
from .mesh_scc import build_model_dependency_graph, compute_model_sccs
from .model import Edge, Node
from .model_mesh import qualified_model_key, qualified_node_key
from .model_store import canonical_digest
from .provenance import ProvenanceRecord
from .schema import (
    ATTACK_EDGE_TYPES,
    STATE_IN,
    STATE_OUT,
    STATE_UNDECIDED,
    SUPPORT_EDGE_TYPES,
    UNDERCUT_EDGE_TYPES,
)
from .simulator import apply_default_perturbation


def _callable_fingerprint(value) -> str:
    try:
        source = inspect.getsource(value).encode("utf-8")
    except (OSError, TypeError):
        source = repr(value).encode("utf-8")
    return f"sha256:{hashlib.sha256(source).hexdigest()}"


MESH_EVALUATOR_FINGERPRINT = canonical_digest(
    {
        "component": "researchguard.logic.mesh-evaluator.v1",
        "p0_evaluator": _callable_fingerprint(evaluate_model),
        "p0_depth": _callable_fingerprint(_build_native_depth_analysis),
        "proxy_adapter": "qualified-revision-bound-proxy-v1",
        "scc": "iterative-kosaraju-grounded-support-v1",
        "contribution_dedup": "source-content-or-independence-group-v1",
    }
)
MESH_SIMULATOR_FINGERPRINT = canonical_digest(
    {
        "component": "researchguard.logic.mesh-simulator-contract.v1",
        "p0_perturbation": _callable_fingerprint(apply_default_perturbation),
    }
)


def _provenance_for_node(payload: Mapping[str, Any]) -> tuple[ProvenanceRecord, ...]:
    records = []
    for raw in payload.get("provenance") or ():
        record = raw if isinstance(raw, ProvenanceRecord) else ProvenanceRecord.from_dict(raw)
        if record.is_evidentiary:
            records.append(record)
    return tuple(records)


def build_cross_model_contribution_ledger(
    materialized: MaterializedMesh,
) -> tuple[EvidenceContributionRecord, ...]:
    """Count one contribution per target equivalence component.

    Two arrivals join the same component when they share exact source/content
    identity or the same declared independence group.  Only distinct
    source/content *and* distinct groups may count independently.
    """

    node_by_ref = {item.ref: item for item in materialized.nodes}
    candidates: dict[QualifiedNodeRef, list[dict[str, Any]]] = defaultdict(list)
    for edge in materialized.cross_edges:
        if edge.type not in SUPPORT_EDGE_TYPES:
            continue
        source = node_by_ref.get(edge.source)
        if source is None or source.payload.get("type") != "Evidence":
            continue
        for record in _provenance_for_node(source.payload):
            candidates[edge.target].append(
                {
                    "arrival": edge.source,
                    "source_identity": record.normalized_source_identity,
                    "content_hash": record.content_hash,
                    "independence_group": record.independence_group or "",
                }
            )

    ledger: list[EvidenceContributionRecord] = []
    for target, raw_items in candidates.items():
        components: list[list[dict[str, Any]]] = []
        for item in sorted(
            raw_items,
            key=lambda value: (
                value["source_identity"],
                value["content_hash"],
                value["independence_group"],
                qualified_node_key(value["arrival"]),
            ),
        ):
            matching = [
                index
                for index, component in enumerate(components)
                if any(
                    (
                        existing["source_identity"] == item["source_identity"]
                        and existing["content_hash"] == item["content_hash"]
                    )
                    or (
                        existing["independence_group"]
                        and existing["independence_group"] == item["independence_group"]
                    )
                    for existing in component
                )
            ]
            if not matching:
                components.append([item])
                continue
            first = matching[0]
            components[first].append(item)
            for index in reversed(matching[1:]):
                components[first].extend(components.pop(index))
        for component in components:
            source_content = sorted(
                {
                    (item["source_identity"], item["content_hash"])
                    for item in component
                }
            )
            groups = sorted({item["independence_group"] for item in component})
            arrivals = tuple(
                sorted({item["arrival"] for item in component}, key=qualified_node_key)
            )
            representative = min(
                component,
                key=lambda value: (
                    value["source_identity"],
                    value["content_hash"],
                    value["independence_group"],
                ),
            )
            contribution_key = canonical_digest(
                {
                    "target": target.to_dict(),
                    "source_content_keys": [list(item) for item in source_content],
                    "independence_groups": groups,
                }
            )
            ledger.append(
                EvidenceContributionRecord(
                    target=target,
                    contribution_key=contribution_key,
                    source_identity=representative["source_identity"],
                    content_hash=representative["content_hash"],
                    independence_group=representative["independence_group"],
                    arrivals=arrivals,
                    duplicate_arrival_count=max(len(arrivals) - 1, 0),
                )
            )
    return tuple(
        sorted(ledger, key=lambda item: (qualified_node_key(item.target), item.contribution_key))
    )


def _grounded_contributions(
    materialized: MaterializedMesh,
    ledger: Iterable[EvidenceContributionRecord],
) -> dict[QualifiedModelRef, set[str]]:
    by_arrival = {
        arrival: record.contribution_key
        for record in ledger
        for arrival in record.arrivals
    }
    result: dict[QualifiedModelRef, set[str]] = defaultdict(set)
    for arrival, key in by_arrival.items():
        result[QualifiedModelRef(arrival.model_id, arrival.revision)].add(key)
    return result


def _ordered_models(analysis) -> tuple[QualifiedModelRef, ...]:
    by_id = {item.scc_id: item for item in analysis.sccs}
    return tuple(
        member
        for scc_id in analysis.condensation_order
        for member in sorted(by_id[scc_id].members, key=qualified_model_key)
    )


def _proxy_inputs(materialized, ledger, current, analysis):
    node_by_ref = {item.ref: item for item in materialized.nodes}
    contribution_by_arrival = {
        arrival: record.contribution_key
        for record in ledger
        for arrival in record.arrivals
    }
    groups: dict[tuple[QualifiedNodeRef, str, str], list[Any]] = defaultdict(list)
    for edge in materialized.cross_edges:
        if edge.source not in current or edge.target not in current:
            continue
        source_node = node_by_ref.get(edge.source)
        dedup = contribution_by_arrival.get(edge.source)
        if dedup is None:
            dedup = str(edge.id)
        groups[(edge.target, edge.type, dedup)].append(edge)
    inputs: dict[QualifiedModelRef, list[dict[str, Any]]] = defaultdict(list)
    for (target, edge_type, dedup), edges in sorted(
        groups.items(),
        key=lambda item: (
            qualified_node_key(item[0][0]),
            item[0][1],
            item[0][2],
        ),
    ):
        states = [current[item.source] for item in edges]
        state = STATE_IN if any(item.state == STATE_IN for item in states) else (
            STATE_UNDECIDED if any(item.state == STATE_UNDECIDED for item in states) else STATE_OUT
        )
        confidence = max((item.confidence for item in states), default=0.0)
        source_model = QualifiedModelRef(edges[0].source.model_id, edges[0].source.revision)
        target_model = QualifiedModelRef(target.model_id, target.revision)
        source_scc = analysis.scc_for(source_model)
        target_scc = analysis.scc_for(target_model)
        cycle_blocked = (
            edge_type in SUPPORT_EDGE_TYPES
            and source_scc.scc_id == target_scc.scc_id
            and source_scc.cyclic
            and not source_scc.grounded_contribution_keys
        )
        if cycle_blocked:
            state = STATE_UNDECIDED
            confidence = 0.0
        inputs[target_model].append(
            {
                "target": target,
                "type": edge_type,
                "dedup": dedup,
                "state": state,
                "confidence": confidence,
                "edge_ids": tuple(sorted(str(item.id) for item in edges)),
                "cycle_blocked": cycle_blocked,
            }
        )
    return inputs


def _evaluate_with_proxies(model, proxy_inputs):
    for raw in proxy_inputs:
        digest = canonical_digest(
            {
                "target": raw["target"].to_dict(),
                "type": raw["type"],
                "dedup": raw["dedup"],
            }
        ).split(":", 1)[1]
        proxy_id = f"mesh_proxy_{digest[:32]}"
        model.nodes[proxy_id] = Node(
            id=proxy_id,
            type="Evidence",
            text="Revision-bound cross-model proxy",
            confidence=raw["confidence"],
            metadata={"forced_state": raw["state"], "mesh_proxy": True},
        )
        model.edges.append(
            Edge(
                id=f"mesh_proxy_edge_{digest[:32]}",
                source=proxy_id,
                target=str(raw["target"].node_id),
                type=raw["type"],
                weight=1.0,
                explanation="Temporary cross-model evaluation input",
            )
        )
    return evaluate_model(model)


def _depth_bindings(view, materialized, requested_scope, profile, budget):
    materialized_refs = {item.ref for item in materialized.nodes}
    bindings = []
    gaps = []
    for model_ref in materialized.model_pins:
        snapshot = view.model_snapshot(model_ref)
        model = snapshot.to_model()
        local_requested = tuple(
            ref for ref in requested_scope if QualifiedModelRef(ref.model_id, ref.revision) == model_ref
        )
        local_ids = tuple(str(item.node_id) for item in local_requested)
        if not local_ids and model.root_claim:
            local_ids = (model.root_claim,)
            local_requested = (
                QualifiedNodeRef(model_ref.model_id, model_ref.revision, model.root_claim),
            )
        try:
            receipt = _build_native_depth_analysis(
                model,
                budget=budget,
                requested_claim_scope_ids=local_ids,
            )
            universe_ids = (
                receipt.coverage_universe.important_node_ids
                if receipt.coverage_universe is not None
                else ()
            )
            important_refs = tuple(
                QualifiedNodeRef(model_ref.model_id, model_ref.revision, item)
                for item in universe_ids
            )
            depth_payload = receipt.to_dict()
            # Native depth execution time is audit metadata, not part of the
            # repeatable semantic result bound into a mesh overlay.
            depth_payload.pop("generated_at", None)
            relation = (
                "materialization_superset"
                if all(item in set(snapshot.model_payload["nodes"]) for item in universe_ids)
                else "incomplete"
            )
            binding = MeshDepthBinding(
                model_ref=model_ref,
                depth_receipt_digest=canonical_digest(depth_payload),
                model_fingerprint=receipt.model_fingerprint,
                requested_claim_refs=local_requested,
                important_node_refs=important_refs,
                scope_relation=relation,
                status=receipt.status,
                broad_claim_licensed=receipt.broad_claim_licensed,
                gaps=receipt.unresolved_gaps,
            )
        except Exception as exc:
            binding = MeshDepthBinding(
                model_ref=model_ref,
                depth_receipt_digest=canonical_digest({"error": str(exc)}),
                model_fingerprint=snapshot.content_digest,
                requested_claim_refs=local_requested,
                important_node_refs=(),
                scope_relation="incomplete",
                status="blocked",
                broad_claim_licensed=False,
                gaps=(f"native_depth_error:{type(exc).__name__}:{exc}",),
            )
        bindings.append(binding)
        gaps.extend(f"depth:{model_ref.model_id}:{item}" for item in binding.gaps)
    return tuple(bindings), gaps


def _dependency_binding(
    view,
    materialized,
    requested_scope,
    profile,
    ledger,
):
    keys: list[MeshDependencyKey] = []
    registry = {item.model_ref: item for item in view.snapshot.registry}
    for model_ref in materialized.model_pins:
        entry = registry[model_ref]
        keys.append(
            MeshDependencyKey.create(
                "model_pin",
                {"model_ref": model_ref.to_dict(), "content_digest": entry.content_digest},
            )
        )
    for node in materialized.nodes:
        keys.append(
            MeshDependencyKey.create(
                "node",
                {"node_ref": node.ref.to_dict(), "payload_digest": canonical_digest(node.to_dict())},
            )
        )
    for membership in materialized.memberships:
        keys.append(
            MeshDependencyKey.create(
                "membership",
                {
                    "membership_key": membership.membership_key,
                    "content_digest": membership.content_digest,
                },
            )
        )
    for edge in materialized.cross_edges:
        keys.append(
            MeshDependencyKey.create(
                "edge",
                {
                    "edge_id": str(edge.id),
                    "relation_key": edge.relation_key,
                    "content_digest": canonical_digest(edge.to_dict()),
                },
            )
        )
    for record in ledger:
        keys.append(
            MeshDependencyKey.create(
                "evidence_identity",
                {
                    "contribution_key": record.contribution_key,
                    "source_identity": record.source_identity,
                    "content_hash": record.content_hash,
                },
            )
        )
        keys.append(
            MeshDependencyKey.create(
                "independence_group",
                {
                    "independence_group": record.independence_group,
                    "contribution_key": record.contribution_key,
                },
            )
        )
    keys.extend(
        (
            MeshDependencyKey.create(
                "evaluator", {"fingerprint": MESH_EVALUATOR_FINGERPRINT}
            ),
            MeshDependencyKey.create(
                "simulator", {"fingerprint": MESH_SIMULATOR_FINGERPRINT}
            ),
            MeshDependencyKey.create(
                "scope", {"requested": [item.to_dict() for item in requested_scope]}
            ),
            MeshDependencyKey.create("profile", {"profile": profile}),
        )
    )
    return OverlayDependencyBinding.create(
        mesh_id=materialized.mesh_id,
        mesh_revision=materialized.mesh_revision,
        mesh_content_digest=materialized.mesh_content_digest,
        materialization_fingerprint=materialized.materialization_fingerprint,
        model_refs=materialized.model_pins,
        node_refs=tuple(item.ref for item in materialized.nodes),
        membership_keys=tuple(item.membership_key for item in materialized.memberships),
        edge_ids=tuple(item.id for item in materialized.cross_edges),
        contribution_keys=tuple(item.contribution_key for item in ledger),
        independence_groups=tuple(item.independence_group for item in ledger),
        evaluator_fingerprint=MESH_EVALUATOR_FINGERPRINT,
        simulator_fingerprint=MESH_SIMULATOR_FINGERPRINT,
        requested_claim_scope=requested_scope,
        profile=profile,
        dependency_keys=keys,
    )


def evaluate_materialized_mesh(
    view,
    materialized: MaterializedMesh,
    *,
    requested_claim_scope: Iterable[QualifiedNodeRef],
    profile: str,
    max_model_iterations: int = 25,
    max_scc_iterations: int = 25,
    depth_budget: int = 6,
    authority: str = "production",
) -> MeshEvaluationOverlay:
    if (
        materialized.mesh_id != view.snapshot.mesh_id
        or materialized.mesh_revision != view.snapshot.revision
        or materialized.mesh_content_digest != view.snapshot.content_digest
    ):
        raise ValueError("materialization does not bind evaluator mesh view")
    if profile not in {"broad", "bounded"}:
        raise ValueError("mesh evaluation profile must be broad or bounded")
    if authority not in {"production", "simulation"}:
        raise ValueError("mesh evaluation authority must be production or simulation")
    requested_scope = tuple(sorted(set(requested_claim_scope), key=qualified_node_key))
    materialized_refs = {item.ref for item in materialized.nodes}
    if not requested_scope or any(item not in materialized_refs for item in requested_scope):
        raise ValueError("requested claim scope must be non-empty and materialized")

    models = {
        model_ref: view.model_snapshot(model_ref).to_model()
        for model_ref in materialized.model_pins
    }
    local_results = {
        model_ref: evaluate_model(model, max_iterations=max_model_iterations)
        for model_ref, model in models.items()
    }
    current = {
        QualifiedNodeRef(model_ref.model_id, model_ref.revision, node_id): node_result
        for model_ref, result in local_results.items()
        for node_id, node_result in result.node_results.items()
        if QualifiedNodeRef(model_ref.model_id, model_ref.revision, node_id) in materialized_refs
    }
    ledger = build_cross_model_contribution_ledger(materialized)
    graph = build_model_dependency_graph(materialized)
    analysis = compute_model_sccs(
        graph, grounded_contributions=_grounded_contributions(materialized, ledger)
    )
    ordered_models = _ordered_models(analysis)
    seen = set()
    converged = False
    oscillating = False
    last_results = dict(local_results)
    for _iteration in range(max_scc_iterations):
        vector = tuple(
            sorted(
                (qualified_node_key(ref), result.state, round(result.confidence, 6))
                for ref, result in current.items()
            )
        )
        if vector in seen:
            oscillating = True
            break
        seen.add(vector)
        inputs = _proxy_inputs(materialized, ledger, current, analysis)
        working = dict(current)
        next_results = {}
        for model_ref in ordered_models:
            model = view.model_snapshot(model_ref).to_model()
            result = _evaluate_with_proxies(model, inputs.get(model_ref, ()))
            next_results[model_ref] = result
            for node_id, node_result in result.node_results.items():
                ref = QualifiedNodeRef(model_ref.model_id, model_ref.revision, node_id)
                if ref in materialized_refs:
                    working[ref] = node_result
        if all(
            current[ref].state == working[ref].state
            and abs(current[ref].confidence - working[ref].confidence) <= 0.000001
            for ref in current
        ):
            current = working
            last_results = next_results
            converged = True
            break
        current = working
        last_results = next_results

    if oscillating:
        cyclic_models = {
            member for scc in analysis.sccs if scc.cyclic for member in scc.members
        }
        for ref, result in tuple(current.items()):
            if QualifiedModelRef(ref.model_id, ref.revision) in cyclic_models:
                current[ref] = type(result)(
                    node_id=result.node_id,
                    state=STATE_UNDECIDED,
                    confidence=0.0,
                    explanation="Cross-model SCC oscillated; result withheld.",
                    blockers=list(result.blockers),
                )

    node_results = tuple(
        MeshNodeResult(
            node_ref=ref,
            state=result.state,
            confidence=result.confidence,
            explanation=result.explanation,
            blockers=tuple(result.blockers),
        )
        for ref, result in sorted(current.items(), key=lambda item: qualified_node_key(item[0]))
    )
    depth_bindings, depth_gaps = _depth_bindings(
        view, materialized, requested_scope, profile, depth_budget
    )
    gaps = [f"materialization:{item}" for item in materialized.truncation_reasons]
    gaps.extend(depth_gaps)
    if materialized.unresolved_references:
        gaps.append("unresolved_materialization_references")
    if not converged:
        gaps.append("cross_model_evaluation_not_converged")
    for scc in analysis.sccs:
        if scc.status == "ungrounded-cycle":
            gaps.append(f"ungrounded_support_cycle:{scc.scc_id}")
    for edge in materialized.cross_edges:
        target_model = models[QualifiedModelRef(edge.target.model_id, edge.target.revision)]
        if str(edge.target.node_id) in target_model.acceptance:
            gaps.append(f"explicit_acceptance_cross_input_not_consumed:{edge.target}")
    gaps = tuple(sorted(set(gaps)))

    block_results = []
    for model_ref in materialized.model_pins:
        model = view.model_snapshot(model_ref).to_model()
        for block_id, block in sorted(model.blocks.items()):
            member_refs = tuple(
                QualifiedNodeRef(model_ref.model_id, model_ref.revision, node_id)
                for node_id in block.member_node_ids()
                if QualifiedNodeRef(model_ref.model_id, model_ref.revision, node_id)
                in materialized_refs
            )
            if not member_refs:
                continue
            block_results.append(
                {
                    "model_ref": model_ref.to_dict(),
                    "block_id": block_id,
                    "member_refs": [item.to_dict() for item in member_refs],
                    "output_results": [
                        {
                            "node_ref": QualifiedNodeRef(
                                model_ref.model_id, model_ref.revision, node_id
                            ).to_dict(),
                            "state": current[
                                QualifiedNodeRef(model_ref.model_id, model_ref.revision, node_id)
                            ].state,
                        }
                        for node_id in block.output_claims
                        if QualifiedNodeRef(model_ref.model_id, model_ref.revision, node_id)
                        in current
                    ],
                }
            )
    cycle_records = [
        {
            "kind": "model_scc",
            "scc_id": item.scc_id,
            "members": [member.to_dict() for member in item.members],
            "status": item.status,
        }
        for item in analysis.sccs
        if item.cyclic
    ]
    dependency_binding = _dependency_binding(
        view, materialized, requested_scope, profile, ledger
    )
    requested_in = all(current[item].state == STATE_IN for item in requested_scope)
    broad_claim_licensed = (
        profile == "broad"
        and materialized.request.profile == "broad"
        and materialized.complete
        and not gaps
        and requested_in
        and bool(depth_bindings)
        and all(item.licenses_mesh_scope for item in depth_bindings)
        and authority == "production"
    )
    return MeshEvaluationOverlay(
        mesh_id=materialized.mesh_id,
        mesh_revision=materialized.mesh_revision,
        mesh_content_digest=materialized.mesh_content_digest,
        materialization_fingerprint=materialized.materialization_fingerprint,
        authoritative_universe_fingerprint=materialized.authoritative_universe_fingerprint,
        requested_claim_scope=requested_scope,
        selected_models=materialized.model_pins,
        profile=profile,
        completeness="complete" if materialized.complete else "partial",
        truncated=bool(materialized.truncation_reasons),
        node_results=node_results,
        block_results=tuple(block_results),
        model_sccs=tuple(item.to_dict() for item in analysis.sccs),
        cycles=tuple(cycle_records),
        contribution_ledger=ledger,
        depth_bindings=depth_bindings,
        unresolved_references=tuple(item.to_dict() for item in materialized.unresolved_references),
        gaps=gaps,
        warnings=(
            ("Cross-model fixed point did not converge.",) if not converged else ()
        ),
        dependency_binding=dependency_binding,
        evaluator_fingerprint=MESH_EVALUATOR_FINGERPRINT,
        simulator_fingerprint=MESH_SIMULATOR_FINGERPRINT,
        package_version="0.17.4",
        authority=authority,
        broad_claim_licensed=broad_claim_licensed,
    )


__all__ = [
    "MESH_EVALUATOR_FINGERPRINT",
    "MESH_SIMULATOR_FINGERPRINT",
    "build_cross_model_contribution_ledger",
    "evaluate_materialized_mesh",
]
