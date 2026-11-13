package guideimport

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
)

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL, applies
// the goose Up sections of App/migrations_pg and drops it at the end.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := "ubyhost_go_guideimport_" + strings.ReplaceAll(time.Now().Format("150405.000000000"), ".", "")
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
			return
		}
		defer c.Close(context.Background())
		c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)")
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

type fakeAI struct {
	reply map[string]any
	err   error
	calls int
	turn  string
}

func (f *fakeAI) Enabled(string) bool { return true }
func (f *fakeAI) Call(_ context.Context, _ string, _ []string, m []anthropic.Message, _ json.RawMessage, _ *string, _ int) (map[string]any, error) {
	f.calls++
	f.turn = m[0].Content
	return f.reply, f.err
}

type fakeFetch struct {
	item map[string]any
	err  error
}

func (f fakeFetch) Fetch(context.Context, string, string) (map[string]any, error) {
	return f.item, f.err
}

func seed(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	for _, q := range []string{
		`INSERT INTO user_account (id, username, password_hash, role, created_at) VALUES (1, 'o@example.test', 'x', 'host', '2026-01-01')`,
		`INSERT INTO apartment (id, owner_user_id, internal_name, city_en, uby_name, permalink_token, created_at) VALUES (7, 1, 'Flat', 'Brno', 'UBY', 'tok7', '2026-01-01')`,
		`INSERT INTO guide_import (id, apartment_id, source, url, status, created_at) VALUES (1, 7, 'booking', 'https://www.booking.com/hotel/cz/x.html', 'queued', '2026-11-13T10:00:00+00:00')`,
	} {
		if _, err := pool.Exec(context.Background(), q); err != nil {
			t.Fatal(err)
		}
	}
}

func str(t *testing.T, pool *pgxpool.Pool, q string, args ...any) string {
	t.Helper()
	var s *string
	if err := pool.QueryRow(context.Background(), q, args...).Scan(&s); err != nil {
		t.Fatal(err)
	}
	if s == nil {
		return "<null>"
	}
	return *s
}

func TestQueueFetchesAndFillsPage(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	ctx := context.Background()
	now := time.Date(2026, 11, 13, 10, 5, 0, 0, time.UTC)
	item := map[string]any{"name": "Flat", "description": "Quiet flat. Check-in 15:00.", "checkIn": "15:00", "photos": []any{"https://x/p.jpg"}}
	j := &Job{Pool: pool, Apify: fakeFetch{item: item}, AI: &fakeAI{}, Cfg: Config{Token: "t", MonthlyRuns: 40}, Now: func() time.Time { return now }}
	n, err := j.ProcessQueue(ctx, 3)
	if err != nil || n != 1 {
		t.Fatalf("n=%d err=%v", n, err)
	}
	if got := str(t, pool, "SELECT status FROM guide_import WHERE id = 1"); got != "done" {
		t.Errorf("status %s", got)
	}
	want := `{"source": "booking", "name": "Flat", "description": "Quiet flat. Check-in 15:00.", "checkIn": "15:00"}`
	if got := str(t, pool, "SELECT raw_json FROM guide_import WHERE id = 1"); got != want {
		t.Errorf("raw_json %s", got)
	}
	if got := str(t, pool, "SELECT description FROM property_page WHERE apartment_id = 7"); got != "Quiet flat. Check-in 15:00." {
		t.Errorf("description %s", got)
	}
	if got := str(t, pool, "SELECT checkin_text FROM property_page WHERE apartment_id = 7"); got != "15:00" {
		t.Errorf("checkin %s", got)
	}
	if got := str(t, pool, "SELECT photos_json FROM property_page WHERE apartment_id = 7"); got != "<null>" {
		t.Errorf("photos stored: %s", got)
	}
	if got := str(t, pool, "SELECT calls::text FROM lock_api_usage WHERE month = '2026-11' AND provider = 'apify'"); got != "1" {
		t.Errorf("calls %s", got)
	}
}

func TestQueueFailureBudgetAndStale(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	ctx := context.Background()
	now := time.Date(2026, 11, 13, 10, 5, 0, 0, time.UTC)
	j := &Job{Pool: pool, Apify: fakeFetch{err: &Error{"http_500"}}, AI: &fakeAI{}, Cfg: Config{Token: "t", MonthlyRuns: 40}, Now: func() time.Time { return now }}
	if n, err := j.ProcessQueue(ctx, 3); err != nil || n != 1 {
		t.Fatalf("n=%d err=%v", n, err)
	}
	if got := str(t, pool, "SELECT error FROM guide_import WHERE id = 1"); got != "http_500" {
		t.Errorf("error %s", got)
	}
	// budget: one run counted, limit 1 -> the next queued row fails with 'budget'
	pool.Exec(ctx, `INSERT INTO guide_import (id, apartment_id, source, url, status, created_at) VALUES (2, 7, 'airbnb', 'https://www.airbnb.com/rooms/1', 'queued', '2026-11-13T10:00:00+00:00')`)
	j.Cfg.MonthlyRuns = 1
	if n, err := j.ProcessQueue(ctx, 3); err != nil || n != 0 {
		t.Fatalf("n=%d err=%v", n, err)
	}
	if got := str(t, pool, "SELECT error FROM guide_import WHERE id = 2"); got != "budget" {
		t.Errorf("error %s", got)
	}
	// stale: running for more than 800 s
	pool.Exec(ctx, `INSERT INTO guide_import (id, apartment_id, source, url, status, created_at, started_at) VALUES (3, 7, 'airbnb', 'https://www.airbnb.com/rooms/2', 'running', '2026-11-13T09:00:00+00:00', '2026-11-13T09:50:00+00:00')`)
	pool.Exec(ctx, `INSERT INTO guide_import (id, apartment_id, source, url, status, created_at, started_at) VALUES (4, 7, 'airbnb', 'https://www.airbnb.com/rooms/3', 'running', '2026-11-13T09:00:00+00:00', '2026-11-13T10:00:00+00:00')`)
	j.Now = func() time.Time { return time.Date(2026, 11, 13, 10, 5, 0, 0, time.UTC) }
	j.Cfg.Token = ""
	j.ProcessQueue(ctx, 3)
	if got := str(t, pool, "SELECT error FROM guide_import WHERE id = 3"); got != "stale" {
		t.Errorf("row 3 error %s", got)
	}
	if got := str(t, pool, "SELECT status FROM guide_import WHERE id = 4"); got != "running" {
		t.Errorf("row 4 status %s", got)
	}
}

func TestPendingMergesCards(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	ctx := context.Background()
	raw := `{"source": "booking", "description": "Check-in from 15:00 at the key box, code 4821."}`
	pool.Exec(ctx, `UPDATE guide_import SET status = 'done', raw_json = $1 WHERE id = 1`, raw)
	// a host-written card must stay, a missing one is filled
	pool.Exec(ctx, `INSERT INTO guide_item (apartment_id, topic, kind, source, sort_order, state, steps, created_at, updated_at) VALUES (7, 'wifi', 'wifi', 'host', 5, 'done', 'host text', 'n', 'n')`)
	ai := &fakeAI{reply: map[string]any{"cards": []any{
		map[string]any{"kind": "checkin", "topic": "", "title": "", "location": "Key box", "steps": "Check in from 15:00.\nCode 4821.", "watch_out": "",
			"quotes": []any{"Check-in from 15:00 at the key box, code 4821"}},
		map[string]any{"kind": "wifi", "topic": "", "title": "", "location": "Router", "steps": "Check in from 15:00.", "watch_out": "",
			"quotes": []any{"Check-in from 15:00 at the key box"}},
		map[string]any{"kind": "custom", "topic": "rooms", "title": "Pool", "location": "", "steps": "Open 15:00", "watch_out": "",
			"quotes": []any{"Check-in from 15:00 at the key box"}},
	}}}
	j := &Job{Pool: pool, Apify: fakeFetch{}, AI: ai, Cfg: Config{Token: "t"}, Now: func() time.Time { return time.Date(2026, 11, 13, 10, 5, 0, 0, time.UTC) }}
	n, err := j.ProcessPending(ctx, 3)
	if err != nil || n != 1 {
		t.Fatalf("n=%d err=%v", n, err)
	}
	if got := str(t, pool, "SELECT status FROM guide_import WHERE id = 1"); got != "used" {
		t.Errorf("status %s", got)
	}
	if got := str(t, pool, "SELECT raw_json FROM guide_import WHERE id = 1"); got != "<null>" {
		t.Errorf("raw kept: %s", got)
	}
	if got := str(t, pool, "SELECT state || '|' || source || '|' || steps || '|' || sort_order FROM guide_item WHERE kind = 'checkin'"); got != "check|booking|Check in from 15:00.\nCode 4821.|0" {
		t.Errorf("checkin card %q", got)
	}
	if got := str(t, pool, "SELECT steps FROM guide_item WHERE kind = 'wifi'"); got != "host text" {
		t.Errorf("host card overwritten: %s", got)
	}
	if got := str(t, pool, "SELECT count(*)::text FROM guide_item WHERE kind = 'custom'"); got != "1" {
		t.Errorf("custom card count %s", got)
	}
}

func TestPendingModelFailureCountsAttempts(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	ctx := context.Background()
	pool.Exec(ctx, `UPDATE guide_import SET status = 'done', raw_json = '{"source": "booking", "name": "Flat"}' WHERE id = 1`)
	ai := &fakeAI{err: &anthropic.Error{Reason: "api"}}
	j := &Job{Pool: pool, Apify: fakeFetch{}, AI: ai, Cfg: Config{Token: "t"}, Now: func() time.Time { return time.Now() }}
	for i, want := range []string{"merge:api:1", "merge:api:2", "merge:api"} {
		if n, err := j.ProcessPending(ctx, 3); err != nil || n != 0 {
			t.Fatalf("round %d n=%d err=%v", i, n, err)
		}
		if got := str(t, pool, "SELECT error FROM guide_import WHERE id = 1"); got != want {
			t.Errorf("round %d error %q, want %q", i, got, want)
		}
	}
	if got := str(t, pool, "SELECT status || coalesce(raw_json, '-') FROM guide_import WHERE id = 1"); got != "failed-" {
		t.Errorf("final %s", got)
	}
	// a budget error pauses without touching the row
	pool.Exec(ctx, `UPDATE guide_import SET status = 'done', error = NULL, raw_json = '{"source": "booking", "name": "Flat"}' WHERE id = 1`)
	ai.err = &anthropic.Error{Reason: "month", Budget: true}
	j.ProcessPending(ctx, 3)
	if got := str(t, pool, "SELECT coalesce(error, 'none') FROM guide_import WHERE id = 1"); got != "none" {
		t.Errorf("budget pause changed the row: %s", got)
	}
}

func TestRealServiceLedger(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte(`{"content":[{"type":"text","text":"{\"cards\": []}"}],"stop_reason":"end_turn","usage":{"input_tokens":100,"cache_creation_input_tokens":10,"cache_read_input_tokens":5,"output_tokens":20}}`))
	}))
	defer srv.Close()
	env := map[string]string{"UBYHOST_AI_FEATURES": "guide_import", "UBYHOST_ANTHROPIC_API_KEY": "k"}
	s := anthropic.NewService(pool, anthropic.ConfigFromEnv(func(n string) (string, bool) { v, ok := env[n]; return v, ok }))
	c := anthropic.NewClient("k")
	c.BaseURL = srv.URL
	s.Anthropic = c
	key := "7"
	for i := 0; i < 2; i++ {
		if _, err := s.Call(ctx, "guide_import", []string{"s"}, []anthropic.Message{{Role: "user", Content: "u"}}, json.RawMessage(`{}`), &key, 0); err != nil {
			t.Fatal(err)
		}
	}
	if got := str(t, pool, "SELECT requests::text || ',' || input_tokens || ',' || cache_write_tokens || ',' || cache_read_tokens || ',' || output_tokens FROM ai_usage WHERE feature = 'guide_import' AND key = '7'"); got != "2,200,20,10,40" {
		t.Errorf("ledger %s", got)
	}
}
