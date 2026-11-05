"""Saved-original capture and quote matching; source bytes are not a truth verdict."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import yaml


def digest(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalize_text(text):
    # Join only conventional groups of three; a year is never joined to another number.
    text = re.sub(r"(?<![\d.,])(\d{1,3})((?:[ ,\u2009\u202f\u00a0]\d{3})+)(?!\d)",
                  lambda m: m[1] + re.sub(r"[ ,\u2009\u202f\u00a0]", ",", m[2]), text)
    text = unicodedata.normalize("NFKC", text)
    for a,b in (("‘", "'"),("’", "'"),("“", '\"'),("”", '\"'),("–", "-"),("—", "-"),("−", "-")):
        text=text.replace(a,b)
    return re.sub(r"\s+", " ", text).strip()


def _headings(raw):
    lines=raw.splitlines(); result=[]
    for i,line in enumerate(lines):
        if line.lstrip().startswith("#"):
            result.append(line.lstrip("# ").strip())
        elif i+1<len(lines) and re.fullmatch(r"[=~-]{3,}",lines[i+1].strip()) and line.strip():
            result.append(line.strip())
    return result


def match_quote(capture_text, quote):
    """Return normalized-text offsets, omitted text and local context, or None.

    Ellipsis parts must occur in order with at most 300 characters between parts.
    Offsets refer to `normalized_text`, which is returned with the match.
    """
    q=normalize_text(quote)
    if not q:
        return None
    parts=[p.strip() for p in re.split(r"\s*(?:\[\s*\.\.\.\s*\]|\.\.\.|…)\s*",q) if p.strip()]
    variants=[capture_text,re.sub(r"(?<=[A-Za-z])-[ \t]*\n[ \t]*(?=[a-z])","",capture_text),
              re.sub(r"(?<=[A-Za-z])-[ \t]*\n[ \t]*(?=[A-Za-z])","-",capture_text)]
    title=next((line.lstrip("# ").strip() for line in capture_text.splitlines() if line.strip()),"")
    for raw in variants:
        text=normalize_text(raw); start=text.find(parts[0])
        while start>=0:
            pos=start+len(parts[0]); omitted=[]
            for part in parts[1:]:
                nxt=text.find(part,pos)
                if nxt<0 or nxt-pos>300:
                    break
                omitted.append(text[pos:nxt].strip());pos=nxt+len(part)
            else:
                heading=""
                for h in _headings(raw):
                    where=text.find(normalize_text(h))
                    if 0<=where<=start:
                        heading=h
                return {"start":start,"end":pos,"omitted_words":omitted,"title":title,
                        "heading":heading,"section":heading,"normalized_text":text,"text":text[start:pos]}
            start=text.find(parts[0],start+1)
    return None


def capture_passage(text, quote):
    """Return the title and nearest heading's passage containing the matched quote."""
    matched=match_quote(text,quote)
    if matched is None:
        return None
    normalized=matched["normalized_text"]; start=matched["start"]; end=len(normalized)
    for h in _headings(text):
        at=normalized.find(normalize_text(h),matched["end"])
        if at>=0:
            end=min(end,at)
    heading_at=normalized.rfind(normalize_text(matched["heading"]),0,start+1) if matched["heading"] else 0
    return {**matched,"text":normalized[max(0,heading_at):end]}


def capture_source(project, source_id, *, file=None, url=None):
    """Save a UTF-8 text/CSV original and attach its digest to existing anchors."""
    project=Path(project); project.mkdir(parents=True,exist_ok=True)
    if bool(file)==bool(url):
        raise ValueError("choose exactly one of --file and --url")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+",source_id) or source_id in {".",".."}:
        raise ValueError("source_id must be a simple file-safe identifier")
    if url:
        if urlparse(url).scheme not in {"http","https"}:
            raise ValueError("capture URL must use http or https")
        with urlopen(url,timeout=20) as response:
            payload=response.read()
        origin=url
    else:
        payload=Path(file).read_bytes();origin=str(Path(file).resolve())
    payload.decode("utf-8-sig")  # Explicitly reject unreadable binary/PDF; no fabricated extraction.
    suffix=".csv" if str(file or url).split("?")[0].lower().endswith(".csv") else ".txt"
    relative=Path("captures")/(source_id+suffix);dest=project/relative
    dest.parent.mkdir(exist_ok=True);dest.write_bytes(payload)
    manifest_path=project/"captures.json"
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {"sources":{}}
    row={"table" if suffix==".csv" else "text":relative.as_posix(),"sha256":digest(dest),
         "kind":"url" if url else "file","origin":origin}
    manifest.setdefault("sources",{})[source_id]=row
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    index=project/"research.yaml";source_path=project/"source.yaml"
    if index.exists():
        data=yaml.safe_load(index.read_text()) or {}
        source_path=project/data.get("models",{}).get("source","source.yaml")
    if source_path.exists():
        model=yaml.safe_load(source_path.read_text())
        for a in model.get("anchors",[]):
            if a.get("source_id")==source_id:
                a["source_content_fingerprint"]=row["sha256"]
        source_path.write_text(yaml.safe_dump(model,sort_keys=False,allow_unicode=True),encoding="utf-8")
    return row


def check_captures(project, source):
    """Read captured bytes once; return anchor rows, problems and input paths."""
    project=Path(project);manifest_path=project/"captures.json"
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {"sources":{}}
    rows=[];errors=[];info=[];paths=[manifest_path] if manifest_path.exists() else []
    for anchor in source.anchors if source else ():
        row={"id":anchor.anchor_id,"source_id":anchor.source_id,"colour":"grey",
             "reason":"anchor has no captured original","source_digest":""}
        saved=manifest.get("sources",{}).get(anchor.source_id)
        if not saved:
            info.append("anchor_uncaptured:"+anchor.anchor_id);rows.append(row);continue
        path=project/(saved.get("text") or saved.get("table",""))
        actual=digest(path);paths.append(path);row["source_digest"]=actual
        expected=str(saved.get("sha256","")).removeprefix("sha256:")
        anchored=anchor.source_content_fingerprint.removeprefix("sha256:")
        if actual.removeprefix("sha256:")!=expected or (anchored and anchored!=expected):
            errors.append("capture_changed:"+anchor.source_id)
            row.update(colour="red",reason="capture changed since it was saved")
        elif "table" in saved:
            row["reason"]="captured table requires cell reading"
        else:
            match=match_quote(path.read_text(encoding="utf-8-sig"),anchor.text)
            if match is None:
                errors.append("quote_not_in_capture:"+anchor.anchor_id)
                row.update(colour="red",reason="quote not found in captured original")
            else:
                row.update(colour="green",reason="quote found in captured original",
                           context={"title":match["title"],"heading":match["heading"]},
                           omitted_words=match["omitted_words"])
        rows.append(row)
    return {"rows":rows,"errors":sorted(set(errors)),"info":info,"paths":paths}


def load_anchor_capture(project, anchor_id):
    """Public bridge for writers; return original text, quote and checked status."""
    from .loader import load_model
    project=Path(project)
    index=yaml.safe_load((project/"research.yaml").read_text())
    source=load_model(project/index.get("models",{}).get("source","source.yaml"))
    anchor=next((a for a in source.anchors if a.anchor_id==anchor_id),None)
    if anchor is None:
        return None
    status=next(r for r in check_captures(project,source)["rows"] if r["id"]==anchor_id)
    manifest_path=project/"captures.json"
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {"sources":{}}
    saved=manifest.get("sources",{}).get(anchor.source_id)
    if not saved:
        return {**status,"quote":anchor.text,"text":"","path":""}
    path=project/(saved.get("text") or saved.get("table",""))
    return {**status,"quote":anchor.text,"text":path.read_text(encoding="utf-8-sig"),
            "path":str(path),"kind":"table" if "table" in saved else "text"}
