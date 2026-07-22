"""TraceGuard entity-resolution helper.

Purpose: Provide conservative record-linkage-style entity scoring for v0.1.4.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: TraceGuard
Math boundary: Heuristic scorer only; not full Fellegi-Sunter parameter estimation.
CLI: researchguard trace evaluate <model.yaml>
Boundary: A high score suggests merge plausibility, not factual identity proof.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .schema import EntityMention, clamp01


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


@dataclass(frozen=True)
class EntityScore:
    left_id: str
    right_id: str
    relation: str
    score: float
    reasons: tuple[str, ...]
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "left_id": self.left_id,
            "right_id": self.right_id,
            "relation": self.relation,
            "score": round(self.score, 6),
            "reasons": list(self.reasons),
            "blockers": list(self.blockers),
        }


def score_entities(left: EntityMention, right: EntityMention) -> EntityScore:
    reasons: list[str] = []
    blockers: list[str] = []
    left_names = {normalize_name(left.normalized_name), *(normalize_name(alias) for alias in left.aliases)}
    right_names = {normalize_name(right.normalized_name), *(normalize_name(alias) for alias in right.aliases)}
    left_names.discard("")
    right_names.discard("")

    alias_match = bool(left_names & right_names)
    name_similarity = max(
        (SequenceMatcher(None, a, b).ratio() for a in left_names for b in right_names),
        default=0.0,
    )
    if alias_match:
        reasons.append("alias_match")
    if name_similarity >= 0.82:
        reasons.append("name_similarity")

    country_bonus = 0.0
    if left.country and right.country:
        if left.country.lower() == right.country.lower():
            country_bonus = 0.1
            reasons.append("country_match")
        else:
            blockers.append("country_mismatch")

    role_bonus = 0.0
    if left.role and right.role:
        if left.role == right.role:
            role_bonus = 0.05
            reasons.append("role_match")
        elif {left.role, right.role} & {"project_site", "company_headquarter", "patent_office_country"}:
            blockers.append("role_blocker")

    base = max(0.92 if alias_match else 0.0, name_similarity * 0.8 + country_bonus + role_bonus)
    if blockers:
        base -= 0.25
    score = clamp01(base)
    if score >= 0.86 and not blockers:
        relation = "same_as"
    elif score >= 0.55:
        relation = "possible_same_as"
    elif blockers:
        relation = "different"
    else:
        relation = "unknown"
    return EntityScore(left.mention_id, right.mention_id, relation, score, tuple(reasons), tuple(blockers))
