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
    merged, added, conflicts = sync_traceguard_seed(state, existing)
    assert added == {'sources': ['src-new'], 'evidence': ['anc-new']}
    assert existing == before
    for key in before:
        if key not in ('sources', 'evidence'):
            assert merged[key] == before[key]
    for key in ('sources', 'evidence'):
        assert merged[key][:-1] == before[key]
    assert conflicts  # Existing enrichment is reported, never overwritten.
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
