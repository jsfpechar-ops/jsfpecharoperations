#!/usr/bin/env bash
# Merge a pull request only when CI is green for its *current* head commit.
#
# Why this exists: `gh pr checks` can briefly show a previous commit's passing
# checks right after a force-push. A loop that merges on the first
# "nothing is pending" result can therefore merge a commit whose own run is
# still failing. This script pins the head SHA, waits for the checks of that
# SHA to settle, refuses to merge while anything failed or is pending, and
# re-checks that the SHA did not move before it merges.
#
# Branch protection is not available on this private plan, so this is the
# guard. Usage:
#
#   scripts/merge-pr-on-green.sh <pr-number> [--merge|--squash|--rebase]
#
# Env: MERGE_GUARD_TIMEOUT (seconds, default 1800).
# Env: MERGE_GUARD_MIN_CHECKS (default 12) — refuse to merge while gh shows
#      fewer checks (stale partial list after force-push; see #1144).
# Env: MERGE_GUARD_REQUIRED — space-separated required check names (default: go).
set -euo pipefail

PR="${1:?usage: merge-pr-on-green.sh <pr-number> [--merge|--squash|--rebase]}"
METHOD="${2:---merge}"
case "${METHOD}" in
  --merge|--squash|--rebase) ;;
  *) echo "unknown merge method: ${METHOD}" >&2; exit 2 ;;
esac
TIMEOUT="${MERGE_GUARD_TIMEOUT:-1800}"
MIN_CHECKS="${MERGE_GUARD_MIN_CHECKS:-12}"
REQUIRED_CHECKS="${MERGE_GUARD_REQUIRED:-go}"

command -v gh >/dev/null 2>&1 || { echo "gh is not installed" >&2; exit 2; }

required_checks_ok() {
  local output="$1"
  local name state
  for name in ${REQUIRED_CHECKS}; do
    state="$(printf '%s\n' "${output}" | awk -F'\t' -v n="${name}" '$1==n{print $2; exit}')"
    # Path-filtered PRs legitimately skip `go` when no Go paths changed; treat as satisfied.
    if [ "${state}" != "pass" ] && [ "${state}" != "skipping" ]; then
      echo "required check ${name} not pass (state=${state:-missing})" >&2
      return 1
    fi
  done
  return 0
}

# `gh pr checks` prints tab-separated lines: name<TAB>state<TAB>elapsed<TAB>url
# state is one of pass, fail, pending, skipping, cancel.
checks() {
  gh pr checks "${PR}" 2>&1 || true
}

head_sha() {
  # gh's own --jq needs no external jq.
  gh pr view "${PR}" --json headRefOid --jq '.headRefOid'
}

# Owner policy: auto-merge PRs when green, but never while main's go job is red.
main_go_red() {
  local conclusion
  conclusion="$(gh api repos/jsfpechar-ops/jsfpecharoperations/commits/main/check-runs \
    --jq '.check_runs[]|select(.name=="go")|.conclusion' 2>/dev/null | head -1)"
  [ "${conclusion}" = "failure" ]
}

pinned="$(head_sha)"
echo "guarding PR #${PR} at ${pinned}"
deadline=$(( $(date +%s) + TIMEOUT ))

while :; do
  current="$(head_sha)"
  if [ "${current}" != "${pinned}" ]; then
    echo "head moved ${pinned} -> ${current}; waiting for the new commit"
    pinned="${current}"
  fi

  output="$(checks)"
  total="$(printf '%s\n' "${output}" | awk -F'\t' 'NF>=2{c++} END{print c+0}')"
  pending="$(printf '%s\n' "${output}" | awk -F'\t' '$2=="pending"{c++} END{print c+0}')"
  failed="$(printf '%s\n' "${output}" | awk -F'\t' '($2=="fail"||$2=="cancel"){printf "%s ", $1}')"

  if [ "${total}" -ge "${MIN_CHECKS}" ] && [ "${pending}" -eq 0 ]; then
    if [ -n "${failed}" ]; then
      echo "refusing to merge: checks failed for ${pinned}: ${failed}" >&2
      printf '%s\n' "${output}" >&2
      exit 1
    fi
    if ! required_checks_ok "${output}"; then
      printf '%s\n' "${output}" >&2
      sleep 10
      continue
    fi
    # Re-read right before merging: a force-push during the poll must restart it.
    if [ "$(head_sha)" != "${pinned}" ]; then
      echo "head changed during the final check; re-evaluating"
      continue
    fi
    if main_go_red; then
      echo "main go job is red; pausing merge for PR #${PR} until main is green"
      sleep 30
      continue
    fi
    echo "all ${total} check(s) green for ${pinned} (required: ${REQUIRED_CHECKS}); merging (${METHOD})"
    gh pr merge "${PR}" "${METHOD}" --delete-branch
    exit 0
  fi

  if [ "${total}" -gt 0 ] && [ "${total}" -lt "${MIN_CHECKS}" ] && [ "${pending}" -eq 0 ]; then
  echo "only ${total} check(s) visible (need ${MIN_CHECKS}); waiting for full CI list for ${pinned}"
  fi

  if [ "$(date +%s)" -ge "${deadline}" ]; then
    echo "timed out after ${TIMEOUT}s waiting for checks on ${pinned}" >&2
    printf '%s\n' "${output}" >&2
    exit 1
  fi
  sleep 10
done
