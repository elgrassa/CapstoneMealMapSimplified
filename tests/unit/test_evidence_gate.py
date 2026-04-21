"""Evidence gate — tier threshold logic + authority-weight application.

Behavioral guarantees these tests pin:
- Authority weights apply only to evidence collections (not recipes).
- Sorting uses the adjusted score (weight * raw).
- Three tiers: supported / fallback / refused with the correct thresholds.
- Safety-sensitive top-3 propagates `require_disclaimer`.
"""
from __future__ import annotations

from mealmaster_ai.rag.evidence_gate import (
    AUTHORITY_WEIGHTS,
    DEFAULT_FALLBACK_MESSAGE,
    DEFAULT_REFUSAL_MESSAGE,
    EVIDENCE_COLLECTIONS,
    evaluate_evidence,
)


def test_empty_input_refuses():
    decision = evaluate_evidence([])
    assert decision.status == "refused"
    assert decision.confidence == 0.0
    assert decision.fallback_message == DEFAULT_REFUSAL_MESSAGE


def test_authority_weight_applies_to_evidence_only():
    results = [
        {"chunk_id": "ev", "score": 0.25, "collection": "nutrition_science", "authority_level": "high"},
        {"chunk_id": "rc", "score": 0.25, "collection": "recipes", "authority_level": "high"},
    ]
    d = evaluate_evidence(results)
    # High-authority evidence chunk gets 0.25 * 1.3 = 0.325 > 0.3 → supported
    assert d.status == "supported"
    # Recipes authority is ignored so the recipes chunk stays at 0.25 (fallback-range)
    # The evidence chunk ranks first.
    assert d.sources[0]["collection"] == "nutrition_science"


def test_fallback_tier_between_thresholds():
    results = [{"chunk_id": "x", "score": 0.15, "collection": "recipes"}]
    d = evaluate_evidence(results)
    assert d.status == "fallback"
    assert d.fallback_message == DEFAULT_FALLBACK_MESSAGE


def test_refused_below_floor():
    results = [{"chunk_id": "x", "score": 0.05, "collection": "recipes"}]
    d = evaluate_evidence(results)
    assert d.status == "refused"
    assert d.fallback_message == DEFAULT_REFUSAL_MESSAGE


def test_safety_sensitive_top3_triggers_disclaimer():
    results = [
        {"chunk_id": "a", "score": 0.5, "collection": "recipes", "safety_sensitive": True},
        {"chunk_id": "b", "score": 0.3, "collection": "recipes"},
    ]
    d = evaluate_evidence(results)
    assert d.require_disclaimer is True


def test_custom_authority_weights_flip_decision():
    """A custom low weight for `medium` pushes a borderline result from supported to fallback."""
    results = [{"chunk_id": "x", "score": 0.4, "collection": "nutrition_science", "authority_level": "medium"}]
    d_default = evaluate_evidence(results)
    d_low_weight = evaluate_evidence(results, authority_weights={"medium": 0.5, "high": 1.3, "low": 0.7})
    assert d_default.status == "supported"
    assert d_low_weight.status == "fallback"


def test_evidence_collections_set_contains_expected():
    assert "nutrition_science" in EVIDENCE_COLLECTIONS
    assert "health_food_practical" in EVIDENCE_COLLECTIONS
    assert "medical_dietary_guidelines" in EVIDENCE_COLLECTIONS
    assert "recipes" not in EVIDENCE_COLLECTIONS


def test_authority_weights_monotonic():
    assert AUTHORITY_WEIGHTS["high"] > AUTHORITY_WEIGHTS["medium"] > AUTHORITY_WEIGHTS["low"]
