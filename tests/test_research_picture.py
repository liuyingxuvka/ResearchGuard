"""The picture of a conclusion is computed from the folder's models, kept readable, and says what it leaves out."""
import json
import re
import shutil
from pathlib import Path

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
    assert "anc-lloyds · src-lloyds: no title, url or date" in boxes["E_lloyds"]["lines"]


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
