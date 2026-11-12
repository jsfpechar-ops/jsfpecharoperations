package metacapi

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

func str(s string) *string { return &s }

// Pinned from Python: json.dumps([event], separators=(",", ":")) of the same values.
func TestEventJSONMatchesPython(t *testing.T) {
	cfg := Config{PublicBase: "https://app.example.com"}
	cases := []struct {
		name string
		r    row
		want string
	}{
		{
			"null event id, awkward user agent",
			row{fbc: "fb.1.1.x", eventID: nil, emailVerifiedAt: "2026-01-01T00:00:00+00:00",
				clientUserAgent: "A\"B\\C\n\t\U0001F600 <i>&"},
			`[{"event_name":"CompleteRegistration","event_time":1767225600,"event_id":null,"action_source":"website","event_source_url":"https://app.example.com/signup","opt_out":true,"user_data":{"fbc":"fb.1.1.x","client_user_agent":"A\"B\\C\n\t\ud83d\ude00 <i>&"}}]`,
		},
		{
			"no user agent",
			row{fbc: "fb.1.1.x", eventID: str("abc"), emailVerifiedAt: "2026-01-01T02:00:00+02:00"},
			`[{"event_name":"CompleteRegistration","event_time":1767225600,"event_id":"abc","action_source":"website","event_source_url":"https://app.example.com/signup","opt_out":true,"user_data":{"fbc":"fb.1.1.x"}}]`,
		},
	}
	for _, c := range cases {
		ev, err := buildEvent(cfg, c.r)
		if err != nil {
			t.Fatal(c.name, err)
		}
		got, err := eventJSON(ev)
		if err != nil {
			t.Fatal(c.name, err)
		}
		if got != c.want {
			t.Errorf("%s:\n got %s\nwant %s", c.name, got, c.want)
		}
	}
}

// Pinned from Python: int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()), naive read as UTC.
func TestParseStoredMatchesPython(t *testing.T) {
	for _, s := range []string{
		"2026-01-01T00:00:00+00:00", "2026-01-01T02:00:00+02:00", "2026-01-01T00:00:00Z",
		"2026-01-01T00:00:00", "2026-01-01 00:00:00", "2026-01-01T00:00:00.000000+00:00",
	} {
		got, err := parseStored(s)
		if err != nil || got.Unix() != 1767225600 {
			t.Errorf("parseStored(%q) = %v, %v; want 1767225600", s, got.Unix(), err)
		}
	}
	if _, err := parseStored(""); err == nil {
		t.Error("an empty email_verified_at must be an error, as in Python")
	}
}

func TestRetryDelayAndIso(t *testing.T) {
	// Python: min(6 * 60 * 60, 60 * 2 ** min(attempts, 8)).
	for attempts, want := range map[int]time.Duration{1: 120 * time.Second, 2: 240 * time.Second, 8: 15360 * time.Second, 9: 15360 * time.Second} {
		if got := retryDelay(attempts); got != want {
			t.Errorf("retryDelay(%d) = %v, want %v", attempts, got, want)
		}
	}
	if got := iso(time.Date(2026, 11, 12, 10, 0, 5, 999, time.FixedZone("x", 3600))); got != "2026-11-12T09:00:05+00:00" {
		t.Errorf("iso = %s", got)
	}
	if got := truncate("ééé", 2); got != "éé" {
		t.Errorf("truncate counts characters, got %q", got)
	}
}

func TestConfigFromEnvAndEnabled(t *testing.T) {
	env := map[string]string{
		"UBYHOST_META_DATASET_ID": " 123 ", "UBYHOST_META_ACCESS_TOKEN": " tok ",
		"UBYHOST_PUBLIC_BASE_URL": "https://app.example.com/",
	}
	lookup := func(n string) (string, bool) { v, ok := env[n]; return v, ok }
	got := ConfigFromEnv(lookup)
	want := Config{DatasetID: "123", AccessToken: "tok", GraphVersion: "v26.0", PublicBase: "https://app.example.com", GraphHost: DefaultGraphHost}
	if got != want || !got.Enabled() {
		t.Errorf("ConfigFromEnv = %+v", got)
	}
	if got.endpoint() != "https://graph.facebook.com/v26.0/123/events" {
		t.Errorf("endpoint = %s", got.endpoint())
	}
	env["UBYHOST_META_GRAPH_VERSION"] = ""
	if ConfigFromEnv(lookup).GraphVersion != "" {
		t.Error("an empty UBYHOST_META_GRAPH_VERSION stays empty, as in Python")
	}
	for _, drop := range []string{"UBYHOST_META_DATASET_ID", "UBYHOST_META_ACCESS_TOKEN"} {
		saved := env[drop]
		delete(env, drop)
		if ConfigFromEnv(lookup).Enabled() {
			t.Errorf("must be off without %s", drop)
		}
		env[drop] = saved
	}
}

func TestSendOffMakesNoRequestAndNeedsNoDatabase(t *testing.T) {
	called := false
	srv := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) { called = true }))
	defer srv.Close()
	// A nil pool would panic on any database call.
	sum, err := Send(context.Background(), nil, Config{DatasetID: "123", GraphHost: srv.URL, GraphVersion: "v26.0"}, nil, time.Now())
	if err != nil || sum != (Summary{}) || called {
		t.Errorf("sum=%+v err=%v called=%v", sum, err, called)
	}
}

func TestPostOutcomes(t *testing.T) {
	const token = "SECRET-TOKEN"
	cases := []struct {
		name       string
		status     int
		body       string
		wantOK     bool
		wantRetry  bool
		wantConfig bool
		wantDetail string
	}{
		{"sent", 200, `{"events_received":1}`, true, false, false, ""},
		{"zero received", 200, `{"events_received":0}`, false, false, false, "HTTP 200"},
		{"server error", 500, `oops`, false, true, false, "HTTP 500"},
		{"rate limited", 429, `{}`, false, true, false, "HTTP 429"},
		{"transient flag", 400, `{"error":{"code":100,"is_transient":true,"message":"later"}}`, false, true, false, "HTTP 400, code 100: later"},
		{"transient code", 400, `{"error":{"code":4,"message":"slow down"}}`, false, true, false, "HTTP 400, code 4: slow down"},
		{"config code, token echoed", 400, `{"error":{"code":190,"message":"bad ` + token + ` here"}}`, false, true, true, "HTTP 400, code 190: bad [redacted] here"},
		{"fatal", 400, `{"error":{"code":100,"message":"Invalid parameter"}}`, false, false, false, "HTTP 400, code 100: Invalid parameter"},
		{"fatal without body", 404, ``, false, false, false, "HTTP 404"},
	}
	for _, c := range cases {
		var gotPath, gotQuery, gotType string
		var form map[string][]string
		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			gotPath, gotQuery, gotType = r.URL.Path, r.URL.RawQuery, r.Header.Get("Content-Type")
			_ = r.ParseForm()
			form = r.PostForm
			w.WriteHeader(c.status)
			_, _ = w.Write([]byte(c.body))
		}))
		cfg := Config{DatasetID: "123", AccessToken: token, TestEventCode: "TEST1", GraphVersion: "v26.0", GraphHost: srv.URL}
		out := post(context.Background(), srv.Client(), cfg, `[{"x":1}]`)
		srv.Close()
		if out.ok != c.wantOK || out.retry != c.wantRetry || out.config != c.wantConfig || out.detail != c.wantDetail {
			t.Errorf("%s: %+v", c.name, out)
		}
		if gotPath != "/v26.0/123/events" || gotQuery != "" || gotType != "application/x-www-form-urlencoded" {
			t.Errorf("%s: path=%q query=%q type=%q (the token must not be in the URL)", c.name, gotPath, gotQuery, gotType)
		}
		if form["data"][0] != `[{"x":1}]` || form["access_token"][0] != token || form["test_event_code"][0] != "TEST1" {
			t.Errorf("%s: form = %v", c.name, form)
		}
	}
	// A transport error is a retry and its detail names no URL and no token.
	srv := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	cfg := Config{DatasetID: "123", AccessToken: token, GraphVersion: "v26.0", GraphHost: srv.URL}
	srv.Close()
	out := post(context.Background(), http.DefaultClient, cfg, `[]`)
	if !out.retry || out.detail != "network: ConnectionError" || strings.Contains(out.detail, token) {
		t.Errorf("transport error: %+v", out)
	}
}

func TestSendEndToEnd(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	now := time.Date(2026, 11, 12, 10, 0, 0, 0, time.UTC)
	fresh := "2026-11-11T00:00:00+00:00" // verified yesterday: inside the 7-day window
	old := "2026-11-01T00:00:00+00:00"   // verified 11 days ago: outside it
	if _, err := pool.Exec(ctx, `INSERT INTO consent_texts (id, version, purpose, lang, text, text_sha256, created_at) VALUES (1, 'v1', 'meta', 'en', 't', 'h', '2026-01-01T00:00:00+00:00')`); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, created_at, email_verified_at) VALUES
		(1, 'a', 'x', $1, $1), (2, 'b', 'x', $1, $1), (3, 'c', 'x', $1, $1), (4, 'd', 'x', $2, $2),
		(5, 'e', 'x', $1, $1), (6, 'f', 'x', $1, $1)`, fresh, old); err != nil {
		t.Fatal(err)
	}
	// 1 sends, 2 is refused by Meta (retry), 3 is refused for good, 4 is too old,
	// 5 withdrew, 6 is not due yet.
	if _, err := pool.Exec(ctx, `INSERT INTO ad_click
		(id, user_account_id, platform, clicked_at, consent_text_id, consented_at, created_at, fbc, event_id, send_state, attempts, next_attempt_at, withdrawn_at, client_user_agent) VALUES
		(1, 1, 'meta', 'c', 1, 'c', 'c', 'fb.1.1.one', 'evt-one', 'pending', 2, '2026-11-12T09:00:00+00:00', NULL, 'UA one'),
		(2, 2, 'meta', 'c', 1, 'c', 'c', 'fb.1.1.two', 'evt-two', 'pending', 0, '2026-11-12T09:00:00+00:00', NULL, NULL),
		(3, 3, 'meta', 'c', 1, 'c', 'c', 'fb.1.1.three', 'evt-three', 'pending', 0, '2026-11-12T09:00:00+00:00', NULL, NULL),
		(4, 4, 'meta', 'c', 1, 'c', 'c', 'fb.1.1.four', 'evt-four', 'pending', 0, '2026-11-12T09:00:00+00:00', NULL, NULL),
		(5, 5, 'meta', 'c', 1, 'c', 'c', 'fb.1.1.five', 'evt-five', 'pending', 0, '2026-11-12T09:00:00+00:00', '2026-11-12T08:00:00+00:00', NULL),
		(6, 6, 'meta', 'c', 1, 'c', 'c', 'fb.1.1.six', 'evt-six', 'pending', 0, '2026-11-12T11:00:00+00:00', NULL, NULL)`); err != nil {
		t.Fatal(err)
	}
	var mu sync.Mutex
	var sent []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = r.ParseForm()
		data := r.PostForm.Get("data")
		mu.Lock()
		sent = append(sent, data)
		mu.Unlock()
		switch {
		case strings.Contains(data, "evt-two"):
			w.WriteHeader(http.StatusServiceUnavailable)
		case strings.Contains(data, "evt-three"):
			w.WriteHeader(http.StatusBadRequest)
			_, _ = w.Write([]byte(`{"error":{"code":100,"message":"Invalid parameter"}}`))
		default:
			_, _ = w.Write([]byte(`{"events_received":1}`))
		}
	}))
	defer srv.Close()
	cfg := Config{DatasetID: "123", AccessToken: "tok", GraphVersion: "v26.0", PublicBase: "https://app.example.com", GraphHost: srv.URL}
	sum, err := Send(ctx, pool, cfg, srv.Client(), now)
	if err != nil {
		t.Fatal(err)
	}
	if sum != (Summary{Sent: 1, Retry: 1, Failed: 1, Expired: 1}) {
		t.Errorf("summary = %+v", sum)
	}
	sort.Strings(sent)
	wantOne := `[{"event_name":"CompleteRegistration","event_time":1794355200,"event_id":"evt-one","action_source":"website","event_source_url":"https://app.example.com/signup","opt_out":true,"user_data":{"fbc":"fb.1.1.one","client_user_agent":"UA one"}}]`
	if len(sent) != 3 || !contains(sent, wantOne) {
		t.Errorf("sent = %v", sent)
	}
	type state struct {
		State    string
		Attempts int
		Err      *string
		Next     *string
		Uploaded *string
	}
	got := map[int]state{}
	rows, err := pool.Query(ctx, "SELECT id, send_state, attempts, last_error, next_attempt_at, uploaded_at FROM ad_click ORDER BY id")
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var id int
		var s state
		if err := rows.Scan(&id, &s.State, &s.Attempts, &s.Err, &s.Next, &s.Uploaded); err != nil {
			t.Fatal(err)
		}
		got[id] = s
	}
	rows.Close()
	if s := got[1]; s.State != "sent" || s.Attempts != 3 || s.Err != nil || s.Uploaded == nil {
		t.Errorf("row 1 = %+v", s)
	}
	// Retry: attempts 1, delay 120 s from now.
	if s := got[2]; s.State != "pending" || s.Attempts != 1 || s.Err == nil || *s.Err != "HTTP 503" || s.Next == nil || *s.Next != "2026-11-12T10:02:00+00:00" {
		t.Errorf("row 2 = %+v", s)
	}
	if s := got[3]; s.State != "failed" || s.Attempts != 1 || s.Err == nil || *s.Err != "HTTP 400, code 100: Invalid parameter" {
		t.Errorf("row 3 = %+v", s)
	}
	if s := got[4]; s.State != "expired" || s.Err == nil || *s.Err != "older than Meta's 7-day event window" || s.Attempts != 0 {
		t.Errorf("row 4 = %+v", s)
	}
	if got[5].State != "pending" || got[5].Attempts != 0 || got[6].State != "pending" || got[6].Attempts != 0 {
		t.Errorf("rows 5 and 6 must be untouched: %+v %+v", got[5], got[6])
	}
	// A second run later: row 2 is due again and is retried, nothing is sent twice.
	sent = nil
	later := now.Add(3 * time.Minute)
	if _, err := Send(ctx, pool, cfg, srv.Client(), later); err != nil {
		t.Fatal(err)
	}
	if len(sent) != 1 || !strings.Contains(sent[0], "evt-two") {
		t.Errorf("second run sent %v (only row 2 is due)", sent)
	}
	// A claim whose worker died is handed back after 10 minutes and sent once.
	if _, err := pool.Exec(ctx, `UPDATE ad_click SET send_state = 'sending', next_attempt_at = '2026-11-12T09:00:00+00:00' WHERE id = 6`); err != nil {
		t.Fatal(err)
	}
	sent = nil
	if _, err := Send(ctx, pool, cfg, srv.Client(), now.Add(2*time.Hour)); err != nil {
		t.Fatal(err)
	}
	resent := 0
	for _, data := range sent {
		if strings.Contains(data, "evt-six") {
			resent++
		}
	}
	if resent != 1 {
		t.Errorf("the stale claim must be handed back and sent once, got %d in %v", resent, sent)
	}
}

func contains(list []string, want string) bool {
	for _, s := range list {
		if s == want {
			return true
		}
	}
	return false
}

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL, applies
// the goose Up sections of App/migrations_pg and drops the database at the end.
// It skips when the variable is unset.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_metacapi_%d", time.Now().UnixNano())
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
	applyMigrations(t, pool)
	return pool
}

func applyMigrations(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	files, err := filepath.Glob("../../../App/migrations_pg/*.sql")
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
		if _, err := pool.Exec(context.Background(), up); err != nil {
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
}
