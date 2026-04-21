"""Response validator — runs AFTER the agent produces a response, before it ships to the user.

Catches four classes of output defect:

1. **Unsupported confidence claim** — `supported` tier must carry citations; a
   supported tier with zero citations is a bug or a hallucination escape.
2. **Missing disclaimer** — when `requires_disclaimer` is True, the
   `disclaimer_text` must be non-empty AND the answer should not contradict it.
3. **Forbidden-phrase escape** — the response text must not contain diagnostic
   or curative claims (sampled from `medical_boundary_sample`).
4. **Tier / confidence consistency** — a `supported` response with
   confidence=0.0 is inconsistent; a `refused` with citations is inconsistent.

Pure Python, no network. Used by the agent loop as a post-validation step and
by tests to pin output-shape invariants.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mealmaster_ai.validation.medical_boundary_sample import (
    contains_forbidden_phrase,
)


@dataclass
class ResponseValidation:
    """Result of validating a structured agent response."""

    ok: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _as_dict(response: Any) -> dict[str, Any]:
    """Accept a Pydantic model or a dict; normalize to dict."""
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if isinstance(response, dict):
        return response
    raise TypeError(f"response must be a Pydantic model or dict, got {type(response)}")


def validate_response(response: Any) -> ResponseValidation:
    """Return a `ResponseValidation` with any issues or warnings found."""
    data = _as_dict(response)
    issues: list[str] = []
    warnings: list[str] = []

    tier = data.get("evidence_tier")
    confidence = float(data.get("confidence") or 0.0)
    answer = str(data.get("answer") or "")
    citations = data.get("citations") or []
    requires_disclaimer = bool(data.get("requires_disclaimer"))
    disclaimer = data.get("disclaimer_text")

    # 1. Citations invariant
    if tier == "supported" and not citations:
        issues.append("tier=supported has no citations (hallucination risk)")
    if tier == "refused" and citations:
        warnings.append("tier=refused unexpectedly has citations (tier flipped after retrieval?)")

    # 2. Tier / confidence consistency
    if tier == "supported" and confidence <= 0.0:
        issues.append("tier=supported with confidence<=0.0 is inconsistent")
    if tier == "refused" and confidence > 0.3:
        warnings.append("tier=refused but confidence>0.3 — evidence-gate logic may be off")

    # 3. Disclaimer invariant
    if requires_disclaimer:
        if not disclaimer:
            issues.append("requires_disclaimer=True but disclaimer_text is empty")
        if tier == "supported" and disclaimer and "not medical advice" not in (answer + " " + (disclaimer or "")).lower():
            warnings.append("supported tier with requires_disclaimer lacks 'not medical advice' marker")

    # 4. Forbidden-phrase escape
    forbidden = contains_forbidden_phrase(answer)
    if forbidden:
        issues.append(f"answer contains forbidden phrase: {forbidden!r}")

    # 5. Empty-answer guard
    if len(answer.strip()) < 10:
        issues.append("answer is empty or trivially short")

    return ResponseValidation(ok=len(issues) == 0, issues=issues, warnings=warnings)
