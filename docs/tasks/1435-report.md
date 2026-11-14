# 1435 report: Go port of the Leon setup wizard pages

Status: review. One big PR mode: commits on the current branch, nothing pushed, no PR opened.

## Files changed

Commit `3419b3886 1435 step 1` adds 12 files, all from the sidecars, sha256 verified against the brief table:
App/scripts/leon_golden.py, App/tests/test_go_ai_leon.py,
go/internal/web/ai/leon_catalog.json, leon_extra.go, leon_facts.go, leon_facts_test.go, leon_handlers.go, leon_handlers_test.go, leon_i18n.json, leon_i18n_keys.txt, leon_templates/leon_setup.tmpl, testdata/leon_golden.json.
Plus this report and the brief Status line (todo to review).

## Commands (last lines)

- `leon_golden.py --check`: rc=0, no `stale:` line.
- gofmt, `go build ./...`, `go vet ./internal/web/ai/`: no output, rc=0.
- `go test ./internal/web/ai/ -run Leon -count=1 -v` (UBYHOST_TEST_DATABASE_URL set): 11 PASS, 0 SKIP, `ok ... 7.944s`. Includes all 7 named Leon tests.
- `pytest tests/test_go_ai_leon.py -q -rs`: `1 passed in 0.42s`, 0 skipped.
- `context_lint.py`: `context lint: OK`.

## Section 7

- [x] 12 sha256 values match
- [x] golden `--check` no stale line
- [x] gofmt, build, vet clean; 7 Leon tests PASS, 0 skipped
- [x] pytest 1 passed, 0 skipped
- [x] only section 3 paths changed
- [ ] commit "1435 step 4" and "1435 step 5": step 4 changed no file, so no commit; step 5 committed as below

## Deviations

- Used PostgreSQL port 5637, data dir /var/tmp/pg1435 (task message), not the brief's 55432 and /var/tmp/pgai. Stopped and deleted after the run.
- Created App/.venv (untracked, not committed).
- Step 4 has no commit (no file change).

## Questions

- Brief 1435 says nothing under `/apartments/*/leon` is in `UBYHOST_GO_PATHS`. Brief 1437 must list these paths; a broad `/apartments/*` entry would send them to Go at deploy.

## Owner steps left

None.
