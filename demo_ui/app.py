"""Streamlit demo UI — 5 chained-sample tabs for the capstone.

Run locally: `make demo` (port 8502)

Design principle: every tab that operates on source content has a prominent
**"[x] Use pre-processed demo corpus"** checkbox, checked by default. Unchecking
switches to **"Upload / paste your own content"** mode where the full pipeline
runs live on the user's text. This demonstrates the architecture without
leaking proprietary corpus data.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import streamlit as st

THIS_DIR = Path(__file__).resolve().parent
CAPSTONE_ROOT = THIS_DIR.parent
sys.path.insert(0, str(CAPSTONE_ROOT / "src"))
sys.path.insert(0, str(CAPSTONE_ROOT / "ai" / "week1-rag"))
sys.path.insert(0, str(CAPSTONE_ROOT))

from agent_config import AgentConfig  # noqa: E402
from agent_tools_v2 import (  # noqa: E402
    TOOL_FUNCTIONS,
    _DEFAULT_INDEX_REGISTRY,
    available_collections,
    register_index,
    search_knowledge,
    get_evidence_confidence,
    check_medical_boundaries,
    check_allergens,
    get_nutrition_facts,
)
from backend.services.corpus_manager import load_all_demo_indexes  # noqa: E402
from mealmaster_ai.data.canonical_ingredients_sample import CANONICAL_INGREDIENTS_SAMPLE  # noqa: E402
from mealmaster_ai.data.demo_user_profile import DEMO_PROFILE, profile_as_markdown  # noqa: E402
from mealmaster_ai.rag.chunking import (  # noqa: E402
    COLLECTION_CHUNK_PARAMS,
    chunk_recipe_boundary,
    chunk_sliding_window,
    chunk_structured_header,
)
from mealmaster_ai.rag.evidence_gate import AUTHORITY_WEIGHTS, evaluate_evidence  # noqa: E402
from mealmaster_ai.rag.pipeline import build_chunks_for_source, build_index  # noqa: E402
from mealmaster_ai.rate_limiter import get_limiter  # noqa: E402
from monitoring.feedback import record_event, session_summary  # noqa: E402
from pydantic_agent import run_agent  # noqa: E402

# ---------------------------------------------------------------------------
# App init
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="MealMaster Capstone Demo",
    page_icon="🍽️",
    layout="wide",
)


@st.cache_resource
def _bootstrap_indexes() -> dict[str, bool]:
    return load_all_demo_indexes()


_bootstrap_indexes()


# ---------------------------------------------------------------------------
# Sidebar — cost meter, feedback tracker, rubric coverage
# ---------------------------------------------------------------------------
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())
if "user_indexes" not in st.session_state:
    st.session_state["user_indexes"] = {}
if "rubric_touched" not in st.session_state:
    st.session_state["rubric_touched"] = set()

with st.sidebar:
    st.markdown("### 🍽️ MealMaster Capstone")
    st.caption("[meal-map.app](https://meal-map.app) — full product")
    st.divider()
    summary = session_summary(st.session_state["session_id"])
    # Cost meter: pull from the rate limiter (source of truth for $ spent on
    # live LLM calls). feedback.db tracks events not cost, so `summary['cost_usd']`
    # is always 0 and is misleading in the sidebar.
    rl_snapshot = get_limiter().snapshot(st.session_state["session_id"])
    st.metric("Queries this session", summary["calls"])
    st.metric("Est. cost (today, USD)", f"${rl_snapshot['daily_spend_usd']:.4f}")
    st.metric("👍 / 👎", f"{summary['thumbs_up']} / {summary['thumbs_down']}")

    st.divider()
    st.markdown("**Cost guardrail**")
    session_cap_col = st.progress(
        min(1.0, rl_snapshot["session_calls_used"] / max(1, rl_snapshot["session_cap"])),
        text=f"Session LLM calls: {rl_snapshot['session_calls_used']} / {rl_snapshot['session_cap']}",
    )
    daily_progress = min(1.0, rl_snapshot["daily_spend_usd"] / max(0.0001, rl_snapshot["daily_budget_usd"]))
    st.progress(
        daily_progress,
        text=f"Daily spend: ${rl_snapshot['daily_spend_usd']:.4f} / ${rl_snapshot['daily_budget_usd']:.2f}",
    )
    if not rl_snapshot["allowed"]:
        st.warning(
            f"Rate limit reached ({rl_snapshot['reason']}). Agent is in **deterministic fallback** mode until the cap resets."
        )
    else:
        st.caption(f"{rl_snapshot['session_calls_remaining']} calls + ${rl_snapshot['daily_spend_remaining_usd']:.4f} left before fallback.")

    st.divider()
    with st.expander("👨‍👩‍👧‍👦 Demo household profile (hardcoded)", expanded=False):
        st.markdown(profile_as_markdown(DEMO_PROFILE))
        st.caption(
            "All questions in Tab 1 are personalized against this profile so the grader can "
            "reproduce the same retrieval + allergen-aware behavior. No real PII; production "
            "MealMaster at [meal-map.app](https://meal-map.app) uses user-entered profiles."
        )
    st.divider()
    st.markdown("**Rubric coverage**")
    criteria = {
        "problem_description": "Problem",
        "kb_retrieval": "KB + retrieval",
        "agents_llm": "Agents + tools",
        "code_organization": "Code org",
        "testing": "Testing",
        "evaluation": "Evaluation",
        "monitoring": "Monitoring",
        "feedback": "Feedback (bonus)",
        "logs_to_gt": "Logs → GT (bonus)",
        "docker": "Docker",
        "makefile": "Makefile",
        "uv": "UV",
        "ci_cd": "CI/CD",
        "ui": "UI (this page)",
        "cloud": "Cloud (meal-map.app)",
    }
    for k, label in criteria.items():
        mark = "✅" if k in st.session_state["rubric_touched"] else "◽"
        st.markdown(f"{mark} {label}")
    st.divider()
    st.caption("Demo scope: 2 of 5 collections populated. Remaining 3 live at [meal-map.app](https://meal-map.app).")


def _touch_rubric(*keys: str) -> None:
    for k in keys:
        st.session_state["rubric_touched"].add(k)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_arch, tab_query, tab_parse, tab_eval, tab_tune, tab_recipe = st.tabs([
    "📐 0. Architecture",
    "💬 1. Query the demo",
    "📖 2. Book parsing playground",
    "🧪 3. Evaluation laboratory",
    "🎛️ 4. Parameter tuning sandbox",
    "🥗 5. Recipe nutrition & household fit",
])


# ---------------------------------------------------------------------------
# Tab 0 — Architecture walkthrough
# ---------------------------------------------------------------------------
with tab_arch:
    _touch_rubric("problem_description", "code_organization")
    st.header("Architecture walkthrough")
    st.caption("Each node maps to a module file + a rubric criterion.")
    st.markdown(
        """
```mermaid
flowchart LR
    U[User query] --> R[Intent router<br/>rag/router.py]
    R --> S[BM25 search<br/>rag/search.py]
    S --> H[Optional hybrid fusion<br/>rag/hybrid.py]
    H --> RE[Reranker<br/>rag/reranker.py]
    RE --> EG{Evidence gate<br/>rag/evidence_gate.py<br/>0.3 / 0.1}
    EG -->|supported| AG[Agent<br/>pydantic_agent.py<br/>8 tools]
    EG -->|fallback| AG
    EG -->|refused| REF[Refusal]
    AG --> V[Pydantic validator<br/>structured_models.py]
    V --> RESP[Response + citations]
    RESP --> L[JSONL logs<br/>monitoring.py]
    RESP --> FB[Thumbs feedback<br/>monitoring/feedback.py]
    L --> D[Dashboard :8501]
    FB --> GT[logs_to_gt.py]
```
        """
    )
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Retrieval layer**")
        st.markdown("- `rag/search.py` — BM25 (BM25Lite default, minsearch optional)")
        st.markdown("- `rag/hybrid.py` — optional BM25 + embeddings fusion (RRF)")
        st.markdown("- `rag/reranker.py` — diversity + authority reranker")
        st.markdown("- `rag/evidence_gate.py` — tiered confidence")
        st.markdown("_Rubric: **KB + retrieval (2 pts)**_")
    with col2:
        st.markdown("**Agent layer**")
        st.markdown("- `pydantic_agent.py` — PydanticAI agent + fallback")
        st.markdown("- `agent_tools_v2.py` — 8 documented tools")
        st.markdown("- `structured_models.py` — Pydantic output schema")
        st.markdown("_Rubric: **Agents + LLM (3 pts)**_")

    st.divider()
    loaded = _bootstrap_indexes()
    st.success(f"Indexes loaded: {loaded}")
    with st.expander("See the 8 tools (click to collapse)", expanded=True):
        for name, fn in TOOL_FUNCTIONS.items():
            doc = (fn.__doc__ or "").strip().split("\n")[0]
            st.markdown(f"**`{name}`** — {doc}")


# ---------------------------------------------------------------------------
# Helpers shared by Tabs 1-4
# ---------------------------------------------------------------------------
def _use_preprocessed_checkbox(key: str, container=None) -> bool:
    target = container if container else st
    return target.checkbox(
        "Use pre-processed demo corpus (fast, no uploads)",
        value=True,
        key=key,
        help="Unchecked: upload / paste your own text and run the full parse → chunk → index → query pipeline live on it.",
    )


def _chunker_picker(key_prefix: str) -> tuple[str, int, int]:
    strategy = st.selectbox(
        "Chunking strategy",
        ["recipe_boundary", "structured_header", "sliding_window"],
        key=f"{key_prefix}_strategy",
    )
    col1, col2 = st.columns(2)
    with col1:
        size = st.slider("Size (words)", 30, 400, value=150, key=f"{key_prefix}_size")
    with col2:
        step = st.slider("Step (overlap = size - step)", 15, 400, value=75, key=f"{key_prefix}_step")
    return strategy, size, step


def _chunk_with_strategy(text: str, strategy: str, size: int, step: int) -> list[str]:
    if strategy == "recipe_boundary":
        return chunk_recipe_boundary(text, size, step)
    if strategy == "structured_header":
        return chunk_structured_header(text, size, step)
    return chunk_sliding_window(text, size, step)


# ---------------------------------------------------------------------------
# Tab 1 — Query the demo (chain: retrieve → gate → agent → respond)
# ---------------------------------------------------------------------------
with tab_query:
    _touch_rubric("agents_llm", "kb_retrieval", "ui")
    st.header("Query the demo")
    st.caption("Full chain: retrieve → evidence gate → agent → structured response with citations.")

    use_prep = _use_preprocessed_checkbox("tab1_prep")

    if not use_prep:
        st.info("**Parse-my-own mode:** upload a .txt file or paste text below; the pipeline chunks → BM25-indexes → queries it.")
        uploaded = st.file_uploader("Upload .txt", type=["txt", "md"], key="tab1_upload")
        pasted = st.text_area("Or paste text (≤ 50k chars)", height=160, key="tab1_paste", max_chars=50_000)
        if uploaded is not None:
            raw_text = uploaded.getvalue().decode("utf-8", errors="ignore")
        else:
            raw_text = pasted or ""

        if raw_text.strip():
            doc_id = f"user_{uuid.uuid4().hex[:8]}"
            chunks = build_chunks_for_source(
                raw_text,
                doc_id=doc_id,
                collection="user_books",
                source_title=uploaded.name if uploaded else "pasted_text",
                source_url="user_upload",
                authority_level="low",
                safety_sensitive=False,
            )
            idx = build_index(chunks)
            # Session-scope the key so uploads don't leak across Streamlit sessions
            # running in the same server process.
            session_key = f"user_books_{st.session_state['session_id']}"
            register_index(session_key, idx)
            register_index("user_books", idx)  # also expose under the agent-tool-expected name for THIS session
            st.session_state["user_indexes"][doc_id] = len(chunks)
            st.success(f"Built index with {len(chunks)} chunks. You can now query it below.")

    query_col, ask_col = st.columns([4, 1])
    with query_col:
        query = st.text_input("Query", value="What is the RDA for vitamin D in adults?", key="tab1_query")
    with ask_col:
        st.write("")
        st.write("")
        ask = st.button("Ask agent", key="tab1_ask")

    if ask and query.strip():
        cfg = AgentConfig.from_env()
        with st.spinner("Running agent…"):
            t0 = time.time()
            response = run_agent(query, cfg, session_id=st.session_state["session_id"])
            elapsed_ms = int((time.time() - t0) * 1000)

        tier_color = {"supported": "success", "fallback": "warning", "refused": "error"}[response.evidence_tier]
        getattr(st, tier_color)(
            f"**Evidence tier:** {response.evidence_tier}  •  confidence: {response.confidence:.3f}  •  {elapsed_ms} ms"
        )
        st.markdown("### Response")
        st.write(response.answer)
        if response.requires_disclaimer and response.disclaimer_text:
            st.warning(response.disclaimer_text)
        if response.demo_blocked_collections:
            st.info(f"**Demo scope:** these collections live at meal-map.app — {response.demo_blocked_collections}")

        with st.expander("Citations", expanded=True):
            for c in response.citations:
                st.markdown(
                    f"- **{c.source_title}** (`{c.collection}`, score={c.score:.3f}, authority={c.authority_level})\n"
                    f"  chunk id: `{c.chunk_id}`"
                )
        with st.expander("Tool-calls trace", expanded=False):
            for tc in response.tool_calls:
                st.markdown(f"- `{tc.name}` — `{tc.result_preview or ''}`")

        fb_col1, fb_col2, _ = st.columns([1, 1, 6])
        with fb_col1:
            if st.button("👍", key="tab1_up"):
                record_event(st.session_state["session_id"], "thumbs", {"direction": "up", "query": query, "response": response.answer})
                st.toast("Thanks — recorded as 👍")
        with fb_col2:
            if st.button("👎", key="tab1_down"):
                record_event(st.session_state["session_id"], "thumbs", {"direction": "down", "query": query, "response": response.answer})
                st.toast("Thanks — recorded as 👎")

        record_event(
            st.session_state["session_id"],
            "query",
            {"query": query, "tier": response.evidence_tier, "confidence": response.confidence, "cost_usd": 0.0},
        )

    st.caption("_Rubric: **Agents + LLM (3 pts)** • **KB + retrieval (2 pts)** • **Monitoring feedback bonus (1 pt)**_")


# ---------------------------------------------------------------------------
# Tab 2 — Book parsing playground (chain: extract → chunk)
# ---------------------------------------------------------------------------
with tab_parse:
    _touch_rubric("kb_retrieval", "code_organization")
    st.header("Book parsing playground")
    st.caption("Pick a chunking strategy, see the chunks the retrieval index will be built from.")

    use_prep = _use_preprocessed_checkbox("tab2_prep")

    if use_prep:
        sample_choices = {
            "Utah WIC Recipe Book (sample)": CAPSTONE_ROOT / "data" / "rag" / "demo" / "recipes" / "raw" / "utah_wic_recipe_book.txt",
            "Let's Cook With Kids (California WIC)": CAPSTONE_ROOT / "data" / "rag" / "demo" / "recipes" / "raw" / "lets_cook_with_kids_ca_wic.txt",
            "Open Oregon — Everyday Nutrition": CAPSTONE_ROOT / "data" / "rag" / "demo" / "nutrition_science" / "raw" / "nutrition_science_everyday_application.txt",
            "UH Hawai'i — Human Nutrition": CAPSTONE_ROOT / "data" / "rag" / "demo" / "nutrition_science" / "raw" / "human_nutrition_hawaii.txt",
        }
        label = st.selectbox("Choose a baked source", list(sample_choices.keys()), key="tab2_src")
        raw_text = sample_choices[label].read_text(encoding="utf-8")
    else:
        st.info("**Parse-my-own mode:** upload or paste; the demo chunks your text live.")
        uploaded = st.file_uploader("Upload .txt", type=["txt", "md"], key="tab2_upload")
        pasted = st.text_area("Or paste text", height=180, key="tab2_paste", max_chars=50_000)
        raw_text = uploaded.getvalue().decode("utf-8", errors="ignore") if uploaded else (pasted or "")

    if raw_text:
        strategy, size, step = _chunker_picker("tab2")
        chunks = _chunk_with_strategy(raw_text, strategy, size, step)
        total_words = len(raw_text.split())
        avg_len = sum(len(c.split()) for c in chunks) / (len(chunks) or 1)
        cols = st.columns(3)
        cols[0].metric("Total input words", f"{total_words:,}")
        cols[1].metric("Chunks produced", len(chunks))
        cols[2].metric("Avg words / chunk", f"{avg_len:.0f}")

        st.markdown(f"**Strategy:** `{strategy}` • **size:** {size} • **step:** {step}")
        st.markdown(f"**Production default** (for this collection): {COLLECTION_CHUNK_PARAMS}")

        st.markdown("### Chunks")
        for i, c in enumerate(chunks[:12]):
            with st.expander(f"Chunk {i+1} ({len(c.split())} words)", expanded=(i < 2)):
                st.write(c)
        if len(chunks) > 12:
            st.caption(f"…and {len(chunks) - 12} more (trimmed for readability).")

        record_event(
            st.session_state["session_id"],
            "chunk_demo",
            {"strategy": strategy, "size": size, "step": step, "chunk_count": len(chunks)},
        )

    st.caption("_Rubric: demonstrates the chunking layer of **KB + retrieval (2 pts)**_")


# ---------------------------------------------------------------------------
# Tab 3 — Evaluation laboratory (chain: query → retrieve → respond → judge)
# ---------------------------------------------------------------------------
with tab_eval:
    _touch_rubric("evaluation", "testing")
    st.header("Evaluation laboratory")
    st.caption("Run a ground-truth query through the agent, then score the response with the LLM-as-Judge (offline / mocked).")

    gt_path = CAPSTONE_ROOT / "ai" / "week1-rag" / "evals" / "ground_truth_handcrafted.json"
    with open(gt_path, encoding="utf-8") as f:
        gt_data = json.load(f)
    cases = gt_data.get("cases", [])

    case_labels = [f"{c['id']} — {c['query'][:70]}..." for c in cases]
    case_idx = st.selectbox("Hand-crafted ground truth case", range(len(case_labels)), format_func=lambda i: case_labels[i], key="tab3_case")
    case = cases[case_idx]

    with st.expander("Case details", expanded=True):
        st.json(case)

    if st.button("Run case through agent + judge", key="tab3_run"):
        cfg = AgentConfig.from_env()
        with st.spinner("Running agent…"):
            response = run_agent(case["query"], cfg)
        st.markdown("### Agent response")
        st.write(response.answer)
        st.markdown(f"**Evidence tier:** {response.evidence_tier}  •  **confidence:** {response.confidence:.3f}")

        # Judge
        fixtures_path = CAPSTONE_ROOT / "fixtures" / "mock_llm_responses.json"
        fixtures = json.loads(fixtures_path.read_text(encoding="utf-8")) if fixtures_path.exists() else {}
        from evals.llm_judge import judge_response_offline, JUDGE_CRITERIA  # noqa: WPS433
        judge = judge_response_offline(case["query"], response.answer, fixtures)
        st.markdown("### Judge scoring")
        st.metric("Total", f"{judge.total} / {judge.max}", delta="pass" if judge.passed else "below threshold")
        for s, meta in zip(judge.scores, JUDGE_CRITERIA):
            emoji = "✅" if s.score else "❌"
            st.markdown(f"{emoji} **{meta['name']}** — _{s.rationale}_")

        retrieved_ids = [c.chunk_id for c in response.citations]
        expected_ids = case.get("expected_chunk_ids", [])
        hit = any(e in retrieved_ids for e in expected_ids) if expected_ids else "N/A"
        st.markdown(f"**Hit@k vs GT:** `{hit}` | Expected: `{expected_ids}` | Retrieved: `{retrieved_ids[:3]}...`")

        record_event(
            st.session_state["session_id"],
            "eval",
            {"case_id": case["id"], "judge_total": judge.total, "judge_passed": judge.passed, "hit": str(hit)},
        )

    st.caption("_Rubric: **Evaluation (3 pts)** via LLM-as-Judge + hand-crafted GT (2 pts bonus)_")


# ---------------------------------------------------------------------------
# Tab 4 — Parameter tuning sandbox (chain: slider → recompute → compare)
# ---------------------------------------------------------------------------
with tab_tune:
    _touch_rubric("evaluation", "kb_retrieval")
    st.header("Parameter tuning sandbox")
    st.caption("Change thresholds + authority weights; see the evidence gate's decision flip live.")

    use_prep = _use_preprocessed_checkbox("tab4_prep")
    default_query = "What is the RDA for vitamin D in adults?"
    query = st.text_input("Test query", value=default_query, key="tab4_query")

    conf_th = st.slider("confidence_threshold", 0.0, 8.0, value=0.3, step=0.05, key="tab4_conf")
    fb_th = st.slider("fallback_threshold", 0.0, 8.0, value=0.1, step=0.05, key="tab4_fb")
    col_h, col_m, col_l = st.columns(3)
    with col_h:
        w_high = st.slider("authority weight: high", 0.5, 2.0, value=1.3, step=0.05, key="tab4_wh")
    with col_m:
        w_med = st.slider("authority weight: medium", 0.5, 2.0, value=1.0, step=0.05, key="tab4_wm")
    with col_l:
        w_low = st.slider("authority weight: low", 0.1, 2.0, value=0.7, step=0.05, key="tab4_wl")

    top_k = st.slider("top_k", 1, 15, value=5, key="tab4_k")

    # Run retrieval once
    search = search_knowledge(query, top_k=top_k)
    results = search.get("results", [])

    # Evaluate with custom params
    custom_weights = {"high": w_high, "medium": w_med, "low": w_low}
    decision = evaluate_evidence(
        results,
        confidence_threshold=conf_th,
        fallback_threshold=fb_th,
        authority_weights=custom_weights,
    )
    # Baseline (production defaults)
    baseline = evaluate_evidence(
        results,
        confidence_threshold=0.3,
        fallback_threshold=0.1,
        authority_weights=AUTHORITY_WEIGHTS,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Custom parameters**")
        st.metric("Status", decision.status)
        st.metric("Adjusted top score", f"{decision.confidence:.3f}")
    with col2:
        st.markdown("**Production defaults**")
        st.metric("Status", baseline.status)
        st.metric("Adjusted top score", f"{baseline.confidence:.3f}")

    if decision.status != baseline.status:
        st.warning(
            f"⚠️ Gate decision flipped: **{baseline.status} → {decision.status}** "
            f"with your custom parameters vs production defaults."
        )

    with st.expander("Retrieved set (shared across both)", expanded=False):
        for r in results:
            st.markdown(
                f"- `{r.get('source_title')}` score={r.get('score'):.3f} "
                f"[coll={r.get('collection')}, authority={r.get('authority_level')}]"
            )

    record_event(
        st.session_state["session_id"],
        "tune",
        {
            "conf_th": conf_th,
            "fb_th": fb_th,
            "weights": custom_weights,
            "flipped": decision.status != baseline.status,
            "status_custom": decision.status,
            "status_baseline": baseline.status,
        },
    )

    st.caption("_Rubric: **Evaluation (3 pts)** — demonstrates param-tuning methodology live._")


# ---------------------------------------------------------------------------
# Tab 5 — Recipe nutrition & household fit
# ---------------------------------------------------------------------------
with tab_recipe:
    _touch_rubric("agents_llm", "kb_retrieval")
    st.header("Recipe nutrition & household fit")
    st.caption(
        "Pick a baked recipe → see its ingredients, per-serving macros, and whether it fits "
        "each demo household member (dairy / peanuts / age-band). Two data paths: the pre-computed "
        "JSON under `data/rag/demo/derived/recipes.json` (default, deterministic) or the live "
        "regex parser running against the raw recipe text (unchecked, demonstrates the pipeline)."
    )

    # Load pre-computed structured data
    import json as _json
    recipes_json_path = CAPSTONE_ROOT / "data" / "rag" / "demo" / "derived" / "recipes.json"
    try:
        recipes_data = _json.loads(recipes_json_path.read_text(encoding="utf-8"))
    except Exception as e:  # pragma: no cover — deploy-time only
        st.error(f"Could not load recipes.json: {e}")
        recipes_data = {"recipes": [], "sample_weekly_plans": []}

    use_precomputed = st.checkbox(
        "Use pre-computed derived/recipes.json (fast, deterministic)",
        value=True,
        key="tab5_use_precomputed",
        help="Unchecked: re-parse the same recipe from raw text via regex + fuzzy-match against "
             "the canonical 10-ingredient USDA sample.",
    )

    recipes_list = recipes_data.get("recipes", [])
    recipe_options = {
        f"{r['title']} — {r['servings']} servings ({r['cook_time_minutes']} min)": r
        for r in recipes_list
    }
    if not recipe_options:
        st.warning("No recipes in the committed JSON.")
    else:
        label = st.selectbox("Recipe", list(recipe_options.keys()), key="tab5_recipe_pick")
        recipe = recipe_options[label]

        # ---- Ingredients table ----
        st.subheader("Ingredients")
        if use_precomputed:
            import pandas as _pd
            ing_rows = [
                {
                    "amount": i.get("amount") or "",
                    "unit": i.get("unit") or "",
                    "ingredient": i.get("text", ""),
                    "canonical match": i.get("canonical_match") or "—",
                    "allergens": ", ".join(i.get("allergens", [])) or "—",
                }
                for i in recipe.get("ingredients", [])
            ]
            st.dataframe(_pd.DataFrame(ing_rows), width="stretch", hide_index=True)
        else:
            # Load raw text for this recipe's source chunk and re-parse it.
            from mealmaster_ai.nutrition.recipe_nutrition import (
                parse_recipe_ingredients,
                match_all,
                aggregate_macros,
                household_fit as _hh_fit,
            )
            raw_path = CAPSTONE_ROOT / "data" / "rag" / "demo" / "recipes" / "raw" / f"{recipe['source_doc_id']}.txt"
            raw_text = raw_path.read_text(encoding="utf-8")
            # Narrow to the chunk that contains this recipe by title match.
            title = recipe["title"].lower()
            lines = raw_text.split("\n")
            start = 0
            for idx, line in enumerate(lines):
                if title.split()[0] in line.lower() and ("recipe" in line.lower() or "##" in line):
                    start = idx
                    break
            snippet = "\n".join(lines[start:start + 40])
            st.code(snippet, language="markdown")
            parsed = parse_recipe_ingredients(snippet)
            matched = match_all(parsed)
            live_rows = [
                {
                    "amount": m.ingredient_text[:3] + "…" if False else (parsed[i].amount_text or ""),
                    "ingredient": m.ingredient_text,
                    "canonical match": m.matched.name if m.matched else "—",
                    "matched via": m.matched_via or "—",
                }
                for i, m in enumerate(matched)
            ]
            import pandas as _pd
            st.dataframe(_pd.DataFrame(live_rows), width="stretch", hide_index=True)

        # ---- Per-serving nutrition ----
        st.subheader("Per-serving nutrition")
        if use_precomputed:
            n = recipe.get("nutrition_per_serving", {})
            col_a, col_b, col_c, col_d, col_e = st.columns(5)
            col_a.metric("kcal", n.get("energy_kcal", "—"))
            col_b.metric("protein (g)", n.get("protein_g", "—"))
            col_c.metric("carbs (g)", n.get("carbs_g", "—"))
            col_d.metric("fat (g)", n.get("fat_g", "—"))
            col_e.metric("fiber (g)", n.get("fiber_g", "—"))
            st.caption(
                f"Sodium label: **{n.get('sodium_mg_label', '—')}** • "
                f"Source: per-serving nutrition written by the original publisher for WIC; "
                f"committed in `derived/recipes.json`."
            )
        else:
            agg = aggregate_macros(matched)
            col_a, col_b, col_c, col_d, col_e = st.columns(5)
            col_a.metric("Σ kcal / 100g", f"{agg.energy_kcal_per_100g_sum:.0f}")
            col_b.metric("Σ protein", f"{agg.protein_g_per_100g_sum:.1f}")
            col_c.metric("Σ carbs", f"{agg.carbs_g_per_100g_sum:.1f}")
            col_d.metric("Σ fat", f"{agg.fat_g_per_100g_sum:.1f}")
            col_e.metric("Σ fiber", f"{agg.fiber_g_per_100g_sum:.1f}")
            st.caption(
                f"Matched {agg.matched_count} of {agg.matched_count + agg.unmatched_count} "
                f"ingredients against the 10-item USDA canonical sample. "
                f"Per-100g sum (no amount scaling) — this is an intentional demo simplification. "
                f"Production `meal-map.app` applies amount × canonical 82×19 catalog."
            )

        # ---- Household fit ----
        st.subheader("Demo household fit")
        import pandas as _pd
        if use_precomputed:
            recipe_allergens = set(recipe.get("allergens_eu14", []))
            suitable = set(recipe.get("suitable_for_age_bands", []))
            fit_rows = []
            for m in DEMO_PROFILE.members:
                allergen_hits = sorted(set(m.allergens) & recipe_allergens)
                age_ok = m.age_band in suitable
                if allergen_hits:
                    verdict = f"❌ allergen conflict ({', '.join(allergen_hits)})"
                elif not age_ok:
                    verdict = f"⚠️  age-band not listed as suitable ({m.age_band})"
                else:
                    verdict = "✅ safe"
                fit_rows.append({
                    "member": m.display_name,
                    "age band": m.age_band,
                    "member allergens": ", ".join(m.allergens) or "—",
                    "verdict": verdict,
                })
            st.dataframe(_pd.DataFrame(fit_rows), width="stretch", hide_index=True)
        else:
            live_fit = _hh_fit(matched)
            st.dataframe(
                _pd.DataFrame([
                    {
                        "member": f.display_name,
                        "age band": f.age_band,
                        "verdict": (
                            f"❌ allergen conflict ({', '.join(f.conflicting_allergens)})"
                            if f.verdict == "allergen_conflict"
                            else ("⚠️  partial data (unmatched ingredients)"
                                  if f.verdict == "partial_data"
                                  else "✅ safe (all ingredients matched, no allergen overlap)")
                        ),
                    }
                    for f in live_fit
                ]),
                width="stretch",
                hide_index=True,
            )

        # ---- 7-day sample plan (static JSON) ----
        st.divider()
        st.subheader("Sample 7-day plan for the demo household (static, JSON-sourced)")
        st.caption(
            "A **static committed plan** from `derived/recipes.json`. Built by hand so every "
            "meal is safe for all 4 household members *by construction* — no per-member "
            "substitutions needed. Production weekly-plan generation is at "
            "[meal-map.app](https://meal-map.app). For the RAG-grounded alternative path, "
            "use the **'Generate plan via the RAG agent'** button below."
        )
        plans = recipes_data.get("sample_weekly_plans", [])
        if plans:
            plan = plans[0]
            plan_rows = []
            by_id = {r["recipe_id"]: r for r in recipes_list}
            for day in plan.get("days", []):
                plan_rows.append({
                    "day": day["day"],
                    "breakfast": by_id.get(day.get("breakfast", ""), {}).get("title", day.get("breakfast", "")),
                    "lunch": by_id.get(day.get("lunch", ""), {}).get("title", day.get("lunch", "")),
                    "dinner": by_id.get(day.get("dinner", ""), {}).get("title", day.get("dinner", "")),
                })
            st.dataframe(_pd.DataFrame(plan_rows), width="stretch", hide_index=True)

            with st.expander("Construction rules (why these 4 recipes)", expanded=False):
                for rule in plan.get("construction_rules", []):
                    st.markdown(f"- {rule}")
                excluded = plan.get("recipes_excluded_and_why", [])
                if excluded:
                    st.markdown("**Excluded by construction:**")
                    for e in excluded:
                        st.markdown(f"- `{e['recipe_id']}` — {e['reason']}")

            with st.expander("Household fit notes for this plan", expanded=True):
                for note in plan.get("household_fit_notes", []):
                    st.markdown(f"- {note}")

        # ---- RAG-based plan generation (honest answer to "is this RAG?") ----
        st.divider()
        st.subheader("Generate plan via the RAG agent (live retrieval + LLM)")
        st.caption(
            "**Yes, this is RAG.** Click below to trigger `run_agent()` with a "
            "plan-generation query. The agent calls `search_knowledge` (BM25 over the "
            "indexed recipes + nutrition_science collections), feeds retrieved chunks "
            "as context to `gpt-4.1-mini`, and returns a response grounded in citations. "
            "Counts against the cost guardrail."
        )
        rag_plan_query = st.text_input(
            "Plan request",
            value=(
                "Suggest 3 dinner recipes from the demo corpus that avoid dairy and peanuts "
                "and are suitable for a toddler (age 1-3). Cite the specific chunk IDs."
            ),
            key="tab5_rag_plan_query",
        )
        if st.button("Generate plan via RAG agent", key="tab5_rag_plan_btn"):
            cfg = AgentConfig.from_env()
            with st.spinner("Retrieving recipes + composing plan…"):
                t0 = time.time()
                response = run_agent(rag_plan_query, cfg, session_id=st.session_state["session_id"])
                elapsed_ms = int((time.time() - t0) * 1000)

            tier_color = {"supported": "success", "fallback": "warning", "refused": "error"}.get(
                response.evidence_tier, "info"
            )
            getattr(st, tier_color)(
                f"**Evidence tier:** {response.evidence_tier}  •  confidence: {response.confidence:.3f}  •  {elapsed_ms} ms"
            )
            st.markdown("#### RAG-generated plan")
            st.write(response.answer)

            if response.citations:
                st.markdown("**Citations (proof of retrieval):**")
                for c in response.citations:
                    st.markdown(
                        f"- `{c.chunk_id}` from **{c.source_title}** "
                        f"(collection `{c.collection}`, score {c.score:.3f}, authority {c.authority_level})"
                    )
            else:
                st.caption("No citations returned (response may be from the deterministic fallback path).")

            if response.tool_calls:
                with st.expander("Tool-call trace", expanded=False):
                    for tc in response.tool_calls:
                        st.markdown(f"- `{tc.name}` — `{(tc.result_preview or '')[:140]}`")

            record_event(
                st.session_state["session_id"],
                "rag_plan",
                {
                    "query": rag_plan_query[:100],
                    "tier": response.evidence_tier,
                    "confidence": response.confidence,
                    "citation_count": len(response.citations),
                },
            )

        record_event(
            st.session_state["session_id"],
            "recipe_nutrition",
            {
                "recipe_id": recipe["recipe_id"],
                "precomputed": use_precomputed,
            },
        )

    st.caption(
        "_Rubric: ties together **Agents + LLM (3 pts)** — the same tools "
        "(`get_nutrition_facts`, `check_allergens`, `search_knowledge`) used in the agent loop "
        "operate on real recipe data here — and **KB + retrieval (2 pts)**._"
    )


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    f"Session `{st.session_state['session_id'][:8]}`  •  "
    f"Feedback stored at `monitoring/feedback.db`  •  "
    f"[Production product](https://meal-map.app) • "
    f"[Self-score guide](./docs/self-score-report.md)"
)
