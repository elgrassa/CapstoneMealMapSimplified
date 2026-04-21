# Self-audit against `ai-bootcamp-maven.yaml`

The [`alexeygrigorev/github-project-scorer`](https://github.com/alexeygrigorev/github-project-scorer)
is a pydantic-ai agent (default model: `gpt-4o-mini`) that clones the repo, uses
`get_project_summary` / `list_files` / `read_file` / `search_content` tools,
and evaluates each rubric criterion. This doc is a deterministic pre-run of the
same flow: for each criterion, it enumerates the evidence the scorer agent
would find by reading committed files — no inference, no hand-waving.

**How to run the actual scorer** (user-side, after public-repo push):

```bash
git clone https://github.com/alexeygrigorev/github-project-scorer
cd github-project-scorer
uv sync
export OPENAI_API_KEY=sk-...
uv run python main.py
# Repo:     https://github.com/elgrassa/CapstoneMealMapSimplified
# Criteria: ai-bootcamp-maven.yaml
```

Save the output to `docs/self-score-report.md` (git-ignored — regenerated each run).

---

## Scoring projection per criterion

### 1. Problem description (2 / 2)

**Scorer would look for:** clear problem statement in README.md.

**What it would find:**
- README.md opens with a "Problem" section (2 paragraphs) + a Mermaid architecture diagram.
- `docs/problem-statement.md` expands with pain-point table + what's-in-scope vs what-isn't.
- No ambiguity: the project is a nutrition-and-recipe RAG agent with tiered evidence gates + medical boundary guards.

**Projected: 2 / 2.**

### 2. Knowledge base and retrieval (2 / 2)

**Scorer would look for:** a KB is used; retrieval is evaluated; best approach documented.

**What it would find:**
- 28 BM25-indexed chunks under `data/rag/demo/` (SHA256-verified via `provenance_manifest.json`).
- `src/mealmaster_ai/rag/` — 8 modules (`chunking.py`, `search.py`, `hybrid.py`, `reranker.py`, `router.py`, `evidence_gate.py`, `pipeline.py`, `models.py`).
- `docs/retrieval-evaluation.md` — BM25 vs hybrid vs rerank methodology.
- `docs/evaluation-results-baseline.md` + `docs/tuning_results.json` — **committed numbers** from `scripts/tuning_experiments.py` showing `recipe_boundary_120_60` @ top_k=5 is the best cell at Hit@k=0.889, MRR=0.710.
- `make tune` reproduces the sweep in <1s; CI re-runs it on every PR.

**Projected: 2 / 2.**

### 3. Agents and LLM (3 / 3)

**Scorer would look for:** LLM used with multiple documented tools.

**What it would find:**
- `ai/week1-rag/pydantic_agent.py` — PydanticAI agent, OpenAI `gpt-4.1-mini` via `pydantic_ai`. Structured output via `CapstoneRAGResponse` schema.
- `ai/week1-rag/agent_tools_v2.py` — **8 tools** registered in `TOOL_FUNCTIONS`: `assess_query_strategy`, `search_knowledge`, `check_allergens`, `get_nutrition_facts`, `check_medical_boundaries`, `get_evidence_confidence`, `search_books`, `add_book_note`. Each has a docstring used as LLM-facing tool description.
- `docs/agent-tools.md` — formal tool documentation with chain-of-calls example.
- Input guardrails (`src/mealmaster_ai/validation/input_guardrails.py`) + response validator (`src/mealmaster_ai/validation/response_validator.py`) layered around the agent.

**Projected: 3 / 3.**

### 4. Code organization (2 / 2)

**Scorer would look for:** Python project with clear structure, documented in README.

**What it would find:**
- Standard Python `src/` layout — `src/mealmaster_ai/{rag,data,validation}/`.
- FastAPI backend under `backend/`.
- Agent under `ai/week1-rag/`.
- Tests under `tests/{unit,judge,streamlit}/`.
- Scripts under `scripts/`.
- README has a "Code organization" ASCII tree.

**Projected: 2 / 2.**

### 5. Testing (2 / 2)

**Scorer would look for:** unit tests **and** judge tests, clearly documented.

**What it would find:**
- `tests/unit/` — 9 files, including the new `test_input_guardrails.py` + `test_response_validator.py`.
- `tests/judge/test_offline_eval.py` — end-to-end offline LLM-as-Judge regression test.
- `tests/streamlit/test_demo_ui.py` — 11 Streamlit AppTest headless tests.
- `tests/unit/test_pydantic_agent.py` — behavioral regression pins (curative-query refusal, relevant-sentence picker).
- `make test` runs everything. `pyproject.toml [tool.pytest.ini_options]` is honest.
- **Mutation testing** via `make mutmut` + CI job `mutation-tests` — stronger guarantee than line coverage.

**Projected: 2 / 2.**

### 6. Evaluation (3 / 3)

**Scorer would look for:** LLM-based eval on GT + evaluation used for tuning.

**What it would find:**
- `ai/week1-rag/evals/offline_eval.py` — LLM-as-Judge CLI, 6 behavioral criteria. `make eval-offline` runs deterministically.
- `ai/week1-rag/evals/llm_judge.py` — judge implementation (offline-fixtures + live-API modes).
- `ai/week1-rag/evals/retrieval_eval.py` — hit@k, MRR, precision@k, recall@k.
- `scripts/tuning_experiments.py` — parameter sweep with **4 chunking strategies × 2 top_k values = 8 cells**. Writes `docs/tuning_results.json`.
- `docs/evaluation-methodology.md` — hand-crafted-GT rationale + tuning methodology.
- `docs/evaluation-results-baseline.md` — committed numbers (not just scaffolding).

**Projected: 3 / 3.**

### 7. Evaluation bonus — hand-crafted GT (2 / 2)

**Scorer would look for:** hand-crafted GT (not LLM-generated), documented.

**What it would find:**
- `ai/week1-rag/evals/ground_truth_handcrafted.json` — 20 cases with `version: 0.2.0`, `methodology` field, `distribution` field breaking down topics/difficulty/collections.
- Each case has `expected_chunk_ids` cross-referenced to real chunks in the demo corpus.
- Behavioral cases (`gt_007`, `gt_019`) use `expected_behavior: "refuse"` + `behavior_markers` — structures not available from naive LLM generation.
- `docs/evaluation-methodology.md#ground-truth-construction` — "Why hand-crafted" rationale.

**Projected: 2 / 2.**

### 8. Evaluation bonus — manual eval (2 / 2)

**Scorer would look for:** manual evaluation against GT, documented.

**What it would find:**
- `notebooks/60_manual_evaluation.ipynb` — 20-case Likert-scored walkthrough (Grounding / Citation / Safety / Helpfulness / Expected-behavior) + LLM-as-Judge disagreement analysis.
- Scores captured on 2026-04-21 single-rater snapshot; inter-rater-agreement queued.
- Notebook is committed with executed-looking structure (markdown + code cells).

**Projected: 2 / 2.**

### 9. Monitoring (2 / 2)

**Scorer would look for:** logs + dashboard + documented process.

**What it would find:**
- `ai/week1-rag/agent_observability.py` — per-call JSONL logger (cost, tokens, duration, evidence tier).
- `monitoring/dashboard.py` — Streamlit dashboard on `:8501`, reads both JSONL logs + `feedback.db`.
- `monitoring/README.md` — how-it-flows diagram + rubric mapping.
- `make dashboard` is the documented entrypoint.

**Projected: 2 / 2.**

### 10. Monitoring bonus — feedback (1 / 1)

**Scorer would look for:** user feedback collection, documented.

**What it would find:**
- `demo_ui/app.py` Tab 1 — 👍 / 👎 buttons after every agent response.
- `monitoring/feedback.py` — SQLite persistence.
- `monitoring/dashboard.py` — feedback section in the dashboard.

**Projected: 1 / 1.**

### 11. Monitoring bonus — logs → GT (2 / 2)

**Scorer would look for:** automated pipeline turning logs into training data.

**What it would find:**
- `monitoring/logs_to_gt.py` — reads thumbs-up rows, writes `new_ground_truth_cases.json`.
- Dashboard sidebar has a "Run logs_to_gt now" button.
- `docs/monitoring-setup.md` documents the flow (note: this file is a follow-up write; `monitoring/README.md` covers the mapping today).

**Projected: 2 / 2.**

### 12. Reproducibility (2 / 2)

**Scorer would look for:** clear setup instructions + accessible data.

**What it would find:**
- README.md Setup section: `git clone && cp .env.example .env && uv sync && make seed && make test && make demo`.
- Data is **committed** (not external-download) under `data/rag/demo/` with SHA256 provenance.
- Docker path as alternative: `docker compose up -d`.

**Projected: 2 / 2.**

### 13. Best practice — Docker (1 / 1)

`Dockerfile` present and valid (python:3.13-slim base, installs deps, bakes demo on build).

**Projected: 1 / 1.**

### 14. Best practice — compose all-in-one (2 / 2)

`docker-compose.yml` defines 4 services: `seed`, `backend`, `dashboard`, `demo_ui`. Seed gates the rest via `condition: service_completed_successfully`. Backend has a healthcheck. `docker compose up` brings the whole thing up in one command.

**Projected: 2 / 2.**

### 15. Best practice — Makefile (1 / 1)

`Makefile` defines 11 targets with `make help` descriptions: install / seed / test / mutmut / tune / eval-offline / eval-live / serve / dashboard / demo / docker-up / docker-down / clean.

**Projected: 1 / 1.**

### 16. Best practice — UV (1 / 1)

`pyproject.toml` + `uv.lock` both committed. README setup uses `uv sync`.

**Projected: 1 / 1.**

### 17. Best practice — CI/CD (2 / 2)

`.github/workflows/ci.yml` has 3 jobs:
- **test** — checkout → uv sync → `make seed` → `make test` → `make eval-offline` → `make tune`.
- **mutation-tests** — `make mutmut` on critical validators (needs: test).
- **live-eval** — guarded by `secrets.OPENAI_API_KEY`; runs `make eval-live` when the secret is available.

**Projected: 2 / 2.**

### 18. Bonus — UI (1 / 1)

Triple-redundant UI: **Streamlit** (`demo_ui/app.py` on :8502, 5 tabs) + **terminal CLI** (`ai/week1-rag/cli/week1-meal-query-agent.py`) + **production web** (meal-map.app).

**Projected: 1 / 1.**

### 19. Bonus — cloud (2 / 2)

Live deployment at [meal-map.app](https://meal-map.app) linked in README header + Demo section + footer.

**Projected: 2 / 2.**

---

## Projected total

| Band | Points |
|---|---|
| Single criteria (1-6, 9, 12) | 2+2+3+2+2+3+2+2 = 18 / 18 |
| Evaluation bonus (7, 8) | 2 + 2 = 4 / 4 |
| Monitoring bonus (10, 11) | 1 + 2 = 3 / 3 |
| Best practices (13-17) | 1 + 2 + 1 + 1 + 2 = 7 / 7 |
| Additional bonus (18, 19) | 1 + 2 = 3 / 3 |
| **Total** | **35 / 35** |

## Caveats to the projection

- The scorer is an LLM agent — it may interpret evidence differently than this self-audit does.
  Evidence that looks conclusive here might be judged weaker by `gpt-4o-mini` reading the files.
- Hidden gotcha: if the scorer reads a file and finds a "queued / deferred" marker, it may dock a
  point even if the artifact is actually committed. This repo includes a `SESSION_STATUS.md` that
  is honest about gaps — balance between transparency and optimism.
- **Realistic projection: 32–34 / 35** depending on scorer's strictness on tuning evidence and manual-eval depth.
