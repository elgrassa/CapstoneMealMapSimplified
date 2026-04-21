# Next steps — publishing the capstone

The capstone subfolder is complete in this repo. Three steps remain (user-side):

## 1. Copy the subfolder contents into [`elgrassa/CapstoneMealMapSimplified`](https://github.com/elgrassa/CapstoneMealMapSimplified)

```bash
# Fresh clone of the public repo
cd ~/IdeaProjects   # or wherever
rm -rf CapstoneMealMapSimplified.tmp
git clone https://github.com/elgrassa/CapstoneMealMapSimplified CapstoneMealMapSimplified.tmp
cd CapstoneMealMapSimplified.tmp

# Copy the capstone subfolder contents to the repo root
rsync -a --delete \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='node_modules' \
  --exclude='_clone' \
  --exclude='__pycache__' \
  --exclude='*.egg-info' \
  /path/to/SimplifiedMealMasterCapstone/ ./

# Commit + push
git add -A
git commit -m "feat: initial capstone submission — full scaffold from main-repo PR #201"
git push origin main
```

After push: visit https://github.com/elgrassa/CapstoneMealMapSimplified — you should see `README.md`, `src/`, `ai/`, `backend/`, `demo_ui/`, `monitoring/`, `tests/`, `docs/`, `scorer/`, `.github/workflows/*`.

## 2. Secrets that must exist on the public repo

The `OPENAI_API_KEY` is already set (you mentioned). Verify at:

https://github.com/elgrassa/CapstoneMealMapSimplified/settings/secrets/actions

For **Streamlit Cloud** (separate system), the same key must also be added to the app's Advanced Settings → Secrets, in TOML format. See [`docs/deployment.md`](deployment.md#2-streamlit-community-cloud) for the full TOML block.

## 3. Run the scorer — two ways

### Option A: GitHub Actions workflow (recommended — uses repo secret, no local key needed)

Once the subfolder contents land in the public repo:

1. Open https://github.com/elgrassa/CapstoneMealMapSimplified/actions/workflows/self-score.yml
2. Click **"Run workflow"** → **Run workflow** (green button). Leave the `target_repo` input blank to score the current repo.
3. Wait ~5 min. The workflow:
   - Clones `alexeygrigorev/github-project-scorer` at the pinned SHA.
   - Installs deps via `uv sync`.
   - Runs the scorer with `OPENAI_API_KEY` from repo secrets.
   - Writes the report to `docs/self-score-report.md`.
   - Commits the report back to `main` with message `chore(capstone): refresh self-score report via scorer workflow [skip ci]`.
   - Uploads the report as an Actions artifact (download from the run summary).
4. The same workflow also runs **weekly (Mondays 06:00 UTC)** so the report stays fresh as the scorer evolves.

### Option B: Local run (if you want the report immediately)

```bash
cd /path/to/CapstoneMealMapSimplified
export OPENAI_API_KEY=sk-...    # same key
bash scorer/run_self_score.sh
# Writes docs/self-score-report.md (commit + push yourself)
```

Cost: ~$0.05–0.10 USD per run.

## 4. Deploy the Streamlit demo

Full step-by-step in [`docs/deployment.md`](deployment.md). TL;DR:

1. Sign in at https://share.streamlit.io with GitHub.
2. "Create app" → `elgrassa/CapstoneMealMapSimplified` → `main` → `demo_ui/app.py` → Python 3.13.
3. Advanced Settings → Secrets TOML:
   ```toml
   OPENAI_API_KEY = "sk-..."
   CAPSTONE_DAILY_BUDGET_USD = "0.50"
   CAPSTONE_SESSION_LLM_CAP = "20"
   CAPSTONE_SESSION_LLM_WINDOW_S = "3600"
   DEMO_MODE = "true"
   ```
4. Deploy. First build ~3–5 min. URL format: `<username>-capstonemealmapsimplified-demo-ui-app-<hash>.streamlit.app`.
5. Once live: add the URL to README.md "Demo visuals" / header banner — and to the capstone submission form.

## 5. Verify

After steps 1–4:

- [ ] `docs/self-score-report.md` on `main` is no longer the placeholder (it has a real score table).
- [ ] Streamlit Cloud URL loads the demo; Tab 1 "Ask agent" returns a supported response for "What is the RDA for vitamin D?".
- [ ] Clicking thumbs-up persists to `monitoring/feedback.db` (visible in the monitoring dashboard).
- [ ] Exceeding 20 calls in one hour triggers the "Rate limit reached" banner (hard to verify manually — just inspect the sidebar progress bar).
- [ ] README's "Demo" section links to the real Streamlit URL, not a placeholder.

## 6. Submit

Once all 5 checks pass, submit the capstone using the course's submission form:
- Public repo URL: https://github.com/elgrassa/CapstoneMealMapSimplified
- Live demo URL: your Streamlit Cloud URL (from step 4)
- Self-score report: point the reviewer to `docs/self-score-report.md`

## Rollback

If anything goes wrong with the scorer workflow:

1. The workflow is `workflow_dispatch` + weekly schedule — you can disable it anytime at Actions → self-score workflow → ⋯ → Disable workflow.
2. To revert the committed report: `git revert <commit-sha>` on `main`.
3. To re-pin a different scorer version: edit `scorer/SCORER_COMMIT_SHA` with a new SHA and run the workflow.
