"""Agent behavioural tests — query-side boundary pre-check + response shape."""
from __future__ import annotations

from agent_config import AgentConfig
from backend.services.corpus_manager import load_all_demo_indexes
from pydantic_agent import (
    _pick_relevant_sentences,
    _query_contains_curative_claim,
    run_agent,
)


def test_curative_query_detector_positive():
    assert _query_contains_curative_claim("Can I cure my diabetes with kale?")
    assert _query_contains_curative_claim("Will cure my asthma if I do this")
    assert _query_contains_curative_claim("prescribe me a diet")
    assert _query_contains_curative_claim("reverse my iron deficiency")


def test_curative_query_detector_negative():
    assert not _query_contains_curative_claim("What is the RDA for vitamin D?")
    assert not _query_contains_curative_claim("Show me a low-sodium pasta recipe")
    assert not _query_contains_curative_claim("How does vitamin C affect iron absorption?")


def test_curative_query_refused_pre_retrieval():
    """gt_007 behavior: curative query → refused tier + clinician-referral disclaimer.

    Pins the regression: before this chunk, the agent retrieved on cure queries and
    returned 'supported' responses. The new query-side pre-check blocks that path.
    """
    load_all_demo_indexes()
    response = run_agent("Can I cure my iron deficiency by eating spinach?", AgentConfig.from_env())
    assert response.evidence_tier == "refused"
    assert response.confidence == 0.0
    assert response.requires_disclaimer is True
    assert response.disclaimer_text
    assert not response.citations  # no retrieval happened
    # The refusal text must mention clinician / healthcare professional
    assert any(term in response.answer.lower() for term in ("professional", "clinician", "dietitian"))
    # Must not include a curative claim itself
    assert "will cure" not in response.answer.lower()


def test_pick_relevant_sentences_prioritizes_query_overlap():
    chunk = (
        "The chef prepares the pasta sauce. "
        "Vitamin D is a fat-soluble vitamin essential for bone health. "
        "Serve with whole-wheat pasta and low-sodium tomato sauce."
    )
    query = "vitamin D bone"
    picked = _pick_relevant_sentences(chunk, query, max_sentences=1)
    assert "vitamin" in picked.lower() and "bone" in picked.lower()


def test_non_curative_query_retrieves_normally():
    """Sanity: a normal nutrition query still flows through retrieval + evidence gate."""
    load_all_demo_indexes()
    response = run_agent("What are the main functions of dietary fiber?", AgentConfig.from_env())
    assert response.evidence_tier in ("supported", "fallback")
    assert len(response.citations) >= 1
