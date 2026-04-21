"""Offline eval — runs an end-to-end agent + judge pass without OPENAI_API_KEY.

Uses `fixtures/mock_llm_responses.json` for deterministic judge output and the
deterministic-fallback path inside `pydantic_agent.run_agent` for the response.
"""
from __future__ import annotations

import json
from pathlib import Path

from evals.llm_judge import JUDGE_CRITERIA, judge_response_offline


ROOT = Path(__file__).resolve().parents[2]
FIXTURES_PATH = ROOT / "fixtures" / "mock_llm_responses.json"
GT_PATH = ROOT / "ai" / "week1-rag" / "evals" / "ground_truth_handcrafted.json"


def test_judge_criteria_has_six_items():
    assert len(JUDGE_CRITERIA) == 6
    for c in JUDGE_CRITERIA:
        assert "id" in c and "name" in c and "desc" in c


def test_judge_offline_scoring_produces_valid_result():
    fixtures = json.loads(FIXTURES_PATH.read_text())
    result = judge_response_offline(
        "What is the RDA for vitamin D in adults?",
        "Grounded response based on Open Oregon chunk…",
        fixtures,
    )
    assert result.max == 6
    assert 0 <= result.total <= 6
    assert len(result.scores) == 6


def test_ground_truth_file_loads_and_has_expected_shape():
    data = json.loads(GT_PATH.read_text())
    assert "cases" in data
    for case in data["cases"]:
        assert "query" in case
        assert "expected_chunk_ids" in case
        assert "expected_collection" in case


def test_end_to_end_agent_plus_judge_runs_offline():
    """End-to-end: agent retrieves from the demo corpus and judge scores via fixtures."""
    # Ensure indexes loaded
    from backend.services.corpus_manager import load_all_demo_indexes
    load_all_demo_indexes()

    from agent_config import AgentConfig
    from pydantic_agent import run_agent

    fixtures = json.loads(FIXTURES_PATH.read_text())
    response = run_agent("What is the RDA for vitamin D in adults?", AgentConfig.from_env())
    assert response.evidence_tier in ("supported", "fallback", "refused")
    assert len(response.tool_calls) >= 2  # at minimum: assess_query_strategy + search_knowledge

    judge = judge_response_offline("What is the RDA for vitamin D in adults?", response.answer, fixtures)
    assert judge.total <= judge.max
