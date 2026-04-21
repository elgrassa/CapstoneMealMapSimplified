# Session status — 2026-04-21 autonomous chunk

This file tracks what the autonomous 1-2h chunk delivered and what's queued for the next session. It's meant as a quick handoff note for the user returning to the branch.

## ✅ What landed this chunk

- **Folder + foundation** — `pyproject.toml` (Python 3.13), `Makefile`, `Dockerfile`, `docker-compose.yml`, `LICENSE` (AGPL-3.0), `NOTICE`, `.env.example`, `.gitignore`, `README.md`, `.github/workflows/ci.yml`.
- **Scrubbed Python modules** under `src/mealmaster_ai/` — RAG layer (chunking, search, router, reranker, hybrid, evidence gate, pipeline, models, config), validation + data samples (canonical ingredients, medical boundary).
- **Agent layer** under `ai/week1-rag/` — `pydantic_agent.py` (with deterministic fallback when OPENAI_API_KEY is missing), 8 tools in `agent_tools_v2.py`, `agent_config.py`, `structured_models.py`, `rules_corpus.py` (3-rule sample), `agent_observability.py`, eval harness (`evals/llm_judge.py`, `evals/retrieval_eval.py`, `evals/offline_eval.py`), hand-crafted GT (7 cases), CLI agent.
- **Backend** — FastAPI app, `/api/v1/health`, `/api/v1/rag/query`, `/api/v1/rag/agent-query`, corpus loader.
- **Demo corpus** — 4 public-domain sources (2 recipes from Utah WIC + California WIC; 2 nutrition textbooks from Open Oregon + UH Hawai'i) chunked into **28 total chunks**, BM25-indexed, committed under `data/rag/demo/`. Provenance manifest with SHA256 per doc.
- **Streamlit demo UI** (`demo_ui/app.py` on port 8502) — 5 tabs: Architecture walkthrough / Query the demo / Book parsing playground / Evaluation laboratory / Parameter tuning sandbox. **"Use pre-processed demo corpus (default ON) / Parse my own" checkbox** across every applicable tab. Sidebar with cost meter, feedback counters, rubric-coverage checklist.
- **Monitoring** — `monitoring/dashboard.py` on port 8501, `monitoring/feedback.py` (SQLite), `monitoring/logs_to_gt.py` (thumbs-up → GT).
- **Tests** — 42 tests across 6 files, all green in 0.21 s: `tests/unit/{test_chunking,test_evidence_gate,test_router,test_agent_tools,test_structured_models}.py`, `tests/judge/test_offline_eval.py`.
- **Docs** — `problem-statement.md`, `architecture.md`, `agent-tools.md`, `evaluation-methodology.md`, `ip-strategy.md`.

## Rubric coverage estimate (post-this-chunk)

| Criterion | Max | Earned this chunk (estimate) | Gap to 100% |
|---|---|---|---|
| Problem description | 2 | 2 | — |
| KB + retrieval | 2 | 2 | — |
| Agents and LLM | 3 | 3 | — |
| Code organization | 2 | 2 | — |
| Testing | 2 | 2 | — |
| Evaluation | 3 | 2 | Tuning matrix + committed baseline results pending |
| Eval bonus — hand-crafted GT | 2 | 1 | 7 cases shipped; expand to 20 |
| Eval bonus — manual eval | 2 | 0 | `60_manual_evaluation.ipynb` + narrative pending |
| Monitoring | 2 | 2 | — |
| Monitoring bonus — feedback | 1 | 1 | — |
| Monitoring bonus — logs→GT | 2 | 2 | — |
| Reproducibility | 2 | 2 | — |
| Docker | 1 | 1 | — |
| Compose all-in-one | 2 | 2 | — |
| Makefile | 1 | 1 | — |
| UV | 1 | 0.5 | `uv.lock` needs `uv sync` (deferred if network-shy) |
| CI/CD | 2 | 2 | — |
| UI bonus | 1 | 1 | Triple-redundant |
| Cloud bonus | 2 | 2 | meal-map.app live |
| **Total** | **35** | **~30.5** | ≥30 target met |

## Verification commands the user can run on return

```bash
cd SimplifiedMealMasterCapstone

# Tests (all 42 green)
python3 -m pytest tests/ -q

# Offline eval (mock fixtures, no API key)
python3 ai/week1-rag/evals/offline_eval.py --mode offline --fixtures fixtures/mock_llm_responses.json

# Seed demo (<1 s; already seeded this chunk — re-verifies SHA256)
python3 scripts/seed_demo.py

# Streamlit demo — THE showcase artifact for the grader
streamlit run demo_ui/app.py --server.port 8502

# Monitoring dashboard
streamlit run monitoring/dashboard.py --server.port 8501

# CLI agent
python3 ai/week1-rag/cli/week1-meal-query-agent.py "What is the RDA for vitamin D in adults?"
```

## Next-session queue (priority order)

1. **Expand GT to 20 hand-crafted cases** (13 more) targeting the 28 demo chunks with known answers.
2. **Run the 3 × 2 × 2 tuning matrix** (chunk strategy × prompt × model) and commit `docs/evaluation-results-baseline.md` with real numbers.
3. **`uv sync` + commit `uv.lock`** — earns the remaining 0.5 pt on UV criterion.
4. **Notebooks** — `20_retrieval_eval.ipynb`, `50_judge_eval.ipynb`, `60_manual_evaluation.ipynb` pre-run with outputs committed.
5. **Full docs** — problem-statement done; add `retrieval-evaluation.md`, `monitoring-setup.md`, `canonical-data.md`, `medical-boundary-pattern.md`.
6. **Media assets** — `agent-demo.gif`, cropped `mealmap-screenshot.png` (user-captured).
7. **Sentence-transformers embeddings** — optional; `make seed --embed` once the ml extra is installed.
8. **PR description expansion** — after review, add a detailed summary listing each rubric pt earned.

## Known gaps documented honestly

- **Sentence-transformers embeddings not baked.** Hybrid-retrieval code path falls back to BM25 (documented in-code + in `data/rag/demo/README.md`). Fix: install `[ml]` extra, run `scripts/seed_demo.py --embed`.
- **7 GT cases, not 20.** Enough to smoke-test the eval pipeline; expand in next session.
- **Tuning matrix not run against real data.** Methodology is documented in `docs/evaluation-methodology.md`; matrix execution queued.
- **`uv.lock` not committed.** `uv sync` was not attempted this chunk to avoid network-dependent failures.
- **Notebooks are placeholders.** Directory exists; notebook files not written yet.
