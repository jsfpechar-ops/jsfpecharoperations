package guest

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

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
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES (9020172001, 'g17201720a1@example.test', 'x', 'host', 1, $1) ON CONFLICT DO NOTHING`, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, permalink_pin, created_at)
		VALUES (9020172001, 9020172001, 'Flat 1720', 'Prague', 1, 'perm1720abcxyz', '1234', $1) ON CONFLICT DO NOTHING`, stamp)
	apt, link, moved, ok := ResolveKey(ctx, pool, "perm1720abcxyz")
	if !ok || apt == nil || link != "perm1720abcxyz" || moved {
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
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES (9020172002, 'g17201720a2@example.test', 'x', 'host', 1, $1) ON CONFLICT DO NOTHING`, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, permalink_pin, created_at)
		VALUES (9020172002, 9020172002, 'Flat 1721', 'Prague', 1, 'perm1721abcxyz', '1234', $1) ON CONFLICT DO NOTHING`, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment_slug (slug, apartment_id, is_current, created_at)
		VALUES ('flat-1721-abc234', 9020172002, 1, $1) ON CONFLICT (slug) DO NOTHING`, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment_slug (slug, apartment_id, is_current, created_at)
		VALUES ('old-flat-abc235', 9020172002, 0, $1) ON CONFLICT (slug) DO NOTHING`, stamp)
	r := httptest.NewRequest(http.MethodGet, "/l/old-flat-abc235", nil)
	_, link, early := OpenLink(r, pool, "old-flat-abc235", "en")
	if early == nil {
		t.Fatal("want 301")
	}
	rr := httptest.NewRecorder()
	early.ServeHTTP(rr, r)
	if rr.Code != http.StatusMovedPermanently {
		t.Fatalf("status %d", rr.Code)
	}
	loc := rr.Header().Get("Location")
	if !strings.Contains(loc, "flat-1721-abc234") {
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
	url := strings.TrimSpace(os.Getenv("UBYHOST_TEST_DATABASE_URL"))
	if url == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL not set")
		return nil
	}
	pool, err := pgxpool.New(context.Background(), url)
	if err != nil {
		t.Fatalf("pool: %v", err)
	}
	return pool
}

func mustExecGuest(t *testing.T, ctx context.Context, pool *pgxpool.Pool, sql string, args ...any) {
	t.Helper()
	if _, err := pool.Exec(ctx, sql, args...); err != nil {
		t.Fatalf("exec: %v", err)
	}
}
