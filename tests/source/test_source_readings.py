"""Round14 finite-reader regressions; originals are synthetic handoff fixtures."""
from pathlib import Path
import json
import pytest

from researchguard.research import load_research,research_status
from researchguard.source.capture import capture_passage,load_anchor_capture,match_quote,table_cells
from researchguard.source.readings import (Grid,readings_in,same_reading,split_clauses,unit_info,CaptureScreen)

FIXTURES=Path(__file__).resolve().parents[1]/"fixtures/source_readings"
EXPECTED = json.loads((FIXTURES / 'expected.json').read_text())['seeds']


@pytest.mark.parametrize('name', sorted(EXPECTED))
def test_every_public_seed_matches_the_supplied_source_sensor_colours(name):
    status = research_status(load_research(FIXTURES / name))
    expected = EXPECTED[name]
    sections = {}
    for reading in status['source_checks']:
        sections.setdefault(reading['section'], []).append({'green': 'G', 'red': 'R', 'grey': '.'}[reading['colour']])
    assert sections == expected['sections'], status['source_checks']
    assert int(bool(status['errors'])) == expected['exit'], status['errors']


def test_dc1_merged_headers_and_dc11_last_word_alias(tmp_path):
    path=tmp_path/"grid.csv"
    path.write_text("period,region A,,region B\n,average delay,on time,average delay\nQ1,10,90,30\nQ2,20,80,40\n")
    grid=Grid("s",path,{})
    assert [c.levels for c in grid.columns]==[["region A","average delay"],["region A","on time"],["region B","average delay"]]
    readings,refs,_=grid.walk("region A average delay Q1 10; Q2 20")
    assert [(r,col.index,value.value) for r,col,value in readings]==[(0,1,10),(1,1,20)]
    # An alias is usable only when it identifies one header owner.
    single=tmp_path/"single.csv";single.write_text("period,average delay\nQ1,10\nQ2,20\n")
    grid=Grid("s",single,{})
    assert grid.walk("Q1 delays 10")[0][0][1].label()=="average delay"


def test_dc6_clock_words_and_day_part():
    def time(text):return next(r for r in readings_in(text) if r.kind=="time")
    assert same_reading(time("a quarter past eight in the evening"),time("20:15"))
    assert not same_reading(time("a quarter past eight in the morning"),time("8.15 p.m."))
    assert not any(r.kind=="time" for r in readings_in("3.1 to 2.7"))


def test_dc9_one_day_precision_reader():
    def date(text):return next(r for r in readings_in(text) if r.kind=="date")
    assert same_reading(date("the 3rd of July 2022"),date("2022-07-03"))
    assert not same_reading(date("13 July 2022"),date("2022-07-03"))
    dates=[r.value for r in readings_in("23-29 Mar 2021") if r.kind=="date"]
    assert dates==[(2021,3,23),(2021,3,29)]


def test_dc10_month_and_comma_hardening():
    assert not any(r.kind=="date" for r in readings_in("the market decreased and may recover"))
    assert split_clauses("rates halved, from ~7,000 to 3,500")==["rates halved, from ~7,000 to 3,500"]


def test_dc2_units_have_one_native_owner():
    # Without the optional physical reader, quantities remain explicitly unread.
    if unit_info("kWh") is None:
        assert all(r.unit is None for r in readings_in("1 kWh"))
    else:
        assert same_reading(readings_in("1 kWh")[0],readings_in("3600 kJ")[0])
        assert not same_reading(readings_in("1 m3")[0],readings_in("1 kWh")[0])
    assert unit_info("imaginary-unit-42") is None


def test_shared_writer_capture_keeps_raw_table_and_ellipsis():
    text="# Facts\n## Section\n| year | count |\n| --- | --- |\n| 2024 | 12 |\n## Other\nUnrelated 99."
    passage=capture_passage(text,"2024 | 12")
    assert "\n|" in passage["raw_text"] and "Unrelated" not in passage["raw_text"]
    cells=table_cells(passage["raw_text"])
    value=next(c for c in cells if c["text"]=="12")
    assert value["row"]=="2024" and value["cols"]==["count"]
    assert match_quote("Alpha, NEVER agreed.","alpha ... agreed",word_match=True)["omitted_words"]==["never"]


def test_legacy_writer_capture_manifest(tmp_path):
    import hashlib,yaml
    (tmp_path/"captures").mkdir();(tmp_path/"tools").mkdir()
    raw=b"Original sentence.";(tmp_path/"captures/a.txt").write_bytes(raw)
    (tmp_path/"tools/captures.yaml").write_text(yaml.safe_dump({"files":{"a.txt":{"sha256":hashlib.sha256(raw).hexdigest(),"source_id":"s"}},"anchors":{"a":{"file":"a.txt","quote":"Original sentence."}}}))
    found=load_anchor_capture(tmp_path,"a")
    assert found["text"]==found["quote"]=="Original sentence." and found["colour"]=="green"


def test_writer_capture_bridge_checks_quote_as_well_as_file_hash(tmp_path):
    import hashlib,yaml
    (tmp_path/'captures').mkdir();(tmp_path/'tools').mkdir()
    raw=b'Original sentence.'
    (tmp_path/'captures/a.txt').write_bytes(raw)
    manifest={'files':{'a.txt':{'sha256':hashlib.sha256(raw).hexdigest(),'source_id':'s'}},
              'anchors':{'a':{'file':'a.txt','quote':'Rewritten sentence.'}}}
    (tmp_path/'tools/captures.yaml').write_text(yaml.safe_dump(manifest))
    found=load_anchor_capture(tmp_path,'a')
    assert found['colour']=='red' and found['reason']=='quote not in capture'


def test_all_supplied_seeds_have_explicit_sensor_rows():
    counts={"red":0,"green":0,"grey":0}
    folders=sorted(p.parent for p in FIXTURES.glob("*/*/research.yaml"))
    assert len(folders)>=40
    for folder in folders:
        status=research_status(load_research(folder))
        assert status["source_readings"],folder
        for row in status["source_readings"]:
            assert set(("id","colour","reason","source_digest"))<=row.keys()
            assert row["reason"] and row["colour"] in counts
            counts[row["colour"]]+=1
    assert all(counts.values())


def test_source_reading_settings_join_the_status_input_digest(tmp_path):
    import shutil,yaml
    project=tmp_path/'research'
    shutil.copytree(FIXTURES/'holdout/e0_cycling_control',project)
    before=research_status(load_research(project))
    digests={row['path']:row['sha256'] for row in before['input_digests']}
    assert 'screen.yaml' in digests
    path=project/'screen.yaml'
    data=yaml.safe_load(path.read_text())
    data.setdefault('ai_choices',{})['change_tolerance']=0.01
    path.write_text(yaml.safe_dump(data))
    after=research_status(load_research(project))
    assert next(row['sha256'] for row in after['input_digests'] if row['path']=='screen.yaml')!=digests['screen.yaml']


@pytest.mark.parametrize("name",["s0_control","s5_correct_word"])
def test_good_public_seed_has_no_source_sensor_error(name):
    status=research_status(load_research(FIXTURES/"public"/name))
    assert status["errors"]==[]


def test_known_bad_controls_are_caught():
    for name in ["s1_doubled","s2_numslip"]:
        status=research_status(load_research(FIXTURES/"public"/name))
        assert any(key in error for error in status["errors"] for key in ("change_word_disagrees:","table_cell_disagrees:")),(name,status["errors"])


def test_change_amount_and_partial_percentage_never_false_green():
    for text,ratio,expected in [("fell by 70-75%",0.08,False),("rose by about a third",4/3,True),("fell by more than a fifth",0.819,False)]:
        screen=object.__new__(CaptureScreen)
        assert screen.amount(text,"fell" if ratio<1 else "rose",ratio)[0] is expected
    # DC15: a partially understood percentage clause must remain a grey reading.
    tree=load_research(FIXTURES/"holdout"/"e0_cycling_control")
    screen=CaptureScreen(tree,research_status(tree));screen.check_anchors()
    screen.check_change("logic:x","logic x","Harbour Road rose with growth of 40% between 2022 and 2023",[])
    assert screen.lines[-1][1]==".",screen.lines[-1]


@pytest.mark.parametrize("group,name,prefix",[
    ("new","d1_version_off_by_one","restatement_disagrees:"),
    ("holdout","e4_morning_to_evening","restatement_disagrees:"),
    ("holdout","e6_dropped_digit","restatement_disagrees:"),
    ("holdout","e5_noun_change","change_word_disagrees:"),
    ("new","c4_rounding_changes_claim","change_word_disagrees:"),
])
def test_dc3_restatements_and_dc4_changes(group,name,prefix):
    status=research_status(load_research(FIXTURES/group/name))
    assert any(e.startswith(prefix) for e in status["errors"]),status["source_checks"]
    assert status["verdict"]["errors"]==len(status["errors"])


def test_repeated_heading_words_do_not_retarget_capture_passage():
    text="Release notes\n=============\nWe mention ssl here.\nFree threading\n--------------\nFree mode is supported.\nssl\n---\nOther data 99.\nFree threading\n--------------\nA later section 88."
    passage=capture_passage(text,"Free mode is supported.")
    assert passage["section"]=="Free threading"
    assert "supported" in passage["raw_text"]
    assert "Other data" not in passage["raw_text"] and "88" not in passage["raw_text"]


def test_word_match_keeps_original_speaker_context_offsets():
    raw='A witness said: "I saw it." Jonas Berg replied. Later, Mina left.'
    match=match_quote(raw,"i saw it",word_match=True)
    assert match["context_text"][match["context_start"]:match["context_end"]]=="I saw it"
    assert "Jonas Berg replied." in match["context_text"][match["context_end"]:]


def test_capture_title_skips_rst_overline_and_reads_pep_title():
    text="****************************\nWhat's New In Python 3.13\n****************************\nFree-threaded CPython\n---------------------\nFree mode is supported."
    assert match_quote(text,"Free mode is supported.")["title"]=="What's New In Python 3.13"
    assert match_quote("PEP: 703\nTitle: Optional GIL\n\nThe body.","The body.")["title"]=="Optional GIL"
