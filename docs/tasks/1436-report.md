# 1436 report: Go port of Leon's setup test message

Status: review

## Files changed (commits 1ede3baa step 1, ecd52892 step 4, step 5)

Ten §3 paths: App/scripts/leon_try_golden.py, App/tests/test_go_ai_leon_try.py, go/internal/web/ai/leon_core.go, go/internal/web/ai/leon_extra.go (replaces 1435's empty file), go/internal/web/ai/leon_facts_catalog.json, go/internal/web/ai/leon_guest_i18n.json, go/internal/web/ai/leon_prompt.txt, go/internal/web/ai/leon_try.go, go/internal/web/ai/leon_try_test.go, go/internal/web/ai/testdata/leon_try_golden.json. go/go.mod and go/go.sum unchanged. Nothing pushed.

## Commands (last lines)

- Step 1 sha256: all 10 match the §4 table.
- Step 2 `leon_try_golden.py --check`: exit 0, no output (no stale line).
- Step 4 gofmt, `go build ./...`, `go vet ./internal/web/ai/`: no output.
- Step 4 `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55436/postgres go test ./internal/web/ai/ -run Leon -count=1 -v`: `--- PASS` for all 16 Leon tests (7 from 1435, 6 new, plus the guide Leon tests); last line `ok github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai 25.310s`. SKIP count: 0.
- Step 5 `pytest tests/test_go_ai_leon.py tests/test_go_ai_leon_try.py -q --tb=short -rs`: `2 passed in 0.85s`. SKIP count: 0.
- `python3 scripts/context_lint.py`: `context lint: OK`.

## §7 acceptance

- [x] 10 sha256 values match.
- [x] golden --check: no stale line, exit 0.
- [x] gofmt, build, vet silent; Leon tests PASS, 0 skipped.
- [x] pytest 2 passed, 0 skipped; go.mod and go.sum unchanged.
- [x] Only §3 paths changed.
- [x] Commits present: "1436 step 1", "1436 step 4", "1436 step 5".

## Deviations

- PostgreSQL ran on port 55436 with data dir /var/tmp/pg-1436 (per run rules), not 55432 and /var/tmp/pgai.
- App/.venv was missing and was created.
- Step 4 changed no files; committed as an empty commit so the "1436 step 4" acceptance check passes.
- Brief line 3 (Status) set to `review` per §9.

## Known difference (list in PR, per §2)

A non-ASCII decimal digit counts as an ASCII digit in the phone and long-ID matchers, and a card id such as `c٣` is not matched (Python reads it as 3).

## Questions

None.

## Owner steps left

None.
