#!/usr/bin/env bash
# Run before adding anything to UBYHOST_GO_PATHS or UBYHOST_GO_JOB_KINDS.
#   scripts/go_switch_preflight.sh "<UBYHOST_GO_PATHS value or the entries you add>" [--e2e]
# 1. every Python METHOD /path those entries catch has a Go handler (GET and POST);
# 2. all 15 job kinds exist in Go with Python's intervals;
# 3. with --e2e: the differential harness (needs Postgres, the app venv; see docs/plans/go-parity-suite.md).
set -euo pipefail
cd "$(dirname "$0")/.."
paths="${1:?give the UBYHOST_GO_PATHS entries}"
python3 scripts/go_parity_check.py --paths "$paths" | tail -30
python3 scripts/go_jobs_parity.py | tail -20
if [ "${2:-}" = "--e2e" ]; then
  "${UBYHOST_VENV_PY:-App/.venv/bin/python}" scripts/e2e/diff_harness.py --go-paths "$paths" | tail -30
fi
