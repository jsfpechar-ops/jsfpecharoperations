# 1816: job table: Go purge (done 7 days, dead 30 days) and autovacuum settings

Status: todo
Depends on: none | Base commit: current tip of the working branch | Branch: task/1816-job-table-purge-autovacuum
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (it deletes rows of the queue that runs `submit`; a new goose migration). Writer: Sonnet. Review: the full diff of every file in §3 by a fresh reviewer.

> Work on the current branch. After each step that changes a file, commit with the message `1816 step k`. Never push, never open a PR unless the owner's chat says so.

## 1. Objective

The Go service deletes finished `job` rows after 7 days and dead (failed) rows after 30 days, in small batches, and the `job` table gets its own autovacuum settings, so the table stays at a flat size at any number of properties.

## 2. Context (findings of the brief writer; each was checked by grep on this branch)

**Two facts that differ from the plan text in `docs/plans/optimization-wins.md` §1/§6. Do not "fix" them, just know them.**

1. Rows are NOT only never deleted. Python already purges: `App/app/jobqueue.py` `purge()` (hourly, called by `_job_queue` in `App/app/scheduler.py:711-721`) deletes done and dead rows older than `KEEP_DONE_DAYS = 7`. 11,476 rows is consistent with that: `push` runs every minute (about 1,440 rows a day, 7 days = about 10,000 rows). Go has NO purge (`grep -rniE "delete from job" go/` finds nothing). Python is being retired ([go-first](../context/go-first.md)), so the purge must exist in Go before the Python worker goes. Python deletes dead rows after 7 days; the owner wants 30, so the Python purge changes too (step 3), otherwise it would defeat the 30 days.
2. Rows grow with the number of job KINDS and run frequency, not with the number of properties. One open row per kind (index `job_one_open_per_kind`). At 2,000 properties the table is about as big as today. The purge still matters (steady state, bloat), but the "millions of rows" estimate is wrong.

**Claim.** Already `FOR UPDATE SKIP LOCKED`: `go/internal/jobs/queue.go:57-70` (`Claim`) and the twin in `App/app/jobqueue.py:80-90`. Do NOT change either.

**Schema** (`App/migrations_pg/00003_job.sql`): `job(id, kind, run_at, payload, attempts, locked_at, locked_by, done_at, dead_at, error, created_at)`, all timestamps are TEXT in the form `2026-11-16T10:00:00+00:00` (UTC). Text comparison equals time comparison. `jobs.Now(delta)` in `go/internal/jobs/queue.go` builds that text. Index `job_due` and the unique index cover open rows only. An open row (`done_at IS NULL AND dead_at IS NULL`) is never deleted.

**Every reader of `job` rows found** (grep over `go/`, `App/app/`, `App/scripts/`, `scripts/`, `deploy/`; tests are not readers):

| # | Reader (file:line) | What it reads | Verdict for a 7 day (done) / 30 day (dead) delete |
|---|---|---|---|
| 1 | `go/internal/jobs/queue.go:57-70` Claim | open rows only | safe: finished rows are never read |
| 2 | `go/internal/jobs/queue.go:82,96,110` Finish/Fail | updates by `id AND locked_by`, a leased open row | safe: only open rows |
| 3 | `go/internal/scheduler/scheduler.go:265` Enqueue | INSERT with `ON CONFLICT (kind) WHERE done_at IS NULL AND dead_at IS NULL DO NOTHING` | safe: the unique index covers open rows only, so deleting finished rows creates no duplicate and loses no dedupe |
| 4 | `App/app/jobqueue.py:59` enqueue | same INSERT | safe, same reason |
| 5 | `App/app/jobqueue.py:80-90,104-127` claim/finish/fail | open or leased rows | safe |
| 6 | `App/app/jobqueue.py:148-160` `stuck_kinds` | `MIN(run_at)` of open, unleased rows | safe: open rows only |
| 7 | `App/app/scheduler.py:652-662` `watch_go_scheduler` | per kind `MAX(created_at)`, `MAX(done_at)`, `MAX(created_at)` of rows whose payload is not the watch payload, count of open rows | safe, checked: it compares these with `_go_due_since` which looks back at most `2 * interval + 1` minutes. The longest interval is 24 h (48 h + 1 min), far below 7 days. `go_last` is the newest Go row over all kinds and `push` runs every minute. A kind whose finished rows were all deleted and that has no open row reads as "left out" and is enqueued: the correct, safe result. |
| 8 | Admin Operations page "last success" | reads `settings` rows `job_last_ok:<kind>` (`App/app/scheduler.py`, `JOB_LAST_OK_PREFIX`), NOT the `job` table | not a reader of `job` |
| 9 | `submit` (UbyPort filing) | no code reads the `job` table to decide "was this stay already submitted". Filing state lives in `submission`/`guest` (`submit_state`). No `payload` carries an idempotency key (payload is `'{}'` or the watch payload). | safe: `submit` job rows are only a trigger. Rule 1 holds: this brief does not touch filing code. |
| 10 | ical, billing_snapshot, stripe_sweep, deadlines, posthog, meta_capi, push | no reader of old job rows for last-run or dedupe (same greps) | safe |

All kinds are therefore purged with the same periods. No kind is excluded.

**Open question for the orchestrator (does not block; the executor does not decide it):** `grep` found no other reader, but the writer could not read production. If the owner wants proof before deploy, run on the server `SELECT kind, count(*), min(created_at) FROM job GROUP BY kind` and confirm the oldest finished row is about 7 days old (that confirms the Python purge already works). The brief changes nothing based on the answer.

**Personal data.** `job.error` holds an exception class and message (300 characters at most) and may name an address. It is already documented in `App/app/retention.py:37-38` ("purged with the row 7 days after done/dead (jobqueue.purge)"). `payload` holds no personal data. No new field, so no new retention step, but the dead period changes from 7 to 30 days: update that comment and add one row to `docs/privacy/RETENTION.md`.

**Rules that apply** (AGENTS.md): 1 filing first (not touched); 2 privacy (above; no new outbound request); 3 no secrets or real data; 5 SQL through the repo helpers: in Go that is `pgxpool` with `$n` placeholders (as `queue.go`), in Python `db.execute` with `?`; Postgres-portable, no triggers; a schema change is a new `App/migrations_pg/` file, additive, and `App/app/migrations/` is frozen; 11 Go first. Rules: database (`docs/context/rules.md` Database): keep each write short, never hold a long lock. Go-first: the Python edit in step 3 is category 1 (port plumbing: a Go purge needs the Python purge to agree on the dead period). If the reviewer disagrees, drop step 3 and say so in the report.

**Anchors (grep each with `grep -nF`; not found: STOP).**
- `App/app/jobqueue.py`: `KEEP_DONE_DAYS = 7`, and the whole `def purge() -> int:` block (lines 133-142).
- `App/app/retention.py`: `# purged with the row 7 days after done/dead (jobqueue.purge).`
- `go/cmd/ubyhost-web/registry.go`: `func registerBackground(`
- latest goose file: `App/migrations_pg/00017_goose_parity.sql`; `python3 scripts/context_lint.py | tail -3` prints `goose migration 00018`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/jobs/purge.go` | create | `Purge`, batched delete |
| `go/internal/jobs/purge_test.go` | create | the new test |
| `go/cmd/ubyhost-web/register_job_purge.go` | create | hourly background task |
| `App/migrations_pg/00019_job_autovacuum.sql` | create | per-table autovacuum settings |
| `App/app/jobqueue.py` | edit | dead rows 30 days (step 3) |
| `App/tests/test_job_queue.py` | edit | one test for step 3 |
| `App/app/retention.py` | edit | comment line 37-38 only |
| `docs/privacy/RETENTION.md` | edit | one table row |
| `docs/tasks/1816-report.md` | create | the report (§9) |

No other file may change. If the lint prints a goose number other than 00018, use that number in the file name and tell the report.

## 4. Steps

**Step 1: Go purge.** Create `go/internal/jobs/purge.go`:

```go
package jobs

import (
	"context"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	// KeepDoneDays and KeepDeadDays: how long a finished or a dead row stays.
	KeepDoneDays = 7
	KeepDeadDays = 30
	// PurgeBatch rows per DELETE. Each batch is its own short transaction, so
	// no lock is held across batches and a claim is never kept waiting.
	PurgeBatch = 500
	// purgeMaxBatches caps one call (500 x 100 = 50,000 rows); the next hourly run continues.
	purgeMaxBatches = 100
)

// Open rows (done_at and dead_at both NULL) are never selected. SKIP LOCKED
// leaves any row another session holds for the next run.
const purgeDoneSQL = `
	DELETE FROM job WHERE id IN (
		SELECT id FROM job
		WHERE done_at IS NOT NULL AND done_at < $1
		ORDER BY id LIMIT $2
		FOR UPDATE SKIP LOCKED)`

const purgeDeadSQL = `
	DELETE FROM job WHERE id IN (
		SELECT id FROM job
		WHERE dead_at IS NOT NULL AND dead_at < $1
		ORDER BY id LIMIT $2
		FOR UPDATE SKIP LOCKED)`

// Purge deletes done rows older than KeepDoneDays and dead rows older than
// KeepDeadDays, PurgeBatch at a time, and returns the rows removed.
func Purge(ctx context.Context, pool *pgxpool.Pool) (int64, error) {
	var total int64
	for _, q := range []struct {
		sql  string
		days int
	}{{purgeDoneSQL, KeepDoneDays}, {purgeDeadSQL, KeepDeadDays}} {
		cutoff := Now(-time.Duration(q.days) * 24 * time.Hour)
		for i := 0; i < purgeMaxBatches; i++ {
			tag, err := pool.Exec(ctx, q.sql, cutoff, PurgeBatch)
			if err != nil {
				return total, err
			}
			total += tag.RowsAffected()
			if tag.RowsAffected() < PurgeBatch {
				break
			}
		}
	}
	if total > 0 {
		slog.Info("job purge", "removed", total)
	}
	return total, nil
}
```

Create `go/cmd/ubyhost-web/register_job_purge.go`:

```go
package main

// Brief 1816: the Go twin of App/app/jobqueue.py purge(). Housekeeping, not a
// queued job (it must not write job rows itself). It runs one minute after
// start and then every hour until the context ends. A failed run is logged
// and tried again next hour.

import (
	"context"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
)

func init() { registerBackground("job_purge", jobPurgeTask) }

func jobPurgeTask(pool *pgxpool.Pool) (func(context.Context), error) {
	return func(ctx context.Context) {
		wait := time.Minute
		for {
			t := time.NewTimer(wait)
			select {
			case <-ctx.Done():
				t.Stop()
				return
			case <-t.C:
			}
			if _, err := jobs.Purge(ctx, pool); err != nil && ctx.Err() == nil {
				slog.Warn("job purge failed", "error", err.Error())
			}
			wait = time.Hour
		}
	}, nil
}
```

Run: `cd go && gofmt -l ./internal/jobs ./cmd/ubyhost-web | tail -30` (prints nothing) and `go build ./... 2>&1 | tail -30`. Commit `1816 step 1`.

**Step 2: Go test.** Create `go/internal/jobs/purge_test.go` (package `jobs`, same as `queue_test.go`; reuse its `testPool(t)` helper). The test inserts rows with `INSERT INTO job (kind, run_at, payload, created_at, done_at, dead_at) VALUES ($1, $2, '{}', $2, $3, $4)` and asserts, after one `Purge(ctx, pool)`:

| Row | Kind | done_at | dead_at | Expected |
|---|---|---|---|---|
| a | push | `Now(-8*24h)` | NULL | deleted |
| b | push | `Now(-6*24h)` | NULL | kept |
| c | mail | NULL | `Now(-8*24h)` | kept (dead keeps 30 days) |
| d | mail | NULL | `Now(-31*24h)` | deleted |
| e | submit | NULL | NULL, `run_at` 40 days old | kept (open row, never deleted) |

Use `kind` values so the unique open-row index is not violated (only row e is open). A second test inserts `PurgeBatch*2 + 10` done rows 8 days old with distinct kinds is NOT possible (open index does not apply to done rows, so the same kind is fine): insert 1,010 rows of kind `push` with `done_at = Now(-8*24h)` via `generate_series`, run `Purge`, assert 0 rows left and the returned count is 1,010. Then run (needs `UBYHOST_TEST_DATABASE_URL`; without it the tests skip, and a skip is NOT a pass: see §8):

`cd go && go test ./internal/jobs/ -run Purge -count=1 -v 2>&1 | tail -30`

Commit `1816 step 2`.

**Step 3: Python dead period 30 days.** In `App/app/jobqueue.py`, after the line `KEEP_DONE_DAYS = 7` add `KEEP_DEAD_DAYS = 30`. Replace the body of `purge()` (the docstring and the `cutoff`/`db.execute` block, quoted in §2 anchors) with:

```python
def purge() -> int:
    """Delete done rows older than KEEP_DONE_DAYS and dead rows older than KEEP_DEAD_DAYS; the number removed."""
    _require_postgres()
    done_cutoff = _stamp(-timedelta(days=KEEP_DONE_DAYS))
    dead_cutoff = _stamp(-timedelta(days=KEEP_DEAD_DAYS))
    return db.execute(
        "DELETE FROM job WHERE (done_at IS NOT NULL AND done_at < ?) "
        "OR (dead_at IS NOT NULL AND dead_at < ?)",
        (done_cutoff, dead_cutoff),
    )
```

In `App/tests/test_job_queue.py` add after `test_purge_removes_only_rows_older_than_seven_days` one test `test_purge_keeps_dead_rows_for_thirty_days`: insert with `_insert` a row, then `db.execute("UPDATE job SET dead_at = ? WHERE id = (SELECT MAX(id) FROM job)", (stamp,))` for stamp 8 days old (kept) and a second row 31 days old (deleted); assert `jobqueue.purge() == 1` and one row left. (`_insert` has no `dead_at` argument; do not change it.) Edit `App/app/retention.py` comment lines 37-38 to: `# job.error: exception class and message (300 chars max), may name an address;` / `# purged with the row 7 days after done, 30 days after dead (jobqueue.purge, go/internal/jobs/purge.go).` Add to `docs/privacy/RETENTION.md` after the row "Mail rows ..." (the `| Mail rows` line) one row: `| Background job rows (kind, times, attempts; error text of a failed run, 300 characters at most, may name an address; no payload data) | \`job\` | done / failed | 7 days after done, 30 days after failed | \`jobqueue.purge\` (Python, hourly) and \`jobs.Purge\` (Go, hourly) | Minimisation |`. Commit `1816 step 3`.

**Step 4: Migration.** Create `App/migrations_pg/00019_job_autovacuum.sql` (goose-only, no `schema_migrations` row, like `00017_goose_parity.sql`; additive; a storage parameter does not change any query, so the previous image keeps working):

```sql
-- +goose Up
-- Brief 1816. The job table is small (about 12,000 rows) but every row is updated 2-3 times,
-- so dead tuples pile up fast; the default 20% scale factor waits for thousands. Vacuum
-- early and often, and analyze early so the partial indexes keep good plans.
SET LOCAL lock_timeout = '5s';
ALTER TABLE job SET (
    autovacuum_vacuum_scale_factor = 0.01,
    autovacuum_vacuum_threshold = 100,
    autovacuum_analyze_scale_factor = 0.02,
    autovacuum_analyze_threshold = 100
);

-- +goose Down
ALTER TABLE job RESET (
    autovacuum_vacuum_scale_factor,
    autovacuum_vacuum_threshold,
    autovacuum_analyze_scale_factor,
    autovacuum_analyze_threshold
);
```

Then from `App/`: `.venv/bin/python scripts/pg_schema_golden.py 2>&1 | tail -30` (the database rule says to rerun it after a goose file; if it needs a database that is not there, STOP and report). Commit `1816 step 4`.

**Step 5: Report** (§9). Commit `1816 step 5`.

## 5. Do not touch

- `Claim`, `Finish`, `Fail` in `go/internal/jobs/queue.go` and the Python twins (already `SKIP LOCKED`; unchanged).
- The `job` table definition, `job_one_open_per_kind`, `job_due`, `App/migrations_pg/00003_job.sql`, `App/app/migrations/` (frozen).
- Everything for filing: `go/internal/ubyport`, `App/app/reporting.py`, `submit` handlers, `submission` code.
- `watch_go_scheduler`, `stuck_kinds` and the scheduler plan (they are safe, §2 table).
- `UBYHOST_GO_JOB_KINDS`, `UBYHOST_JOB_QUEUE_KINDS`, `docker-compose.yml`, any server file. No new env var, no new dependency, no new outbound request.
- Hard rules: 1, 2, 3, 4, 5, 11.

## 6. Commands (test-map: "Database, migrations" and "Retention, privacy" rows, plus the Go package)

From `App/`:
- `.venv/bin/python -m pytest tests/test_job_queue.py tests/test_migrations.py tests/test_db_*.py -q --tb=short -x 2>&1 | tail -30`
- `.venv/bin/python -m pytest tests/test_retention*.py tests/test_privacy_*.py -q --tb=short -x 2>&1 | tail -30`

From the repo root: `python3 scripts/context_lint.py | tail -3` must say `OK`.

From `go/`:
- `go test ./internal/jobs/ -run Purge -count=1 -v 2>&1 | tail -30`
- `go test ./internal/jobs/ ./cmd/ubyhost-web/ -run 'Purge|Background' -count=1 2>&1 | tail -30` (the background tests in `register_background_test.go` swap `backgroundTasks`, so the new task must not break them; if one fails because it lists task names, STOP and report, do not edit that file).

Never the full suite.

## 7. Acceptance

- [ ] `go build ./...` and `gofmt -l` are clean; the two Go purge tests pass with the database variable set and show `PASS` (not `SKIP`) in the `-v` output.
- [ ] The Python tests of §6 pass; the new dead-row test passes.
- [ ] `git diff --stat` lists only §3 paths; `queue.go` and `00003_job.sql` are unchanged.
- [ ] `grep -nF "FOR UPDATE SKIP LOCKED" go/internal/jobs/queue.go App/app/jobqueue.py` still shows both claims.
- [ ] `grep -rn "DELETE FROM job" go App/app | tail -5` shows exactly the two Go statements (via `purge.go`) and the one Python statement, each with a cutoff and never touching an open row.
- [ ] Done when (after deploy, owner/orchestrator check, not the executor): `SELECT count(*) FROM job` stays flat (about 12,000 or fewer, no more than 8 days of rows) over a week; dead rows older than 30 days are gone; the `job_failed` and "left out" alerts do not fire; `submit` still runs (the Operations page shows its last success fresh).

## 8. Stop and ask

Stop, write the report as `blocked` if: an anchor is not found verbatim; a test fails twice; the Go purge tests only SKIP because no test database is available (report it, the orchestrator runs them in CI); `pg_schema_golden.py` needs something not available; the lint prints a goose number you cannot use; you find a reader of finished job rows that §2 does not list (give file:line, change nothing more); 25 tool calls or about 50k tokens.

## 9. Report

`docs/tasks/1816-report.md`, 600 tokens at most: `git diff --stat`; each §6 command with its last 5 lines; §7 ticked; Deviations (including the goose number if it was not 00018); Questions (the open question of §2 is for the orchestrator); owner steps left: merge with `scripts/merge-pr-on-green.sh`, deploy, and after a week run `SELECT count(*), min(created_at) FROM job` on the server. Set `Status: review`.

## Rollout wave and rollback

- **Rollout:** normal green merge and deploy. The migration is storage parameters only and runs in the deploy's migration step; it fails within 5 s rather than queueing behind a lock.
- **Rollback:** revert the PR. The Down section resets the four parameters. Deleted rows are not restored; nothing reads them.

## Owner steps

None before merge. Optional proof (open question in §2): the one SELECT on the server.
