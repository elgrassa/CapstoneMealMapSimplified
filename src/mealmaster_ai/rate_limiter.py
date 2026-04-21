"""Cost + session rate limiter for the capstone demo.

Two-level cap protects the user's OPENAI_API_KEY when the app is hosted
publicly (Streamlit Cloud + GitHub Actions secret):

1. **Per-session cap** — N live-LLM calls per Streamlit session within a
   rolling window. Default: 20 calls / 3600 s.
2. **Global daily $ budget** — aggregate `cost_usd` across all sessions in
   the current UTC day. Default: $0.50 / day.

When either cap is hit, the caller should fall through to the deterministic
fallback path (no LLM call). This is the same behaviour as having no API key.

Storage: a tiny SQLite DB (`monitoring/rate_limit.db` by default). Separate
from `monitoring/feedback.db` so the user can nuke either independently.

Configuration via env vars (with sensible defaults):
- `CAPSTONE_DAILY_BUDGET_USD` — default 0.50
- `CAPSTONE_SESSION_LLM_CAP` — default 20
- `CAPSTONE_SESSION_LLM_WINDOW_S` — default 3600
- `RATE_LIMIT_DB_PATH` — default monitoring/rate_limit.db
"""
from __future__ import annotations

import datetime as _dt
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "monitoring" / "rate_limit.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    ts_unix     INTEGER NOT NULL,
    ts_utc_day  TEXT NOT NULL,
    cost_usd    REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_calls_session ON calls(session_id);
CREATE INDEX IF NOT EXISTS idx_calls_day     ON calls(ts_utc_day);
CREATE INDEX IF NOT EXISTS idx_calls_ts      ON calls(ts_unix);
"""


@dataclass
class RateLimitDecision:
    """Result of checking whether a new LLM call is allowed.

    When `allowed=False`, caller should skip the live LLM and use the
    deterministic fallback. `reason` is one of `ok`, `session_cap`,
    `daily_budget`, or `disabled`.
    """

    allowed: bool
    reason: str
    session_calls_used: int
    session_cap: int
    daily_spend_usd: float
    daily_budget_usd: float

    @property
    def session_calls_remaining(self) -> int:
        return max(0, self.session_cap - self.session_calls_used)

    @property
    def daily_spend_remaining_usd(self) -> float:
        return max(0.0, self.daily_budget_usd - self.daily_spend_usd)


class RateLimiter:
    def __init__(
        self,
        *,
        db_path: Path | None = None,
        session_cap: int = 20,
        session_window_s: int = 3600,
        daily_budget_usd: float = 0.50,
    ) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.session_cap = int(session_cap)
        self.session_window_s = int(session_window_s)
        self.daily_budget_usd = float(daily_budget_usd)
        self._ensure_schema()

    @classmethod
    def from_env(cls) -> "RateLimiter":
        return cls(
            db_path=Path(os.getenv("RATE_LIMIT_DB_PATH", str(DEFAULT_DB_PATH))),
            session_cap=int(os.getenv("CAPSTONE_SESSION_LLM_CAP", "20")),
            session_window_s=int(os.getenv("CAPSTONE_SESSION_LLM_WINDOW_S", "3600")),
            daily_budget_usd=float(os.getenv("CAPSTONE_DAILY_BUDGET_USD", "0.50")),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def check_budget(self, session_id: str) -> RateLimitDecision:
        """Return whether the caller is allowed to make a new LLM call.

        Does not mutate state. Call `record_call` after a successful LLM call.
        """
        if not session_id:
            session_id = "_anon"
        now = int(time.time())
        day = _utc_day_key(now)

        session_used = self._count_session_calls(session_id, since_unix=now - self.session_window_s)
        daily_spend = self._sum_day_cost(day)

        if session_used >= self.session_cap:
            return RateLimitDecision(
                allowed=False, reason="session_cap",
                session_calls_used=session_used, session_cap=self.session_cap,
                daily_spend_usd=daily_spend, daily_budget_usd=self.daily_budget_usd,
            )
        if daily_spend >= self.daily_budget_usd:
            return RateLimitDecision(
                allowed=False, reason="daily_budget",
                session_calls_used=session_used, session_cap=self.session_cap,
                daily_spend_usd=daily_spend, daily_budget_usd=self.daily_budget_usd,
            )
        return RateLimitDecision(
            allowed=True, reason="ok",
            session_calls_used=session_used, session_cap=self.session_cap,
            daily_spend_usd=daily_spend, daily_budget_usd=self.daily_budget_usd,
        )

    def record_call(self, session_id: str, cost_usd: float) -> None:
        """Record a successful LLM call. Caller should call this AFTER the LLM returns.

        Never raises — rate-limit DB failures must not break the agent.
        """
        if not session_id:
            session_id = "_anon"
        cost_usd = max(0.0, float(cost_usd))
        now = int(time.time())
        day = _utc_day_key(now)
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO calls (session_id, ts_unix, ts_utc_day, cost_usd) VALUES (?, ?, ?, ?)",
                    (session_id, now, day, cost_usd),
                )
        except Exception:
            # Fire-and-forget — never block agent on DB failure
            pass

    def reset(self) -> None:
        """Testing helper: wipe all recorded calls."""
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM calls")
        except Exception:
            pass

    def snapshot(self, session_id: str) -> dict[str, float | int]:
        """Return a summary dict for UI rendering."""
        d = self.check_budget(session_id)
        return {
            "session_calls_used": d.session_calls_used,
            "session_cap": d.session_cap,
            "session_calls_remaining": d.session_calls_remaining,
            "daily_spend_usd": round(d.daily_spend_usd, 4),
            "daily_budget_usd": d.daily_budget_usd,
            "daily_spend_remaining_usd": round(d.daily_spend_remaining_usd, 4),
            "allowed": d.allowed,
            "reason": d.reason,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _ensure_schema(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as conn:
                conn.executescript(_SCHEMA)
        except Exception:
            # Still allow the limiter to exist if the DB file can't be created —
            # it just won't persist. Every call then appears as first-ever.
            pass

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        return conn

    def _count_session_calls(self, session_id: str, *, since_unix: int) -> int:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM calls WHERE session_id = ? AND ts_unix >= ?",
                    (session_id, since_unix),
                ).fetchone()
                return int(row[0]) if row else 0
        except Exception:
            return 0

    def _sum_day_cost(self, day_key: str) -> float:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COALESCE(SUM(cost_usd), 0) FROM calls WHERE ts_utc_day = ?",
                    (day_key,),
                ).fetchone()
                return float(row[0]) if row else 0.0
        except Exception:
            return 0.0


def _utc_day_key(ts_unix: int) -> str:
    return _dt.datetime.fromtimestamp(ts_unix, _dt.UTC).strftime("%Y-%m-%d")


_default_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    """Module-level singleton. Safe to call concurrently from Streamlit sessions."""
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = RateLimiter.from_env()
    return _default_limiter
