# 1162 report

Status: review

## 1. Files changed (git diff --stat 20746d7..HEAD, last 10 lines)

```
 docs/ENVIRONMENT.md                        |   2 +-
 go/cmd/ubyhost-web/main.go                 |   8 +-
 go/cmd/ubyhost-web/main_test.go            |  10 +++
 go/internal/calendar/deadlines_job.go      | 107 +++++++++++++++++++++++
 go/internal/calendar/deadlines_job_test.go | 135 +++++++++++++++++++++++++++++
 go/internal/jobs/queue.go                  |   4 +-
 6 files changed, 262 insertions(+), 4 deletions(-)
```

## 2. sha256 per file (all match the brief)

| File | Match |
|---|---|
| go/internal/calendar/deadlines_job.go | yes (f917eb69...) |
| go/internal/calendar/deadlines_job_test.go | yes (c0a9b317...) |
| go/internal/jobs/queue.go | yes (c6ca1a2c...) |
| go/cmd/ubyhost-web/main.go | yes (4abfffc3...) |
| go/cmd/ubyhost-web/main_test.go | yes (bb459cf0...) |
| docs/ENVIRONMENT.md | yes (157d891d...) |

## 3. Commands (§6), each with tail output

- Command 1 (gofmt, vet, test, run with UBYHOST_TEST_DATABASE_URL set to local PostgreSQL 16): three `ok` lines (calendar, jobs, cmd/ubyhost-web). PASS.
- Command 2 (targeted run): `--- PASS` TestRunDeadlinesOrderMatchesPython, TestRunDeadlinesSummary, TestRunDeadlinesJobOnDatabase (DB, not skipped), TestParseGoKindsDeadlines; two `ok` lines. PASS.
- Command 3 (`python3 scripts/context_lint.py`): `context lint: OK`. PASS.

## 4. Section 7 acceptance

- [x] Command 1 prints three `ok` lines.
- [x] Each sha256 matched.
- [x] Diff lists only §3 paths (see stat above).
- [x] App, go.mod, go.sum: no diff (output: []).
- [x] "deadlines" count: main.go 2, queue.go 2.
- [x] No slog line with url or err text (output: [71:		slog.Error("deadline watch failed", "error", fmt.Sprintf("%T", watchErr))
81:		slog.Error("filing watchdog failed", "error", fmt.Sprintf("%T", err))]).
- [x] context lint passes.
- [x] Six step commits (1162 step 1 to step 6); nothing pushed.

## 5. Deviations

- §7 base: `git log --grep=^Brief.1162` finds nothing (the brief commit subject is "docs(tasks): 1162 brief"), so the diff base used was 20746d7, the brief commit.
- Command 1 was run with UBYHOST_TEST_DATABASE_URL set so the DB test ran locally instead of skipping.
- The DB test drops table data_subject_request in the throwaway local test DB, as the brief specifies.

## 6. Questions

None.

## 7. Owner steps left

None for this brief. Switching `deadlines` to Go is the owner step in the brief (after merge).
