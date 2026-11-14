package auth

// The cases in testdata/login.json are Python's answers to the login pages,
// recorded by App/scripts/auth_login_golden.py (brief 1502). Each case is
// replayed on Postgres through Routes, with the real Turnstile verifier
// pointed at a fake siteverify server that answers as the script's fake does.

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/turnstile"
)

type loginCookie struct {
	Name    string            `json:"name"`
	Attrs   map[string]string `json:"attrs"`
	Empty   bool              `json:"empty"`
	Payload map[string]any    `json:"payload,omitempty"`
	Value   *string           `json:"value,omitempty"`
}

type loginWant struct {
	Status         int                    `json:"status"`
	Location       *string                `json:"location"`
	ContentType    *string                `json:"content_type"`
	CacheControl   *string                `json:"cache_control"`
	ReferrerPolicy *string                `json:"referrer_policy"`
	Body           *string                `json:"body"`
	Cookies        []loginCookie          `json:"cookies"`
	Pending        map[string]any         `json:"pending"`
	AdminFile      bool                   `json:"admin_file"`
	DB             map[string][][]*string `json:"db"`
}

type loginCase struct {
	Name      string            `json:"name"`
	Method    string            `json:"method"`
	Path      string            `json:"path"`
	Query     string            `json:"query"`
	Session   map[string]int64  `json:"session"`
	Device    map[string]int64  `json:"device"`
	CSRF      *bool             `json:"csrf"`
	Lang      string            `json:"lang"`
	Client    string            `json:"client"`
	Headers   map[string]string `json:"headers"`
	Form      [][2]string       `json:"form"`
	Seed      [][2]any          `json:"seed"`
	Env       map[string]string `json:"env"`
	AdminFile bool              `json:"admin_file"`
	Want      loginWant         `json:"want"`
}

type loginGolden struct {
	Secret string            `json:"secret"`
	Nonce  string            `json:"nonce"`
	Env    map[string]string `json:"env"`
	Seed   [][2]any          `json:"seed"`
	Cases  []loginCase       `json:"cases"`
}

// loginTables are emptied before each case, as the script deletes them.
var loginTables = []string{"alert", "console_mail_log", "email_outbox", "rate_limit_event", "audit", "login_token", "user_account"}

// loginWatch is the script's WATCH: the same columns in the same order.
var loginWatch = map[string]string{
	"audit":            `SELECT action, actor, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit ORDER BY id`,
	"rate_limit_event": `SELECT scope, key FROM rate_limit_event ORDER BY id`,
	"login_token":      `SELECT user_account_id, purpose, email, remember, next_path, used_at FROM login_token ORDER BY id`,
	"user_account":     `SELECT id, last_login_at, email_verified_at FROM user_account ORDER BY id`,
	"email_outbox": `SELECT idempotency_key, kind, owner_user_id, to_email, subject, state, substring(payload from '"lang": *"([a-z]*)"')
		FROM email_outbox ORDER BY id`,
	"alert": `SELECT level, kind, dedupe_key, resolved_at FROM alert ORDER BY id`,
}

var linkKey = regexp.MustCompile(`^(login_link:\d+:)[0-9a-f]{24}$`)

func loginNorm(v any) *string {
	p := norm(v)
	if p != nil {
		s := linkKey.ReplaceAllString(*p, "${1}<key>")
		p = &s
	}
	return p
}

func loginDump(t *testing.T, ctx context.Context, pool *pgxpool.Pool) map[string][][]*string {
	t.Helper()
	out := map[string][][]*string{}
	for name, sql := range loginWatch {
		rows, err := pool.Query(ctx, sql)
		if err != nil {
			t.Fatal(err)
		}
		out[name] = [][]*string{}
		for rows.Next() {
			vals, err := rows.Values()
			if err != nil {
				t.Fatal(err)
			}
			row := make([]*string, len(vals))
			for i, v := range vals {
				row[i] = loginNorm(v)
			}
			out[name] = append(out[name], row)
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			t.Fatalf("%s: %v", name, err)
		}
	}
	return out
}

func loginSeed(t *testing.T, ctx context.Context, pool *pgxpool.Pool, seed [][2]any, now time.Time) {
	t.Helper()
	if _, err := pool.Exec(ctx, "TRUNCATE "+strings.Join(loginTables, ", ")+" RESTART IDENTITY CASCADE"); err != nil {
		t.Fatal(err)
	}
	for _, item := range seed {
		table := item[0].(string)
		row := item[1].(map[string]any)
		cols := make([]string, 0, len(row))
		for c := range row {
			cols = append(cols, c)
		}
		sort.Strings(cols)
		marks := make([]string, len(cols))
		vals := make([]any, len(cols))
		for i, c := range cols {
			marks[i] = "$" + strconv.Itoa(i+1)
			vals[i] = seedValue(row[c], now)
		}
		if _, err := pool.Exec(ctx, "INSERT INTO "+table+" ("+strings.Join(cols, ", ")+") VALUES ("+strings.Join(marks, ", ")+")", vals...); err != nil {
			t.Fatalf("seed %s: %v", table, err)
		}
	}
	for _, table := range loginTables {
		if _, err := pool.Exec(ctx, fmt.Sprintf(`SELECT setval(pg_get_serial_sequence('%s', 'id'), COALESCE((SELECT MAX(id) FROM %s), 0) + 1, false)
			WHERE pg_get_serial_sequence('%s', 'id') IS NOT NULL`, table, table, table)); err != nil {
			t.Fatal(err)
		}
	}
}

// pageTokens are the values the script replaces before it compares a page.
var pageTokens = []struct {
	re   *regexp.Regexp
	with string
}{
	{regexp.MustCompile(`(name="_csrf" value=")[^"]*"`), `${1}<csrf>"`},
	{regexp.MustCompile(`(name="csrf-token" content=")[^"]*"`), `${1}<csrf>"`},
	{regexp.MustCompile(`name="pending" value="[^"]*"`), `name="pending" value="<pending>"`},
	{regexp.MustCompile(`(/login/link\?t=)[A-Za-z0-9_-]+`), `${1}<token>`},
	{regexp.MustCompile(`[ \t\n\r\f\v]+`), " "},
}

var pendingRE = regexp.MustCompile(`name="pending" value="([^"]*)"`)
var csrfRE = regexp.MustCompile(`name="csrf-token" content="([^"]*)"`)

// normalizePage is the script's normalize. html/template writes "+" as
// "&#43;" where markupsafe keeps it; a browser reads both the same.
func normalizePage(html string) string {
	html = strings.ReplaceAll(html, "&#43;", "+")
	for _, p := range pageTokens {
		html = p.re.ReplaceAllString(html, p.with)
	}
	return strings.TrimSpace(strings.ReplaceAll(html, "> <", "><"))
}

// siteverify answers as the script's fake_post does, by token.
func siteverify(t *testing.T) *httptest.Server {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := r.ParseForm(); err != nil {
			t.Error(err)
		}
		if r.PostForm.Get("secret") != "golden-turnstile-secret" {
			t.Errorf("siteverify secret %q", r.PostForm.Get("secret"))
		}
		switch r.PostForm.Get("response") {
		case "good":
			_, _ = w.Write([]byte(`{"success": true, "action": "host_login", "hostname": "ubyhost.test"}`))
		case "other-action":
			_, _ = w.Write([]byte(`{"success": true, "action": "guest_claim", "hostname": "ubyhost.test"}`))
		case "down":
			w.WriteHeader(http.StatusServiceUnavailable)
			_, _ = w.Write([]byte("unavailable"))
		default:
			_, _ = w.Write([]byte(`{"success": false}`))
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

func loginParseCookie(t *testing.T, secret, line string, now time.Time) loginCookie {
	t.Helper()
	base := parseCookie(t, secret, line, now)
	c := loginCookie{Name: base.Name, Attrs: base.Attrs, Empty: base.Empty, Payload: base.Payload}
	value := strings.TrimSpace(strings.SplitN(strings.SplitN(line, ";", 2)[0], "=", 2)[1])
	switch c.Name {
	case session.DeviceCookieName:
		var payload map[string]any
		if err := secure.NewTimedSerializer(secret, "ubyhost-device").Loads(value, 31*24*time.Hour, time.Now().Add(time.Second), &payload); err != nil {
			t.Fatalf("device cookie does not verify: %v", err)
		}
		if did, ok := payload["did"].(string); ok {
			payload["did"] = float64(len(did))
		}
		c.Payload = payload
	case "ubyhost_lang":
		c.Value = &value
	}
	return c
}

func TestLoginGoldenDatabase(t *testing.T) {
	raw, err := os.ReadFile("testdata/login.json")
	if err != nil {
		t.Fatal(err)
	}
	var g loginGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	pool := testPool(t)
	ctx := context.Background()
	sum := sha256.Sum256([]byte(g.Nonce))
	csrfToken, err := secure.NewTimedSerializer(g.Secret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	srv := siteverify(t)
	oldVerifier, oldSend := loginVerifier, sendLinkNow
	t.Cleanup(func() { loginVerifier, sendLinkNow = oldVerifier, oldSend })
	loginVerifier = func(d deps) turnstile.Verifier {
		return turnstile.Verifier{Pool: d.pool, Getenv: d.getenv, Now: d.now, URL: srv.URL, Client: srv.Client()}
	}
	sendLinkNow = func(d deps, id int64) {
		if err := mail.SendNow(context.Background(), d.pool, d.getenv, id); err != nil {
			t.Errorf("send_now: %v", err)
		}
	}
	seen := map[string]bool{}
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			now := time.Now()
			loginSeed(t, ctx, pool, append(append([][2]any{}, g.Seed...), c.Seed...), now)
			dir := t.TempDir()
			adminFile := filepath.Join(dir, "initial_admin_login")
			if c.AdminFile {
				if err := os.WriteFile(adminFile, []byte("golden\n"), 0o600); err != nil {
					t.Fatal(err)
				}
			}
			env := map[string]string{"UBYHOST_DATA_DIR": dir}
			for k, v := range g.Env {
				env[k] = v
			}
			for k, v := range c.Env {
				env[k] = v
			}
			getenv := func(k string) string { return env[k] }
			mux := http.NewServeMux()
			for _, r := range Routes(pool, getenv, time.Now) {
				h := r.Handler
				// main.go's metrics.wrap sets hardenHeaders first.
				mux.Handle(r.Pattern, http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
					w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
					w.Header().Set("Cache-Control", "no-store, private")
					h(w, req)
				}))
				if strings.HasSuffix(r.Pattern, " /login") || strings.HasSuffix(r.Pattern, " /login/link") {
					seen[r.Pattern] = true
				}
			}
			csrf := c.CSRF == nil || *c.CSRF
			var pairs []string
			for _, p := range c.Form {
				pairs = append(pairs, url.QueryEscape(p[0])+"="+url.QueryEscape(p[1]))
			}
			if csrf && c.Method == http.MethodPost {
				pairs = append(pairs, "_csrf="+url.QueryEscape(csrfToken))
			}
			target := "http://testserver" + c.Path
			if c.Query != "" {
				target += "?" + c.Query
			}
			req := httptest.NewRequest(c.Method, target, strings.NewReader(strings.Join(pairs, "&")))
			client := c.Client
			if client == "" {
				client = "testclient"
			}
			req.RemoteAddr = client + ":50000"
			if c.Method == http.MethodPost {
				req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
			}
			var cookies []string
			if c.Session != nil {
				cookies = append(cookies, "ubyhost_session="+sessionToken(t, g.Secret, c.Session, now))
			}
			if c.Device != nil {
				sv := int64(1)
				if v, ok := c.Device["sv"]; ok {
					sv = v
				}
				token, err := session.DeviceToken(g.Secret, c.Device["uid"], sv, "golden-device", now)
				if err != nil {
					t.Fatal(err)
				}
				cookies = append(cookies, session.DeviceCookieName+"="+token)
			}
			if csrf {
				cookies = append(cookies, "ubyhost_csrf="+g.Nonce)
			}
			if c.Lang != "" {
				cookies = append(cookies, "ubyhost_lang="+c.Lang)
			}
			if len(cookies) > 0 {
				req.Header.Set("Cookie", strings.Join(cookies, "; "))
			}
			for k, v := range c.Headers {
				if strings.EqualFold(k, "host") {
					req.Host = v
					continue
				}
				req.Header.Set(k, v)
			}
			rec := httptest.NewRecorder()
			mux.ServeHTTP(rec, req)
			res := rec.Result()
			w := c.Want
			if res.StatusCode != w.Status {
				t.Fatalf("status %d, want %d (body %q)", res.StatusCode, w.Status, rec.Body.String())
			}
			for _, h := range []struct {
				name string
				want *string
			}{{"Location", w.Location}, {"Content-Type", w.ContentType}, {"Cache-Control", w.CacheControl}, {"Referrer-Policy", w.ReferrerPolicy}} {
				if got := header(res.Header, h.name); str(got) != str(h.want) {
					t.Errorf("%s %q, want %q", h.name, str(got), str(h.want))
				}
			}
			body := rec.Body.String()
			if w.Body != nil {
				if got := normalizePage(body); got != *w.Body {
					t.Errorf("body differs at %s", firstDiff(got, *w.Body))
				}
			} else if w.Status < 300 || w.Status >= 400 {
				if body != "" {
					t.Errorf("body %q, want none", body)
				}
			}
			if m := csrfRE.FindStringSubmatch(body); m != nil {
				var payload map[string]any
				if err := secure.NewTimedSerializer(g.Secret, "ubyhost-csrf").Loads(m[1], time.Hour, time.Now(), &payload); err != nil {
					t.Errorf("page csrf token does not verify: %v", err)
				}
			}
			var pending map[string]any
			if m := pendingRE.FindStringSubmatch(body); m != nil {
				p, ok := session.ReadTwoFactorPending(g.Secret, m[1], time.Now())
				if !ok {
					t.Fatal("pending token does not verify")
				}
				raw, _ := json.Marshal(p)
				_ = json.Unmarshal(raw, &pending)
			}
			if !reflect.DeepEqual(pending, w.Pending) {
				t.Errorf("pending %v, want %v", pending, w.Pending)
			}
			_, statErr := os.Stat(adminFile)
			if exists := statErr == nil; exists != w.AdminFile {
				t.Errorf("initial_admin_login exists %v, want %v", exists, w.AdminFile)
			}
			var got []loginCookie
			for _, line := range res.Header["Set-Cookie"] {
				got = append(got, loginParseCookie(t, g.Secret, line, now))
			}
			if len(got) != len(w.Cookies) {
				t.Fatalf("cookies %+v, want %+v", got, w.Cookies)
			}
			for i := range got {
				wc := w.Cookies[i]
				if got[i].Name != wc.Name || got[i].Empty != wc.Empty || !reflect.DeepEqual(got[i].Attrs, wc.Attrs) ||
					str(got[i].Value) != str(wc.Value) ||
					(wc.Payload != nil && !samePayload(got[i].Payload, wc.Payload)) {
					t.Errorf("cookie %d: %+v, want %+v", i, got[i], wc)
				}
			}
			if db := loginDump(t, ctx, pool); !reflect.DeepEqual(db, w.DB) {
				for name := range w.DB {
					if !reflect.DeepEqual(db[name], w.DB[name]) {
						gj, _ := json.Marshal(db[name])
						wj, _ := json.Marshal(w.DB[name])
						t.Errorf("table %s:\n got  %s\n want %s", name, gj, wj)
					}
				}
			}
		})
	}
	if len(seen) != 4 {
		t.Errorf("login routes registered: %v", seen)
	}
}

// firstDiff shows where two normalised pages part, with some context.
func firstDiff(got, want string) string {
	i := 0
	for i < len(got) && i < len(want) && got[i] == want[i] {
		i++
	}
	lo := i - 80
	if lo < 0 {
		lo = 0
	}
	end := func(s string) string {
		hi := i + 80
		if hi > len(s) {
			hi = len(s)
		}
		return s[lo:hi]
	}
	return fmt.Sprintf("byte %d:\n got  %q\n want %q", i, end(got), end(want))
}
