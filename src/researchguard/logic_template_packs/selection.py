"""Deterministic zero/one/many selection for LogicGuard template packs."""

from __future__ import annotations

from itertools import combinations

from .canonical import canonical_sha256
from .models import (
    Finding,
    TemplateCatalog,
    TemplateProfile,
    TemplateRequest,
    TemplateSelection,
)


def select_template_pack(
    catalog: TemplateCatalog,
    request: TemplateRequest,
) -> TemplateSelection:
    candidates = tuple(
        sorted(
            (
                profile
                for profile in catalog.profiles
                if not profile.is_base and profile.selector.matches(request)
            ),
            key=lambda item: item.profile_id,
        )
    )
    candidate_ids = tuple(profile.profile_id for profile in candidates)
    findings: tuple[Finding, ...] = ()
    selected_ids: tuple[str, ...] = ()

    if not candidates:
        if request.allow_base:
            decision = "base"
            selected_ids = (catalog.base_profile_id,)
        else:
            decision = "no_match"
            findings = (
                Finding(
                    "no_matching_profile",
                    "No non-base profile matched and the request forbids base use.",
                ),
            )
    elif len(candidates) == 1:
        decision = "selected"
        selected_ids = candidate_ids
    else:
        candidate_id_set = set(candidate_ids)
        dominance_edges = {
            (profile.profile_id, dominated_id)
            for profile in candidates
            for dominated_id in profile.strictly_dominates
            if dominated_id in candidate_id_set
        }
        complete_dominators = tuple(
            profile
            for profile in candidates
            if set(candidate_ids) - {profile.profile_id}
            <= set(profile.strictly_dominates)
        )
        if len(complete_dominators) == 1:
            decision = "selected"
            selected_ids = (complete_dominators[0].profile_id,)
        elif len(complete_dominators) > 1:
            decision = "ambiguous"
            findings = (
                Finding(
                    "multiple_complete_dominators",
                    "More than one candidate claims complete strict dominance.",
                ),
            )
        elif dominance_edges:
            decision = "ambiguous"
            if _has_dominance_cycle(candidate_ids, dominance_edges):
                code = "dominance_cycle"
                message = "The candidate dominance graph contains a cycle and cannot authorize selection or composition."
            else:
                code = "incomplete_dominance"
                message = "The candidate dominance graph does not contain one complete dominator."
            findings = (Finding(code, message),)
        else:
            composition_findings = _composition_findings(candidates)
            if not composition_findings:
                decision = "composed"
                selected_ids = candidate_ids
            else:
                decision = "ambiguous"
                dominance_findings = (
                    Finding(
                        "no_complete_dominator",
                        "No candidate strictly dominates every other candidate.",
                    ),
                )
                findings = tuple(
                    sorted(
                        (*dominance_findings, *composition_findings),
                        key=lambda item: (
                            item.code,
                            item.profile_id,
                            item.field_path,
                            item.message,
                        ),
                    )
                )

    payload = {
        "catalog_digest": catalog.catalog_digest,
        "request": request.to_dict(),
        "candidate_ids": list(candidate_ids),
        "decision": decision,
        "selected_profile_ids": list(selected_ids),
        "findings": [item.to_dict() for item in findings],
    }
    return TemplateSelection(
        decision=decision,
        request=request,
        catalog_digest=catalog.catalog_digest,
        candidate_ids=candidate_ids,
        selected_profile_ids=selected_ids,
        findings=findings,
        selection_fingerprint=canonical_sha256(payload),
    )


def _has_dominance_cycle(
    candidate_ids: tuple[str, ...],
    edges: set[tuple[str, str]],
) -> bool:
    outgoing = {
        candidate_id: {
            target
            for source, target in edges
            if source == candidate_id
        }
        for candidate_id in candidate_ids
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(candidate_id: str) -> bool:
        if candidate_id in visiting:
            return True
        if candidate_id in visited:
            return False
        visiting.add(candidate_id)
        for target in sorted(outgoing[candidate_id]):
            if visit(target):
                return True
        visiting.remove(candidate_id)
        visited.add(candidate_id)
        return False

    return any(visit(candidate_id) for candidate_id in candidate_ids)


def _composition_findings(
    candidates: tuple[TemplateProfile, ...],
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for left, right in combinations(candidates, 2):
        if (
            right.profile_id not in left.composable_with
            or left.profile_id not in right.composable_with
        ):
            findings.append(
                Finding(
                    "composition_not_declared",
                    f"{left.profile_id} and {right.profile_id} are not explicitly pairwise composable.",
                )
            )
    field_owners: dict[str, list[str]] = {}
    for profile in candidates:
        for field_path in profile.emitted_field_paths:
            field_owners.setdefault(field_path, []).append(profile.profile_id)
    for field_path, owners in field_owners.items():
        if len(owners) > 1:
            findings.append(
                Finding(
                    "field_owner_conflict",
                    f"Field {field_path} would have multiple owners: {sorted(owners)}.",
                    field_path=field_path,
                )
            )
    return tuple(findings)
