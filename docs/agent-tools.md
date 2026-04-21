# Agent tools

The capstone agent exposes **8 documented tools**. Each is a plain Python function with a docstring — the LLM sees that docstring as the tool description. Source: [ai/week1-rag/agent_tools_v2.py](../ai/week1-rag/agent_tools_v2.py).

| # | Tool | Purpose |
|---|---|---|
| 1 | `assess_query_strategy(query)` | Classify the query, pick retrieval mode + collection set. Always called first. |
| 2 | `search_knowledge(query, collections?, top_k?, mode?)` | BM25 / hybrid retrieval across allowed collections. Returns flat dicts with scores. |
| 3 | `check_allergens(text, restricted?)` | Word-boundary allergen detection. Sample of EU-14 groups in the demo. |
| 4 | `get_nutrition_facts(ingredient_name)` | Macro lookup for canonical ingredients (10-item sample). |
| 5 | `check_medical_boundaries(text)` | Forbidden-phrase + referral-trigger detection. Sample of 5 phrases + 2 triggers. |
| 6 | `get_evidence_confidence(search_results, ...)` | Run the evidence gate over a retrieved set. Returns a tier decision. |
| 7 | `search_books(query, book_ids?, top_k?)` | Scoped search within user-uploaded books (demo UI Tab 1 "parse my own"). |
| 8 | `add_book_note(book_id, note)` | Append a user-authored note to a book. |

## Example: full tool-chain for a nutrition question

The agent's decision flow for "What is the RDA for vitamin D in adults?":

```
1. assess_query_strategy("What is the RDA for vitamin D in adults?")
   → intent: nutrition, mode: hybrid, collections: ["nutrition_science"], disclaimer: no

2. search_knowledge(query, collections=["nutrition_science"], top_k=6, mode="hybrid")
   → results: [5 chunks from Open Oregon + UH Hawai'i, top score 5.957]

3. get_evidence_confidence(results)
   → status: supported, confidence: 5.957, 5 citations

4. <LLM composes response grounded in the top chunks>

5. (Optional) check_medical_boundaries(response_text)
   → boundary_ok: true (stays within nutrition-education)
```

## Tool schemas for structured output

The agent returns a `CapstoneRAGResponse` which includes a `tool_calls: list[ToolCall]` trace so every run is inspectable in the demo UI (Tab 1 → "Tool-calls trace") and in the monitoring dashboard.

## Registering indexes

Before `search_knowledge` can retrieve, indexes must be loaded:

```python
from agent_tools_v2 import register_index
from mealmaster_ai.rag.pipeline import build_index

index = build_index(chunks)
register_index("my_collection", index)
```

This happens automatically in:
- `backend/services/corpus_manager.load_all_demo_indexes()` — called on backend startup.
- `demo_ui/app.py` bootstrap.
- `ai/week1-rag/evals/offline_eval.py` eval CLI.

## Production differences

The production MealMaster agent at [meal-map.app](https://meal-map.app) runs with:
- **10 tools** (2 additional: `generate_meal_plan` + `validate_household_constraints` — not shipped here).
- **Full canonical ingredient database** (82 × 19 × EU-14) — this demo ships a 10-item sample.
- **Full medical-boundary validator** (44 phrases + 9 triggers) — this demo ships 5 + 2.
- **Full rule corpus** (curated across age-band, allergen, medical-condition, macro-bound categories) — this demo ships 3 example rules.
- **Tuned system prompt** — this demo ships a generic RAG template.
