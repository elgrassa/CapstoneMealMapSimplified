"""Simplified RAG package — mirrors the production layout at meal-map.app.

The 11 reachable modules in this package form the retrieval-and-evidence-gate
half of the capstone (the other half is the agent in `ai/week1-rag/`).
"""

from .config import Collection, ALL_COLLECTIONS, DEMO_COLLECTIONS, RAGConfig, default_config
from .models import Chunk, RetrievalResult, EvidenceTier
from .evidence_gate import (
    EvidenceGateDecision,
    evaluate_evidence,
    AUTHORITY_WEIGHTS,
    EVIDENCE_COLLECTIONS,
    DEFAULT_FALLBACK_MESSAGE,
    DEFAULT_REFUSAL_MESSAGE,
)
from .router import route_query, RoutingResult, classify_intent, INTENT_CATEGORIES
from .chunking import (
    COLLECTION_CHUNK_PARAMS,
    chunk_recipe_boundary,
    chunk_structured_header,
    chunk_sliding_window,
    select_chunker,
)

__all__ = [
    "Collection",
    "ALL_COLLECTIONS",
    "DEMO_COLLECTIONS",
    "RAGConfig",
    "default_config",
    "Chunk",
    "RetrievalResult",
    "EvidenceTier",
    "EvidenceGateDecision",
    "evaluate_evidence",
    "AUTHORITY_WEIGHTS",
    "EVIDENCE_COLLECTIONS",
    "DEFAULT_FALLBACK_MESSAGE",
    "DEFAULT_REFUSAL_MESSAGE",
    "route_query",
    "RoutingResult",
    "classify_intent",
    "INTENT_CATEGORIES",
    "COLLECTION_CHUNK_PARAMS",
    "chunk_recipe_boundary",
    "chunk_structured_header",
    "chunk_sliding_window",
    "select_chunker",
]
