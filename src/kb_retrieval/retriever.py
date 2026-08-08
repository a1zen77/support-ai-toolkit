"""
Query interface over the KB index built in indexer.py.

Matching strategy: exact error-code matches are treated as high-confidence
and surfaced first (a ticket literally mentioning `AUTH_TOKEN_EXPIRED` should
always cite that section) - embedding similarity fills in the rest and
catches cases where the ticket describes a symptom without naming a code.
"""

from __future__ import annotations

import re

import numpy as np
from sentence_transformers import SentenceTransformer

from src.common.schemas import KBMatch
from src.kb_retrieval.indexer import KBChunk, build_index, _embedder

# Matches how error codes actually appear in ticket text: same shape as the
# codes we extract from the KB (word chars + underscore, or a 3-digit HTTP code).
_TICKET_CODE_RE = re.compile(r"\b([A-Z][A-Z0-9]*_[A-Z0-9_]+|\b\d{3}\s+[A-Za-z]+)\b")

EXACT_MATCH_SCORE = 1.0
SEMANTIC_SCORE_FLOOR = 0.35  # below this, a semantic match isn't worth surfacing


def _find_ticket_error_codes(text: str) -> set[str]:
    return set(_TICKET_CODE_RE.findall(text))


def _retrieve_raw(query_text: str, top_k: int = 3) -> list[tuple[KBChunk, float, str]]:
    """Returns (chunk, score, reason) tuples - the shared logic behind both
    public entry points below."""
    idx = build_index()
    picked: dict[str, tuple[KBChunk, float, str]] = {}  # keyed to dedupe

    def key(chunk: KBChunk) -> str:
        return f"{chunk.doc_path}#{chunk.section_title}"

    # 1. Exact error-code matches (high confidence, always included)
    ticket_codes = _find_ticket_error_codes(query_text)
    if ticket_codes:
        for chunk in idx.chunks:
            hit_codes = ticket_codes & set(chunk.error_codes)
            if hit_codes:
                reason = f"exact error code match: {', '.join(sorted(hit_codes))}"
                picked[key(chunk)] = (chunk, EXACT_MATCH_SCORE, reason)

    # 2. Semantic similarity, fills remaining slots
    model: SentenceTransformer = _embedder()
    query_emb = model.encode([query_text], normalize_embeddings=True)[0]
    sims = idx.embeddings @ query_emb  # cosine similarity (both sides normalised)

    ranked = np.argsort(-sims)
    for i in ranked:
        if len(picked) >= top_k:
            break
        chunk = idx.chunks[i]
        score = float(sims[i])
        if score < SEMANTIC_SCORE_FLOOR:
            break  # sorted descending, so nothing after this clears the floor either
        k = key(chunk)
        if k in picked:
            continue  # already have this section via exact match
        reason = f"semantic similarity ({score:.2f}) to \"{chunk.section_title}\""
        picked[k] = (chunk, score, reason)

    ranked_results = sorted(picked.values(), key=lambda t: -t[1])
    return ranked_results[:top_k]


def retrieve(query_text: str, top_k: int = 3) -> list[KBMatch]:
    """Given raw ticket text (subject + body), return up to top_k ranked KB matches."""
    return [
        KBMatch(doc_path=c.doc_path, doc_title=c.doc_title, matched_reason=reason, relevance_score=score)
        for c, score, reason in _retrieve_raw(query_text, top_k)
    ]


def retrieve_with_context(query_text: str, top_k: int = 3) -> list[tuple[KBMatch, str]]:
    """Like retrieve(), but also returns each match's raw section text -
    used when the caller needs actual KB content, e.g. to ground a drafted
    response instead of letting the LLM invent steps."""
    return [
        (
            KBMatch(doc_path=c.doc_path, doc_title=c.doc_title, matched_reason=reason, relevance_score=score),
            c.text,
        )
        for c, score, reason in _retrieve_raw(query_text, top_k)
    ]


if __name__ == "__main__":
    # Quick manual check: `python -m src.kb_retrieval.retriever`
    test_queries = [
        "Our automated pipeline job is failing with AUTH_TOKEN_EXPIRED every night at 2am.",
        "Dashboard in AnalyticsHub just spins forever and never loads any data.",
        "We are being billed for 50 seats but only have 30 people using the product.",
        "asdkjfh randomtext nothing relevant to any product at all",
    ]
    for q in test_queries:
        print(f"\nQuery: {q}")
        for m in retrieve(q):
            print(f"  [{m.relevance_score:.2f}] {m.doc_path} — {m.matched_reason}")