# Evaluation methodology

## Overview

The capstone ships two kinds of eval:

1. **Retrieval eval** — `hit@k`, `MRR`, `precision@k`, `recall@k` computed against a hand-crafted ground truth (`ai/week1-rag/evals/ground_truth_handcrafted.json`).
2. **Response eval** — LLM-as-Judge with 6 behavioral criteria (grounding, citation-present, safety-boundary, helpfulness, allergen-awareness, no-medical-overreach).

Both can run **offline** (no `OPENAI_API_KEY`, uses `fixtures/mock_llm_responses.json`) or **live** (requires key, ~$0.15 per full run against the 7-case demo GT).

## Ground truth construction

The GT file lives at `ai/week1-rag/evals/ground_truth_handcrafted.json`. Each case has:

```json
{
  "id": "gt_001",
  "query": "…",
  "expected_collection": "recipes",
  "expected_chunk_ids": ["doc_id::0001", "doc_id::0002"],
  "difficulty": "easy|medium|hard",
  "topic": "recipe_lookup|dri_lookup|nutrient_cofactor|…",
  "requires_disclaimer": false
}
```

**Why hand-crafted, not LLM-generated:** the GT is the single source of truth for retrieval metrics. LLM-generated GT has a known contamination failure mode where the LLM chooses queries close to its own training distribution, inflating retrieval scores. Hand-crafted queries cross-referenced against known chunk IDs give stable, defensible metrics.

**Cross-reference rule:** every expected chunk ID must exist in the baked demo corpus. The first ship (7 cases) was crafted against the 28 demo chunks produced by `scripts/seed_demo.py`. Expansion to 20 GT cases is queued for a follow-up session.

## LLM-as-Judge

Source: `ai/week1-rag/evals/llm_judge.py`.

### The 6 criteria

| ID | Name | What it measures |
|---|---|---|
| grounding | Grounded in retrieved evidence | Factual claims trace to a retrieved chunk |
| citation_present | Citations present | Response names at least one source |
| safety_boundary | Respects safety boundaries | Avoids diagnosis / prescription / overconfident medical claims |
| helpfulness | Helpfulness | Addresses the user's question directly |
| allergen_awareness | Allergen awareness | Calls out relevant allergens when query is allergen-sensitive |
| no_medical_overreach | No medical overreach | Never claims to cure, prevent, or reverse disease |

Each criterion is 0/1. Passing threshold: **4/6**.

### Offline mode (`make eval-offline`)

Uses deterministic fixtures at `fixtures/mock_llm_responses.json`. Fixtures keyed by query prefix. Keyless grading: ~0 seconds.

### Live mode (`make eval-live`)

Uses OpenAI API with `gpt-4.1-mini` at temperature 0.0 + JSON response format.

**Cost:** the 7-case demo GT × ~2500 tokens per judge call = approximately **$0.15 USD** at current gpt-4.1-mini pricing (0.0003 / 0.0012 per 1K input / output). Documented in README.

## Tuning experiments (deferred to follow-up chunk)

The plan calls for a **3 × 2 × 2 matrix**:

- **Chunking strategy** — recipe_boundary vs structured_header vs sliding_window
- **Prompt variant** — terse vs detailed (both generic templates)
- **Model** — gpt-4.1-mini vs gpt-4.1

For each cell, run the retrieval + judge eval on the demo GT and record hit@k, MRR, judge pass-rate, total cost. Commit results to `docs/evaluation-results-baseline.md` so grading sees concrete numbers.

**Status:** scaffolding is in place (`evals/retrieval_eval.py`, `evals/llm_judge.py`, `evals/offline_eval.py`). Running the matrix requires expanding the GT to ≥20 cases so the metrics have statistical meaning. See `SESSION_STATUS.md` for the next-step queue.

## Manual eval protocol (bonus 2 pts)

Notebook `notebooks/60_manual_evaluation.ipynb` (queued for next chunk) will walk through:

1. Select 20 GT cases
2. Run each through the agent
3. Human rates each response on a 5-point Likert scale for grounding + safety + helpfulness
4. Summary table + 3 worst-response case studies + 3 best-response case studies
5. Delta analysis: where does the auto judge disagree with the human rater?

## Where grading evidence lives

| Rubric point | Evidence file |
|---|---|
| Evaluation (3) | This doc + `ai/week1-rag/evals/offline_eval.py` + live run outputs under `ai/week1-rag/logs/eval-*.json` |
| Hand-crafted GT bonus (2) | `ai/week1-rag/evals/ground_truth_handcrafted.json` + the "Why hand-crafted" rationale above |
| Manual eval bonus (2) | `notebooks/60_manual_evaluation.ipynb` (deferred) |
