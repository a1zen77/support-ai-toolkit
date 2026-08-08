"""
Parses knowledge_base/*.md into retrievable chunks and builds a local
embedding index (sentence-transformers) over them. No external API calls,
no vector DB dependency — just numpy cosine similarity over a few dozen
chunks, which is more than fast enough at this KB size.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from src.common.config import settings

_HEADER_RE = re.compile(r"^(#{1,3})\s+(.*)$")
_CODE_TOKEN_RE = re.compile(r"^([A-Z][A-Z0-9]*_[A-Z0-9_]+|\d{3}\s+[A-Za-z]+)")


@dataclass
class KBChunk:
    doc_path: str        # relative path, e.g. "troubleshooting/authentication-sso.md"
    doc_title: str        # H1 of the file, e.g. "Troubleshooting: Authentication & SSO"
    section_title: str    # nearest H2/H3 heading, e.g. "Service Account Token Expired"
    text: str
    error_codes: list[str] = field(default_factory=list)

    @property
    def embedding_text(self) -> str:
        """Text actually embedded — includes doc/section titles for context."""
        return f"{self.doc_title} — {self.section_title}\n{self.text}"


def _extract_error_codes(text: str) -> list[str]:
    """
    Pulls likely error codes out of backtick-quoted spans, e.g. `AUTH_TOKEN_EXPIRED`
    or `403 Forbidden`. Filters out lowercase config field names like `batch_size`
    (those don't match the pattern) so we only capture actual error codes.
    """
    codes = []
    for span in re.findall(r"`([^`]+)`", text):
        m = _CODE_TOKEN_RE.match(span)
        if m:
            codes.append(m.group(1))
    return sorted(set(codes))


def parse_markdown_file(path: Path, relative_to: Path) -> list[KBChunk]:
    """Split a markdown file into chunks at each H2/H3 header boundary."""
    text = path.read_text()
    lines = text.splitlines()

    doc_title = path.stem
    chunks: list[KBChunk] = []
    section_title = ""
    buffer: list[str] = []
    rel_path = str(path.relative_to(relative_to))

    def flush():
        content = "\n".join(buffer).strip()
        if content:
            chunks.append(
                KBChunk(
                    doc_path=rel_path,
                    doc_title=doc_title,
                    section_title=section_title or doc_title,
                    text=content,
                    error_codes=_extract_error_codes(content),
                )
            )

    for line in lines:
        m = _HEADER_RE.match(line)
        if m:
            level, heading_text = len(m.group(1)), m.group(2).strip()
            if level == 1:
                flush()
                buffer = []
                doc_title = heading_text
                section_title = ""
            else:  # level 2 or 3 -> new chunk boundary
                flush()
                buffer = []
                section_title = heading_text
        else:
            buffer.append(line)
    flush()

    return chunks


def load_all_chunks() -> list[KBChunk]:
    chunks: list[KBChunk] = []
    for md_path in sorted(settings.kb_dir.rglob("*.md")):
        chunks.extend(parse_markdown_file(md_path, relative_to=settings.kb_dir))
    return chunks


@lru_cache(maxsize=1)
def _embedder() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model)


@dataclass
class KBIndex:
    chunks: list[KBChunk]
    embeddings: np.ndarray  # shape (n_chunks, dim), L2-normalised


@lru_cache(maxsize=1)
def build_index() -> KBIndex:
    chunks = load_all_chunks()
    model = _embedder()
    texts = [c.embedding_text for c in chunks]
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return KBIndex(chunks=chunks, embeddings=np.asarray(embeddings))


if __name__ == "__main__":
    # Quick manual check: `python -m src.kb_retrieval.indexer`
    idx = build_index()
    print(f"Indexed {len(idx.chunks)} chunks from {settings.kb_dir}")
    print(f"Embedding matrix shape: {idx.embeddings.shape}")

    with_codes = [c for c in idx.chunks if c.error_codes]
    print(f"\n{len(with_codes)} chunks contain at least one error code:")
    for c in with_codes[:8]:
        print(f"  [{c.doc_path}] {c.section_title}: {c.error_codes}")