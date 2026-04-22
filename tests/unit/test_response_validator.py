"""Response validator — output-shape invariants for the agent response."""
from __future__ import annotations

from structured_models import CapstoneRAGResponse, Citation
from mealmaster_ai.validation.response_validator import validate_response


def _supported_response(**overrides):
    defaults = dict(
        answer="Supported response grounded in chunk X with clear evidence, not medical advice.",
        evidence_tier="supported",
        confidence=0.7,
        citations=[Citation(chunk_id="x::0001", source_title="Source", collection="nutrition_science", score=0.7)],
        tool_calls=[],
        requires_disclaimer=False,
        disclaimer_text=None,
    )
    defaults.update(overrides)
    return CapstoneRAGResponse(**defaults)


def test_valid_supported_response_passes():
    v = validate_response(_supported_response())
    assert v.ok, v.issues


def test_supported_without_citations_fails():
    r = _supported_response(citations=[])
    v = validate_response(r)
    assert not v.ok
    assert any("no citations" in i for i in v.issues)


def test_supported_with_zero_confidence_fails():
    r = _supported_response(confidence=0.0)
    v = validate_response(r)
    assert not v.ok


def test_requires_disclaimer_without_text_fails():
    r = _supported_response(requires_disclaimer=True, disclaimer_text=None)
    v = validate_response(r)
    assert not v.ok
    assert any("disclaimer" in i for i in v.issues)


def test_forbidden_phrase_in_answer_fails():
    r = _supported_response(answer="This will cure your iron deficiency if you eat spinach every day.")
    v = validate_response(r)
    assert not v.ok
    assert any("forbidden phrase" in i for i in v.issues)


def test_empty_answer_fails():
    r = _supported_response(answer="   ")
    v = validate_response(r)
    assert not v.ok


def test_refused_with_citations_warns_not_fails():
    r = _supported_response(
        evidence_tier="refused",
        confidence=0.0,
        citations=[Citation(chunk_id="x::0001", source_title="S", collection="recipes", score=0.1)],
    )
    v = validate_response(r)
    # Refused+citations is a warning, not a hard fail
    assert any("refused" in w for w in v.warnings)


def test_validate_response_accepts_dict_input():
    """Validator must accept a plain dict as well as a Pydantic model."""
    v = validate_response({
        "answer": "ok ok ok ok ok ok ok ok ok ok ok",
        "evidence_tier": "supported",
        "confidence": 0.5,
        "citations": [{"chunk_id": "x", "source_title": "s", "collection": "c", "score": 0.5}],
        "requires_disclaimer": False,
        "disclaimer_text": None,
    })
    assert v.ok, v.issues


def test_validate_response_none_does_not_raise():
    """Regression pin for v3 TypeError fix — validator must NOT raise on None.

    Root cause of the live-Streamlit `TypeError` on `Generate plan`:
    `_run_pydantic_ai` could return `None` (when pydantic-ai failed to parse
    structured output) and `validate_response(None)` used to raise TypeError
    from `_as_dict` — propagating uncaught out of `run_agent` to Streamlit's
    call site. Validator must now surface the shape issue, not crash.
    """
    v = validate_response(None)
    assert v.ok is False
    assert any("shape invalid" in i for i in v.issues), v.issues
    assert any("NoneType" in i for i in v.issues), v.issues


def test_validate_response_unexpected_type_does_not_raise():
    """Same regression pin — string, list, and bare int inputs all handled gracefully."""
    for bad in ("a raw string", ["list", "not dict"], 42):
        v = validate_response(bad)
        assert v.ok is False
        assert any("shape invalid" in i for i in v.issues), (bad, v.issues)
