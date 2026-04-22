"""Post-hoc validator for structured agent responses.

Runs after the agent returns, before the response ships to the user. Flags:
`supported` tier with zero citations, `requires_disclaimer=True` with empty
disclaimer text, forbidden medical phrases in the answer body, and tier /
confidence inconsistency (e.g. `supported` with confidence=0.0).

Pure Python, no network.
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
    """Accept a Pydantic model, a dict, or — as a fallback — return a synthetic
    error-shaped dict.

    Never raises. A validator that crashes the whole request pipeline is worse
    than one that flags an issue. If something upstream hands us `None`, a raw
    string, or any other unexpected shape, we surface it via a `_shape_error`
    key the caller then folds into `issues`.
    """
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if isinstance(response, dict):
        return response
    return {
        "answer": f"(validator received unexpected type: {type(response).__name__})",
        "evidence_tier": "refused",
        "confidence": 0.0,
        "citations": [],
        "requires_disclaimer": False,
        "disclaimer_text": None,
        "_shape_error": f"unexpected response type: {type(response).__name__}",
    }


def validate_response(response: Any) -> ResponseValidation:
    """Return a `ResponseValidation` with any issues or warnings found."""
    data = _as_dict(response)
    issues: list[str] = []
    warnings: list[str] = []

    # Shape error from `_as_dict` — surface as an issue, then keep going so the
    # caller also sees the tier/confidence/answer checks that fail below.
    if data.get("_shape_error"):
        issues.append(f"response shape invalid: {data['_shape_error']}")

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
