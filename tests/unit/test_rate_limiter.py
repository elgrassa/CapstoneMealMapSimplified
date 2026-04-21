"""Rate limiter — session cap + daily $ budget."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mealmaster_ai.rate_limiter import RateLimiter


@pytest.fixture
def tmp_limiter(tmp_path: Path) -> RateLimiter:
    db = tmp_path / "rate_limit.db"
    return RateLimiter(
        db_path=db,
        session_cap=5,
        session_window_s=3600,
        daily_budget_usd=0.01,
    )


def test_initial_state_allows(tmp_limiter: RateLimiter):
    d = tmp_limiter.check_budget("sess-1")
    assert d.allowed is True
    assert d.reason == "ok"
    assert d.session_calls_used == 0
    assert d.daily_spend_usd == 0.0


def test_session_cap_blocks_after_N_calls(tmp_limiter: RateLimiter):
    for _ in range(5):
        tmp_limiter.record_call("sess-1", 0.0)  # no cost, only session-cap trigger
    d = tmp_limiter.check_budget("sess-1")
    assert d.allowed is False
    assert d.reason == "session_cap"
    assert d.session_calls_used == 5
    assert d.session_calls_remaining == 0


def test_daily_budget_blocks_across_sessions(tmp_limiter: RateLimiter):
    # Spend beyond the daily budget across two different sessions
    tmp_limiter.record_call("sess-A", 0.008)
    tmp_limiter.record_call("sess-B", 0.003)
    d = tmp_limiter.check_budget("sess-C")
    assert d.allowed is False
    assert d.reason == "daily_budget"
    assert d.daily_spend_usd >= 0.01


def test_different_sessions_have_independent_caps(tmp_limiter: RateLimiter):
    # Fill session A to cap
    for _ in range(5):
        tmp_limiter.record_call("sess-A", 0.0)
    # Session B should still be allowed
    d = tmp_limiter.check_budget("sess-B")
    assert d.allowed is True
    assert d.session_calls_used == 0


def test_record_call_is_fire_and_forget(tmp_path: Path):
    """Even if the DB is unwritable, record_call must not raise."""
    bad_path = tmp_path / "no" / "such" / "folder" / "db.sqlite"
    rl = RateLimiter(db_path=bad_path, session_cap=2, daily_budget_usd=0.01)
    # Parent dir exists via _ensure_schema best-effort, but forcibly remove it
    try:
        rl.record_call("x", 0.001)  # should not raise
    except Exception as e:
        pytest.fail(f"record_call raised: {e}")


def test_snapshot_returns_ui_shape(tmp_limiter: RateLimiter):
    tmp_limiter.record_call("sess-1", 0.002)
    s = tmp_limiter.snapshot("sess-1")
    for key in (
        "session_calls_used", "session_cap", "session_calls_remaining",
        "daily_spend_usd", "daily_budget_usd", "daily_spend_remaining_usd",
        "allowed", "reason",
    ):
        assert key in s, f"snapshot missing key: {key}"


def test_reset_clears_counters(tmp_limiter: RateLimiter):
    tmp_limiter.record_call("sess-1", 0.005)
    assert tmp_limiter.check_budget("sess-1").session_calls_used == 1
    tmp_limiter.reset()
    assert tmp_limiter.check_budget("sess-1").session_calls_used == 0


def test_empty_session_id_falls_back_to_anon(tmp_limiter: RateLimiter):
    tmp_limiter.record_call("", 0.001)
    d = tmp_limiter.check_budget("")
    # Should have recorded under _anon, not raise
    assert d.session_calls_used == 1
