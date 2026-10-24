"""One real handoff updates copied provenance, never the author's argument."""
from copy import deepcopy

from researchguard.logic.provenance import content_hash_for
from researchguard.logic.trace_import import sync_trace_bundle


def _bundle():
    return {"schema": "researchguard.trace.logic-handoff.v1", "hypotheses": [{
        "hypothesis_id": "C0", "claim": "Imported claim wording", "role": "primary",
        "supporting_evidence_ids": ["anc-dates"], "opposing_evidence_ids": [], "limiting_evidence_ids": []}],
        "evidence": [{"evidence_id": "anc-dates", "source_id": "src-official", "text": "23 March 2021",
                      "locator": "official section", "source_reference": "https://example.org/current", "source_date": "2021-03-23"}]}


def _existing():
    return {"model": {"id": "hand-built", "root_claim": "C0"}, "nodes": {
        "C0": {"type": "Claim", "text": "The author's claim"},
        "E_dates": {"type": "Evidence", "text": "The author's overview", "provenance": [
            {"origin_kind": "external_source", "source_id": "src-official", "locator": "anc-dates",
             "quote": "3 March 2020", "content_hash": content_hash_for("3 March 2020"),
             "source_reference": "https://example.org/old", "source_date": "2020-03-03",
             "actor": "human", "independence_group": "reviewed-source", "metadata": {"note": "keep"}},
            {"origin_kind": "external_source", "source_id": "src-other", "locator": "another-anchor",
             "quote": "Other source remains unchanged", "content_hash": content_hash_for("Other source remains unchanged")},
        ]}}, "edges": [{"source": "E_dates", "target": "C0", "type": "supports", "note": "hand-built link"}]}


def test_import_handoff_into_refreshes_owned_provenance():
    bundle, existing = _bundle(), _existing()
    before = deepcopy(existing)
    merged, added, updated, conflicts = sync_trace_bundle(bundle, existing)
    assert existing == before
    assert added == {"nodes": [], "edges": []} and updated == {"nodes": ["E_dates"], "edges": []} and conflicts == []
    assert "anc-dates" not in merged["nodes"]
    assert merged["model"] == before["model"] and merged["edges"] == before["edges"]
    assert merged["nodes"]["C0"] == before["nodes"]["C0"]
    node = merged["nodes"]["E_dates"]
    assert node["text"] == "The author's overview"
    assert node["provenance"][1] == before["nodes"]["E_dates"]["provenance"][1]
    row = node["provenance"][0]
    assert row["quote"] == "23 March 2021" and row["content_hash"] == content_hash_for("23 March 2021")
    assert row["source_reference"] == "https://example.org/current" and row["source_date"] == "2021-03-23"
    assert row["actor"] == "human" and row["metadata"] == {"note": "keep"} and row["independence_group"] == "reviewed-source"
    again, added, updated, conflicts = sync_trace_bundle(bundle, merged)
    assert again == merged and added == {"nodes": [], "edges": []} and updated == {"nodes": [], "edges": []} and conflicts == []
    legacy = deepcopy(bundle)
    del legacy["evidence"][0]["source_reference"]
    del legacy["evidence"][0]["source_date"]
    unchanged, _, updated, conflicts = sync_trace_bundle(legacy, merged)
    assert unchanged == merged and updated == {"nodes": [], "edges": []} and conflicts == []
    hash_only = _existing()
    del hash_only["nodes"]["E_dates"]["provenance"][0]["quote"]
    hashed, _, updated, conflicts = sync_trace_bundle(bundle, hash_only)
    record = hashed["nodes"]["E_dates"]["provenance"][0]
    assert "quote" not in record and record["content_hash"] == content_hash_for("23 March 2021")
    assert updated["nodes"] == ["E_dates"] and conflicts == []


def test_sync_reports_identity_conflicts_without_overwriting_authored_nodes():
    existing = _existing()
    existing["nodes"]["anc-dates"] = {"type": "Claim", "text": "An unrelated authored claim owns this id"}
    before = deepcopy(existing)
    merged, added, updated, conflicts = sync_trace_bundle(_bundle(), existing)
    assert conflicts == [{"kind": "nodes", "id": "anc-dates"}]
    assert merged == before and existing == before
    assert added == {"nodes": [], "edges": []} and updated == {"nodes": [], "edges": []}
