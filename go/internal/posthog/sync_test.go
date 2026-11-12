package posthog

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Pinned from Python: uuid.uuid5(UUID('6f1c5c6e-0b8e-4d55-9d43-4b1f0b7a3e37'), '<id>:<stage>').
func TestEventUUIDMatchesPython(t *testing.T) {
	if got := eventUUID(42, "created"); got != "a51b963f-709b-582f-b689-11c358242436" {
		t.Errorf("eventUUID(42, created) = %s", got)
	}
	if got := eventUUID(7, "first_filing"); got != "2d037069-eb48-533d-9117-897709d7e848" {
		t.Errorf("eventUUID(7, first_filing) = %s", got)
	}
}

func TestApiHostOffAndOn(t *testing.T) {
	cases := []struct {
		name string
		cfg  Config
		want string
	}{
		{"on defaults", Config{"k", DefaultHost, DefaultAssetsHost}, "https://eu.i.posthog.com"},
		{"on with port", Config{"k", "https://ph.example.com:8443", DefaultAssetsHost}, "https://ph.example.com:8443"},
		{"no key", Config{"", DefaultHost, DefaultAssetsHost}, ""},
		{"http host", Config{"k", "http://eu.i.posthog.com", DefaultAssetsHost}, ""},
		{"http assets", Config{"k", DefaultHost, "http://eu-assets.i.posthog.com"}, ""},
		{"us host", Config{"k", "https://us.i.posthog.com", DefaultAssetsHost}, ""},
		{"us assets", Config{"k", DefaultHost, "https://us-assets.i.posthog.com"}, ""},
		{"empty host", Config{"k", "", DefaultAssetsHost}, ""},
	}
	for _, c := range cases {
		if got := apiHost(c.cfg); got != c.want {
			t.Errorf("%s: apiHost = %q, want %q", c.name, got, c.want)
		}
	}
}

func TestConfigFromEnvDefaultsOnlyWhenUnset(t *testing.T) {
	env := map[string]string{"POSTHOG_PROJECT_API_KEY": " k ", "POSTHOG_HOST": " https://h.example.com// "}
	lookup := func(n string) (string, bool) { v, ok := env[n]; return v, ok }
	want := Config{APIKey: "k", Host: "https://h.example.com", AssetsHost: DefaultAssetsHost}
	if got := ConfigFromEnv(lookup); got != want {
		t.Errorf("ConfigFromEnv = %+v, want %+v", got, want)
	}
	env["POSTHOG_HOST"] = ""
	if got := ConfigFromEnv(lookup); got.Host != "" {
		t.Errorf("empty POSTHOG_HOST must stay empty (off), got %q", got.Host)
	}
}

func TestStagesToSend(t *testing.T) {
	row := funnelRow{stage: "first_property", dates: map[string]string{
		"created": "2026-01-01T00:00:00+00:00", "first_login": "2026-01-02T00:00:00+00:00",
		"first_entity": "2026-01-03T00:00:00+00:00", "first_property": "2026-01-04T00:00:00+00:00",
	}}
	str := func(s string) *string { return &s }
	cases := []struct {
		name     string
		previous *string
		want     []string
	}{
		{"never sent", nil, []string{"created", "first_login", "first_entity", "first_property"}},
		{"unknown previous", str("nonsense"), []string{"created", "first_login", "first_entity", "first_property"}},
		{"after created", str("created"), []string{"first_login", "first_entity", "first_property"}},
		{"stage without date as previous", str("legal_accepted"), []string{"first_entity", "first_property"}},
		{"already current", str("first_property"), nil},
	}
	for _, c := range cases {
		if got := stagesToSend(c.previous, row); !reflect.DeepEqual(got, c.want) {
			t.Errorf("%s: got %v, want %v", c.name, got, c.want)
		}
	}
	if got := stagesToSend(nil, funnelRow{}); got != nil {
		t.Errorf("empty stage: got %v, want none", got)
	}
}

func TestPersonSet(t *testing.T) {
	a := account{id: 1, username: "host@example.com", displayName: "Villa Test", signupSource: "google",
		utmSource: "newsletter", utmMedium: "CPC-GCLID-1", utmCampaign: ""}
	want := map[string]any{
		"funnel_stage": "created", "email": "host@example.com", "workspace_name": "Villa Test",
		"signup_source": "google", "utm_source": "newsletter",
	}
	if got := personSet(a, "created"); !reflect.DeepEqual(got, want) {
		t.Errorf("personSet = %v, want %v", got, want)
	}
	b := account{id: 2, email: "real@example.com", username: "other@example.com", signupSource: "organic", utmCampaign: "xFBCLIDx"}
	if got := personSet(b, "first_login"); !reflect.DeepEqual(got, map[string]any{"funnel_stage": "first_login", "email": "real@example.com"}) {
		t.Errorf("personSet(b) = %v", got)
	}
	c := account{id: 3, username: "plainname"}
	if got := personSet(c, "created"); !reflect.DeepEqual(got, map[string]any{"funnel_stage": "created"}) {
		t.Errorf("personSet(c) = %v", got)
	}
}

func TestMonthStarts(t *testing.T) {
	prev, cur, err := monthStarts(time.Date(2026, 11, 12, 10, 0, 0, 0, time.UTC))
	if err != nil || prev != "2026-09-30T22:00:00+00:00" || cur != "2026-10-31T23:00:00+00:00" {
		t.Errorf("november: %s %s %v", prev, cur, err)
	}
	prev, cur, err = monthStarts(time.Date(2027, 1, 15, 10, 0, 0, 0, time.UTC))
	if err != nil || prev != "2026-11-30T23:00:00+00:00" || cur != "2026-12-31T23:00:00+00:00" {
		t.Errorf("january: %s %s %v", prev, cur, err)
	}
}

func TestCapturePayloadAndStatus(t *testing.T) {
	var mu sync.Mutex
	var gotPath, gotType string
	var gotBody map[string]any
	status := http.StatusOK
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		mu.Lock()
		defer mu.Unlock()
		gotPath, gotType = r.URL.Path, r.Header.Get("Content-Type")
		_ = json.Unmarshal(raw, &gotBody)
		w.WriteHeader(status)
	}))
	defer srv.Close()
	payload := map[string]any{
		"api_key": "k", "event": "created", "distinct_id": "42", "uuid": eventUUID(42, "created"),
		"timestamp":  "2026-01-01T00:00:00+00:00",
		"properties": map[string]any{"$ip": nil, "$geoip_disable": true, "$set": personSet(account{id: 42}, "created")},
	}
	if err := capture(context.Background(), srv.Client(), srv.URL, payload); err != nil {
		t.Fatal(err)
	}
	if gotPath != "/capture/" || gotType != "application/json" {
		t.Errorf("path %q type %q", gotPath, gotType)
	}
	props, _ := gotBody["properties"].(map[string]any)
	if gotBody["api_key"] != "k" || gotBody["event"] != "created" || gotBody["distinct_id"] != "42" ||
		gotBody["uuid"] != "a51b963f-709b-582f-b689-11c358242436" ||
		gotBody["timestamp"] != "2026-01-01T00:00:00+00:00" || props["$geoip_disable"] != true {
		t.Errorf("payload = %v", gotBody)
	}
	if v, has := props["$ip"]; !has || v != nil {
		t.Error("$ip must be present as null")
	}
	status = http.StatusInternalServerError
	err := capture(context.Background(), srv.Client(), srv.URL, payload)
	if se, ok := err.(*statusError); !ok || se.status != 500 {
		t.Errorf("500 gave %v, want statusError 500", err)
	}
}

func TestSyncOffMakesNoRequestAndNeedsNoDatabase(t *testing.T) {
	hit := false
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { hit = true }))
	defer srv.Close()
	for _, cfg := range []Config{
		{"", srv.URL, srv.URL}, {"k", "http://x.example", srv.URL}, {"k", "https://us.i.posthog.com", srv.URL},
	} {
		counts, err := Sync(context.Background(), nil, cfg, srv.Client(), time.Now())
		if err != nil || counts != (Counts{}) {
			t.Errorf("off: %+v %v", counts, err)
		}
	}
	if hit {
		t.Error("a request was made while PostHog is off")
	}
}

func TestSyncEndToEnd(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	if _, err := pool.Exec(ctx, `INSERT INTO user_account
		(id, username, password_hash, created_at, email, display_name, signup_source, signup_utm_source, signup_at, email_verified_at, posthog_stage) VALUES
		(1, 'one@example.com', 'x', '2026-01-03T00:00:00+00:00', NULL, 'Villa One', 'google', 'newsletter', '2026-01-01T00:00:00+00:00', '2026-01-02T00:00:00+00:00', NULL),
		(2, 'two', 'x', '2026-02-01T00:00:00+00:00', 'two@example.com', NULL, NULL, NULL, NULL, NULL, 'created'),
		(3, 'three', 'x', '2026-03-01T00:00:00+00:00', NULL, NULL, NULL, NULL, NULL, NULL, NULL)`); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, created_at, role) VALUES (4, 'boss', 'x', '2026-01-01T00:00:00+00:00', 'admin')`); err != nil {
		t.Fatal(err)
	}
	var mu sync.Mutex
	var events []string
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body map[string]any
		raw, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(raw, &body)
		mu.Lock()
		events = append(events, fmt.Sprintf("%v:%v:%v", body["distinct_id"], body["event"], body["timestamp"]))
		mu.Unlock()
		if body["distinct_id"] == "3" {
			w.WriteHeader(http.StatusBadGateway)
			return
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()
	cfg := Config{APIKey: "k", Host: srv.URL, AssetsHost: DefaultAssetsHost}
	now := time.Date(2026, 11, 12, 10, 0, 0, 0, time.UTC)
	counts, err := Sync(ctx, pool, cfg, srv.Client(), now)
	if err != nil {
		t.Fatal(err)
	}
	if counts != (Counts{Sent: 3, Skipped: 1, Failed: 1}) {
		t.Errorf("counts = %+v", counts)
	}
	sort.Strings(events)
	want := []string{
		"1:created:2026-01-03T00:00:00+00:00",
		"1:email_verified:2026-01-02T00:00:00+00:00",
		"1:signed_up:2026-01-01T00:00:00+00:00",
		"3:created:2026-03-01T00:00:00+00:00",
	}
	if !reflect.DeepEqual(events, want) {
		t.Errorf("events = %v, want %v", events, want)
	}
	stages := map[int64]*string{}
	rows, err := pool.Query(ctx, "SELECT id, posthog_stage FROM user_account ORDER BY id")
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var id int64
		var s *string
		if err := rows.Scan(&id, &s); err != nil {
			t.Fatal(err)
		}
		stages[id] = s
	}
	rows.Close()
	if stages[1] == nil || *stages[1] != "created" || stages[2] == nil || *stages[2] != "created" || stages[3] != nil || stages[4] != nil {
		t.Errorf("posthog_stage = %v %v %v %v", stages[1], stages[2], stages[3], stages[4])
	}
	events = nil
	counts, err = Sync(ctx, pool, cfg, srv.Client(), now)
	if err != nil || counts.Sent != 0 || counts.Failed != 1 || len(events) != 1 {
		t.Errorf("second run: %+v %v events=%v (only account 3 retries)", counts, err, events)
	}
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
	name := fmt.Sprintf("ubyhost_go_posthog_%d", time.Now().UnixNano())
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
