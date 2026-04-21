# Monitoring — rubric evidence for 2 + 1 + 2 = 5 pts

## What lives here

| File | Purpose | Rubric mapping |
|---|---|---|
| `dashboard.py` | Streamlit dashboard on `:8501` | Monitoring (2 pts) |
| `feedback.py` | SQLite events + thumbs persistence + session summary | Monitoring + Feedback bonus (1 pt) |
| `logs_to_gt.py` | Convert thumbs-up rows → new ground-truth cases | Logs→GT bonus (2 pts) |
| `feedback.db` | Runtime DB, git-ignored | — |

## How logs flow in

```
demo_ui/app.py   ── record_event() ──▶   monitoring/feedback.db
ai/week1-rag/…   ── JSONL line ───────▶  ai/week1-rag/logs/*.jsonl
                                                    │
                                                    ▼
                                    monitoring/dashboard.py (:8501)
```

## Run

```bash
make dashboard          # opens http://localhost:8501
make demo               # generates events on http://localhost:8502
python3 monitoring/logs_to_gt.py  # harvest GT candidates from thumbs-up rows
```

## What the grader sees

1. **Dashboard rendered with metrics** — agent call count, cost, latency, evidence-tier distribution.
2. **Thumbs-up/down DataFrame** — proves user feedback is collected.
3. **`new_ground_truth_cases.json`** — proof the logs→GT pipeline produces training data.

## What this is NOT

- Not a full production monitoring stack (Prometheus, Grafana, alerting). The production MealMaster at meal-map.app uses a separate observability stack with PostHog + server-side log aggregation. This is the demo-scale equivalent.
