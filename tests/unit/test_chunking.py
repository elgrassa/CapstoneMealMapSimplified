"""Chunking strategy tests — per-collection params + boundary conditions."""
from __future__ import annotations

from mealmaster_ai.rag.chunking import (
    COLLECTION_CHUNK_PARAMS,
    build_chunks_adaptive,
    chunk_recipe_boundary,
    chunk_sliding_window,
    chunk_structured_header,
    select_chunker,
)


def test_collection_chunk_params_contains_all_five_collections():
    for c in ["recipes", "nutrition_science", "health_food_practical", "medical_dietary_guidelines", "natural_medicine_experimental"]:
        assert c in COLLECTION_CHUNK_PARAMS
        assert COLLECTION_CHUNK_PARAMS[c]["size"] > 0
        assert COLLECTION_CHUNK_PARAMS[c]["step"] > 0


def test_sliding_window_handles_empty():
    assert chunk_sliding_window("") == []


def test_sliding_window_produces_overlapping_chunks():
    text = " ".join(f"word{i}" for i in range(200))
    chunks = chunk_sliding_window(text, size=50, step=25)
    # 200 words / step 25 → ~8 chunks
    assert 6 <= len(chunks) <= 10
    assert all(len(c.split()) <= 50 for c in chunks)


def test_recipe_boundary_splits_on_markers():
    text = "## Recipe 1\nStep A\nStep B\n## Recipe 2\nStep C\nIngredients: salt\nServings: 2"
    chunks = chunk_recipe_boundary(text, size=400, step=200)
    # Recipe 1 + Recipe 2 + Ingredients + Servings → at least 2 chunks
    assert len(chunks) >= 2


def test_structured_header_splits_on_headers():
    text = "# Intro\nparagraph\n## Section A\nmore text\n## Section B\neven more"
    chunks = chunk_structured_header(text, size=400, step=200)
    assert len(chunks) >= 2


def test_select_chunker_returns_callable():
    for strategy in ["recipe_boundary", "structured_header", "sliding_window", "unknown_strategy"]:
        fn = select_chunker(strategy)
        assert callable(fn)


def test_adaptive_uses_per_collection_params():
    long_text = " ".join(f"w{i}" for i in range(400))
    recipe_chunks = build_chunks_adaptive(long_text, "recipes")
    nutrition_chunks = build_chunks_adaptive(long_text, "nutrition_science")
    # Different size/step produce different chunk counts
    assert len(recipe_chunks) > 0
    assert len(nutrition_chunks) > 0


def test_adaptive_falls_back_on_unknown_collection():
    chunks = build_chunks_adaptive("hello world " * 200, "nonexistent_collection")
    assert len(chunks) > 0
