"""Saved-original capture and quote matching; source bytes are not a truth verdict."""
from __future__ import annotations

from functools import lru_cache
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


@lru_cache(maxsize=32)
def _heading_spans(raw):
    lines=raw.splitlines(keepends=True);result=[];offset=0
    for i,line in enumerate(lines):
        stripped=line.strip()
        if line.lstrip().startswith("#"):
            result.append((line.lstrip("# ").strip(),offset))
        elif i+1<len(lines) and re.fullmatch(r"[=~`^:+*#-]{3,}",lines[i+1].strip()) and stripped:
            if not re.fullmatch(r"[=~`^:+*#-]{3,}",stripped):
                result.append((stripped,offset))
        offset+=len(line)
    return tuple(result)


def _headings(raw):
    return [heading for heading,_ in _heading_spans(raw)]


@lru_cache(maxsize=32)
def _prepared_capture(raw, word_match):
    normal = (lambda value: re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", normalize_text(value))).strip().casefold()) if word_match else normalize_text
    headings=dict((offset,(i,h)) for i,(h,offset) in enumerate(_heading_spans(raw)))
    offset=0;length=0;placed=[]
    for line in raw.splitlines(keepends=True):
        normalized=normal(line)
        if offset in headings:
            index,heading=headings[offset]
            placed.append((length+(1 if length and normalized else 0),index,heading))
        if normalized:
            length+=len(normalized)+(1 if length else 0)
        offset+=len(line)
    context=normalize_text(raw)
    return normal(raw),placed,context,tuple((m.start(),m.end()) for m in re.finditer(r"\w+",context)) if word_match else ()


def match_quote(capture_text, quote, *, word_match=False):
    """Return normalized-text offsets, omitted text and local context, or None.

    Ellipsis parts must occur in order with at most 300 characters between parts.
    Offsets refer to `normalized_text`, which is returned with the match.
    """
    normal = (lambda value: re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", normalize_text(value))).strip().casefold()) if word_match else normalize_text
    q=normal(quote)
    if not q:
        return None
    parts=[normal(p) for p in re.split(r"\s*(?:\[\s*\.\.\.\s*\]|\.\.\.|…)\s*",quote) if normal(p)]
    variants=[capture_text,re.sub(r"(?<=[A-Za-z])-[ \t]*\n[ \t]*(?=[a-z])","",capture_text),
              re.sub(r"(?<=[A-Za-z])-[ \t]*\n[ \t]*(?=[A-Za-z])","-",capture_text)]
    pep=re.search(r"(?mi)^Title:\s*(.+)$",capture_text)
    h1=re.search(r"(?m)^#\s+(.+)$",capture_text)
    headings=_heading_spans(capture_text)
    title=pep[1].strip() if pep else h1[1].strip() if h1 else headings[0][0] if headings else next(
        (line.strip() for line in capture_text.splitlines() if line.strip() and not re.fullmatch(r"[=~`^:+*#-]+",line.strip())),"")
    for raw in variants:
        text,heading_positions,context_text,context_tokens=_prepared_capture(raw,word_match)
        start=text.find(parts[0])
        while start>=0:
            pos=start+len(parts[0]); omitted=[]
            for part in parts[1:]:
                nxt=text.find(part,pos)
                if nxt<0 or nxt-pos>300:
                    break
                omitted.append(text[pos:nxt].strip());pos=nxt+len(part)
            else:
                heading="";heading_index=None
                for found,index,h in heading_positions:
                    if found<=start:
                        heading=h;heading_index=index
                context_start=start;context_end=pos
                if word_match:
                    first=len(text[:start].split());last=len(text[:pos].split())-1
                    context_start=context_tokens[first][0];context_end=context_tokens[last][1]
                return {"context_text":context_text,"context_start":context_start,"context_end":context_end,
                        "start":start,"end":pos,"omitted_words":omitted,"title":title,
                        "heading":heading,"heading_index":heading_index,"section":heading,
                        "normalized_text":text,"text":text[start:pos]}
            start=text.find(parts[0],start+1)
    return None


def capture_passage(text, quote, *, word_match=False):
    """Return the title and nearest heading's passage containing the matched quote."""
    matched=match_quote(text,quote,word_match=word_match)
    if matched is None:
        return None
    spans=_heading_spans(text);index=matched["heading_index"]
    raw_start=spans[index][1] if index is not None else 0
    raw_end=(spans[index+1][1] if index+1<len(spans) else len(text)) if index is not None else (spans[0][1] if spans else len(text))
    raw_text=text[raw_start:raw_end]
    return {**matched,"text":normalize_text(raw_text),"raw_text":raw_text}


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
    legacy=project/"tools/captures.yaml"
    if not legacy.exists():
        legacy=project/"captures.yaml"
    if legacy.exists() and not (project/"captures.json").exists():
        manifest=yaml.safe_load(legacy.read_text()) or {}
        anchor=manifest.get("anchors",{}).get(anchor_id)
        if not anchor:
            return None
        filename=anchor["file"];saved=manifest.get("files",{}).get(filename,{})
        path=project/"captures"/filename
        actual=digest(path);changed=actual.removeprefix("sha256:")!=str(saved.get("sha256","")).removeprefix("sha256:")
        text=path.read_text(encoding="utf-8-sig")
        quoted=match_quote(text,anchor["quote"])
        return {"id":anchor_id,"source_id":saved.get("source_id",filename),"colour":"red" if changed or quoted is None else "green",
                "reason":"capture changed" if changed else "quote not in capture" if quoted is None else "quote found in saved original", "source_digest":actual,
                "quote":anchor["quote"],"text":text,"path":str(path),"kind":"text"}
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


def table_cells(text):
    """Pipe-table cells with their row and merged header labels for writer checks."""
    from .readings import table_rows
    out=[];block=[]
    for line in text.splitlines()+[""]:
        if line.lstrip().startswith("|"):
            block.append(line)
            continue
        if block:
            levels,body=table_rows(block)
            row_labels=[r[0] for r in body]
            level_labels=[sorted({cell for cell in level[1:] if cell}) for level in levels]
            for level in levels:
                for cell in level[1:]:
                    out.append({"text":cell,"sentence":cell,"header":True})
            for row in body:
                for j,cell in enumerate(row):
                    out.append({"text":cell,"sentence":" | ".join(row),"header":j==0,"cell":j>0,
                                "row":row[0],"cols":[lv[j] if j<len(lv) else "" for lv in levels],
                                "row_labels":row_labels,"level_labels":level_labels})
            block=[]
    return out
