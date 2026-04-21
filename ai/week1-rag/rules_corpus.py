"""Rules corpus — SAMPLE (3 rules).

The production MealMaster system maintains a curated library of dietary rules
used to validate meal plans against family-member constraints (allergens,
age bands, medical conditions, cuisine preferences). The SAMPLE below
illustrates the schema with 3 representative rules.

See https://meal-map.app for the full curated library.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RuleCategory = Literal["allergen_safety", "age_band", "medical_condition", "macro_bound"]
RuleSeverity = Literal["hard_block", "warn", "inform"]


@dataclass(frozen=True)
class DietaryRule:
    id: str
    category: RuleCategory
    severity: RuleSeverity
    description: str
    applies_to_tag: str
    rationale: str


RULES_CORPUS_SAMPLE: list[DietaryRule] = [
    DietaryRule(
        id="gluten_block_celiac",
        category="allergen_safety",
        severity="hard_block",
        description="Exclude any recipe containing gluten when a family member has confirmed celiac disease.",
        applies_to_tag="celiac",
        rationale="EU-14 allergen regulation + clinical necessity — a single cross-contamination event can trigger intestinal damage.",
    ),
    DietaryRule(
        id="low_sodium_toddler",
        category="age_band",
        severity="warn",
        description="Limit sodium to <1.5 g/day for children aged 1-3.",
        applies_to_tag="toddler_1_3",
        rationale="WHO + EFSA recommendations — early life sodium affects long-term BP regulation.",
    ),
    DietaryRule(
        id="iron_pair_with_vit_c",
        category="macro_bound",
        severity="inform",
        description="When an iron-rich meal is planned, include a vitamin C source in the same meal to enhance non-heme iron absorption.",
        applies_to_tag="vegetarian_or_iron_deficient",
        rationale="Co-factor interaction documented in nutrition textbooks; improves absorption ~3-4x.",
    ),
]


def rules_by_tag(tag: str) -> list[DietaryRule]:
    return [r for r in RULES_CORPUS_SAMPLE if r.applies_to_tag == tag]
