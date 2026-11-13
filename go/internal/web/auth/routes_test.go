package auth

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

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// The cases in testdata/routes.json are Python's answers, recorded by
// App/scripts/auth_routes_golden.py. Each case is replayed on Postgres.

type cookieRec struct {
	Name    string            `json:"name"`
	Attrs   map[string]string `json:"attrs"`
	Empty   bool              `json:"empty"`
	Payload map[string]any    `json:"payload,omitempty"`
}

type want struct {
	Status             int                    `json:"status"`
	Location           *string                `json:"location"`
	ContentType        *string                `json:"content_type"`
	CacheControl       *string                `json:"cache_control"`
	ContentDisposition *string                `json:"content_disposition"`
	Body               *string                `json:"body"`
	Cookies            []cookieRec            `json:"cookies"`
	DB                 map[string][][]*string `json:"db"`
}

type goldenCase struct {
	Name    string            `json:"name"`
	Method  string            `json:"method"`
	Path    string            `json:"path"`
	Query   string            `json:"query"`
	Session map[string]int64  `json:"session"`
	CSRF    *bool             `json:"csrf"`
	Lang    string            `json:"lang"`
	Headers map[string]string `json:"headers"`
	Form    [][2]string       `json:"form"`
	Seed    [][2]any          `json:"seed"`
	Env     map[string]string `json:"env"`
	Want    want              `json:"want"`
}

type golden struct {
	Secret string            `json:"secret"`
	Nonce  string            `json:"nonce"`
	Env    map[string]string `json:"env"`
	Seed   [][2]any          `json:"seed"`
	Cases  []goldenCase      `json:"cases"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/routes.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

// tables are truncated before each case, as the script deletes them.
var tables = []string{"ad_click", "consent_texts", "security_incident", "mail_suppression", "legal_entity",
	"legal_acceptance", "rate_limit_event", "audit", "login_token", "user_account"}

// watch is the script's WATCH: the same columns in the same order.
var watch = map[string]string{
	"audit": `SELECT action, actor, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit ORDER BY id`,
	"user_account": `SELECT id, session_version, totp_enabled,
		CASE WHEN totp_secret_enc IS NULL THEN 0 ELSE 1 END AS has_secret,
		CASE WHEN recovery_codes_hash IS NULL THEN 0 ELSE 1 END AS has_codes,
		onboarding_emails_opt_out, onboarding_emails_opt_out_at, stay_fee_emails_opt_out,
		stay_fee_emails_opt_out_at, guest_details_mail, two_factor_prompted_at FROM user_account ORDER BY id`,
	"mail_suppression": `SELECT email_hash, scope FROM mail_suppression ORDER BY email_hash, scope`,
	"security_incident": `SELECT id, detected_at, reported_by, summary, data_categories, affected_owner_ids, approx_subjects,
		risk_level, contained_at, controllers_notified_at, authority_notified_at, subjects_notified_at,
		closed_at, notes, created_at, updated_at FROM security_incident ORDER BY id`,
	"rate_limit_event": `SELECT scope, key FROM rate_limit_event ORDER BY id`,
	"ad_click": `SELECT id, gclid, gbraid, wbraid, fbc, event_id, withdrawn_at, uploaded_at, ids_deleted_at,
		send_state FROM ad_click ORDER BY id`,
}

var stamp = regexp.MustCompile(`^\d{4}-\d\d-\d\dT`)

func norm(v any) *string {
	if v == nil {
		return nil
	}
	s := fmt.Sprint(v)
	if stamp.MatchString(s) && !strings.HasPrefix(s, "2001-") && !strings.HasPrefix(s, "2099-") {
		s = "<now>"
	}
	return &s
}

func dump(t *testing.T, ctx context.Context, pool *pgxpool.Pool) map[string][][]*string {
	t.Helper()
	out := map[string][][]*string{}
	for name, sql := range watch {
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

func seedValue(v any, now time.Time) any {
	switch x := v.(type) {
	case float64:
		if x == float64(int64(x)) {
			return int64(x)
		}
		return x
	case string:
		if x == "<now-epoch>" {
			return float64(now.UnixNano()) / 1e9
		}
	}
	return v
}

func loadSeed(t *testing.T, ctx context.Context, pool *pgxpool.Pool, seed [][2]any, now time.Time) {
	t.Helper()
	if _, err := pool.Exec(ctx, "TRUNCATE "+strings.Join(tables, ", ")+" RESTART IDENTITY CASCADE"); err != nil {
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
	for _, table := range tables {
		if table == "mail_suppression" {
			continue
		}
		if _, err := pool.Exec(ctx, fmt.Sprintf(`SELECT setval(pg_get_serial_sequence('%s', 'id'), COALESCE((SELECT MAX(id) FROM %s), 0) + 1, false)`, table, table)); err != nil {
			t.Fatal(err)
		}
	}
}

// sessionToken is the script's session_cookie: auth.issue_session with
// times relative to now, through 1280's IssueSession.
func sessionToken(t *testing.T, secret string, spec map[string]int64, now time.Time) string {
	t.Helper()
	sv := int64(1)
	if v, ok := spec["sv"]; ok {
		sv = v
	}
	iat := now.Unix() - 60
	if v, ok := spec["iat"]; ok {
		iat = now.Unix() + v
	}
	opt := session.IssueOptions{Workspace: spec["as"], Remember: spec["rm"] != 0, IssuedAt: &iat}
	if v, ok := spec["ast"]; ok {
		ast := now.Unix() + v
		opt.ImpersonationStartedAt = &ast
	}
	token, err := session.IssueSession(secret, spec["uid"], sv, opt, now)
	if err != nil {
		t.Fatal(err)
	}
	return token
}

func parseCookie(t *testing.T, secret, line string, now time.Time) cookieRec {
	t.Helper()
	parts := strings.Split(line, ";")
	name, value, _ := strings.Cut(strings.TrimSpace(parts[0]), "=")
	rec := cookieRec{Name: name, Attrs: map[string]string{}, Empty: value == "" || value == `""`}
	for _, p := range parts[1:] {
		k, v, _ := strings.Cut(strings.TrimSpace(p), "=")
		k = strings.ToLower(k)
		switch k {
		case "expires":
			rec.Attrs[k] = "set"
		case "httponly", "secure":
			rec.Attrs[k] = "true"
		case "samesite":
			rec.Attrs[k] = strings.ToLower(v)
		default:
			rec.Attrs[k] = v
		}
	}
	if name == "ubyhost_session" && !rec.Empty {
		var payload map[string]any
		if err := secure.NewTimedSerializer(secret, "ubyhost-session").Loads(value, 400*24*time.Hour, time.Now().Add(time.Second), &payload); err != nil {
			t.Fatalf("session cookie does not verify: %v", err)
		}
		for _, k := range []string{"iat", "rf", "ast"} {
			if v, ok := payload[k].(float64); ok {
				payload[k] = float64(int64(v) - now.Unix())
			}
		}
		rec.Payload = payload
	}
	return rec
}

// sameOffsets compares session payloads, the time offsets within 2 seconds.
func samePayload(got, want map[string]any) bool {
	if len(got) != len(want) {
		return false
	}
	for k, w := range want {
		g, ok := got[k]
		if !ok {
			return false
		}
		if k == "iat" || k == "rf" || k == "ast" {
			d := g.(float64) - w.(float64)
			if d < -2 || d > 2 {
				return false
			}
			continue
		}
		if !reflect.DeepEqual(g, w) {
			return false
		}
	}
	return true
}

func str(p *string) string {
	if p == nil {
		return "<nil>"
	}
	return *p
}

func header(h http.Header, k string) *string {
	if v, ok := h[http.CanonicalHeaderKey(k)]; ok && len(v) > 0 {
		return &v[0]
	}
	return nil
}

// knownGaps are differences that live in read-only packages, not here.
var knownGaps = map[string]string{
	// hostweb.endExpired signs {uid, sv, iat} with SameSite=Strict; Python's
	// end_expired_impersonation goes through issue_session (adds rf) and
	// attach_session (SameSite=Lax). Reported for the hostweb owner.
	"stop_expired": "rf",
}

func TestRoutesGoldenDatabase(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	ctx := context.Background()
	sum := sha256.Sum256([]byte(g.Nonce))
	csrfToken, err := secure.NewTimedSerializer(g.Secret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, time.Now())
	if err != nil {
		t.Fatal(err)
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
				if gap := knownGaps[c.Name]; gap != "" {
					if got[i].Payload != nil {
						delete(got[i].Payload, gap)
					}
					if wc.Payload != nil {
						delete(wc.Payload, gap)
						wc.Attrs = got[i].Attrs
					}
				}
				if got[i].Name != wc.Name || got[i].Empty != wc.Empty || !reflect.DeepEqual(got[i].Attrs, wc.Attrs) ||
					(wc.Payload != nil && !samePayload(got[i].Payload, wc.Payload)) {
					t.Errorf("cookie %d: %+v, want %+v", i, got[i], wc)
				}
			}
			if db := dump(t, ctx, pool); !reflect.DeepEqual(db, w.DB) {
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

func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_webauth_%d", time.Now().UnixNano())
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
			return
		}
		defer c.Close(context.Background())
		_, _ = c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)")
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
