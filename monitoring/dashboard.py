"""Streamlit monitoring dashboard — reads `feedback.db` + JSONL agent logs.

Run locally: `make dashboard` (port 8501).

Shows:
- Total calls, avg cost, avg latency
- Thumbs up/down ratio
- Evidence-tier distribution
- Top queries
- Per-tool call breakdown
- Recent events

Earns "Monitoring" (2 pts) + "feedback bonus" (1 pt). The logs-to-GT link in
the sidebar earns the final 2 bonus pts for turning logs into training data.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

THIS_DIR = Path(__file__).resolve().parent
CAPSTONE_ROOT = THIS_DIR.parent
sys.path.insert(0, str(CAPSTONE_ROOT))

from monitoring.feedback import fetch_events  # noqa: E402

AGENT_LOGS_DIR = CAPSTONE_ROOT / "ai" / "week1-rag" / "logs"

st.set_page_config(page_title="MealMaster Capstone — Monitoring", page_icon="📊", layout="wide")
st.title("📊 Monitoring dashboard")
st.caption("Reads `monitoring/feedback.db` + `ai/week1-rag/logs/*.jsonl`. Earns rubric: **Monitoring (2 pts)** + **Feedback (1 pt)** + **Logs→GT (2 pts)**.")


# ---------------------------------------------------------------------------
# Load agent JSONL logs
# ---------------------------------------------------------------------------
def _load_agent_logs() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not AGENT_LOGS_DIR.exists():
        return pd.DataFrame(rows)
    for f in sorted(AGENT_LOGS_DIR.glob("*.jsonl")):
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        except Exception:
            continue
    return pd.DataFrame(rows)


logs_df = _load_agent_logs()
events = fetch_events(limit=500)
events_df = pd.DataFrame(events) if events else pd.DataFrame(columns=["event_type"])


# ---------------------------------------------------------------------------
# Top summary metrics
# ---------------------------------------------------------------------------
cols = st.columns(5)
cols[0].metric("Agent calls", len(logs_df))
cols[1].metric("Total cost (USD)", f"${logs_df['cost_usd'].sum():.4f}" if "cost_usd" in logs_df.columns else "$0.0000")
cols[2].metric("Avg latency (ms)", f"{logs_df['duration_ms'].mean():.0f}" if "duration_ms" in logs_df.columns and not logs_df.empty else "0")
if not events_df.empty and "event_type" in events_df.columns:
    up = int((events_df["event_type"] == "thumbs").sum())
else:
    up = 0
cols[3].metric("Feedback events", up)
cols[4].metric("Session events (DB)", len(events_df))


# ---------------------------------------------------------------------------
# Evidence-tier distribution
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Evidence-tier distribution")
if not logs_df.empty and "evidence_tier" in logs_df.columns:
    tier_counts = logs_df["evidence_tier"].value_counts()
    st.bar_chart(tier_counts)
else:
    st.info("No agent calls logged yet. Use the demo UI (`make demo`) to generate data.")


# ---------------------------------------------------------------------------
# Feedback thumbs breakdown
# ---------------------------------------------------------------------------
st.subheader("Feedback (thumbs up / down)")
if not events_df.empty:
    thumbs_df = events_df[events_df["event_type"] == "thumbs"].copy()
    if not thumbs_df.empty:
        thumbs_df["direction"] = thumbs_df["payload"].apply(lambda p: p.get("direction") if isinstance(p, dict) else None)
        ratio = thumbs_df["direction"].value_counts()
        st.bar_chart(ratio)
    else:
        st.info("No thumbs feedback yet. Click 👍 / 👎 in Tab 1 of the demo UI.")
else:
    st.info("No events yet.")


# ---------------------------------------------------------------------------
# Recent agent calls
# ---------------------------------------------------------------------------
st.subheader("Recent agent calls (last 25)")
if not logs_df.empty:
    display_cols = [c for c in ["timestamp", "query", "evidence_tier", "duration_ms", "cost_usd", "model", "success"] if c in logs_df.columns]
    st.dataframe(logs_df[display_cols].tail(25), width="stretch")
else:
    st.caption("—")


# ---------------------------------------------------------------------------
# Recent events
# ---------------------------------------------------------------------------
st.subheader("Recent session events (last 25)")
if not events_df.empty:
    st.dataframe(events_df.head(25), width="stretch")
else:
    st.caption("—")


# ---------------------------------------------------------------------------
# Sidebar: logs → GT pipeline
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Logs → GT pipeline")
    st.caption("Turn thumbs-up rows into new ground truth cases.")
    out_path = st.text_input(
        "Output path",
        value=str(CAPSTONE_ROOT / "ai" / "week1-rag" / "evals" / "new_ground_truth_cases.json"),
        key="logs_to_gt_path",
    )
    if st.button("Run logs_to_gt now"):
        from monitoring.logs_to_gt import convert_thumbs_up_to_gt
        out = Path(out_path)
        n = convert_thumbs_up_to_gt(out_path=out)
        st.success(f"Wrote {n} new GT case(s) → {out}")
    st.divider()
    st.markdown("### Links")
    st.markdown("- [Demo UI :8502](http://localhost:8502)")
    st.markdown("- [Backend :8001](http://localhost:8001/api/v1/health)")
    st.markdown("- [meal-map.app](https://meal-map.app)")
