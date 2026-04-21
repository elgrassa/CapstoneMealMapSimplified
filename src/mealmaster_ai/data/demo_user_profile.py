"""Hardcoded demo household profile — used by the capstone AI meal coach.

A fixed, generic family profile is shipped here so that:

1. **Reproducibility** — every grader runs against the same profile, so any
   retrieval or eval differences are attributable to code changes, not to
   user-entered inputs varying between runs.
2. **No PII** — names are placeholders ("Adult 1", "Child 1"); no real email,
   birth dates, or medical conditions.
3. **Visible scope** — README + Streamlit sidebar expose the profile so the
   grader understands exactly what personalization context the agent uses.
4. **Allergen + age-band signal** — profile includes enough diversity
   (toddler + school-age, one lactose-intolerant adult, one peanut-allergic
   child) to exercise the allergen + age-band reasoning paths without leaking
   the production MealMaster family-setup schema.

Production MealMaster (meal-map.app) uses a real, user-edited FamilyMember
entity backed by Base44 with encryption at rest. This demo profile is a
hardcoded sample that mirrors the same shape for pattern demonstration only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AgeBand = Literal["infant_0_12m", "toddler_1_3", "child_4_8", "child_9_12", "adolescent_13_18", "adult", "elderly_65_plus"]
BudgetTier = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class FamilyMember:
    display_name: str
    age_band: AgeBand
    allergens: tuple[str, ...] = ()           # EU-14 keys (sample)
    conditions: tuple[str, ...] = ()          # medical conditions (none in demo)
    dietary_tags: tuple[str, ...] = ()        # e.g. "vegetarian"


@dataclass(frozen=True)
class DemoUserProfile:
    household_label: str
    members: tuple[FamilyMember, ...]
    cuisine_preferences: tuple[str, ...]
    weekly_budget_tier: BudgetTier
    cooking_time_pref_minutes: int
    kitchen_equipment: tuple[str, ...] = field(default_factory=tuple)

    @property
    def household_size(self) -> int:
        return len(self.members)

    @property
    def has_children(self) -> bool:
        child_bands = {"infant_0_12m", "toddler_1_3", "child_4_8", "child_9_12", "adolescent_13_18"}
        return any(m.age_band in child_bands for m in self.members)

    @property
    def all_allergens(self) -> set[str]:
        out: set[str] = set()
        for m in self.members:
            out.update(m.allergens)
        return out

    def to_dict(self) -> dict:
        return {
            "household_label": self.household_label,
            "household_size": self.household_size,
            "has_children": self.has_children,
            "members": [
                {
                    "display_name": m.display_name,
                    "age_band": m.age_band,
                    "allergens": list(m.allergens),
                    "conditions": list(m.conditions),
                    "dietary_tags": list(m.dietary_tags),
                }
                for m in self.members
            ],
            "cuisine_preferences": list(self.cuisine_preferences),
            "weekly_budget_tier": self.weekly_budget_tier,
            "cooking_time_pref_minutes": self.cooking_time_pref_minutes,
            "kitchen_equipment": list(self.kitchen_equipment),
            "all_allergens": sorted(self.all_allergens),
        }


# A hardcoded demo household. Keep it generic + diverse enough to exercise
# the personalization code path without any real-person fingerprint.
DEMO_PROFILE = DemoUserProfile(
    household_label="Demo household (2 adults + 2 children)",
    members=(
        FamilyMember(display_name="Adult 1", age_band="adult", allergens=(), conditions=(), dietary_tags=()),
        FamilyMember(display_name="Adult 2", age_band="adult", allergens=("dairy",), conditions=(), dietary_tags=("lactose_intolerant",)),
        FamilyMember(display_name="Child 1 (age 7)", age_band="child_4_8", allergens=("peanuts",), conditions=(), dietary_tags=()),
        FamilyMember(display_name="Child 2 (age 3)", age_band="toddler_1_3", allergens=(), conditions=(), dietary_tags=()),
    ),
    cuisine_preferences=("mediterranean", "italian"),
    weekly_budget_tier="medium",
    cooking_time_pref_minutes=30,
    kitchen_equipment=("oven", "stovetop", "blender"),
)


def personalize_query(query: str, profile: DemoUserProfile = DEMO_PROFILE) -> str:
    """Append a compact household context tag to `query` so the retrieval /
    agent can reason family-aware.

    Keeps the original query first so BM25 tokenization still hits the user's
    vocabulary; the context tag is appended in a deterministic short form.
    """
    if not query or not query.strip():
        return query
    members_summary = (
        f"{profile.household_size} members "
        f"({', '.join(m.age_band for m in profile.members)})"
    )
    allergens = sorted(profile.all_allergens)
    allergen_tag = f"household allergens: {', '.join(allergens)}" if allergens else "no household allergens"
    cuisine_tag = f"prefers {', '.join(profile.cuisine_preferences)}"
    budget_tag = f"{profile.weekly_budget_tier} weekly budget"
    time_tag = f"{profile.cooking_time_pref_minutes}-minute cook time"
    context = f" [Household context: {members_summary}; {allergen_tag}; {cuisine_tag}; {budget_tag}; {time_tag}]"
    return query.strip() + context


def profile_as_markdown(profile: DemoUserProfile = DEMO_PROFILE) -> str:
    """Compact markdown rendering of the profile — used by README + the Streamlit sidebar."""
    lines = [
        f"**{profile.household_label}**",
        "",
        "| Member | Age band | Allergens | Notes |",
        "|---|---|---|---|",
    ]
    for m in profile.members:
        allergens = ", ".join(m.allergens) if m.allergens else "—"
        notes = ", ".join(m.dietary_tags) if m.dietary_tags else "—"
        lines.append(f"| {m.display_name} | {m.age_band} | {allergens} | {notes} |")
    lines.append("")
    lines.append(f"- **Cuisine preferences:** {', '.join(profile.cuisine_preferences)}")
    lines.append(f"- **Weekly budget tier:** {profile.weekly_budget_tier}")
    lines.append(f"- **Cooking time preference:** {profile.cooking_time_pref_minutes} min")
    lines.append(f"- **Kitchen equipment:** {', '.join(profile.kitchen_equipment)}")
    return "\n".join(lines)
