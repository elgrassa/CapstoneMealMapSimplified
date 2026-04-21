"""Medical-boundary validator — SAMPLE subset.

The production MealMaster validator holds **44 forbidden phrases** and **9 referral
triggers** across 3 severity levels (CRITICAL / WARNING / INFO). The sample below
is reduced to a representative 5 phrases + 2 triggers so the pattern is
demonstrable while the full list stays behind the production product.

See `docs/medical-boundary-pattern.md` for the architectural pattern; for the
full catalog, see https://meal-map.app.

Two checks:
1. `contains_forbidden_phrase(text)` — fast substring check (case-insensitive).
2. `detect_referral_triggers(symptoms)` — structured list-of-dicts matcher.

Both return the first match; callers in the production path collect all matches.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Severity = Literal["CRITICAL", "WARNING", "INFO"]


# Five representative forbidden phrases covering diagnostic, prescriptive, curative,
# and overconfident claim patterns. Production has 44.
FORBIDDEN_PHRASES_SAMPLE: list[str] = [
    "you have iron deficiency",
    "i prescribe",
    "will cure",
    "guaranteed to reverse",
    "will prevent",
]


@dataclass(frozen=True)
class ReferralTrigger:
    id: str
    severity: Severity
    description: str
    symptom_keywords: frozenset[str]
    action: str


# Two representative triggers (one CRITICAL, one WARNING). Production has 9.
REFERRAL_TRIGGERS_SAMPLE: list[ReferralTrigger] = [
    ReferralTrigger(
        id="spoon_shaped_nails",
        severity="CRITICAL",
        description="Spoon-shaped nails (koilonychia) suggest possible iron-deficiency anemia requiring clinical work-up.",
        symptom_keywords=frozenset({"spoon", "koilonychia", "concave nails"}),
        action="Block nutrition-only response; advise immediate clinician referral.",
    ),
    ReferralTrigger(
        id="chronic_fatigue_multi_factor",
        severity="WARNING",
        description="Chronic fatigue with coexisting celiac + vegetarian diet — elevated risk of deficiency, needs clinician + RD consultation.",
        symptom_keywords=frozenset({"fatigue", "celiac", "vegetarian"}),
        action="Pair nutrition guidance with explicit clinician + dietitian referral.",
    ),
]


def contains_forbidden_phrase(text: str) -> str | None:
    """Return the first forbidden phrase found in `text`, or None."""
    t = text.lower()
    for phrase in FORBIDDEN_PHRASES_SAMPLE:
        if phrase in t:
            return phrase
    return None


def detect_referral_triggers(symptoms_text: str) -> list[ReferralTrigger]:
    """Return triggers whose keyword set overlaps the lowered symptom text."""
    t = symptoms_text.lower()
    tokens = set(re.findall(r"[a-z]+", t))
    hits: list[ReferralTrigger] = []
    for trigger in REFERRAL_TRIGGERS_SAMPLE:
        if trigger.symptom_keywords & tokens:
            hits.append(trigger)
    return hits


DEFAULT_MEDICAL_DISCLAIMER = (
    "This response is educational and not medical advice. "
    "Consult a qualified healthcare professional or registered dietitian for personal guidance."
)
