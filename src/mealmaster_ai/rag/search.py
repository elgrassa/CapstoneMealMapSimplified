"""Minimal BM25 search over chunk sets — uses `minsearch` when available, else a pure-Python fallback.

The demo ships pre-built minsearch pickles under `data/rag/demo/<collection>/index/bm25.pkl`.
When `minsearch` is not installed, `BM25Lite` provides a very small TF-IDF fallback so tests run.
"""
from __future__ import annotations

import math
import pickle
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25Lite:
    """Tiny pure-Python BM25 so search works even without minsearch.

    Production at meal-map.app uses `minsearch.Index` for better scoring; this
    fallback lets unit tests run in the CI sandbox without heavy deps.
    """

    def __init__(self, text_fields: list[str], keyword_fields: list[str] | None = None):
        self.text_fields = text_fields
        self.keyword_fields = keyword_fields or []
        self.docs: list[dict[str, Any]] = []
        self.doc_tokens: list[list[str]] = []
        self.avgdl: float = 0.0
        self.df: Counter[str] = Counter()
        self.k1 = 1.5
        self.b = 0.75

    def fit(self, docs: list[dict[str, Any]]) -> "BM25Lite":
        self.docs = list(docs)
        self.doc_tokens = []
        df_counter: Counter[str] = Counter()
        for d in self.docs:
            toks: list[str] = []
            for f in self.text_fields:
                toks.extend(_tokenize(str(d.get(f, ""))))
            self.doc_tokens.append(toks)
            for t in set(toks):
                df_counter[t] += 1
        self.df = df_counter
        self.avgdl = (sum(len(t) for t in self.doc_tokens) / len(self.doc_tokens)) if self.doc_tokens else 0.0
        return self

    def search(self, query: str, num_results: int = 5, filter_dict: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        q_toks = _tokenize(query)
        N = len(self.docs) or 1
        scores: list[tuple[float, int]] = []
        for i, toks in enumerate(self.doc_tokens):
            if filter_dict:
                if any(self.docs[i].get(k) != v for k, v in filter_dict.items()):
                    continue
            score = 0.0
            counts = Counter(toks)
            dl = len(toks) or 1
            for t in q_toks:
                f = counts.get(t, 0)
                if f == 0:
                    continue
                df = self.df.get(t, 0)
                idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
                denom = f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                score += idf * (f * (self.k1 + 1)) / denom
            if score > 0:
                scores.append((score, i))
        scores.sort(reverse=True)
        top = scores[:num_results]
        return [
            {**self.docs[i], "score": round(s, 6)}
            for s, i in top
        ]


def load_index(path: Path) -> Any:
    """Load a pickled BM25 index. Tries minsearch first; falls back to BM25Lite."""
    with open(path, "rb") as f:
        return pickle.load(f)


def run_collection_search(
    index: Any,
    query: str,
    num_results: int = 5,
    collection: str | None = None,
) -> list[dict[str, Any]]:
    """Run a query against a minsearch-style index. Returns a list of flat result dicts.

    Compatibility layer:
    - `BM25Lite` returns dicts with a `score` field populated.
    - `minsearch.Index` returns dicts without a score by default; we add a
      rank-proportional pseudo-score so the evidence gate + reranker have
      numbers to work with. Production at meal-map.app uses minsearch
      configured to emit scores (or a cross-encoder for rescoring).
    """
    if not hasattr(index, "search"):
        return []

    try:
        results = index.search(query, num_results=num_results)
    except TypeError:
        results = index.search(query, k=num_results)

    enriched: list[dict[str, Any]] = []
    for rank, r in enumerate(results):
        if not isinstance(r, dict):
            r = dict(r)
        if collection and "collection" not in r:
            r["collection"] = collection
        if "score" not in r:
            # Rank-proportional fallback in [0, 1]; top result → 1.0
            r["score"] = round(1.0 - rank / max(num_results, 1), 6) if num_results else 1.0
        enriched.append(r)
    return enriched
