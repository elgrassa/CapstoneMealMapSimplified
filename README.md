# meal-map — capstone submission

> **Live grading app:** https://elgrassa-capstonemealmapsimplified-demo-uiapp-djyorf.streamlit.app/ (Streamlit Cloud)
> **Production product:** https://meal-map.app
> **Score (latest scorer run):** [`docs/self-score-report.md`](docs/self-score-report.md)

[meal-map](https://meal-map.app) is a family meal-planning product. This repo is the **capstone submission** for Alexey Grigorev's "From RAG to Agents" course. It contains the retrieval + agent + evaluation spine: Python code, a committed demo corpus, tests, an evaluation harness, and a Streamlit app **built specifically for capstone grading** (deployed on Streamlit Cloud — URL above).

The full product UI (family setup, weekly plan, shopping, pantry, nutrition tracking) lives at [meal-map.app](https://meal-map.app) and is in active development. The Streamlit app in this repo is **not** the product — it's a grading surface that exercises the retrieval + agent pipeline end-to-end in 5 tabs.


<img width="2882" height="2692" alt="215FD3BC-D69B-421E-B74E-4B318712F5D3" src="https://github.com/user-attachments/assets/411ea58a-8608-493b-9572-88f13806daab" />
<img width="2924" height="2730" alt="7250DD96-9425-4D2B-805A-86ACBB8DD434" src="https://github.com/user-attachments/assets/40f4a7e9-aeac-48d3-b5b3-3be7a63bbfd6" />
<img width="2918" height="2706" alt="34F69E0F-B324-4AB1-85B1-6C7BF88C6052" src="https://github.com/user-attachments/assets/d9ea35ed-e383-492e-8eda-102f899c1543" />
<img width="1084" height="724" alt="AA45CC1C-E80F-42EE-B491-E691FF766875_1_105_c" src="https://github.com/user-attachments/assets/1eab19f4-6c6d-44fb-bf6e-a4eae0c43545" />

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

**Is this RAG?** Yes. Every agent query flows: user question → `search_knowledge` retrieves chunks from the BM25-indexed demo corpus (4 public-domain sources, 28 chunks) → retrieved chunks are passed to `gpt-4.1-mini` as grounding context → the response cites the `chunk_id` it drew from → an authority-weighted evidence gate classifies confidence as `supported / fallback / refused`. Verifiable live in **Tab 1** (`Query the demo`) and **Tab 5** (`Generate plan via the RAG agent`). The static JSON artefacts (`data/rag/demo/derived/*.json`) are a separate, non-RAG path used for deterministic comparison — they're *derived from* the same corpus but serve as an offline fallback for cost-sensitive displays.

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

## Reproducibility

- **Python pinned.** `pyproject.toml` requires Python `>=3.13,<3.14`.
- **Dependencies locked.** [`uv.lock`](uv.lock) is committed; `uv sync` gives everyone the same versions.
- **Data accessible.** The demo BM25 corpus (4 public-domain sources, 28 chunks) is committed under [`data/rag/demo/`](data/rag/demo/). No external downloads required. Each source file's SHA256 is recorded in [`data/rag/demo/provenance_manifest.json`](data/rag/demo/provenance_manifest.json); `make seed` re-verifies every hash in <1 second.
- **One-command setup:** `git clone … && cd CapstoneMealMapSimplified && uv sync && make seed && make test` — 118 tests green, zero API key required.
- **Docker alternative:** `docker compose up -d` brings up the seed job + backend + monitoring dashboard + Streamlit grading app in one command.
- **CI regression gate.** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs seed → test → eval-offline → tuning sweep on every PR.

---

## Best coding practices

| Practice | Evidence |
|---|---|
| **Containerization (Docker)** | [`Dockerfile`](Dockerfile) — `python:3.13-slim` base, bakes the demo corpus into the image |
| **docker-compose all-in-one** | [`docker-compose.yml`](docker-compose.yml) — 4 services (seed, backend, dashboard, streamlit app) with a `service_completed_successfully` gate on `seed` |
| **Makefile** | [`Makefile`](Makefile) — 13 targets: `install` / `seed` / `test` / `mutmut` / `tune` / `eval-offline` / `eval-live` / `serve` / `dashboard` / `demo` / `docker-up` / `docker-down` / `clean` |
| **UV + virtual env** | [`pyproject.toml`](pyproject.toml) + [`uv.lock`](uv.lock). Setup uses `uv sync`; the lockfile pins every transitive dep |
| **CI/CD** | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — 3 jobs (test, mutation-tests, live-eval). Live-eval is manual-only (`workflow_dispatch`) so PRs stay free |

---

## Additional bonus points

- **Terminal UI** — [`ai/week1-rag/cli/week1-meal-query-agent.py`](ai/week1-rag/cli/week1-meal-query-agent.py) runs the full agent from a single CLI call: `python3 ai/week1-rag/cli/week1-meal-query-agent.py "What is the RDA for vitamin D?"`.
- **Web UI (capstone grading)** — [`demo_ui/app.py`](demo_ui/app.py) is a Streamlit app built for evaluation: 5 tabs with live parameter tuning. `make demo` opens it on `http://localhost:8502`.
- **Web UI (production)** — the full React product at [meal-map.app](https://meal-map.app) — see the screenshot grid above.
- **Cloud deployment** — the Streamlit grading app deploys to Streamlit Community Cloud from this repo (free tier, public repos). Setup: [`docs/deployment.md`](docs/deployment.md). Production React UI at [meal-map.app](https://meal-map.app) is on a separate stack (Base44).

---

## Streamlit app for capstone evaluation


https://elgrassa-capstonemealmapsimplified-demo-uiapp-djyorf.streamlit.app/

[`demo_ui/app.py`](demo_ui/app.py) runs on port 8502 (`make demo`). Six tabs:

1. **Architecture walkthrough** — a diagram of the pipeline above, each node linked to its module file.
2. **Query the demo** — runs the full agent against the baked corpus. "Use pre-processed corpus" is on by default; uncheck to upload your own text and exercise the full parse → chunk → index → retrieve → respond flow on it.
3. **Book parsing playground** — pick a chunking strategy and see the chunks it produces.
4. **Evaluation laboratory** — pick a ground-truth case, see retrieval output, LLM-as-Judge scoring.
5. **Parameter tuning sandbox** — move thresholds and authority weights, watch the evidence gate flip supported / fallback / refused.
6. **Recipe nutrition & household fit** — pick one of the 5 baked recipes, see its structured ingredients, per-serving macros, and a per-member verdict (safe / allergen-conflict / partial-data) for the demo household. Toggle the default `derived/recipes.json` path vs. the live regex parser + canonical-sample matcher to see how the same data is reached either way. Also shows a static sample 7-day plan for the demo household (full weekly plan generation is a production-only feature at [meal-map.app](https://meal-map.app)).

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
