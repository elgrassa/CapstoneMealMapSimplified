"""Recipe-level nutrition aggregation + household allergen fit."""
from __future__ import annotations

from mealmaster_ai.data.demo_user_profile import DEMO_PROFILE, DemoUserProfile, FamilyMember
from mealmaster_ai.nutrition.recipe_nutrition import (
    aggregate_macros,
    household_fit,
    match_all,
    match_to_canonical,
    parse_recipe_ingredients,
)


WIC_PANCAKES = """\
## Recipe 1 — Banana Oat Pancakes

Ingredients:
- 1 ripe banana, mashed
- 1 cup rolled oats, blended into flour
- 1 large egg
- 3/4 cup low-fat milk
- 1 teaspoon baking powder
- 1/2 teaspoon cinnamon
- Cooking oil for the pan

Servings: 4 small pancakes.

Method:
1. Mix all ingredients in a bowl until smooth.
"""


def test_parse_recipe_ingredients_picks_all_bullets():
    parsed = parse_recipe_ingredients(WIC_PANCAKES)
    assert len(parsed) == 7
    # "1 ripe banana" — plain number, no unit word.
    assert parsed[0].amount_text == "1"
    assert parsed[0].ingredient_text == "ripe banana, mashed"
    # "3/4 cup low-fat milk" — number + unit ("cup") folded into amount.
    assert parsed[3].amount_text.lower() == "3/4 cup"
    assert "milk" in parsed[3].ingredient_text


def test_parse_recipe_stops_at_method():
    parsed = parse_recipe_ingredients(WIC_PANCAKES)
    # 'Method:' line must not appear in output
    assert all("mix" not in p.ingredient_text.lower() for p in parsed)


def test_parse_recipe_handles_empty_text():
    assert parse_recipe_ingredients("") == []


def test_parse_recipe_handles_no_ingredients_block():
    assert parse_recipe_ingredients("just some nutrition text without an ingredient list") == []


def test_match_oats_hits_canonical():
    ing, via = match_to_canonical("1 cup rolled oats, blended into flour")
    assert ing is not None
    assert ing.name == "oats_rolled_dry"
    assert via == "oats"


def test_match_egg_hits_canonical():
    ing, via = match_to_canonical("1 large egg")
    assert ing is not None
    assert ing.name == "egg_whole_raw"
    assert via == "egg"


def test_match_unknown_returns_none():
    ing, via = match_to_canonical("1 teaspoon baking powder")
    assert ing is None
    assert via is None


def test_aggregate_macros_counts_matched_only():
    parsed = parse_recipe_ingredients(WIC_PANCAKES)
    matched = match_all(parsed)
    agg = aggregate_macros(matched)
    # oats + egg should match; banana, milk, baking powder, cinnamon, oil don't
    assert agg.matched_count == 2
    assert agg.unmatched_count == 5
    # oats has ~379 kcal, egg has ~143 — total ~522
    assert 500 < agg.energy_kcal_per_100g_sum < 540


def test_household_fit_flags_egg_allergic_member():
    custom = DemoUserProfile(
        household_label="test",
        members=(
            FamilyMember(display_name="Egg-allergic", age_band="adult", allergens=("eggs",)),
            FamilyMember(display_name="Peanut-allergic", age_band="adult", allergens=("peanuts",)),
        ),
        cuisine_preferences=("mediterranean",),
        weekly_budget_tier="medium",
        cooking_time_pref_minutes=30,
    )
    parsed = parse_recipe_ingredients(WIC_PANCAKES)
    matched = match_all(parsed)
    fit = household_fit(matched, profile=custom)
    # Egg-allergic member should have an eggs conflict (from matched egg ingredient).
    by_name = {f.display_name: f for f in fit}
    assert by_name["Egg-allergic"].verdict == "allergen_conflict"
    assert "eggs" in by_name["Egg-allergic"].conflicting_allergens
    # Peanut-allergic should be partial_data (no peanut conflict, but unmatched items)
    assert by_name["Peanut-allergic"].verdict == "partial_data"
    assert by_name["Peanut-allergic"].conflicting_allergens == ()


def test_household_fit_uses_default_profile_when_none_given():
    parsed = parse_recipe_ingredients(WIC_PANCAKES)
    matched = match_all(parsed)
    fit = household_fit(matched)
    # DEMO_PROFILE has 4 members
    assert len(fit) == 4
    # Adult 2 has dairy allergy; pancakes have oats/egg matches (no dairy match because "milk"
    # isn't in our canonical sample), so Adult 2 should be `partial_data`, not allergen_conflict.
    adult_2 = next(f for f in fit if f.display_name == "Adult 2")
    assert adult_2.verdict == "partial_data"


def test_match_all_preserves_order():
    parsed = parse_recipe_ingredients(WIC_PANCAKES)
    matched = match_all(parsed)
    assert len(matched) == len(parsed)
    for p, m in zip(parsed, matched):
        assert m.raw_line == p.raw_line
        assert m.ingredient_text == p.ingredient_text
