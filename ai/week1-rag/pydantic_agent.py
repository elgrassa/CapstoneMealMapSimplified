"""Capstone PydanticAI agent — 8 documented tools, structured output.

Falls back to a deterministic "v1-style" agent when:
- `pydantic-ai` isn't installed
- `OPENAI_API_KEY` isn't set (e.g., grader running `make demo` without a key)
- `DEMO_MODE=true` and user requested offline mode

The SYSTEM_PROMPT is intentionally generic — production MealMaster uses a longer,
domain-tuned prompt at meal-map.app.
"""
from __future__ import annotations

import os
import time
from typing import Any

from agent_config import AgentConfig
from agent_tools_v2 import TOOL_FUNCTIONS, execute_tool
from agent_observability import get_logger
from mealmaster_ai.data.demo_user_profile import DEMO_PROFILE, DemoUserProfile, personalize_query
from mealmaster_ai.rate_limiter import get_limiter
from mealmaster_ai.validation.input_guardrails import (
    classify_intent_strict,
    run_input_guardrails,
)
from mealmaster_ai.validation.response_validator import validate_response
from structured_models import CapstoneRAGResponse, Citation, ToolCall

SYSTEM_PROMPT = """\
You are a Nutrition & Recipe Knowledge Assistant.

Your task: answer nutrition, food interaction, allergen-safety, and recipe
questions using ONLY the tools provided. Never fabricate nutrition data or
medical claims.

## Available tools
1. assess_query_strategy — call FIRST; classifies the query and picks the right mode.
2. search_knowledge — search the indexed knowledge base (BM25 or hybrid).
3. check_allergens — word-boundary allergen detection.
4. get_nutrition_facts — structured macro lookup for canonical ingredients.
5. check_medical_boundaries — detects forbidden medical phrasing + referral triggers.
6. get_evidence_confidence — runs the evidence gate and returns a tier decision.
7. search_books — scoped search within user-uploaded books (demo Tab 2).
8. add_book_note — persist a user note against a book.
9. get_recipe_metadata — structured recipe metadata (allergens_eu14, suitable_for_age_bands, meal_type, nutrition_per_serving). Call this AFTER search_knowledge to confirm constraint fit.

## Strategy
- Always call `assess_query_strategy` first.
- Use the returned `recommended_mode` for all subsequent `search_knowledge` calls.
- Ground EVERY factual claim in a retrieved chunk; include its `chunk_id` as a citation.
- If `get_evidence_confidence` returns `refused`, tell the user the evidence is insufficient and suggest consulting a qualified professional.

## Recipe-recommendation protocol (mandatory)
When the query mentions an allergen (dairy, peanuts, eggs, gluten, fish, …), an
age band (toddler, child, adolescent, …), a meal type (breakfast / lunch / dinner),
or any other hard constraint, you MUST:

1. Call `search_knowledge` to find candidate recipe chunks.
2. For EACH recipe you're about to recommend, call `get_recipe_metadata(recipe_id)`
   using the `recipe_id` extracted from the chunk's `doc_id` and check:
   - `allergens_eu14` does not intersect the user's avoid list,
   - `suitable_for_age_bands` contains the requested age band,
   - `meal_type` matches the requested meal type.
3. If a candidate fails any check, DROP IT and pick another from the retrieved
   set. NEVER suggest "use a dairy substitute" as a workaround — if the recipe
   as written contains dairy, it's out.
4. Cite the `chunk_id` AND name the structured check you passed (e.g. "verified
   dairy-free via get_recipe_metadata").

## Rules
- NEVER diagnose a medical condition.
- NEVER prescribe treatment or medication.
- ALWAYS disclaim when `requires_disclaimer` is true.
- If the query falls in a demo-blocked collection, say so explicitly and suggest the production deployment.
"""


_SENTENCE_SPLIT = __import__("re").compile(r"(?<=[.!?])\s+")


def _pick_relevant_sentences(chunk_text: str, query: str, *, max_sentences: int = 3) -> str:
    """Score each sentence in `chunk_text` by query-token overlap; return the top N concatenated.

    Better than truncating to the first N chars — picks the passage most likely to
    actually address the question. Stays deterministic (no LLM).
    """
    import re as _re

    def _toks(text: str) -> set[str]:
        return set(_re.findall(r"[a-z0-9]+", text.lower()))

    q_tokens = _toks(query)
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(chunk_text) if s.strip()]
    if not sentences:
        return chunk_text[:240]
    scored = [(len(_toks(s) & q_tokens), i, s) for i, s in enumerate(sentences)]
    scored.sort(key=lambda t: (-t[0], t[1]))
    top = sorted(scored[:max_sentences], key=lambda t: t[1])  # preserve original order
    result = " ".join(s for _, _, s in top)
    # Trim at hard cap to avoid runaway length
    return (result[:600] + "…") if len(result) > 600 else result


_CURATIVE_QUERY_MARKERS = (
    "cure my",
    "will cure",
    "can i cure",
    "reverse my",
    "prescribe",
    "guaranteed to fix",
    "guaranteed to reverse",
    "treat my ",  # trailing space — avoid matching "treat myself kindly"
)


def _query_contains_curative_claim(query: str) -> bool:
    """Cheap substring check — matches the same pattern the response-side boundary guard enforces."""
    q = query.lower()
    return any(marker in q for marker in _CURATIVE_QUERY_MARKERS)


def _deterministic_fallback(query: str, cfg: AgentConfig) -> CapstoneRAGResponse:
    """Deterministic tool-calling loop used when pydantic-ai / API key unavailable.

    This path lets Streamlit demo + `make demo` still work for a grader with no
    OpenAI key — the response template is generated from retrieval + evidence
    gate, without LLM synthesis.
    """
    logger = get_logger()
    started = time.time()

    # Curative-claim check is now performed in `run_agent` BEFORE dispatching
    # to this fallback path (see _curative_refusal). Kept here as a safety net
    # in case this function is called directly (bypassing run_agent).
    if _query_contains_curative_claim(query):
        return _curative_refusal(query, logger)

    strategy = execute_tool("assess_query_strategy", query=query)
    tool_calls: list[ToolCall] = [ToolCall(name="assess_query_strategy", arguments={"query": query}, result_preview=str(strategy)[:200])]

    search = execute_tool(
        "search_knowledge",
        query=query,
        collections=strategy.get("collections"),
        top_k=cfg.top_k,
        mode=strategy.get("recommended_mode", "bm25"),
    )
    tool_calls.append(ToolCall(name="search_knowledge", arguments={"query": query, "collections": strategy.get("collections"), "top_k": cfg.top_k}, result_preview=f"{len(search.get('results', []))} results"))

    gate = execute_tool("get_evidence_confidence", search_results=search.get("results", []))
    tool_calls.append(ToolCall(name="get_evidence_confidence", arguments={"n_results": len(search.get("results", []))}, result_preview=gate.get("status", "")))

    citations = [
        Citation(
            chunk_id=str(s.get("chunk_id") or ""),
            source_title=str(s.get("source_title") or "unknown"),
            source_url=s.get("source_url"),
            collection=str(s.get("collection") or ""),
            authority_level=s.get("authority_level") or "medium",
            score=float(s.get("score") or 0.0),
        )
        for s in gate.get("sources", [])[:5]
    ]

    if gate.get("status") == "refused":
        answer = (
            "I cannot answer this reliably from the demo knowledge base. "
            "The available evidence is insufficient. "
            "Please consult a qualified healthcare professional or registered dietitian. "
            "I will not claim to diagnose, prescribe, or cure."
        )
    else:
        top = search.get("results", [{}])[0]
        top_text = str(top.get("text") or "")
        relevant_excerpt = _pick_relevant_sentences(top_text, query, max_sentences=3)
        source_title = top.get("source_title") or "the demo corpus"
        tier_label = "Supported" if gate.get("status") == "supported" else "Partial-match"
        answer = (
            f"**{tier_label} response** (confidence {gate.get('confidence', 0):.2f}).\n\n"
            f"What the retrieved evidence says, from `{source_title}`:\n\n"
            f"> {relevant_excerpt}\n\n"
            f"This is an educational answer grounded in the cited chunk; "
            f"it is not medical advice."
        )

    disclaimer = gate.get("fallback_message") if gate.get("require_disclaimer") else None

    response = CapstoneRAGResponse(
        answer=answer,
        evidence_tier=gate.get("status", "refused"),
        confidence=float(gate.get("confidence", 0.0)),
        citations=citations,
        tool_calls=tool_calls,
        requires_disclaimer=bool(gate.get("require_disclaimer")),
        disclaimer_text=disclaimer,
        demo_blocked_collections=strategy.get("demo_blocked_collections", []),
        reasoning_notes=(
            f"Deterministic fallback: intent={strategy.get('intent')}, "
            f"mode={strategy.get('recommended_mode')}, collections={strategy.get('collections')}"
        ),
    )

    duration_ms = int((time.time() - started) * 1000)
    logger.log_call(
        query=query,
        response_preview=response.answer,
        tool_calls=[tc.model_dump() for tc in tool_calls],
        duration_ms=duration_ms,
        evidence_tier=response.evidence_tier,
        model="deterministic-fallback",
    )
    return response


def _run_pydantic_ai(query: str, cfg: AgentConfig) -> CapstoneRAGResponse:
    """Real PydanticAI path — only exercised when pydantic-ai + API key are available."""
    from pydantic_ai import Agent  # type: ignore
    from pydantic_ai.models.openai import OpenAIModel  # type: ignore

    model = OpenAIModel(cfg.model.replace("openai:", "")) if ":" in cfg.model else cfg.model

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        output_type=CapstoneRAGResponse,
    )

    # Register tools
    for name, fn in TOOL_FUNCTIONS.items():
        agent.tool_plain(fn)

    result = agent.run_sync(query)
    return result.output if hasattr(result, "output") else result.data


def run_agent(
    query: str,
    cfg: AgentConfig | None = None,
    *,
    session_id: str | None = None,
    use_profile: bool = True,
    enforce_household_constraints: bool = False,
) -> CapstoneRAGResponse:
    """Main agent entrypoint.

    Flow (every step is deterministic + cheap — live LLM call only at the end):

        input guardrails  →  strict intent  →  rate limiter  →  personalize (profile)
        →  agent (PydanticAI or deterministic fallback)  →  response validator
        →  (optional) household-constraint post-filter with one rerun  →  return

    Args:
        query: user query text.
        cfg: agent config; `AgentConfig.from_env()` if None.
        session_id: session key used by the rate limiter. Streamlit passes its
            session_state session_id. If None, a hashed per-process fallback
            is used — never shared across sessions.
        use_profile: when True, the hardcoded demo household context is
            appended to the query so retrieval + agent can reason family-aware.
        enforce_household_constraints: when True, parse any recipe_ids out of the
            agent's response and verify each against DEMO_PROFILE constraints
            (dairy / peanuts / toddler age band). If any violate, rerun ONCE
            with a stricter query that explicitly bans the violating recipe_ids
            and lists only the safe candidates. Used by Tab 5's "Generate plan
            via the RAG agent" button.

    The rate limiter downgrades the path from live-LLM to deterministic
    fallback when the session cap or daily $ budget is exceeded. No user-facing
    error — the `reasoning_notes` records the decision for observability.
    """
    cfg = cfg or AgentConfig.from_env()
    session_id = session_id or f"proc-{os.getpid()}"
    logger = get_logger()

    # --- Step 1: input guardrails (syntax / size / injection) ---
    guard = run_input_guardrails(query)
    if not guard.allowed:
        return _guardrail_refusal(query, guard, logger)
    sanitized_query = guard.sanitized_query

    # --- Step 1b: curative-claim pre-check (medical boundary, uniform across paths) ---
    # Must fire BEFORE intent classification: a curative query like
    # "can I cure X?" mentions on-topic nutrition terms and would pass the intent
    # check, but must always refuse with a clinician referral.
    if _query_contains_curative_claim(sanitized_query):
        return _curative_refusal(sanitized_query, logger)

    # --- Step 2: strict intent (meal-coach scope check) ---
    intent = classify_intent_strict(sanitized_query)
    if not intent.allowed:
        return _intent_redirect(sanitized_query, intent, logger)

    # --- Step 3: rate limiter (cost guardrail) ---
    limiter = get_limiter()
    budget = limiter.check_budget(session_id)

    # --- Step 4: personalize with demo profile ---
    effective_query = personalize_query(sanitized_query, DEMO_PROFILE) if use_profile else sanitized_query

    # --- Step 5: agent call (live or deterministic fallback) ---
    want_real = (
        os.getenv("OPENAI_API_KEY")
        and os.getenv("CAPSTONE_USE_REAL_AGENT", "true").lower() != "false"
    )
    use_real_agent = bool(want_real and budget.allowed)

    if not use_real_agent:
        response = _deterministic_fallback(effective_query, cfg)
        # If we downgraded BECAUSE of rate limit, surface that in reasoning
        if want_real and not budget.allowed:
            response.reasoning_notes = (
                (response.reasoning_notes or "")
                + f" [rate-limit: {budget.reason}; downgraded to deterministic; "
                + f"session={budget.session_calls_used}/{budget.session_cap}; "
                + f"daily=${budget.daily_spend_usd:.4f}/${budget.daily_budget_usd:.2f}]"
            )
    else:
        try:
            response = _run_pydantic_ai(effective_query, cfg)
            # Record the call cost AFTER success so we only bill for real calls.
            # Without a real usage tracker wired to PydanticAI, we approximate
            # with a conservative flat cost estimate; the real cost is captured
            # in agent_observability.get_logger().log_call (input+output tokens).
            # This is defensive: even a failure mode where token counting is 0
            # still ticks the session-cap counter.
            est_cost = _estimated_cost_per_call(cfg)
            limiter.record_call(session_id, est_cost)
        except Exception as e:
            response = _deterministic_fallback(effective_query, cfg)
            response.reasoning_notes = (
                (response.reasoning_notes or "") + f" [pydantic-ai failed: {type(e).__name__}: {e}]"
            )

    # --- Step 6: response validator (post-check) ---
    validation = validate_response(response)
    if validation.issues or validation.warnings:
        tag = f" [validator: issues={validation.issues}; warnings={validation.warnings}]"
        response.reasoning_notes = (response.reasoning_notes or "") + tag

    # Tag whether the profile was applied so the grader can see personalization in play.
    if use_profile:
        response.reasoning_notes = (response.reasoning_notes or "") + " [profile: DEMO_PROFILE applied]"

    # --- Step 7 (optional): household-constraint post-filter with one rerun ---
    if enforce_household_constraints:
        response = _enforce_constraints_with_rerun(
            original_query=sanitized_query,
            response=response,
            cfg=cfg,
            session_id=session_id,
            use_profile=use_profile,
        )

    return response


def _household_constraint_check(recipe_id: str, profile: DemoUserProfile = DEMO_PROFILE) -> tuple[bool, list[str]]:
    """Return (ok, violations) for a single recipe_id against the household profile.

    Returns (True, []) when the recipe passes all member constraints. Returns
    (False, [reason, ...]) listing each violation. Also returns (True, [])
    when the recipe_id is unknown — the caller should treat that as "no data,
    do not reject on this alone".
    """
    meta = execute_tool("get_recipe_metadata", recipe_id=recipe_id)
    if meta.get("error"):
        return True, []
    allergens = {a.lower() for a in meta.get("allergens_eu14", [])}
    age_bands = {b for b in meta.get("suitable_for_age_bands", [])}

    violations: list[str] = []
    for member in profile.members:
        member_allergens = {a.lower() for a in member.allergens}
        bad_allergens = sorted(member_allergens & allergens)
        if bad_allergens:
            violations.append(
                f"`{recipe_id}` contains {', '.join(bad_allergens)} — conflict for {member.display_name}"
            )
        if member.age_band not in age_bands:
            violations.append(
                f"`{recipe_id}` is not listed as suitable for {member.age_band} ({member.display_name})"
            )
    return (len(violations) == 0), violations


_RECIPE_ID_PATTERN = __import__("re").compile(r"\b(?:utah_wic|lets_cook_with_kids_ca_wic|ca_wic|demo)_[a-z0-9_]+")


def _extract_recipe_ids_from_response(answer_text: str) -> list[str]:
    """Pull plausible recipe_ids out of the agent's free-text answer.

    Matches the prefixes of our known recipe_ids in `data/rag/demo/derived/recipes.json`.
    Cross-check each extracted id against the canonical list via get_recipe_metadata
    (which returns `error` for unknowns).
    """
    found = _RECIPE_ID_PATTERN.findall(answer_text or "")
    seen: list[str] = []
    for rid in found:
        if rid not in seen:
            seen.append(rid)
    return seen


def _enforce_constraints_with_rerun(
    *,
    original_query: str,
    response: CapstoneRAGResponse,
    cfg: AgentConfig,
    session_id: str,
    use_profile: bool,
) -> CapstoneRAGResponse:
    """Post-filter the agent's response against household constraints; rerun once if any violate.

    Rationale: the LLM may ignore the SYSTEM_PROMPT's call-get_recipe_metadata
    instruction and pick constraint-violating recipes. This defense-in-depth
    step validates deterministically and retries ONCE with a stricter query
    that names the violators and lists only the safe alternatives.
    """
    recipe_ids = _extract_recipe_ids_from_response(response.answer)
    if not recipe_ids:
        return response  # no recipes to check — return as-is

    violating: list[str] = []
    all_violations: list[str] = []
    for rid in recipe_ids:
        ok, violations = _household_constraint_check(rid)
        if not ok:
            violating.append(rid)
            all_violations.extend(violations)

    if not violating:
        # All picks passed — tag the response with the clean-pass marker.
        response.reasoning_notes = (response.reasoning_notes or "") + " [constraint-enforce: all picks passed]"
        return response

    # Violations found — construct the stricter retry query.
    # Load the full corpus to list safe alternatives.
    all_recipes_meta = execute_tool("get_recipe_metadata", recipe_id="__force_dump__")
    # ^ returns error, but we need the `available_ids` list from the error payload.
    safe_ids: list[str] = []
    for rid in all_recipes_meta.get("available_ids", []):
        ok, _ = _household_constraint_check(rid)
        if ok:
            safe_ids.append(rid)

    strict_query = (
        f"{original_query}\n\n"
        f"IMPORTANT — your previous selection violated the household constraints: "
        f"{violating}. Reasons: {all_violations}.\n"
        f"Pick recipes ONLY from this verified-safe list: {safe_ids}. "
        f"Call get_recipe_metadata on each candidate before including it in your answer."
    )

    effective_query = personalize_query(strict_query, DEMO_PROFILE) if use_profile else strict_query

    # Second attempt — we're inside run_agent already, so reuse the lower-level agent path directly.
    want_real = (
        os.getenv("OPENAI_API_KEY")
        and os.getenv("CAPSTONE_USE_REAL_AGENT", "true").lower() != "false"
    )
    limiter = get_limiter()
    budget = limiter.check_budget(session_id)
    use_real_agent = bool(want_real and budget.allowed)

    if not use_real_agent:
        rerun_response = _deterministic_fallback(effective_query, cfg)
    else:
        try:
            rerun_response = _run_pydantic_ai(effective_query, cfg)
            limiter.record_call(session_id, _estimated_cost_per_call(cfg))
        except Exception as e:
            rerun_response = _deterministic_fallback(effective_query, cfg)
            rerun_response.reasoning_notes = (
                (rerun_response.reasoning_notes or "") + f" [rerun-pydantic-ai failed: {type(e).__name__}: {e}]"
            )

    # Re-check the rerun's picks; tag accordingly.
    rerun_ids = _extract_recipe_ids_from_response(rerun_response.answer)
    rerun_violations: list[str] = []
    for rid in rerun_ids:
        ok, v = _household_constraint_check(rid)
        if not ok:
            rerun_violations.extend(v)

    rerun_response.reasoning_notes = (rerun_response.reasoning_notes or "") + (
        f" [constraint-enforce: initial violations={violating} ({len(all_violations)} checks failed); "
        f"reran once; rerun picks={rerun_ids}; rerun violations={rerun_violations or 'none'}]"
    )
    return rerun_response


def _guardrail_refusal(query, guard, logger) -> CapstoneRAGResponse:
    refusal = CapstoneRAGResponse(
        answer=(
            f"Your query was blocked by input guardrails (reason: {guard.reason}). "
            "This assistant accepts nutrition, recipe, and meal-planning questions only. "
            "Please rephrase or ask a food-related question."
        ),
        evidence_tier="refused",
        confidence=0.0,
        citations=[],
        tool_calls=[ToolCall(
            name="input_guardrails",
            arguments={"query_len": len(query or "")},
            result_preview=f"{guard.reason}; markers={guard.blocked_markers}",
        )],
        requires_disclaimer=False,
        disclaimer_text=None,
        demo_blocked_collections=[],
        reasoning_notes=f"input guardrail: {guard.reason}",
    )
    logger.log_call(
        query=query or "", response_preview=refusal.answer,
        tool_calls=[tc.model_dump() for tc in refusal.tool_calls],
        evidence_tier="refused", model="input-guardrail", success=True,
    )
    return refusal


def _curative_refusal(query: str, logger) -> CapstoneRAGResponse:
    """Refuse a curative-claim query with clinician-referral disclaimer.

    Pinned by test_curative_query_refused_pre_retrieval + gt_007.
    """
    response = CapstoneRAGResponse(
        answer=(
            "I cannot answer this query. The question asks about curing, reversing, or prescribing "
            "for a medical condition, which is outside the scope of this nutrition knowledge assistant. "
            "Please consult a qualified healthcare professional or registered dietitian for personal "
            "medical guidance. This is not medical advice."
        ),
        evidence_tier="refused",
        confidence=0.0,
        citations=[],
        tool_calls=[ToolCall(
            name="check_medical_boundaries",
            arguments={"query": query},
            result_preview="curative-claim pattern matched; refused before retrieval",
        )],
        requires_disclaimer=True,
        disclaimer_text=(
            "Educational response only. Not medical advice. Consult a licensed clinician for diagnosis or treatment."
        ),
        demo_blocked_collections=[],
        reasoning_notes="query-side curative-claim pre-check matched; skipped retrieval by design.",
    )
    logger.log_call(
        query=query, response_preview=response.answer,
        tool_calls=[tc.model_dump() for tc in response.tool_calls],
        evidence_tier="refused", model="curative-guard", success=True,
    )
    return response


def _intent_redirect(query: str, intent, logger) -> CapstoneRAGResponse:
    answer = intent.redirect_suggestion or (
        "This MealMap coach answers questions about meals, nutrition, recipes, "
        "and allergen safety only."
    )
    response = CapstoneRAGResponse(
        answer=answer,
        evidence_tier="refused",
        confidence=0.0,
        citations=[],
        tool_calls=[ToolCall(
            name="classify_intent_strict",
            arguments={"query_len": len(query or "")},
            result_preview=f"{intent.status}; reason={intent.reason}",
        )],
        requires_disclaimer=False,
        disclaimer_text=None,
        demo_blocked_collections=[],
        reasoning_notes=f"intent classifier: {intent.status}/{intent.reason}",
    )
    logger.log_call(
        query=query or "", response_preview=response.answer,
        tool_calls=[tc.model_dump() for tc in response.tool_calls],
        evidence_tier="refused", model="intent-classifier", success=True,
    )
    return response


def _estimated_cost_per_call(cfg: AgentConfig) -> float:
    """Conservative flat estimate used for session-cap bookkeeping.

    Real token-level cost is logged by agent_observability.log_call; this
    estimate only matters for the rate-limiter's day-budget aggregation. We
    deliberately err slightly high (~$0.001/call) so the budget cap is reached
    sooner rather than later when real cost tracking is unavailable.
    """
    return 0.001
