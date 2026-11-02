package palette

import (
	"context"
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

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
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
	name := "ubyhost_go_palette_" + strings.ReplaceAll(time.Now().Format("150405.000000000"), ".", "")
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

func noEnv(string) string { return "" }

// host is a signed-in, non-admin account whose workspace is id.
func host(id int64, role string) *session.Host {
	a := session.Account{ID: id, Username: "owner@example.test", Role: role}
	return &session.Host{Account: a, Workspace: a}
}

func labels(items []object) []string {
	var out []string
	for _, it := range items {
		for _, f := range it {
			if f.k == "label" {
				out = append(out, f.v.(string))
			}
		}
	}
	return out
}

func seed(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	ctx := context.Background()
	stmts := []string{
		`INSERT INTO user_account (id, username, password_hash, role, created_at) VALUES (1, 'owner@example.test', 'x', 'host', '2026-01-01')`,
		`INSERT INTO user_account (id, username, password_hash, role, created_at) VALUES (2, 'admin@example.test', 'x', 'admin', '2026-01-01')`,
		`INSERT INTO apartment (id, owner_user_id, internal_name, city_en, uby_name, permalink_token, created_at) VALUES (7, 1, 'Byt Dole', 'Brno', 'UBY', 'tok7', '2026-01-01')`,
		`INSERT INTO apartment_slug (slug, apartment_id, is_current, created_at) VALUES ('byt-dole', 7, 1, '2026-01-01')`,
		`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, summary, created_at, updated_at) VALUES (1, 7, 'u1', '2026-05-01', '2026-05-03', 'Anna', '2026-01-01', '2026-01-01')`,
		`INSERT INTO submission (id, apartment_id, created_at, state) VALUES (1, 7, '2026-05-02', 'done')`,
	}
	for _, s := range stmts {
		if _, err := pool.Exec(ctx, s); err != nil {
			t.Fatal(err)
		}
	}
}

func TestEncodingKeepsOrderAndNoHTMLEscape(t *testing.T) {
	got, err := marshalNoHTML(struct {
		Items []object `json:"items"`
	}{Items: []object{{{"label", "A & <b>"}, {"tone", 3}}}})
	if err != nil {
		t.Fatal(err)
	}
	if want := `{"items":[{"label":"A & <b>","tone":3}]}`; string(got) != want {
		t.Fatalf("got %s want %s", got, want)
	}
}

func TestSignedInOneProperty(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	items, err := Items(context.Background(), pool, host(1, "host"), "en", noEnv)
	if err != nil {
		t.Fatal(err)
	}
	var hub string
	for _, it := range items {
		for _, f := range it {
			if f.k == "url" && strings.HasPrefix(f.v.(string), "/apartments/7?view=settings") {
				hub = f.v.(string)
			}
		}
	}
	if hub == "" {
		t.Fatal("one property should open its Settings group")
	}
	copyLink := ""
	for _, it := range items {
		for _, f := range it {
			if f.k == "copy" {
				copyLink = f.v.(string)
			}
		}
	}
	if copyLink != "http://127.0.0.1:8080/l/byt-dole" {
		t.Fatalf("copy link %q", copyLink)
	}
	if n := len(items); n < 20 {
		t.Fatalf("too few items: %d", n)
	}
}

func TestOtherOwnersStaysLeftOut(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	items, err := Items(context.Background(), pool, host(2, "admin"), "en", noEnv)
	if err != nil {
		t.Fatal(err)
	}
	for _, l := range labels(items) {
		if strings.Contains(l, "Byt Dole") {
			t.Fatalf("other owner's property leaked: %q", l)
		}
	}
}

func TestSignedOutIs401JSON(t *testing.T) {
	pool := testPool(t)
	req := httptest.NewRequest(http.MethodGet, "/api/command-palette", nil)
	rec := httptest.NewRecorder()
	Handler(pool, func(k string) string {
		if k == "UBYHOST_SECRET_KEY" {
			return strings.Repeat("s", 40)
		}
		if k == "UBYHOST_DEPLOYMENT" {
			return "production"
		}
		return ""
	}, time.Now)(rec, req)
	if rec.Code != http.StatusUnauthorized || rec.Body.String() != `{"items":[]}` {
		t.Fatalf("got %d %s", rec.Code, rec.Body.String())
	}
}

func TestAIGate(t *testing.T) {
	env := map[string]string{
		"UBYHOST_AI_FEATURES":       "havel",
		"UBYHOST_ANTHROPIC_API_KEY": "k",
	}
	get := func(k string) string { return env[k] }
	if !aiEnabledFor(get, "havel", "a@x") {
		t.Fatal("empty test list lets everyone in")
	}
	env["UBYHOST_AI_TEST_EMAILS"] = "b@x"
	if aiEnabledFor(get, "havel", "a@x") {
		t.Fatal("account not on the test list")
	}
	if !aiEnabledFor(get, "havel", "B@x") {
		t.Fatal("test list is case-insensitive")
	}
}

func TestLanguageCzech(t *testing.T) {
	want := catalog.T("cs", "nav.overview", nil)
	if want == "nav.overview" {
		t.Fatal("Czech catalog missing nav.overview")
	}
}

func TestTTLockGate(t *testing.T) {
	env := map[string]string{"UBYHOST_DOOR_CODES": "1", "UBYHOST_TTLOCK_CLIENT_ID": "id", "UBYHOST_TTLOCK_CLIENT_SECRET": "s"}
	if !ttlockEnabled(func(k string) string { return env[k] }) {
		t.Fatal("ttlock should be on")
	}
	env["UBYHOST_DOOR_CODES"] = "on"
	if ttlockEnabled(func(k string) string { return env[k] }) {
		t.Fatal("only 1, true or yes switch door codes on")
	}
}
