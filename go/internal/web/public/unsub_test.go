package public

import (
	"context"
	"encoding/json"
	"fmt"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"testing"
	"text/template/parse"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/lifecyclemail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// unsubFile is testdata/unsub/cases.json (App/scripts/public_unsubscribe_golden.py).
type unsubFile struct {
	Secret  string            `json:"secret"`
	Address string            `json:"address"`
	Tokens  map[string]string `json:"tokens"`
	Cases   []unsubCase       `json:"cases"`
}

type unsubRows struct {
	Users map[string]struct {
		OptOut     int  `json:"opt_out"`
		OptOutAtOn bool `json:"opt_out_at_set"`
	} `json:"users"`
	Suppressions []struct {
		EmailHash string `json:"email_hash"`
		Scope     string `json:"scope"`
	} `json:"suppressions"`
	Audit []struct {
		Actor      string `json:"actor"`
		Action     string `json:"action"`
		Detail     string `json:"detail"`
		Owner      *int64 `json:"owner_user_id"`
		ActorUser  *int64 `json:"actor_user_id"`
		Impersonat *int64 `json:"impersonator_user_id"`
	} `json:"audit"`
	RateEvents int `json:"rate_events"`
}

type unsubCase struct {
	Name       string            `json:"name"`
	Method     string            `json:"method"`
	Who        string            `json:"who"`
	Query      string            `json:"query"`
	Cookies    map[string]string `json:"cookies"`
	Env        map[string]string `json:"env"`
	RateEvents int               `json:"rate_events"`
	Token      string            `json:"token"`
	Expected   struct {
		Status      int            `json:"status"`
		ContentType string         `json:"content_type"`
		CacheCtl    string         `json:"cache_control"`
		CSP         string         `json:"csp"`
		SetCookies  []goldenCookie `json:"set_cookies"`
		Rows        unsubRows      `json:"rows"`
	} `json:"expected"`
}

func loadUnsub(t *testing.T) unsubFile {
	t.Helper()
	raw, err := os.ReadFile("testdata/unsub/cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var f unsubFile
	if err := json.Unmarshal(raw, &f); err != nil {
		t.Fatal(err)
	}
	return f
}

var csrfBlank = regexp.MustCompile(`(name="_csrf" value=|name="csrf-token" content=)"[^"]*"`)

func normUnsub(s string) string { return csrfBlank.ReplaceAllString(normalize(s), `$1""`) }

func unsubMux(d UnsubDeps) *http.ServeMux {
	mux := http.NewServeMux()
	mux.Handle("GET /mail/unsubscribe/{token}", UnsubscribeForm(d))
	mux.Handle("POST /mail/unsubscribe/{token}", UnsubscribeSubmit(d))
	return mux
}

// unsubTestPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL,
// applies the goose Up sections of App/migrations_pg and drops it at the end.
// It skips when the variable is unset.
func unsubTestPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_public_%d", time.Now().UnixNano())
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

// reseed is the golden script's _reset: two accounts, 1 opted in, 2 opted out.
func reseed(t *testing.T, pool *pgxpool.Pool, rateEvents int) {
	t.Helper()
	ctx := context.Background()
	for _, q := range []string{
		`DELETE FROM audit`, `DELETE FROM mail_suppression`, `DELETE FROM rate_limit_event`, `DELETE FROM user_account`,
		`INSERT INTO user_account (id, username, password_hash, created_at) VALUES (1, 'host', 'x', '2026-01-01T00:00:00+00:00')`,
		`INSERT INTO user_account (id, username, password_hash, created_at, onboarding_emails_opt_out, onboarding_emails_opt_out_at)
		 VALUES (2, 'opted', 'x', '2026-01-01T00:00:00+00:00', 1, '2026-01-01T00:00:00+00:00')`,
	} {
		if _, err := pool.Exec(ctx, q); err != nil {
			t.Fatal(err)
		}
	}
	for i := 0; i < rateEvents; i++ {
		if _, err := pool.Exec(ctx, `INSERT INTO rate_limit_event (scope, key, at) VALUES ($1, $2, $3)`,
			unsubScope, "192.0.2.1:"+unsubScope, epoch(time.Now())); err != nil {
			t.Fatal(err)
		}
	}
}

func rowsOf(t *testing.T, pool *pgxpool.Pool) unsubRows {
	t.Helper()
	ctx := context.Background()
	var r unsubRows
	r.Users = map[string]struct {
		OptOut     int  `json:"opt_out"`
		OptOutAtOn bool `json:"opt_out_at_set"`
	}{}
	rows, err := pool.Query(ctx, `SELECT id, onboarding_emails_opt_out, onboarding_emails_opt_out_at IS NOT NULL FROM user_account ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var id int64
		var flag int
		var at bool
		if err := rows.Scan(&id, &flag, &at); err != nil {
			t.Fatal(err)
		}
		r.Users[fmt.Sprint(id)] = struct {
			OptOut     int  `json:"opt_out"`
			OptOutAtOn bool `json:"opt_out_at_set"`
		}{flag, at}
	}
	rows.Close()
	sup, err := pool.Query(ctx, `SELECT email_hash, scope FROM mail_suppression ORDER BY email_hash`)
	if err != nil {
		t.Fatal(err)
	}
	for sup.Next() {
		var s struct {
			EmailHash string `json:"email_hash"`
			Scope     string `json:"scope"`
		}
		if err := sup.Scan(&s.EmailHash, &s.Scope); err != nil {
			t.Fatal(err)
		}
		r.Suppressions = append(r.Suppressions, s)
	}
	sup.Close()
	aud, err := pool.Query(ctx, `SELECT actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	for aud.Next() {
		var a struct {
			Actor      string `json:"actor"`
			Action     string `json:"action"`
			Detail     string `json:"detail"`
			Owner      *int64 `json:"owner_user_id"`
			ActorUser  *int64 `json:"actor_user_id"`
			Impersonat *int64 `json:"impersonator_user_id"`
		}
		if err := aud.Scan(&a.Actor, &a.Action, &a.Detail, &a.Owner, &a.ActorUser, &a.Impersonat); err != nil {
			t.Fatal(err)
		}
		r.Audit = append(r.Audit, a)
	}
	aud.Close()
	if r.Suppressions == nil {
		r.Suppressions = make([]struct {
			EmailHash string `json:"email_hash"`
			Scope     string `json:"scope"`
		}, 0)
	}
	if r.Audit == nil {
		r.Audit = make([]struct {
			Actor      string `json:"actor"`
			Action     string `json:"action"`
			Detail     string `json:"detail"`
			Owner      *int64 `json:"owner_user_id"`
			ActorUser  *int64 `json:"actor_user_id"`
			Impersonat *int64 `json:"impersonator_user_id"`
		}, 0)
	}
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM rate_limit_event`).Scan(&r.RateEvents); err != nil {
		t.Fatal(err)
	}
	return r
}

func unsubRequest(c unsubCase, signedIn bool, secret string, pool *pgxpool.Pool) *httptest.ResponseRecorder {
	url := "/mail/unsubscribe/" + c.Token
	if c.Query != "" {
		url += "?" + c.Query
	}
	req := httptest.NewRequest(c.Method, url, nil)
	for k, v := range c.Cookies {
		req.AddCookie(&http.Cookie{Name: k, Value: v})
	}
	rec := httptest.NewRecorder()
	rec.Header().Set("Cache-Control", "no-store, private") // main.go's wrap()
	d := UnsubDeps{Pool: pool, Getenv: func(k string) string {
		if k == "UBYHOST_SECRET_KEY" {
			return secret
		}
		return c.Env[k]
	}}
	if signedIn {
		d.SignedIn = func(*http.Request) bool { return true }
	}
	unsubMux(d).ServeHTTP(rec, req)
	return rec
}

// TestUnsubGolden compares every case with the FastAPI route: the page, the
// status, the headers and cookies and the rows left in the database.
func TestUnsubGolden(t *testing.T) {
	pool := unsubTestPool(t)
	f := loadUnsub(t)
	if len(f.Cases) < 20 {
		t.Fatalf("only %d golden cases", len(f.Cases))
	}
	for _, c := range f.Cases {
		t.Run(c.Name, func(t *testing.T) {
			reseed(t, pool, c.RateEvents)
			rec := unsubRequest(c, false, f.Secret, pool)
			e := c.Expected
			if rec.Code != e.Status {
				t.Fatalf("status %d, want %d", rec.Code, e.Status)
			}
			want, err := os.ReadFile(filepath.Join("testdata/unsub", c.Name+".html"))
			if err != nil {
				t.Fatal(err)
			}
			got := normUnsub(rec.Body.String()) + "\n"
			if got != string(want) {
				i := firstDiff(got, string(want))
				t.Errorf("html differs at byte %d:\n got: %s\nwant: %s", i, around(got, i), around(string(want), i))
			}
			h := rec.Header()
			if h.Get("Content-Type") != e.ContentType || h.Get("Cache-Control") != e.CacheCtl || h.Get("Content-Security-Policy") != "" {
				t.Errorf("headers %q %q %q, want %q %q and the wrap() CSP", h.Get("Content-Type"), h.Get("Cache-Control"),
					h.Get("Content-Security-Policy"), e.ContentType, e.CacheCtl)
			}
			var cookies []goldenCookie
			for _, line := range h.Values("Set-Cookie") {
				ck, err := http.ParseSetCookie(line)
				if err != nil {
					t.Fatal(err)
				}
				ss := map[http.SameSite]string{http.SameSiteLaxMode: "lax", http.SameSiteStrictMode: "strict"}[ck.SameSite]
				if ck.Name == "ubyhost_csrf" {
					if ck.Value == "" {
						t.Error("empty csrf nonce")
					}
					ck.Value = ""
				}
				cookies = append(cookies, goldenCookie{ck.Name, ck.Value, ck.Path, itoa(ck.MaxAge), ss, ck.Secure, ck.HttpOnly})
			}
			gotC, _ := json.Marshal(cookies)
			wantC, _ := json.Marshal(e.SetCookies)
			if string(gotC) != string(wantC) {
				t.Errorf("set-cookie %s, want %s", gotC, wantC)
			}
			gotR, _ := json.Marshal(rowsOf(t, pool))
			wantR, _ := json.Marshal(e.Rows)
			if string(gotR) != string(wantR) {
				t.Errorf("rows %s\nwant %s", gotR, wantR)
			}
		})
	}
}

// TestUnsubSignedInHost: a signed-in host with no language choice gets English
// and the "not you" logout form (auth_base.html current_user).
func TestUnsubSignedInHost(t *testing.T) {
	pool := unsubTestPool(t)
	f := loadUnsub(t)
	reseed(t, pool, 0)
	c := unsubCase{Method: "GET", Token: f.Tokens["host"], Env: map[string]string{"UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.example"}}
	body := unsubRequest(c, true, f.Secret, pool).Body.String()
	if !strings.Contains(body, `<html lang="en">`) || !strings.Contains(body, `action="/logout" class="auth-not-you"`) {
		t.Fatalf("signed-in page: %.400s", body)
	}
	if strings.Contains(unsubRequest(c, false, f.Secret, pool).Body.String(), "auth-not-you") {
		t.Fatal("logout form shown to a visitor")
	}
}

// TestUnsubLoadsNothingFromOutside: the page is not on the PostHog list, so a
// configured POSTHOG_PROJECT_API_KEY adds no script and no CSP change.
func TestUnsubLoadsNothingFromOutside(t *testing.T) {
	pool := unsubTestPool(t)
	f := loadUnsub(t)
	reseed(t, pool, 0)
	c := unsubCase{Method: "GET", Token: f.Tokens["host"], Env: map[string]string{
		"POSTHOG_PROJECT_API_KEY": "phc_golden_key", "UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.example"}}
	rec := unsubRequest(c, false, f.Secret, pool)
	body := rec.Body.String()
	if strings.Contains(strings.ToLower(body), "posthog") || strings.Contains(body, "https://") && strings.Contains(body, "<script src=\"https://") {
		t.Fatal("the unsubscribe page loads an outside script")
	}
	if rec.Header().Get("Content-Security-Policy") != "" {
		t.Fatal("the unsubscribe page changed the CSP")
	}
}

// TestUnsubTokenFromGo: a token the Go mail job writes is read back, and
// every forgery fails.
func TestUnsubTokenFromGo(t *testing.T) {
	f := loadUnsub(t)
	tok, err := lifecyclemail.UnsubscribeToken(f.Secret, 7, f.Address)
	if err != nil {
		t.Fatal(err)
	}
	id, digest, ok := readUnsubscribeToken(f.Secret, tok)
	if !ok || id != 7 || digest != lifecyclemail.EmailHash(f.Secret, f.Address) {
		t.Fatalf("Go token read as %d %q %v", id, digest, ok)
	}
	if id, digest, ok := readUnsubscribeToken(f.Secret, f.Tokens["host_no_address"]); !ok || id != 1 || digest != "" {
		t.Fatalf("token without address read as %d %q %v", id, digest, ok)
	}
	if id, _, ok := readUnsubscribeToken(f.Secret, f.Tokens["host"]); !ok || id != 1 {
		t.Fatal("Python token not read")
	}
	i := strings.LastIndexByte(f.Tokens["host"], '.')
	for name, bad := range map[string]string{
		"forged":      f.Tokens["forged"],
		"empty":       "",
		"no dot":      "abc",
		"bad sig":     f.Tokens["host"][:i+1] + "AAAA",
		"cut":         f.Tokens["host"][:i],
		"other value": f.Tokens["unknown_user"][:i] + f.Tokens["host"][i:],
	} {
		if _, _, ok := readUnsubscribeToken(f.Secret, bad); ok {
			t.Errorf("%s token accepted", name)
		}
	}
	if _, _, ok := readUnsubscribeToken(f.Secret+"x", f.Tokens["host"]); ok {
		t.Error("token accepted under another key")
	}
}

// TestCSRFTokenBinding: the token verifies against the nonce cookie, the way
// hostweb.CSRF checks it.
func TestCSRFTokenBinding(t *testing.T) {
	const secret = "public-legal-golden-secret-not-real-0123"
	now := time.Now()
	req := httptest.NewRequest("GET", "/", nil)
	token, cookie, err := csrfToken(req, secret, func(string) string { return "" }, now)
	if err != nil || cookie == nil || cookie.Value == "" {
		t.Fatalf("no nonce cookie: %v", err)
	}
	var payload map[string]any
	if err := secure.NewTimedSerializer(secret, csrfSalt).Loads(token, csrfMaxAge*time.Second, now, &payload); err != nil || payload["nonce"] == "" {
		t.Fatalf("token does not load: %v", err)
	}
	req.AddCookie(&http.Cookie{Name: csrfCookieName, Value: cookie.Value})
	if _, again, _ := csrfToken(req, secret, func(string) string { return "" }, now); again != nil {
		t.Fatal("a request with a nonce cookie got another one")
	}
}

// unsubPrints are the only things the unsubscribe template may print.
var unsubPrints = map[string]bool{
	"T": true, "E": true, "Check": true, "LangOn": true, "Lang": true, "CSRF": true,
}

func TestUnsubEveryActionEscapes(t *testing.T) {
	files, _ := fs.Glob(unsubFS, "templates/unsub/*.tmpl")
	if len(files) != 1 {
		t.Fatalf("%d unsubscribe templates", len(files))
	}
	for _, file := range files {
		src, _ := fs.ReadFile(unsubFS, file)
		trees, err := parse.Parse(file, string(src), "{{", "}}", map[string]any{})
		if err != nil {
			t.Fatal(err)
		}
		for _, tree := range trees {
			walkUnsub(t, file, tree.Root)
		}
	}
}

func walkUnsub(t *testing.T, file string, n parse.Node) {
	switch n := n.(type) {
	case *parse.ListNode:
		if n == nil {
			return
		}
		for _, c := range n.Nodes {
			walkUnsub(t, file, c)
		}
	case *parse.ActionNode:
		cmd := n.Pipe.Cmds[len(n.Pipe.Cmds)-1]
		if f, ok := cmd.Args[0].(*parse.FieldNode); !ok || !unsubPrints[f.Ident[len(f.Ident)-1]] {
			t.Errorf("%s: %s prints without escaping", file, n)
		}
	case *parse.IfNode:
		walkUnsub(t, file, n.List)
		walkUnsub(t, file, n.ElseList)
	}
}
