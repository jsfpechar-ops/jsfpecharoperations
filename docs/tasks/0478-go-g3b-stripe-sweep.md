# 0478: Go G3b: the stripe_sweep job in Go
Status: todo
Depends on: 0476 (#631) | Base commit: main | Branch: task/0478-go-g3b-stripe-sweep
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Plan v4 step 15 (G3), second job. `stripe_sweep` becomes a Go-owned kind next to `billing_snapshot`. Despite its name it makes no outbound call: it expires overdue payment requests and prunes old webhook dedupe rows. Same rows, same audit lines as Python. Rollback is removing the kind from `UBYHOST_GO_JOB_KINDS`.
## 2. Context
- Python job: `App/app/scheduler.py` `_job_stripe_sweep` (line 432), interval `24 * 60` (line 101). `today` is `datetime.date.today()`: the server's local date (production runs UTC; use the UTC date in Go).
- Expire: `App/app/payment_request.py` `expire_sweep` (line 144) and `set_status` (lines 105-126). For each row with `status IN ('sent','awaiting_payment') AND expires_at < <today YYYY-MM-DD>` (plain text comparison, keep it): `UPDATE payment_request SET status = 'expired', paid_at = COALESCE(NULL, paid_at), updated_at = <now> WHERE id = $1 AND status = <current>`; only when exactly 1 row changed, insert audit `action='payment_request_status'`, `detail='id=<id> <current>->expired'`, `owner_user_id=<owner>`. Count = rows selected (Python returns `len(expired)`).
- Prune: `App/app/stripe_connect.py` `sweep_webhook_events` (line 365): `DELETE FROM stripe_webhook_event WHERE created_at < <today minus 30 days, YYYY-MM-DD>`; when the count is above 0, audit `action='stripe_webhook_sweep'`, `detail='deleted=<n>'`, owner NULL.
- Audit row (`App/app/db.py` `audit`, line 2138, table in `App/migrations_pg/00001_baseline.sql` line 332): `at=<now>`, `actor='host'` (the scheduler has no signed-in actor), `actor_user_id` and `impersonator_user_id` NULL. Timestamps: `jobs.Now(0)` form.
- Go pattern to copy: `go/internal/billing/snapshot.go` (+ test), `go/internal/jobs/queue.go` (`jobNames` line 115), `go/cmd/ubyhost-web/main.go` (`goIntervals`, `goHandlers`, `parseGoKinds`, lines 212-240). Alert job name in `App/app/host_i18n.py` line 667: `payment check`.
## 3. Files
New: `go/internal/payments/sweep.go` (+ `sweep_test.go`). Edit: `go/internal/jobs/queue.go` (one map entry), `go/cmd/ubyhost-web/main.go`, `docs/ENVIRONMENT.md` (the `UBYHOST_GO_JOB_KINDS` row: "Today `billing_snapshot` and `stripe_sweep`."). Write `docs/tasks/0478-report.md`.
## 4. Steps
1. `sweep.go`: `Sweep(ctx, pool, today time.Time, now string) (expired, deleted int, err error)`: both parts in one transaction, exactly the SQL and audit rows of section 2.
2. `main.go`: add `stripe_sweep` to `goIntervals` (24*60) and `goHandlers` (handler returns `expired + deleted`, logs both counts in the run line if the handler shape allows, otherwise rows only). `parseGoKinds` accepts any key of `goHandlers` instead of the hard-coded name, and its error lists the supported kinds.
3. `queue.go`: `jobNames["stripe_sweep"] = "payment check"`.
4. Test (PostgreSQL from `UBYHOST_TEST_DATABASE_URL`, schema applied as in `snapshot_test.go`): requests in `draft`, `sent` (expired yesterday), `awaiting_payment` (expired yesterday), `sent` (expires today), `paid` (expired) give 2 expired, with 2 audit rows of the exact detail; webhook rows 31 and 29 days old give 1 deleted and one `deleted=1` audit row; a second run changes nothing and writes no audit row. `parseGoKinds("stripe_sweep, billing_snapshot")` works, an unknown kind fails.
## 5. Do not touch
Every Python file (Python already skips Go kinds via 0476), `billing/`, `secure/`, `schema/`, compose, goose files.
## 6. Commands
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && UBYHOST_TEST_DATABASE_URL=postgresql://postgres:ubyhost@127.0.0.1/ubyhost_test go test ./... -count=1 2>&1 | tail -30` (if local PostgreSQL is down, say so and rely on CI).
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
The Go sweep writes the same rows and audit lines Python would on the same data. `git diff --stat origin/main` lists only section 3 files.
## 8. Stop and ask
Stop if `payment_request` or `stripe_webhook_event` columns differ from section 2, or if a step needs a Python or schema change.
## 9. Report
`docs/tasks/0478-report.md`: command tails and the diff stat.
