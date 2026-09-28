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
set -euo pipefail

PR="${1:?usage: merge-pr-on-green.sh <pr-number> [--merge|--squash|--rebase]}"
METHOD="${2:---merge}"
case "${METHOD}" in
  --merge|--squash|--rebase) ;;
  *) echo "unknown merge method: ${METHOD}" >&2; exit 2 ;;
esac
TIMEOUT="${MERGE_GUARD_TIMEOUT:-1800}"

command -v gh >/dev/null 2>&1 || { echo "gh is not installed" >&2; exit 2; }

# `gh pr checks` prints tab-separated lines: name<TAB>state<TAB>elapsed<TAB>url
# state is one of pass, fail, pending, skipping, cancel.
checks() {
  gh pr checks "${PR}" 2>&1 || true
}

head_sha() {
  # gh's own --jq needs no external jq.
  gh pr view "${PR}" --json headRefOid --jq '.headRefOid'
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

  if [ "${total}" -gt 0 ] && [ "${pending}" -eq 0 ]; then
    if [ -n "${failed}" ]; then
      echo "refusing to merge: checks failed for ${pinned}: ${failed}" >&2
      printf '%s\n' "${output}" >&2
      exit 1
    fi
    # Re-read right before merging: a force-push during the poll must restart it.
    if [ "$(head_sha)" != "${pinned}" ]; then
      echo "head changed during the final check; re-evaluating"
      continue
    fi
    echo "all ${total} check(s) green for ${pinned}; merging (${METHOD})"
    gh pr merge "${PR}" "${METHOD}" --delete-branch
    exit 0
  fi

  if [ "$(date +%s)" -ge "${deadline}" ]; then
    echo "timed out after ${TIMEOUT}s waiting for checks on ${pinned}" >&2
    printf '%s\n' "${output}" >&2
    exit 1
  fi
  sleep 10
done
