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


def retrieve(query_text: str, top_k: int = 3) -> list[KBMatch]:
    """
    Given raw ticket text (subject + body), return up to top_k ranked KB matches.
    """
    idx = build_index()
    matches: dict[str, KBMatch] = {}  # keyed by doc_path+section to dedupe

    def key(chunk: KBChunk) -> str:
        return f"{chunk.doc_path}#{chunk.section_title}"

    # 1. Exact error-code matches (high confidence, always included)
    ticket_codes = _find_ticket_error_codes(query_text)
    if ticket_codes:
        for chunk in idx.chunks:
            hit_codes = ticket_codes & set(chunk.error_codes)
            if hit_codes:
                matches[key(chunk)] = KBMatch(
                    doc_path=chunk.doc_path,
                    doc_title=chunk.doc_title,
                    matched_reason=f"exact error code match: {', '.join(sorted(hit_codes))}",
                    relevance_score=EXACT_MATCH_SCORE,
                )

    # 2. Semantic similarity, fills remaining slots
    model: SentenceTransformer = _embedder()
    query_emb = model.encode([query_text], normalize_embeddings=True)[0]
    sims = idx.embeddings @ query_emb  # cosine similarity (both sides normalised)

    ranked = np.argsort(-sims)
    for i in ranked:
        if len(matches) >= top_k:
            break
        chunk = idx.chunks[i]
        score = float(sims[i])
        if score < SEMANTIC_SCORE_FLOOR:
            break  # sorted descending, so nothing after this clears the floor either
        k = key(chunk)
        if k in matches:
            continue  # already have this section via exact match
        matches[k] = KBMatch(
            doc_path=chunk.doc_path,
            doc_title=chunk.doc_title,
            matched_reason=f"semantic similarity ({score:.2f}) to \"{chunk.section_title}\"",
            relevance_score=score,
        )

    ranked_matches = sorted(matches.values(), key=lambda m: -m.relevance_score)
    return ranked_matches[:top_k]


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