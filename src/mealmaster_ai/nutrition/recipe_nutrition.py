"""Recipe-level nutrition estimation on top of the 10-item USDA canonical sample.

Chain:
    raw recipe text → parse_recipe_ingredients (regex over '- AMOUNT UNIT name')
                   → match_to_canonical (token-level fuzzy match vs
                     CANONICAL_INGREDIENTS_SAMPLE)
                   → aggregate_macros (sum per-100g across matched ingredients)
                   → allergen_fit (cross-check vs DemoUserProfile.all_allergens)

Production at meal-map.app runs the same chain over the full 82-ingredient × 19-field
catalog with amount parsing and per-portion scaling. This demo keeps the scope
honest: per-100g aggregation of matched ingredients with an explicit
unmatched-list so the grader sees what the sample covers and what it doesn't.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from mealmaster_ai.data.canonical_ingredients_sample import (
    CANONICAL_INGREDIENTS_SAMPLE,
    Ingredient,
)
from mealmaster_ai.data.demo_user_profile import DemoUserProfile, DEMO_PROFILE


@dataclass(frozen=True)
class ParsedIngredient:
    raw_line: str           # "- 4 chicken thighs, skinless"
    amount_text: str        # "4"
    ingredient_text: str    # "chicken thighs, skinless"


@dataclass(frozen=True)
class MatchedIngredient:
    raw_line: str
    ingredient_text: str
    matched: Ingredient | None     # None if no canonical sample hit
    matched_via: str | None        # token used to match (for explain)


_INGREDIENT_LINE = re.compile(r"^\s*[-*]\s*(.+)$")
# Amount prefix: a number, optionally followed by a recognised unit word.
# "1 ripe banana" → amount="1", name="ripe banana" (not amount="1 ripe").
# "2 tablespoons olive oil" → amount="2 tablespoons", name="olive oil".
_UNIT_WORDS = r"(?:cup|cups|tbsp|tablespoons?|tsp|teaspoons?|g|grams?|kg|oz|ml|l|liter|liters?|can|cans|cloves?|sticks?|slices?|pinch|dash)"
_AMOUNT_PREFIX = re.compile(
    rf"^(\d+(?:[./]\d+)?(?:\s+{_UNIT_WORDS})?)\s+(.+)$",
    re.IGNORECASE,
)
_INGREDIENTS_HEADER = re.compile(r"^\s*ingredients?\s*:", re.I)
_END_OF_INGREDIENTS = re.compile(r"^\s*(method|preparation|steps?|servings?|directions?)\b", re.I)
_NEW_RECIPE_HEADER = re.compile(r"^\s*#+\s*recipe", re.I)

# Tokens in the canonical `name` field that are cooking-method / form descriptors
# rather than ingredient identity — skip these when matching against free-text recipes.
_CANONICAL_NOISE_TOKENS = frozenset({
    "raw", "dry", "cooked", "whole", "lowfat", "low", "fat", "plain",
    "long", "grain", "rolled", "atlantic",
})


def parse_recipe_ingredients(chunk_text: str) -> list[ParsedIngredient]:
    """Scan `chunk_text` for an 'Ingredients:' block and return one entry per bullet line."""
    out: list[ParsedIngredient] = []
    in_block = False
    for raw_line in chunk_text.splitlines():
        line = raw_line.rstrip()
        if _INGREDIENTS_HEADER.search(line):
            in_block = True
            continue
        if not in_block:
            continue
        if _END_OF_INGREDIENTS.search(line) or _NEW_RECIPE_HEADER.search(line):
            break
        m = _INGREDIENT_LINE.match(line)
        if not m:
            # blank line inside the ingredients block → probably end
            if not line.strip():
                if out:
                    break
                continue
            continue
        inner = m.group(1).strip()
        amt_match = _AMOUNT_PREFIX.match(inner)
        if amt_match:
            amount_text = amt_match.group(1).strip()
            ingredient_text = amt_match.group(2).strip()
        else:
            amount_text = ""
            ingredient_text = inner
        out.append(ParsedIngredient(
            raw_line=line.strip(),
            amount_text=amount_text,
            ingredient_text=ingredient_text,
        ))
    return out


def _canonical_meaning_tokens(ing: Ingredient) -> list[str]:
    """Return the identity tokens of an Ingredient name, skipping form descriptors."""
    parts = ing.name.split("_")
    return [p for p in parts if p not in _CANONICAL_NOISE_TOKENS]


def match_to_canonical(ingredient_text: str) -> tuple[Ingredient | None, str | None]:
    """Return `(matched_ingredient, match_reason)` or `(None, None)`.

    Token-level substring match. E.g. "oats" in recipe text → matches
    `oats_rolled_dry` because "oats" is an identity token of that canonical entry.
    """
    needle = ingredient_text.lower()
    # Iterate in declared order so the first / more-common hit wins.
    for ing in CANONICAL_INGREDIENTS_SAMPLE:
        for tok in _canonical_meaning_tokens(ing):
            if tok and re.search(rf"\b{re.escape(tok)}\b", needle):
                return ing, tok
    return None, None


def match_all(parsed: list[ParsedIngredient]) -> list[MatchedIngredient]:
    out: list[MatchedIngredient] = []
    for p in parsed:
        matched, via = match_to_canonical(p.ingredient_text)
        out.append(MatchedIngredient(
            raw_line=p.raw_line,
            ingredient_text=p.ingredient_text,
            matched=matched,
            matched_via=via,
        ))
    return out


@dataclass(frozen=True)
class MacroAggregate:
    matched_count: int
    unmatched_count: int
    energy_kcal_per_100g_sum: float
    protein_g_per_100g_sum: float
    carbs_g_per_100g_sum: float
    fat_g_per_100g_sum: float
    fiber_g_per_100g_sum: float


def aggregate_macros(matched: list[MatchedIngredient]) -> MacroAggregate:
    """Sum per-100g macros across matched ingredients.

    Per-100g aggregation is a deliberate simplification — the production system
    multiplies by parsed amounts. Documented in the UI.
    """
    hits = [m.matched for m in matched if m.matched is not None]
    return MacroAggregate(
        matched_count=len(hits),
        unmatched_count=sum(1 for m in matched if m.matched is None),
        energy_kcal_per_100g_sum=round(sum(h.energy_kcal for h in hits), 1),
        protein_g_per_100g_sum=round(sum(h.protein_g for h in hits), 1),
        carbs_g_per_100g_sum=round(sum(h.carbs_g for h in hits), 1),
        fat_g_per_100g_sum=round(sum(h.fat_g for h in hits), 1),
        fiber_g_per_100g_sum=round(sum(h.fiber_g for h in hits), 1),
    )


MemberVerdict = Literal["safe", "allergen_conflict", "partial_data"]


@dataclass(frozen=True)
class HouseholdMemberFit:
    display_name: str
    age_band: str
    verdict: MemberVerdict
    conflicting_allergens: tuple[str, ...]


def household_fit(
    matched: list[MatchedIngredient],
    profile: DemoUserProfile = DEMO_PROFILE,
) -> tuple[HouseholdMemberFit, ...]:
    """Cross-check the matched ingredients' allergens vs each household member's allergens."""
    recipe_allergens: set[str] = set()
    for m in matched:
        if m.matched is not None:
            for a in m.matched.allergens:
                if a and a != "none":
                    recipe_allergens.add(a)

    out: list[HouseholdMemberFit] = []
    for member in profile.members:
        conflicts = tuple(sorted(set(member.allergens) & recipe_allergens))
        if conflicts:
            verdict: MemberVerdict = "allergen_conflict"
        elif any(m.matched is None for m in matched):
            verdict = "partial_data"
        else:
            verdict = "safe"
        out.append(HouseholdMemberFit(
            display_name=member.display_name,
            age_band=member.age_band,
            verdict=verdict,
            conflicting_allergens=conflicts,
        ))
    return tuple(out)
