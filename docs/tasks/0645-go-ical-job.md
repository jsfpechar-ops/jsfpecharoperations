# 0645: Go: the `ical` job kind (sync every active feed), off in production
Status: todo
Depends on: 0644 | Base commit: task/0644-go-ical-sync-feed | Branch: task/0645-go-ical-job
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Last slice of porting the `ical` job to Go: `sync_all` and `import_paused` (`App/app/icalsync.py` 997-1058) plus job kind `ical` in the Go service. It runs only when the owner lists `ical` in `UBYHOST_GO_JOB_KINDS`, which production does not, so nothing changes in production.
## 2. Context
- Read `App/app/icalsync.py` 997-1058, `App/app/scheduler.py` 139-151 (`_job_sync_calendars`), `App/app/billing.py` 49-50 and 140-152 (paused rule: billing enabled via `UBYHOST_BILLING_ENABLED` in `1,true,yes` case-insensitive, and `billing_account.status = 'paused'` for the apartment's owner; no account or no owner means not paused).
- Go: `go/cmd/ubyhost-web/main.go` 216-245 (`goIntervals`, `goHandlers`, the `submit` handler is the model), `go/internal/jobs/queue.go` 115 (`jobNames`, failure alert and `job_last_ok` are already done by the jobs package), `go/internal/ical/syncfeed.go` (`SyncFeed`, `Feed`), `reconcile.go` (`recordFeedFailure`), `fetch.go` (`FetchOptions`), `feedurl.go` (`AllowPrivate(getenv)`; the real resolver: see how `fetch_test.go` or `ResolveTarget` builds one, use `net.DefaultResolver` if it satisfies `Resolver`).
- **Traps:**
  - Only the job path: no `apartment_id`/`owner_user_id` arguments, no `sync_owner_if_stale` (that is a web request path, ported later with the APIs).
  - Feed query: `f.active = 1 AND a.active = 1`, all `ical_feed` columns `Feed` needs. Paused apartments are skipped and not counted; the paused answer is cached per apartment for one run.
  - A Go error from `SyncFeed` is logged, then `recordFeedFailure(feed, err)`, counted in `errors`; stats with `Error` set count in `errors` too. Otherwise add created/updated/cancelled and count the outcome as `not_modified`, `unchanged` or `changed`.
  - After the loop write setting `last_ical_sync` = `ubyport.UTCNow()` with the same upsert as Python `db.set_setting` (`App/app/db.py` 2110), and log one `ical_sync_run` line with the same counts.
  - Interval: `UBYHOST_ICAL_POLL_MINUTES`, default 60, as Python `config.ICAL_POLL_MINUTES`; read it once when building `goIntervals`, or keep 60 if that map must stay a literal and say so in the report.
  - Python pings `HEARTBEAT_ICAL_URL` after a good run; the Go `submit` kind does not ping either. Do not add it; list it in the report.
  - Handler returns the number of feeds read and the error only when the feed query itself fails.
## 3. Files
- New `go/internal/ical/syncall.go` + `_test.go`: `type SyncTotals`, `SyncAll(ctx, pool, getenv, opt FetchOptions) (SyncTotals, error)`, unexported `importPaused`. DB tests with feeds whose URL fails fast (e.g. a blocked private address with `AllowPrivate` false): paused skipped when billing on and not when off, an error feed counted and its row marked `error`, setting written. Reuse the test pool helper in `reconcile_test.go`.
- Edit `go/cmd/ubyhost-web/main.go`: `ical` in `goIntervals` and `goHandlers`.
- Edit `go/internal/jobs/queue.go` line 115: add `"ical": "calendar sync"` to `jobNames` (copy from `App/app/host_i18n.py` 660).
- Edit `docs/ENVIRONMENT.md` line 51: the kinds list now reads `billing_snapshot`, `stripe_sweep`, `submit` and `ical`.
- Write `docs/tasks/0645-report.md`.
## 4. Steps
1. `SyncAll` and tests.
2. Wire the kind; `go build ./...`; existing `go/cmd` and `jobs` tests still pass.
3. Commit: `0645: Go job kind ical syncs every calendar feed (off in production)`.
## 5. Do not touch
`App/` (all), `go/internal/ubyport/`, other `go/internal/` packages except `ical` and the one `jobs` line, compose, CI, `.env` files, templates/CSS/JS.
## 6. Commands
- Local Postgres: `pg_ctlcluster 16 main start; su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'ubyhost'\""`, then `export UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres`.
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go build ./... && go test ./internal/ical/ ./internal/jobs/ ./cmd/... -count=1 2>&1 | tail -30`.
- From the repo root: `git diff --stat task/0644-go-ical-sync-feed`, `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
The diff against the 0644 branch lists only section 3 files and this brief. gofmt, vet, build and tests pass with the DB URL set, 0 skipped in the new tests.
## 8. Stop and ask
Stop if wiring needs a compose, CI or env change in production, or a new dependency.
## 9. Report
`docs/tasks/0645-report.md`: command tails, diff stat, any difference from Python, and the owner steps to switch `ical` to Go later (not to be done now).
