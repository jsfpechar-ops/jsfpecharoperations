# 2079: Raise the existing alert for unclaimed jobs

Status: todo
Depends on: none | Base commit: f6be14e46b68677884e26533eef674b15cb89f6a | Branch: task/2079-go-unclaimed-job-alert
Executor: Luna | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Restore the Python warning for a due queue row left unclaimed. Reuse the existing alert key and normal recovery path.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests. Review the named anchors against the approved base or its prerequisite tip.

- `App/app/jobqueue.py:144`

  ```text
  def stuck_kinds() -> list[str]:
  ```
- `App/app/jobqueue.py:168`

  ```text
  def watch_stuck() -> list[str]:
  ```
- `go/internal/jobs/queue.go:183`

  ```text
  func Run(ctx context.Context, pool *pgxpool.Pool, kinds []string, handlers map[string]Handler, intervals map[string]int) {
  ```
- `go/internal/jobs/queue.go:141`

  ```text
  func RaiseFailed(ctx context.Context, pool *pgxpool.Pool, kind string) error {
  ```

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/internal/jobs/queue.go` | edit | Check unclaimed rows from the Go poll lifecycle. |
| `go/internal/jobs/queue_test.go` | edit | Verify thresholds, leases, dedupe and recovery. |

The executor report and brief status follow section 9.

## 4. Steps

1. Add a check for the oldest `run_at` per configured kind with both terminal timestamps NULL and no valid lease. Reuse the existing lease constant and configured interval map. Apply Python's `late_after_minutes` function with the two-hour ceiling and strict older-than comparison. Sort names before logging.
2. Wire the check into `Run` at the Python cadence so it gets a turn when the worker is busy as well as idle. Call the existing `RaiseFailed` with the same kind and dedupe key. Log errors safely and leave the normal successful processing path responsible for resolution.
3. Add `TestUnclaimedJobAlert` with a fixed time and synthetic rows for a due unleased job, an active lease, an expired lease, exact threshold, a future retry, terminal rows and an unconfigured kind. Verify two workers open one alert and a success resolves it. Run section 6.

## 5. Do not touch

Keep schema, queue lifecycle, retry delays, enabled job kinds, alert copy and filing watchdog unchanged.

## 6. Commands

Run from the indicated directory with pipeline failure reporting on. Expect the listed cases to run and pass. Required database and browser cases must show zero skips.

```sh
cd go && go test ./internal/jobs/ -run 'UnclaimedJobAlert|Claim|Queue|RaiseFailed' -count=1 -v 2>&1 | tail -30
```

Use fixture credentials and record only pass/fail, counts, and redacted diagnostics.

## 7. Acceptance

- [ ] Only eligible unclaimed rows open the existing alert.
- [ ] Both slots dedupe the alert, and a successful job resolves it.
- [ ] An observer failure leaves job handling operational.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2079-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/internal/jobs/queue.go`

## Owner steps

1. Review the result for an old unclaimed row and an actively leased row.
