"""Retrieval metrics: hit@k, MRR, precision@k, recall@k.

Given a ground truth list where each entry has `{query, expected_chunk_ids}`,
and a retrieval function, compute standard IR metrics and return a summary dict.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


def hit_at_k(expected: list[str], retrieved: list[str], k: int = 5) -> float:
    """1.0 if any expected chunk appears in the top-k retrieved, else 0."""
    return 1.0 if set(retrieved[:k]) & set(expected) else 0.0


def mrr(expected: list[str], retrieved: list[str]) -> float:
    """Mean reciprocal rank of the first expected chunk in the retrieved list."""
    expected_set = set(expected)
    for i, r in enumerate(retrieved):
        if r in expected_set:
            return 1.0 / (i + 1)
    return 0.0


def precision_at_k(expected: list[str], retrieved: list[str], k: int = 5) -> float:
    if k == 0:
        return 0.0
    hits = len(set(retrieved[:k]) & set(expected))
    return hits / k


def recall_at_k(expected: list[str], retrieved: list[str], k: int = 5) -> float:
    if not expected:
        return 0.0
    hits = len(set(retrieved[:k]) & set(expected))
    return hits / len(expected)


def evaluate_retrieval(
    ground_truth: list[dict[str, Any]],
    retrieval_fn: Callable[[str], list[dict[str, Any]]],
    k: int = 5,
) -> dict[str, Any]:
    """Run `retrieval_fn(query)` for each GT case; aggregate hit@k / MRR / P@k / R@k."""
    results: list[dict[str, Any]] = []
    for case in ground_truth:
        query = case["query"]
        expected = case.get("expected_chunk_ids", [])
        retrieved = retrieval_fn(query)
        retrieved_ids = [str(r.get("chunk_id") or "") for r in retrieved]
        results.append({
            "query": query,
            "expected": expected,
            "retrieved": retrieved_ids[:k],
            "hit_at_k": hit_at_k(expected, retrieved_ids, k),
            "mrr": mrr(expected, retrieved_ids),
            "precision_at_k": precision_at_k(expected, retrieved_ids, k),
            "recall_at_k": recall_at_k(expected, retrieved_ids, k),
        })

    n = len(results) or 1
    summary = {
        "n_queries": len(results),
        "k": k,
        "avg_hit_at_k": sum(r["hit_at_k"] for r in results) / n,
        "avg_mrr": sum(r["mrr"] for r in results) / n,
        "avg_precision_at_k": sum(r["precision_at_k"] for r in results) / n,
        "avg_recall_at_k": sum(r["recall_at_k"] for r in results) / n,
        "per_query": results,
    }
    return summary


def load_ground_truth(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "cases" in data:
        return data["cases"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unrecognized ground-truth shape in {path}")
