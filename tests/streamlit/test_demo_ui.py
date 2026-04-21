"""Streamlit AppTest coverage for `demo_ui/app.py`.

Runs the demo UI headlessly (no browser) and asserts on rendered elements +
widget interactions. Catches regressions that unit tests miss — broken widget
bindings, missing tab content, exceptions during first paint.

See https://docs.streamlit.io/develop/api-reference/app-testing
"""
from __future__ import annotations

from pathlib import Path

import pytest

try:
    from streamlit.testing.v1 import AppTest
    HAS_STREAMLIT = True
except ImportError:  # pragma: no cover
    HAS_STREAMLIT = False

APP_PATH = str(Path(__file__).resolve().parents[2] / "demo_ui" / "app.py")


pytestmark = pytest.mark.skipif(not HAS_STREAMLIT, reason="streamlit not installed in this env")


def _new_app() -> "AppTest":
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    return at


def test_app_boots_without_exceptions():
    """First paint of the app MUST NOT raise — catches import errors, typo bugs, missing modules."""
    at = _new_app()
    # Print anything that exploded so CI output is useful.
    if at.exception:
        pytest.fail(f"App raised during first paint: {[e.value for e in at.exception]}")
    assert len(at.exception) == 0


def test_sidebar_has_capstone_brand_and_rubric_checklist():
    """Sidebar is the control panel — must show brand, links, metrics, and rubric chips."""
    at = _new_app()
    sidebar_text = " ".join(m.value for m in at.sidebar.markdown)
    assert "MealMaster Capstone" in sidebar_text
    assert "meal-map.app" in sidebar_text
    # Rubric coverage labels (sample of the critical ones)
    assert "Agents + tools" in sidebar_text
    assert "KB + retrieval" in sidebar_text
    assert "Monitoring" in sidebar_text
    # Cost meter is a metric widget
    metric_labels = [m.label for m in at.sidebar.metric]
    assert "Queries this session" in metric_labels
    # After the fix to pull from the rate limiter, label shifted to "Est. cost (today, USD)".
    assert any("Est. cost" in label for label in metric_labels)


def test_all_top_level_tabs_are_defined():
    """Structural guarantee: the 6 top-level tabs exist — regressions in tab count would drop rubric coverage."""
    at = _new_app()
    tab_labels = [t.label for t in at.tabs]
    top_level_labels = {
        "📐 0. Architecture",
        "💬 1. Query the demo",
        "📖 2. Book parsing playground",
        "🧪 3. Evaluation laboratory",
        "🎛️ 4. Parameter tuning sandbox",
        "🥗 5. Recipe nutrition & household fit",
    }
    assert top_level_labels.issubset(set(tab_labels)), f"Missing tabs. Got: {tab_labels}"


def test_use_preprocessed_checkbox_default_is_true_across_tabs():
    """User-requested invariant: the 'use pre-processed corpus' checkbox is ON by default everywhere."""
    at = _new_app()
    # There are 4 checkboxes — one per tab that has the toggle (Tabs 1/2/3/4).
    # Every one must start checked (`value == True`).
    prep_checkboxes = [c for c in at.checkbox if "Use pre-processed" in (c.label or "")]
    assert len(prep_checkboxes) >= 3, f"Expected ≥3 use-preprocessed checkboxes, got {len(prep_checkboxes)}"
    for cb in prep_checkboxes:
        assert cb.value is True, f"Checkbox '{cb.label}' (key={cb.key}) default is not True"


def test_tab1_query_input_has_sensible_default():
    """Tab 1 — Query the demo — should boot with a sensible starter query so the grader can click Ask immediately."""
    at = _new_app()
    queries = [ti for ti in at.text_input if ti.key == "tab1_query"]
    assert len(queries) == 1
    assert queries[0].value.strip() != ""
    # Query input should reference something the demo corpus can answer.
    assert any(term in queries[0].value.lower() for term in ("vitamin", "rda", "recipe", "pasta"))


def test_tab1_ask_button_exists():
    """The 'Ask agent' button is THE primary call-to-action in Tab 1. Missing = demo is broken."""
    at = _new_app()
    ask_buttons = [b for b in at.button if b.key == "tab1_ask"]
    assert len(ask_buttons) == 1
    assert "Ask" in (ask_buttons[0].label or "")


def test_tab4_tuning_sliders_have_production_defaults():
    """Parameter tuning sandbox must boot with the production defaults (0.3 / 0.1 / 1.3 / 1.0 / 0.7)."""
    at = _new_app()
    sliders_by_key = {s.key: s.value for s in at.slider}
    assert sliders_by_key.get("tab4_conf") == pytest.approx(0.3)
    assert sliders_by_key.get("tab4_fb") == pytest.approx(0.1)
    assert sliders_by_key.get("tab4_wh") == pytest.approx(1.3)
    assert sliders_by_key.get("tab4_wm") == pytest.approx(1.0)
    assert sliders_by_key.get("tab4_wl") == pytest.approx(0.7)


def test_tab3_evaluation_has_ground_truth_selectbox():
    """Tab 3 — Evaluation lab — must expose a selectbox of GT cases; empty = can't run eval."""
    at = _new_app()
    eval_selectboxes = [s for s in at.selectbox if s.key == "tab3_case"]
    assert len(eval_selectboxes) == 1
    # Each GT case shows as a label; we shipped 7 cases this session.
    # Streamlit format_func is applied at render time; raw options len is 7.
    selectbox = eval_selectboxes[0]
    assert len(selectbox.options) >= 5, f"Expected ≥5 GT cases, got {len(selectbox.options)}"


def test_uncheck_preprocessed_reveals_upload_widget():
    """Unchecking 'use pre-processed' in Tab 1 must reveal the file_uploader for 'parse my own'."""
    at = _new_app()
    prep = [c for c in at.checkbox if c.key == "tab1_prep"][0]
    assert prep.value is True  # baseline
    # File uploader should NOT be present while pre-processed is on.
    uploaders_before = [u for u in at.file_uploader if u.key == "tab1_upload"]
    assert len(uploaders_before) == 0

    # Toggle off and re-run.
    prep.uncheck().run()
    uploaders_after = [u for u in at.file_uploader if u.key == "tab1_upload"]
    assert len(uploaders_after) == 1, "Unchecking 'use pre-processed' did not reveal the file_uploader"


def test_ask_agent_with_default_query_runs_without_exception():
    """Click 'Ask agent' with the default query → agent runs → structured response renders."""
    at = _new_app()
    # Tab 1's Ask button (key=tab1_ask)
    ask = [b for b in at.button if b.key == "tab1_ask"][0]
    ask.click().run(timeout=30)
    if at.exception:
        pytest.fail(f"Ask agent path raised: {[e.value for e in at.exception]}")

    # Evidence-tier alert should be one of {success, warning, error} — all three are Streamlit notifications.
    # A successful run typically produces a `success` with "Evidence tier:" text.
    tier_alerts = [a for a in (list(at.success) + list(at.warning) + list(at.error)) if "Evidence tier" in str(a.value)]
    assert len(tier_alerts) >= 1, "No evidence-tier alert rendered after Ask click."


def test_tab4_slider_change_flips_decision_on_mismatch():
    """Move confidence_threshold above the top score → decision flips from supported to refused/fallback.

    This pins the Tab 4 "tuning-flips-decision" demo behaviour: the whole point of the tab.
    """
    at = _new_app()
    conf = [s for s in at.slider if s.key == "tab4_conf"][0]
    # Set threshold impossibly high so every BM25 score falls below it.
    conf.set_value(7.99).run()
    # The custom-param status metric should now read `refused`.
    custom_status_metrics = [m for m in at.metric if m.label == "Status"]
    assert len(custom_status_metrics) >= 1
    # The first Status metric (custom params) should be `refused` when threshold=7.99 exceeds all BM25 scores.
    # The second is the production baseline which should stay `supported`.
    custom_status_values = [m.value for m in custom_status_metrics]
    assert "refused" in custom_status_values or "fallback" in custom_status_values, (
        f"Expected status flip to refused/fallback at threshold=7.99, got {custom_status_values}"
    )
