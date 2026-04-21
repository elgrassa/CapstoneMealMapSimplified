"""Structured output models — validation."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from structured_models import AgentQueryRequest, CapstoneRAGResponse, Citation, JudgeResult, JudgeScore


def test_query_request_rejects_short_query():
    with pytest.raises(ValidationError):
        AgentQueryRequest(query="hi")


def test_query_request_accepts_valid():
    req = AgentQueryRequest(query="What is the RDA for vitamin D?")
    assert req.demo_mode is True
    assert req.use_preprocessed_corpus is True


def test_rag_response_requires_tier():
    with pytest.raises(ValidationError):
        CapstoneRAGResponse(answer="x", evidence_tier="unknown", confidence=0.5)  # type: ignore[arg-type]


def test_rag_response_accepts_large_confidence():
    """BM25 scores have no natural upper bound; the schema must tolerate >1.0 values."""
    r = CapstoneRAGResponse(answer="x", evidence_tier="supported", confidence=5.2, citations=[])
    assert r.confidence == 5.2


def test_citation_requires_nonnegative_score():
    with pytest.raises(ValidationError):
        Citation(chunk_id="a", source_title="t", collection="recipes", score=-0.1)


def test_judge_result_passed_above_threshold():
    scores = [JudgeScore(criterion=f"c{i}", score=1, rationale="ok") for i in range(5)]
    jr = JudgeResult(query="q", response="r", scores=scores, total=5, max=6)
    assert jr.passed is True


def test_judge_result_failed_below_threshold():
    scores = [JudgeScore(criterion=f"c{i}", score=0, rationale="bad") for i in range(6)]
    jr = JudgeResult(query="q", response="r", scores=scores, total=0, max=6)
    assert jr.passed is False
