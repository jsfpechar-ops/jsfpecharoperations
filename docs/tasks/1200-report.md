# 1200 report

Status: review

## 1. Files changed (`git diff --stat b84a765 HEAD`)

```
App/app/scheduler.py                       | 72 +++++------------------
App/tests/test_filing_watchdog.py          | 94 ++++++++----------------------
App/tests/test_p1_review.py                |  3 +-
App/tests/test_scheduler.py                | 33 +++++++----
docs/ENVIRONMENT.md                        |  2 +-
go/internal/calendar/deadlines_job.go      |  4 +-
go/internal/calendar/deadlines_job_test.go |  2 +-
7 files changed, 66 insertions(+), 144 deletions(-)
```

Commits: `1200 step 1` to `1200 step 7` (7 commits, one per patch block, on top of b84a765).

## 2. Commands

- sha256 (step 8): all 7 hashes match the brief.
- pytest (§6, first command): `773 passed, 18 skipped, 3 warnings in 43.83s`. Skips are the expected playwright and PostgreSQL-only job-queue tests.
- ruff (§6): `All checks passed!`
- go vet: no output (clean).
- go test ./internal/calendar: `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar 0.028s`
- context_lint: `context lint: OK` (warnings only: brief 1167/0784/0851 name overlapping tests; 4 App commits after status.md update)
- grep `_job_deadlines\b|_filing_heartbeat`: no matches.
- `"deadlines": _job_deadlines_go_only` in scheduler.py: one line (514).

## 3. §7 acceptance

- [x] `git diff --stat` lists exactly the §3 files
- [x] step 8 hashes match
- [x] §6 tests, ruff, Go vet and calendar tests pass, lint OK, grep empty
- [x] `_job_deadlines_go_only` mapping present

## 4. Deviations

- The awk extract wrote patch files to the session scratchpad instead of `/tmp/p1200.diff` (scratchpad rule). Content identical.
- Not pushed and no PR opened (executor rule: the owner or orchestrator pushes).

## 5. Questions

None.

## 6. Owner steps left

1. Check on the server that `deadlines` is in both `UBYHOST_JOB_QUEUE_KINDS` and `UBYHOST_GO_JOB_KINDS` (see brief §Owner steps).
2. Push the branch and open a draft PR; the orchestrator reviews it (Tier A: Fable diff review before ready).
