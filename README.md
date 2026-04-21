# meal-map — capstone submission

[meal-map](https://meal-map.app) is a family meal-planning product. This repo is the **capstone submission** for Alexey Grigorev's "From RAG to Agents" course. It contains the retrieval + agent + evaluation spine: Python code, a committed demo corpus, tests, an evaluation harness, and a Streamlit app **built specifically for capstone grading**.

The full product UI (family setup, weekly plan, shopping, pantry, nutrition tracking) lives at [meal-map.app](https://meal-map.app) and is in active development. The Streamlit app in this repo is **not** the product — it's a grading surface that exercises the retrieval + agent pipeline end-to-end in 5 tabs.

---

## Production UI (meal-map.app)

The capstone evaluates the AI pipeline powering these screens. The React UI itself is in progress and not part of this submission.

| Dashboard | Recipe hub | AI transparency | How it works | Meal planner |
|---|---|---|---|---|
| ![Dashboard](docs/media/meal-map-dashboard.png) | ![Recipes](docs/media/meal-map-recipes.png) | ![AI transparency](docs/media/meal-map-ai-transparency.png) | ![How it works](docs/media/meal-map-howitworks.png) | ![Meal planner](docs/media/meal-map-planner.png) |

Screenshot source files: [`docs/media/README.md`](docs/media/README.md).

---

## Problem

Every week a family has to answer: *what should we cook?* and *is this food safe and nutritious for everyone?* Generic AI chatbots don't cite sources, will happily claim cures, and aren't allergen-aware. Recipe apps skip the nutrition side. meal-map combines a deterministic safety layer (EU-14 allergens, medical-boundary validation, GDPR-aware handling of health PII) with an LLM that answers grounded in a curated corpus.

This capstone ships the RAG + agent + evaluation + monitoring subset of that system. The production privacy stack (field-level encryption, subprocessor flows) is out of scope because it's tied to the React/Base44 backend.

---

## Architecture

```
query → input guardrails → strict intent → curative-claim check → rate limiter
      → personalize (demo household) → retrieve (BM25, optional hybrid)
      → evidence gate (supported / fallback / refused) → agent (8 tools)
      → response validator → structured response + citations
```

- Retrieval — `minsearch` BM25 + sentence-transformer vectors (RRF fused, optional). Full pipeline in [`src/mealmaster_ai/rag/`](src/mealmaster_ai/rag/).
- Agent — PydanticAI with `gpt-4.1-mini` and 8 documented tools. Falls back to a deterministic path when no API key is set. See [`ai/week1-rag/pydantic_agent.py`](ai/week1-rag/pydantic_agent.py) and [`docs/agent-tools.md`](docs/agent-tools.md).
- Evidence gate — authority-weighted top-score check with safety escalation. Source: [`evidence_gate.py`](src/mealmaster_ai/rag/evidence_gate.py).
- Evaluation — LLM-as-Judge (6 criteria) + retrieval metrics + chunk-strategy sweep. 20-case hand-crafted ground truth at [`ai/week1-rag/evals/ground_truth_handcrafted.json`](ai/week1-rag/evals/ground_truth_handcrafted.json).
- Monitoring — JSONL logs + SQLite feedback DB + Streamlit dashboard + logs → GT pipeline.

---

## Run locally

```bash
git clone https://github.com/elgrassa/CapstoneMealMapSimplified
cd CapstoneMealMapSimplified
uv sync
make seed            # verifies the baked BM25 corpus (<1s)
make test            # 107 tests
make eval-offline    # LLM-as-Judge on mock fixtures, no API key
make tune            # chunk-strategy × top_k sweep
```

With an OpenAI key:

```bash
export OPENAI_API_KEY=sk-...
make eval-live       # ~$0.15
make demo            # Streamlit grading app on http://localhost:8502
```

Docker:

```bash
docker compose up -d   # seed + backend + dashboard + streamlit grading app
```

---

## Streamlit app for capstone evaluation

[`demo_ui/app.py`](demo_ui/app.py) runs on port 8502 (`make demo`). Five tabs:

1. **Architecture walkthrough** — a diagram of the pipeline above, each node linked to its module file.
2. **Query the demo** — runs the full agent against the baked corpus. "Use pre-processed corpus" is on by default; uncheck to upload your own text and exercise the full parse → chunk → index → retrieve → respond flow on it.
3. **Book parsing playground** — pick a chunking strategy and see the chunks it produces.
4. **Evaluation laboratory** — pick a ground-truth case, see retrieval output, LLM-as-Judge scoring.
5. **Parameter tuning sandbox** — move thresholds and authority weights, watch the evidence gate flip supported / fallback / refused.

Sidebar shows a live cost budget (session + daily), the hardcoded demo household used for personalization, and a rubric-coverage checklist.

---

## Cost guardrail

The repo is public and the deployed Streamlit app uses a stored OpenAI key, so there's a built-in limiter: **20 live LLM calls per session per hour** + **$0.50 total spend per UTC day**. When either cap hits, the agent downgrades to the deterministic fallback path — the demo still works, it just stops spending. Overrides via env vars: `CAPSTONE_DAILY_BUDGET_USD`, `CAPSTONE_SESSION_LLM_CAP`, `CAPSTONE_SESSION_LLM_WINDOW_S`. Source: [`rate_limiter.py`](src/mealmaster_ai/rate_limiter.py).

---

## Intent policy

The agent only answers meal / nutrition / recipe / allergen questions. Off-topic queries get redirected. Prompt-injection attempts get blocked. Curative-claim queries ("can I cure X by eating Y?") are refused before retrieval with a clinician-referral disclaimer. All three policies are deterministic regex + substring checks in [`input_guardrails.py`](src/mealmaster_ai/validation/input_guardrails.py), backed by [`tests/unit/test_intent_classifier.py`](tests/unit/test_intent_classifier.py).

---

## Demo household

Every query is personalized against a hardcoded family — 2 adults + 2 children, dairy and peanut allergens, mediterranean cuisine, 30-minute cook time. No real data, reproducible across runs. Source + renderable markdown in [`demo_user_profile.py`](src/mealmaster_ai/data/demo_user_profile.py). The profile is visible in the Streamlit sidebar.

---

## Self-score

The `alexeygrigorev/github-project-scorer` tool with the `ai-bootcamp-maven.yaml` rubric runs against this repo via a manual GitHub Actions workflow. Latest result: [`docs/self-score-report.md`](docs/self-score-report.md).

Trigger a fresh run:

- GitHub Actions tab → `capstone-self-score` → Run workflow. Uses the repo's `OPENAI_API_KEY` secret. Commits the updated report back to `main`.
- Or locally: `export OPENAI_API_KEY=sk-...; bash scorer/run_self_score.sh`.

Per-criterion expected evidence: [`docs/self-audit.md`](docs/self-audit.md). Methodology: [`docs/evaluation-methodology.md`](docs/evaluation-methodology.md). Tuning numbers: [`docs/evaluation-results-baseline.md`](docs/evaluation-results-baseline.md) + [`docs/tuning_results.json`](docs/tuning_results.json).

---

## Rubric evidence

| Criterion | Evidence |
|---|---|
| Problem description (2) | this README, [`docs/problem-statement.md`](docs/problem-statement.md) |
| KB + retrieval (2) | [`src/mealmaster_ai/rag/`](src/mealmaster_ai/rag/), [`docs/retrieval-evaluation.md`](docs/retrieval-evaluation.md), [`docs/evaluation-results-baseline.md`](docs/evaluation-results-baseline.md) |
| Agents + LLM (3) | [`pydantic_agent.py`](ai/week1-rag/pydantic_agent.py), [`agent_tools_v2.py`](ai/week1-rag/agent_tools_v2.py), [`docs/agent-tools.md`](docs/agent-tools.md) |
| Code organization (2) | standard `src/` layout, modules split by concern |
| Testing (2) | 107 tests across [`tests/unit/`](tests/unit/), [`tests/judge/`](tests/judge/), [`tests/streamlit/`](tests/streamlit/); mutation via `make mutmut` |
| Evaluation (3) | [`ai/week1-rag/evals/`](ai/week1-rag/evals/), `make eval-offline` / `make eval-live` / `make tune` |
| Hand-crafted GT (2) | [`ai/week1-rag/evals/ground_truth_handcrafted.json`](ai/week1-rag/evals/ground_truth_handcrafted.json) — 20 cases with behaviour markers |
| Manual eval (2) | [`notebooks/60_manual_evaluation.ipynb`](notebooks/60_manual_evaluation.ipynb) |
| Monitoring (2) | [`monitoring/dashboard.py`](monitoring/dashboard.py), [`monitoring/README.md`](monitoring/README.md), `make dashboard` |
| Feedback bonus (1) | thumbs up/down in the Streamlit app Tab 1 → [`monitoring/feedback.py`](monitoring/feedback.py) |
| Logs → GT bonus (2) | [`monitoring/logs_to_gt.py`](monitoring/logs_to_gt.py) |
| Reproducibility (2) | `git clone && make seed && make test` — corpus is committed with SHA256 provenance |
| Docker (1) | [`Dockerfile`](Dockerfile) |
| Compose (2) | [`docker-compose.yml`](docker-compose.yml) — 4 services with seed gate |
| Makefile (1) | [`Makefile`](Makefile) |
| UV (1) | [`pyproject.toml`](pyproject.toml) + [`uv.lock`](uv.lock) |
| CI/CD (2) | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |
| UI bonus (1) | Streamlit (`demo_ui/app.py`) + CLI (`ai/week1-rag/cli/`) + production UI at [meal-map.app](https://meal-map.app) |
| Cloud bonus (2) | [meal-map.app](https://meal-map.app) |

---

## Deploying the Streamlit grading app

Streamlit Community Cloud, from this repo's `demo_ui/app.py`. Setup + required secrets: [`docs/deployment.md`](docs/deployment.md).

---

## License

AGPL-3.0. See [`LICENSE`](LICENSE).
