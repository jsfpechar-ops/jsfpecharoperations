# 2085: Use Prague civil date in Go stays overdue window, ordering, and range defaults

Status: review
Depends on: none | Base commit: 3a4e1e88ca4f23fbbde6dc26c45d45c9c29b421b | Branch: claude/nice-hawking-fw98ct
Executor: Gemini 4 Neon (medium) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Switch the Go `/reservations` overdue-unfinished 45-day lookback window, list `ORDER BY` bucket cutoff, and range-default date from raw UTC `at` to the Prague civil date (`civilDate(deadlines.LocalNow(at))` / `pragueToday(at)`). This eliminates the midnight UTC-vs-Prague parity drift against Python's `reservations_list` and `reporting.dashboard_rows`.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema (`UBYHOST_TEST_DATABASE_URL`) for DB tests. If any excerpt below is not found verbatim, STOP (§8).

Python reference (do not edit):

- `App/app/reporting.py:934-936`:

```python
    today = deadlines.local_now().date()
    start = (today - timedelta(days=days_back)).isoformat()
    end = (today + timedelta(days=days_ahead)).isoformat()
```

- `App/app/routes/admin.py:3713-3714,3725`:

```python
    # UTC date.today() on the server lags Czech local time near midnight.
    today = deadlines.local_now().date().isoformat()
```

```python
        date_from, date_to = "", (deadlines.local_now().date() - timedelta(days=1)).isoformat()
```

Go anchors to verify before editing (`go/cmd/ubyhost-web/register_web_stays.go:15` passes `time.Now`, which is UTC on servers and CI):

- `go/internal/web/stays/overdue.go:15-18`:

```go
func overdueUnfinishedIDs(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, ownerID int64, at time.Time) ([]int64, error) {
	today := civilDate(at)
	start := formatISODate(today.AddDate(0, 0, -45))
	end := formatISODate(today.AddDate(0, 0, 21))
```

- `go/internal/web/stays/query.go:10-12` and `40-41`:

```go
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)
```

```go
func List(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, accountID int64, p Params, at time.Time) (View, error) {
	todayISO := formatISODate(civilDate(at))
```

- `go/internal/web/stays/handlers.go:75-77` (`pragueToday` is defined in `go/internal/web/stays/tpl.go:70` and already used on `handlers.go:112`; `params.go:34` documents `today` as the Prague civil date):

```go
		ctx := r.Context()
		p := ParseParams(r.URL.Query(), at)
		v, err := List(ctx, pool, getenv, owner, p, at)
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/stays/overdue.go` | edit | Compute `today` from `deadlines.LocalNow(at)` instead of raw UTC `at`. |
| `go/internal/web/stays/query.go` | edit | Import `internal/deadlines` and compute `todayISO` from `deadlines.LocalNow(at)`. |
| `go/internal/web/stays/handlers.go` | edit | Pass `pragueToday(at)` to `ParseParams` so range defaults match Prague civil date. |
| `go/internal/web/stays/overdue_test.go` | edit | Add deterministic Prague-midnight regression test for overdue cutoff, `ParseParams`, and `List` ordering. |

No other file may change.

## 4. Steps

1. Edit `go/internal/web/stays/overdue.go` (exact diff):

```diff
--- a/go/internal/web/stays/overdue.go
+++ b/go/internal/web/stays/overdue.go
@@ -13,7 +13,7 @@ import (
 // overdueUnfinishedIDs is admin._overdue_unfinished_ids: stays the dashboard
 // still treats as overdue and unfinished (reporting.FINISHED_STATUSES excluded).
 func overdueUnfinishedIDs(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, ownerID int64, at time.Time) ([]int64, error) {
-	today := civilDate(at)
+	today := civilDate(deadlines.LocalNow(at))
 	start := formatISODate(today.AddDate(0, 0, -45))
 	end := formatISODate(today.AddDate(0, 0, 21))
 	rows, err := pool.Query(ctx, `SELECT r.id, r.date_from, r.date_to, r.declared_guests,
```

2. Edit `go/internal/web/stays/query.go` (exact diff):

```diff
--- a/go/internal/web/stays/query.go
+++ b/go/internal/web/stays/query.go
@@ -9,6 +9,8 @@ import (
 
 	"github.com/jackc/pgx/v5"
 	"github.com/jackc/pgx/v5/pgxpool"
+
+	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
 )
 
 // Row is one line of the stays table (reservation + progress metadata).
@@ -38,7 +40,7 @@ type Reservation struct {
 
 // List runs the reservations_list query and builds the view model.
 func List(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, accountID int64, p Params, at time.Time) (View, error) {
-	todayISO := formatISODate(civilDate(at))
+	todayISO := formatISODate(civilDate(deadlines.LocalNow(at)))
 	var overdueIDs []int64
 	if p.DateRange == "upcoming" && p.DateFrom != "" {
 		var err error
```

3. Edit `go/internal/web/stays/handlers.go` (exact diff):

```diff
--- a/go/internal/web/stays/handlers.go
+++ b/go/internal/web/stays/handlers.go
@@ -73,7 +73,7 @@ func ListHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time
 		}
 		owner := host.Workspace.ID
 		ctx := r.Context()
-		p := ParseParams(r.URL.Query(), at)
+		p := ParseParams(r.URL.Query(), pragueToday(at))
 		v, err := List(ctx, pool, getenv, owner, p, at)
 		if err != nil {
 			serverError(w, err)
```

4. Append `TestOverdueUnfinishedIDsPragueDateNearMidnight` to `go/internal/web/stays/overdue_test.go`:

```go
func TestOverdueUnfinishedIDsPragueDateNearMidnight(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()
	// 23:30 UTC on Nov 24 is 00:30 CET on Nov 25 in Prague.
	at := time.Date(2026, 11, 24, 23, 30, 0, 0, time.UTC)

	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ('overdue-prague-host', 'x', 'host', 1, 1, $1) RETURNING id`, at).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	var entityID int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, created_at)
		VALUES ($1, 'Entity', $2) RETURNING id`, ownerID, at).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	var aptID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, automation_mode, submit_after_hours, active, created_at)
		VALUES ($1, $2, 'Flat', 'tok', 'manual', 24, 1, $3) RETURNING id`, ownerID, entityID, at).Scan(&aptID); err != nil {
		t.Fatal(err)
	}

	insertUnfiled := func(uid, from, to string) int64 {
		t.Helper()
		var id int64
		if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, declared_guests, created_at, updated_at)
			VALUES ($1, $2, $3, $4, 'active', 'manual', 1, $5, $5) RETURNING id`,
			aptID, uid, from, to, at).Scan(&id); err != nil {
			t.Fatal(err)
		}
		if _, err := pool.Exec(ctx, `INSERT INTO guest (reservation_id, surname, nationality, stay_from, submit_state, is_lead, entered_by, created_at, updated_at)
			VALUES ($1, 'Unfiled', 'DEU', $2, 'pending', 1, 'guest', $3, $3)`, id, from, at); err != nil {
			t.Fatal(err)
		}
		return id
	}

	// 46 days before Prague Nov 25 (45 days before UTC Nov 24) -> excluded.
	excludedID := insertUnfiled("prague-46d", "2026-10-10", "2026-10-12")
	// 45 days before Prague Nov 25 -> included.
	includedID := insertUnfiled("prague-45d", "2026-10-11", "2026-10-13")

	getenv := func(k string) string { return os.Getenv(k) }
	ids, err := overdueUnfinishedIDs(ctx, pool, getenv, ownerID, at)
	if err != nil {
		t.Fatal(err)
	}
	var sawIncluded bool
	for _, id := range ids {
		if id == excludedID {
			t.Fatalf("46-day-old stay %d (2026-10-10) must be excluded on Prague 2026-11-25; ids=%v", excludedID, ids)
		}
		if id == includedID {
			sawIncluded = true
		}
	}
	if !sawIncluded {
		t.Fatalf("45-day-old stay %d (2026-10-11) missing on Prague 2026-11-25; ids=%v", includedID, ids)
	}

	// Verify ParseParams(pragueToday(at)) and List ORDER BY todayISO use Prague 2026-11-25.
	var pastInPragueID, todayInPragueID int64
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, created_at, updated_at)
		VALUES ($1, 'prague-yesterday', '2026-11-24', '2026-11-24', 'active', 'manual', $2, $2) RETURNING id`,
		aptID, at).Scan(&pastInPragueID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, created_at, updated_at)
		VALUES ($1, 'prague-today', '2026-11-25', '2026-11-26', 'active', 'manual', $2, $2) RETURNING id`,
		aptID, at).Scan(&todayInPragueID); err != nil {
		t.Fatal(err)
	}

	pUpcoming := ParseParams(url.Values{"range": {"upcoming"}}, pragueToday(at))
	if pUpcoming.DateFrom != "2026-11-25" {
		t.Fatalf("upcoming DateFrom = %q, want 2026-11-25", pUpcoming.DateFrom)
	}
	pAll := ParseParams(url.Values{"range": {"all"}}, pragueToday(at))
	vAll, err := List(ctx, pool, getenv, ownerID, pAll, at)
	if err != nil {
		t.Fatal(err)
	}
	if len(vAll.Rows) < 2 || vAll.Rows[0].Reservation.ID != todayInPragueID || vAll.Rows[1].Reservation.ID != pastInPragueID {
		t.Fatalf("range=all order mismatch: got first two IDs %v, want [%d, %d]", vAll.Rows, todayInPragueID, pastInPragueID)
	}
}
```

5. Run every command in §6.

## 5. Do not touch

- Do not edit any file under `App/`, `deploy/`, `scripts/`, or Go packages outside `go/internal/web/stays/`.
- Do not add dependencies (`go.mod` / `go.sum` untouched).
- Do not touch templates, CSS, or filing logic (`go/internal/ubyport/`, `go/internal/deadlines/`).
- No real guest data, secrets, or outbound requests.

## 6. Commands

Run from the indicated directory with `set -o pipefail`. Ensure `UBYHOST_TEST_DATABASE_URL` points to local Postgres so DB tests run with zero skips.

```sh
cd go && test -z "$(gofmt -l .)" && echo "gofmt OK" | tail -30
cd go && go vet ./... 2>&1 | tail -30
cd go && go test ./internal/web/stays/... -count=1 -v 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
```

## 7. Acceptance

- [ ] `go/internal/web/stays/overdue.go` computes `today := civilDate(deadlines.LocalNow(at))`.
- [ ] `go/internal/web/stays/query.go` computes `todayISO := formatISODate(civilDate(deadlines.LocalNow(at)))`.
- [ ] `go/internal/web/stays/handlers.go` passes `pragueToday(at)` to `ParseParams`.
- [ ] `TestOverdueUnfinishedIDsPragueDateNearMidnight` runs and passes (not skipped), proving `2026-10-10` is excluded, `2026-10-11` is included, `upcoming` starts on `2026-11-25`, and `List` ranks `2026-11-25..2026-11-26` ahead of `2026-11-24..2026-11-24` at `2026-11-24T23:30:00Z`.
- [ ] `gofmt -l .` is empty, `go vet ./...` exits 0, `go test ./internal/web/stays/... -count=1 -v` passes, and `python3 scripts/context_lint.py` reports `context lint: OK`.

## 8. Stop and ask

Stop, and write the report as `blocked`, if:

- an excerpt in §2 is not found verbatim;
- a required test fails twice or skips because Postgres is unavailable;
- a file outside §3 or a new dependency seems needed;
- you reach 25 tool calls or ~50k tokens;
- you need push, merge, secrets, SSH, or deploy.

## 9. Report

Write `docs/tasks/2085-report.md` (at most 600 tokens) and set `Status: review` in this brief. Include:

1. `git diff --stat`.
2. Each §6 command with its pass/fail outcome and last 5 lines.
3. §7 ticked.
4. Deviations (if any).
5. Questions (if any).
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/stays/overdue.go`
- `go/internal/web/stays/query.go`
- `go/internal/web/stays/handlers.go`

## Owner steps

1. None (internal Go parity bugfix; re-run `scripts/e2e/parity_gate.sh` in CI or before cutover).
