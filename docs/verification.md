# Verification runbook

End-to-end sanity check after a clone. Matches what the grader would do.

```bash
git clone https://github.com/elgrassa/CapstoneMealMapSimplified
cd CapstoneMealMapSimplified
```

## 1. Dependencies (UV)

```bash
uv sync
```

Installs everything from `pyproject.toml` + `uv.lock`. Expect a clean `.venv/`.

## 2. Seed the pre-baked demo corpus (<5s, no downloads, SHA256-verified)

```bash
make seed
```

Expected output: `[seed_demo] 5/5 documents ready in 0.01s`. 5 sources → 38 total chunks (Utah WIC + California WIC + Open Oregon + UH Hawai'i + demo-added-for-capstone).

## 3. Unit + judge tests

```bash
make test
```

Expected: **127 passed** in ~2s. Tests cover chunking, evidence gate, router, agent tools (9), response validator, input guardrails, intent classifier, demo user profile, rate limiter, recipe nutrition, streamlit AppTest.

## 4. Offline eval (free — uses mock LLM fixtures, no API key)

```bash
make eval-offline
```

Writes a fresh result JSON under `ai/week1-rag/logs/eval-*.json`.

## 5. Live eval (optional — requires OPENAI_API_KEY, ~$0.15)

```bash
export OPENAI_API_KEY=sk-...
make eval-live
```

## 6. Docker end-to-end

```bash
docker compose up -d

# Backend health (GET)
curl http://localhost:8001/api/v1/health

# Agent query (POST with JSON — not GET with query param)
curl -X POST -H 'Content-Type: application/json' \
     -d '{"query": "show me a low-sodium baked chicken recipe", "demo_mode": true}' \
     http://localhost:8001/api/v1/rag/query

# Monitoring dashboard
open http://localhost:8501

# Streamlit grading app
open http://localhost:8502

docker compose down
```

The agent query should return a response citing a **Utah WIC** recipe chunk. Demo corpus sources: Utah WIC, California WIC, Open Oregon nutrition textbook, University of Hawai'i nutrition textbook, plus 5 demo-added recipes.

## 7. Terminal CLI agent

```bash
uv run python ai/week1-rag/cli/week1-meal-query-agent.py "What is the RDA for vitamin D?"
```

Expected: `supported` tier, 3-5 citations from `human_nutrition_hawaii` or `nutrition_science_everyday_application`.

## 8. CI workflow

```bash
# Using GitHub Actions locally (act):
act -j test

# Or trigger the hosted run via gh:
gh workflow run ci.yml --repo elgrassa/CapstoneMealMapSimplified
```

## 9. IP sweep — must exit 0

```bash
bash scripts/ip_sweep.sh
```

Scans the repo for denylisted production-only terms (Polish market, Base44 identifiers, personal emails, production field names). Expected: `[ip-sweep] clean`.

## 10. Self-score (user-side, requires OPENAI_API_KEY)

Either run the vendored wrapper locally:

```bash
export OPENAI_API_KEY=sk-...
bash scorer/run_self_score.sh
```

Or trigger via GitHub Actions:

```bash
gh workflow run capstone-self-score --repo elgrassa/CapstoneMealMapSimplified
```

Scorer uses `alexeygrigorev/github-project-scorer` with the `ai-bootcamp-maven.yaml` rubric against **https://github.com/elgrassa/CapstoneMealMapSimplified**. Result lands at `docs/self-score-report.md`. Latest committed run: 30 / 35.

## 11. Live Streamlit Cloud demo

Deployed app: **https://elgrassa-capstonemealmapsimplified-demo-uiapp-djyorf.streamlit.app/**

Tab 5 ("Recipe nutrition & household fit") is the end-to-end recipe → meal-plan flow:
- **RAG plan generator** at the top — click `Generate plan` / `🔁 Regenerate plan`, the agent retrieves recipes via BM25, filters against the demo household via `get_recipe_metadata`, and auto-reruns once if any pick violates the constraints.
- **Per-recipe inspector** in the middle — pick any of the 12 baked recipes to see ingredients / per-serving macros / household fit.
- **Static 7-day plan** at the bottom — 9 distinct recipes rotating, every slot safe-by-construction for all 4 household members.
