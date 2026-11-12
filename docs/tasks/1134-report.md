# 1134 report

Status: done. Blocked at step 4 (test-map.md over its 1200-token cap); orchestrator fixed it by folding the line into the glob `test_*deadline*.py` (same files, lint OK) and ran step 5: `TestCheckDeadlinesMatchesPython` and `TestWatchTitle` PASS on local PostgreSQL 16, golden fresh, 24 pytest passed.

## 1. Diff stat (ab35038..HEAD, tail)

```
8 files changed, 3962 insertions(+), 2 deletions(-)
```

Includes the brief itself (docs/tasks/1134-go-check-deadlines.md) from the brief commit.

## 2. Commands

Step 1, sha256: script `9f13c676f55c8ec2da42f50f0a682652de2529a200e3a4d331d5b58367fea64c` and golden `b48506b79d2d241835368495b1818cde4133e14c65be1718ea7cf6de52c4f422`, both match.

Step 2, sha256: watch.go `e5e49fb8...ef87a` and watch_test.go `7c66c44e...7241d04`, both match. `gofmt -l` empty, `go vet ./...` clean, `go test ./internal/calendar/ -count=1` `ok` (DB test skipped locally, no UBYHOST_TEST_DATABASE_URL).

Step 3, sha256 of the Python test `e339110e...f8f9c` matches. `pytest tests/test_check_deadlines_golden.py tests/test_deadlines.py tests/test_deadlines_golden.py -q` `24 passed`.

Step 4: the executor's one-line edit pushed test-map.md over its 1200-token cap (lint FAIL). Orchestrator fix: the Filing row now uses the glob `test_*deadline*.py` (matches the four old files and the new one). `context_lint.py` OK.

Step 5 (orchestrator, local PostgreSQL 16): `TestCheckDeadlinesMatchesPython` and `TestWatchTitle` `--- PASS`, `ok`. Golden regenerates byte-identical.

## 3. §7 acceptance

All ticked.

## 4. Deviations

test-map.md edit uses a glob instead of adding the file name (cap).

## 5. Review (Fable, full diff vs brief)

OK to mark ready; minor only. Follow-ups for a later brief: CI runs `go test ./...` without `-v`, so a skipped DB test would be silent (assert `--- PASS` in CI); seed one property name with diacritics, `&` and quotes for the `params` JSON; validation's `today` is the UTC date where Python uses `date.today()`, identical while the server clock is UTC.

## 6. Owner steps left

Merge when CI is green. Nothing calls CheckDeadlines yet (brief 1132 §10 E).
