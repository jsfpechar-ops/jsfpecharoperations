package guest

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

func TestGuestLanguage(t *testing.T) {
	SetGuestLanguages("en,cs,de")
	defer SetGuestLanguages("en,cs")
	if got := GuestLanguage("de-AT"); got != "de" {
		t.Fatalf("de-AT = %q", got)
	}
	if got := GuestLanguage("sk"); got != "cs" {
		t.Fatalf("sk = %q", got)
	}
	if got := GuestLanguage("xx"); got != defaultLang {
		t.Fatalf("xx = %q", got)
	}
}

func TestAcceptLanguage(t *testing.T) {
	SetGuestLanguages("en,cs,de")
	defer SetGuestLanguages("en,cs")
	if got := AcceptLanguage("de;q=0.9, en;q=0.8"); got != "de" {
		t.Fatalf("header = %q", got)
	}
}

func TestGuestLinkAndLangQuery(t *testing.T) {
	if got := GuestLink("tok", 0, "/privacy"); got != "/l/tok/privacy" {
		t.Fatalf("link %q", got)
	}
	if got := GuestLink("tok", 7, ""); got != "/l/tok/7" {
		t.Fatalf("res %q", got)
	}
	if got := LangQuery("de", ""); got != "?lang=de" {
		t.Fatalf("q %q", got)
	}
}

func TestLooksLikeSlug(t *testing.T) {
	if !looksLikeSlug("byt-dole-abc234") {
		t.Fatal("valid slug")
	}
	if looksLikeSlug("plaintexttoken") {
		t.Fatal("token not slug")
	}
}

func TestLanguageRequest(t *testing.T) {
	SetGuestLanguages("en,cs,de,fr")
	defer SetGuestLanguages("en,cs")
	r := httptest.NewRequest(http.MethodGet, "/l/tok?lang=fr", nil)
	r.AddCookie(&http.Cookie{Name: LangCookie, Value: "de"})
	if got := Language(r); got != "fr" {
		t.Fatalf("query wins: %q", got)
	}
	r = httptest.NewRequest(http.MethodGet, "/l/tok", nil)
	r.Header.Set("Accept-Language", "es")
	SetGuestLanguages("en,cs,es")
	if got := Language(r); got != "es" {
		t.Fatalf("accept %q", got)
	}
}

func TestResolveKeyToken(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	ctx := context.Background()
	stamp := "2026-01-01T00:00:00Z"
	aptID := time.Now().UnixNano() % 9000000000
	if aptID < 1000000 {
		aptID += 1000000
	}
	userID := aptID
	tok := fmt.Sprintf("perm%dtok", aptID)
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3) ON CONFLICT DO NOTHING`, userID, fmt.Sprintf("g%d@example.test", aptID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, permalink_pin, created_at)
		VALUES ($1, $2, 'Flat', 'Prague', 1, $3, '1234', $4)`, aptID, userID, tok, stamp)
	apt, link, moved, ok := ResolveKey(ctx, pool, tok)
	if !ok || apt == nil || link != tok || moved {
		t.Fatalf("resolve token ok=%v link=%q moved=%v", ok, link, moved)
	}
}

func TestOpenLinkSlugRedirect(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	ctx := context.Background()
	stamp := "2026-01-01T00:00:00Z"
	aptID := time.Now().UnixNano()%9000000000 + 1000000
	userID := aptID
	curSlug := fmt.Sprintf("flat-%06d-abc234", aptID%1000000)
	oldSlug := fmt.Sprintf("old-%06d-abc235", aptID%1000000)
	tok := fmt.Sprintf("perm%dtok", aptID)
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3) ON CONFLICT DO NOTHING`, userID, fmt.Sprintf("g%d@example.test", aptID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, permalink_pin, created_at)
		VALUES ($1, $2, 'Flat', 'Prague', 1, $3, '1234', $4)`, aptID, userID, tok, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment_slug (slug, apartment_id, is_current, created_at)
		VALUES ($1, $2, 1, $3)`, curSlug, aptID, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment_slug (slug, apartment_id, is_current, created_at)
		VALUES ($1, $2, 0, $3)`, oldSlug, aptID, stamp)
	r := httptest.NewRequest(http.MethodGet, "/l/"+oldSlug, nil)
	_, link, early := OpenLink(r, pool, oldSlug, "en")
	if early == nil {
		t.Fatal("want 301")
	}
	rr := httptest.NewRecorder()
	early.ServeHTTP(rr, r)
	if rr.Code != http.StatusMovedPermanently {
		t.Fatalf("status %d", rr.Code)
	}
	loc := rr.Header().Get("Location")
	if !strings.Contains(loc, curSlug) {
		t.Fatalf("location %q link %q", loc, link)
	}
}

func TestWritePageBase(t *testing.T) {
	r := httptest.NewRequest(http.MethodGet, "/l/tok", nil)
	rr := httptest.NewRecorder()
	WritePage(rr, r, http.StatusOK, Page{Lang: "en", LangURLs: map[string]string{"en": "/l/tok?lang=en"}}, nil)
	body := rr.Body.String()
	if !strings.Contains(body, "Guest registration") {
		t.Fatal("missing title")
	}
	if !strings.Contains(body, "tracking cookies") {
		t.Fatal("missing privacy line")
	}
}

func testPoolOptional(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := strings.TrimSpace(os.Getenv("UBYHOST_TEST_DATABASE_URL"))
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL not set")
		return nil
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_guest_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal(err)
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
		_, _ = c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)")
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
	migrateGuestPool(t, pool)
	return pool
}

func migrateGuestPool(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	ctx := context.Background()
	files, err := filepath.Glob("../../../../App/migrations_pg/*.sql")
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
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("migration %s: %v", f, err)
		}
	}
}

func mustExecGuest(t *testing.T, ctx context.Context, pool *pgxpool.Pool, q string, args ...any) {
	t.Helper()
	if _, err := pool.Exec(ctx, q, args...); err != nil {
		t.Fatalf("exec: %v", err)
	}
}
