"""TraceGuard temporal relation evaluator.

Purpose: Parse coarse time intervals and detect Allen-style relations and obvious contradictions.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: TraceGuard
Math boundary: Lightweight interval comparison, not fake precise dating.
CLI: researchguard trace diagnose <model.yaml>
Boundary: Unknown or relative dates remain uncertain unless evidence narrows them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .schema import TimeInterval


@dataclass(frozen=True)
class DateRange:
    start: date | None
    end: date | None

    @property
    def known(self) -> bool:
        return self.start is not None and self.end is not None


def _last_day(year: int, month: int) -> int:
    if month == 2:
        return 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
    return 30 if month in {4, 6, 9, 11} else 31


def parse_date_token(token: str | None, precision: str) -> DateRange:
    if not token:
        return DateRange(None, None)
    token = str(token)
    if precision == "exact_date" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
        y, m, d = map(int, token.split("-"))
        value = date(y, m, d)
        return DateRange(value, value)
    if precision == "month" and re.fullmatch(r"\d{4}-\d{2}", token):
        y, m = map(int, token.split("-"))
        return DateRange(date(y, m, 1), date(y, m, _last_day(y, m)))
    if precision == "quarter" and re.fullmatch(r"\d{4}-Q[1-4]", token):
        y = int(token[:4])
        q = int(token[-1])
        start_month = (q - 1) * 3 + 1
        end_month = start_month + 2
        return DateRange(date(y, start_month, 1), date(y, end_month, _last_day(y, end_month)))
    if precision == "year" and re.fullmatch(r"\d{4}", token):
        y = int(token)
        return DateRange(date(y, 1, 1), date(y, 12, 31))
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
        y, m, d = map(int, token.split("-"))
        value = date(y, m, d)
        return DateRange(value, value)
    return DateRange(None, None)


def interval_to_range(interval: TimeInterval | None) -> DateRange:
    if interval is None or interval.precision in {"unknown", "relative"}:
        return DateRange(None, None)
    if interval.precision == "interval":
        start = parse_date_token(interval.start, "exact_date")
        end = parse_date_token(interval.end, "exact_date")
        if not start.known:
            start = parse_date_token(interval.start, "month")
        if not end.known:
            end = parse_date_token(interval.end, "month")
        return DateRange(start.start, end.end)
    start_range = parse_date_token(interval.start or interval.text, interval.precision)
    return start_range


def allen_relation(left: TimeInterval | None, right: TimeInterval | None) -> str:
    left_range = interval_to_range(left)
    right_range = interval_to_range(right)
    if not left_range.known or not right_range.known:
        return "uncertain"
    assert left_range.start and left_range.end and right_range.start and right_range.end
    if left_range.end < right_range.start:
        delta = (right_range.start - left_range.end).days
        return "meets" if delta <= 1 else "before"
    if right_range.end < left_range.start:
        delta = (left_range.start - right_range.end).days
        return "met_by" if delta <= 1 else "after"
    if left_range.start == right_range.start and left_range.end == right_range.end:
        return "equals"
    if left_range.start >= right_range.start and left_range.end <= right_range.end:
        return "during"
    if left_range.start <= right_range.start and left_range.end >= right_range.end:
        return "contains"
    return "overlaps"
