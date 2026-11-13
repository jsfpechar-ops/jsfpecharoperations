package privacy

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const (
	testSecret     = "privacy-test-secret-key-0123456789abcdef"
	testCSRFCookie = "privacy-test-csrf-cookie"
)

func testEnv(k string) string {
	return map[string]string{
		"UBYHOST_SECRET_KEY":      testSecret,
		"UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.example",
		"UBYHOST_TERMS_VERSION":   "t1",
		"UBYHOST_PRIVACY_VERSION": "p1",
		"UBYHOST_DPA_VERSION":     "d1",
	}[k]
}

// csrfToken mints a token bound to the CSRF cookie value, as csrf_token does.
func csrfToken(t *testing.T, cookie string, at time.Time) string {
	t.Helper()
	sum := sha256.Sum256([]byte(cookie))
	tok, err := secure.NewTimedSerializer(testSecret, "ubyhost-csrf").
		Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, at)
	if err != nil {
		t.Fatal(err)
	}
	return tok
}

func TestFormStr(t *testing.T) {
	req := httptest.NewRequest(http.MethodPost, "/privacy-requests",
		strings.NewReader("channel=fax&channel=+email%1F+&outcome_note=&empty"))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	if err := parseForm(req); err != nil {
		t.Fatal(err)
	}
	if got := formStr(req, "channel"); got != "email" {
		t.Errorf("channel = %q, want the last value stripped", got)
	}
	if got := formStr(req, "missing"); got != "" || formHas(req, "missing") {
		t.Errorf("missing key: %q", got)
	}
	if !formHas(req, "outcome_note") || !formHas(req, "empty") {
		t.Error("a posted empty key must count as present")
	}
}

func TestPathInt(t *testing.T) {
	for raw, ok := range map[string]bool{
		"5": true, "+5": true, "-5": true, "05": true, "5.00": true, "1_0.0": true,
		"5.": false, "5.5": false, "_5": false, "5_": false, "1__0": false, "0x10": false, "": false,
	} {
		if got := pathInt.MatchString(raw); got != ok {
			t.Errorf("pathInt(%q) = %v, want %v", raw, got, ok)
		}
	}
}

func TestBadCSRFNeverTouchesThePool(t *testing.T) {
	at := time.Date(2026, 11, 13, 9, 30, 0, 0, time.UTC)
	now := func() time.Time { return at }
	mux := http.NewServeMux()
	mux.Handle("POST /privacy-requests", CreateHandler(nil, testEnv, now))
	mux.Handle("POST /privacy-requests/{id}", UpdateHandler(nil, testEnv, now))
	for _, path := range []string{"/privacy-requests", "/privacy-requests/5", "/privacy-requests/abc"} {
		req := httptest.NewRequest(http.MethodPost, path, strings.NewReader("status=fulfilled"))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.Header.Set("x-csrf-token", "not-a-token")
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: testCSRFCookie})
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req) // a nil pool would panic if it were used
		if rec.Code != http.StatusForbidden && rec.Code != http.StatusSeeOther {
			t.Errorf("%s: code %d", path, rec.Code)
		}
		if loc := rec.Header().Get("Location"); strings.HasPrefix(loc, "/privacy-requests") {
			t.Errorf("%s: bad CSRF reached the route, Location %q", path, loc)
		}
	}
}

// seedValue turns a JSON number into the int64 the seed columns hold.
func seedValue(v any) any {
	if f, ok := v.(float64); ok && f == math.Trunc(f) {
		return int64(f)
	}
	return v
}

func TestPrivacyRequestsGolden(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	ctx := context.Background()
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = fmt.Sprintf("$%d", i+1)
		}
		sql := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)", table.Table,
			strings.Join(table.Columns, ", "), strings.Join(marks, ", "))
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = seedValue(v)
			}
			if _, err := pool.Exec(ctx, sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
	}
	// The seed wrote ids by hand; SQLite's next id is MAX(id) + 1, so move the
	// Postgres identity there too.
	if _, err := pool.Exec(ctx, `SELECT setval(pg_get_serial_sequence('data_subject_request', 'id'),
		(SELECT MAX(id) FROM data_subject_request))`); err != nil {
		t.Fatal(err)
	}
	at, err := time.Parse(time.RFC3339, g.Now)
	if err != nil {
		t.Fatal(err)
	}
	now := func() time.Time { return at }
	mux := http.NewServeMux()
	mux.Handle("POST /privacy-requests", CreateHandler(pool, testEnv, now))
	mux.Handle("POST /privacy-requests/{id}", UpdateHandler(pool, testEnv, now))

	read := func(sql string) []map[string]any {
		rows, err := pool.Query(ctx, sql)
		if err != nil {
			t.Fatal(err)
		}
		defer rows.Close()
		out := []map[string]any{}
		for rows.Next() {
			var raw []byte
			if err := rows.Scan(&raw); err != nil {
				t.Fatal(err)
			}
			var m map[string]any
			if err := json.Unmarshal(raw, &m); err != nil {
				t.Fatal(err)
			}
			out = append(out, m)
		}
		if err := rows.Err(); err != nil {
			t.Fatal(err)
		}
		return out
	}
	queries := map[string]string{
		"data_subject_request": `SELECT to_jsonb(t)::text FROM data_subject_request t ORDER BY id`,
		"audit":                `SELECT (to_jsonb(t) - 'id')::text FROM audit t ORDER BY id`,
		"alert": `SELECT jsonb_build_object('id', id, 'dedupe_key', dedupe_key,
			'resolved_at', resolved_at)::text FROM alert ORDER BY id`,
	}
	for _, step := range g.Steps {
		req := httptest.NewRequest(http.MethodPost, step.Path, strings.NewReader(step.Body))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.Header.Set("x-csrf-token", csrfToken(t, testCSRFCookie, at))
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: testCSRFCookie})
		payload := map[string]any{"uid": step.Account, "sv": int64(1), "iat": at.Unix()}
		if step.Account != step.Workspace {
			payload["as"] = step.Workspace
			payload["ast"] = at.Unix()
		}
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, at)})
		if step.Lang != "" {
			req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: step.Lang})
		}
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req)
		if rec.Code != step.Status {
			t.Errorf("%s: status %d, Python %d (body %q)", step.Name, rec.Code, step.Status, rec.Body.String())
		}
		if got := rec.Header().Get("Location"); got != step.Location {
			t.Errorf("%s: Location %q, Python %q", step.Name, got, step.Location)
		}
		if step.Status != http.StatusSeeOther && rec.Body.String() != step.Response {
			t.Errorf("%s: body %q, Python %q", step.Name, rec.Body.String(), step.Response)
		}
		for table, sql := range queries {
			got, want := read(sql), step.State[table]
			if !reflect.DeepEqual(got, want) {
				gj, _ := json.Marshal(got)
				wj, _ := json.Marshal(want)
				t.Errorf("%s: %s\n got  %s\n want %s", step.Name, table, gj, wj)
			}
		}
		if t.Failed() {
			t.Fatalf("stopped after step %s", step.Name)
		}
	}
	for key, want := range g.ListForOwner {
		var owner *int64
		if key != "None" {
			var id int64
			fmt.Sscan(key, &id)
			owner = &id
		}
		rows, err := ListForOwner(ctx, pool, owner)
		if err != nil {
			t.Fatal(err)
		}
		got := []int64{}
		for _, r := range rows {
			got = append(got, r.ID)
		}
		if !reflect.DeepEqual(got, want) {
			t.Errorf("ListForOwner(%s) = %v, Python %v", key, got, want)
		}
	}
}
