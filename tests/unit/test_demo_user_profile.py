"""Hardcoded demo user profile + query personalization."""
from __future__ import annotations

from mealmaster_ai.data.demo_user_profile import (
    DEMO_PROFILE,
    DemoUserProfile,
    FamilyMember,
    personalize_query,
    profile_as_markdown,
)


def test_demo_profile_has_household_of_four():
    assert DEMO_PROFILE.household_size == 4
    assert DEMO_PROFILE.has_children is True


def test_demo_profile_allergens_cover_dairy_and_peanuts():
    allergens = DEMO_PROFILE.all_allergens
    assert "dairy" in allergens
    assert "peanuts" in allergens


def test_demo_profile_contains_no_real_pii():
    """No real names, emails, birth dates. Only generic labels."""
    for m in DEMO_PROFILE.members:
        assert "@" not in m.display_name
        assert "adult" in m.display_name.lower() or "child" in m.display_name.lower()


def test_personalize_query_appends_context_tag():
    original = "What's a low-sodium family dinner?"
    personalized = personalize_query(original)
    assert personalized.startswith(original)
    assert "[Household context:" in personalized
    assert "4 members" in personalized
    # Allergens named
    assert "dairy" in personalized and "peanuts" in personalized
    # Cuisine named
    assert "mediterranean" in personalized or "italian" in personalized


def test_personalize_query_handles_empty_input():
    assert personalize_query("") == ""
    assert personalize_query("   ") == "   "


def test_personalize_query_is_deterministic():
    q = "What is the RDA for vitamin D?"
    a = personalize_query(q)
    b = personalize_query(q)
    assert a == b


def test_profile_to_dict_has_expected_keys():
    d = DEMO_PROFILE.to_dict()
    expected_keys = {
        "household_label", "household_size", "has_children", "members",
        "cuisine_preferences", "weekly_budget_tier", "cooking_time_pref_minutes",
        "kitchen_equipment", "all_allergens",
    }
    assert expected_keys.issubset(d.keys())


def test_profile_markdown_renders_member_rows():
    md = profile_as_markdown(DEMO_PROFILE)
    assert "| Member |" in md
    assert "Adult 1" in md and "Adult 2" in md
    assert "Child 1" in md and "Child 2" in md


def test_family_member_is_frozen():
    m = FamilyMember(display_name="x", age_band="adult")
    import pytest
    with pytest.raises(Exception):
        m.display_name = "y"  # type: ignore[misc]


def test_custom_profile_respects_personalization():
    """A caller can pass a different profile instance (used by tests / tooling)."""
    custom = DemoUserProfile(
        household_label="Single",
        members=(FamilyMember(display_name="Adult 1", age_band="adult"),),
        cuisine_preferences=("mediterranean",),
        weekly_budget_tier="low",
        cooking_time_pref_minutes=20,
    )
    out = personalize_query("What is protein?", profile=custom)
    assert "1 members" in out
    assert "low weekly budget" in out
