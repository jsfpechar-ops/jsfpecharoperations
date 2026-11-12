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

Step 4: `python3 scripts/context_lint.py` FAIL: `ERROR docs/context/test-map.md: ~1208 tokens > cap 1200`. The step 4 edit added 31 bytes to test-map.md (4802 to 4833) and pushed the file over the cap. Not fixed: compacting test-map.md is outside the brief's one-line edit.

Step 5: not run (stopped at step 4).

## 3. §7 acceptance

Ticked: the sha256 checks; gofmt, vet and calendar test; pytest files; commits 1 to 4. Not ticked: context_lint (fails); step 5 (not run); the `git diff --stat` line lists the §3 paths plus the brief.

## 4. Deviations

Done: steps 0 to 4 (commits 1 to 4). Left: step 5 (local PostgreSQL run), and the lint fix.

## 5. Questions

Owner or orchestrator: compact docs/context/test-map.md under the cap (or raise it) so lint passes, or accept the step 4 edit as is? Lint currently fails on main-plus-branch with this brief's line.

## 6. Owner steps left

None until lint passes. Nothing calls CheckDeadlines (brief 1132 §10 E).
