package auth

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"reflect"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// The cases in testdata/admin_users.json are Python's answers to the three
// admin account writes, recorded by App/scripts/admin_users_golden.py (brief
// 1504). Each is replayed on Postgres through Routes, with the seed, session,
// cookie and table helpers of routes_test.go.

type aupGolden struct {
	Secret string            `json:"secret"`
	Nonce  string            `json:"nonce"`
	Env    map[string]string `json:"env"`
	Seed   [][2]any          `json:"seed"`
	Watch  map[string]string `json:"watch"`
	Cases  []goldenCase      `json:"cases"`
}

var (
	aupWholeStamp = regexp.MustCompile(`^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$`)
	aupInnerStamp = regexp.MustCompile(`\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00`)
	aupLinkHash   = regexp.MustCompile(`:[0-9a-f]{24}$`)
	aupGenerated  = regexp.MustCompile(`-[0-9a-f]{4}$`)
)

// aupNorm is the script's norm: routes_test.go's norm, then the in-string rules.
func aupNorm(v any) *string {
	p := norm(v)
	if p == nil || *p == "<now>" || aupWholeStamp.MatchString(*p) {
		return p
	}
	s := aupInnerStamp.ReplaceAllString(*p, "<ts>")
	s = aupLinkHash.ReplaceAllString(s, ":<hash>")
	s = aupGenerated.ReplaceAllString(s, "-<hex>")
	return &s
}

func TestAdminUsersPostGoldenDatabase(t *testing.T) {
	raw, err := os.ReadFile("testdata/admin_users.json")
	if err != nil {
		t.Fatal(err)
	}
	var g aupGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) == 0 || len(g.Watch) == 0 {
		t.Fatal("empty golden")
	}
	pool := testPool(t)
	ctx := context.Background()
	sum := sha256.Sum256([]byte(g.Nonce))
	csrfToken, err := secure.NewTimedSerializer(g.Secret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	dumpWatched := func(t *testing.T) map[string][][]*string {
		t.Helper()
		out := map[string][][]*string{}
		for name, sql := range g.Watch {
			rows, err := pool.Query(ctx, sql)
			if err != nil {
				t.Fatalf("%s: %v", name, err)
			}
			out[name] = [][]*string{}
			for rows.Next() {
				vals, err := rows.Values()
				if err != nil {
					t.Fatal(err)
				}
				row := make([]*string, len(vals))
				for i, v := range vals {
					row[i] = aupNorm(v)
				}
				out[name] = append(out[name], row)
			}
			rows.Close()
		}
		return out
	}
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			now := time.Now()
			if _, err := pool.Exec(ctx, "TRUNCATE console_mail_log, email_outbox RESTART IDENTITY CASCADE"); err != nil {
				t.Fatal(err)
			}
			loadSeed(t, ctx, pool, append(append([][2]any{}, g.Seed...), c.Seed...), now)
			env := map[string]string{}
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
				// main.go's metrics.wrap sets hardenHeaders first; this is its Cache-Control.
				mux.Handle(r.Pattern, http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
					w.Header().Set("Cache-Control", "no-store, private")
					h(w, req)
				}))
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
			req.RemoteAddr = "testclient:50000"
			if c.Method == http.MethodPost {
				req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
			}
			var cookies []string
			if c.Session != nil {
				cookies = append(cookies, "ubyhost_session="+sessionToken(t, g.Secret, c.Session, now))
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
			}{{"Location", w.Location}, {"Content-Type", w.ContentType}, {"Cache-Control", w.CacheControl}, {"Content-Disposition", w.ContentDisposition}} {
				if got := header(res.Header, h.name); str(got) != str(h.want) {
					t.Errorf("%s %q, want %q", h.name, str(got), str(h.want))
				}
			}
			if w.Body != nil && rec.Body.String() != *w.Body {
				t.Errorf("body %q, want %q", rec.Body.String(), *w.Body)
			}
			var got []cookieRec
			for _, line := range res.Header["Set-Cookie"] {
				got = append(got, parseCookie(t, g.Secret, line, now))
			}
			if len(got) != len(w.Cookies) {
				t.Fatalf("cookies %+v, want %+v", got, w.Cookies)
			}
			for i := range got {
				wc := w.Cookies[i]
				if got[i].Name != wc.Name || got[i].Empty != wc.Empty || !reflect.DeepEqual(got[i].Attrs, wc.Attrs) ||
					(wc.Payload != nil && !samePayload(got[i].Payload, wc.Payload)) {
					t.Errorf("cookie %d: %+v, want %+v", i, got[i], wc)
				}
			}
			if db := dumpWatched(t); !reflect.DeepEqual(db, w.DB) {
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
}

// TestAdminUsersPostRoutes: the three writes are in Routes, next to the GET
// that 1282 serves, so the whole /admin/users path can move to Go.
func TestAdminUsersPostRoutes(t *testing.T) {
	want := map[string]bool{"GET /admin/users": false, "POST /admin/users": false,
		"POST /admin/users/{id}/invite": false, "POST /admin/users/{id}/email": false}
	for _, r := range Routes(nil, func(string) string { return "" }, time.Now) {
		if _, ok := want[r.Pattern]; ok {
			want[r.Pattern] = true
		}
	}
	for p, ok := range want {
		if !ok {
			t.Errorf("route %q missing", p)
		}
	}
}
