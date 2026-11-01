package session

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

type golden struct {
	Secret    string `json:"secret"`
	Timestamp int64  `json:"timestamp"`
	Cases     []struct {
		Name    string          `json:"name"`
		Payload json.RawMessage `json:"payload"`
		Token   string          `json:"token"`
	} `json:"cases"`
}

// loadGolden reads the tokens written by App/scripts/session_golden.py.
func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "tokens.json"))
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) == 0 {
		t.Fatal("no golden cases")
	}
	return g
}

func firstDiff(a, b string) int {
	for i := 0; i < len(a) && i < len(b); i++ {
		if a[i] != b[i] {
			return i
		}
	}
	return min(len(a), len(b))
}

func TestGoldenTokens(t *testing.T) {
	g := loadGolden(t)
	now := time.Unix(g.Timestamp, 0)
	for _, c := range g.Cases {
		want, ok := decodePayload(c.Payload)
		if !ok {
			t.Fatalf("%s: bad golden payload", c.Name)
		}
		got, ok := Verify(g.Secret, c.Token, now)
		if !ok {
			t.Errorf("%s: token does not verify", c.Name)
			continue
		}
		if !reflect.DeepEqual(got, want) {
			t.Errorf("%s: payload %v, want %v", c.Name, got, want)
		}
		re := Sign(g.Secret, want, now)
		if re == c.Token {
			continue
		}
		if strings.HasPrefix(c.Token, ".") {
			// Python compressed this payload with zlib; Go's deflate output differs
			// (stdlib only), so Sign is checked by round trip (brief 0672 open question).
			if _, ok := Verify(g.Secret, re, now); !ok {
				t.Errorf("%s: Go-signed compressed-case token does not verify", c.Name)
			}
			continue
		}
		t.Errorf("%s: Sign differs from Python at byte %d", c.Name, firstDiff(re, c.Token))
	}
}

func TestNegativeCases(t *testing.T) {
	g := loadGolden(t)
	now := time.Unix(g.Timestamp, 0)
	token := g.Cases[0].Token
	b := []byte(token)
	if b[4] == 'a' {
		b[4] = 'b'
	} else {
		b[4] = 'a'
	}
	if _, ok := Verify(g.Secret, string(b), now); ok {
		t.Error("flipped byte verified")
	}
	if _, ok := Verify(g.Secret+"x", token, now); ok {
		t.Error("wrong secret verified")
	}
	payload := map[string]any{"uid": int64(7), "sv": int64(3), "iat": g.Timestamp}
	other, err := secure.NewTimedSerializer(g.Secret, "other-salt").Dumps(payload, now)
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := Verify(g.Secret, other, now); ok {
		t.Error("different salt verified")
	}
}

func TestSessionAge(t *testing.T) {
	g := loadGolden(t)
	base := time.Unix(g.Timestamp, 0)
	plain := Sign(g.Secret, map[string]any{"uid": int64(7), "sv": int64(3)}, base)
	if _, ok := Verify(g.Secret, plain, base.Add(11*time.Hour+59*time.Minute)); !ok {
		t.Error("plain token rejected at 11h59m")
	}
	if _, ok := Verify(g.Secret, plain, base.Add(12*time.Hour+time.Minute)); ok {
		t.Error("plain token accepted at 12h01m")
	}
	remember := Sign(g.Secret, map[string]any{"uid": int64(7), "sv": int64(3), "rm": int64(1)}, base)
	if _, ok := Verify(g.Secret, remember, base.Add(399*24*time.Hour)); !ok {
		t.Error("remember token rejected at 399 days")
	}
	if _, ok := Verify(g.Secret, remember, base.Add(401*24*time.Hour)); ok {
		t.Error("remember token accepted at 401 days")
	}
}

func TestImpersonationMaxAge(t *testing.T) {
	env := func(v string) func(string) string {
		return func(k string) string {
			if k == "UBYHOST_IMPERSONATION_MAX_HOURS" {
				return v
			}
			return ""
		}
	}
	cases := map[string]int64{"": 24 * 3600, "0": 0, "2": 2 * 3600, "x": 24 * 3600, "-3": 0}
	for raw, want := range cases {
		if got := impersonationMaxAge(env(raw)); got != want {
			t.Errorf("hours %q: got %d, want %d", raw, got, want)
		}
	}
}

// testPool and applyMigrations follow go/internal/payments/sweep_test.go.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_session_%d", time.Now().UnixNano())
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
	applyMigrations(t, pool)
	return pool
}

func applyMigrations(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
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
		if _, err := pool.Exec(context.Background(), up); err != nil {
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
}

const dbSecret = "session-db-test-secret-0123456789-abcd"

func dbEnv(k string) string {
	if k == "UBYHOST_SECRET_KEY" {
		return dbSecret
	}
	return ""
}

func TestLoadDatabase(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, created_at, role, active, session_version) VALUES
		(1, 'admin01', 'x', '2026-01-01T00:00:00+00:00', 'admin', 1, 1),
		(2, 'host01', 'x', '2026-01-01T00:00:00+00:00', 'host', 1, 1),
		(3, 'gone01', 'x', '2026-01-01T00:00:00+00:00', 'host', 0, 1)`); err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC().Truncate(time.Second)
	tok := func(p map[string]any) string { return Sign(dbSecret, p, now) }
	load := func(token string, env func(string) string) *Host {
		t.Helper()
		h, err := Load(ctx, pool, token, now, env)
		if err != nil {
			t.Fatal(err)
		}
		return h
	}

	if h := load(tok(map[string]any{"uid": int64(2), "sv": int64(9)}), dbEnv); h != nil {
		t.Error("wrong sv returned a host")
	}
	if h := load(tok(map[string]any{"uid": int64(3), "sv": int64(1)}), dbEnv); h != nil {
		t.Error("inactive account returned a host")
	}
	h := load(tok(map[string]any{"uid": int64(2), "sv": int64(1)}), dbEnv)
	if h == nil || h.Account.ID != 2 || h.Workspace.ID != 2 || h.Impersonating {
		t.Errorf("plain host: %+v", h)
	}
	h = load(tok(map[string]any{"uid": int64(1), "sv": int64(1), "as": int64(2), "ast": now.Unix()}), dbEnv)
	if h == nil || h.Workspace.ID != 2 || !h.Impersonating {
		t.Errorf("admin as: %+v", h)
	}
	h = load(tok(map[string]any{"uid": int64(2), "sv": int64(1), "as": int64(1), "ast": now.Unix()}), dbEnv)
	if h == nil || h.Workspace.ID != 2 || h.Impersonating {
		t.Errorf("non-admin as was honoured: %+v", h)
	}
	h = load(tok(map[string]any{"uid": int64(1), "sv": int64(1), "as": int64(2), "ast": now.Unix() - 25*3600}), dbEnv)
	if h == nil || !h.ImpersonationExpired || h.Workspace.ID != 1 {
		t.Errorf("expired ast: %+v", h)
	}
	h = load(tok(map[string]any{"uid": int64(1), "sv": int64(1), "as": int64(2)}), dbEnv)
	if h == nil || !h.ImpersonationExpired || h.Workspace.ID != 1 {
		t.Errorf("missing ast not expired: %+v", h)
	}

	pending, err := AcceptancePending(ctx, pool, 2, dbEnv)
	if err != nil || !pending {
		t.Fatalf("before acceptance: pending=%v err=%v", pending, err)
	}
	for i, doc := range []string{"terms", "privacy", "dpa"} {
		if _, err := pool.Exec(ctx, `INSERT INTO legal_acceptance (id, user_account_id, document, version, accepted_at, method) VALUES ($1, $2, $3, $4, $5, $6)`,
			int64(i+1), int64(2), doc, "1.7", "2026-01-01T00:00:00+00:00", "clickwrap"); err != nil {
			t.Fatal(err)
		}
	}
	pending, err = AcceptancePending(ctx, pool, 2, dbEnv)
	if err != nil || pending {
		t.Fatalf("after acceptance: pending=%v err=%v", pending, err)
	}
}
