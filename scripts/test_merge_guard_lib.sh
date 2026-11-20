#!/usr/bin/env bash
# Unit tests for merge-guard-lib.sh (no gh/network).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=scripts/merge-guard-lib.sh
source "${ROOT}/scripts/merge-guard-lib.sh"

failures=0

assert_docs_only() {
  local expect="$1"
  local label="$2"
  shift 2
  if printf '%s\n' "$@" | merge_guard_docs_tasks_only; then
    got=1
  else
    got=0
  fi
  if [ "${got}" -ne "${expect}" ]; then
    echo "FAIL ${label}: expected docs_only=${expect} got ${got}" >&2
    failures=$((failures + 1))
  fi
}

assert_state() {
  local expect="$1" name="$2" state="$3" docs_only="$4" label="$5"
  if merge_guard_required_state_ok "${name}" "${state}" "${docs_only}"; then
    got=1
  else
    got=0
  fi
  if [ "${got}" -ne "${expect}" ]; then
    echo "FAIL ${label}: expected ok=${expect} got ${got} (${name} ${state} docs=${docs_only})" >&2
    failures=$((failures + 1))
  fi
}

# docs/tasks-only PRs
assert_docs_only 1 "only sidecar dir" \
  docs/tasks/1722-files/party.go.txt \
  docs/tasks/1722-files/MANIFEST.sha256

assert_docs_only 1 "brief update under docs/tasks" \
  docs/tasks/1722-go-guest-party-count.md

# Anything under go/ or App/ (or outside docs/tasks) => not docs-only
assert_docs_only 0 "go code" go/internal/web/guest/party.go
assert_docs_only 0 "app code" App/app/routes/guest.py
assert_docs_only 0 "mixed sidecar + go" \
  docs/tasks/1722-files/foo.txt \
  go/cmd/ubyhost-web/register.go
assert_docs_only 0 "scripts change" scripts/merge-pr-on-green.sh

# go check: skipping allowed only for docs/tasks-only
assert_state 1 go pass 0 "go-pass-code-pr"
assert_state 1 go pass 1 "go-pass-docs-pr"

assert_state 1 go skipping 1 "go-skip-docs"
assert_state 0 go skipping 0 "go-skip-code"
assert_state 0 go skipping 0 "go-skip-app"

assert_state 0 go fail 1 "go-fail-docs"
assert_state 0 go pending 1 "go-pending"

if [ "${failures}" -ne 0 ]; then
  echo "${failures} test(s) failed" >&2
  exit 1
fi
echo "merge_guard_lib: all tests passed"