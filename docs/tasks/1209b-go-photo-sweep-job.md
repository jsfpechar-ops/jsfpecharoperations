# 1209b: Go photo sweep, part 2: database steps, parity test, job kind `photo_sweep`

Status: todo
Depends on: 1209 (same branch) | Base commit: a83df541 plus the 1209 commits | Branch: task/1201-go-photo-sweep
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier A (guest data, deletion)

## 1. Objective

Finish the Go port of `photo_sweep`: the three database steps (`reporting.purge_submission_payloads`, `guest_draft.purge`, `signup.purge` with `meta_capi.expire_unsendable`), `photosweep.Run` (all five steps in Python's order, stop at the first error), the PostgreSQL parity test against the 1209 golden file, and the job registration. The kind stays off: Python keeps running it until an operator adds `photo_sweep` to `UBYHOST_GO_JOB_KINDS`.

## 2. Context

Hard rules that apply: rule 2 (privacy: this job deletes guest data, it must delete exactly what Python deletes, no more, no less), rule 3 (the fixture holds only made-up values), rule 4 (no new dependency: only the Go standard library, pgx and `go/internal/deadlines`, all already in go.mod), rule 5 (the Python side is not touched at all; the SQL is the same SQL Python runs on PostgreSQL).

Python (do not edit), the steps after the two file steps of 1209, same single try:

3. `reporting.purge_submission_payloads()`: cutoff `iso(now-90d)`; submissions with `created_at < cutoff`, `state` in `ok ok_duplicate partial error transport_error outcome_unknown` and any of `request_xml`, `request_xml_enc`, `response_xml` not NULL get all three set to NULL; then `db.audit("submission_payload_purge", "blanked the request and response envelope on N submission(s) older than 90 days")` (actor `host`, no ids) and `db.audit_retention("ubyport_xml", N, cutoff)`. With no rows: only the zero-count retention line.
4. `guest_draft.purge()`: `DELETE FROM guest_form_draft WHERE updated_at < iso(now-7d) OR reservation_id IN (SELECT r.id FROM reservation r WHERE r.status <> 'active' OR date(r.date_to) < prague_today)`.
5. `signup.purge()`: unverified sign-ups (`email_verified_at IS NULL AND signup_at IS NOT NULL AND active = 0 AND signup_at < iso(now-7d)`), one transaction per account deleting `legal_acceptance`, `ad_click`, `email_outbox` (by `owner_user_id`), `audit` (by `owner_user_id`), `user_account`; then `meta_capi.expire_unsendable(now)`; then per platform (google: gclid gbraid wbraid, 90/30 days; meta: fbc client_user_agent, 90/7 days) one transaction blanking the ids and setting `ids_deleted_at = iso(now)`.

`expire_unsendable` is already ported as the unexported `expireUnsendable` in `go/internal/metacapi/send.go`; that package may not change here, so `db.go` carries a commented copy of its one UPDATE.

Job wiring: `go/cmd/ubyhost-web/registry.go` `registerJob(kind, minutes, factory)` from `init()`; the factory must not use the pool while it builds (tests call it with nil). Interval 12*60 as `scheduler.job_intervals()["photo_sweep"]`. `jobNames` in `go/internal/jobs/queue.go` already has `photo_sweep`; `jobLevels` leaves it at `warning`, as Python's `_JOB_LEVELS`. Handler return: Python's `_log_run` counts `photos` and `payloads`, so the handler returns `Photos + Payloads` and logs every count in one `slog.Info` line.

Known difference: Python raises `job_failed` at once on a failed run; the Go queue retries (1/5/15 min, capped at the interval) and raises it when the row dies, like every other Go job (warning level, not filing).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/photosweep/db.go` | create | the three database steps |
| `go/internal/photosweep/sweep.go` | create | `Summary`, `Run`, `run` |
| `go/internal/photosweep/sweep_test.go` | create | PostgreSQL parity test, read-only test, no-data-dir test |
| `go/cmd/ubyhost-web/register_job_photo_sweep.go` | create | `init()` registers `photo_sweep` |
| `docs/tasks/1209b-report.md` | create | the report |

No other file may change.

## 4. Steps

Work from the repo root. Create each file with the heredoc exactly as given.

### Step 0: check the start

```bash
git branch --show-current; git log --oneline -3 | tail -3; ls go/internal/photosweep go/internal/photosweep/testdata 2>&1 | tail -8; grep -c 'func registerJob(kind string, minutes int, h func(\*pgxpool.Pool) jobs.Handler) {' go/cmd/ubyhost-web/registry.go; grep -c 'func LocalNow(now time.Time) time.Time {' go/internal/deadlines/deadlines.go
```

Expected: `task/1201-go-photo-sweep`; a `1209 steps 1-6` commit; `audit.go files.go files_test.go testdata` and `photo_sweep_golden.json`; `1`; `1`. Otherwise STOP (§8).

### Step 1: create `go/internal/photosweep/db.go`

```bash
mkdir -p go/internal/photosweep && cat > go/internal/photosweep/db.go <<'EOF'
package photosweep

// The three database steps of the photo sweep: reporting.purge_submission_payloads,
// guest_draft.purge and signup.purge (which calls meta_capi.expire_unsendable).

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	// submissionPayloadDays is reporting.SUBMISSION_PAYLOAD_DAYS.
	submissionPayloadDays = 90
	// draftMaxAgeDays is guest_draft.MAX_AGE_DAYS.
	draftMaxAgeDays = 7
	// unverifiedTTLDays is signup.UNVERIFIED_TTL_DAYS.
	unverifiedTTLDays = 7
	// metaSendWindow is meta_capi.SEND_WINDOW.
	metaSendWindow = 7*24*time.Hour - time.Hour
)

// terminalSubmissionStates is reporting.TERMINAL_SUBMISSION_STATES.
var terminalSubmissionStates = []string{"ok", "ok_duplicate", "partial", "error", "transport_error", "outcome_unknown"}

// clickPlatform is one entry of signup.PLATFORMS with its ID_COLUMNS and
// ID_RETENTION_DAYS (days after the click, days after an upload or send).
type clickPlatform struct {
	name        string
	columns     []string
	afterClick  int
	afterUpload int
}

// clickPlatforms is signup.PLATFORMS, in that order.
var clickPlatforms = []clickPlatform{
	{"google", []string{"gclid", "gbraid", "wbraid"}, 90, 30},
	{"meta", []string{"fbc", "client_user_agent"}, 90, 7},
}

// purgeSubmissionPayloads is reporting.purge_submission_payloads() for the
// global sweep: the envelopes of settled submissions older than 90 days are
// blanked. It returns the number of rows blanked and writes the retention
// audit line on every run, zero included.
func purgeSubmissionPayloads(ctx context.Context, pool *pgxpool.Pool, now time.Time) (int, error) {
	cutoff := iso(now.Add(-submissionPayloadDays * 24 * time.Hour))
	rows, err := pool.Query(ctx,
		`SELECT s.id FROM submission s JOIN apartment a ON a.id = s.apartment_id
		 WHERE s.created_at < $1 AND s.state = ANY($2)
		 AND (s.request_xml IS NOT NULL OR s.request_xml_enc IS NOT NULL OR s.response_xml IS NOT NULL)
		 ORDER BY s.id`,
		cutoff, terminalSubmissionStates)
	if err != nil {
		return 0, err
	}
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return 0, err
		}
		ids = append(ids, id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}
	if len(ids) == 0 {
		return 0, auditRetention(ctx, pool, now, "ubyport_xml", 0, cutoff)
	}
	if _, err := pool.Exec(ctx,
		`UPDATE submission SET request_xml = NULL, request_xml_enc = NULL, response_xml = NULL
		 WHERE id = ANY($1)`, ids); err != nil {
		return 0, err
	}
	detail := fmt.Sprintf("blanked the request and response envelope on %d submission(s) older than %d days",
		len(ids), submissionPayloadDays)
	if err := auditHost(ctx, pool, now, "submission_payload_purge", detail); err != nil {
		return 0, err
	}
	if err := auditRetention(ctx, pool, now, "ubyport_xml", len(ids), cutoff); err != nil {
		return 0, err
	}
	return len(ids), nil
}

// purgeGuestDrafts is guest_draft.purge(): a draft goes 7 days after its last
// change, or when its stay is no longer active or checked out before
// pragueToday (YYYY-MM-DD, claim.prague_today()).
func purgeGuestDrafts(ctx context.Context, pool *pgxpool.Pool, now time.Time, pragueToday string) (int, error) {
	tag, err := pool.Exec(ctx,
		`DELETE FROM guest_form_draft WHERE updated_at < $1 OR reservation_id IN
		 (SELECT r.id FROM reservation r WHERE r.status <> 'active' OR ubyhost_sqlite_date(r.date_to) < $2)`,
		iso(now.Add(-draftMaxAgeDays*24*time.Hour)), pragueToday)
	if err != nil {
		return 0, err
	}
	return int(tag.RowsAffected()), nil
}

// SignupCounts is the dict signup.purge returns.
type SignupCounts struct {
	UnverifiedDeleted int
	ClickIDsCleared   int
	MetaEventsExpired int
}

// expireUnsendableMeta duplicates meta_capi.expire_unsendable
// (App/app/meta_capi.py), which go/internal/metacapi/send.go also ports as the
// unexported expireUnsendable. Keep the three in step.
func expireUnsendableMeta(ctx context.Context, pool *pgxpool.Pool, now time.Time) (int, error) {
	tag, err := pool.Exec(ctx,
		`UPDATE ad_click SET send_state = $1, last_error = $2
		 WHERE platform = 'meta' AND send_state = $3 AND user_account_id IN (
		   SELECT id FROM user_account WHERE email_verified_at < $4)`,
		"expired", "older than Meta's 7-day event window", "pending", iso(now.Add(-metaSendWindow)))
	if err != nil {
		return 0, err
	}
	return int(tag.RowsAffected()), nil
}

// deleteUnverified is one iteration of signup.purge's per-account
// transaction (db.immediate()).
func deleteUnverified(ctx context.Context, pool *pgxpool.Pool, userID int64) error {
	return pgx.BeginFunc(ctx, pool, func(tx pgx.Tx) error {
		for _, sql := range []string{
			`DELETE FROM legal_acceptance WHERE user_account_id = $1`,
			`DELETE FROM ad_click WHERE user_account_id = $1`,
			`DELETE FROM email_outbox WHERE owner_user_id = $1`,
			`DELETE FROM audit WHERE owner_user_id = $1`,
			`DELETE FROM user_account WHERE id = $1 AND email_verified_at IS NULL AND active = 0`,
		} {
			if _, err := tx.Exec(ctx, sql, userID); err != nil {
				return err
			}
		}
		return nil
	})
}

// purgeSignups is signup.purge(): unconfirmed sign-ups older than 7 days go
// with their rows, unsendable Meta events expire, and click identifiers past
// their time are blanked, one platform per transaction.
func purgeSignups(ctx context.Context, pool *pgxpool.Pool, now time.Time) (SignupCounts, error) {
	var c SignupCounts
	daysAgo := func(days int) string { return iso(now.Add(-time.Duration(days) * 24 * time.Hour)) }
	rows, err := pool.Query(ctx,
		`SELECT id FROM user_account WHERE email_verified_at IS NULL
		 AND signup_at IS NOT NULL AND active = 0 AND signup_at < $1 ORDER BY id`,
		daysAgo(unverifiedTTLDays))
	if err != nil {
		return c, err
	}
	var stale []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return c, err
		}
		stale = append(stale, id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return c, err
	}
	for _, id := range stale {
		if err := deleteUnverified(ctx, pool, id); err != nil {
			return c, err
		}
	}
	c.UnverifiedDeleted = len(stale)
	stamp := iso(now)
	if c.MetaEventsExpired, err = expireUnsendableMeta(ctx, pool, now); err != nil {
		return c, err
	}
	for _, p := range clickPlatforms {
		sets := make([]string, len(p.columns))
		for i, col := range p.columns {
			sets[i] = col + " = NULL"
		}
		var n int64
		err := pgx.BeginFunc(ctx, pool, func(tx pgx.Tx) error {
			tag, err := tx.Exec(ctx,
				`UPDATE ad_click SET `+strings.Join(sets, ", ")+`, ids_deleted_at = $1
				 WHERE platform = $2 AND ids_deleted_at IS NULL AND (
				 clicked_at < $3 OR uploaded_at < $4 OR withdrawn_at IS NOT NULL
				 OR send_state IN ('failed', 'expired'))`,
				stamp, p.name, daysAgo(p.afterClick), daysAgo(p.afterUpload))
			n = tag.RowsAffected()
			return err
		})
		if err != nil {
			return c, err
		}
		c.ClickIDsCleared += int(n)
	}
	return c, nil
}
EOF
sha256sum go/internal/photosweep/db.go 2>&1 | tail -1
```

Expected: `98e754e6281c1d374fff731dc0ffd4ae6cd20d9eaf2c10a956e969dd497d30ad  go/internal/photosweep/db.go`. Different: delete the file and repeat the step once; still different: STOP (§8).

### Step 2: create `go/internal/photosweep/sweep.go`

```bash
mkdir -p go/internal/photosweep && cat > go/internal/photosweep/sweep.go <<'EOF'
package photosweep

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
)

// Summary holds the counts of one sweep, one field per step.
type Summary struct {
	Photos       int // passport_photos.purge_stale
	GuideOrphans int // guide_photos.purge_orphans
	Payloads     int // reporting.purge_submission_payloads
	Drafts       int // guest_draft.purge
	Signup       SignupCounts
}

// clock is the time of one run as each Python step reads it: now for every
// datetime.now(timezone.utc), today for passport_photos' date.today() (the
// server's local date) and pragueToday for claim.prague_today().
type clock struct {
	now         time.Time
	today       time.Time
	pragueToday string
}

// Run is scheduler._job_photo_sweep for the Go job queue. dataDir is
// UBYHOST_DATA_DIR; it must be writable, or the first file to delete fails the
// job. The steps run in Python's order and the first error stops the run and
// is returned, as Python's single try does.
func Run(ctx context.Context, pool *pgxpool.Pool, dataDir string, now time.Time) (Summary, error) {
	if dataDir == "" {
		return Summary{}, errors.New("photo sweep: UBYHOST_DATA_DIR is not set")
	}
	return run(ctx, pool, dataDir, clock{
		now:         now,
		today:       now.Local(),
		pragueToday: deadlines.LocalNow(now).Format("2006-01-02"),
	})
}

func run(ctx context.Context, pool *pgxpool.Pool, dataDir string, c clock) (Summary, error) {
	var s Summary
	var err error
	if s.Photos, err = purgePassportPhotos(ctx, pool, dataDir, c.today, c.now); err != nil {
		return s, err
	}
	if s.GuideOrphans, err = purgeGuideOrphans(ctx, pool, dataDir, c.now); err != nil {
		return s, err
	}
	if s.Payloads, err = purgeSubmissionPayloads(ctx, pool, c.now); err != nil {
		return s, err
	}
	if s.Drafts, err = purgeGuestDrafts(ctx, pool, c.now, c.pragueToday); err != nil {
		return s, err
	}
	if s.Signup, err = purgeSignups(ctx, pool, c.now); err != nil {
		return s, err
	}
	return s, nil
}
EOF
sha256sum go/internal/photosweep/sweep.go 2>&1 | tail -1
```

Expected: `d0cbb89230679e4896af67e597e893ae5d74608513e62a1de95487c263fb8e62  go/internal/photosweep/sweep.go`. Different: delete the file and repeat the step once; still different: STOP (§8).

### Step 3: create `go/internal/photosweep/sweep_test.go`

```bash
mkdir -p go/internal/photosweep && cat > go/internal/photosweep/sweep_test.go <<'EOF'
package photosweep

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
)

type goldenTable struct {
	Table   string   `json:"table"`
	Columns []string `json:"columns"`
	Rows    [][]any  `json:"rows"`
}

type goldenFile struct {
	Dir      string `json:"dir"`
	Name     string `json:"name"`
	MtimeAgo int64  `json:"mtime_ago"`
	Kind     string `json:"kind"`
}

type goldenSignup struct {
	ClickIDsCleared   int `json:"click_ids_cleared"`
	MetaEventsExpired int `json:"meta_events_expired"`
	UnverifiedDeleted int `json:"unverified_deleted"`
}

type goldenCounts struct {
	Photos       int          `json:"photos"`
	GuideOrphans int          `json:"guide_orphans"`
	Payloads     int          `json:"payloads"`
	Drafts       int          `json:"drafts"`
	Signup       goldenSignup `json:"signup"`
}

type golden struct {
	Now          string             `json:"now"`
	Today        string             `json:"today"`
	Seed         []goldenTable      `json:"seed"`
	Files        []goldenFile       `json:"files"`
	Snapshot     []goldenTable      `json:"snapshot"`
	AuditColumns []string           `json:"audit_columns"`
	Counts       goldenCounts       `json:"counts"`
	FilesLeft    []string           `json:"files_left"`
	After        map[string][][]any `json:"after"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/photo_sweep_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var g golden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Seed) == 0 || len(g.Files) == 0 || len(g.Snapshot) == 0 {
		t.Fatal("golden file has no seed, files or snapshot")
	}
	return g
}

// dbPool creates a throwaway database with every App/migrations_pg file, as
// go/internal/calendar/handler_test.go does.
func dbPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := "ubyhost_go_photosweep_" + strings.ReplaceAll(time.Now().Format("150405.000000000"), ".", "")
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal("admin connect failed")
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		admin.Close(ctx)
		t.Fatal(err)
	}
	admin.Close(ctx)
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err != nil {
			t.Errorf("admin connect for cleanup failed")
			return
		}
		defer c.Close(context.Background())
		if _, err := c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)"); err != nil {
			t.Errorf("drop test database: %v", err)
		}
	})
	cfg, err := pgxpool.ParseConfig(base)
	if err != nil {
		t.Fatal("bad UBYHOST_TEST_DATABASE_URL")
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	files, _ := filepath.Glob("../../../App/migrations_pg/*.sql")
	sort.Strings(files)
	for _, f := range files {
		raw, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		up := string(raw)
		if i := strings.Index(up, "-- +goose Up"); i >= 0 {
			up = up[i+len("-- +goose Up"):]
		}
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
	return pool
}

// seedValue turns a decoded JSON value into a query argument.
func seedValue(t *testing.T, v any) any {
	t.Helper()
	if n, ok := v.(json.Number); ok {
		i, err := n.Int64()
		if err != nil {
			t.Fatalf("seed number %s: %v", n, err)
		}
		return i
	}
	return v
}

// seed loads the golden rows and files; it returns the data directory.
func seed(t *testing.T, pool *pgxpool.Pool, g golden, now time.Time) string {
	t.Helper()
	ctx := context.Background()
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = "$" + strconv.Itoa(i+1)
		}
		sql := "INSERT INTO " + table.Table + " (" + strings.Join(table.Columns, ", ") + ") VALUES (" +
			strings.Join(marks, ", ") + ")"
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = seedValue(t, v)
			}
			if _, err := pool.Exec(ctx, sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
	}
	dir := t.TempDir()
	for _, f := range g.Files {
		folder := filepath.Join(dir, f.Dir)
		if err := os.MkdirAll(folder, 0o755); err != nil {
			t.Fatal(err)
		}
		path := filepath.Join(folder, f.Name)
		if f.Kind == "dir" {
			if err := os.Mkdir(path, 0o755); err != nil {
				t.Fatal(err)
			}
			continue
		}
		if err := os.WriteFile(path, []byte("golden"), 0o600); err != nil {
			t.Fatal(err)
		}
		at := now.Add(-time.Duration(f.MtimeAgo) * time.Second)
		if err := os.Chtimes(path, at, at); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

// rowLines reads every row of a query as one JSON line.
func rowLines(t *testing.T, pool *pgxpool.Pool, sql string) []string {
	t.Helper()
	rows, err := pool.Query(context.Background(), sql)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		vals, err := rows.Values()
		if err != nil {
			t.Fatal(err)
		}
		b, _ := json.Marshal(vals)
		out = append(out, string(b))
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	return out
}

func goldenLines(rows [][]any) []string {
	out := make([]string, 0, len(rows))
	for _, r := range rows {
		b, _ := json.Marshal(r)
		out = append(out, string(b))
	}
	return out
}

func compareLines(t *testing.T, what string, got, want []string) {
	t.Helper()
	if strings.Join(got, "\n") != strings.Join(want, "\n") {
		t.Errorf("%s differs from Python\n got:\n%s\nwant:\n%s", what, strings.Join(got, "\n"), strings.Join(want, "\n"))
	}
}

func goldenClock(t *testing.T, g golden) clock {
	t.Helper()
	now, err := time.Parse(time.RFC3339, g.Now)
	if err != nil {
		t.Fatal(err)
	}
	today, err := time.Parse("2006-01-02", g.Today)
	if err != nil {
		t.Fatal(err)
	}
	return clock{now: now, today: today, pragueToday: deadlines.LocalNow(now).Format("2006-01-02")}
}

// TestRunMatchesPython seeds the golden rows and files, runs the sweep at the
// golden clock and compares every count, the files left, the rows in the
// snapshot and the audit table with what the Python job did.
func TestRunMatchesPython(t *testing.T) {
	g := loadGolden(t)
	c := goldenClock(t, g)
	pool := dbPool(t)
	dir := seed(t, pool, g, c.now)
	sum, err := run(context.Background(), pool, dir, c)
	if err != nil {
		t.Fatal(err)
	}
	want := Summary{Photos: g.Counts.Photos, GuideOrphans: g.Counts.GuideOrphans, Payloads: g.Counts.Payloads,
		Drafts: g.Counts.Drafts, Signup: SignupCounts{UnverifiedDeleted: g.Counts.Signup.UnverifiedDeleted,
			ClickIDsCleared: g.Counts.Signup.ClickIDsCleared, MetaEventsExpired: g.Counts.Signup.MetaEventsExpired}}
	if sum != want {
		t.Errorf("counts %+v, Python %+v", sum, want)
	}
	var left []string
	for _, f := range g.Files {
		if _, err := os.Lstat(filepath.Join(dir, f.Dir, f.Name)); err == nil {
			left = append(left, f.Dir+"/"+f.Name)
		}
	}
	sort.Strings(left)
	compareLines(t, "files left", left, g.FilesLeft)
	for _, spec := range g.Snapshot {
		got := rowLines(t, pool, "SELECT "+strings.Join(spec.Columns, ", ")+" FROM "+spec.Table+" ORDER BY id")
		compareLines(t, spec.Table, got, goldenLines(g.After[spec.Table]))
	}
	got := rowLines(t, pool, "SELECT "+strings.Join(g.AuditColumns, ", ")+" FROM audit")
	wantAudit := goldenLines(g.After["audit"])
	sort.Strings(got)
	sort.Strings(wantAudit)
	compareLines(t, "audit", got, wantAudit)
}

// TestRunFailsOnReadOnlyPhotos: the Go service mounts /data read-only today.
// The first photo that must go fails the job, and no later step runs.
func TestRunFailsOnReadOnlyPhotos(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root ignores directory permissions")
	}
	g := loadGolden(t)
	c := goldenClock(t, g)
	pool := dbPool(t)
	dir := seed(t, pool, g, c.now)
	photos := filepath.Join(dir, "passport_photos")
	if err := os.Chmod(photos, 0o555); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = os.Chmod(photos, 0o755) })
	if _, err := run(context.Background(), pool, dir, c); err == nil {
		t.Fatal("run on a read-only photo directory returned nil")
	}
	var n int
	if err := pool.QueryRow(context.Background(), `SELECT count(*) FROM guest_form_draft`).Scan(&n); err != nil {
		t.Fatal(err)
	}
	if n != 6 {
		t.Errorf("drafts left %d, want all 6: a later step ran after the failure", n)
	}
}

func TestRunNeedsDataDir(t *testing.T) {
	if _, err := Run(context.Background(), nil, "", time.Now()); err == nil {
		t.Fatal("Run with no data dir returned nil")
	}
}
EOF
sha256sum go/internal/photosweep/sweep_test.go 2>&1 | tail -1
```

Expected: `589c765becaa3df94fb0c3eb643f5f07778fae857595a0416f1e90f02eb7cf6e  go/internal/photosweep/sweep_test.go`. Different: delete the file and repeat the step once; still different: STOP (§8).

### Step 4: create `go/cmd/ubyhost-web/register_job_photo_sweep.go`

```bash
mkdir -p go/cmd/ubyhost-web && cat > go/cmd/ubyhost-web/register_job_photo_sweep.go <<'EOF'
package main

// Lane J1 (brief 1209/1209b): the photo_sweep job, off until an operator adds
// photo_sweep to UBYHOST_GO_JOB_KINDS. Interval as scheduler.job_intervals().

import (
	"context"
	"log/slog"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/photosweep"
)

func init() {
	registerJob("photo_sweep", 12*60, func(pool *pgxpool.Pool) jobs.Handler {
		return func(ctx context.Context) (int, error) {
			sum, err := photosweep.Run(ctx, pool, os.Getenv("UBYHOST_DATA_DIR"), time.Now())
			if err == nil {
				slog.Info("photo sweep", "photos", sum.Photos, "guide_orphans", sum.GuideOrphans,
					"payloads", sum.Payloads, "drafts", sum.Drafts,
					"unverified_deleted", sum.Signup.UnverifiedDeleted,
					"click_ids_cleared", sum.Signup.ClickIDsCleared,
					"meta_events_expired", sum.Signup.MetaEventsExpired)
			}
			// Python's _log_run counts photos and payloads; the same here.
			return sum.Photos + sum.Payloads, err
		}
	})
}
EOF
sha256sum go/cmd/ubyhost-web/register_job_photo_sweep.go 2>&1 | tail -1
```

Expected: `ec8dbb262707e03219a9103d0f7b05a7fff8565141b92cf543c5b3f21d11c356  go/cmd/ubyhost-web/register_job_photo_sweep.go`. Different: delete the file and repeat the step once; still different: STOP (§8).

### Step 5: build, vet, test, commit

```bash
cd go && gofmt -l internal/photosweep cmd/ubyhost-web; go build ./... 2>&1 | tail -5; go vet ./internal/photosweep ./cmd/ubyhost-web 2>&1 | tail -5; go test ./internal/photosweep ./cmd/ubyhost-web -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -15; cd .. && git add go/internal/photosweep go/cmd/ubyhost-web/register_job_photo_sweep.go && git commit -q -m "1209b steps 1-4" && git status --short | tail -5
```

Expected: no gofmt/build/vet output; both packages `ok`. Without `UBYHOST_TEST_DATABASE_URL` the two DB tests print `--- SKIP` (fine here, CI's `go` job runs them; say so in the report); as root the read-only tests skip too.

## 5. Do not touch

`go/internal/metacapi/` (copy, never call or edit), `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_jobs.go` and every other `register_*.go`, `go/internal/hostweb/`, `go/internal/session/`, everything in `App/`, the 1209 files, `deploy/`, `docs/ENVIRONMENT.md`, `docs/context/`. Rules 2, 3, 4, 5 (§2). Never push, never merge.

## 6. Commands

Executor: step 5. Orchestrator, with a local PostgreSQL 16 (as the `postgres` user, data dir outside `/tmp/claude-0`):

```bash
su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1202/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1202/data -o '-p 54321 -k /var/tmp/pg1202' -l /var/tmp/pg1202/log start" 2>&1 | tail -2
```

```bash
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:54321/postgres go test ./internal/photosweep ./cmd/ubyhost-web ./internal/jobs -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -15
```

```bash
cd App && .venv/bin/python scripts/photo_sweep_golden.py | tail -1 && cd .. && git status --short | tail -3
```

Expected: `TestRunMatchesPython` PASS (the parity check); the golden re-run leaves `git status` clean.

## 7. Acceptance

- [ ] The four files exist with the sha256 values in §4.
- [ ] `go build ./...`, `go vet`, `go test ./internal/photosweep ./cmd/ubyhost-web` pass.
- [ ] `git diff --stat a83df541..HEAD` lists only the 1209 and 1209b §3 files.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found or a sha256 differs twice;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1209b-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`go/internal/photosweep/db.go` (every DELETE/UPDATE against its Python original, the per-account and per-platform transactions), `go/internal/photosweep/sweep.go` (order, first error stops), `go/cmd/ubyhost-web/register_job_photo_sweep.go` (data dir from `UBYHOST_DATA_DIR`, return value).

## Handover (coordinator only; this brief does not edit these)

- `docs/ENVIRONMENT.md` line 53 (`UBYHOST_GO_JOB_KINDS`): add `photo_sweep` to the list, with: "`photo_sweep` deletes files under `/data`: the `ubyhost-go` service needs `ubyhost-data:/data` mounted read-write (today `:ro`) before it is switched on; on a read-only mount every run fails at the first file."
- `docs/context/test-map.md`: new row "Go photo sweep | `test_go_photo_sweep_golden.py`; from `go/`: `go test ./internal/photosweep ./cmd/ubyhost-web`".
- `docs/context/known-issues.md`: "[go] `ubyhost-go` mounts `/data` read-only (`deploy/lightsail/docker-compose.yml`); Go jobs that delete files (photo_sweep, later retention) need it read-write. Go photo_sweep raises job_failed after 5 retries, Python at once."
- `docs/context/status.md`: "J1 photo_sweep in Go merged, off; switch needs the rw mount."

## Owner steps

After merge, to switch the job to Go (not before a compose change makes the mount read-write, which is its own PR):

1. On the server, edit `.env`: add `photo_sweep` to `UBYHOST_GO_JOB_KINDS` (it must also be in `UBYHOST_JOB_QUEUE_KINDS`).
2. Run `./scripts/deploy.sh`.
3. After 12 hours, check the audit log shows a `retention_delete` line for `passport_photos` written by Go and no `photo sweep` error in `docker compose logs ubyhost-go`.
4. To hand it back: remove `photo_sweep` from `UBYHOST_GO_JOB_KINDS` and run `./scripts/deploy.sh` again.
