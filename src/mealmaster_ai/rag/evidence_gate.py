"""Deterministic evidence gate — capstone version.

Mirrors the production algorithm at meal-map.app (Python port of the canonical JS
in `src/ai/rag/evidenceGate.js`). Thresholds, authority weights, sorting, and
decision rules are identical so that the same retrieved set produces the same
gate status here as in production.

Result shape:
- Flat dicts (what `run_collection_search` produces in this demo).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DEFAULT_FALLBACK_MESSAGE = (
    "The evidence available for this claim did not meet the confidence threshold. "
    "Treat the response as generated guidance only and consult primary sources if needed."
)
DEFAULT_REFUSAL_MESSAGE = (
    "No sufficiently relevant evidence was found for this question. "
    "Please consult a qualified healthcare professional or registered dietitian for personal guidance."
)

# Evidence collections where `authority_level` influences scoring.
# Recipes are intentionally excluded — they use relevance-first ranking.
EVIDENCE_COLLECTIONS = frozenset({
    "nutrition_science",
    "health_food_practical",
    "medical_dietary_guidelines",
})

AUTHORITY_WEIGHTS: dict[str, float] = {"high": 1.3, "medium": 1.0, "low": 0.7}

GateStatus = Literal["supported", "fallback", "refused"]


@dataclass
class EvidenceGateDecision:
    status: GateStatus
    confidence: float
    sources: list[dict[str, Any]] = field(default_factory=list)
    fallback_message: str | None = None
    require_disclaimer: bool = False


def _round4(x: float) -> float:
    return round(x * 10000) / 10000


def evaluate_evidence(
    search_results: list[dict[str, Any]] | None,
    confidence_threshold: float = 0.3,
    fallback_threshold: float = 0.1,
    require_disclaimer: bool = False,
    authority_weights: dict[str, float] | None = None,
) -> EvidenceGateDecision:
    """Return a tiered decision for the retrieved set.

    - `supported` when adjusted top score >= `confidence_threshold`
    - `fallback` between the two thresholds
    - `refused` below `fallback_threshold`

    Authority weights apply only to `EVIDENCE_COLLECTIONS` — recipes pass through.
    """
    weights = authority_weights or AUTHORITY_WEIGHTS

    if not search_results:
        return EvidenceGateDecision(
            status="refused",
            confidence=0.0,
            sources=[],
            fallback_message=DEFAULT_REFUSAL_MESSAGE,
            require_disclaimer=require_disclaimer,
        )

    weighted: list[tuple[float, dict[str, Any]]] = []
    for r in search_results:
        score = float(r.get("score", 0.0) or 0.0)
        coll = r.get("collection")
        adjusted = score
        if coll in EVIDENCE_COLLECTIONS:
            weight = weights.get(str(r.get("authority_level") or ""), 1.0)
            adjusted = score * weight
        weighted.append((adjusted, r))

    weighted.sort(key=lambda t: t[0], reverse=True)
    top_score = weighted[0][0]

    has_safety_sensitive = any(
        bool(r.get("safety_sensitive")) for _, r in weighted[:3]
    )

    sources = [
        {
            "chunk_id": r.get("chunk_id"),
            "source_title": r.get("source_title"),
            "source_url": r.get("source_url"),
            "collection": r.get("collection"),
            "authority_level": r.get("authority_level"),
            "score": _round4(adj),
        }
        for adj, r in weighted
    ]

    needs_disclaimer = require_disclaimer or has_safety_sensitive

    if top_score >= confidence_threshold:
        return EvidenceGateDecision(
            status="supported",
            confidence=_round4(top_score),
            sources=sources,
            fallback_message=DEFAULT_FALLBACK_MESSAGE if needs_disclaimer else None,
            require_disclaimer=needs_disclaimer,
        )

    if top_score >= fallback_threshold:
        return EvidenceGateDecision(
            status="fallback",
            confidence=_round4(top_score),
            sources=sources,
            fallback_message=DEFAULT_FALLBACK_MESSAGE,
            require_disclaimer=needs_disclaimer,
        )

    return EvidenceGateDecision(
        status="refused",
        confidence=_round4(top_score),
        sources=sources,
        fallback_message=DEFAULT_REFUSAL_MESSAGE,
        require_disclaimer=needs_disclaimer,
    )
