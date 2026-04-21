"""Agent tool tests — 8 tools exist, each returns the documented shape."""
from __future__ import annotations

import pytest

from agent_tools_v2 import (
    TOOL_FUNCTIONS,
    assess_query_strategy,
    check_allergens,
    check_medical_boundaries,
    get_evidence_confidence,
    get_nutrition_facts,
)


def test_eight_tools_registered():
    expected = {
        "assess_query_strategy",
        "search_knowledge",
        "check_allergens",
        "get_nutrition_facts",
        "check_medical_boundaries",
        "get_evidence_confidence",
        "search_books",
        "add_book_note",
    }
    assert set(TOOL_FUNCTIONS.keys()) == expected


def test_assess_query_strategy_returns_required_keys():
    out = assess_query_strategy("What is vitamin D?")
    for key in ("intent", "recommended_mode", "collections", "requires_disclaimer", "reason"):
        assert key in out


def test_check_allergens_finds_dairy_in_milk():
    out = check_allergens("milk and cookies")
    assert out["safe"] is False
    assert any(h["allergen"] == "dairy" for h in out["hits"])


def test_check_allergens_clean_text():
    out = check_allergens("plain salad with cucumber and tomato")
    assert out["safe"] is True
    assert out["hits"] == []


def test_get_nutrition_facts_known():
    facts = get_nutrition_facts("oats_rolled_dry")
    assert "per_100g" in facts
    assert facts["per_100g"]["protein_g"] > 10


def test_get_nutrition_facts_unknown_returns_error():
    facts = get_nutrition_facts("definitely-not-in-the-sample")
    assert facts.get("error") == "not_in_sample"
    assert "available" in facts


def test_check_medical_boundaries_flags_forbidden_phrase():
    out = check_medical_boundaries("I will cure your iron deficiency")
    assert out["boundary_ok"] is False
    assert out["forbidden_phrase"] is not None


def test_check_medical_boundaries_accepts_safe_text():
    out = check_medical_boundaries("Iron is important for oxygen transport. Consult a clinician if you have concerns.")
    assert out["boundary_ok"] is True


def test_get_evidence_confidence_passes_through_to_gate():
    results = [{"chunk_id": "x", "score": 0.5, "collection": "recipes"}]
    out = get_evidence_confidence(results)
    assert out["status"] in ("supported", "fallback", "refused")
    assert "confidence" in out
    assert "sources" in out
