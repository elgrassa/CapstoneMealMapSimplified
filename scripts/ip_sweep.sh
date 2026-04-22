#!/usr/bin/env bash
# IP grep sweep — fail the build if any committed file references brand / market
# / production-specific terms that should not leak into the public capstone.
#
# Usage:
#   bash scripts/ip_sweep.sh          # exits 0 if clean, 1 if any denylisted term is found
#
# The denylist is deliberately narrow — targets concrete production identifiers
# (MealMaster Polish market, Base44 backend, user emails, specific family names)
# rather than broad brand mentions. "MealMaster" itself is allowed because it's
# the trademark-holding name and appears in LICENSE + NOTICE + historical doc
# references.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/.." && pwd)"

# Terms that MUST NOT appear in committed source (excluding .git, .venv, caches).
DENY=(
  "Lidl"
  "Biedronka"
  "PLN"
  "zł"
  "pavlo.skorodziievskyi"
  "@gmail.com"
  "VITE_BASE44"
  "base44.app"
  "mandatory_products"     # production FamilyMember cipher field — must not leak
)

EXCLUDES=(
  ".git" ".venv" "__pycache__" "node_modules" "*.egg-info"
  ".pytest_cache" ".mypy_cache" ".ruff_cache"
  "docs/self-score-history"   # historical scorer reports — not our content
)

# Files whose presence of a denylisted term is intentional (they're about the
# term itself, not leaking a real value).
ALLOWLIST_FILES=(
  "./scripts/ip_sweep.sh"        # this script defines the denylist
  "./docs/ip-strategy.md"        # meta-doc about the IP protection strategy itself
)

build_grep_exclude_flags() {
  local out=()
  for e in "${EXCLUDES[@]}"; do
    out+=(--exclude-dir="${e}")
  done
  echo "${out[@]}"
}

is_allowlisted() {
  local path="$1"
  for f in "${ALLOWLIST_FILES[@]}"; do
    [[ "${path}" == "${f}" ]] && return 0
  done
  return 1
}

FOUND=0
echo "[ip-sweep] scanning ${REPO_ROOT}"
for term in "${DENY[@]}"; do
  # shellcheck disable=SC2046
  hits=$(cd "${REPO_ROOT}" && grep -rn --binary-files=without-match $(build_grep_exclude_flags) -F "${term}" . 2>/dev/null || true)
  if [[ -z "${hits}" ]]; then
    continue
  fi
  # Filter out allowlisted files
  filtered=""
  while IFS= read -r line; do
    file_path="${line%%:*}"
    if is_allowlisted "${file_path}"; then
      continue
    fi
    filtered+="${line}"$'\n'
  done <<< "${hits}"
  if [[ -n "${filtered}" ]]; then
    echo "[ip-sweep] DENIED term found: ${term}"
    echo "${filtered}"
    FOUND=1
  fi
done

if [[ ${FOUND} -eq 0 ]]; then
  echo "[ip-sweep] clean — no denylisted terms in committed source."
  exit 0
else
  echo "[ip-sweep] FAILED — remove the flagged references or add a principled exception to scripts/ip_sweep.sh."
  exit 1
fi
