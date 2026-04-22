"""9 agent tools.

Each tool has a docstring the LLM sees as its description, structured inputs
and outputs (dicts compatible with PydanticAI's tool-plain schema), and an
implementation that runs on the sample data shipped with the repo. Production
at meal-map.app uses the same tool shape with tuned catalogs.
"""
from __future__ import annotations

import re
from typing import Any

from mealmaster_ai.data.canonical_ingredients_sample import (
    macro_summary,
    CANONICAL_INGREDIENTS_SAMPLE,
)
from mealmaster_ai.validation.medical_boundary_sample import (
    contains_forbidden_phrase,
    detect_referral_triggers,
    DEFAULT_MEDICAL_DISCLAIMER,
    FORBIDDEN_PHRASES_SAMPLE,
    REFERRAL_TRIGGERS_SAMPLE,
)
from mealmaster_ai.rag.evidence_gate import evaluate_evidence
from mealmaster_ai.rag.router import classify_intent, route_query
from mealmaster_ai.rag.search import run_collection_search

from rules_corpus import RULES_CORPUS_SAMPLE, rules_by_tag


# Module-level index registry. NOTE: shared across all Streamlit sessions that
# hit the same server process. For multi-user demos, prefer session-scoped keys
# like `user_books_<session_id>` for user-uploaded indexes (see demo_ui/app.py).
# For the baked demo corpus (shared, read-only) this is the right scope.
_DEFAULT_INDEX_REGISTRY: dict[str, Any] = {}


def register_index(collection: str, index: Any) -> None:
    """Register a loaded BM25 index so the tools can use it.

    The Streamlit demo + backend call this at startup with the baked demo indexes.

    Caller contract:
    - For shared, read-only corpus indexes (recipes, nutrition_science), use the
      plain collection name.
    - For per-user indexes (e.g. uploaded books in Tab 1 / Tab 2), use a
      session-scoped key such as ``user_books_<session_id>`` to avoid leaking
      one user's upload to another Streamlit session on the same process.
    """
    _DEFAULT_INDEX_REGISTRY[collection] = index


def unregister_index(collection: str) -> None:
    """Remove an index — used by session cleanup in the demo UI."""
    _DEFAULT_INDEX_REGISTRY.pop(collection, None)


def available_collections() -> list[str]:
    return sorted(_DEFAULT_INDEX_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Tool 1 — assess_query_strategy
# ---------------------------------------------------------------------------
def assess_query_strategy(query: str) -> dict[str, Any]:
    """Classify the query and recommend which search mode + collection mix to use.

    Always call this tool FIRST. It routes the query to the right collections
    and flags whether the response needs a medical disclaimer.

    Args:
        query: The user's natural-language question.

    Returns:
        dict with keys: `intent`, `recommended_mode`, `collections`,
        `requires_disclaimer`, `demo_blocked_collections`, `reason`.
    """
    routing = route_query(query, demo_mode=True)
    recommended_mode = "hybrid" if routing.intent in ("nutrition", "medical") else "bm25"
    return {
        "intent": routing.intent,
        "recommended_mode": recommended_mode,
        "collections": routing.collections,
        "requires_disclaimer": routing.requires_disclaimer,
        "demo_blocked_collections": routing.demo_blocked_collections,
        "reason": routing.reason,
    }


# ---------------------------------------------------------------------------
# Tool 2 — search_knowledge
# ---------------------------------------------------------------------------
def search_knowledge(
    query: str,
    collections: list[str] | None = None,
    top_k: int = 5,
    mode: str = "bm25",
) -> dict[str, Any]:
    """Retrieve evidence chunks from the demo knowledge base.

    Args:
        query: The search query.
        collections: If None, uses all registered collections. Otherwise filters.
        top_k: Number of results per collection.
        mode: "bm25" (default) or "hybrid" (only if embeddings are baked).

    Returns:
        dict with `results: list[dict]` (flat chunk dicts with score + citation fields)
        and `stats: dict` (per-collection counts).
    """
    target = collections or available_collections()
    all_results: list[dict[str, Any]] = []
    stats: dict[str, int] = {}
    for c in target:
        idx = _DEFAULT_INDEX_REGISTRY.get(c)
        if idx is None:
            continue
        hits = run_collection_search(idx, query, num_results=top_k, collection=c)
        stats[c] = len(hits)
        all_results.extend(hits)
    all_results.sort(key=lambda r: float(r.get("score") or 0.0), reverse=True)
    return {"results": all_results[: top_k * len(target) if target else top_k], "stats": stats, "mode": mode}


# ---------------------------------------------------------------------------
# Tool 3 — check_allergens
# ---------------------------------------------------------------------------
_SIMPLE_ALLERGEN_TERMS: dict[str, list[str]] = {
    "gluten": ["wheat", "barley", "rye", "oats"],
    "dairy": ["milk", "cream", "butter", "cheese", "yogurt"],
    "eggs": ["egg", "omelet", "meringue"],
    "fish": ["salmon", "tuna", "cod", "mackerel"],
    "tree_nuts": ["almond", "walnut", "pecan", "cashew", "hazelnut"],
    "peanuts": ["peanut", "groundnut"],
    "soy": ["soy", "tofu", "tempeh", "edamame"],
}


def check_allergens(text: str, restricted: list[str] | None = None) -> dict[str, Any]:
    """Word-boundary allergen detection on a recipe / ingredient text.

    Args:
        text: Recipe / ingredient text to scan.
        restricted: List of allergen group keys to check. Defaults to all groups.

    Returns:
        dict with `hits: list[{allergen, matched_term, position}]`, `safe: bool`,
        and `disclaimer: str`. Production uses the full EU-14 allergen taxonomy.
    """
    groups = restricted or list(_SIMPLE_ALLERGEN_TERMS.keys())
    t = text.lower()
    hits: list[dict[str, Any]] = []
    for group in groups:
        for term in _SIMPLE_ALLERGEN_TERMS.get(group, []):
            pattern = re.compile(rf"\b{re.escape(term)}\b")
            match = pattern.search(t)
            if match:
                hits.append({
                    "allergen": group,
                    "matched_term": term,
                    "position": match.start(),
                })
    return {
        "hits": hits,
        "safe": len(hits) == 0,
        "disclaimer": (
            "This check uses a representative subset of the EU-14 allergen list. "
            "Always verify against the full EU-14 set in production."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 4 — get_nutrition_facts
# ---------------------------------------------------------------------------
def get_nutrition_facts(ingredient_name: str) -> dict[str, Any]:
    """Look up macro nutrition for a canonical ingredient.

    Args:
        ingredient_name: e.g. "oats_rolled_dry" or "broccoli_raw".

    Returns:
        dict with `per_100g` macros, `allergens`, `source`, or `error` if not in sample.
    """
    summary = macro_summary(ingredient_name)
    if summary is None:
        return {
            "error": "not_in_sample",
            "available": [i.name for i in CANONICAL_INGREDIENTS_SAMPLE],
            "note": "Demo ships a 10-item sample. Full 82-ingredient catalog lives at meal-map.app.",
        }
    return summary


# ---------------------------------------------------------------------------
# Tool 5 — check_medical_boundaries
# ---------------------------------------------------------------------------
def check_medical_boundaries(text: str) -> dict[str, Any]:
    """Check response text for forbidden medical claims + referral triggers.

    Args:
        text: Candidate response text to validate.

    Returns:
        dict with `forbidden_phrase` (or None), `referral_triggers` (list),
        `boundary_ok: bool`, `disclaimer: str`. This repo ships a 5-phrase +
        2-trigger sample that mirrors the production shape.
    """
    forbidden = contains_forbidden_phrase(text)
    triggers = detect_referral_triggers(text)
    return {
        "forbidden_phrase": forbidden,
        "referral_triggers": [
            {
                "id": t.id,
                "severity": t.severity,
                "description": t.description,
                "action": t.action,
            }
            for t in triggers
        ],
        "boundary_ok": forbidden is None and not any(t.severity == "CRITICAL" for t in triggers),
        "disclaimer": DEFAULT_MEDICAL_DISCLAIMER,
        "sample_counts": {
            "forbidden_phrases_sample": len(FORBIDDEN_PHRASES_SAMPLE),
            "referral_triggers_sample": len(REFERRAL_TRIGGERS_SAMPLE),
            "production_counts_at_meal_map_app": {"forbidden_phrases": 44, "referral_triggers": 9},
        },
    }


# ---------------------------------------------------------------------------
# Tool 6 — get_evidence_confidence
# ---------------------------------------------------------------------------
def get_evidence_confidence(
    search_results: list[dict[str, Any]],
    confidence_threshold: float = 0.3,
    fallback_threshold: float = 0.1,
) -> dict[str, Any]:
    """Run the evidence gate over a retrieved set.

    Args:
        search_results: Output of `search_knowledge`.
        confidence_threshold: Top adjusted score required for `supported`.
        fallback_threshold: Top adjusted score required for `fallback`.

    Returns:
        dict matching `EvidenceGateDecision`: `status`, `confidence`, `sources`,
        `fallback_message`, `require_disclaimer`.
    """
    decision = evaluate_evidence(
        search_results,
        confidence_threshold=confidence_threshold,
        fallback_threshold=fallback_threshold,
    )
    return {
        "status": decision.status,
        "confidence": decision.confidence,
        "sources": decision.sources,
        "fallback_message": decision.fallback_message,
        "require_disclaimer": decision.require_disclaimer,
    }


# ---------------------------------------------------------------------------
# Tool 7 — search_books
# ---------------------------------------------------------------------------
def search_books(query: str, book_ids: list[str] | None = None, top_k: int = 5) -> dict[str, Any]:
    """Search within user-uploaded books (demo Tab 2 "parse my own" mode).

    Args:
        query: Search query.
        book_ids: Optional filter to specific book IDs registered via `add_book_note`.
        top_k: Number of results.

    Returns:
        dict with `results: list[dict]` — chunk dicts from the in-memory user-book index.
    """
    idx = _DEFAULT_INDEX_REGISTRY.get("user_books")
    if idx is None:
        return {"results": [], "note": "No user books registered — upload a text in Tab 2 first."}
    results = run_collection_search(idx, query, num_results=top_k, collection="user_books")
    if book_ids:
        results = [r for r in results if r.get("doc_id") in book_ids]
    return {"results": results}


# ---------------------------------------------------------------------------
# Tool 8 — add_book_note
# ---------------------------------------------------------------------------
_BOOK_NOTES: dict[str, list[str]] = {}


def add_book_note(book_id: str, note: str) -> dict[str, Any]:
    """Append a user-authored note to a book's note list.

    Args:
        book_id: Book ID returned by the parse-my-own upload.
        note: Free-text note.

    Returns:
        dict with `book_id`, `note_count_after`, confirming persistence.
    """
    _BOOK_NOTES.setdefault(book_id, []).append(note)
    return {"book_id": book_id, "note_count_after": len(_BOOK_NOTES[book_id])}


# ---------------------------------------------------------------------------
# Tool 9 — get_recipe_metadata (structured fields, not chunk text)
# ---------------------------------------------------------------------------
import functools as _functools
import json as _json
from pathlib import Path as _Path


@_functools.lru_cache(maxsize=1)
def _load_recipes_json() -> dict[str, Any]:
    """Load data/rag/demo/derived/recipes.json once per process. Fail-safe."""
    try:
        # THIS_FILE = ai/week1-rag/agent_tools_v2.py → parents[2] = repo root
        here = _Path(__file__).resolve()
        candidates = [
            here.parents[2] / "data" / "rag" / "demo" / "derived" / "recipes.json",
            _Path.cwd() / "data" / "rag" / "demo" / "derived" / "recipes.json",
        ]
        for p in candidates:
            if p.exists():
                return _json.loads(p.read_text(encoding="utf-8"))
        return {"recipes": [], "sample_weekly_plans": [], "_error": "recipes.json not found"}
    except Exception as exc:  # pragma: no cover — defensive
        return {"recipes": [], "sample_weekly_plans": [], "_error": str(exc)}


def get_recipe_metadata(recipe_id: str) -> dict[str, Any]:
    """Return the STRUCTURED metadata for a single recipe — not chunk text.

    IMPORTANT FOR THE LLM: call this tool AFTER `search_knowledge` whenever the
    user mentions an allergen, an age band, or any hard constraint. Retrieval
    gives you candidates; this tool tells you — with certainty — whether each
    candidate satisfies the constraint. `search_knowledge` returns raw chunk
    text and does NOT expose the structured allergen / age-band / meal_type
    fields reliably enough to filter on.

    Args:
        recipe_id: canonical recipe id (e.g. `utah_wic_baked_chicken_with_vegetables`,
            `demo_lentil_stew_carrots_spinach`). Exact match — no fuzzy lookup.

    Returns:
        A dict with:
            title, meal_type, servings, cook_time_minutes,
            nutrition_per_serving (kcal / protein_g / carbs_g / fat_g / fiber_g),
            allergens_eu14 (list of EU-14 allergen group strings),
            suitable_for_age_bands (list of age-band tokens),
            notes.
        OR `{"error": "recipe_id not found", "recipe_id": …, "available_ids": [...]}`
        when the id doesn't exist.
    """
    data = _load_recipes_json()
    for r in data.get("recipes", []):
        if r.get("recipe_id") == recipe_id:
            return {
                "recipe_id": r["recipe_id"],
                "title": r.get("title"),
                "meal_type": r.get("meal_type"),
                "servings": r.get("servings"),
                "cook_time_minutes": r.get("cook_time_minutes"),
                "cuisine": r.get("cuisine"),
                "nutrition_per_serving": r.get("nutrition_per_serving", {}),
                "allergens_eu14": r.get("allergens_eu14", []),
                "suitable_for_age_bands": r.get("suitable_for_age_bands", []),
                "notes": r.get("notes"),
            }
    return {
        "error": "recipe_id not found",
        "recipe_id": recipe_id,
        "available_ids": [r.get("recipe_id") for r in data.get("recipes", [])],
    }


# ---------------------------------------------------------------------------
# Dispatcher used by the agent runner + tests
# ---------------------------------------------------------------------------
TOOL_FUNCTIONS: dict[str, Any] = {
    "assess_query_strategy": assess_query_strategy,
    "search_knowledge": search_knowledge,
    "check_allergens": check_allergens,
    "get_nutrition_facts": get_nutrition_facts,
    "check_medical_boundaries": check_medical_boundaries,
    "get_evidence_confidence": get_evidence_confidence,
    "search_books": search_books,
    "add_book_note": add_book_note,
    "get_recipe_metadata": get_recipe_metadata,
}


def execute_tool(name: str, **kwargs) -> dict[str, Any]:
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return {"error": f"unknown tool: {name}", "available": sorted(TOOL_FUNCTIONS.keys())}
    return fn(**kwargs)
