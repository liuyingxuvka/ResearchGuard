"""The picture of a conclusion is computed from the folder's models, kept readable, and says what it leaves out."""
import json
import re
import shutil
from pathlib import Path

import pytest

from researchguard.cli import main
from researchguard.picture import MAX_ARROWS, MAX_BOXES, render_picture_markdown, support_picture
from researchguard.research import load_research, research_status
from research_tree_support import EVERGIVEN, _rewrite, folder  # noqa: F401 - shared question fixture

ROOT = Path(__file__).resolve().parents[1]


def _picture(folder, claim):
    tree = load_research(folder)
    return support_picture(tree, research_status(tree), claim)


def test_root_claim_picture_shows_its_blockers_support_and_sources():
    picture = _picture(EVERGIVEN, "h_suez")
    boxes = {row["id"]: row for row in picture["boxes"]}
    assert set(boxes) == {"h_suez", "R_pretrend", "h_demand", "R_h_suez_anc-transpacific", "R_h_suez_anc-unctad-surge",
                          "E_dates", "E_series", "W_capacity", "A_timing", "E_pretrend", "E_transpacific"}
    assert picture["blocked_by"] == sorted(["R_pretrend", "h_demand", "R_h_suez_anc-transpacific", "R_h_suez_anc-unctad-surge"])
    assert boxes["h_suez"]["lines"][-1] == "UNDECIDED 0.16 · licence withhold"
    assert "anc-sca-dates · Suez Canal Authority statements on th..." in boxes["E_dates"]["lines"]
    arrows = {(row["from"], row["to"]): row for row in picture["arrows"]}
    assert arrows[("h_demand", "h_suez")]["label"] == "contradicts · blocks"
    assert arrows[("E_dates", "h_suez")]["label"] == "supports · trace agrees"
    assert arrows[("E_transpacific", "h_suez")] == {"from": "E_transpacific", "to": "h_suez", "relation": "oppose",
                                                    "routes": ["trace"], "style": "trace", "label": "trace: oppose"}
    assert len(picture["boxes"]) <= MAX_BOXES and len(picture["arrows"]) <= MAX_ARROWS
    assert "route states shown as text, not boxes: trace not live; experiment eliminated" in picture["not_drawn"]


@pytest.mark.parametrize("reverse", [False, True])
def test_parallel_relations_are_both_drawn_and_keep_their_trace_labels(tmp_path, reverse):
    folder = tmp_path / "parallel"
    shutil.copytree(EVERGIVEN, folder)

    def parallel(data):
        data["edges"].append({"source": "E_dates", "target": "h_suez", "type": "qualifies", "weight": 0.6})
        if reverse:
            data["edges"].reverse()

    _rewrite(folder, "logic.yaml", parallel)
    picture = _picture(folder, "h_suez")
    arrows = [row for row in picture["arrows"] if (row["from"], row["to"]) == ("E_dates", "h_suez")]
    assert {row["relation"] for row in arrows} == {"supports", "qualifies"}
    assert len(arrows) == 2
    assert {row["label"] for row in arrows} == {"supports · trace agrees", "qualifies · trace says support (routes disagree)"}
    assert all(row["routes"] == ["logic", "trace"] for row in arrows)
    text = render_picture_markdown(picture)
    assert all(f'|"{row["label"]}"|' in text for row in arrows)

    tree = load_research(folder)
    bounded = support_picture(tree, research_status(tree), "h_suez", max_arrows=5)
    assert len(bounded["arrows"]) <= 5
    kept = [row for row in bounded["arrows"] if row["from"] == "E_dates"]
    assert len(kept) in (0, 2)
    if not kept:
        assert any(item.startswith("E_dates ") and "kept out to stay readable" in item for item in bounded["not_drawn"])


def test_the_picture_follows_the_model_not_a_description(tmp_path):
    folder = tmp_path / "changed"
    shutil.copytree(EVERGIVEN, folder)
    _rewrite(folder, "logic.yaml", lambda data: data.update(edges=[edge for edge in data["edges"]
                                                                    if not (edge["source"] == "R_pretrend" and edge["target"] == "h_suez")]))
    picture = _picture(folder, "h_suez")
    assert "R_pretrend" not in picture["blocked_by"]
    assert ("R_pretrend", "h_suez") not in {(row["from"], row["to"]) for row in picture["arrows"]}
    assert any(item.startswith("1 argument nodes that h_suez does not rest on: R_pretrend") for item in picture["not_drawn"])


def test_a_large_argument_is_cut_to_a_readable_size_and_names_what_it_left_out(folder):
    def many(data):
        for index in range(16):
            data["nodes"][f"E{index:02d}"] = {"type": "Evidence", "text": f"Observation {index}",
                "provenance": [{"origin_kind": "external_source", "source_id": "s", "locator": "a", "quote": "Observed text"}]}
            data["edges"].append({"source": f"E{index:02d}", "target": "h", "type": "supports"})

    _rewrite(folder, "logic.yaml", many)
    picture = _picture(folder, "h")
    assert len(picture["boxes"]) == MAX_BOXES
    drawn = {row["id"] for row in picture["boxes"]}
    # The fixture's own evidence node E reaches h through the trace route, so it competes for a box too.
    left = sorted(item for item in ["E", *(f"E{index:02d}" for index in range(16))] if item not in drawn)
    assert len(left) == 17 - (MAX_BOXES - 1)
    assert sorted(line.split(" ")[0] for line in picture["not_drawn"] if "kept out to stay readable" in line) == left
    text = render_picture_markdown(picture)
    assert all(f"- {item} (Evidence → h) — kept out to stay readable" in text for item in left)


def test_a_hypothesis_outside_the_argument_says_so(capsys):
    assert main(["status", str(EVERGIVEN), "--hypothesis", "h_yantian", "--picture", "--json"]) == 0
    picture = json.loads(capsys.readouterr().out)
    assert [row["id"] for row in picture["boxes"]] == ["h_yantian"] and picture["arrows"] == []
    assert picture["not_drawn"][0] == "h_yantian has no node in the logic model, so no argument edges reach it"


def test_an_unnamed_source_is_visible_in_the_picture(tmp_path):
    from test_research_tree_crossref import _add_bare_source_evidence
    folder = tmp_path / "bare"
    shutil.copytree(EVERGIVEN, folder)
    _add_bare_source_evidence(folder)
    boxes = {row["id"]: row for row in _picture(folder, "h_suez")["boxes"]}
    assert "anc-lloyds · src-lloyds names no document · unverifiable source" in boxes["E_lloyds"]["lines"]


def test_picture_options(capsys):
    assert main(["status", str(EVERGIVEN), "--picture", "--candidate", str(EVERGIVEN)]) == 2
    assert "status_options_conflict: --picture cannot be combined with --candidate" in capsys.readouterr().out
    assert main(["status", str(EVERGIVEN), "--picture"]) == 0
    text = capsys.readouterr().out
    assert text.startswith("**What h_suez rests on**\n") and "```mermaid\nflowchart BT\n" in text and "**Not drawn**" in text


def test_the_example_discussion_shows_the_computed_picture(capsys):
    readme = (ROOT / "examples/research/evergiven/README.md").read_text(encoding="utf-8")
    shown = re.search(r"<!-- BEGIN COMPUTED PICTURE: researchguard status examples/research/evergiven --picture -->\n(.*?)<!-- END COMPUTED PICTURE -->",
                      readme, re.S)
    assert shown, "the example README must carry the picture between its markers"
    assert main(["status", str(EVERGIVEN), "--picture"]) == 0
    assert shown.group(1) == capsys.readouterr().out


def test_a_logic_model_that_fails_to_load_is_reported_not_drawn_as_absent(tmp_path, capsys):
    folder = tmp_path / "broken-logic"
    shutil.copytree(EVERGIVEN, folder)
    (folder / "logic.yaml").write_text("nodes: [not, a, mapping]\n", encoding="utf-8")
    assert main(["status", str(folder), "--picture", "--json"]) == 1
    picture = json.loads(capsys.readouterr().out)
    assert picture["boxes"] == [] and picture["arrows"] == []
    assert len(picture["cannot_draw"]) == 1 and picture["cannot_draw"][0].startswith("model_invalid:logic: ")
    assert main(["status", str(folder), "--picture"]) == 1
    text = capsys.readouterr().out
    assert text.startswith("**What h_suez rests on: not drawn**\n") and picture["cannot_draw"][0] in text
    assert "```mermaid" not in text and "not in the logic route" not in text and "has no node in the logic model" not in text


def test_an_anchor_the_source_model_does_not_hold_is_not_drawn_as_source_support(tmp_path):
    folder = tmp_path / "made-up-anchor"
    shutil.copytree(EVERGIVEN, folder)

    def made_up(data):
        for record in data["nodes"]["E_series"]["provenance"]:
            record["locator"] = "anc-made-up"

    _rewrite(folder, "logic.yaml", made_up)
    picture = _picture(folder, "h_suez")
    lines = {row["id"]: row for row in picture["boxes"]}["E_series"]["lines"]
    assert "anc-made-up: not an anchor of src-drewry-wci in the source model" in lines
    assert not any("Drewry" in line for line in lines)
    problem = "dangling_anchor:logic:E_series:anc-made-up (source src-drewry-wci)"
    assert {"level": "error", "text": problem} in picture["problems"]
    text = render_picture_markdown(picture)
    assert "**Problems in what is drawn**" in text and f"- error {problem}" in text


def test_anchors_are_not_checked_when_the_source_model_fails_to_load(tmp_path):
    folder = tmp_path / "broken-source"
    shutil.copytree(EVERGIVEN, folder)
    (folder / "source.yaml").write_text("sources: 7\n", encoding="utf-8")
    picture = _picture(folder, "h_suez")
    lines = {row["id"]: row for row in picture["boxes"]}["E_dates"]["lines"]
    assert "anc-sca-dates: not checked, the source model failed to load" in lines
    assert any(row["text"].startswith("model_invalid:source: ") for row in picture["problems"])


def test_a_failed_trace_route_is_named_in_the_picture(tmp_path):
    folder = tmp_path / "broken-trace"
    shutil.copytree(EVERGIVEN, folder)
    (folder / "trace.yaml").write_text("events: 7\n", encoding="utf-8")
    picture = _picture(folder, "h_suez")
    assert not any("trace" in row["routes"] for row in picture["arrows"])
    assert any(row["text"].startswith("model_invalid:trace: ") for row in picture["problems"])
    assert "the trace route's evidence directions: the trace model failed to load" in picture["not_drawn"]


def _flagged(picture):
    return {row["id"] for row in picture["boxes"] if row["problem"]}


def test_a_warning_about_the_anchor_or_source_of_a_drawn_evidence_box_marks_that_box(tmp_path):
    # Review round 3: anchor_locator_names_no_place:anc-sca-dates was listed under Problems, but the
    # E_dates box that shows anc-sca-dates was drawn as if nothing were wrong.
    folder = tmp_path / "placeless-locator"
    shutil.copytree(EVERGIVEN, folder)
    _rewrite(folder, "source.yaml", lambda data: next(row for row in data["anchors"]
                                                      if row["anchor_id"] == "anc-sca-dates").update(locator="colleague"))
    picture = _picture(folder, "h_suez")
    warning = "anchor_locator_names_no_place:anc-sca-dates (locator 'colleague' in src-sca-2021)"
    assert {"level": "warning", "text": warning} in picture["problems"]
    assert "E_dates" in _flagged(picture) and "E_series" not in _flagged(picture)
    ids = {row["id"]: f"n{index}" for index, row in enumerate(picture["boxes"])}
    assert re.search(rf"^  class (\S+,)?{ids['E_dates']}(,\S+)? problem$", render_picture_markdown(picture), re.M)
    # A warning about a source marks every drawn box that shows an anchor of that source.
    folder = tmp_path / "bad-link"
    shutil.copytree(EVERGIVEN, folder)
    _rewrite(folder, "source.yaml", lambda data: next(row for row in data["sources"]
                                                      if row["source_id"] == "src-drewry-wci").update(url="x"))
    picture = _picture(folder, "h_suez")
    assert any(row["text"].startswith("source_identity_invalid:src-drewry-wci ") for row in picture["problems"])
    assert "E_series" in _flagged(picture) and "E_dates" not in _flagged(picture)


def test_a_source_named_only_in_the_details_of_a_warning_marks_no_box(tmp_path):
    # The warning is about anc-late, which is not drawn; it mentions src-sca-2021 only to say what it is
    # compared with, so the E_dates box filed under that source is listed with it but not marked.
    folder = tmp_path / "late-quote"
    shutil.copytree(EVERGIVEN, folder)
    _rewrite(folder, "source.yaml", lambda data: data["anchors"].append(
        {"anchor_id": "anc-late", "source_id": "src-sca-2021", "locator": "para 9", "text": "Rates doubled in April 2021."}))
    picture = _picture(folder, "h_suez")
    warning = "anchor_after_source_date:anc-late (the quote names April 2021; src-sca-2021 is dated 2021-03-29)"
    assert {"level": "warning", "text": warning} in picture["problems"]
    assert "E_dates" not in _flagged(picture)


def test_an_unverifiable_source_is_dashed_in_the_picture(tmp_path):
    from test_research_tree_crossref import _add_titled_source_evidence
    folder = tmp_path / "titled"
    shutil.copytree(EVERGIVEN, folder)
    _add_titled_source_evidence(folder, "Colleague's note, 2021", "email 2021")
    picture = _picture(folder, "h_suez")
    box = {row["id"]: row for row in picture["boxes"]}["E_lloyds"]
    assert "anc-lloyds · Colleague's note, 2021 · unverifiable source" in box["lines"]
    assert box["problem"]
    assert any(row["text"].startswith("unverifiable_source:src-lloyds (") for row in picture["problems"])


def _add_second_record(folder, anchor, source=None):
    """Give E_dates a second provenance record, citing ``anchor`` (and adding ``source`` when given)."""
    def add_anchor(data):
        if source is not None:
            data["sources"].append(source)
        data["anchors"].append(anchor)

    _rewrite(folder, "source.yaml", add_anchor)
    _rewrite(folder, "logic.yaml", lambda data: data["nodes"]["E_dates"]["provenance"].append(
        {"origin_kind": "external_source", "source_id": anchor["source_id"], "locator": anchor["anchor_id"], "quote": anchor["text"]}))


def test_every_provenance_record_of_a_drawn_evidence_box_counts(tmp_path):
    # Review round 4: only the first provenance record of an evidence node was read, so an unverifiable
    # second anchor and a warning naming only a second anchor left E_dates drawn as if nothing were wrong.
    folder = tmp_path / "second-note"
    shutil.copytree(EVERGIVEN, folder)
    _add_second_record(folder, {"anchor_id": "anc-note", "source_id": "src-note", "locator": "email 2021",
                                "text": "The canal reopened on 29 March 2021."},
                       {"source_id": "src-note", "title": "Colleague's note, 2021"})
    picture = _picture(folder, "h_suez")
    box = {row["id"]: row for row in picture["boxes"]}["E_dates"]
    assert "anc-sca-dates · Suez Canal Authority statements on th..." in box["lines"]
    assert "anc-note · Colleague's note, 2021 · unverifiable source" in box["lines"]
    assert any(row["text"].startswith("unverifiable_source:src-note (") for row in picture["problems"])
    assert "E_dates" in _flagged(picture) and "E_series" not in _flagged(picture)
    folder = tmp_path / "second-late"
    shutil.copytree(EVERGIVEN, folder)
    _add_second_record(folder, {"anchor_id": "anc-sca-extra", "source_id": "src-sca-2021", "locator": "para 9",
                                "text": "Rates doubled in April 2021."})
    picture = _picture(folder, "h_suez")
    warning = "anchor_after_source_date:anc-sca-extra (the quote names April 2021; src-sca-2021 is dated 2021-03-29)"
    assert {"level": "warning", "text": warning} in picture["problems"]
    assert "E_dates" in _flagged(picture) and "E_series" not in _flagged(picture)
    ids = {row["id"]: f"n{index}" for index, row in enumerate(picture["boxes"])}
    assert re.search(rf"^  class (\S+,)?{ids['E_dates']}(,\S+)? problem$", render_picture_markdown(picture), re.M)
    # A record that names a source but no anchor counts too.
    folder = tmp_path / "second-source-only"
    shutil.copytree(EVERGIVEN, folder)
    _rewrite(folder, "source.yaml", lambda data: data["sources"].append({"source_id": "src-note", "title": "Colleague's note, 2021"}))
    _rewrite(folder, "logic.yaml", lambda data: data["nodes"]["E_dates"]["provenance"].append(
        {"origin_kind": "external_source", "source_id": "src-note", "quote": "The canal reopened on 29 March 2021."}))
    picture = _picture(folder, "h_suez")
    box = {row["id"]: row for row in picture["boxes"]}["E_dates"]
    assert "no anchor named · Colleague's note, 2021 · unverifiable source" in box["lines"]
    assert any(row["text"].startswith("unverifiable_source:src-note (") for row in picture["problems"])
    assert "E_dates" in _flagged(picture)


def test_provenance_without_a_source_id_is_drawn_and_marked_without_inventing_a_source(tmp_path):
    cases = [(0, "Colleague said so", "email", "email · Colleague said so"),
             (1, "Colleague said so", "email", "email · Colleague said so"),
             (1, "Colleague said so", "", "no locator named · Colleague said so")]
    for index, (position, reference, locator, shown) in enumerate(cases):
        folder = tmp_path / f"unlinked-{index}"
        shutil.copytree(EVERGIVEN, folder)
        record = {"origin_kind": "external_source", "source_reference": reference,
                  "locator": locator, "quote": "The canal reopened on 29 March 2021."}
        _rewrite(folder, "logic.yaml", lambda data: data["nodes"]["E_dates"]["provenance"].insert(position, record))
        source_before = (folder / "source.yaml").read_bytes()
        picture = _picture(folder, "h_suez")
        box = {row["id"]: row for row in picture["boxes"]}["E_dates"]
        assert shown + " · names no source in the source model" in box["lines"]
        assert "anc-sca-dates · Suez Canal Authority statements on th..." in box["lines"]
        assert "E_dates" in _flagged(picture) and "E_series" not in _flagged(picture)
        assert any(row["text"].startswith("provenance_names_no_source:E_dates") for row in picture["problems"])
        text = render_picture_markdown(picture)
        assert shown in text and "names no source in the source model" in text
        assert (folder / "source.yaml").read_bytes() == source_before
