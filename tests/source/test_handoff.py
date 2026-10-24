from researchguard.source.handoff import export_traceguard_seed
from researchguard.source.loader import load_model


def test_export_traceguard_seed_does_not_generate_validated_trace():
    seed = export_traceguard_seed(load_model("examples/source/multimodal_report_video_discovery.yaml"))
    assert seed["events"] == []
    assert seed["traces"] == []
    assert "not validated" in seed["metadata"]["boundary"]


def test_metadata_boundary_exists():
    seed = export_traceguard_seed(load_model("examples/source/starter_researchguard.source.yaml"))
    assert seed["metadata"]["boundary"]


def test_exports_accept_a_model_written_by_an_older_release():
    state = load_model("examples/source/fuel_cell_project_discovery.yaml")
    state.metadata["version"] = "0.5.8"
    assert export_traceguard_seed(state)["metadata"]["source_model_version"] == "0.5.8"


def test_traceguard_seed_loads_as_a_traceguard_model():
    from researchguard.trace.schema import TraceGuardModel
    from researchguard.trace.validation import validate_references

    state = load_model("examples/source/paper_citation_discovery.yaml")
    model = TraceGuardModel.from_dict(export_traceguard_seed(state))
    validate_references(model)
    assert model.sources and model.evidence and not model.traces


def test_export_marks_claim_usable_anchors_as_trace_evidence():
    state = load_model('tests/source/fixtures/evergiven/src_v4.yaml')
    anchor = state.anchors[0]
    anchor.usable_for_trace, anchor.usable_for_claim = False, True
    seed = export_traceguard_seed(state)
    assert next(row for row in seed['evidence'] if row['evidence_id'] == anchor.anchor_id)['usable_as_trace_evidence'] is True


def test_export_into_adds_only_missing_records(tmp_path):
    import copy
    import json
    import yaml
    from researchguard.cli import main
    from researchguard.source.handoff import sync_traceguard_seed
    from researchguard.source.schema import EvidenceAnchor, SourceRecord
    state = load_model('tests/source/fixtures/evergiven/src_v4.yaml')
    state.sources.append(SourceRecord.from_dict({'source_id': 'src-new', 'title': 'New observation'}))
    state.anchors.append(EvidenceAnchor.from_dict({'anchor_id': 'anc-new', 'source_id': 'src-new', 'text': 'New observation'}))
    existing = yaml.safe_load(open('tests/trace/fixtures/evergiven/tr_v1.yaml'))
    before = copy.deepcopy(existing)
    merged, added, updated, conflicts = sync_traceguard_seed(state, existing)
    assert added == {'sources': ['src-new'], 'evidence': ['anc-new']}
    assert existing == before
    for key in before:
        if key not in ('sources', 'evidence'):
            assert merged[key] == before[key]
    from researchguard.ownership import TRACE_ANCHOR_FIELDS, TRACE_SOURCE_FIELDS
    for key, fields in (("sources", TRACE_SOURCE_FIELDS), ("evidence", TRACE_ANCHOR_FIELDS)):
        owned = {field.copy for field in fields}
        for previous, current in zip(before[key], merged[key][:-1]):
            assert {name: value for name, value in previous.items() if name not in owned} == {
                name: value for name, value in current.items() if name not in owned}
    assert set(updated) == {"sources", "evidence"}
    assert conflicts == []  # Enrichment is local work, not an identity clash.
    into = tmp_path / 'into.yaml'
    into.write_text(yaml.safe_dump(existing))
    source = tmp_path / 'source.yaml'
    from researchguard.source.loader import write_yaml
    from researchguard.source.schema import to_plain
    write_yaml(source, to_plain(state))
    data = into.read_bytes()
    assert main(['source', 'export-traceguard', str(source), '--into', str(into), '--output', str(into)]) == 2
    out = tmp_path / 'out.yaml'
    assert main(['source', 'export-traceguard', str(source), '--into', str(into), '--output', str(out)]) == 0
    assert into.read_bytes() == data
    assert yaml.safe_load(out.read_text()) == merged


def test_export_into_refreshes_owned_fields_and_keeps_links():
    from copy import deepcopy
    from researchguard.source.handoff import sync_traceguard_seed
    state = load_model("tests/source/fixtures/evergiven/src_v4.yaml")
    existing = export_traceguard_seed(state)
    anchor = state.anchors[0]
    evidence = next(row for row in existing["evidence"] if row["evidence_id"] == anchor.anchor_id)
    evidence.update(raw_text="wrong copied date", supports=["hand-built-event"], reliability_note="reviewer's note")
    source = next(row for row in existing["sources"] if row["source_id"] == anchor.source_id)
    source.update(title="wrong copied title", source_date="1900-01-01", lineage_id="wrong-lineage")
    source["source_reliability"] = 0.123
    before = deepcopy(existing)
    merged, added, updated, conflicts = sync_traceguard_seed(state, existing)
    assert existing == before
    assert added == {"sources": [], "evidence": []} and conflicts == []
    assert updated == {"sources": [anchor.source_id], "evidence": [anchor.anchor_id]}
    refreshed = next(row for row in merged["evidence"] if row["evidence_id"] == anchor.anchor_id)
    assert refreshed["raw_text"] == (anchor.text or anchor.normalized_summary)
    assert refreshed["supports"] == ["hand-built-event"] and refreshed["reliability_note"] == "reviewer's note"
    actual_source = next(row for row in state.sources if row.source_id == anchor.source_id)
    refreshed_source = next(row for row in merged["sources"] if row["source_id"] == anchor.source_id)
    assert refreshed_source["title"] == actual_source.title
    assert refreshed_source["source_date"] == (actual_source.source_date or None)
    assert refreshed_source["lineage_id"] == (actual_source.lineage_id or actual_source.source_id)
    assert refreshed_source["source_reliability"] == 0.123
    again, added, updated, conflicts = sync_traceguard_seed(state, merged)
    assert again == merged
    assert added == {"sources": [], "evidence": []} and updated == {"sources": [], "evidence": []} and conflicts == []
    wrong = deepcopy(merged)
    other = next(row for row in wrong["evidence"] if row["evidence_id"] == anchor.anchor_id)
    other["source_id"] = "another-source"
    rejected, _, updated, conflicts = sync_traceguard_seed(state, wrong)
    assert conflicts == [{"kind": "evidence", "id": anchor.anchor_id}]
    assert next(row for row in rejected["evidence"] if row["evidence_id"] == anchor.anchor_id)["source_id"] == "another-source"
    assert not updated["evidence"]
