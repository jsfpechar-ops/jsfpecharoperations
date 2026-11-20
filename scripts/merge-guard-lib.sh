# shellcheck shell=bash
# Shared helpers for scripts/merge-pr-on-green.sh (source, do not execute).
#
# Tests: scripts/test_merge_guard_lib.sh and App/tests/test_merge_guard_lib.py

# Return 0 when every path is under docs/tasks/ (exact-diff sidecar PRs).
merge_guard_docs_tasks_only() {
  local f
  while IFS= read -r f; do
    [ -z "${f}" ] && continue
    case "${f}" in
      docs/tasks/*) ;;
      *) return 1 ;;
    esac
  done
  return 0
}

# name, state (pass|fail|pending|skipping|cancel), docs_tasks_only (0|1)
merge_guard_required_state_ok() {
  local name="$1" state="$2" docs_only="$3"
  if [ "${state}" = "pass" ]; then
    return 0
  fi
  if [ "${name}" = "go" ] && [ "${state}" = "skipping" ] && [ "${docs_only}" -eq 1 ]; then
    return 0
  fi
  return 1
}