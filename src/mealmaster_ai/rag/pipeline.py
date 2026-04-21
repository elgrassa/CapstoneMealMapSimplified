"""Small end-to-end pipeline used by the demo seed script and Streamlit Tab 1.

Takes raw text → adaptive chunks → BM25 index. Returns an in-memory index that
can be persisted with pickle.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .chunking import build_chunks_adaptive


def build_chunks_for_source(
    raw_text: str,
    *,
    doc_id: str,
    collection: str,
    source_title: str,
    source_url: str,
    authority_level: str = "medium",
    safety_sensitive: bool = False,
) -> list[dict[str, Any]]:
    """Chunk a raw text into the standard chunk dict shape."""
    texts = build_chunks_adaptive(raw_text, collection)
    return [
        {
            "chunk_id": f"{doc_id}::{i:04d}",
            "doc_id": doc_id,
            "collection": collection,
            "text": chunk,
            "source_title": source_title,
            "source_url": source_url,
            "authority_level": authority_level,
            "safety_sensitive": safety_sensitive,
        }
        for i, chunk in enumerate(texts)
    ]


def build_index(docs: list[dict[str, Any]], *, backend: str = "auto") -> Any:
    """Build a BM25 index.

    Args:
        docs: Flat chunk dicts.
        backend: "bm25lite" (always returns scores — default in demo),
                 "minsearch" (uses minsearch.Index; scores fallback to rank-proportional),
                 "auto" (bm25lite — matches default; kept for forward-compat).

    Why BM25Lite by default: the minsearch 0.0.10 release does not emit match
    scores through `Index.search()`, so the evidence gate + reranker can't
    differentiate relevance. BM25Lite is a ~80-line pure-Python BM25 that
    returns calibrated scores; suitable for a 15-chunk demo corpus.
    """
    if backend in ("bm25lite", "auto"):
        from .search import BM25Lite
        return BM25Lite(
            text_fields=["text", "source_title"],
            keyword_fields=["collection", "authority_level", "doc_id", "chunk_id"],
        ).fit(docs)

    try:
        from minsearch import Index  # type: ignore
        index = Index(
            text_fields=["text", "source_title"],
            keyword_fields=["collection", "authority_level", "doc_id", "chunk_id"],
        )
        index.fit(docs)
        return index
    except ImportError:
        from .search import BM25Lite
        return BM25Lite(
            text_fields=["text", "source_title"],
            keyword_fields=["collection", "authority_level", "doc_id", "chunk_id"],
        ).fit(docs)


def save_chunks_jsonl(chunks: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")


def load_chunks_jsonl(path: Path) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks
