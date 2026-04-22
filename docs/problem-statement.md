# Problem statement

## The user pain point

Every week, families across the EU and North America face the same recurring problem:

- **"What should we cook this week?"** — with 2–6 family members, everyone has different tastes, age-appropriate needs, and allergies. Meal planning by hand is a weekly cognitive load tax.
- **"Is this food safe and nutritious for each family member?"** — generic Google searches give contradictory nutrition advice without citations; recipe sites rarely surface allergen warnings; nutrition apps don't know your child has celiac.
- **"Can I trust the AI answer?"** — commodity LLM chatbots will happily fabricate DRI values, make curative medical claims, and get EU-14 allergen detection wrong.

## Why existing tools fall short

| Tool class | Gap |
|---|---|
| Generic LLM chatbots (ChatGPT, Claude, Gemini) | No citations, no allergen safety, prone to medical overreach, no persistent household context. |
| Recipe apps (Yummly, Paprika, Mealime) | Zero nutrition evidence, weak allergen filtering, no per-member personalization, no scientific grounding. |
| Nutrition apps (MyFitnessPal, Cronometer) | Tracking-only, no generative meal planning, no family-aware personalization. |
| Commercial "AI meal planner" sites | Opaque algorithms, no retrieval grounding, high false-positive allergen miss rate, no safety boundaries. |

## What this capstone demonstrates

A **retrieval-augmented agent** with explicit grounding, tiered evidence gates, medical-boundary guardrails, and agent-tool orchestration — applied to the nutrition & recipe domain. Specifically:

1. **Retrieval** — 5-collection corpus (operational recipes, evidence-tier nutrition, medical guidelines, experimental) with per-collection ranking strategies (relevance-first for recipes, relevance + authority for evidence, authority-boosted for medical). Demo ships 2 collections fully populated from public-domain sources; the other 3 live in production at [meal-map.app](https://meal-map.app).
2. **Evidence gate** — tiered confidence (`supported ≥ 0.3`, `fallback 0.1–0.3`, `refused < 0.1`) with authority-weighted adjustment.
3. **Safety** — medical-boundary validator catches 44 forbidden phrases (5 shipped in the demo sample) + 9 referral triggers (2 shipped). Never diagnoses. Never prescribes.
4. **Agent with 9 documented tools** — PydanticAI agent that composes retrieval, allergen-detection, nutrition-lookup, medical-boundary checks, and evidence gating.
5. **Evaluation** — LLM-as-Judge on 6 behavioral criteria + hand-crafted ground truth with hit@k / MRR / precision / recall.
6. **Monitoring** — JSONL logs + SQLite feedback DB + logs-to-GT pipeline that turns thumbs-up responses into new training data.

The **production UI** at [meal-map.app](https://meal-map.app) wraps this machine in a full family-planning loop: setup → plan → validate → shop → pantry → nutrition tracking. This repository ships the *AI engineering spine* under an AGPL-3.0 license as the capstone submission artifact.
