"""
Purpose: Provide local lexical ranking helpers for SourceGuard candidate texts without external search calls.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source frontier <model.yaml>
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Any

from .schema import Gap, Lead


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "")]


def lexical_score(query: str, text: str) -> float:
    query_terms = set(tokenize(query))
    if not query_terms:
        return 0.0
    text_terms = set(tokenize(text))
    return len(query_terms & text_terms) / len(query_terms)


def simple_bm25_like(query: str, documents: list[str]) -> list[float]:
    query_terms = tokenize(query)
    if not query_terms:
        return [0.0 for _ in documents]
    tokenized_docs = [tokenize(doc) for doc in documents]
    doc_count = max(len(tokenized_docs), 1)
    document_frequency: Counter[str] = Counter()
    for tokens in tokenized_docs:
        document_frequency.update(set(tokens))
    avg_len = sum(len(tokens) for tokens in tokenized_docs) / doc_count if doc_count else 1.0
    scores: list[float] = []
    for tokens in tokenized_docs:
        counts = Counter(tokens)
        doc_len = len(tokens) or 1
        score = 0.0
        for term in query_terms:
            df = document_frequency.get(term, 0)
            idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
            tf = counts.get(term, 0)
            denom = tf + 1.2 * (1 - 0.75 + 0.75 * doc_len / (avg_len or 1.0))
            score += idf * ((tf * 2.2) / denom) if denom else 0.0
        scores.append(score)
    max_score = max(scores) if scores else 0.0
    if max_score <= 0:
        return scores
    return [score / max_score for score in scores]


def rank_local_texts(query: str, documents: list[dict[str, Any] | str]) -> list[dict[str, Any]]:
    texts = [doc if isinstance(doc, str) else str(doc.get("text", "")) for doc in documents]
    scores = simple_bm25_like(query, texts)
    ranked = []
    for index, (doc, score) in enumerate(zip(documents, scores)):
        item = {"index": index, "score": score, "boundary": "Local lexical ranking only; no web search was performed."}
        if isinstance(doc, dict):
            item.update(doc)
        else:
            item["text"] = doc
        ranked.append(item)
    return sorted(ranked, key=lambda item: item["score"], reverse=True)


def deduplicate_by_title_url_hash(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for record in records:
        key_text = f"{record.get('title', '')}|{record.get('url', '')}".strip().lower()
        digest = hashlib.sha256(key_text.encode("utf-8")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        output.append(record)
    return output


def query_terms_from_gap(gap: Gap) -> list[str]:
    return tokenize(" ".join([gap.gap_type, gap.description, " ".join(gap.suggested_source_roles), " ".join(gap.suggested_modalities)]))


def query_terms_from_lead(lead: Lead) -> list[str]:
    return tokenize(" ".join([lead.question, lead.hypothesis, " ".join(lead.related_entities)]))
