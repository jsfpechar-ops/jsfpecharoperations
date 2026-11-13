package layout

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"regexp"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// pinnedEnv is PINNED_ENV in App/scripts/go_layout_golden.py.
var pinnedEnv = map[string]string{
	"UBYHOST_UBYPORT_ENV":     "mock",
	"UBYHOST_DEPLOYMENT":      "local",
	"UBYHOST_OPERATOR_EMAIL":  "",
	"UBYHOST_PUBLIC_BASE_URL": "http://127.0.0.1:8080",
	"UBYHOST_SECRET_KEY":      "golden-secret-key-not-for-real-use",
}

func getenv(k string) string { return pinnedEnv[k] }

type goldenCase struct {
	Name           string `json:"name"`
	URL            string `json:"url"`
	Cookie         string `json:"cookie"`
	V2             bool   `json:"v2"`
	Nav            string `json:"nav"`
	BodyKind       string `json:"body_kind"`
	HowKey         string `json:"how_key"`
	ShowNav        bool   `json:"show_nav"`
	AdminWorkspace bool   `json:"admin_workspace"`
	BackURL        string `json:"back_url"`
	IsAdmin        bool   `json:"is_admin"`
	Impersonating  bool   `json:"impersonating"`
	DisplayName    string `json:"display_name"`
	Username       string `json:"username"`
	DeletionDueAt  string `json:"deletion_due_at"`
	PropertyCount  int    `json:"property_count"`
	MinutesLeft    *int   `json:"minutes_left"`
	Title          string `json:"title"`
	SetCookie      string `json:"set_cookie"`
}

var (
	wsRun     = regexp.MustCompile(`\s+`)
	afterTag  = regexp.MustCompile(`> `)
	beforeTag = regexp.MustCompile(` <`)
)

// normalise is the golden comparison: html/template writes "+" as &#43;,
// whitespace runs become one space, and the space next to a tag goes.
func normalise(s string) string {
	s = strings.ReplaceAll(s, "&#43;", "+")
	s = wsRun.ReplaceAllString(s, " ")
	s = afterTag.ReplaceAllString(s, ">")
	s = beforeTag.ReplaceAllString(s, "<")
	return strings.TrimSpace(s)
}

func goldenTemplates(t *testing.T) *Templates {
	t.Helper()
	tpl, err := Parse(nil, os.DirFS("testdata"), "golden_page.html")
	if err != nil {
		t.Fatal(err)
	}
	return tpl
}

func TestGoldenMatchesPython(t *testing.T) {
	raw, err := os.ReadFile("testdata/golden_cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var file struct {
		Value string       `json:"value"`
		Cases []goldenCase `json:"cases"`
	}
	if err := json.Unmarshal(raw, &file); err != nil {
		t.Fatal(err)
	}
	if len(file.Cases) < 3 {
		t.Fatalf("want 3 cases, got %d", len(file.Cases))
	}
	tpl := goldenTemplates(t)
	for _, c := range file.Cases {
		t.Run(c.Name, func(t *testing.T) {
			want, err := os.ReadFile("testdata/" + c.Name + ".html")
			if err != nil {
				t.Fatal(err)
			}
			r := httptest.NewRequest(http.MethodGet, c.URL, nil)
			if c.Cookie != "" {
				r.Header.Set("Cookie", c.Cookie)
			}
			name := c.DisplayName
			if name == "" {
				name = c.Username
			}
			sh := shell{
				SignedIn: true, IsAdmin: c.IsAdmin, Impersonating: c.Impersonating,
				WorkspaceName: name, WorkspaceUsername: c.Username,
				DeletionDueAt: c.DeletionDueAt, PropertyCount: c.PropertyCount, MinutesLeft: c.MinutesLeft,
			}
			p := Page{
				Title: c.Title, Nav: c.Nav, BodyKind: c.BodyKind, V2: c.V2, HideNav: !c.ShowNav,
				HowKey: c.HowKey, BackURL: c.BackURL, AdminWorkspace: c.AdminWorkspace,
			}
			w := httptest.NewRecorder()
			env := Env{Getenv: getenv, Now: time.Date(2026, 11, 13, 9, 0, 0, 0, time.UTC)}
			if err := render(w, r, env, sh, "GOLDEN-CSRF", p, tpl, "golden", map[string]any{"Value": file.Value}); err != nil {
				t.Fatal(err)
			}
			got, exp := normalise(w.Body.String()), normalise(string(want))
			if got != exp {
				i := 0
				for i < len(got) && i < len(exp) && got[i] == exp[i] {
					i++
				}
				lo := max(0, i-120)
				t.Fatalf("differs at byte %d\n go: %s\n py: %s", i, got[lo:min(len(got), i+200)], exp[lo:min(len(exp), i+200)])
			}
			var lang *http.Cookie
			for _, ck := range w.Result().Cookies() {
				if ck.Name == "ubyhost_lang" {
					lang = ck
				}
			}
			if (lang != nil) != (c.SetCookie != "") {
				t.Fatalf("lang cookie: go %v, python %q", lang, c.SetCookie)
			}
			if lang != nil {
				py := fmt.Sprintf("ubyhost_lang=%s; Max-Age=%d; Path=/; SameSite=lax", lang.Value, lang.MaxAge)
				if py != c.SetCookie || lang.HttpOnly || lang.SameSite != http.SameSiteLaxMode {
					t.Fatalf("lang cookie %q, python %q", py, c.SetCookie)
				}
			}
			if ct := w.Header().Get("Content-Type"); ct != "text/html; charset=utf-8" {
				t.Fatalf("content type %q", ct)
			}
		})
	}
}

func TestConcurrentRendersKeepTheirLanguage(t *testing.T) {
	tpl := goldenTemplates(t)
	var wg sync.WaitGroup
	errs := make(chan error, 60)
	for i := 0; i < 60; i++ {
		lang := []string{"en", "cs", "vi"}[i%3]
		wg.Add(1)
		go func() {
			defer wg.Done()
			r := httptest.NewRequest(http.MethodGet, "/reservations?lang="+lang, nil)
			w := httptest.NewRecorder()
			sh := shell{SignedIn: true, WorkspaceName: "A", WorkspaceUsername: "a"}
			if err := render(w, r, Env{Getenv: getenv, Now: time.Now()}, sh, "tok", Page{Title: "x"}, tpl, "golden", map[string]any{"Value": lang}); err != nil {
				errs <- err
				return
			}
			want := `<html lang="` + lang + `">`
			skip := Strings.T(lang, "a11y.skip_to_content", nil)
			if body := w.Body.String(); !strings.Contains(body, want) || !strings.Contains(body, skip) {
				errs <- fmt.Errorf("render for %s lost its language", lang)
			}
		}()
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		t.Fatal(err)
	}
}

func TestMacrosEscapeAndBind(t *testing.T) {
	c := &reqCtx{lang: "en", layout: Strings}
	h, err := c.uiButton(`<b>"x"</b>`, "primary", map[string]any{"href": "/a?b=1&c=2"})
	if err != nil {
		t.Fatal(err)
	}
	if want := `<a class="ui-btn ui-btn-primary" href="/a?b=1&amp;c=2"><span>&lt;b&gt;&#34;x&#34;&lt;/b&gt;</span></a>`; string(h) != want {
		t.Fatalf("ui_button = %s", h)
	}
	if _, err := c.uiButton("x", map[string]any{"nope": 1}); err == nil {
		t.Fatal("unknown keyword accepted")
	}
	if _, err := icon("no-such-icon"); err == nil {
		t.Fatal("unknown icon accepted")
	}
	if _, err := kv("a"); err == nil {
		t.Fatal("odd kv accepted")
	}
	if got := c.tp("nav.property_count", 1); got != Strings.T("en", "nav.property_count.one", map[string]any{"count": 1}) {
		t.Fatalf("tp one = %q", got)
	}
	if got := c.t("no.such.key"); got != "no.such.key" {
		t.Fatalf("missing key = %q", got)
	}
	page := hostweb.Catalog{"en": {"nav.stays": "Page stays"}}
	c.page = page
	if got := c.t("nav.stays"); got != "Page stays" {
		t.Fatalf("page catalog not first: %q", got)
	}
	if got := truncate("Some help text that is rather long so the truncate filter has to cut it off", 50); got != "Some help text that is rather long so the..." {
		t.Fatalf("truncate = %q", got)
	}
	if got := datetimeLocal("2026-07-01T10:00:00"); got != "2026-07-01 12:00" {
		t.Fatalf("datetime_local summer = %q", got)
	}
	if got := datetimeLocal("not a date at all"); got != "not a date at al" {
		t.Fatalf("datetime_local raw = %q", got)
	}
}

func TestMinutesLeft(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	h := &session.Host{Impersonating: true, Payload: map[string]any{"ast": int64(now.Unix() - 61)}}
	env := map[string]string{"UBYHOST_IMPERSONATION_MAX_HOURS": "1"}
	if m := minutesLeft(h, func(k string) string { return env[k] }, now); m == nil || *m != 59 {
		t.Fatalf("minutes = %v", m)
	}
	env["UBYHOST_IMPERSONATION_MAX_HOURS"] = "0"
	if m := minutesLeft(h, func(k string) string { return env[k] }, now); m != nil {
		t.Fatal("no limit must be nil")
	}
	h.Impersonating = false
	if minutesLeft(h, getenv, now) != nil {
		t.Fatal("outside an impersonation must be nil")
	}
}

func TestCSRFTokenBindsTheNonceCookie(t *testing.T) {
	now := time.Now()
	r := httptest.NewRequest(http.MethodGet, "/", nil)
	token, cookie, err := csrfToken(r, "s3cret", getenv, now)
	if err != nil || cookie == nil || !cookie.HttpOnly || cookie.SameSite != http.SameSiteStrictMode || len(cookie.Value) != 43 {
		t.Fatalf("new nonce: %v %+v", err, cookie)
	}
	var payload map[string]any
	if err := secure.NewTimedSerializer("s3cret", csrfSalt).Loads(token, time.Hour, now, &payload); err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256([]byte(cookie.Value))
	if payload["nonce"] != hex.EncodeToString(sum[:]) {
		t.Fatal("token not bound to the cookie nonce")
	}
	r.AddCookie(cookie)
	if _, again, _ := csrfToken(r, "s3cret", getenv, now); again != nil {
		t.Fatal("a request with a nonce must not get a new cookie")
	}
}

func TestShellQuery(t *testing.T) {
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_layout_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal("admin connect failed")
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		t.Fatal(err)
	}
	admin.Close(ctx)
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err == nil {
			_, _ = c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)")
			c.Close(context.Background())
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
	defer pool.Close()
	for _, q := range []string{
		`CREATE TABLE user_account (id BIGINT PRIMARY KEY, username TEXT, display_name TEXT, deletion_due_at TEXT)`,
		`CREATE TABLE apartment (id BIGINT PRIMARY KEY, owner_user_id BIGINT, archived_at TEXT)`,
		`INSERT INTO user_account VALUES (1, 'admin-1', 'Admin', NULL), (2, 'host-2', NULL, '2026-12-01T10:00:00')`,
		`INSERT INTO apartment VALUES (1, 2, NULL), (2, 2, NULL), (3, 2, '2026-01-01'), (4, 1, NULL)`,
	} {
		if _, err := pool.Exec(ctx, q); err != nil {
			t.Fatal(err)
		}
	}
	h := &session.Host{
		Account:       session.Account{ID: 1, Username: "admin-1", Role: "admin"},
		Workspace:     session.Account{ID: 2, Username: "host-2", Role: "host"},
		Impersonating: true, Payload: map[string]any{},
	}
	sh, err := loadShell(ctx, Env{Pool: pool, Getenv: getenv, Now: time.Now()}, h)
	if err != nil {
		t.Fatal(err)
	}
	if sh.WorkspaceName != "host-2" || sh.PropertyCount != 2 || sh.DeletionDueAt != "2026-12-01T10:00:00" || !sh.IsAdmin || !sh.Impersonating {
		t.Fatalf("shell = %+v", sh)
	}
	w := httptest.NewRecorder()
	r := httptest.NewRequest(http.MethodGet, "/reservations", nil)
	env := Env{Pool: pool, Getenv: getenv, Now: time.Now()}
	if err := Render(w, r, env, h, Page{Title: "T", Status: http.StatusNotFound}, goldenTemplates(t), "golden", map[string]any{"Value": "v"}); err != nil {
		t.Fatal(err)
	}
	body := w.Body.String()
	if w.Code != http.StatusNotFound || !strings.Contains(body, "@host-2") || !strings.Contains(body, `name="csrf-token" content="`) {
		t.Fatalf("Render: %d", w.Code)
	}
	if !strings.Contains(w.Header().Get("Set-Cookie"), "ubyhost_csrf=") {
		t.Fatal("Render did not set the CSRF nonce cookie")
	}
	if err := Render(w, r, env, h, Page{}, goldenTemplates(t), "missing", nil); err == nil {
		t.Fatal("unknown page template accepted")
	}
}
