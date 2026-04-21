# Retrieval evaluation

## Methodology

For each GT case `{query, expected_chunk_ids}` we run `search_knowledge(query, top_k=5)` and compute:

- **Hit@k** — 1 if any `expected_chunk_ids` appears in the top-k retrieved, else 0.
- **MRR** — mean reciprocal rank of the first expected chunk.
- **Precision@k** — fraction of top-k that are expected.
- **Recall@k** — fraction of expected chunks found in top-k.

Source: `ai/week1-rag/evals/retrieval_eval.py` + `ai/week1-rag/evals/ground_truth_handcrafted.json`.

## Approaches compared

| Approach | Implementation | Status |
|---|---|---|
| BM25 (BM25Lite) | Pure-Python BM25 over `text + source_title` | **Shipped + measured** |
| BM25 (minsearch) | `minsearch.Index` from PyPI | Shipped but scores not emitted by 0.0.10 — use BM25Lite for scoring |
| Hybrid (BM25 + sentence-transformers RRF) | `hybrid.run_hybrid_search` with `all-MiniLM-L6-v2` | Code shipped; measurements queued for next chunk |
| Rerank (heuristic diversity + authority) | `reranker.rerank` | Code shipped; not wired into default path |
| Rerank (cross-encoder) | `sentence-transformers/ms-marco-MiniLM-L-6-v2` | Production at meal-map.app; not shipped here |

## Why BM25 is the default in this demo

1. **Zero network.** Sentence-transformers downloads 90 MB on first use. BM25 is pure Python + data already committed.
2. **Reproducibility.** Deterministic scoring; no model-version drift.
3. **Small corpus.** 28 chunks — cross-encoder reranking is overkill at that scale.
4. **Grader-friendly.** Offline CI path runs in seconds; no secrets needed.

## Known limitations (documented honestly)

- **Semantic matching gap.** BM25 alone misses queries that use different vocabulary than the indexed text (e.g. "how much vitamin D" vs chunk saying "recommended dietary allowance"). Hybrid retrieval would close this gap.
- **Tiny corpus, tokenizer ties.** With 28 chunks, token collisions across sections produce occasional surprising top-1 results (a query for vitamin D can return the magnesium section because both mention "RDA" + "adults"). A larger corpus (~hundreds of chunks, as in production) amortizes this.
- **No query preprocessing.** Stop-word removal and stemming would help; deferred as not in scope for this chunk.

## Chosen approach and justification

For the demo shipped in this repo: **BM25Lite over adaptively-chunked corpus, with the evidence gate as a post-filter**. This gives:

- sub-second retrieval,
- deterministic scores,
- a meaningful confidence signal to feed the tiered evidence gate (supported / fallback / refused),
- zero runtime dependency on OpenAI embeddings or sentence-transformer downloads.

For the production system at meal-map.app: **BM25 + sentence-transformer embeddings (RRF-fused) + cross-encoder rerank** — an additional 1-2 metric points across Hit@5 / MRR that matter at scale but don't materially help a 28-chunk demo.

## Baseline numbers

See [evaluation-results-baseline.md](evaluation-results-baseline.md).

## Roadmap

| Chunk | What lands |
|---|---|
| This chunk | BM25 baseline + behavioral-test refusal path + committed numbers |
| Next chunk | Hybrid numbers (install `[ml]` extra, re-run seed with `--embed`) |
| Next chunk | Rerank wired into the default path + ablation numbers |
| Next chunk | GT expanded to 20 cases |
