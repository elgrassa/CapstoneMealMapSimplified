#!/usr/bin/env bash
# Reproducible self-score runner. One command: clone (pinned SHA) → sync → run.
# Writes a markdown report at ../docs/self-score-report.md.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAPSTONE_ROOT="$(cd "${HERE}/.." && pwd)"
CLONE_DIR="${HERE}/_clone"
SCORER_REPO_URL="https://github.com/alexeygrigorev/github-project-scorer.git"
PINNED_SHA="$(tr -d '[:space:]' < "${HERE}/SCORER_COMMIT_SHA")"
TARGET_REPO="${SCORER_TARGET_REPO:-$(tr -d '[:space:]' < "${HERE}/TARGET_REPO_URL")}"
CRITERIA_YAML="criteria/ai-bootcamp-maven.yaml"
REPORT_OUT_DIR="${SCORER_OUTPUT_DIR:-${CAPSTONE_ROOT}/docs}"
REPORT_OUT_PATH="${REPORT_OUT_DIR}/self-score-report.md"

usage() {
  cat <<EOF
run_self_score.sh — reproducible capstone self-scorer

Usage:
  bash $(basename "$0")             # clone scorer @ pinned SHA, run against TARGET_REPO_URL
  bash $(basename "$0") --help      # show this message

Environment:
  OPENAI_API_KEY       required — used by the scorer agent (gpt-4o-mini)
  SCORER_TARGET_REPO   override the repo URL being scored
  SCORER_OUTPUT_DIR    override the output directory (default: ${CAPSTONE_ROOT}/docs)

Pin: ${PINNED_SHA}
Target: ${TARGET_REPO}
Report: ${REPORT_OUT_PATH}
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "[self-score] OPENAI_API_KEY is not set — aborting." >&2
  echo "[self-score] Export a real key before running, e.g.: export OPENAI_API_KEY=sk-..." >&2
  exit 2
fi

# 1. Clone / update the scorer at the pinned SHA
if [[ ! -d "${CLONE_DIR}/.git" ]]; then
  echo "[self-score] cloning scorer into ${CLONE_DIR} ..."
  git clone --depth 50 "${SCORER_REPO_URL}" "${CLONE_DIR}"
fi
(
  cd "${CLONE_DIR}"
  git fetch --depth 50 origin
  git checkout "${PINNED_SHA}" --quiet
)

# 2. Install deps (uv preferred)
if command -v uv >/dev/null 2>&1; then
  (cd "${CLONE_DIR}" && uv sync --quiet)
  RUNNER="uv run python"
else
  (cd "${CLONE_DIR}" && python3 -m pip install -q -e .)
  RUNNER="python3"
fi

# 3. Run the scorer.
# Use gpt-4o (not gpt-4o-mini) because the scorer fires parallel requests and
# mini hits its 200k TPM limit on repos our size — two earlier runs showed 5+
# criteria getting 'Evaluation failed: rate_limit_exceeded' with mini. gpt-4o
# has a 10M TPM limit and costs ~4x more (~$0.30 vs ~$0.08 per run), which is
# still well within the capstone budget for a manual-only workflow.
#
# Wrapped in a 3-attempt retry loop with 30s backoff so a one-off 429 doesn't
# sink the whole run. The scorer returns non-zero on any per-criterion failure
# (even if most criteria passed), so we also check the output report for the
# 'rate_limit_exceeded' marker and retry only when that's the cause.
SCORER_MODEL="${SCORER_MODEL:-gpt-4o}"
SCORER_MAX_ATTEMPTS="${SCORER_MAX_ATTEMPTS:-3}"
SCORER_RETRY_BACKOFF_S="${SCORER_RETRY_BACKOFF_S:-30}"

mkdir -p "${REPORT_OUT_DIR}"
echo "[self-score] scoring ${TARGET_REPO} against ${CRITERIA_YAML} with ${SCORER_MODEL}"

SCORER_EXIT=1
for attempt in $(seq 1 "${SCORER_MAX_ATTEMPTS}"); do
  echo "[self-score] attempt ${attempt}/${SCORER_MAX_ATTEMPTS}"
  (
    cd "${CLONE_DIR}"
    ${RUNNER} main.py "${TARGET_REPO}" \
      --criteria "${CRITERIA_YAML}" \
      --output "${REPORT_OUT_DIR}" \
      --model-provider openai \
      --model-name "${SCORER_MODEL}" \
      --no-cleanup
  ) && SCORER_EXIT=0 || SCORER_EXIT=$?

  # Look for a fresh markdown report (skip the stable-path one).
  NEW_REPORT="$(ls -t "${REPORT_OUT_DIR}"/*.md 2>/dev/null | grep -v '/self-score-report\.md$' | head -n1 || true)"

  if [[ ${SCORER_EXIT} -eq 0 ]] && [[ -n "${NEW_REPORT}" ]]; then
    if grep -q 'rate_limit_exceeded' "${NEW_REPORT}"; then
      echo "[self-score] rate-limit hit on at least one criterion — retry after ${SCORER_RETRY_BACKOFF_S}s"
      rm -f "${NEW_REPORT}"
      sleep "${SCORER_RETRY_BACKOFF_S}"
      continue
    fi
    break
  fi

  if [[ ${attempt} -lt ${SCORER_MAX_ATTEMPTS} ]]; then
    echo "[self-score] scorer failed (exit ${SCORER_EXIT}) — retry after ${SCORER_RETRY_BACKOFF_S}s"
    sleep "${SCORER_RETRY_BACKOFF_S}"
  fi
done

# 4. Locate the newest markdown dropped by the scorer and copy it to the stable path.
NEW_REPORT="$(ls -t "${REPORT_OUT_DIR}"/*.md 2>/dev/null | grep -v '/self-score-report\.md$' | head -n1 || true)"
if [[ -n "${NEW_REPORT}" ]]; then
  cp -f "${NEW_REPORT}" "${REPORT_OUT_PATH}"
  echo "[self-score] canonical report at ${REPORT_OUT_PATH}"
else
  echo "[self-score] no new markdown report produced — check scorer output."
fi

echo "[self-score] done."
