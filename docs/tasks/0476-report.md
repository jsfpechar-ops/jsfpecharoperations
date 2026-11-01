# 0476 report: Go G3a billing_snapshot

Status: review

## Files changed
Go: `go/internal/billing/quote.go`, `quote_test.go`, `snapshot.go`, `snapshot_test.go`, `testdata/quote_fixtures.json`; `go/internal/jobs/queue.go`, `queue_test.go`; `go/cmd/ubyhost-web/main.go`.
Python: `App/scripts/billing_fixtures.py`, `App/tests/test_billing_fixtures.py`, `App/app/config.py` (GO_JOB_KINDS), `App/app/jobqueue.py` (claim skips Go kinds), `App/app/scheduler.py` (start refuses GO kinds outside JOB_QUEUE_KINDS), `App/tests/test_job_queue.py` (2 tests).
Other: `deploy/lightsail/docker-compose.yml` (one line in ubyhost-go), `docs/ENVIRONMENT.md` (one row).

## Commands (last 5 lines)
Go vet and gofmt: exit 0.
```

```
Go tests (`UBYHOST_TEST_DATABASE_URL` set, local PostgreSQL 16): exit 0, 17 PASS, 0 FAIL.
```
--- PASS: TestLegacyKeyMatchesFixture (0.00s)
=== RUN   TestNegativeCases
--- PASS: TestNegativeCases (0.00s)
PASS
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure	0.012s
```
Python (`test_billing_fixtures`, `test_job_queue`, `test_billing_analytics`, with PostgreSQL URL): exit 0.
```
SKIPPED [1] tests/test_job_queue.py:69: SQLite registration rules
SKIPPED [1] tests/test_job_queue.py:78: SQLite registration rules
42 passed, 3 skipped in 12.60s
```
context_lint: OK.

Fixture count: 1120 quote cases and 18 monthly cases (1138 total), half cases included.

## Section 7
- [x] Go Quote equals Python on every fixture (Go test over committed JSON).
- [x] Empty `UBYHOST_GO_JOB_KINDS`: Python claim SQL only gains a clause when the set is non-empty.
- [x] Go claims only its kinds (Go and Python tests).
- [x] Snapshot prices checked against the fixture values (Go test, founder yearly and max monthly with discount and carry). Not a live diff against Python output.
- [x] diff stat lists only section 3 files (checked before push).

## Deviations
- Step 1 and step 2 are in one commit (e73c2f2): fixture generator, drift test, and JSON.
- Go handler returns `(int, error)` so the log line has `rows=`; brief said `error`.
- Test database helper is folded into `snapshot_test.go` and `queue_test.go` (no extra file). Each test creates a throwaway database from `UBYHOST_TEST_DATABASE_URL` and drops it.
- Compose and ENVIRONMENT: the table default cell says "empty"; the sentence starts "PostgreSQL only.".
- Snapshot month is UTC (brief); Python uses local `date.today()`. Same on a UTC server.
- Alert: Go does UPDATE then INSERT, not ON CONFLICT. A racing duplicate could log an error, and the next run fixes it.
- Local sandbox: I set the local postgres password to `ubyhost` and created `ubyhost_test` so the tests could run. No repo change.
- Python run shows 3 SQLite-only skips (`test_job_queue.py`), expected on PostgreSQL.

## Questions
None.

## Owner steps left
1. Merge the PR after CI is green with `scripts/merge-pr-on-green.sh` (owner only).
2. Production: set `UBYHOST_JOB_QUEUE_KINDS` to include `billing_snapshot`, then set `UBYHOST_GO_JOB_KINDS=billing_snapshot`, then redeploy `ubyhost-go`. Rollback: unset `UBYHOST_GO_JOB_KINDS`.
