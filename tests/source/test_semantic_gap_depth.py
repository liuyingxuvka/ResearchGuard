from __future__ import annotations

import json
from pathlib import Path

import pytest

from researchguard.source import (
    BeliefState,
    EvidenceAnchor,
    Gap,
    Lead,
    Observation,
    SourceDepthPolicy,
    SourceRecord,
    apply_observation_and_replan,
    build_source_depth_receipt,
)
from researchguard.source.planner import generate_actions_from_gaps
from researchguard.source.guard_contract import prove_target_model_contract
from researchguard.source.loader import load_model
from researchguard.source.update import apply_observation
from researchguard.source.schema import (
    SchemaError,
    SourceGuardPreventedFailure,
    SourceGuardProofCase,
    bind_sourceguard_model_contract,
    build_sourceguard_model_contract,
    sourceguard_model_contract_fingerprint,
    to_plain,
)


ROOT = Path(__file__).resolve().parents[2]


def _guard(state: BeliefState, model_id: str = "test-sourceguard-depth") -> BeliefState:
    gap_id = state.gaps[0].gap_id if state.gaps else "test-gap"
    failure = SourceGuardPreventedFailure(
        failure_id=f"failure:{model_id}:unqualified-candidate",
        title="Unqualified source evidence licenses closure",
        block_when="a gap closes although the supplied anchor is not claim-usable",
        oracle_id="oracle:sourceguard:source-qualification",
        known_good=SourceGuardProofCase("good:test:qualified", "good.yaml", "pass"),
        known_bad=SourceGuardProofCase(
            "bad:test:unqualified",
            "good.yaml",
            "blocked",
            "make-all-anchors-unusable",
            f"gaps:{gap_id}",
        ),
    )
    return bind_sourceguard_model_contract(
        state,
        contract=build_sourceguard_model_contract(
            model_id=model_id,
            purpose="Prevent shallow source evidence from licensing unsupported closure or broad claims.",
            prevented_failures=[failure],
            gap_ids=[gap.gap_id for gap in state.gaps],
            target_unit_ids=[gap.structure_unit_id for gap in state.gaps if gap.structure_unit_id],
            claim_boundary="Source discovery and evidence-depth closure only; factual truth remains downstream.",
        ),
    )


def test_sourceguard_prompt_requires_exact_per_obligation_evidence() -> None:
    raw_prompt = (ROOT / "skills/sourceguard/SKILL.md").read_text(encoding="utf-8")
    assert "\n+Keep only" not in raw_prompt
    prompt = " ".join(raw_prompt.split())
    assert "not proof of an individual SourceGuard obligation" in prompt
    assert "`evidence_ref`" in prompt
    assert "lowercase content hash" in prompt


def _gap() -> Gap:
    return Gap(
        gap_id="g1",
        lead_id="l1",
        gap_type="missing_independent_source",
        description="Independent clinical outcome evidence is missing",
        importance=0.9,
        blocking=True,
        suggested_source_roles=["independent_report"],
        suggested_modalities=["text"],
    )


def _qualified_observation(*, add_gap: bool = False) -> Observation:
    return Observation(
        observation_id="obs-qualified",
        observed_sources=[
            SourceRecord(
                source_id="s1",
                source_type="paper",
                source_role="independent_report",
                source_reliability=0.9,
                access_status="public",
            )
        ],
        observed_anchors=[
            EvidenceAnchor(
                anchor_id="a1",
                source_id="s1",
                anchor_type="paragraph",
                locator="results:paragraph-3",
                modality="text",
                extraction_confidence=0.9,
                specificity=0.9,
                supports=["g1"],
                usable_for_claim=True,
            )
        ],
        new_gaps=[
            Gap(
                gap_id="g-followup",
                lead_id="l1",
                gap_type="missing_counterevidence",
                description="Check adverse-outcome counterevidence",
                importance=0.7,
            )
        ]
        if add_gap
        else [],
    )


def test_locator_only_anchor_does_not_close_or_become_claim_usable() -> None:
    state = _guard(BeliefState(gaps=[_gap()]), "test-locator-only")
    observation = Observation(
        observation_id="obs-shallow",
        observed_sources=[
            SourceRecord(
                source_id="s1",
                source_role="independent_report",
                source_reliability=0.0,
                access_status="public",
            )
        ],
        observed_anchors=[
            EvidenceAnchor(
                anchor_id="a1",
                source_id="s1",
                locator="page=1",
                modality="text",
                extraction_confidence=0.0,
                specificity=0.0,
                supports=["g1"],
                usable_for_claim=False,
            )
        ],
    )

    updated = apply_observation(state, observation)
    gap = updated.gaps[0]
    assert gap.semantic_state == "observed"
    assert gap.qualification.usable_for_claim is False
    assert not gap.closure_basis.is_complete()


def test_retired_gap_status_is_rejected_before_runtime() -> None:
    contract = build_sourceguard_model_contract(
        model_id="test-legacy-closed",
        purpose="Prevent retired gap status labels from entering normal runtime.",
        prevented_failures=[
            SourceGuardPreventedFailure(
                failure_id="failure:test-legacy:unqualified-closure",
                title="Retired status projection is accepted",
                block_when="a retired gap status field is accepted",
                oracle_id="oracle:sourceguard:source-qualification",
                known_good=SourceGuardProofCase("good:test-legacy", "good.yaml", "pass"),
                known_bad=SourceGuardProofCase(
                    "bad:test-legacy", "good.yaml", "blocked",
                    "make-all-anchors-unusable", "gaps:legacy"
                ),
            )
        ],
        gap_ids=["legacy"],
        target_unit_ids=[],
        claim_boundary="Current gap schema admission only; factual truth remains downstream.",
    )
    with pytest.raises(SchemaError, match="gap.status is retired"):
        BeliefState.from_dict(
            {
                "guard_contract": contract.to_dict(),
                "candidate_contract_fingerprint": sourceguard_model_contract_fingerprint(contract),
                "gaps": [
                    {
                        "gap_id": "legacy",
                        "gap_type": "missing_primary_source",
                        "status": "closed",
                        "semantic_state": "closed",
                    }
                ],
            }
        )


def test_qualified_observation_records_complete_closure_basis() -> None:
    updated = apply_observation(
        _guard(BeliefState(gaps=[_gap()]), "test-qualified-observation"),
        _qualified_observation(),
    )
    gap = updated.gaps[0]

    assert gap.semantic_state == "closed"
    assert gap.qualification.decision == "claim_usable"
    assert gap.closure_basis.is_complete()
    assert gap.closure_basis.observation_ids == ["obs-qualified"]


def test_observation_runs_on_clone_and_receipt_compares_replan() -> None:
    baseline = _guard(
        BeliefState(leads=[Lead(lead_id="l1", question="Clinical outcomes")], gaps=[_gap()]),
        "test-observation-replan",
    )
    updated, receipt = apply_observation_and_replan(baseline, _qualified_observation(add_gap=True))

    assert baseline.gaps[0].semantic_state == "discovered"
    assert updated.gap_by_id()["g1"].semantic_state == "closed"
    assert receipt.observation_depth_completed is True
    assert "g1" not in receipt.replan_comparison.after_open_gap_ids
    assert "g-followup" in receipt.replan_comparison.remaining_gap_ids
    assert receipt.replan_comparison.removed_action_ids
    assert receipt.replan_comparison.added_action_ids
    assert receipt.status == "bounded"


def test_medical_execution_gap_does_not_inject_industrial_vocabulary() -> None:
    state = _guard(
        BeliefState(
            metadata={"domain_hints": ["medical literature", "clinical outcomes"]},
            leads=[Lead(lead_id="l1", question="Was the therapy used in a randomized clinical trial?")],
            gaps=[
                Gap(
                    gap_id="g-medical",
                    lead_id="l1",
                    gap_type="missing_execution_evidence",
                    description="Need evidence that the intervention was actually administered",
                )
            ],
        ),
        "test-medical-vocabulary",
    )
    queries = " ".join(action.query.lower() for action in generate_actions_from_gaps(state))

    for forbidden in ("fuel cell", "fuel-cell", "deployment", "procurement", "site photo"):
        assert forbidden not in queries
    assert "clinical" in queries


def test_no_observation_receipt_is_honestly_planning_only() -> None:
    receipt = build_source_depth_receipt(
        _guard(BeliefState(gaps=[_gap()]), "test-planning-only")
    )

    assert receipt.planning_depth_completed is True
    assert receipt.observation_depth_completed is False
    assert receipt.provider_status == "NOT_RUN"
    assert receipt.observation_status == "NOT_RUN"
    assert receipt.gap_transitions == []
    assert receipt.broad_claim_licensed is False
    assert receipt.status == "planning_only"


def _broad_state() -> BeliefState:
    gaps = [
        Gap(
            gap_id="g-direct",
            lead_id="l-broad",
            gap_type="missing_primary_source",
            importance=0.9,
            blocking=True,
            suggested_source_roles=["primary_source"],
            suggested_modalities=["text"],
            structure_unit_id="unit:central-claim",
        ),
        Gap(
            gap_id="g-independent",
            lead_id="l-broad",
            gap_type="missing_independent_source",
            importance=0.9,
            blocking=True,
            suggested_source_roles=["independent_report"],
            suggested_modalities=["text"],
            structure_unit_id="unit:central-claim",
        ),
        Gap(
            gap_id="g-limiting",
            lead_id="l-broad",
            gap_type="missing_counterevidence",
            importance=0.9,
            blocking=True,
            suggested_source_roles=["limiting_evidence"],
            suggested_modalities=["text"],
            structure_unit_id="unit:central-claim",
        ),
    ]
    return _guard(
        BeliefState(
            depth_policy=SourceDepthPolicy(
                requested_claim_scope="broad",
                target_unit_inventory_ids=["unit:central-claim"],
                required_target_unit_ids=["unit:central-claim"],
            ),
            leads=[
                Lead(
                    lead_id="l-broad",
                    question="Can the claim survive a broad source portfolio?",
                    importance=0.9,
                    gaps=[gap.gap_id for gap in gaps],
                )
            ],
            gaps=gaps,
        ),
        "test-broad-source-depth",
    )


def _broad_observation(*, shared_lineage: bool = False) -> Observation:
    source_rows = [
        ("s-direct", "primary_source", "g-direct"),
        ("s-independent", "independent_report", "g-independent"),
        ("s-limiting", "limiting_evidence", "g-limiting"),
    ]
    all_gap_ids = [gap_id for _, _, gap_id in source_rows]
    return Observation(
        observation_id="obs-broad",
        observed_sources=[
            SourceRecord(
                source_id=source_id,
                source_type="report",
                source_role=role,
                lineage_id="shared-origin" if shared_lineage else f"origin:{source_id}",
                source_reliability=0.9,
                access_status="public",
            )
            for source_id, role, _ in source_rows
        ],
        observed_anchors=[
            EvidenceAnchor(
                anchor_id=f"a:{source_id}",
                source_id=source_id,
                anchor_type="paragraph",
                locator=f"section:{gap_id}",
                normalized_summary=f"Qualified evidence contribution from {source_id} for the central claim.",
                modality="text",
                extraction_confidence=0.9,
                specificity=0.9,
                supports=(
                    all_gap_ids
                    if role in {"primary_source", "independent_report"}
                    else [gap_id]
                ),
                limits=(
                    [item for item in all_gap_ids if item != gap_id]
                    if role == "limiting_evidence"
                    else []
                ),
                usable_for_claim=True,
            )
            for source_id, role, gap_id in source_rows
        ],
    )


def test_content_anchor_purpose_contract_observes_catalog_blocking_finding(
    tmp_path: Path,
) -> None:
    model = _broad_state()
    observation = _broad_observation()
    contract = build_sourceguard_model_contract(
        model_id="test-content-anchor-purpose-proof",
        purpose="Prevent contentless anchors from satisfying governed source depth.",
        prevented_failures=[
            SourceGuardPreventedFailure(
                failure_id="failure:test:contentless-anchor",
                title="Contentless anchor satisfies governed source depth",
                block_when=(
                    "a governed gap passes although every linked anchor lacks extracted "
                    "text and a normalized content summary"
                ),
                oracle_id="oracle:sourceguard:content-anchor",
                known_good=SourceGuardProofCase(
                    "good:test:content-bearing",
                    "content-anchor-observation.json",
                    "pass",
                ),
                known_bad=SourceGuardProofCase(
                    "bad:test:contentless",
                    "content-anchor-observation.json",
                    "blocked",
                    "remove-anchor-content",
                    "sourceguard_blocked:contentless-anchor",
                ),
            )
        ],
        gap_ids=[gap.gap_id for gap in model.gaps],
        target_unit_ids=["unit:central-claim"],
        claim_boundary=(
            "Content-anchor depth identity only; factual truth remains downstream."
        ),
    )
    bind_sourceguard_model_contract(model, contract=contract)

    model_path = tmp_path / "content-anchor-model.json"
    contract_path = tmp_path / "content-anchor-model.contract.json"
    observation_path = tmp_path / "content-anchor-observation.json"
    model_path.write_text(json.dumps(to_plain(model), indent=2), encoding="utf-8")
    contract_path.write_text(json.dumps(contract.to_dict(), indent=2), encoding="utf-8")
    observation_path.write_text(
        json.dumps(to_plain(observation), indent=2), encoding="utf-8"
    )

    loaded = load_model(model_path, contract_path)
    proof = prove_target_model_contract(loaded, contract_path)

    assert proof["status"] == "pass"
    assert proof["failure_results"][0]["known_good"]["status"] == "pass"
    assert proof["failure_results"][0]["known_bad"] == {
        "status": "blocked",
        "observation_path": "content-anchor-observation.json",
        "native_finding": "sourceguard_blocked:contentless-anchor",
    }


def test_one_gap_one_source_cannot_license_broad_source_depth() -> None:
    state = _guard(
        BeliefState(
            depth_policy=SourceDepthPolicy(requested_claim_scope="broad"),
            leads=[Lead(lead_id="l1", importance=0.9, gaps=["g1"])],
            gaps=[_gap()],
        ),
        "test-one-gap-broad",
    )
    receipt = build_source_depth_receipt(state, _qualified_observation())

    assert receipt.status == "bounded"
    assert receipt.requested_claim_scope == "broad"
    assert receipt.covered_claim_scope == "bounded"
    assert receipt.adequacy_status == "fail"
    assert receipt.broad_claim_licensed is False
    assert any(item.startswith("portfolio_classes:") for item in receipt.critical_uncovered_ids)


def test_complete_native_source_portfolio_can_license_broad_depth() -> None:
    receipt = build_source_depth_receipt(_broad_state(), _broad_observation())

    assert receipt.status == "pass"
    assert receipt.adequacy_status == "pass"
    assert receipt.covered_claim_scope == "broad"
    assert receipt.broad_claim_licensed is True
    assert receipt.critical_uncovered_ids == []
    assert receipt.coverage_universe.universe_fingerprint
    dimensions = {item.dimension_id: item for item in receipt.coverage_universe.dimensions}
    assert dimensions["portfolio_classes"].coverage_ratio == 1.0
    assert dimensions["independent_lineages"].closed_count == 2
    assert dimensions["target_units"].coverage_ratio == 1.0
    assert dimensions["per_gap_portfolio"].coverage_ratio == 1.0
    assert dimensions["per_gap_lineages"].coverage_ratio == 1.0
    assert all(item.status == "pass" for item in receipt.coverage_universe.object_depth_rows)


def test_native_receipt_preserves_exact_evidence_for_each_gap_obligation() -> None:
    receipt = build_source_depth_receipt(_broad_state(), _broad_observation())

    assert receipt.native_obligation_evidence
    for row in receipt.coverage_universe.object_depth_rows:
        evidence_by_obligation: dict[str, list[dict[str, object]]] = {}
        for evidence in row.obligation_evidence:
            for obligation_id in evidence["target_obligation_ids"]:
                evidence_by_obligation.setdefault(str(obligation_id), []).append(evidence)
            assert str(evidence["evidence_ref"]).startswith("sourceguard:")
            assert len(str(evidence["evidence_sha256"])) == 64
            assert str(evidence["evidence_sha256"]) == str(evidence["evidence_sha256"]).lower()
        for portfolio_class in row.required_portfolio_classes:
            assert evidence_by_obligation[f"{row.gap_id}:portfolio:{portfolio_class}"]
        for index in range(1, row.required_lineage_count + 1):
            lineage_rows = evidence_by_obligation[f"{row.gap_id}:lineage:{index}"]
            assert all(item.get("lineage_id") for item in lineage_rows)
        assert evidence_by_obligation[f"{row.gap_id}:content-anchor"]
        assert evidence_by_obligation[f"{row.gap_id}:target-unit"]

    changed = _broad_observation()
    changed.observed_anchors[0].normalized_summary += " Content-addressed change."
    changed_receipt = build_source_depth_receipt(_broad_state(), changed)
    original_hashes = {
        (str(row["native_object_id"]), str(row["evidence_ref"])): str(row["evidence_sha256"])
        for row in receipt.native_obligation_evidence
    }
    changed_hashes = {
        (str(row["native_object_id"]), str(row["evidence_ref"])): str(row["evidence_sha256"])
        for row in changed_receipt.native_obligation_evidence
    }
    changed_ref = "sourceguard:anchor:a:s-direct"
    assert any(
        original_hashes[key] != changed_hashes[key]
        for key in original_hashes.keys() & changed_hashes.keys()
        if key[1] == changed_ref
    )


def test_dependent_sources_do_not_satisfy_independent_lineage_floor() -> None:
    receipt = build_source_depth_receipt(
        _broad_state(),
        _broad_observation(shared_lineage=True),
    )

    assert receipt.status == "bounded"
    assert receipt.broad_claim_licensed is False
    assert "independent_lineages:independent_lineage_slot:2" in receipt.critical_uncovered_ids


def test_broad_scope_requires_a_nonempty_target_unit_inventory() -> None:
    state = _broad_state()
    state.depth_policy.target_unit_inventory_ids = []
    state.depth_policy.required_target_unit_ids = []

    receipt = build_source_depth_receipt(state, _broad_observation())

    assert receipt.broad_claim_licensed is False
    assert "target_units_required_universe_empty" in receipt.coverage_universe.findings
    assert "target_unit_inventory_required_for_broad" in receipt.coverage_universe.findings


def test_discovered_target_unit_cannot_be_omitted_from_declared_inventory() -> None:
    state = _broad_state()
    state.gaps.append(
        Gap(
            gap_id="g-silently-omitted-unit",
            lead_id="l-broad",
            gap_type="missing_independent_source",
            importance=0.2,
            structure_unit_id="unit:omitted-section",
        )
    )
    state = _guard(state, "test-omitted-unit")

    receipt = build_source_depth_receipt(state, _broad_observation())

    assert receipt.broad_claim_licensed is False
    assert "unit:omitted-section" in receipt.coverage_universe.discovered_target_unit_ids
    assert any(
        finding.startswith("target_unit_inventory_missing_discovered:")
        for finding in receipt.coverage_universe.findings
    )


def test_declared_target_unit_must_be_required_or_explicitly_excluded() -> None:
    state = _broad_state()
    state.depth_policy.target_unit_inventory_ids.append("unit:appendix")

    receipt = build_source_depth_receipt(state, _broad_observation())

    assert receipt.broad_claim_licensed is False
    assert "target_unit_inventory_unclassified:unit:appendix" in receipt.coverage_universe.findings


def test_excluded_target_unit_needs_reason_and_cannot_hide_an_active_gap() -> None:
    state = _broad_state()
    state.depth_policy.target_unit_inventory_ids.append("unit:excluded")
    state.depth_policy.excluded_target_unit_ids.append("unit:excluded")
    state.gaps.append(
        Gap(
            gap_id="g-excluded",
            lead_id="l-broad",
            gap_type="missing_counterevidence",
            importance=0.2,
            structure_unit_id="unit:excluded",
        )
    )
    state = _guard(state, "test-excluded-active-gap")

    receipt = build_source_depth_receipt(state, _broad_observation())

    assert receipt.broad_claim_licensed is False
    assert "target_unit_exclusion_reason_missing:unit:excluded" in receipt.coverage_universe.findings
    assert "target_unit_excluded_has_active_gap:unit:excluded" in receipt.coverage_universe.findings


def test_null_exclusion_reason_is_not_coerced_into_apparent_text() -> None:
    state = _broad_state()
    state.depth_policy.target_unit_inventory_ids.append("unit:appendix")
    state.depth_policy.excluded_target_unit_ids.append("unit:appendix")
    state.depth_policy.target_unit_exclusion_reasons["unit:appendix"] = None  # type: ignore[assignment]

    receipt = build_source_depth_receipt(state, _broad_observation())

    assert receipt.broad_claim_licensed is False
    assert "target_unit_exclusion_reason_missing:unit:appendix" in receipt.coverage_universe.findings


def test_global_portfolio_does_not_replace_per_gap_portfolio_depth() -> None:
    observation = _broad_observation()
    for anchor in observation.observed_anchors:
        if anchor.source_id == "s-independent":
            anchor.supports = [item for item in anchor.supports if item != "g-direct"]
        if anchor.source_id == "s-limiting":
            anchor.limits = [item for item in anchor.limits if item != "g-direct"]

    receipt = build_source_depth_receipt(_broad_state(), observation)

    assert receipt.broad_claim_licensed is False
    assert "per_gap_portfolio:g-direct:portfolio:independent" in receipt.critical_uncovered_ids
    row = next(item for item in receipt.coverage_universe.object_depth_rows if item.gap_id == "g-direct")
    assert row.status == "fail"


def test_locator_without_anchor_content_cannot_satisfy_broad_object_depth() -> None:
    observation = _broad_observation()
    for anchor in observation.observed_anchors:
        anchor.normalized_summary = ""
        anchor.text = ""

    receipt = build_source_depth_receipt(_broad_state(), observation)

    assert receipt.broad_claim_licensed is False
    assert all(item.status == "fail" for item in receipt.coverage_universe.object_depth_rows)
    rows = receipt.coverage_universe.object_depth_rows
    assert all(
        "sourceguard_blocked:contentless-anchor" in item.findings for item in rows
    )
    assert all(
        any(finding.startswith("missing_portfolio_classes:") for finding in item.findings)
        for item in rows
    )
    assert all("independent_lineage_floor_not_met" in item.findings for item in rows)


def test_missing_lineage_is_not_treated_as_independent_source_identity() -> None:
    observation = _broad_observation()
    for source in observation.observed_sources:
        source.lineage_id = ""

    receipt = build_source_depth_receipt(_broad_state(), observation)

    assert receipt.broad_claim_licensed is False
    dimensions = {item.dimension_id: item for item in receipt.coverage_universe.dimensions}
    assert dimensions["explicit_lineage_sources"].coverage_ratio == 0.0
    assert dimensions["per_gap_lineages"].coverage_ratio == 0.0


def test_broad_empty_universe_fails_closed() -> None:
    receipt = build_source_depth_receipt(
        _guard(
            BeliefState(depth_policy=SourceDepthPolicy(requested_claim_scope="broad")),
            "test-empty-broad",
        ),
        Observation(observation_id="obs-empty"),
    )

    assert receipt.broad_claim_licensed is False
    assert receipt.adequacy_status == "fail"
    assert "gaps_required_universe_empty" in receipt.coverage_universe.findings
    assert "branches_required_universe_empty" in receipt.coverage_universe.findings


def test_coverage_universe_fingerprint_changes_when_authoritative_gap_changes() -> None:
    first = build_source_depth_receipt(_broad_state(), _broad_observation())
    changed = _broad_state()
    changed.gaps.append(
        Gap(
            gap_id="g-bridge",
            lead_id="l-broad",
            gap_type="missing_bridge_evidence",
            importance=0.8,
            blocking=True,
        )
    )
    changed = _guard(changed, "test-coverage-fingerprint-change")
    second = build_source_depth_receipt(changed, _broad_observation())

    assert first.coverage_universe.universe_fingerprint != second.coverage_universe.universe_fingerprint
    assert second.broad_claim_licensed is False
    assert "gaps:g-bridge" in second.critical_uncovered_ids


def test_v2_skillguard_binds_native_receipt_without_parallel_planner() -> None:
    control = (
        Path(__file__).resolve().parents[2]
        / "skills"
        / "sourceguard"
        / ".skillguard"
    )
    source = json.loads((control / "contract-source.json").read_text(encoding="utf-8"))
    manifest = json.loads((control / "check-manifest.json").read_text(encoding="utf-8"))
    checks = {item["check_id"]: item for item in source["checks"]}
    manifest_ids = {item["check_id"] for item in manifest["checks"]}

    assert set(checks) == manifest_ids == {
        "check:sourceguard:consumer-contract",
        "check:sourceguard:native-tests",
    }
    assert source["maintenance_unit_id"] == "unit:researchguard-suite"
    assert source["integration_mode"] == "native-integrated"
    assert source["may_define_parallel_execution_route"] is False
    assert source["may_define_skillguard_runtime_route"] is False
    assert [row["profile_id"] for row in source["closure_profiles"]] == [
        "enforced",
    ]
    assert "v1_runtime_authority" not in source
    assert not (control / "work-contract.json").exists()
    assert not (control / "check_manifest.json").exists()
