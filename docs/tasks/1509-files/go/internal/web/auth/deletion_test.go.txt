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
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// The cases in testdata/schedule_deletion.json are Python's answers, recorded
// by App/scripts/auth_deletion_golden.py (brief 1509) with admin_accounts'
// clock fixed at "fixed". Each case is replayed on Postgres at that instant,
// through the helpers of routes_test.go (loadSeed, sessionToken, parseCookie,
// header, str, norm, testPool).

type deletionGolden struct {
	golden
	Fixed string `json:"fixed"`
}

// deletionWatch is the script's WATCH: the same columns in the same order.
var deletionWatch = map[string]string{
	"audit":        `SELECT action, actor, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit ORDER BY id`,
	"user_account": `SELECT id, deletion_due_at FROM user_account ORDER BY id`,
	"email_outbox": `SELECT kind, idempotency_key, owner_user_id, to_email, cc_email, subject, payload, state, attempts
		FROM email_outbox ORDER BY id`,
}

func deletionDump(t *testing.T, ctx context.Context, pool *pgxpool.Pool) map[string][][]*string {
	t.Helper()
	out := map[string][][]*string{}
	for name, sql := range deletionWatch {
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
				row[i] = norm(v)
			}
			out[name] = append(out[name], row)
		}
		rows.Close()
	}
	return out
}

func TestDeletionDue(t *testing.T) {
	at := time.Date(2099, 3, 4, 5, 6, 7, 999999999, time.FixedZone("CET", 3600))
	if got, want := deletionDue(at), "2099-04-03T04:06:07+00:00"; got != want {
		t.Fatalf("deletionDue %q, want %q", got, want)
	}
}

func TestScheduleDeletionRouteListed(t *testing.T) {
	n := 0
	for _, r := range Routes(nil, func(string) string { return "" }, time.Now) {
		if r.Pattern == "POST /admin/users/{id}/schedule-deletion" {
			n++
			if r.Path != "/admin/users/{id}/schedule-deletion" {
				t.Errorf("label %q", r.Path)
			}
		}
	}
	if n != 1 {
		t.Fatalf("route listed %d times, want 1", n)
	}
	// ServeMux panics on a conflicting pattern; register every route once.
	mux := http.NewServeMux()
	for _, r := range Routes(nil, func(string) string { return "" }, time.Now) {
		mux.Handle(r.Pattern, r.Handler)
	}
}

func TestScheduleDeletionGoldenDatabase(t *testing.T) {
	raw, err := os.ReadFile("testdata/schedule_deletion.json")
	if err != nil {
		t.Fatal(err)
	}
	var g deletionGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) == 0 {
		t.Fatal("no cases")
	}
	fixed, err := time.Parse(time.RFC3339Nano, g.Fixed)
	if err != nil {
		t.Fatal(err)
	}
	clock := func() time.Time { return fixed }
	pool := testPool(t)
	ctx := context.Background()
	sum := sha256.Sum256([]byte(g.Nonce))
	csrfToken, err := secure.NewTimedSerializer(g.Secret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, fixed)
	if err != nil {
		t.Fatal(err)
	}
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			loadSeed(t, ctx, pool, append(append([][2]any{}, g.Seed...), c.Seed...), fixed)
			if _, err := pool.Exec(ctx, "TRUNCATE email_outbox RESTART IDENTITY"); err != nil {
				t.Fatal(err)
			}
			env := map[string]string{}
			for k, v := range g.Env {
				env[k] = v
			}
			for k, v := range c.Env {
				env[k] = v
			}
			getenv := func(k string) string { return env[k] }
			mux := http.NewServeMux()
			for _, r := range Routes(pool, getenv, clock) {
				h := r.Handler
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
			req := httptest.NewRequest(c.Method, "http://testserver"+c.Path, strings.NewReader(strings.Join(pairs, "&")))
			req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
			var cookies []string
			if c.Session != nil {
				cookies = append(cookies, "ubyhost_session="+sessionToken(t, g.Secret, c.Session, fixed))
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
				got = append(got, parseCookie(t, g.Secret, line, fixed))
			}
			if len(got) != len(w.Cookies) {
				t.Fatalf("cookies %+v, want %+v", got, w.Cookies)
			}
			for i := range got {
				if got[i].Name != w.Cookies[i].Name || got[i].Empty != w.Cookies[i].Empty || !reflect.DeepEqual(got[i].Attrs, w.Cookies[i].Attrs) {
					t.Errorf("cookie %d: %+v, want %+v", i, got[i], w.Cookies[i])
				}
			}
			db := deletionDump(t, ctx, pool)
			for name := range deletionWatch {
				if !reflect.DeepEqual(db[name], w.DB[name]) {
					gj, _ := json.Marshal(db[name])
					wj, _ := json.Marshal(w.DB[name])
					t.Errorf("table %s:\n got  %s\n want %s", name, gj, wj)
				}
			}
		})
	}
}
