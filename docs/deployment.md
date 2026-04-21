# Deployment guide — public repo + hosted Streamlit demo

This doc covers two things the user has to do **once**, after the contents of
`SimplifiedMealMasterCapstone/` are pushed to `elgrassa/CapstoneMealMapSimplified`:

1. **GitHub repo secrets** — for the `live-eval` CI job and the scorer run.
2. **Streamlit Community Cloud deployment** — so the `demo_ui/app.py` is hosted
   at a shareable `*.streamlit.app` URL (the user can link it from the capstone
   submission form).

Both are free (no paid tiers required).

---

## 1. GitHub repo secrets

Location: **https://github.com/elgrassa/CapstoneMealMapSimplified/settings/secrets/actions**

| Name | Required? | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | Optional | Activates the `live-eval` GitHub Action job on PRs (runs `make eval-live` with real LLM). If absent, the job is **skipped gracefully** — all other CI jobs (tests, offline eval, tuning sweep, mutation tests) still run without any key. |

**That's it.** No other repo secrets needed for CI to go green.

### Creating the secret

1. Go to the repo → Settings → Secrets and variables → Actions → New repository secret.
2. Name: `OPENAI_API_KEY`.
3. Value: your `sk-...` key.
4. Save.

### Verifying

After adding the secret, push a PR to trigger CI. The `live-eval` job should appear in the Actions tab and run successfully.

---

## 2. Streamlit Community Cloud

Location: **https://share.streamlit.io**

### One-time setup

1. Sign in at https://share.streamlit.io with your GitHub account.
2. Click **"Create app"** (or "Deploy" → "From existing repo").
3. Fill in:
   - **Repository:** `elgrassa/CapstoneMealMapSimplified`
   - **Branch:** `main`
   - **Main file path:** `demo_ui/app.py`
   - **Python version:** `3.13` (Streamlit Cloud supports 3.10 → 3.13).
4. Click **"Advanced settings"** → paste the following into the **Secrets** box (TOML format):

   ```toml
   # These are read by os.getenv() inside the app (Streamlit Cloud exposes
   # Advanced Settings secrets as env vars).
   OPENAI_API_KEY = "sk-REPLACE-ME"

   # --- Cost guardrail overrides (all optional) ---
   # Defaults: 20 / session / hour, $0.50 / day.
   CAPSTONE_DAILY_BUDGET_USD = "0.50"
   CAPSTONE_SESSION_LLM_CAP = "20"
   CAPSTONE_SESSION_LLM_WINDOW_S = "3600"

   # --- Demo mode (always true on the hosted demo) ---
   DEMO_MODE = "true"
   ```

5. **Deploy.** Streamlit Cloud will install `pyproject.toml` deps + auto-create a Python venv. First build ≈ 3–5 minutes.

6. The URL will be `<your-username>-<repo-slug>-demo-ui-app-<hash>.streamlit.app` — add it to README + the capstone submission.

### Why the rate limiter matters here

Streamlit Cloud is a **public URL**. Anyone with the link (graders, their classmates, random internet traffic) can click "Ask agent". Without the built-in rate limiter, a single grader running a 100-query benchmark could drain the key.

With the defaults (`0.50` USD/day + 20 calls/session/hour):

- Worst case: 20 calls × gpt-4.1-mini ≈ 20 × 800 tokens avg × $0.0003-0.0012 = **~$0.005** per session.
- Any session that hits the caps transparently downgrades to the deterministic-fallback path (no LLM call) — the demo remains usable but free.
- Daily global cap at $0.50 means no single day can cost more than that, regardless of how many sessions hit the URL.

### Updating app code

Streamlit Cloud watches `main`. Every push to `main` redeploys automatically (build takes ≈ 60 seconds for an incremental change).

### Secrets rotation

If you ever need to rotate the OpenAI key:

1. Streamlit Cloud → Your app → Manage app → Settings → Secrets → edit `OPENAI_API_KEY` → Save.
2. Streamlit Cloud restarts the app within ≈ 30 seconds.

You do not need to push a commit.

---

## 3. Optional: hide the scorer behind a workflow

If you want a one-click "run self-scorer and commit the report" flow:

1. Add a new `.github/workflows/self-score.yml` with a `workflow_dispatch` trigger.
2. Runs `bash scorer/run_self_score.sh` — needs `OPENAI_API_KEY` secret.
3. Commits the updated `docs/self-score-report.md` back to `main` (requires `contents: write` permission).

This is **not** wired by default because the scorer consumes ~$0.05-0.10 per run — cheap, but not free. Run it manually when you want to refresh the committed score.

---

## 4. Troubleshooting

| Symptom | Fix |
|---|---|
| Streamlit app boots but every query returns "refused (deterministic-fallback)" | `OPENAI_API_KEY` is missing or invalid in Streamlit Cloud Advanced Settings. |
| Every query returns "Rate limit reached" immediately | Check `CAPSTONE_DAILY_BUDGET_USD` / `CAPSTONE_SESSION_LLM_CAP` overrides — you may have set them to 0. |
| Demo corpus missing / empty retrieval | Streamlit Cloud didn't run `make seed`. Ensure `demo_ui/app.py` calls `load_all_demo_indexes()` at bootstrap (it does, via `_bootstrap_indexes()`). |
| CI `live-eval` job failing | `OPENAI_API_KEY` secret not added to GitHub Actions, or the key has insufficient quota. The job is optional — CI stays green even when it fails. |
| Scorer run fails with "repo not found" | `scorer/TARGET_REPO_URL` points at the public repo. Confirm the repo is public (Streamlit Cloud requires public repos for free tier). |

---

## 5. One-command local run (no deployment needed)

If you just want to test the app before deploying:

```bash
cd SimplifiedMealMasterCapstone
uv sync
export OPENAI_API_KEY=sk-...
make demo        # Streamlit on http://localhost:8502 — uses env var
```

This is the same app that Streamlit Cloud deploys; all guardrails and rate limits apply locally too (they use the same SQLite DB under `monitoring/rate_limit.db`).
