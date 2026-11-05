from pathlib import Path
from types import SimpleNamespace
import json
import yaml

from researchguard.source.capture import capture_source, check_captures, match_quote, capture_passage
from researchguard.source.cli import main


def anchor(text, fingerprint=""):
    return SimpleNamespace(anchor_id="a",source_id="s",text=text,source_content_fingerprint=fingerprint)


def test_capture_file_hash_quote_and_changed_bytes(tmp_path):
    original=tmp_path/"original.txt";original.write_text("# Source\n## Result\nA circuit used 12\u2009400 units.")
    project=tmp_path/"research";project.mkdir()
    (project/"source.yaml").write_text(yaml.safe_dump({"anchors":[{"anchor_id":"a","source_id":"s","text":"A circuit used 12,400 units."}]}))
    saved=capture_source(project,"s",file=original)
    model=yaml.safe_load((project/"source.yaml").read_text())
    fingerprint=model["anchors"][0]["source_content_fingerprint"]
    assert fingerprint==saved["sha256"]
    source=SimpleNamespace(anchors=[anchor("A circuit used 12,400 units.",fingerprint)])
    checked=check_captures(project,source)
    assert checked["rows"][0]["colour"]=="green"
    assert checked["rows"][0]["context"]=={"title":"Source","heading":"Result"}
    (project/saved["text"]).write_text("changed")
    assert check_captures(project,source)["errors"]==["capture_changed:s"]


def test_dc5_hyphenation_and_digit_grouping():
    assert match_quote("A cir-\ncuit used 12\u202f400 units.","A circuit used 12,400 units.")
    assert match_quote("A cir-\ncuit", "A cir-cuit")
    assert not match_quote("A circuit used 12,400 units.","A circuit used 12,401 units.")


def test_dc7_nearest_heading_not_later_heading():
    text="# Release notes\n## Version 2.4.0\nFix a leak.\n## Version 2.5.0\nLater."
    result=match_quote(text,"Fix a leak.")
    assert result["heading"]=="Version 2.4.0"
    assert "Later" not in capture_passage(text,"Fix a leak.")["text"]
    rst="Release notes\n=============\nVersion 2.4.0\n-------------\nFix a leak."
    assert match_quote(rst,"Fix a leak.")["heading"]=="Version 2.4.0"


def test_dc8_ordered_elision_bounded_and_visible():
    result=match_quote("Alpha never approved beta; the board refused.","Alpha ... beta; the board refused.")
    assert result["omitted_words"]==["never approved"]
    assert not match_quote("Alpha "+"x"*301+" beta","Alpha ... beta")
    assert not match_quote("beta then Alpha","Alpha ... beta")


def test_uncaptured_and_wrong_quote_are_different(tmp_path):
    source=SimpleNamespace(anchors=[anchor("the result")])
    assert check_captures(tmp_path,source)["info"]==["anchor_uncaptured:a"]
    file=tmp_path/"input.txt";file.write_text("another result")
    capture_source(tmp_path,"s",file=file)
    checked=check_captures(tmp_path,source)
    assert checked["errors"]==["quote_not_in_capture:a"]
    assert checked["rows"][0]["colour"]=="red"


def test_capture_cli_and_local_url(tmp_path, capsys, monkeypatch):
    import io
    import researchguard.source.capture as capture
    monkeypatch.setattr(capture,"urlopen",lambda *a,**k:io.BytesIO(b"Saved original"))
    assert main(["capture","s","--url","https://example.org/a.txt","--project",str(tmp_path)])==0
    result=json.loads(capsys.readouterr().out)
    assert result["ok"] and result["kind"]=="url"
    assert (tmp_path/"captures/s.txt").read_text()=="Saved original"


def test_binary_capture_refused_without_text_extraction(tmp_path):
    file=tmp_path/"file.pdf";file.write_bytes(b"\xffbinary")
    import pytest
    with pytest.raises(UnicodeError):
        capture_source(tmp_path,"s",file=file)
