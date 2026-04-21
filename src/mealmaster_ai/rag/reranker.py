"""Diversity-aware reranker.

Takes a retrieved set and reorders to balance:
1. top-k score
2. source/doc diversity (avoid 5 chunks from one book)
3. authority (evidence collections boost)

Production reranker at meal-map.app uses a cross-encoder; this demo ships a
lightweight heuristic that still demonstrates the rerank-vs-raw comparison
used in `docs/retrieval-evaluation.md`.
"""
from __future__ import annotations

from typing import Any

RERANK_COLLECTIONS = frozenset({
    "nutrition_science",
    "health_food_practical",
    "medical_dietary_guidelines",
})


def rerank(
    results: list[dict[str, Any]],
    diversity_penalty: float = 0.15,
    authority_boost: float = 0.1,
) -> list[dict[str, Any]]:
    """Return a reordered copy of `results` balancing score, diversity, authority."""
    if not results:
        return []

    seen_docs: dict[str, int] = {}
    scored: list[tuple[float, dict[str, Any]]] = []

    for r in results:
        base_score = float(r.get("score", 0.0) or 0.0)
        doc_id = str(r.get("doc_id") or r.get("source_title") or "")
        times_seen = seen_docs.get(doc_id, 0)
        diversity_factor = (1.0 - diversity_penalty) ** times_seen
        authority = 0.0
        if r.get("collection") in RERANK_COLLECTIONS and r.get("authority_level") == "high":
            authority = authority_boost
        adjusted = base_score * diversity_factor + authority
        seen_docs[doc_id] = times_seen + 1
        scored.append((adjusted, {**r, "rerank_score": round(adjusted, 6)}))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [r for _, r in scored]
