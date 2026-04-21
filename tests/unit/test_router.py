"""Router — intent classification + demo-mode allow-list."""
from __future__ import annotations

from mealmaster_ai.rag.router import classify_intent, route_query


def test_medical_intent_detected():
    assert classify_intent("Can vitamin D help treat my iron deficiency symptoms?") == "medical"


def test_recipe_intent_detected():
    assert classify_intent("Show me a baked chicken recipe") == "recipe"


def test_nutrition_intent_detected():
    assert classify_intent("What is the RDA for protein?") == "nutrition"


def test_demo_mode_blocks_non_allowed_collections():
    result = route_query("What is the medical treatment for iron deficiency?", demo_mode=True)
    # Medical intent tries to route to `medical_dietary_guidelines` which is demo-blocked
    assert "medical_dietary_guidelines" in result.demo_blocked_collections
    assert all(c in ("recipes", "nutrition_science") for c in result.collections)


def test_demo_mode_disabled_routes_freely():
    result = route_query("What is the medical treatment for iron deficiency?", demo_mode=False, available_collections=None)
    # Without demo_mode filtering, medical routes to production collections
    assert not result.demo_blocked_collections


def test_recipe_query_routes_to_recipes():
    result = route_query("What's a family-friendly pasta recipe?", demo_mode=True)
    assert "recipes" in result.collections
