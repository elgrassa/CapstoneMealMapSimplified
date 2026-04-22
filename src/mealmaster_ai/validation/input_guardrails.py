"""Pre-agent input guardrails: prompt-injection patterns, off-topic queries,
size / shape violations. Returns a `GuardrailDecision(allowed, reason,
sanitized_query)` the caller can use to block, modify, or pass the query.
Deterministic, no network.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

GuardrailStatus = Literal["allow", "sanitize", "block", "redirect"]
IntentStatus = Literal["on_topic", "redirect", "off_topic", "injection"]

# Case-insensitive substring markers that commonly signal a prompt-injection
# attempt. Not exhaustive — captures the classes, not every variant.
_PROMPT_INJECTION_MARKERS: tuple[str, ...] = (
    "ignore previous instructions",
    "ignore the above",
    "disregard your instructions",
    "system prompt",
    "you are now",
    "act as ",
    "pretend to be",
    "reveal your",
    "print your system",
    "show me your prompt",
    "repeat the above verbatim",
    "do not follow the previous",
    "jailbreak",
    "developer mode",
    "no restrictions",
)

# Off-topic hard markers. Small list — we err toward allow.
_OFF_TOPIC_HARD_MARKERS: tuple[str, ...] = (
    "write code",
    "write a script",
    "solve this math",
    "translate this to",
    "translate to french",
    "summarize this article",
    "summarize this paper",
    "tell me a joke",
    "write a poem",
    "write a song",
    "bitcoin price",
    "stock price",
    "who is the president",
    "capital of ",
    "how old is ",
    "what time is it",
    "what year is",
    "weather in ",
    "movie recommendation",
    "book recommendation",
    "python function",
    "javascript function",
    "compose an email",
)

# If any in-scope marker appears, allow the query.
_IN_SCOPE_MARKERS: tuple[str, ...] = (
    "food", "eat", "eating", "diet", "nutrition", "nutrient", "recipe", "meal",
    "cook", "cooking", "kitchen",
    "vitamin", "mineral", "protein", "carb", "fat", "fiber", "calorie",
    "iron", "calcium", "magnesium", "potassium", "sodium", "zinc", "omega",
    "deficiency", "anemia", "anaemia", "cofactor", "absorption",
    "allergen", "allergy", "gluten", "dairy", "lactose", "vegetarian", "vegan",
    "breakfast", "lunch", "dinner", "snack", "cuisine", "ingredient",
    "pantry", "shopping", "grocery", "portion", "serving", "macro", "micro",
    "dri", "rda", "hydration", "water",
    "spinach", "broccoli", "salmon", "chicken", "pasta", "rice", "bean", "oat",
    "pregnan", "breastfeed", "toddler", "infant", "child",
)

MAX_QUERY_LEN = 2000
MIN_QUERY_LEN = 3


@dataclass
class GuardrailDecision:
    """Result of running input guardrails over a query."""

    status: GuardrailStatus
    allowed: bool
    reason: str
    sanitized_query: str
    blocked_markers: list[str]


def _strip_control_chars(text: str) -> str:
    """Remove control characters that can confuse downstream tokenizers."""
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _find_injection_markers(text: str) -> list[str]:
    low = text.lower()
    return [m for m in _PROMPT_INJECTION_MARKERS if m in low]


def _find_off_topic_markers(text: str) -> list[str]:
    low = text.lower()
    return [m for m in _OFF_TOPIC_HARD_MARKERS if m in low]


def _looks_in_scope(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in _IN_SCOPE_MARKERS)


def sanitize_for_prompt(text: str) -> str:
    """Return a safe-for-prompt version of `text` — used when status is `sanitize`."""
    out = _strip_control_chars(text)
    out = _collapse_whitespace(out)
    return out[:MAX_QUERY_LEN]


def run_input_guardrails(query: str) -> GuardrailDecision:
    """Classify `query` as allow / sanitize / block and return the rationale."""
    if query is None:
        return GuardrailDecision(
            status="block", allowed=False, reason="null_query",
            sanitized_query="", blocked_markers=[],
        )

    raw = str(query)
    stripped = _strip_control_chars(raw).strip()

    # Size checks
    if len(stripped) < MIN_QUERY_LEN:
        return GuardrailDecision(
            status="block", allowed=False, reason="query_too_short",
            sanitized_query="", blocked_markers=[],
        )
    if len(raw) > MAX_QUERY_LEN:
        return GuardrailDecision(
            status="block", allowed=False, reason="query_too_long",
            sanitized_query="", blocked_markers=[],
        )

    # Prompt injection
    inj = _find_injection_markers(stripped)
    if inj:
        return GuardrailDecision(
            status="block", allowed=False, reason="prompt_injection",
            sanitized_query=sanitize_for_prompt(stripped), blocked_markers=inj,
        )

    # Off-topic hard markers override in-scope markers
    off = _find_off_topic_markers(stripped)
    if off and not _looks_in_scope(stripped):
        return GuardrailDecision(
            status="block", allowed=False, reason="off_topic",
            sanitized_query=sanitize_for_prompt(stripped), blocked_markers=off,
        )

    # Sanitize if the raw query has control chars or was longer than expected
    if stripped != raw.strip() or re.search(r"\s{2,}", raw):
        return GuardrailDecision(
            status="sanitize", allowed=True, reason="sanitized",
            sanitized_query=sanitize_for_prompt(stripped), blocked_markers=[],
        )

    return GuardrailDecision(
        status="allow", allowed=True, reason="ok",
        sanitized_query=stripped, blocked_markers=[],
    )


# ---------------------------------------------------------------------------
# Strict intent classifier — used by the AI meal coach form
# ---------------------------------------------------------------------------


@dataclass
class IntentDecision:
    """Stricter than GuardrailDecision — requires a positive meal-scope signal.

    `redirect` is the friendlier failure mode: the query is syntactically fine
    and safe, but we can't confidently say it's meal/nutrition/recipe. Caller
    should respond with a scope reminder + examples, not an error.
    """

    status: IntentStatus
    allowed: bool
    reason: str
    in_scope_markers: list[str]
    blocked_markers: list[str]
    redirect_suggestion: str | None = None


REDIRECT_SUGGESTION = (
    "This MealMap coach answers questions about meals, nutrition, recipes, "
    "and allergen safety only. Try asking: 'family-friendly low-sodium dinner idea?', "
    "'what is the RDA for vitamin D?', or 'how does vitamin C affect iron absorption?'."
)


def _in_scope_hits(text: str) -> list[str]:
    low = text.lower()
    return [m for m in _IN_SCOPE_MARKERS if re.search(rf"\b{re.escape(m)}\b", low)]


def classify_intent_strict(query: str) -> IntentDecision:
    """Classify whether `query` is clearly a meal/nutrition/recipe question.

    Decision tree:
        1. Injection markers   → status=`injection`
        2. Off-topic hard      → status=`off_topic`
        3. No in-scope hit     → status=`redirect` (friendly, not an error)
        4. In-scope hit found  → status=`on_topic`

    Short queries (< MIN_INTENT_QUERY_LEN) without a scope marker are redirected
    too, since an ambiguous short query is more likely misrouted than on-topic.
    """
    if query is None:
        return IntentDecision(
            status="redirect", allowed=False, reason="null_query",
            in_scope_markers=[], blocked_markers=[], redirect_suggestion=REDIRECT_SUGGESTION,
        )

    stripped = _strip_control_chars(str(query)).strip()
    if not stripped:
        return IntentDecision(
            status="redirect", allowed=False, reason="empty_query",
            in_scope_markers=[], blocked_markers=[], redirect_suggestion=REDIRECT_SUGGESTION,
        )

    inj = _find_injection_markers(stripped)
    if inj:
        return IntentDecision(
            status="injection", allowed=False, reason="prompt_injection",
            in_scope_markers=[], blocked_markers=inj, redirect_suggestion=None,
        )

    off = _find_off_topic_markers(stripped)
    scope = _in_scope_hits(stripped)

    if off and not scope:
        return IntentDecision(
            status="off_topic", allowed=False, reason="off_topic_marker",
            in_scope_markers=[], blocked_markers=off, redirect_suggestion=REDIRECT_SUGGESTION,
        )

    if not scope:
        return IntentDecision(
            status="redirect", allowed=False, reason="no_in_scope_marker",
            in_scope_markers=[], blocked_markers=[], redirect_suggestion=REDIRECT_SUGGESTION,
        )

    return IntentDecision(
        status="on_topic", allowed=True, reason="ok",
        in_scope_markers=scope, blocked_markers=[], redirect_suggestion=None,
    )
