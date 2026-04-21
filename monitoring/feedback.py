"""Feedback + event persistence — tiny SQLite DB.

Captures:
- Every agent query and its evidence tier / confidence
- Every thumbs-up / thumbs-down
- Chunking demo interactions
- Parameter tuning changes
- Eval runs

Used by:
- `monitoring/dashboard.py` (reads events + thumbs)
- `monitoring/logs_to_gt.py` (reads thumbs-up rows, emits new GT cases)
- `demo_ui/app.py` sidebar (live session counters)
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("FEEDBACK_DB_PATH", str(Path(__file__).resolve().parent / "feedback.db")))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    timestamp     INTEGER NOT NULL,
    payload_json  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_type    ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_ts      ON events(timestamp);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def record_event(session_id: str, event_type: str, payload: dict[str, Any]) -> None:
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO events (session_id, event_type, timestamp, payload_json) VALUES (?, ?, ?, ?)",
                (session_id, event_type, int(time.time()), json.dumps(payload)),
            )
    except Exception:
        pass


def session_summary(session_id: str) -> dict[str, Any]:
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT event_type, payload_json FROM events WHERE session_id = ?",
                (session_id,),
            ).fetchall()
    except Exception:
        return {"calls": 0, "cost_usd": 0.0, "thumbs_up": 0, "thumbs_down": 0}

    calls = 0
    cost = 0.0
    up = 0
    down = 0
    for etype, payload_json in rows:
        try:
            payload = json.loads(payload_json)
        except Exception:
            payload = {}
        if etype == "query":
            calls += 1
            cost += float(payload.get("cost_usd", 0.0) or 0.0)
        elif etype == "thumbs":
            if payload.get("direction") == "up":
                up += 1
            elif payload.get("direction") == "down":
                down += 1
    return {"calls": calls, "cost_usd": round(cost, 6), "thumbs_up": up, "thumbs_down": down}


def fetch_events(
    *,
    event_type: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    try:
        with _connect() as conn:
            if event_type:
                rows = conn.execute(
                    "SELECT id, session_id, event_type, timestamp, payload_json FROM events WHERE event_type = ? ORDER BY timestamp DESC LIMIT ?",
                    (event_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, session_id, event_type, timestamp, payload_json FROM events ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for eid, sess, etype, ts, payload_json in rows:
        try:
            payload = json.loads(payload_json)
        except Exception:
            payload = {}
        out.append({
            "id": eid,
            "session_id": sess,
            "event_type": etype,
            "timestamp": ts,
            "payload": payload,
        })
    return out
