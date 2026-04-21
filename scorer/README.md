# Capstone self-scorer

Reproducible wrapper around [`alexeygrigorev/github-project-scorer`](https://github.com/alexeygrigorev/github-project-scorer) — the official scoring tool for the Alexey Grigorev "From RAG to Agents" course.

**Why vendor the wrapper here?** So a grader (or the user) can reproduce the self-score in **one command** without a separate clone + manual argument passing. The scorer itself is NOT vendored (licensing + upstream updates); this wrapper clones it on demand into `_clone/` (git-ignored) at a **pinned commit SHA**.

## Quick start

```bash
# From the SimplifiedMealMasterCapstone/ folder
export OPENAI_API_KEY=sk-...            # required by the scorer (uses gpt-4o-mini by default)
bash scorer/run_self_score.sh           # clones scorer, runs it, writes docs/self-score-report.md
```

The resulting `docs/self-score-report.md` is **committed** to the repo so the grader can see the score without running anything.

## What the wrapper does

1. Clones `alexeygrigorev/github-project-scorer` at the pinned commit (`scorer/SCORER_COMMIT_SHA`) into `scorer/_clone/` (git-ignored).
2. Runs `uv sync` inside the clone.
3. Runs the scorer against **this public repo URL** (see `scorer/TARGET_REPO_URL` — defaults to `https://github.com/elgrassa/CapstoneMealMapSimplified`).
4. Applies the `criteria/ai-bootcamp-maven.yaml` rubric.
5. Writes the resulting markdown report to `../docs/self-score-report.md` (relative to `scorer/`).
6. Prints the total score to stdout.

## Environment

| Variable | Purpose | Required |
|---|---|---|
| `OPENAI_API_KEY` | Scorer's LLM agent (gpt-4o-mini) | Yes |
| `SCORER_TARGET_REPO` | Override the repo URL being scored | No |
| `SCORER_OUTPUT_DIR` | Override `../docs/` | No |

## Cost estimate

The scorer runs one agent per rubric criterion (~12 criteria). Each criterion runs a few `read_file` / `search_content` tool calls. A full run is approximately **$0.05–$0.10 USD** with `gpt-4o-mini` at current pricing. The cost is **not** subject to the capstone's own `CAPSTONE_DAILY_BUDGET_USD` rate limit — the scorer is a separate process with its own OpenAI key.

## Upstream references

- Scorer repo: https://github.com/alexeygrigorev/github-project-scorer
- Rubric file: https://github.com/alexeygrigorev/github-project-scorer/blob/main/criteria/ai-bootcamp-maven.yaml
- Target: https://github.com/elgrassa/CapstoneMealMapSimplified

## Reproducibility

Pin is `scorer/SCORER_COMMIT_SHA` (a SHA-1 string, one line). Update this file to re-pin to a newer scorer release.

If the scorer's CLI arguments change, `run_self_score.sh` is where to update the `uv run python main.py ...` invocation.
