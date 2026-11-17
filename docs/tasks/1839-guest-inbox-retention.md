# 1839: Retention for `guest_inbox` payloads, `guest_form_snapshot` rows and the guest spool

Status: todo
Depends on: 1834, 1837 | Base commit: 4d3bc7bc (or the tip after 1837 merged) | Branch: task/1839-guest-inbox-retention
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (deletion of guest data; exact diffs only; orchestrator reads the full diff before ready)
Plan: [guest-form-isolation](../plans/guest-form-isolation.md) section 3 rule 7, section 4 (spool), section 11 (D4).

> **One PR mode.** Commit each step as `1839 step k`. Never push, merge or deploy. Hand the owner the steps in "Owner steps".

## Open questions (orchestrator answers before execute)

None blocks execution; Step 0 does not wait for answers. Record the answer under each line before `Status: ready`.

1. **Clock for held rows.** This brief deletes a payload only when `status = 'done'` and `processed_at` is older than 7 days. A held row therefore keeps its payload until brief 1838 attaches or dismisses it, and 1838 must end both actions as `status = 'done'` with `processed_at = now()`. Recommended answer: yes, write that into 1838 (and 1837: every `done` sets `processed_at`). A `done` row with `processed_at` NULL keeps its payload forever, and the test below proves it, so a worker bug can only over-keep, never delete early.
2. **The inbox row itself.** After 7 days the row stays without payload (keys, token hash, stay id, `received_at`, status, host note) as the duplicate guard. Recommended answer: keep it for now; a later brief deletes the row once 1837 shows `received_at` is copied into the guest rows (rule 1: it is the legal submission time UbyPort deadlines use).
3. **Not gated by `UBYHOST_RETENTION_AUTOPURGE`.** The deletion runs in the hourly Go `job_purge` task, which deletes `job` rows today with no switch, not in the daily retention job, which is a dry run on the server. Recommended answer: approve; a transient copy of data already held in `guest` must not wait for counsel's sign-off of the six-year schedule.

## 1. Objective

Delete the guest-form payload in `guest_inbox` 7 days after the app processed it (`done`), delete `guest_form_snapshot` rows when their link expires, and write the rule for the future spool files (volume `ubyhost-guestspool`, implemented by brief 1842). The deletion runs in Go, in the hourly task that already runs on the server, and the retention schedule and the processing record say so.

## 2. Context

Hard rules: 1 filing correctness first (only `done` rows lose their payload; `done` means the worker wrote the guest rows in the same transaction, plan section 3 rule 3, and the guest rows are the filing record); 2 privacy first (a personal-data field gets a line in `App/app/retention.py`); 3 no secrets; 4 no new dependency; 5 no schema change here (1834 already made `idx_guest_inbox_purge`); 8 never push to `main`; 11 Go first.

**Why not a retention STEP.** `App/app/retention.py` `STEPS` is mirrored step by step by `go/internal/retention` and pinned by `testdata/golden.json` (`App/tests/test_go_retention_parity.py`, `TestStepsOrderMatchesPython`). Both tables are PostgreSQL-only, and the daily retention job is a dry run on the server. So `retention.py` gets a comment block only (its pattern for `job.error`, which `jobqueue.purge` deletes), and the deletion goes next to `jobs.Purge` in the hourly `job_purge` background task. A comment changes no golden.

**Contract surface from 1834** (`App/migrations_pg/00020_guest_contract.sql`):

- `guest_inbox`: `id`, `idempotency_key` (32 lower-case hex, unique), `token_hash` (64 hex), `reservation_id` (no FK), `contract_version`, `received_at`, `payload_enc` (BYTEA, nullable), `status` (`new`/`done`/`held`), `host_note`, `attempts`, `processed_at`, and `CHECK (payload_enc IS NOT NULL OR status = 'done')`.
- `guest_form_snapshot`: `token_hash` (PK), `apartment_id` (FK to `apartment`), `contract_version`, `expires_at` (TIMESTAMPTZ), `form_config` (JSONB), `updated_at`.
- `payload_enc` is a Fernet token made with the existing data keys, the scheme of the `_enc` columns (decision D4). No new processor, no new key.

**Anchors** (verify each with `grep -nF`; if one is missing, STOP):

`App/migrations_pg/00020_guest_contract.sql`:
```
CREATE INDEX IF NOT EXISTS idx_guest_inbox_purge ON guest_inbox (processed_at)
    WHERE status = 'done' AND payload_enc IS NOT NULL;
```
`go/internal/jobs/purge.go`:
```
	// purgeMaxBatches caps one call (500 x 100 = 50,000 rows); the next hourly run continues.
	purgeMaxBatches = 100
```
`go/cmd/ubyhost-web/register_job_purge.go`:
```
			if _, err := jobs.Purge(ctx, pool); err != nil && ctx.Err() == nil {
				slog.Warn("job purge failed", "error", err.Error())
			}
```
`App/app/retention.py` line 37-38:
```
# job.error: exception class and message (300 chars max), may name an address;
# purged with the row 7 days after done/dead (jobqueue.purge).
```
`docs/privacy/RETENTION.md` (one line, starts with):
```
| Unfinished guest form (draft) | `guest_form_draft` (encrypted) |
```
`docs/privacy/ROPA.md` (one line, starts with):
```
| Unfinished form drafts | The fields a guest typed into an unsent check-in form
```
`go/internal/jobs/queue_test.go` has `func testPool(t *testing.T) *pgxpool.Pool` (applies every `App/migrations_pg/*.sql`; skips without `UBYHOST_TEST_DATABASE_URL`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/jobs/guest_purge.go` | create | `PurgeGuestContract`: payload NULL 7 days after `done`, expired snapshots deleted |
| `go/internal/jobs/guest_purge_test.go` | create | which rows lose what, and what stays |
| `go/cmd/ubyhost-web/register_job_purge.go` | edit | call `PurgeGuestContract` after `jobs.Purge` each hour |
| `App/app/retention.py` | edit | comment block: the personal-data lines for inbox, snapshot, spool |
| `docs/privacy/RETENTION.md` | edit | three table rows |
| `docs/privacy/ROPA.md` | edit | one row in section A |
| `docs/tasks/1839-report.md` | create | the report (section 9) |

No other file may change.

Overlap (context lint warns): `register_job_purge.go` and `RETENTION.md` are also named by 1816, whose code is already merged (the file header says "Brief 1816"); `retention.py`, `RETENTION.md` and `ROPA.md` are also named by 0347, 0350, 0425, 1120, 1170 and 1662, which edit other lines. This brief inserts next to its own anchors only, so order does not matter; a missing anchor stops it.

## 4. Steps

0. **Check the base.** Run `grep -nF 'idx_guest_inbox_purge' App/migrations_pg/00020_guest_contract.sql && grep -rlF 'guest_inbox' App/app go/internal | grep -v _test | head -5`. Expected: the index line, then at least one non-test file (the 1837 worker). If either is missing, STOP: 1834 or 1837 is not merged. Then verify every anchor in section 2 with `grep -nF`.

1. **Create `go/internal/jobs/guest_purge.go`** with exactly:
```go
package jobs

import (
	"context"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// GuestPayloadKeepDays: a done guest_inbox payload stays this long after
// processed_at (plan guest-form-isolation section 3 rule 7, brief 1839).
// The worker wrote the guest rows in the same transaction that set done;
// those rows are the house-book and filing record and are never touched here.
const GuestPayloadKeepDays = 7

// Only done rows with processed_at set are selected: new and held rows keep
// their payload whatever their age. The row stays as the idempotency record.
const guestPayloadSQL = `
	UPDATE guest_inbox SET payload_enc = NULL
	WHERE status = 'done' AND id IN (
		SELECT id FROM guest_inbox
		WHERE status = 'done' AND payload_enc IS NOT NULL
		  AND processed_at IS NOT NULL AND processed_at < $1
		ORDER BY processed_at LIMIT $2
		FOR UPDATE SKIP LOCKED)`

// A snapshot holds the form settings of one guest link; it goes when the link expires.
const guestSnapshotSQL = `
	DELETE FROM guest_form_snapshot WHERE token_hash IN (
		SELECT token_hash FROM guest_form_snapshot
		WHERE expires_at < $1
		ORDER BY token_hash LIMIT $2
		FOR UPDATE SKIP LOCKED)`

// PurgeGuestContract sets guest_inbox.payload_enc to NULL on done rows
// processed more than GuestPayloadKeepDays ago and deletes expired
// guest_form_snapshot rows, PurgeBatch at a time. Counts only in the log.
func PurgeGuestContract(ctx context.Context, pool *pgxpool.Pool) (payloads, snapshots int64, err error) {
	now := time.Now().UTC()
	payloads, err = purgeBatched(ctx, pool, guestPayloadSQL, now.Add(-GuestPayloadKeepDays*24*time.Hour))
	if err != nil {
		return payloads, 0, err
	}
	snapshots, err = purgeBatched(ctx, pool, guestSnapshotSQL, now)
	if err != nil {
		return payloads, snapshots, err
	}
	if payloads+snapshots > 0 {
		slog.Info("guest contract purge", "payloads", payloads, "snapshots", snapshots)
	}
	return payloads, snapshots, nil
}

// purgeBatched runs sql with (cutoff, PurgeBatch) until a batch is short, at
// most purgeMaxBatches times; each batch is its own short transaction.
func purgeBatched(ctx context.Context, pool *pgxpool.Pool, sql string, cutoff time.Time) (int64, error) {
	var total int64
	for i := 0; i < purgeMaxBatches; i++ {
		tag, err := pool.Exec(ctx, sql, cutoff, PurgeBatch)
		if err != nil {
			return total, err
		}
		total += tag.RowsAffected()
		if tag.RowsAffected() < PurgeBatch {
			break
		}
	}
	return total, nil
}
```
   Command (from `go/`): `gofmt -l internal/jobs/ && go vet ./internal/jobs/ 2>&1 | tail -10`. Expected: no output.

2. **Create `go/internal/jobs/guest_purge_test.go`** with exactly:
```go
package jobs

import (
	"context"
	"fmt"
	"strings"
	"testing"
	"time"
)

func TestPurgeGuestContractPayloadsOnlyDoneAfterSevenDays(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	days := func(n int) time.Time { return time.Now().UTC().Add(-time.Duration(n) * 24 * time.Hour) }
	insert := func(n int, status string, processed any) int64 {
		t.Helper()
		var id int64
		err := pool.QueryRow(ctx,
			`INSERT INTO guest_inbox (idempotency_key, token_hash, reservation_id, contract_version,
			   received_at, payload_enc, status, processed_at)
			 VALUES ($1, $2, 1, 1, $3, $4, $5, $6) RETURNING id`,
			fmt.Sprintf("%032x", n), strings.Repeat("a", 64), days(40), []byte("gAAAAA-test"),
			status, processed).Scan(&id)
		if err != nil {
			t.Fatal(err)
		}
		return id
	}
	ids := map[string]int64{
		"done8":     insert(1, "done", days(8)),  // processed 8 days ago: payload NULL
		"done6":     insert(2, "done", days(6)),  // processed 6 days ago: kept
		"doneNull":  insert(3, "done", nil),      // done without processed_at: kept
		"held":      insert(4, "held", nil),      // waiting for the host: kept
		"heldOld":   insert(5, "held", days(30)), // held, whatever the time: kept
		"new":       insert(6, "new", nil),       // not processed yet: kept
	}
	payloads, _, err := PurgeGuestContract(ctx, pool)
	if err != nil {
		t.Fatal(err)
	}
	if payloads != 1 {
		t.Fatalf("payloads %d, want 1", payloads)
	}
	for label, id := range ids {
		var gone bool
		if err := pool.QueryRow(ctx, `SELECT payload_enc IS NULL FROM guest_inbox WHERE id = $1`, id).Scan(&gone); err != nil {
			t.Fatalf("row %s: %v (rows must never be deleted)", label, err)
		}
		if gone != (label == "done8") {
			t.Errorf("row %s: payload deleted=%v", label, gone)
		}
	}
	again, _, err := PurgeGuestContract(ctx, pool)
	if err != nil || again != 0 {
		t.Fatalf("second run: %d, %v; want 0, nil", again, err)
	}
}

func TestPurgeGuestContractDeletesExpiredSnapshots(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	for _, s := range []string{
		`INSERT INTO user_account (id, username, password_hash, role, created_at) VALUES (1, 'owner@example.test', 'x', 'host', '2026-01-01')`,
		`INSERT INTO apartment (id, owner_user_id, internal_name, city_en, uby_name, permalink_token, created_at) VALUES (7, 1, 'Byt Dole', 'Brno', 'UBY', 'tok7', '2026-01-01')`,
	} {
		if _, err := pool.Exec(ctx, s); err != nil {
			t.Fatal(err)
		}
	}
	expired, active := strings.Repeat("b", 64), strings.Repeat("c", 64)
	for hash, expires := range map[string]time.Time{
		expired: time.Now().UTC().Add(-time.Hour),
		active:  time.Now().UTC().Add(24 * time.Hour),
	} {
		if _, err := pool.Exec(ctx,
			`INSERT INTO guest_form_snapshot (token_hash, apartment_id, contract_version, expires_at, form_config)
			 VALUES ($1, 7, 1, $2, '{}')`, hash, expires); err != nil {
			t.Fatal(err)
		}
	}
	_, snapshots, err := PurgeGuestContract(ctx, pool)
	if err != nil {
		t.Fatal(err)
	}
	if snapshots != 1 {
		t.Fatalf("snapshots %d, want 1", snapshots)
	}
	var left string
	if err := pool.QueryRow(ctx, `SELECT string_agg(token_hash, ',') FROM guest_form_snapshot`).Scan(&left); err != nil {
		t.Fatal(err)
	}
	if left != active {
		t.Fatalf("left %q, want only the active link", left)
	}
}
```
   Command (from `go/`): `gofmt -w internal/jobs/guest_purge_test.go && echo "${UBYHOST_TEST_DATABASE_URL:+db set}" && go test ./internal/jobs/ -run 'Purge' -v 2>&1 | tail -20`. Expected: with `db set`, `--- PASS` for both new tests and the two existing purge tests, then `ok`. Without it, the tests `SKIP` and `ok`: write in the report that CI runs them (`test-postgres-full`). `gofmt -w` only fixes the alignment of the comments in the `ids` map; any other change it makes is a deviation to report.

3. **Hourly call.** In `go/cmd/ubyhost-web/register_job_purge.go` replace the anchor
```
			if _, err := jobs.Purge(ctx, pool); err != nil && ctx.Err() == nil {
				slog.Warn("job purge failed", "error", err.Error())
			}
```
   with
```
			if _, err := jobs.Purge(ctx, pool); err != nil && ctx.Err() == nil {
				slog.Warn("job purge failed", "error", err.Error())
			}
			// Brief 1839: guest_inbox payloads 7 days after done, expired form snapshots.
			if _, _, err := jobs.PurgeGuestContract(ctx, pool); err != nil && ctx.Err() == nil {
				slog.Warn("guest contract purge failed", "error", err.Error())
			}
```
   Command (from `go/`): `gofmt -l cmd/ubyhost-web/ && go build ./... && go test ./cmd/ubyhost-web/ -run 'Background|Scheduler' 2>&1 | tail -10`. Expected: no gofmt output, build silent, `ok`.

4. **`App/app/retention.py`.** Replace the anchor
```
# job.error: exception class and message (300 chars max), may name an address;
# purged with the row 7 days after done/dead (jobqueue.purge).
```
   with
```
# job.error: exception class and message (300 chars max), may name an address;
# purged with the row 7 days after done/dead (jobqueue.purge).

# 1839: guest_inbox.payload_enc is one sent guest form (every field, signature,
# consent), gzip JSON encrypted with the data keys as the _enc columns (D4).
# The worker copies it into the guest rows, which are the house-book and
# filing record. The payload is set to NULL 7 days after processed_at of a
# done row; new and held rows keep it (an attached or dismissed held row
# becomes done then). The row without payload stays as the duplicate guard.
# guest_form_snapshot holds one guest link's form settings (no guest data)
# and is deleted when the link expires. Both run hourly in Go
# (go/internal/jobs/guest_purge.go), not in STEPS: PostgreSQL-only tables.
# Guest-program spool files (volume ubyhost-guestspool, brief 1842) are
# deleted as soon as guest_inbox holds the submission.
```
   Command: `grep -c '^# 1839:' App/app/retention.py`. Expected: `1`.

5. **`docs/privacy/RETENTION.md`.** Directly after the line that starts with `| Unfinished guest form (draft) |` insert these three lines (no blank line between table rows):
```
| Sent guest form waiting for the app (every field the guest entered, signature, consent; compressed, then encrypted with the data keys of the `_enc` columns) | `guest_inbox.payload_enc` | the app wrote the guest record (`done`); a held form once the host attaches or dismisses it | 7 days after processing; unprocessed and held forms keep it until then; the row without the form stays as the duplicate guard | `jobs.PurgeGuestContract` (Go, hourly `job_purge` task) | Minimisation; the guest record above is the house-book record |
| Guest-form settings of a link (property name, languages, required fields, guests still expected; no guest data) | `guest_form_snapshot` | link expiry | deleted when the link expires | `jobs.PurgeGuestContract` (Go, hourly) | Minimisation |
| Guest-form spool file (a sent form saved on the server's disk while the database was unreachable; encrypted as above) | volume `ubyhost-guestspool` | delivery to `guest_inbox` | deleted right after the database confirms delivery | guest program delivery loop (brief 1842) | Minimisation |
```
   Command: `grep -c 'PurgeGuestContract\|ubyhost-guestspool' docs/privacy/RETENTION.md`. Expected: `3`.

6. **`docs/privacy/ROPA.md`.** Directly after the line that starts with `| Unfinished form drafts |` insert:
```
| Sent forms in transit | A sent check-in form waits in `guest_inbox`, or while the database is unreachable in a spool file on the same server's disk, until the app writes the guest record; compressed and encrypted with the same data keys as the other encrypted fields; same server and region, no new subprocessor; the form is deleted 7 days after processing, a spool file right after delivery (RETENTION) |
```
   Command: `grep -c '^| Sent forms in transit |' docs/privacy/ROPA.md`. Expected: `1`.

7. **Tests and lint** (section 6), then the report (section 9).

## 5. Do not touch

`App/migrations_pg/` (no schema change), `App/app/retention.py` code and `STEPS`, `go/internal/retention/` and its golden, `go/internal/jobs/purge.go`, the `guest` table and every query on it, `deploy/`. Hard rules 1, 2, 3, 4, 8, 11.

## 6. Commands

From `go/`:
- `go build ./... 2>&1 | tail -10`: silent.
- `go test ./internal/jobs/ ./cmd/ubyhost-web/ 2>&1 | tail -30`: `ok` for both.

From `App/` (test-map row "Retention, privacy"):
- `.venv/bin/python -m pytest tests/test_retention*.py tests/test_privacy_*.py tests/test_go_retention_parity.py -q --tb=short -x 2>&1 | tail -30`: passed, 0 failed.

From the repo root:
- `python3 scripts/context_lint.py 2>&1 | tail -30`: no error for the files above.

## 7. Acceptance

- [ ] `git diff --stat` lists only the section 3 files.
- [ ] `TestPurgeGuestContractPayloadsOnlyDoneAfterSevenDays` and `TestPurgeGuestContractDeletesExpiredSnapshots` pass with a database, or skip without one (said in the report).
- [ ] No row of `guest_inbox` is deleted by this brief: `grep -c 'DELETE FROM guest_inbox' go/internal/jobs/guest_purge.go` prints `0`.
- [ ] `grep -nE '(FROM|UPDATE|JOIN|INTO) guest( |$)' go/internal/jobs/guest_purge.go` prints nothing: no query on the `guest` table.
- [ ] The retention/privacy pytest row passes; `golden.json` unchanged (`git diff --quiet -- go/internal/retention/` exits 0).
- [ ] context lint clean for these files.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found, or Step 0 finds 1834 or 1837 missing;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1839-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked; say whether the DB tests ran or skipped.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/jobs/guest_purge.go`: the `WHERE` of `guestPayloadSQL` (only `done`, only `processed_at` set and older than 7 days, never a row delete) and `guestSnapshotSQL`.
- `go/cmd/ubyhost-web/register_job_purge.go`: runs ungated every hour on the server (open question 3).
- `docs/privacy/RETENTION.md`, `docs/privacy/ROPA.md`: wording a lawyer reads.

## Owner steps

1. Nothing to set: the deletion starts with the first deploy after merge, one minute after the app starts, then every hour. It only acts once the guest program (1840) writes inbox rows.
2. When you next send the privacy documents to your lawyer, point at the three new rows in `docs/privacy/RETENTION.md` (sent guest form, form settings, spool file) and the row "Sent forms in transit" in `docs/privacy/ROPA.md`. Ask: is 7 days after processing an acceptable period for the transit copy, and does "same server and region, no new subprocessor" describe it correctly. Until then the rows are marked by the file header as input for counsel; nothing waits on the answer.
