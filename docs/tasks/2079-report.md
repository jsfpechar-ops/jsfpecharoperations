# 2079 report: unclaimed job alert

Status: review

## Changed paths

- `go/internal/jobs/queue.go`: added configured-kind scanning for overdue rows without a valid lease, Python-equivalent lateness thresholds, five-minute checks in `Run`, sorted warning logs, and best-effort existing alert creation.
- `go/internal/jobs/queue_test.go`: added fixed-time coverage for unleased and expired-lease rows, active leases, the exact threshold, future retries, terminal rows, unconfigured kinds, alert deduplication, and recovery resolution.

## Commands and results

- `gofmt -w internal/jobs/queue.go internal/jobs/queue_test.go` — passed.
- Required focused Go test command with isolated PostgreSQL — passed: `TestUnclaimedJobAlert`, `TestClaimHonoursKinds`, and `TestRaiseFailedSubmitIsCritical` (3 passed, 0 skipped).

  ```text
  --- PASS: TestRaiseFailedSubmitIsCritical (0.32s)
  PASS
  ok   github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs  1.652s
  ```

## Acceptance

- [x] Eligible due unleased and expired-lease kinds are selected; active lease, exact threshold, future retry, terminal row, and unconfigured kind are excluded.
- [x] Repeated alert opens dedupe to one alert; successful processing resolves it.
- [x] Alert-check errors are logged and do not stop normal job draining.

## Deviations and owner steps

The fixture uses distinct timestamp and worker parameters to preserve the queue's text timestamp representation. No live data, deployment, push, PR, or merge used. Owner review: inspect one old unclaimed row and one actively leased row.
