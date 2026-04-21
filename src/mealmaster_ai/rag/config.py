"""Standalone RAG config for the capstone demo.

The production pipeline has a richer, Pydantic-Settings-backed config at
meal-map.app; this simpler version is enough to drive the 2-collection demo.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Collection(str, Enum):
    RECIPES = "recipes"
    NUTRITION_SCIENCE = "nutrition_science"
    HEALTH_FOOD_PRACTICAL = "health_food_practical"
    MEDICAL_DIETARY_GUIDELINES = "medical_dietary_guidelines"
    NATURAL_MEDICINE_EXPERIMENTAL = "natural_medicine_experimental"


ALL_COLLECTIONS: list[str] = [c.value for c in Collection]

DEMO_COLLECTIONS: list[str] = [
    Collection.RECIPES.value,
    Collection.NUTRITION_SCIENCE.value,
]


@dataclass
class RAGConfig:
    """Minimal, standalone config — no external settings dependency.

    Defaults chosen for the demo:
    - `chunk_size` / `chunk_step` are neutral starting points; real per-collection
      values live in `chunking.COLLECTION_CHUNK_PARAMS`.
    - `num_results` (top-k) matches the agent config default.
    """

    data_root: Path
    chunk_size: int = 100
    chunk_step: int = 50
    num_results: int = 5
    llm_model: str = "gpt-4.1-mini"
    embedding_model: str = "all-MiniLM-L6-v2"
    search_mode: str = "text"  # "text" | "hybrid"
    demo_mode: bool = True

    def collection_root(self, collection: str) -> Path:
        return self.data_root / collection

    def collection_chunks(self, collection: str) -> Path:
        return self.collection_root(collection) / "chunks"

    def collection_index(self, collection: str) -> Path:
        return self.collection_root(collection) / "index"

    def collection_manifest(self, collection: str) -> Path:
        return self.collection_root(collection) / "manifest.json"


def default_config(data_root: Path | None = None) -> RAGConfig:
    if data_root is None:
        here = Path(__file__).resolve()
        # SimplifiedMealMasterCapstone/src/mealmaster_ai/rag/config.py -> up 3 -> capstone root
        capstone_root = here.parents[3]
        data_root = capstone_root / "data" / "rag" / "demo"
    return RAGConfig(data_root=data_root)
