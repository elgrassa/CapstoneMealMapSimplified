"""Optional hybrid retrieval — BM25 + sentence-transformer embeddings with RRF fusion.

This module degrades gracefully: if `sentence-transformers` isn't installed or
embeddings haven't been built, it returns the BM25 results as-is. The capstone
demo ships BM25 only; the hybrid path is exercised in production at meal-map.app.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


def _reciprocal_rank_fusion(
    bm25_results: list[dict[str, Any]],
    vector_results: list[dict[str, Any]],
    k: int = 60,
) -> list[dict[str, Any]]:
    """Standard RRF: score = sum(1 / (k + rank)) over constituent rankings."""
    merged: dict[str, dict[str, Any]] = {}

    def _key(r: dict[str, Any]) -> str:
        return str(r.get("chunk_id") or r.get("doc_id") or id(r))

    for rank, r in enumerate(bm25_results):
        kid = _key(r)
        merged.setdefault(kid, {**r, "rrf_score": 0.0})
        merged[kid]["rrf_score"] += 1.0 / (k + rank + 1)
    for rank, r in enumerate(vector_results):
        kid = _key(r)
        merged.setdefault(kid, {**r, "rrf_score": 0.0})
        merged[kid]["rrf_score"] += 1.0 / (k + rank + 1)

    fused = list(merged.values())
    fused.sort(key=lambda r: r.get("rrf_score", 0.0), reverse=True)
    for r in fused:
        r["score"] = round(r.get("rrf_score", 0.0), 6)
    return fused


def run_hybrid_search(
    query: str,
    bm25_results: list[dict[str, Any]],
    vector_index_path: Path | None = None,
    vector_fn=None,
    num_results: int = 5,
) -> list[dict[str, Any]]:
    """Return BM25 results alone if no vector path is available; otherwise RRF-fuse."""
    if not vector_fn or not vector_index_path or not _HAS_NUMPY:
        return bm25_results[:num_results]

    try:
        vector_results = vector_fn(query, top_k=num_results)
    except Exception:
        return bm25_results[:num_results]

    fused = _reciprocal_rank_fusion(bm25_results, vector_results)
    return fused[:num_results]
