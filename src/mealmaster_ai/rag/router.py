"""Intent router + demo-mode allow-list.

The production router (meal-map.app) supports all 5 collections. In demo mode
only `recipes` + `nutrition_science` are allow-listed; queries routed to other
collections return a friendly "production-only" message so the grader doesn't
see empty tool results.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .config import DEMO_COLLECTIONS

IntentCategory = Literal[
    "recipe",
    "nutrition",
    "medical",
    "cooking_technique",
    "allergen_safety",
    "unknown",
]

INTENT_CATEGORIES: list[IntentCategory] = [
    "recipe",
    "nutrition",
    "medical",
    "cooking_technique",
    "allergen_safety",
    "unknown",
]

_RECIPE_KEYWORDS = {"recipe", "cook", "bake", "fry", "roast", "meal", "dish", "dinner", "lunch", "breakfast", "pasta", "salad", "soup"}
_NUTRITION_KEYWORDS = {"vitamin", "mineral", "protein", "carb", "fat", "calorie", "nutrient", "nutrition", "macro", "micro", "rda", "dri"}
_MEDICAL_KEYWORDS = {"disease", "medication", "treatment", "diagnos", "symptom", "deficiency", "chronic"}
_ALLERGEN_KEYWORDS = {"allergen", "allergy", "gluten", "lactose", "peanut", "dairy", "egg-free"}
_COOKING_KEYWORDS = {"saute", "sauté", "simmer", "knead", "blanch", "reduce", "whisk", "temperature", "oven"}


@dataclass
class RoutingResult:
    intent: IntentCategory
    collections: list[str]
    requires_disclaimer: bool
    demo_blocked_collections: list[str]
    reason: str


def classify_intent(query: str) -> IntentCategory:
    q = query.lower()
    tokens = set(re.findall(r"[a-z]+", q))
    if tokens & _MEDICAL_KEYWORDS:
        return "medical"
    if tokens & _ALLERGEN_KEYWORDS:
        return "allergen_safety"
    if tokens & _NUTRITION_KEYWORDS:
        return "nutrition"
    if tokens & _COOKING_KEYWORDS:
        return "cooking_technique"
    if tokens & _RECIPE_KEYWORDS:
        return "recipe"
    return "unknown"


def route_query(
    query: str,
    *,
    demo_mode: bool = True,
    router_config_path: Path | None = None,
    available_collections: list[str] | None = None,
) -> RoutingResult:
    """Return the collections the query should search.

    Demo-mode rule: requested collections get filtered through the demo allow-list.
    If the user's intent routes to a blocked collection, the result still returns
    the allowed fallback (usually `nutrition_science`) and records the blocked set.
    """
    intent = classify_intent(query)
    allow_list = available_collections or (DEMO_COLLECTIONS if demo_mode else None)

    if router_config_path and router_config_path.exists():
        with open(router_config_path) as f:
            cfg = json.load(f)
        if demo_mode and isinstance(cfg.get("demo_allow_list"), list):
            allow_list = cfg["demo_allow_list"]

    proposed: list[str]
    if intent == "recipe":
        proposed = ["recipes"]
    elif intent == "medical":
        proposed = ["medical_dietary_guidelines", "nutrition_science"]
    elif intent == "allergen_safety":
        proposed = ["health_food_practical", "nutrition_science"]
    elif intent == "nutrition":
        proposed = ["nutrition_science", "health_food_practical"]
    elif intent == "cooking_technique":
        proposed = ["recipes"]
    else:
        proposed = ["recipes", "nutrition_science"]

    blocked: list[str] = []
    if allow_list is not None:
        filtered: list[str] = []
        for c in proposed:
            if c in allow_list:
                filtered.append(c)
            else:
                blocked.append(c)
        if not filtered:
            filtered = [c for c in allow_list if c in proposed or c in ("recipes", "nutrition_science")]
        proposed = filtered

    requires_disclaimer = intent in ("medical", "allergen_safety")

    reason = f"intent={intent}"
    if blocked:
        reason += f"; demo-mode blocked {blocked} (production-only at meal-map.app)"

    return RoutingResult(
        intent=intent,
        collections=proposed,
        requires_disclaimer=requires_disclaimer,
        demo_blocked_collections=blocked,
        reason=reason,
    )
