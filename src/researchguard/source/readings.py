"""One source-reading kernel for table anchors, restatements, changes and dates.

Readers retain the finite grammar exercised by Round14 seeds. Unreadable forms
are grey; this module does not decide factual truth or introduce a unit lexicon.
"""
from __future__ import annotations

from functools import lru_cache
import csv

import difflib

import hashlib

import json

import re

import sys

import unicodedata

from datetime import date

from pathlib import Path

import yaml

from researchguard.logic.provenance import coerce_provenance

from researchguard.source.update import times_named
from researchguard.source.capture import match_quote, normalize_text

MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), start=1)}

PART_DAY = {"early": 5, "mid": 15, "late": 25, None: 15}

MONTH_WORD = (r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
              r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")

PERIOD = re.compile(r"\b(?:(early|mid|late)\s+)?" + MONTH_WORD + r"\.?(?:\s+(\d{4}))?\b", re.I)

PAIR = re.compile(PERIOD.pattern + r"\s*(~?)\s*(\d[\d,]*(?:\.\d+)?)\b", re.I)

YEAR_ONLY = re.compile(r"\bin (\d{4})\b")

FACTOR = {"doubled": 2.0, "tripled": 3.0, "quadrupled": 4.0, "halved": 0.5}

DIRECTION = {"rose": 1, "rise": 1, "rising": 1, "risen": 1, "surged": 1, "surging": 1, "increased": 1, "increase": 1,
             "fell": -1, "fall": -1, "dipped": -1, "declined": -1, "decline": -1, "dropped": -1, "drop": -1,
             "decreased": -1, "decrease": -1}

CHANGE = re.compile(r"\b(" + "|".join(list(FACTOR) + list(DIRECTION)) + r")\b", re.I)

NUMBER = re.compile(r"~?\d[\d,]*(?:\.\d+)?")

SEP = "[ ,   ]"

GROUPED = re.compile(rf"(?<![\d.,])(\d{{1,3}})((?:{SEP}\d{{3}})+)(?![\d])")

QUALIFIER = r"(about|around|roughly|nearly|almost|approximately|some|more than|over|at least|less than|under|at most)"

_N = r"~?\s*(\d+(?:\.\d+)?)(?:\s*(?:-|to)\s*(\d+(?:\.\d+)?))?\s*(?:%|per ?cent)"

_VERBS = "|".join(list(DIRECTION) + ["up", "down"])

AMOUNTS = [("by", re.compile(rf"\bby\s+(?:{QUALIFIER}\s+)?{_N}", re.I)),
           ("verb", re.compile(rf"\b({_VERBS})\s+(?:by\s+)?(?:{QUALIFIER}\s+)?{_N}", re.I)),
           ("noun", re.compile(rf"\b(?:an?\s+)?(?:{QUALIFIER}\s+)?{_N}\s+(rise|fall|increase|decrease|drop|decline|jump|gain|reduction)\b", re.I)),
           ("signed", re.compile(r"(?<![\w.])([+-])\s?(\d+(?:\.\d+)?)\s*(?:%|per ?cent)", re.I))]

SIGN_WORDS = {"up": 1, "down": -1, "jump": 1, "gain": 1, "reduction": -1, "+": 1, "-": -1}

FRACTIONS = {"half": 50.0, "a half": 50.0, "a third": 100 / 3, "a quarter": 25.0, "a fifth": 20.0, "a tenth": 10.0,
             "two thirds": 200 / 3, "three quarters": 75.0}

FRACTION = re.compile(rf"\bby\s+(?:{QUALIFIER}\s+)?(" + "|".join(sorted(FRACTIONS, key=len, reverse=True)) + r")\b", re.I)

HOUR_WORDS = {w: i for i, w in enumerate("one two three four five six seven eight nine ten eleven twelve".split(), start=1)}

MIN_WORDS = {"five": 5, "ten": 10, "quarter": 15, "twenty": 20, "twenty-five": 25, "twenty five": 25, "half": 30}

_HOUR = "|".join(HOUR_WORDS) + r"|\d{1,2}"

_HOUR = "|".join(HOUR_WORDS) + r"|\d{1,2}(?![.\d])"

WORD_TIME = re.compile(rf"(?<![\d.])\b(?:(?:a\s+)?(quarter|half|twenty[- ]five|twenty|ten|five|\d{{1,2}}(?=\s+minutes?))(?:\s+minutes?)?\s+(past|to)\s+({_HOUR})\b"
                       rf"|({_HOUR})\s+o'clock\b|(midnight|midday|noon)\b)", re.I)

DIGIT_TIME = re.compile(r"(?<![\d.:/])(\d{1,2})(?::(\d{2})|\.(\d{2})(?=\s*[ap]\.?\s?m\b))(?:\s*([ap])\.?\s?m\b\.?)?(?![\d])", re.I)

VERSION = re.compile(r"(?<![\w.])v?(\d+\.\d+\.\d+)(?![\w]|\.\d)")

ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})(?:-(\d{2}))?\b")

DAY_MONTH = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?" + MONTH_WORD + r"\.?(?:,?\s+(\d{4}))?\b", re.I)

MONTH_DAY = re.compile(r"\b" + MONTH_WORD + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.I)

FISCAL = re.compile(r"\b\d{4}/\d{2}\b")

PLAIN_NUMBER = re.compile(r"(?<![A-Za-z\d.,])(~\s?)?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?![\d]|,\d{3})")

DAY_RANGE = re.compile(r"\b(\d{1,2})\s*-\s*(\d{1,2})\s+" + MONTH_WORD + r"\.?(?:\s+(\d{4}))?\b", re.I)

def group_digits(text: str) -> str:
    """DC5: '12 400', '12,400' and '12 400' are one number; a 4-digit run (a year) is never joined."""
    return GROUPED.sub(lambda m: m[1] + re.sub(SEP, ",", m[2]), text)

def norm(text):
    return normalize_text(text or "")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def num(text: str) -> float:
    return float(text.replace(",", "").lstrip("~"))

def fmt(value: float) -> str:
    return f"{value:,.0f}" if abs(value) >= 100 and value == int(value) else f"{value:,.2f}".rstrip("0").rstrip(".") if abs(value) >= 100 else f"{value:g}"

def pct(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")

def parse_value(cell: str):
    cell = norm(cell)
    return float(cell) if re.fullmatch(r"-?\d+(?:\.\d+)?", cell) else None

@lru_cache(maxsize=1024)
def unit_info(label):
    # PhysicsGuard owns the only unit vocabulary. No implicit download or local copy.
    from importlib.util import find_spec
    if find_spec("physicsguard") is None:
        return None
    from physicsguard.core.units import read_unit
    unit = read_unit(label)
    return (unit.exponents, unit.factor, unit.offset) if unit else None


def unit_of(text):
    return text.strip() if text and unit_info(text.strip()) is not None else None


def find_units(text):
    tokens=list(re.finditer(r"[A-Za-z%°µμ][A-Za-z0-9%°µμ³²/._^-]*(?:-[A-Za-z]+)?",text))
    occupied=-1
    for i, token in enumerate(tokens):
        if token.start()<occupied:
            continue
        for last in reversed(tokens[i:i+5]):
            raw=text[token.start():last.end()]
            if re.search(r"[,;:()\n]",raw):
                continue
            found=unit_of(raw)
            if found:
                yield token.start(),last.end(),found
                occupied=last.end()
                break



class Period:
    def __init__(self, match, default_year=None):
        self.part = (match[1] or "").lower() or None
        self.month = MONTHS[match[2].lower()[:3]]
        self.year = int(match[3]) if match[3] else default_year
        self.text = match[0]

    def day(self):
        return date(self.year or 2000, self.month, PART_DAY[self.part])

    def matches(self, other: "Period") -> bool:
        return (self.month == other.month and (self.year is None or other.year is None or self.year == other.year)
                and (self.part is None or other.part is None or self.part == other.part))

def periods_in(text: str):
    """Month mentions with a sticky year; a lower-case 'may' without a year is the verb."""
    found, year = [], None
    for match in PERIOD.finditer(text):
        if match[2] == "may" and not match[3]:
            continue
        period = Period(match, year)
        year = period.year or year
        found.append((match, period))
    return found

def mentions(text: str) -> list[Period]:
    return [p for _, p in periods_in(text)]

class Clock:
    def __init__(self, minutes, exact, text):
        self.minutes, self.exact, self.text = minutes % 1440, exact, text

    def same(self, other):
        if self.exact and other.exact:
            return self.minutes == other.minutes
        return self.minutes % 720 == other.minutes % 720

    def __str__(self):
        return f"{self.minutes // 60:02d}:{self.minutes % 60:02d}" + ("" if self.exact else " (or +12 h)")

def _hour(word):
    return HOUR_WORDS.get(word.lower()) or int(word)

DAY_PART = re.compile(r"^[^.;!?]{0,40}?(?:\b(morning|afternoon|evening|night)\b|([ap])\.\s?m\.)", re.I)

def _day_part(text, end):
    m = DAY_PART.search(text[end:])
    if not m:
        return None
    return "a" if (m[1] or "").lower() == "morning" or (m[2] or "").lower() == "a" else "p"

def _exact(clock, part):
    if part is None or clock.exact:
        return clock
    return Clock(clock.minutes % 720 + (720 if part == "p" else 0), True, clock.text)

def find_times(text):
    for s, e, clock in _find_times(text):
        yield s, e, _exact(clock, _day_part(text, e))

def _find_times(text):
    for m in WORD_TIME.finditer(text):
        if m[5]:
            minutes = 0 if m[5].lower() == "midnight" else 720
            yield m.start(), m.end(), Clock(minutes, True, m[0])
        elif m[4]:
            yield m.start(), m.end(), Clock(_hour(m[4]) * 60, False, m[0])
        else:
            word = m[1].lower().replace(" ", "-")
            mins = MIN_WORDS.get(word.replace("-", " ")) or MIN_WORDS.get(word) or int(word)
            hour = _hour(m[3])
            total = hour * 60 + mins if m[2].lower() == "past" else hour * 60 - mins
            yield m.start(), m.end(), Clock(total, False, m[0])
    for m in DIGIT_TIME.finditer(text):
        hour, minute = int(m[1]), int(m[2] or m[3])
        if hour > 23 or minute > 59:
            continue
        if m[4]:
            hour = hour % 12 + (12 if m[4].lower() == "p" else 0)
            yield m.start(), m.end(), Clock(hour * 60 + minute, True, m[0])
        else:
            yield m.start(), m.end(), Clock(hour * 60 + minute, hour > 12 or m[1].startswith("0") or hour == 0, m[0])

class Reading:
    def __init__(self, kind, value, text, start, end, unit=None, approx=False, decimals=0, word=None):
        self.kind, self.value, self.text, self.start, self.end = kind, value, text, start, end
        self.unit, self.approx, self.decimals, self.word = unit, approx, decimals, word

    def si(self):
        return self.value * unit_info(self.unit)[1] + unit_info(self.unit)[2] if self.unit else self.value

    def show(self):
        return f"{self.text}" if self.kind != "num" else (f"{'~' if self.approx else ''}{fmt(self.value)}"
                                                         + (f" {self.unit}" if self.unit else ""))

def date_tuple(match_kind, m):
    if match_kind == "iso":
        return (int(m[1]), int(m[2]), int(m[3]) if m[3] else None)
    if match_kind == "dm":
        return (int(m[3]) if m[3] else None, MONTHS[m[2].lower()[:3]], int(m[1]))
    return None

def change_spans(text):
    spans = [m.span() for _, rx in AMOUNTS for m in rx.finditer(text)] + [m.span() for m in FRACTION.finditer(text)]
    return spans + [m.span() for m in re.finditer(r"\b(?:x\s?\d+(?:\.\d+)?|\d+(?:\.\d+)?-fold)\b", text)]

def readings_in(text, masks=(), changes=True):
    """Numbers (with the unit written right after them), clock times, dates, versions in a text.

    Years standing alone, fiscal labels (2019/20) and the change amounts of DC4 are not readings here."""
    text = norm(text)
    out, taken = [], [tuple(span) for span in masks]

    def free(s, e):
        return all(e <= a or s >= b for a, b in taken)

    if changes:  # a change amount is computed in CHANGES; in a quote it stays a reading
        taken += change_spans(text)
    for m in VERSION.finditer(text):
        if free(*m.span()):
            out.append(Reading("version", m[1], m[1], *m.span()))
            taken.append(m.span())
    for m in ISO_DATE.finditer(text):
        if free(*m.span()):
            out.append(Reading("date", date_tuple("iso", m), m[0], *m.span()))
            taken.append(m.span())
    for s, e, clock in find_times(text):
        if free(s, e):
            out.append(Reading("time", clock, clock.text, s, e))
            taken.append((s, e))
    for m in DAY_RANGE.finditer(text):
        if free(*m.span()):
            year = int(m[4]) if m[4] else None
            for day in (m[1], m[2]):
                out.append(Reading("date", (year, MONTHS[m[3].lower()[:3]], int(day)), m[0], *m.span()))
            taken.append(m.span())
    for m in DAY_MONTH.finditer(text):
        if free(*m.span()):
            out.append(Reading("date", date_tuple("dm", m), m[0], *m.span()))
            taken.append(m.span())
    for m in MONTH_DAY.finditer(text):
        if free(*m.span()):
            out.append(Reading("date", (int(m[3]), MONTHS[m[1].lower()[:3]], int(m[2])), m[0], *m.span()))
            taken.append(m.span())
    for m, period in periods_in(text):
        if free(*m.span()):
            out.append(Reading("date", (period.year, period.month, None), m[0], *m.span()))
            taken.append(m.span())
    for m in FISCAL.finditer(text):
        taken.append(m.span())
    units = [u for u in find_units(text) if free(u[0], u[1])]
    for m in PLAIN_NUMBER.finditer(text):
        if not free(*m.span()):
            continue
        value = float(m[2].replace(",", "") + ("." + m[3] if m[3] else ""))
        if not m[3] and not m[1] and len(m[2]) == 4 and 1800 <= value <= 2100:
            continue  # a bare year is not read
        after = next((u for u in units if u[0] >= m.end() and not text[m.end():u[0]].strip()), None)
        word = None if after else (re.match(r"\s*([A-Za-z%°µμ][A-Za-z0-9%°µμ³²/._^-]*)", text[m.end():]) or [None, None])[1]
        if word and word.lower() in {"a", "an", "as", "at", "by", "in", "is", "of", "on", "or", "to"}:
            word = None   # continuation syntax is not an explicit unit label
        out.append(Reading("num", value, m[0].strip(), *m.span(), unit=after[2] if after else None,
                           approx=bool(m[1]), decimals=len(m[3] or ""), word=word.lower() if word else None))
    return sorted(out, key=lambda r: r.start)

def comparable(a: Reading, b: Reading) -> bool:
    """A number with a unit cannot be compared with one followed by a word the unit table cannot read."""
    return not (a.kind == b.kind == "num" and ((a.unit and not b.unit and b.word) or (b.unit and not a.unit and a.word)))

def same_reading(a: Reading, b: Reading) -> bool:
    if a.kind != b.kind:
        return False
    if a.kind == "version":
        return a.value == b.value
    if a.kind == "time":
        return a.value.same(b.value)
    if a.kind == "date":
        return all(x is None or y is None or x == y for x, y in zip(a.value, b.value)) and a.value[1] == b.value[1]
    if a.unit and b.unit:
        if unit_info(a.unit)[0] != unit_info(b.unit)[0]:
            return False
        va, vb, scale = a.si(), b.si(), unit_info(a.unit)[1]
    else:
        va, vb, scale = a.value, b.value, 1.0
    tol = 0.5 * 10 ** (-a.decimals) * scale
    if a.approx or b.approx:
        tol = max(tol, 0.05 * abs(vb))
    return abs(va - vb) <= tol + 1e-9 * abs(vb)

class Series:
    """(period label, value) points of one source, read from its table capture or from an anchor quote."""

    def __init__(self, source_id, points, origin, lane=""):
        self.source_id, self.origin, self.lane = source_id, origin, lane
        self.points = sorted(points, key=lambda p: p[0].day())  # [(Period, value, label)]

    def find(self, period: Period):
        hits = [p for p in self.points if p[0].matches(period)]
        return hits[0] if hits else None

    def before(self, day):
        rows = [p for p in self.points if p[0].day() < day]
        return rows[-1] if rows else None

    def after(self, day):
        return [p for p in self.points if p[0].day() > day]

    def in_year(self, year):
        return [p for p in self.points if p[0].year == year]

class Column:
    def __init__(self, index, levels, unit, numeric):
        self.index, self.levels, self.unit, self.numeric = index, levels, unit, numeric

    def label(self):
        return " ".join(level for level in self.levels if level)

class Grid:
    """A table capture: header rows (merged cells forward-filled), one row-key column, value columns."""

    def __init__(self, source_id, path, cap):
        self.source_id, self.lane, self.origin = source_id, cap.get("lane", ""), "table"
        with path.open(newline="", encoding="utf-8") as handle:
            rows = [r for r in csv.reader(handle) if any(c.strip() for c in r)]
        first_data = next((i for i, r in enumerate(rows) if i and any(parse_value(c) is not None for c in r[1:])), None)
        nhead = first_data if first_data else 1
        header, data = rows[:nhead], rows[nhead:]
        width = max((len(r) for r in rows), default=0)
        filled = []
        for row in header:
            out, last = [], ""
            for c in range(width):
                cell = row[c].strip() if c < len(row) else ""
                last = cell or (last if c else "")
                out.append(cell if c == 0 else last)
            filled.append(out)
        self.header = header
        self.columns = []
        for c in range(1, width):
            levels, unit, raw_unit = [], None, ""
            for out in filled:
                text = out[c]
                m = re.search(r"\(([^)]*)\)", text)
                if m:
                    unit = unit or unit_of(m[1])
                    raw_unit = raw_unit or m[1]
                    text = (text[:m.start()] + text[m.end():]).strip()
                elif out[0].lower() in {"unit", "units"}:
                    unit = unit or unit_of(text)
                    raw_unit = raw_unit or text
                levels.append(text)
            unit = unit or unit_of(cap.get("unit", ""))
            values = [r[c] for r in data if c < len(r) and r[c].strip()]
            column=Column(c, levels, unit, bool(values) and all(parse_value(v) is not None for v in values))
            column.unit_label = raw_unit or cap.get("unit", "")
            self.columns.append(column)
        self.keys = [r[0].strip() for r in data]
        self.cells = {(i, col.index): (data[i][col.index].strip() if col.index < len(data[i]) else "")
                      for i in range(len(data)) for col in self.columns}
        if self.keys and all(PERIOD.fullmatch(k) for k in self.keys):
            self.kind, self.periods = "period", [Period(PERIOD.fullmatch(k)) for k in self.keys]
        elif self.keys and all(ISO_DATE.fullmatch(k) and ISO_DATE.fullmatch(k)[3] for k in self.keys):
            self.kind = "date"
            self.dates = [tuple(int(x) for x in ISO_DATE.fullmatch(k).groups()) for k in self.keys]
        elif self.keys and all(re.fullmatch(r"\d{1,2}:\d{2}", k) for k in self.keys):
            self.kind = "time"
            self.clocks = [Clock(int(k.split(":")[0]) * 60 + int(k.split(":")[1]), True, k) for k in self.keys]
        else:
            self.kind = "label"
        self.nlevels = len(filled)

    def value(self, row, col):
        return parse_value(self.cells[(row, col.index)]) if col.numeric else self.cells[(row, col.index)]

    def label(self, row, col):
        return self.keys[row] if len(self.columns) == 1 else f"{self.keys[row]} {col.label()}"

    def original_unit_basis(self, reading, column, text):
        """A direct cell quote may keep its opaque source label without interpreting it.

        This establishes no conversion: a changed or unrecognized explicit unit
        still needs the PhysicsGuard owner. An omitted unit inherits the already
        selected original column, rather than supplying a different physical unit.
        """
        if reading.unit and not column.unit:
            return False
        if column.unit:
            return not (reading.word and not reading.unit)
        if not column.unit_label:
            return not reading.word
        if not reading.word:
            return True
        tail = text[reading.end:].lstrip()
        label = norm(column.unit_label)
        return tail.startswith(label) and (len(tail) == len(label) or not tail[len(label)].isalnum())

    def resolve(self, levels):
        candidates = [c for c in self.columns if c.numeric] or list(self.columns)
        for level, label in levels.items():
            candidates = [c for c in candidates if c.levels[level].lower() == label]
        return candidates[0] if len(candidates) == 1 else None

    def column_labels(self):
        return {(lv, c.levels[lv].lower()) for c in self.columns for lv in range(self.nlevels) if len(c.levels[lv]) > 1}

    def labels_in(self, low):
        return any(re.search(rf"(?<!\w){re.escape(lab)}(?!\w)", low) for lv, lab in self.column_labels()
                   if not re.fullmatch(r"[\d/]+", lab))

    def events(self, text):
        """Row, column, unit and number mentions in a (normalised) text, in order."""
        ev, taken = [], []
        if self.kind == "period":
            for m, period in periods_in(text):
                idx = next((i for i, p in enumerate(self.periods) if p.matches(period)), None)
                ev.append((m.start(), m.end(), "row", idx, m[0]))
                taken.append(m.span())
        elif self.kind == "date":
            for r in readings_in(text, changes=False):
                if r.kind == "date" and r.value[2] is not None:
                    y, m, d = r.value
                    idx = next((i for i, (yy, mm, dd) in enumerate(self.dates) if (y is None or y == yy) and m == mm and d == dd), None)
                    ev.append((r.start, r.end, "row", idx, r.text))
                    taken.append((r.start, r.end))
        elif self.kind == "time":
            for s, e, clock in find_times(text):
                idx = next((i for i, c in enumerate(self.clocks) if c.same(clock)), None)
                ev.append((s, e, "row", idx, clock.text))
                taken.append((s, e))
        else:
            for i, key in enumerate(self.keys):
                for m in re.finditer(rf"(?<!\w){re.escape(key)}(?!\w)", text, re.I):
                    ev.append((m.start(), m.end(), "row", i, key))
                    taken.append(m.span())
        labels = sorted(self.column_labels(), key=lambda r: -len(r[1]))
        heads = {}
        for level, label in labels:
            head = label.split()[-1] if " " in label else ""
            if len(head) >= 5 and not re.fullmatch(r"[\d/]+", head):
                heads.setdefault((level, head), []).append(label)
        named = []
        for level, label in labels:
            for m in re.finditer(rf"(?<!\w){re.escape(label)}(?!\w)", text, re.I):
                if all(m.end() <= a or m.start() >= b for a, b in taken):
                    ev.append((m.start(), m.end(), "col", (level, label), m[0]))
                    taken.append(m.span())
                    named.append(label)
        for (level, head), owners in heads.items():
            if len(owners) != 1 or owners[0] in named:
                continue
            for m in re.finditer(rf"(?<!\w){re.escape(head)}s?(?!\w)", text, re.I):
                if all(m.end() <= a or m.start() >= b for a, b in taken):
                    ev.append((m.start(), m.end(), "col", (level, owners[0]), m[0]))
                    taken.append(m.span())
        for s, e, unit in find_units(text):
            if all(e <= a or s >= b for a, b in taken):
                ev.append((s, e, "unit", unit, text[s:e]))
                taken.append((s, e))
        for r in readings_in(text, masks=taken):
            if r.kind == "num":
                ev.append((r.start, r.end, "num", r, r.text))
        return sorted(ev, key=lambda row: row[0])

    def walk(self, text, sticky_unit=True):
        """Read a text against the grid: [(row, column, Reading)], the cells it names in order, unknown rows."""
        text = norm(text)
        row, levels, unit, last = None, {}, None, None
        readings, refs, unknown = [], [], []
        for s, e, kind, val, tok in self.events(text):
            if kind == "unit":
                if last is not None and not text[last[2].end:s].strip(" )"):
                    last[2].unit = val
                else:
                    unit = val
                continue
            if kind == "num":
                if sticky_unit and val.unit is None:
                    val.unit = unit
                last = [row, self.resolve(levels), val]
                readings.append(last)
                continue
            last = None
            if kind == "row":
                row = val if val is not None else "unknown"
                if val is None:
                    unknown.append((tok, e))
            else:
                levels[val[0]] = val[1]
            col = self.resolve(levels)
            if isinstance(row, int) and col is not None and (not refs or refs[-1] != (row, col)):
                refs.append((row, col))
        return readings, refs, unknown

    def series(self, col=None):
        col = col or self.resolve({})
        if self.kind != "period" or col is None or not col.numeric:
            return None
        return Series(self.source_id, [(p, self.value(i, col), self.keys[i]) for i, p in enumerate(self.periods)], "table", self.lane)

def quote_series(source_id, text, origin):
    points, year = [], None
    for match in PAIR.finditer(text):
        if match[2] == "may" and not match[3]:
            continue
        period = Period(match, year)
        year = period.year or year
        points.append((period, num(match[5]), match[0].split("~")[0].strip(), match[4] == "~"))
    return points

def own_endpoints(text):
    """The numbers a clause states right after 'from' and 'to' (dates and years are not numbers here)."""
    nums = [r for r in readings_in(text, changes=False) if r.kind == "num"]
    f = re.search(r"\bfrom\s+", text)
    if not f:
        return None
    x = next((r for r in nums if r.start >= f.end() and not text[f.end():r.start].strip("~ ")), None)
    t = re.search(r"\bto\s+", text[x.end:]) if x else None
    y = next((r for r in nums if t and r.start >= x.end + t.end() and not text[x.end + t.end():r.start].strip("~ ")), None)
    return ((x.text, x.value), (y.text, y.value)) if x and y else None

def split_clauses(text):
    """Clauses at ';' and ','; a comma piece without a change word continues the clause before it."""
    out = []
    for part in re.split(r";", text):
        for piece in re.split(r",(?!\d{3}(?!\d))", part):
            if out and out[-1][1] == part and not CHANGE.search(piece):
                out[-1] = (out[-1][0] + "," + piece, part)
            else:
                out.append((piece, part))
    return [c for c, _ in out if c.strip()]

class CaptureScreen:

    def __init__(self, tree, status):
        folder = tree.path.parent
        self.folder = folder
        self.tree = tree
        self.status = status
        self.design = yaml.safe_load((folder / "screen.yaml").read_text()) if (folder / "screen.yaml").is_file() else {}
        caps = json.loads((folder / "captures.json").read_text()) if (folder / "captures.json").is_file() else {"sources": {}}
        self.captures, self.owner = caps.get("sources", {}), caps.get("owner")
        self.lines, self.colour, self.grey_changes = [], {}, []
        self.errors = []
        self.warnings = []
        self.tol = float(self.design.get("ai_choices", {}).get("change_tolerance", 0.25))
        self.source = self.tree.models.get("source")
        self.logic = self.tree.models.get("logic")
        self.trace = self.tree.models.get("trace")
        self.anchors = {a.anchor_id: a for a in (self.source.anchors if self.source else ())}
        self.tables, self.texts = {}, {}
        for source_id, row in self.captures.items():
            path = folder / (row.get("text") or row["table"])
            row["changed"] = sha(path) != str(row["sha256"]).removeprefix("sha256:")
            if "table" in row:
                self.tables[source_id] = Grid(source_id, path, row)
            else:
                self.texts[source_id] = path.read_text(encoding="utf-8-sig")
        self.lanes = {lane: aliases for lane, aliases in self.design.get("lanes", {}).items()}
        self.found = {}         # anchor id -> context lines (DC7) when the quote was found in its capture
        self.quoted = {}

    def add(self, section, colour, text, key=None):
        self.lines.append((section, colour, text))
        if key:
            self.colour[key] = colour
        if colour == "R":
            identifier = key.removeprefix("anchor:") if key else (text.split()[1].rstrip(":") if text.startswith(("logic ","source ")) else text.split()[0])
            if section == "ANCHORS" and "vs table" in text:
                anchor = self.anchors[identifier]
                grid = self.tables.get(anchor.source_id)
                periods = [k for k in grid.keys if k in text] if grid else []
                self.errors.extend(f"table_cell_disagrees:{identifier}:{p}" for p in (periods or ["unknown"]))
            elif section == "CHANGES":
                if text.startswith("source "):
                    other = (re.search(r"table ([^ )]+)", text) or [None,"unknown"])[1]
                    target=self.errors if ", table " in text else self.warnings
                    target.append(f"sources_disagree:{identifier}:{other}")
                else:
                    target=self.errors if ", table " in text else self.warnings
                    target.append("change_word_disagrees:" + identifier)
            elif section == "RESTATEMENTS":
                self.errors.append("restatement_disagrees:" + identifier)
            elif section == "TIMELINE":
                self.errors.append("timeline_disagrees:" + identifier)

    def captured(self, anchor_id):
        a = self.anchors.get(anchor_id)
        return a is not None and a.source_id in self.captures and not self.captures[a.source_id]["changed"]

    def check_anchors(self):
        for anchor in self.anchors.values():
            cap = self.captures.get(anchor.source_id)
            key = f"anchor:{anchor.anchor_id}"
            if cap is None:
                self.add("ANCHORS", ".", f"{anchor.anchor_id} {anchor.source_id}: no capture (AI transcription only)", key)
                continue
            if cap["changed"]:
                self.add("ANCHORS", "R", f"{anchor.anchor_id}: capture of {anchor.source_id} changed after it was recorded", key)
                continue
            if anchor.source_id in self.texts:
                self.check_text_anchor(anchor, self.texts[anchor.source_id], key)
            else:
                self.check_table_anchor(anchor, self.tables[anchor.source_id], cap, key)

    def check_text_anchor(self, anchor, capture, key):
        result = match_quote(capture, anchor.text)
        if result is None:
            self.add("ANCHORS", "R", f"{anchor.anchor_id} quote not in capture of {anchor.source_id}", key)
        else:
            self.found[anchor.anchor_id] = [result["title"], result["heading"]]
            self.add("ANCHORS", "G", f"{anchor.anchor_id} found in capture of {anchor.source_id}", key)

    def check_table_anchor(self, anchor, grid, cap, key):
        problems, unplaced, matched, units, raw_labels = [], [], set(), set(), set()
        readings, refs, unknown = grid.walk(anchor.text)
        text = norm(anchor.text)
        text_cols = [c for c in grid.columns if not c.numeric]
        row_events = [(s, e, val, tok) for s, e, kind, val, tok in grid.events(text) if kind == "row"]
        for n, (s, e, idx, tok) in enumerate(row_events):  # text cells: the words after each row key
            if not text_cols:
                break
            stop = row_events[n + 1][0] if n + 1 < len(row_events) else len(text)
            said = re.split(r";", text[e:stop])[0].strip(" .;,:").lower()
            if idx is None:
                other = next((i for i in range(len(grid.keys)) if any(said and said in str(grid.value(i, c)).lower() for c in text_cols)), None)
                problems.append(f"{tok}: no such row" + (f" ('{said}' is in row {grid.keys[other]})" if other is not None else ""))
                continue
            matched.add(idx)
            cells = " ".join(str(grid.value(idx, c)) for c in text_cols).lower()
            if not said or said not in cells:
                problems.append(f"{grid.keys[idx]}: table '{cells}', quote '{said}'")
        if not text_cols:
            problems += [f"{tok}: no such row" for tok, _ in unknown]
        quoted = {}
        for row, col, r in readings:
            if not text_cols and row == "unknown":
                continue
            if not isinstance(row, int) or col is None or not col.numeric:
                if text_cols and r.decimals == 0 and r.value < 100:
                    continue
                anywhere = [(i, c) for (i, ci), v in grid.cells.items() for c in grid.columns
                            if c.index == ci and c.numeric and parse_value(v) is not None and abs(parse_value(v) - r.value) < 1e-9]
                (unplaced if anywhere else problems).append(f"{r.show()}: " + ("cannot tell which cell" if anywhere else "in no cell of the table"))
                continue
            matched.add(row)
            cell = grid.value(row, col)
            if not grid.original_unit_basis(r, col, text):
                unplaced.append(f"{grid.label(row,col)}: explicit unit cannot be compared with the original {col.unit_label!r}")
                continue
            if col.unit_label and not col.unit:
                raw_labels.add(col.unit_label)
            tolerance = 0.5 * 10 ** (-r.decimals)
            if r.unit and col.unit:
                a,b=unit_info(r.unit),unit_info(col.unit)
                if a[0] != b[0]:
                    problems.append(f"{grid.label(row,col)}: unit {r.unit} differs from {col.unit}")
                else:
                    r.value=(r.value*a[1]+a[2]-b[2])/b[1]
                    tolerance *= abs(a[1] / b[1])
            quoted[(row, col.index)] = r.value
            label = grid.label(row, col)
            off = (abs(cell - r.value) / abs(cell) > 0.05) if r.approx and cell else abs(cell - r.value) > tolerance + 1e-9
            if off:
                hint = next((f" ({fmt(r.value)} is the table's {grid.keys[i]} value)" for i in range(len(grid.keys))
                             if i != row and grid.value(i, col) == r.value), "")
                hint = hint or next((f" ({fmt(r.value)} is the table's {c.label()} value)" for c in grid.columns
                                     if c is not col and c.numeric and grid.value(row, c) == r.value), "")
                problems.append(f"{label}: table {fmt(cell)}, quote {'~' if r.approx else ''}{fmt(r.value)}{hint}")
            if r.word and not r.unit and col.unit:
                unplaced.append(f"{label}: unknown unit or PhysicsGuard unit reader unavailable")
            if col.unit:
                units.add(col.unit)
        self.quoted[anchor.anchor_id] = quoted
        unused = [k for i, k in enumerate(grid.keys) if i not in matched]
        tail = f"; {len(unused)} table rows not quoted" if unused else ""
        n = len(quoted) + (len([1 for s, e, idx, tok in row_events if idx is not None]) if text_cols else 0)
        unit_parts = [", ".join(sorted(units))] if units else []
        if raw_labels:
            unit_parts.append(f"original labels {', '.join(sorted(raw_labels))!r} (no unit conversion)")
        unit = "; ".join(unit_parts) or cap.get("unit")
        if problems:
            self.add("ANCHORS", "R", f"{anchor.anchor_id} vs table {anchor.source_id}: " + "; ".join(problems) + tail, key)
        elif unplaced:
            self.add("ANCHORS", ".", f"{anchor.anchor_id} vs table {anchor.source_id}: " + "; ".join(unplaced) + " (name the row and column)" + tail, key)
        elif not n:
            self.add("ANCHORS", ".", f"{anchor.anchor_id}: no table cell could be read", key)
        else:
            self.add("ANCHORS", "G", f"{anchor.anchor_id} vs table {anchor.source_id}: {n}/{n} cells match, unit {unit}{tail}", key)

    def observation_checks(self):
        """Bind direct literal observations, never infer a semantic outcome label.

        The supported domain is one captured scalar or one explicitly named
        table cell. Numeric labels retain the source unit and existing reading
        precision; enum labels must name the complete captured literal. An
        interpretation such as "similar_rise" remains caller-declared.
        """
        spec = self.tree.models.get("experiment")
        if spec is None:
            return []
        checks = []
        for observation in self.tree.observations:
            row = dict(id=observation.evidence_id, experiment_id=observation.experiment_id,
                       source_ref=observation.source_ref, observed_outcome=observation.observed_outcome,
                       colour="grey", basis="caller_declared", source_digest="",
                       reason="caller-declared outcome; no unique captured literal verifies this label")
            checks.append(row)
            anchor = self.anchors.get(observation.evidence_id)
            if (observation.status != "valid" or anchor is None
                    or anchor.source_id != observation.source_ref or not self.captured(anchor.anchor_id)
                    or self.colour.get("anchor:" + anchor.anchor_id) != "G"):
                continue
            row["source_digest"] = self.captures[anchor.source_id]["sha256"]
            labels = {prediction.outcomes_by_experiment[observation.experiment_id]
                      for prediction in spec.hypothesis_predictions
                      if observation.experiment_id in prediction.outcomes_by_experiment}
            actual, basis, unit = None, "captured_scalar_literal", ""
            if anchor.source_id in self.tables:
                grid = self.tables[anchor.source_id]
                _, refs, unknown = grid.walk(anchor.text)
                if len(refs) != 1 or unknown:
                    continue
                index, column = refs[0]
                actual = grid.value(index, column)
                unit = column.unit_label
                basis = "captured_table_literal"
            else:
                readings = readings_in(anchor.text, changes=False)
                if len(readings) == 1 and readings[0].kind == "num":
                    actual = readings[0]
                elif not readings:
                    actual = anchor.text
            if actual is None:
                continue
            numeric = {label: parse_value(label) for label in labels}
            if isinstance(actual, (int, float)):
                actual = Reading("num", actual, str(actual), 0, len(str(actual)),
                                 decimals=len(str(actual).partition(".")[2]))
            if isinstance(actual, Reading) and all(value is not None for value in numeric.values()):
                matches = [label for label, value in numeric.items()
                           if same_reading(Reading("num", value, label, 0, len(label),
                                                   decimals=len(label.partition(".")[2])), actual)]
                # Distinct textual labels for the same reported measurement do
                # not establish an independently distinguishable observation.
                if len(matches) > 1:
                    row["reason"] = "caller-declared outcome; multiple labels describe the same captured reading"
                    continue
            elif isinstance(actual, str):
                matches = [label for label in labels if norm(label).casefold() == norm(actual).casefold()]
                if len(matches) != 1:
                    continue
            else:
                continue
            if not matches or observation.observed_outcome != matches[0]:
                row.update(colour="red", basis=basis,
                           reason=f"outcome {observation.observed_outcome!r} disagrees with captured literal {actual.show() if isinstance(actual, Reading) else actual!r}")
                self.errors.append(f"experiment_outcome_disagrees:{observation.experiment_id}:{observation.evidence_id}")
            else:
                row.update(colour="green", basis=basis,
                           reason=f"outcome {observation.observed_outcome!r} matches one captured literal" +
                                  (f" in original unit {unit}; no conversion" if unit else ""))
        return checks

    def event_day(self, event_id):
        for event in (self.trace.events if self.trace else ()):
            if event.event_id == event_id:
                for evidence_id in event.evidence_ids:
                    named = times_named(self.anchors[evidence_id].text) if evidence_id in self.anchors else []
                    if named:
                        return named[0][1], f"{named[0][0]} from {evidence_id}"
        return None, ""

    def table_for(self, clause, attached):
        low = norm(clause).lower()
        named = [lane for lane, aliases in self.lanes.items() if any(alias in low for alias in aliases)]
        if named:
            tables = [g for g in self.tables.values() if g.lane in named]
            if tables:
                return tables[0]
        tabs = {self.anchors[a].source_id for a in attached if self.captured(a) and self.anchors[a].source_id in self.tables}
        if len(tabs) == 1:
            return self.tables[tabs.pop()]
        if len(tabs) > 1:
            return None
        hits = [g for g in self.tables.values() if not self.captures[g.source_id]["changed"] and g.labels_in(low)]
        return hits[0] if len(hits) == 1 else None

    def uncaptured_series(self, clause, attached):
        candidates = [a for a in attached if a in self.anchors and quote_series(self.anchors[a].source_id, self.anchors[a].text, "q")]
        if len(candidates) == 1:
            anchor = self.anchors[candidates[0]]
            return Series(anchor.source_id, [(p, v, l) for p, v, l, _ in quote_series(anchor.source_id, anchor.text, "q")], "AI copy (no capture)")
        return None

    def window(self, clause, series):
        low = clause.lower()
        terms = self.design.get("terms", {})
        event_term = next((t for t in terms if re.search(rf"\b{t}\b", low)), None)
        day, day_note = self.event_day(terms[event_term]) if event_term else (None, "")
        found = [series.find(m) for m in mentions(clause)]
        found = sorted((f for f in found if f), key=lambda p: p[0].day())
        if len(found) >= 2:
            return found[0], found[-1], ""
        year = YEAR_ONLY.search(clause)
        if not found and year and series.in_year(int(year[1])):
            rows = series.in_year(int(year[1]))
            return rows[0], rows[-1], ""
        if day is not None:
            base = series.before(day)
            if len(found) == 1 and found[0][0].day() > day:
                return base, found[0], f"baseline = last point before {day_note}"
            if re.search(rf"\bbefore (the )?{event_term}", low):
                return series.points[0], base, f"to the last point before {day_note}"
            if re.search(rf"\bafter (the )?{event_term}", low) and series.after(day):
                return base, series.after(day)[0], f"first point after {day_note}"
        return None, None, "name both periods"

    def amount(self, clause, word, ratio):
        """DC4: the stated size of the change, checked against the computed ratio. None when none is stated."""
        text = norm(clause)
        found = None
        for kind, rx in AMOUNTS:
            m = rx.search(text)
            if m:
                g = m.groups()
                if kind == "by":
                    found = (g[0], g[1], g[2], word)
                elif kind == "verb":
                    found = (g[1], g[2], g[3], g[0].lower())
                elif kind == "noun":
                    found = (g[0], g[1], g[2], g[3].lower())
                else:
                    found = (None, g[1], None, g[0])
                break
        f = FRACTION.search(text) if not found else None
        if not (found or f):
            return None
        qualifier = ((found[0] if found else f[1]) or "").lower()
        low = float(found[1]) if found else FRACTIONS[f[2].lower()]
        high = float(found[2]) if found and found[2] else None
        decimals = len(found[1].split(".")[1]) if found and "." in found[1] else 0
        direction = DIRECTION.get(found[3], SIGN_WORDS.get(found[3], DIRECTION.get(word, 1))) if found else DIRECTION.get(word, 1)
        change = (ratio - 1) * 100
        sign_ok = change * direction > 0
        size = abs(change)
        if high is not None:
            ok, said = low - 0.5 <= size <= high + 0.5, f"{pct(low)}-{pct(high)}%"
        elif qualifier in ("more than", "over"):
            ok, said = size > low, f"more than {pct(low)}%"
        elif qualifier == "at least":
            ok, said = size >= low, f"at least {pct(low)}%"
        elif qualifier in ("less than", "under"):
            ok, said = size < low, f"less than {pct(low)}%"
        elif qualifier == "at most":
            ok, said = size <= low, f"at most {pct(low)}%"
        elif qualifier or f:
            ok, said = abs(size - low) <= max(1.0, 0.05 * low), f"about {pct(low)}%"
        else:
            ok, said = abs(size - low) <= 0.5 * 10 ** (-decimals) + 1e-9, f"{pct(low)}%"
        return ok and sign_ok, f"said {said}, computed {change:+.1f}%"

    def check_change(self, owner_key, who, text, attached, hypotheses=()):
        for clause in split_clauses(text):
            word = CHANGE.search(clause)
            signed = None if word else next((m for _, rx in AMOUNTS[1:] for m in [rx.search(norm(clause))] if m), None)
            if not word and not signed:
                continue
            word = word[1].lower() if word else "rise"
            label = f'{who} "{norm(clause).strip()[:70]}"'
            grey = who.split(" says")[0].replace("logic ", "").replace(" summary", "")
            grid = self.table_for(clause, attached)
            start = end = None
            alt = {}
            if grid is not None:
                for a in attached:
                    if self.captured(a) and self.anchors[a].source_id == grid.source_id:
                        alt.update(self.quoted.get(a, {}))
                _, refs, _ = grid.walk(clause)
                if len(refs) >= 2:
                    (r0, c0), (r1, c1) = refs[0], refs[-1]
                    if (c0 is c1 and r0 > r1) or (r0 == r1 and c0.index > c1.index):  # DC1b: a table lists its axis in order
                        (r0, c0), (r1, c1) = (r1, c1), (r0, c0)
                    start, end = (grid.label(r0, c0), grid.value(r0, c0), (r0, c0.index)), (grid.label(r1, c1), grid.value(r1, c1), (r1, c1.index))
                    origin, source_id = "table", grid.source_id
                else:
                    cols = {c for a in attached if a in self.quoted for (_, c) in self.quoted[a]}
                    col = grid.resolve({}) or (next(c for c in grid.columns if c.index == min(cols)) if len(cols) == 1 else None)
                    series = grid.series(col)
                    if series is not None:
                        s, e, note = self.window(clause, series)
                        if s is not None and e is not None and s is not e:
                            start, end = (s[2], s[1], None), (e[2], e[1], None)
                            origin, source_id = "table", grid.source_id
            else:
                series = self.uncaptured_series(clause, attached)
                if series is not None:
                    s, e, note = self.window(clause, series)
                    if s is not None and e is not None and s is not e:
                        start, end = (s[2], s[1], None), (e[2], e[1], None)
                        origin, source_id = series.origin, series.source_id
            if start is None:
                own = own_endpoints(norm(clause))
                if own:
                    (tx, x), (ty, y) = own
                    start, end, origin, source_id = (tx, x, None), (ty, y, None), "own numbers", "(no cell named)"
                    if grid is not None:
                        level0 = next((val[1] for _, _, kind, val, _ in grid.events(norm(clause)) if kind == "col" and val[0] == 0), None)
                        cols = [c for c in grid.columns if c.numeric and (level0 is None or c.levels[0].lower() == level0)]
                        cells = [[(i, c) for i in range(len(grid.keys)) for c in cols if grid.value(i, c) == v] for v in (x, y)]
                        if all(len(found) == 1 for found in cells):
                            (r0, c0), (r1, c1) = cells[0][0], cells[1][0]
                            start, end = (grid.label(r0, c0), x, (r0, c0.index)), (grid.label(r1, c1), y, (r1, c1.index))
                            origin, source_id = "table", grid.source_id
            if start is None or end is None or not start[1]:
                self.grey_changes.append(grey)
                continue
            ratio = end[1] / start[1]
            amount = self.amount(clause, word, ratio)
            if amount is not None:
                ok, said = amount
            else:
                ok = abs(ratio / FACTOR[word] - 1) <= self.tol if word in FACTOR else (ratio - 1) * DIRECTION[word] > 0
                said = ""
            calc = f"x{ratio:.2f} ({start[0]} {fmt(start[1])} -> {end[0]} {fmt(end[1])}, {origin} {source_id})"
            extra = ""
            if start[2] in alt and end[2] in alt and (alt[start[2]], alt[end[2]]) != (start[1], end[1]) and alt[start[2]]:
                extra = f"; from the AI's copy x{alt[end[2]] / alt[start[2]]:.2f}"
            colour = ("G" if origin == "table" else ".") if ok else "R"  # own numbers: arithmetic alone can prove them wrong
            levels = {v for _, v in (own_endpoints(norm(clause)) or ())}  # "from 88.1% to 92.4%": levels, not an amount
            if amount is None and ok and any(float(m[1]) not in levels for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:%|per ?cent)",norm(clause))):
                colour, said = ".", "a percentage in the clause is not read as its amount"  # never green on the sign alone
            verdict = "agrees" if ok else ("sources disagree" if who.startswith("source") else "disagrees")
            self.add("CHANGES", colour, f"{label}: {verdict}, " + (f"{said}, " if said else "") + f"{calc}{extra}")
            for hypothesis in hypotheses:
                if not ok:
                    self.colour[f"hyp:{hypothesis}"] = "R"

    def node_hyps(self, node_id, targets, hyp_ids):
        return [t for t in targets.get(node_id, []) if t in hyp_ids]

    def check_changes(self):
        targets = {}
        if self.logic:
            for edge in self.logic.edges:
                targets.setdefault(edge.source, []).append(edge.target)
        hyp_ids = {row["id"] for row in self.tree.index["hypotheses"]}
        for anchor in self.anchors.values():
            hyps = sorted({d["hypothesis"] for row in self.status["evidence"] if row["anchor"] == anchor.anchor_id for d in row["directions"]})
            self.check_change(f"anchor:{anchor.anchor_id}", f"source {anchor.source_id} says", anchor.text, [], hyps if anchor.source_id not in self.captures else ())
            if anchor.normalized_summary:
                self.check_change(f"anchor:{anchor.anchor_id}", f"{anchor.anchor_id} summary", anchor.normalized_summary, [anchor.anchor_id], hyps)
        for node_id, node in (self.logic.nodes.items() if self.logic else ()):
            if node.text.startswith("Opposing evidence for") or any(
                    norm(node.text) == norm(r.quote or "") for r in coerce_provenance(node.provenance)):
                continue  # written by sync as a copy of the quote
            attached = [r.locator for r in coerce_provenance(node.provenance)] if node.type == "Evidence" else [
                r.locator for src in self.logic.nodes.values() if src.type == "Evidence" and node_id in targets.get(src.id, [])
                for r in coerce_provenance(src.provenance)]
            self.check_change(f"logic:{node_id}", f"logic {node_id}", node.text, attached, self.node_hyps(node_id, targets, hyp_ids))
        if self.grey_changes:
            names = sorted(set(self.grey_changes))
            self.add("CHANGES", ".", f"{len(self.grey_changes)} change words not computable (one period, no series, or two series) in: " + ", ".join(names))

    def held(self, anchor_id):
        anchor = self.anchors[anchor_id]
        held = readings_in(anchor.text, changes=False)
        grid = self.tables.get(anchor.source_id)
        if grid is not None:  # a table quote: its numbers as the grid reads them, with the column's unit
            nums = []
            for row, col, r in grid.walk(anchor.text)[0]:
                if r.unit is None and col is not None and col.unit:
                    r.unit = col.unit
                nums.append(r)
            held = [h for h in held if h.kind != "num"] + nums
        for line in self.found.get(anchor_id, []):
            held += readings_in(line, changes=False)
        return held

    def check_restatements(self):
        targets, hyp_ids = {}, {row["id"] for row in self.tree.index["hypotheses"]}
        if self.logic:
            for edge in self.logic.edges:
                targets.setdefault(edge.source, []).append(edge.target)
        named_anywhere = [r for a in self.anchors for r in self.held(a) if r.kind == "date"]
        items = []
        for anchor in self.anchors.values():
            if anchor.normalized_summary:
                hyps = sorted({d["hypothesis"] for row in self.status["evidence"] if row["anchor"] == anchor.anchor_id for d in row["directions"]})
                items.append((f"{anchor.anchor_id} summary", anchor.normalized_summary, [anchor.anchor_id], hyps))
        for node_id, node in (self.logic.nodes.items() if self.logic else ()):
            records = coerce_provenance(node.provenance)
            if node.type != "Evidence" or not records or any(norm(node.text) == norm(r.quote or "") for r in records):
                continue
            items.append((f"logic {node_id}", node.text, [r.locator for r in records], self.node_hyps(node_id, targets, hyp_ids)))
        checked, unchecked, on_red, cross = 0, 0, 0, []
        for who, text, anchors, hyps in items:
            own = [a for a in anchors if a in self.anchors]
            if not own or not all(self.captured(a) for a in own):
                unchecked += 1
                continue
            if not all(self.colour.get(f"anchor:{a}") == "G" for a in own):
                on_red += 1  # the quote itself is red: that line already names the cause
                continue
            held = [r for a in own for r in self.held(a)]
            checked += 1
            bad = []
            for r in readings_in(text):
                if r.kind == "num" and r.unit is None and r.decimals == 0 and r.value < 10:
                    continue
                if any(same_reading(r, h) for h in held):
                    continue
                unread = [h for h in held if not comparable(r, h)]
                same_dim = [h for h in held if h.kind == "num" and h.unit and r.unit and unit_info(h.unit)[0] == unit_info(r.unit)[0]]
                if unread and r.kind == "num" and not same_dim:
                    cross.append(f"{who} {r.show()}: cannot compare with {', '.join(f'{h.text} {h.word}' for h in unread[:3])} (unit not in the unit table)")
                    continue
                if r.kind == "date" and any(same_reading(r, h) for h in named_anywhere):
                    cross.append(f"{who} names {r.text}")
                    continue
                kin = [h for h in held if h.kind == r.kind]
                if r.kind == "num" and r.unit:
                    kin = [h for h in kin if h.unit and unit_info(h.unit)[0] == unit_info(r.unit)[0]] or [h for h in kin if h.unit]
                if r.kind == "num" and r.unit and kin:
                    shown = ", ".join(h.show() + (f" = {fmt(h.si() / unit_info(r.unit)[1])} {r.unit}" if h.unit and h.unit != r.unit else "") for h in kin[:4])
                elif r.kind == "time":
                    shown = ", ".join(f"{h.text} ({h.value})" for h in kin[:4])
                else:
                    shown = ", ".join(h.show() for h in kin[:4])
                bad.append(f"{r.show() if r.kind == 'num' else r.text}" + (f" (= {r.value})" if r.kind == "time" else "")
                           + (f": its quote holds {shown}" if shown else ": its quote holds no such reading"))
            if bad:
                self.add("RESTATEMENTS", "R", f"{who}: " + "; ".join(bad))
                for h in hyps:
                    self.colour[f"hyp:{h}"] = "R"
        if checked:
            reds = sum(1 for s, c, _ in self.lines if s == "RESTATEMENTS" and c == "R")
            self.add("RESTATEMENTS", "G" if not reds else ".", f"{checked - reds}/{checked} restatements hold only readings of their own quote"
                     + (f"; {unchecked} rest on uncaptured anchors" if unchecked else "")
                     + (f"; {on_red} not judged, their quote is not green" if on_red else ""))
        for row in cross:
            self.add("RESTATEMENTS", ".", row if "cannot compare" in row else f"{row}: not in its own quote, named by another anchor")

    def check_numbers(self):
        quoted = [r for a in self.anchors for r in self.held(a)]
        texts = []
        if self.trace:
            texts += [(f"trace {m.mechanism_id}", m.description) for m in self.trace.causal_mechanisms]
            texts += [(f"trace {e.event_id}", e.action) for e in self.trace.events]
        if self.logic:
            texts += [(f"logic {k}", n.text) for k, n in self.logic.nodes.items() if n.type != "Evidence" and not n.text.startswith("Opposing")]
        for who, text in texts:
            for r in readings_in(text):
                if r.kind != "num" or (r.value < 10 and r.unit is None and not r.decimals):
                    continue
                if not any(same_reading(r, h) for h in quoted):
                    self.add("NUMBERS", ".", f'{who} "{r.text}": in no anchor quote')

    def check_timeline(self):
        if not self.trace:
            return
        starts, bad, untimed, unsourced = {}, [], [], []
        for e in self.trace.events:
            if not (e.time_interval and e.time_interval.start):
                untimed.append(e.event_id)
                continue
            start = str(e.time_interval.start)
            starts[e.event_id] = start
            texts = [self.anchors[a].text for a in e.evidence_ids if a in self.anchors]
            texts += [line for a in e.evidence_ids for line in self.found.get(a, [])[1:]]  # DC7: the section heading
            named = [r for t in texts for r in readings_in(t, changes=False) if r.kind == "date" and r.value[0]]
            m = ISO_DATE.fullmatch(start)
            own = Reading("date", (int(m[1]), int(m[2]), int(m[3]) if m[3] else None), start, 0, 0) if m else None
            if not named:
                unsourced.append(e.event_id)
            elif own is None or not any(same_reading(own, r) for r in named):
                shown = sorted({"-".join(f"{x:02d}" if i else str(x) for i, x in enumerate(r.value) if x is not None) for r in named})
                bad.append(f"{e.event_id} {start} (its anchors name {', '.join(shown)})")
        n = len(self.trace.events)
        colour = "R" if bad else ("G" if not untimed and not unsourced else ".")
        self.add("TIMELINE", colour, f"{len(starts) - len(bad) - len(unsourced)}/{n} event dates named in their own anchors"
                 + (f"; not named: {'; '.join(bad)}" if bad else "") + (f"; no time: {', '.join(untimed)}" if untimed else "")
                 + (f"; anchors name no date: {', '.join(unsourced)}" if unsourced else ""))
        for c in self.trace.causal_candidates:
            causes = [starts[e] for e in c.cause_event_ids if e in starts]
            effects = [starts[e] for e in c.effect_event_ids if e in starts]
            if causes and effects:
                ok = max(causes) < min(effects)
                self.add("TIMELINE", "G" if ok else "R", f"{c.causal_id}: cause {max(causes)} {'before' if ok else 'NOT before'} effect {min(effects)}")



def table_rows(lines):
    """One merged-header parser for pipe captures and CSV grids."""
    rows=[[c.strip() for c in line.strip().strip("|").split("|")] for line in lines]
    separators={i for i,row in enumerate(rows) if any(row) and all(not c or re.fullmatch(r":?-{3,}:?",c) for c in row)}
    first=min(separators) if separators else next((i for i,row in enumerate(rows) if i and any(parse_value(c) is not None for c in row[1:])),1)
    head=rows[:first];body=[r for i,r in enumerate(rows) if i>=first and i not in separators]
    while body and not body[0][0] and any(body[0][1:]):
        head.append(body.pop(0))
    filled=[]
    for row in head:
        last="";level=[]
        for i,cell in enumerate(row):
            last=cell or (last if i else "");level.append(cell if i==0 else last)
        filled.append(level)
    return filled,body


def source_reading_results(tree, status):
    """Compute source sensors without rerunning native research evaluation."""
    screen=CaptureScreen(tree,status)
    for step in (screen.check_anchors,screen.check_changes,screen.check_restatements,screen.check_numbers,screen.check_timeline):
        step()
    observations = screen.observation_checks()
    return {"observation_checks": observations, "checks":[{"section":section,"colour":{"G":"green","R":"red",".":"grey"}[colour],"reason":reason}
                      for section,colour,reason in screen.lines],"errors":sorted(set(screen.errors)),"warnings":sorted(set(screen.warnings)),
            "anchor_colours":{key.removeprefix("anchor:"):{"G":"green","R":"red",".":"grey"}[value]
                              for key,value in screen.colour.items() if key.startswith("anchor:")}}
