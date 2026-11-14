package turnstile

import (
	"context"
	"fmt"
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
)

// These tests need UBYHOST_TEST_DATABASE_URL (testPool skips without it).

func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_turnstile_%d", time.Now().UnixNano())
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
	files, err := filepath.Glob("../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatal("no migrations found")
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

// TestFailOpenBudget is _fail_open end to end: with siteverify down, one
// address passes five times per action in 15 minutes, then is refused; each
// call refreshes one open turnstile_unavailable alert; another action or
// address has its own budget; after the window the address passes again.
func TestFailOpenBudget(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	g := loadGolden(t)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer srv.Close()
	at := time.Date(2026, 11, 14, 9, 0, 0, 0, time.UTC)
	v := Verifier{Pool: pool, Getenv: verifyEnv(g), URL: srv.URL, Now: func() time.Time { return at }}
	req := func(addr string) *http.Request {
		r := httptest.NewRequest("POST", "/login", nil)
		r.RemoteAddr = addr + ":1234"
		return r
	}
	for i := 1; i <= 6; i++ {
		ok, err := v.Verify(ctx, req("203.0.113.9"), "tok", "host_login")
		if err != nil {
			t.Fatal(err)
		}
		if ok != (i <= 5) {
			t.Fatalf("attempt %d: %v", i, ok)
		}
	}
	for _, c := range []struct{ addr, action string }{{"203.0.113.9", "guest_claim"}, {"203.0.113.10", "host_login"}} {
		if ok, err := v.Verify(ctx, req(c.addr), "tok", c.action); !ok || err != nil {
			t.Fatalf("%s %s: %v %v, want its own budget", c.addr, c.action, ok, err)
		}
	}
	var n int
	var level, msg, key string
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM alert WHERE kind = 'turnstile_unavailable' AND resolved_at IS NULL`).Scan(&n); err != nil || n != 2 {
		t.Fatalf("open alerts %d %v, want 2 (one per action)", n, err)
	}
	if err := pool.QueryRow(ctx, `SELECT level, message, dedupe_key FROM alert WHERE dedupe_key = 'turnstile_unavailable:host_login'`).Scan(&level, &msg, &key); err != nil {
		t.Fatal(err)
	}
	if level != "warning" || msg != alertMessage {
		t.Fatalf("alert %q %q", level, msg)
	}
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM rate_limit_event WHERE scope = 'turnstile_unreachable' AND key = '203.0.113.9:host_login'`).Scan(&n); err != nil || n != 5 {
		t.Fatalf("rate rows %d %v, want 5", n, err)
	}
	at = at.Add(15*time.Minute + time.Second)
	if ok, err := v.Verify(ctx, req("203.0.113.9"), "tok", "host_login"); !ok || err != nil {
		t.Fatalf("after the window: %v %v", ok, err)
	}
}
