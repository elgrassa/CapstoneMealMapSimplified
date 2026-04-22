# Architecture (sanitized)

This document describes the architectural patterns behind the capstone. It deliberately omits production tuning constants (exact chunk sizes tuned per real corpus, exact threshold curves, exact prompt wording, exact rule-corpus content). The public demo uses neutral starting values; production at [meal-map.app](https://meal-map.app) uses tuned values derived from internal eval runs.

## Layered pipeline

```
query → intent router → per-collection retrieval (BM25 + optional hybrid) → reranker → evidence gate (tiered) → agent (8 tools) → LLM → Pydantic validator → structured response
```

Each layer is implemented as a small, testable module.

### Layer 1 — Intent router (`src/mealmaster_ai/rag/router.py`)

- **Pattern:** keyword-based intent classification with a demo-mode allow-list.
- **Output:** `RoutingResult(intent, collections, requires_disclaimer, demo_blocked_collections, reason)`.
- **Why:** restricts retrieval to the right collections to keep BM25 index searches cheap and reduces irrelevant hits.

### Layer 2 — Retrieval (`src/mealmaster_ai/rag/search.py` + `hybrid.py`)

- **BM25 default** — pure-Python `BM25Lite` or `minsearch.Index`.
- **Optional hybrid** — BM25 + sentence-transformer embeddings, fused via reciprocal rank fusion (k=60).
- **Fallback semantics:** when embeddings aren't available, the system returns BM25 results unchanged. This is important for zero-internet grading.

### Layer 3 — Reranker (`src/mealmaster_ai/rag/reranker.py`)

- **Heuristic diversity + authority boost.** The production path at meal-map.app uses a cross-encoder; this demo ships a deterministic heuristic so reranking is reproducible in CI.

### Layer 4 — Evidence gate (`src/mealmaster_ai/rag/evidence_gate.py`)

- **Three tiers** — supported / fallback / refused — based on adjusted-top-score against two thresholds.
- **Authority weights** applied only to evidence collections (recipes pass through). Default weights: high=1.3, medium=1.0, low=0.7.
- **Safety-sensitive top-3** propagates `require_disclaimer`.
- **Tuning** happens at the threshold + weight knobs. The demo ships neutral defaults (0.3 / 0.1); production at meal-map.app uses thresholds tuned against real corpus + real GT.

### Layer 5 — Agent with 9 tools (`ai/week1-rag/pydantic_agent.py`)

- **Pattern:** PydanticAI agent with structured output (`CapstoneRAGResponse`). When `OPENAI_API_KEY` is unavailable, the agent falls back to a deterministic tool-calling loop so the demo still works offline.
- **8 tools:** see [agent-tools.md](agent-tools.md).
- **System prompt:** deliberately generic — production at meal-map.app uses a longer, domain-tuned prompt. The scrubbed template is visible in `pydantic_agent.SYSTEM_PROMPT`.

### Layer 6 — Validator (`ai/week1-rag/structured_models.py`)

- **Pattern:** Pydantic schema with a small fixed output shape — every response has `answer`, `evidence_tier`, `confidence`, `citations`, `tool_calls`, `requires_disclaimer`, `disclaimer_text`, `demo_blocked_collections`, `reasoning_notes`.
- This makes monitoring + eval trivially scoreable.

## Chunking (`src/mealmaster_ai/rag/chunking.py`)

Three strategies, one adaptive dispatcher:

| Strategy | Best for | Demo default (size / step) |
|---|---|---|
| `recipe_boundary` | Cookbooks (recipes start with structural markers) | 120 / 60 |
| `structured_header` | Textbooks (Markdown headers) | 150 / 75 |
| `sliding_window` | Generic text with no structure | 100 / 50 |

The `COLLECTION_CHUNK_PARAMS` dict maps each of the 5 collections to its (strategy, size, step) tuple. Production at meal-map.app uses different tuned values per real corpus — this demo ships neutral values that produce meaningful chunks on the bundled 4 documents.

## Knowledge assets shipped

| Asset | Sample shipped | Production counterpart |
|---|---|---|
| Canonical ingredients (USDA-based) | 10 items × 5 macros (`canonical_ingredients_sample.py`) | 82 items × 19 nutrition fields × EU-14 allergen tags |
| Medical-boundary validator | 5 forbidden phrases + 2 referral triggers (`medical_boundary_sample.py`) | 44 forbidden phrases + 9 referral triggers × 3 severities |
| Dietary-rule corpus | 3 example rules (`rules_corpus.py`) | Full curated catalog |
| Corpus | 2 collections fully populated | 5 collections fully populated |

The samples are illustrative — the *pattern* is public; the *content* stays private. See [ip-strategy.md](ip-strategy.md) for the reasoning.

## Serving

- `backend/main.py` — FastAPI app, `/api/v1/health` + `/api/v1/rag/query` + `/api/v1/rag/agent-query`.
- `backend/services/corpus_manager.py` — loads all demo indexes at startup and registers them with `agent_tools_v2`.

## Monitoring

- `ai/week1-rag/agent_observability.py` — per-call JSONL logger (cost, tokens, duration, tier).
- `monitoring/feedback.py` — SQLite events + thumbs DB.
- `monitoring/dashboard.py` — Streamlit dashboard on `:8501`.
- `monitoring/logs_to_gt.py` — harvests thumbs-up rows into new GT candidates.

## Design choices worth noting

1. **Offline path is first-class.** Every critical component has a no-API-key fallback path: BM25 works without embeddings; the agent works without pydantic-ai; the judge works with `fixtures/mock_llm_responses.json`.
2. **Imports are path-based, not installed.** The capstone works with `pip install -e .` or just `PYTHONPATH=...` — no special distribution required.
3. **Demo mode is a first-class config flag.** `AgentConfig.demo_mode` + router `demo_allow_list` restrict retrieval to 2 of 5 collections and explicitly message the remaining 3 as "production-only". No empty tool results that would confuse a grader.
