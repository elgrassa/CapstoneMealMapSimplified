"""Canonical ingredient reference — 10-item SAMPLE from USDA FoodData Central.

The production MealMaster catalog holds 82 ingredients × 19 nutrition fields × EU-14
allergen tags, tuned per-age-band and per-condition. The sample below is intentionally
limited to a representative 10 common ingredients, sourced from USDA public data
(public domain, 17 USC § 105), and reduced to the 5 most commonly cited macros.

For the full production catalog, see https://meal-map.app.

Units:
- energy_kcal           — kcal per 100 g
- protein_g, carbs_g, fat_g, fiber_g — grams per 100 g

EU-14 allergen tags used (subset applied to this sample):
- none, gluten, dairy, eggs, fish, peanuts, soy, tree_nuts
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Ingredient:
    name: str
    energy_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    allergens: tuple[str, ...]
    usda_fdc_id: str  # USDA FoodData Central ID for verification


CANONICAL_INGREDIENTS_SAMPLE: list[Ingredient] = [
    Ingredient("oats_rolled_dry", 379, 13.1, 67.7, 6.5, 10.1, ("gluten",), "169705"),
    Ingredient("egg_whole_raw", 143, 12.6, 0.7, 9.5, 0.0, ("eggs",), "171287"),
    Ingredient("broccoli_raw", 34, 2.8, 6.6, 0.4, 2.6, ("none",), "170379"),
    Ingredient("salmon_atlantic_raw", 142, 19.8, 0.0, 6.3, 0.0, ("fish",), "175167"),
    Ingredient("lentils_raw", 352, 24.6, 63.4, 1.1, 10.7, ("none",), "172420"),
    Ingredient("spinach_raw", 23, 2.9, 3.6, 0.4, 2.2, ("none",), "168462"),
    Ingredient("almonds_raw", 579, 21.2, 21.6, 49.9, 12.5, ("tree_nuts",), "170567"),
    Ingredient("rice_brown_long_grain_raw", 370, 7.9, 77.2, 2.9, 3.6, ("none",), "169703"),
    Ingredient("yogurt_plain_lowfat", 63, 5.3, 7.0, 1.6, 0.0, ("dairy",), "170886"),
    Ingredient("sweet_potato_raw", 86, 1.6, 20.1, 0.1, 3.0, ("none",), "168482"),
]


def find_by_name(name: str) -> Ingredient | None:
    needle = name.strip().lower().replace(" ", "_")
    for ing in CANONICAL_INGREDIENTS_SAMPLE:
        if ing.name == needle:
            return ing
    return None


def macro_summary(name: str) -> dict | None:
    ing = find_by_name(name)
    if ing is None:
        return None
    return {
        "name": ing.name,
        "per_100g": {
            "energy_kcal": ing.energy_kcal,
            "protein_g": ing.protein_g,
            "carbs_g": ing.carbs_g,
            "fat_g": ing.fat_g,
            "fiber_g": ing.fiber_g,
        },
        "allergens": list(ing.allergens),
        "source": f"USDA FoodData Central FDC ID: {ing.usda_fdc_id}",
    }
