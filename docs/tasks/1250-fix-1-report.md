# 1250-fix-1 report

Status: review. Branch task/1250-go-guide-import. Push and PR not done (owner asked for no push).

## Files changed
- go/internal/guideimport/job.go (edit 1: cancelled fetch fails row; edit 2: dropped as sorted JSON)
- go/internal/anthropic/client.go (retryDelay for retry-after, 10 s cap)
- go/internal/guideimport/job_db_test.go (append: 4 Postgres tests and helpers)
- go/internal/anthropic/ai_test.go (append: retry-after test)
- docs/tasks/1250-report.md (one fix-1 line)
- docs/tasks/1250-fix-1-report.md (this file)
- docs/tasks/1250-fix-1-go-guide-import-review.md (Status: review)

## sha256 after (all four match §3)
- job.go 72b40158dc7cd01dd430c00a1206db9511e1229f341604ab6799572765dc012b
- client.go 2bd14d7ec29ec0d09733be24acca827484e6acc3de7590db1e95501a5cc6dabe
- job_db_test.go 951f798899318d350e3cc63a8a6f4efb6433dc7dce789316a71d2a82112d6087
- ai_test.go 5785d9058dc3d448adf30f7f97253e2697b1c0a34e538904f19ec16690153e79

## Commands (run from go/, Postgres 16.15 on a local socket)
- `gofmt -l internal cmd`: no output.
- `go vet ./internal/guideimport/... ./internal/anthropic/...`: no output, exit 0.
- `go test -count=1 ./internal/guideimport/... ./internal/anthropic/... ./cmd/ubyhost-web/...`:
  ```
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guideimport	3.514s
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic	0.017s
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.007s
  ```
- `go test -v -run 'MergeWriteRules|InputTooLarge|StaleCutoff|CancelledFetch|RetryAfter'`: all 5 PASS, no SKIP
  (TestMergeWriteRules, TestPendingInputTooLargeFailsAtOnce, TestFetchAfterStaleCutoffDropsResult, TestCancelledFetchFailsRow, TestClientHonoursRetryAfter).

## Section 7
- [x] The four sha256 "after" values match.
- [x] The three commands are clean; the five new tests ran, 0 skipped.
- [x] git diff lists only the §3 files plus the fix-1 report and the brief status.

## Deviations
- Edits were applied with a script in /var/tmp/1250fix-exec/apply.py (each OLD asserted to occur once), not retyped.
- Commits follow brief steps 1 to 5 per file, not one commit per tool call.
- Commit trailer: Co-Authored-By uses Claude Haiku 5.5 (the executor's model, per the session attribution rule), not Opus 5.5 as the launch message said.
- No PR opened and no push (owner instruction). Postgres was stopped at the end.

## Questions
- None.

## Owner steps left
- Review this branch, then push and open the PR (or ask the orchestrator to).
