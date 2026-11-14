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
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// The cases in testdata/login_2fa.json are Python's answers to POST
// /login/2fa, recorded by App/scripts/login_2fa_golden.py (brief 1503). Each
// is replayed on Postgres through Routes, with the seed, session, cookie and
// table helpers of routes_test.go. A case's pending token is minted here,
// because it lives 10 minutes. A page answer is compared on the auth-alert
// text and the echoed token; its markup is brief 1502's.

type l2faPending struct {
	UID  int64   `json:"uid"`
	RM   bool    `json:"rm"`
	Next *string `json:"next"`
	Pad  bool    `json:"pad"`
}

type l2faPage struct {
	Alert         *string `json:"alert"`
	PendingFields int     `json:"pending_fields"`
}

type l2faCase struct {
	goldenCase
	Pending    *l2faPending `json:"pending"`
	PendingRaw *string      `json:"pending_raw"`
	Page       *l2faPage    `json:"page"`
}

type l2faGolden struct {
	Secret string            `json:"secret"`
	Nonce  string            `json:"nonce"`
	Env    map[string]string `json:"env"`
	Seed   [][2]any          `json:"seed"`
	Watch  map[string]string `json:"watch"`
	Cases  []l2faCase        `json:"cases"`
}

var l2faAlert = regexp.MustCompile(`(?s)<div class="auth-alert" role="alert">(.*?)</div>`)

func TestLogin2FAGoldenDatabase(t *testing.T) {
	raw, err := os.ReadFile("testdata/login_2fa.json")
	if err != nil {
		t.Fatal(err)
	}
	var g l2faGolden
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
					row[i] = norm(v)
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
			token, sent := "", ""
			var pairs []string
			switch {
			case c.Pending != nil:
				next := "/"
				if c.Pending.Next != nil {
					next = *c.Pending.Next
				}
				if token, err = session.IssueTwoFactorPending(g.Secret, c.Pending.UID, c.Pending.RM, next, now); err != nil {
					t.Fatal(err)
				}
				sent = token
				if c.Pending.Pad {
					sent = " " + token + " "
				}
				pairs = append(pairs, "pending="+url.QueryEscape(sent))
			case c.PendingRaw != nil:
				token, sent = *c.PendingRaw, *c.PendingRaw
				pairs = append(pairs, "pending="+url.QueryEscape(sent))
			}
			csrf := c.CSRF == nil || *c.CSRF
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
			req.RemoteAddr = "testclient:50000" // Starlette's TestClient peer, so the rate-limit keys match
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
			if c.Page != nil {
				body := rec.Body.String()
				var alert *string
				if m := l2faAlert.FindStringSubmatch(body); m != nil {
					alert = &m[1]
				}
				if str(alert) != str(c.Page.Alert) {
					t.Errorf("alert %q, want %q", str(alert), str(c.Page.Alert))
				}
				field := `<input type="hidden" name="pending" value="` + strings.TrimSpace(token) + `">`
				if n := strings.Count(body, field); n != c.Page.PendingFields {
					t.Errorf("%d pending fields, want %d", n, c.Page.PendingFields)
				}
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

// TestLogin2FARoutes: POST /login/2fa sits next to the GET of brief 1282, so
// the whole /login/2fa path can move to Go.
func TestLogin2FARoutes(t *testing.T) {
	want := map[string]bool{"GET /login/2fa": false, "POST /login/2fa": false}
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

// TestPendingHelpers: uid and next as Python reads them from the payload.
func TestPendingHelpers(t *testing.T) {
	for _, c := range []struct {
		in   map[string]any
		uid  int64
		ok   bool
		next string
	}{
		{map[string]any{"uid": int64(3), "next": "/x"}, 3, true, "/x"},
		{map[string]any{"uid": float64(4), "next": ""}, 4, true, "/"},
		{map[string]any{"uid": "3"}, 0, false, "/"},
		{map[string]any{"uid": 2.5, "next": nil}, 0, false, "/"},
	} {
		uid, ok := pendingUserID(c.in)
		if uid != c.uid || ok != c.ok || pendingNext(c.in) != c.next {
			t.Errorf("%v: %d %v %q", c.in, uid, ok, pendingNext(c.in))
		}
	}
}
