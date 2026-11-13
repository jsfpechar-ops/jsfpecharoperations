package stayfeemail

// Go vs Python for the stay_fee_mail job (brief 1242). The golden
// testdata/stay_fee_job_golden.json is written by
// App/scripts/stay_fee_job_golden.py; the database tests skip without
// UBYHOST_TEST_DATABASE_URL (CI's Go job sets it).

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

type jobGolden struct {
	Seed     map[string][]map[string]any `json:"seed"`
	FakePDF  string                      `json:"fake_pdf"`
	Runs     []map[string]any            `json:"runs"`
	Writes   map[string]any              `json:"writes"`
	DueMonth []string                    `json:"due_month"`
}

func loadJobGolden(t *testing.T) *jobGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/stay_fee_job_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g jobGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return &g
}

// norm turns a Go value into the generic JSON form the golden decodes to.
func norm(t *testing.T, v any) any {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	var out any
	if err := json.Unmarshal(raw, &out); err != nil {
		t.Fatal(err)
	}
	return out
}

func sameJSON(t *testing.T, name string, got, want any) {
	t.Helper()
	g := norm(t, got)
	if !reflect.DeepEqual(g, want) {
		a, _ := json.MarshalIndent(g, "", " ")
		b, _ := json.MarshalIndent(want, "", " ")
		t.Errorf("%s:\n got %s\nwant %s", name, a, b)
	}
}

func TestDueMonthGolden(t *testing.T) {
	g := loadJobGolden(t)
	if len(g.DueMonth) != 730 {
		t.Fatalf("%d due_month rows", len(g.DueMonth))
	}
	for _, line := range g.DueMonth {
		parts := strings.Fields(line)
		today, err := time.Parse("2006-01-02", parts[1])
		if err != nil {
			t.Fatal(err)
		}
		got := "-"
		if m, ok := DueMonth(parts[0], today); ok {
			got = m.Format("2006-01-02")
		}
		if got != parts[2] {
			t.Errorf("due_month %s %s: got %s want %s", parts[0], parts[1], got, parts[2])
		}
	}
}

func TestHandlerNeedsRenderer(t *testing.T) {
	n, err := Handler(nil, Deps{Getenv: func(string) string { return "" }})(context.Background())
	if n != 0 || !errors.Is(err, ErrNoRenderer) {
		t.Fatalf("got %d, %v", n, err)
	}
	if _, err := Run(context.Background(), nil, Deps{}); !errors.Is(err, ErrNoRenderer) {
		t.Fatalf("Run: %v", err)
	}
}

func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_stayfeejob_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal(err)
	}
	_, err = admin.Exec(ctx, "CREATE DATABASE "+name)
	_ = admin.Close(ctx)
	if err != nil {
		t.Fatal(err)
	}
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
		t.Fatal(err)
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	files, err := filepath.Glob("../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatalf("no migrations found: %v", err)
	}
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

func goldenEnv(k string) string {
	switch k {
	case "UBYHOST_SECRET_KEY":
		return "golden-secret-key-not-for-real-use"
	case "UBYHOST_STAY_FEE_GUEST_PAY":
		return "on"
	case "UBYHOST_MAIL_BACKEND":
		return "console"
	case "UBYHOST_UBYPORT_ENV":
		return "mock"
	case "UBYHOST_APP_BASE_URL":
		return "https://app.example.test"
	case "UBYHOST_PUBLIC_BASE_URL":
		return "https://www.example.test"
	}
	return ""
}

func goldenKeys(t *testing.T) *secure.MultiFernet {
	t.Helper()
	keys, err := secure.LoadDataKeys(goldenEnv)
	if err != nil {
		t.Fatal(err)
	}
	return keys
}

// insertRow writes one seed row; extra adds columns, and encrypt maps a seed
// key to the column that gets its Fernet token.
func insertRow(t *testing.T, pool *pgxpool.Pool, table string, row map[string]any, extra map[string]any,
	encrypt map[string]string, keys *secure.MultiFernet) {
	t.Helper()
	cols, args, marks := []string{}, []any{}, []string{}
	merged := map[string]any{}
	for k, v := range row {
		merged[k] = v
	}
	for k, v := range extra {
		merged[k] = v
	}
	names := make([]string, 0, len(merged))
	for k := range merged {
		names = append(names, k)
	}
	sort.Strings(names)
	for _, k := range names {
		v := merged[k]
		col := k
		if enc, ok := encrypt[k]; ok {
			col = enc
			if s, _ := v.(string); s != "" {
				token, err := keys.EncryptString(s)
				if err != nil {
					t.Fatal(err)
				}
				v = token
			} else {
				v = nil
			}
		}
		if f, ok := v.(float64); ok {
			v = int64(f)
		}
		cols = append(cols, col)
		args = append(args, v)
		marks = append(marks, "$"+strconv.Itoa(len(args)))
	}
	sql := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)", table, strings.Join(cols, ", "), strings.Join(marks, ", "))
	if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
		t.Fatalf("%s: %v", table, err)
	}
}

func seedJob(t *testing.T, pool *pgxpool.Pool, g *jobGolden, keys *secure.MultiFernet) {
	t.Helper()
	old := "2026-09-01T00:00:00+00:00"
	stamp := map[string]any{"created_at": old}
	both := map[string]any{"created_at": old, "updated_at": old}
	for _, r := range g.Seed["users"] {
		insertRow(t, pool, "user_account", r, stamp, nil, keys)
	}
	for _, r := range g.Seed["legal_entities"] {
		insertRow(t, pool, "legal_entity", r, stamp, nil, keys)
	}
	for _, r := range g.Seed["apartments"] {
		insertRow(t, pool, "apartment", r, stamp, nil, keys)
	}
	for _, r := range g.Seed["reservations"] {
		insertRow(t, pool, "reservation", r, map[string]any{"uid": fmt.Sprintf("uid-%v", r["id"]),
			"created_at": old, "updated_at": old}, nil, keys)
	}
	for _, r := range g.Seed["guests"] {
		insertRow(t, pool, "guest", r, both, nil, keys)
	}
	for _, r := range g.Seed["adjustments"] {
		insertRow(t, pool, "stay_fee_adjustment", r, nil, map[string]string{"reason": "reason_enc"}, keys)
	}
	for _, r := range g.Seed["filings"] {
		insertRow(t, pool, "stay_fee_filing", r, nil, nil, keys)
	}
	for _, r := range g.Seed["outbox"] {
		insertRow(t, pool, "email_outbox", r, nil, nil, keys)
	}
	for _, r := range g.Seed["alerts"] {
		insertRow(t, pool, "alert", r, nil, nil, keys)
	}
	for _, table := range []string{"user_account", "legal_entity", "apartment", "reservation", "guest",
		"stay_fee_adjustment", "stay_fee_filing", "email_outbox", "alert", "audit"} {
		if _, err := pool.Exec(context.Background(), fmt.Sprintf(
			`SELECT setval(pg_get_serial_sequence('%[1]s', 'id'), COALESCE((SELECT MAX(id) FROM %[1]s), 0) + 1, false)`,
			table)); err != nil {
			t.Fatalf("setval %s: %v", table, err)
		}
	}
}

// fakeRenderer returns the golden's fixed bytes and records its input.
type fakeRenderer struct {
	pdf  []byte
	seen []any
	t    *testing.T
}

func (f *fakeRenderer) Render(h stayfee.Hlaseni) ([]byte, error) {
	f.seen = append(f.seen, norm(f.t, h))
	return f.pdf, nil
}

func (f *fakeRenderer) take() []any {
	out := f.seen
	if out == nil {
		out = []any{}
	}
	f.seen = nil
	return out
}

// queryMaps reads rows as column name -> value maps.
func queryMaps(t *testing.T, pool *pgxpool.Pool, sql string) []map[string]any {
	t.Helper()
	rows, err := pool.Query(context.Background(), sql)
	if err != nil {
		t.Fatal(err)
	}
	maps, err := pgx.CollectRows(rows, pgx.RowToMap)
	if err != nil {
		t.Fatal(err)
	}
	return maps
}

func pick(m map[string]any, keys ...string) map[string]any {
	out := map[string]any{}
	for _, k := range keys {
		out[k] = m[k]
	}
	return out
}

func snapshotJob(t *testing.T, pool *pgxpool.Pool, keys *secure.MultiFernet) map[string]any {
	t.Helper()
	open := func(v any) ([]byte, bool) {
		var token string
		switch x := v.(type) {
		case nil:
			return nil, false
		case []byte:
			token = string(x)
		case string:
			token = x
		}
		if token == "" {
			return nil, false
		}
		plain, err := keys.Decrypt(token, 0, time.Now())
		if err != nil {
			t.Fatalf("decrypt: %v", err)
		}
		return plain, true
	}
	b64 := func(v any) any {
		if plain, ok := open(v); ok {
			return base64.StdEncoding.EncodeToString(plain)
		}
		return nil
	}
	text := func(v any) any {
		if plain, ok := open(v); ok {
			return string(plain)
		}
		return nil
	}
	filings := []map[string]any{}
	for _, r := range queryMaps(t, pool, `SELECT * FROM stay_fee_filing ORDER BY id`) {
		f := pick(r, "id", "apartment_id", "period_key", "version", "cadence", "rate_czk", "liable_days",
			"exempt_days", "total_due_czk", "total_collected_czk", "created_at", "superseded_at")
		f["pdf"], f["csv"], f["payload"] = b64(r["pdf_enc"]), b64(r["csv_enc"]), text(r["payload_enc"])
		filings = append(filings, f)
	}
	adjustments := []map[string]any{}
	for _, r := range queryMaps(t, pool, `SELECT * FROM stay_fee_adjustment ORDER BY id`) {
		a := pick(r, "id", "apartment_id", "period_key", "direction", "mode", "people_count", "nights",
			"bed_days", "created_by", "created_at", "reversed_at", "reversed_by", "filing_id")
		a["reason"] = text(r["reason_enc"])
		adjustments = append(adjustments, a)
	}
	outbox := []map[string]any{}
	for _, r := range queryMaps(t, pool, `SELECT * FROM email_outbox ORDER BY idempotency_key`) {
		outbox = append(outbox, pick(r, "idempotency_key", "kind", "reservation_id", "apartment_id",
			"owner_user_id", "to_email", "cc_email", "subject", "payload", "state", "attempts"))
	}
	alerts := []map[string]any{}
	for _, r := range queryMaps(t, pool, `SELECT * FROM alert ORDER BY dedupe_key, id`) {
		a := pick(r, "level", "kind", "apartment_id", "reservation_id", "owner_user_id", "dedupe_key",
			"message", "detail", "params")
		a["resolved"] = r["resolved_at"] != nil
		alerts = append(alerts, a)
	}
	audit := []map[string]any{}
	for _, r := range queryMaps(t, pool, `SELECT * FROM audit WHERE action LIKE 'stay_fee%' ORDER BY id`) {
		audit = append(audit, pick(r, "at", "actor", "action", "detail", "owner_user_id", "actor_user_id"))
	}
	return map[string]any{"filings": filings, "adjustments": adjustments, "outbox": outbox,
		"alerts": alerts, "audit": audit}
}

func fixedNow(t *testing.T, s string) func() time.Time {
	t.Helper()
	at, err := time.Parse(time.RFC3339, s)
	if err != nil {
		t.Fatal(err)
	}
	return func() time.Time { return at }
}

func sameState(t *testing.T, name string, got, want map[string]any) {
	t.Helper()
	for _, part := range []string{"filings", "adjustments", "outbox", "alerts", "audit"} {
		sameJSON(t, name+" "+part, got[part], want[part])
	}
}

func TestJobGolden(t *testing.T) {
	pool := testPool(t)
	g := loadJobGolden(t)
	keys := goldenKeys(t)
	seedJob(t, pool, g, keys)
	pdf, err := base64.StdEncoding.DecodeString(g.FakePDF)
	if err != nil {
		t.Fatal(err)
	}
	fake := &fakeRenderer{pdf: pdf, t: t}
	ctx := context.Background()
	for _, run := range g.Runs {
		name := run["name"].(string)
		for _, sql := range run["before"].([]any) {
			if _, err := pool.Exec(ctx, sql.(string)); err != nil {
				t.Fatal(err)
			}
		}
		now := fixedNow(t, run["now"].(string))
		if got := pragueToday(now()).Format("2006-01-02"); got != run["today"] {
			t.Fatalf("%s: Prague today %s, golden %v", name, got, run["today"])
		}
		counts, err := Run(ctx, pool, Deps{Getenv: goldenEnv, Now: now, Renderer: fake, Keys: keys})
		if err != nil {
			t.Fatalf("%s: %v", name, err)
		}
		reconciled, err := ReconcileAllNoPayWay(ctx, pool, goldenEnv)
		if err != nil {
			t.Fatalf("%s reconcile: %v", name, err)
		}
		sameJSON(t, name+" counts", counts, run["counts"])
		sameJSON(t, name+" reconciled", reconciled, run["reconciled"])
		sameJSON(t, name+" rendered", fake.take(), run["rendered"])
		sameState(t, name, snapshotJob(t, pool, keys), run["state"].(map[string]any))
	}
	runWrites(t, pool, g, keys, fake)
}

func refusal(err error) string {
	switch {
	case err == nil:
		return "no error"
	case errors.Is(err, stayfee.ErrChanged):
		return "ValueError: filing changed"
	case errors.Is(err, stayfee.ErrOverlap):
		return "ValueError: overlaps saved period"
	case errors.Is(err, stayfee.ErrInactive):
		return "ValueError: inactive property"
	}
	return err.Error()
}

func runWrites(t *testing.T, pool *pgxpool.Pool, g *jobGolden, keys *secure.MultiFernet, fake *fakeRenderer) {
	ctx := context.Background()
	want := g.Writes
	now := fixedNow(t, "2026-10-20T06:00:00+00:00")
	today := stayfee.Day(2026, 10, 20)
	deps := stayfee.SaveDeps{Dec: stayfee.FernetDecrypter(keys), Enc: stayfee.FernetEncrypter(keys),
		Renderer: fake, Now: now, ScheduleToday: today}
	ap := map[int64]*stayfee.Apartment{}
	for _, id := range []int64{1, 3, 9} {
		a, err := stayfee.LoadApartment(ctx, pool, id)
		if err != nil {
			t.Fatal(err)
		}
		ap[id] = a
	}
	added, err := stayfee.AddAdjustment(ctx, pool, deps.Enc, stayfee.AdjustmentInput{ApartmentID: 1,
		PeriodKey: "2026-09", Direction: "add", Mode: "people", PeopleCount: 2, Nights: 3, BedDays: 6,
		Reason: "Correction: 2 people × 3 nights", CreatedBy: 1}, now())
	if err != nil {
		t.Fatal(err)
	}
	sameJSON(t, "added", added, want["added"])
	if err := stayfee.ReverseAdjustment(ctx, pool, 1, 1, now()); err != nil {
		t.Fatal(err)
	}
	live, err := stayfee.Latest(ctx, pool, 1, "2026-09")
	if err != nil || live == nil {
		t.Fatalf("latest: %v %v", live, err)
	}
	sameJSON(t, "replaced", live.ID, want["replaced"])
	sept := stayfee.Day(2026, 9, 1)
	corrected, err := stayfee.Save(ctx, pool, deps, ap[1], stayfee.SaveArgs{Month: sept,
		Collected: map[int64]int{101: 0}, IssuedOn: today, ReplacingID: &live.ID})
	if err != nil {
		t.Fatal(err)
	}
	sameJSON(t, "corrected", corrected, want["corrected"])
	_, err = stayfee.Save(ctx, pool, deps, ap[1], stayfee.SaveArgs{Month: sept, Collected: map[int64]int{},
		IssuedOn: today, ReplacingID: &live.ID})
	sameJSON(t, "changed", refusal(err), want["changed"])
	_, err = stayfee.Save(ctx, pool, deps, ap[3], stayfee.SaveArgs{Month: sept, Collected: map[int64]int{}, IssuedOn: today})
	sameJSON(t, "overlap", refusal(err), want["overlap"])
	_, err = stayfee.Save(ctx, pool, deps, ap[9], stayfee.SaveArgs{Month: sept, Collected: map[int64]int{}, IssuedOn: today})
	sameJSON(t, "inactive", refusal(err), want["inactive"])
	sameJSON(t, "writes rendered", fake.take(), want["rendered"])
	sameState(t, "writes", snapshotJob(t, pool, keys), want["state"].(map[string]any))
}

// Without a renderer Run writes nothing, even on a seeded database.
func TestRunNoRendererWritesNothing(t *testing.T) {
	pool := testPool(t)
	g := loadJobGolden(t)
	keys := goldenKeys(t)
	seedJob(t, pool, g, keys)
	before := snapshotJob(t, pool, keys)
	_, err := Run(context.Background(), pool, Deps{Getenv: goldenEnv, Keys: keys,
		Now: fixedNow(t, "2026-10-05T05:00:00+00:00")})
	if !errors.Is(err, ErrNoRenderer) {
		t.Fatalf("Run: %v", err)
	}
	if n, err := Handler(pool, Deps{Getenv: goldenEnv, Keys: keys})(context.Background()); n != 0 || !errors.Is(err, ErrNoRenderer) {
		t.Fatalf("Handler: %d %v", n, err)
	}
	sameJSON(t, "unchanged", snapshotJob(t, pool, keys), norm(t, before))
}
