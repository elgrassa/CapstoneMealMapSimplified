"""Agent behavioural tests — query-side boundary pre-check + response shape."""
from __future__ import annotations

from agent_config import AgentConfig
from backend.services.corpus_manager import load_all_demo_indexes
from pydantic_agent import (
    _enforce_constraints_with_rerun,
    _extract_recipe_ids_from_response,
    _household_constraint_check,
    _pick_relevant_sentences,
    _query_contains_curative_claim,
    run_agent,
)
from structured_models import CapstoneRAGResponse


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


# --- Household constraint post-filter ---


def test_extract_recipe_ids_picks_known_ids_out_of_free_text():
    """Regex must recover recipe_ids from natural LLM answer text."""
    answer = (
        "Here are 3 dinners: `utah_wic_baked_chicken_with_vegetables`, "
        "demo_lentil_stew_carrots_spinach, and ca_wic_banana_oat_pancakes."
    )
    ids = _extract_recipe_ids_from_response(answer)
    assert "utah_wic_baked_chicken_with_vegetables" in ids
    assert "demo_lentil_stew_carrots_spinach" in ids
    assert "ca_wic_banana_oat_pancakes" in ids


def test_household_constraint_check_passes_safe_recipe():
    ok, violations = _household_constraint_check("utah_wic_baked_chicken_with_vegetables")
    assert ok is True
    assert violations == []


def test_household_constraint_check_flags_dairy_in_pancakes():
    """Banana oat pancakes contain dairy — Adult 2 is dairy-allergic → must violate."""
    ok, violations = _household_constraint_check("ca_wic_banana_oat_pancakes")
    assert ok is False
    assert any("dairy" in v.lower() for v in violations)


def test_household_constraint_check_flags_age_band_for_pasta():
    """Pasta primavera is not toddler_1_3 suitable → must violate Child 2's age band."""
    ok, violations = _household_constraint_check("utah_wic_low_sodium_pasta_primavera")
    assert ok is False
    assert any("toddler_1_3" in v for v in violations)


def test_household_constraint_check_tolerates_unknown_recipe():
    """Unknown recipe_id → (True, []) so the post-filter doesn't falsely flag it."""
    ok, violations = _household_constraint_check("zzz_not_a_real_recipe")
    assert ok is True
    assert violations == []


def test_extract_recipe_ids_empty_on_plain_text():
    assert _extract_recipe_ids_from_response("Just some nutrition advice without recipe ids.") == []


# --- Real-LLM-path hardening (v3 regression pins) ---


def test_run_pydantic_ai_raises_typeerror_on_bad_output(monkeypatch):
    """v3 regression pin — uncaught TypeError on live Streamlit.

    If pydantic-ai hands back a non-CapstoneRAGResponse output (e.g. None when
    structured-output validation failed upstream), `_run_pydantic_ai` MUST raise
    TypeError INSIDE its own frame — NOT silently return a broken shape that
    later crashes `validate_response`. That way the existing outer
    try/except in `run_agent` catches it and falls through to the deterministic
    path cleanly.
    """
    import pydantic_agent as pa

    class _FakeResult:
        output = None  # simulate pydantic-ai returning no structured output

    class _FakeAgent:
        def __init__(self, *a, **kw):
            pass

        def tool_plain(self, fn):
            return fn

        def run_sync(self, query):
            return _FakeResult()

    fake_module = type("_M", (), {"Agent": _FakeAgent})
    monkeypatch.setitem(__import__("sys").modules, "pydantic_ai", fake_module)

    cfg = AgentConfig.from_env()
    try:
        pa._run_pydantic_ai("any query", cfg)
    except TypeError as exc:
        assert "CapstoneRAGResponse" in str(exc)
        assert "NoneType" in str(exc)
    else:
        raise AssertionError("_run_pydantic_ai should have raised TypeError on None output")


def test_run_agent_survives_broken_pydantic_ai_return(monkeypatch):
    """End-to-end — with a real OPENAI_API_KEY env var forcing the real-LLM branch,
    if `_run_pydantic_ai` raises TypeError, `run_agent` MUST fall through to the
    deterministic path and return a valid CapstoneRAGResponse. The user must
    never see an uncaught exception reach the Streamlit call site.
    """
    load_all_demo_indexes()
    import pydantic_agent as pa

    def _broken_pydantic_ai(query, cfg):
        raise TypeError("simulated: PydanticAI returned NoneType; expected CapstoneRAGResponse.")

    monkeypatch.setattr(pa, "_run_pydantic_ai", _broken_pydantic_ai)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder-not-called")

    response = run_agent(
        "What are the main functions of dietary fiber?",
        AgentConfig.from_env(),
        session_id="regression-v3",
    )
    assert isinstance(response, CapstoneRAGResponse)
    # Deterministic path tagged the failure in reasoning_notes for observability.
    assert "pydantic-ai failed" in (response.reasoning_notes or "")
    assert "TypeError" in (response.reasoning_notes or "")
