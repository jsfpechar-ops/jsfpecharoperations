# 1330 report: Go stay fee actions and CSV

Status: review

## 1. Files changed (`git diff --stat a83df54..HEAD`)

10 files, 7988 insertions, all new: the §3 paths plus the brief itself.

## 2. Commands (last 5 lines)

- sha256 of brief folder (9 files): all `OK`.
- sha256 of repo copies after step 4: all `OK`.
- `gofmt -l internal/web/stayfees cmd/ubyhost-web && go vet ./internal/web/stayfees/ ./cmd/ubyhost-web/`: no output.
- `go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 -v` (grep filter): `--- PASS: TestActionsMatchPython`, `--- PASS: TestCSRFRequired`, `--- PASS: TestRoutesNeedNoPool`, `ok github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stayfees 1.411s`, 10 PASS lines in cmd/ubyhost-web, `ok .../go/cmd/ubyhost-web 0.010s`. No SKIP, no FAIL.
- `App/.venv/bin/python scripts/stay_fee_actions_golden.py`: `wrote .../actions_golden.json`, `wrote .../i18n.json`. `git status` after it: only the two new Python files (JSON byte-identical).
- `App/.venv/bin/python -m pytest tests/test_go_stay_fee_actions_golden.py -q --tb=short -x`: `1 passed in 1.57s`.
- `python3 scripts/context_lint.py`: `WARN 1 commit(s) touched App/ after the last status.md update` (expected for this brief), `next free: task 1331 | migration 0046`, `context lint: OK`.

## 3. §7 acceptance

- [x] sha256 in brief folder and in repo after step 4.
- [x] gofmt and go vet print nothing.
- [x] Go tests PASS, `TestActionsMatchPython` and `TestCSRFRequired` ran (not skipped).
- [x] Golden script leaves `git status` clean; pytest passes.
- [x] `git diff --stat a83df54..HEAD` lists only §3 paths and the brief.
- [x] context lint ends `context lint: OK`.

## 4. Deviations

Done: steps 1 to 5. Left: none.

Deviations from Python, as in brief §2 (recorded in code and for the PR):
1. `POST /stay-fees/{id}/paid` on a property not owned by the host (or missing): Python 500, Go redirects to `/stay-fees` with `flash.error.no_such_apartment`.
2. Non-ASCII digits: Go accepts ASCII digits only (non-ASCII month falls back to default; non-ASCII or overflowing id is "not found").
3. Signed-out non-numeric path id: Go redirects to `/login` first (Python 422 comes once signed in).
4. Identity-hidden CSV branch is forced by stub in golden script and Go test (not reachable by a real session today).

## 5. Questions

None.

## 6. Owner steps left

PR body facts: "No new outbound request. No new personal-data field. Routes are registered but off: Caddy routes only UBYHOST_GO_PATHS to Go."

1. Wait for CI green on the draft PR, then merge with `scripts/merge-pr-on-green.sh`. The merge switches nothing on.
2. Later and separate: add the paths to `UBYHOST_GO_PATHS` (not part of this brief).
