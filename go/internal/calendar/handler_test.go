package calendar

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const dbSecret = "calendar-test-secret-key-0123456789abcdef"

// dbNow is the clock of every DB test: 2026-04-20 in Prague, before the May stays.
var dbNow = time.Date(2026, 4, 20, 12, 0, 0, 0, time.UTC)

// dbGetenv is the getenv of every DB test: one data key, no legacy key.
func dbGetenv(k string) string {
	return map[string]string{
		"UBYHOST_SECRET_KEY":      dbSecret,
		"UBYHOST_DATA_KEYS":       dbDataKey(),
		"UBYHOST_DATA_KEY_LEGACY": "0",
	}[k]
}

func dbDataKey() string {
	return base64.URLEncoding.EncodeToString(bytes.Repeat([]byte{7}, 32))
}

// dbEncrypt makes a token the way the guest form does, under the test data key.
func dbEncrypt(t *testing.T, plain string) string {
	t.Helper()
	mf, err := secure.NewMultiFernet([]byte(dbDataKey()))
	if err != nil {
		t.Fatal(err)
	}
	tok, err := mf.EncryptString(plain)
	if err != nil {
		t.Fatal(err)
	}
	return tok
}

// dbPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL, applies
// the goose Up sections of App/migrations_pg and drops it at the end.
func dbPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := "ubyhost_go_calendar_" + strings.ReplaceAll(time.Now().Format("150405.000000000"), ".", "")
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
	files, _ := filepath.Glob("../../../App/migrations_pg/*.sql")
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

// dbSeed loads two owners (1 and 2), apartments, stays and guests. Every stay
// has its own id so each case reads its own row from the events list.
func dbSeed(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	ctx := context.Background()
	mustEnc := func(plain string) string { return dbEncrypt(t, plain) }
	doc := mustEnc("C01X00T47")
	street := mustEnc("Hlavni 1")
	city := mustEnc("Brno")
	stmts := []string{
		`INSERT INTO user_account (id, username, password_hash, role, created_at) VALUES (1, 'owner@example.test', 'x', 'host', '2026-01-01')`,
		`INSERT INTO user_account (id, username, password_hash, role, created_at) VALUES (2, 'other@example.test', 'x', 'host', '2026-01-01')`,
		`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES (1, 'terms', '1.7', '2026-01-01', 'clickwrap')`,
		`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES (1, 'privacy', '1.7', '2026-01-01', 'clickwrap')`,
		`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES (1, 'dpa', '1.7', '2026-01-01', 'clickwrap')`,
		`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES (2, 'terms', '1.7', '2026-01-01', 'clickwrap')`,
		`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES (2, 'privacy', '1.7', '2026-01-01', 'clickwrap')`,
		`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES (2, 'dpa', '1.7', '2026-01-01', 'clickwrap')`,
		// Apartments: 7 active with hours, 8 archived, 9 inactive, 10 another owner's, 11 active without hours.
		`INSERT INTO apartment (id, owner_user_id, internal_name, city_en, uby_name, permalink_token, created_at, checkin_hour, checkout_hour, active, archived_at) VALUES (7, 1, 'Byt Dole', 'Brno', 'UBY', 'tok7', '2026-01-01', 14, 10, 1, NULL)`,
		`INSERT INTO apartment (id, owner_user_id, internal_name, city_en, uby_name, permalink_token, created_at, checkin_hour, checkout_hour, active, archived_at) VALUES (8, 1, 'Byt Archiv', 'Brno', 'UBY', 'tok8', '2026-01-01', 14, 10, 1, '2026-01-02')`,
		`INSERT INTO apartment (id, owner_user_id, internal_name, city_en, uby_name, permalink_token, created_at, checkin_hour, checkout_hour, active, archived_at) VALUES (9, 1, 'Byt Vypnuty', 'Brno', 'UBY', 'tok9', '2026-01-01', 14, 10, 0, NULL)`,
		`INSERT INTO apartment (id, owner_user_id, internal_name, city_en, uby_name, permalink_token, created_at, checkin_hour, checkout_hour, active, archived_at) VALUES (10, 2, 'Cizi byt', 'Brno', 'UBY', 'tok10', '2026-01-01', 14, 10, 1, NULL)`,
		`INSERT INTO apartment (id, owner_user_id, internal_name, city_en, uby_name, permalink_token, created_at, checkin_hour, checkout_hour, active, archived_at) VALUES (11, 1, 'Byt Bez Casu', 'Brno', 'UBY', 'tok11', '2026-01-01', NULL, NULL, 1, NULL)`,
		// Stays. 201 ready, 202 demo, 203 reported, 204 no check-in hour, 205 cancelled,
		// 206 another owner, 207 archived stay, 208 archived apartment, 209 inactive apartment,
		// 210 ends on the range start, 211 starts on the range end.
		`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, summary, status, source, declared_guests, archived_at, created_at, updated_at) VALUES (201, 7, 'u201', '2026-05-10', '2026-05-12', 'Erika', 'active', 'host', 1, NULL, '2026-01-01', '2026-01-01')`,
		`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, summary, status, source, declared_guests, archived_at, created_at, updated_at) VALUES (202, 7, 'u202', '2026-05-15', '2026-05-17', 'Demo', 'active', 'demo', 1, NULL, '2026-01-01', '2026-01-01')`,
		`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, summary, status, source, declared_guests, archived_at, created_at, updated_at) VALUES (203, 7, 'u203', '2026-05-20', '2026-05-22', 'Filed', 'active', 'host', 1, NULL, '2026-01-01', '2026-01-01')`,
		`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, summary, status, source, declared_guests, archived_at, created_at, updated_at) VALUES (204, 11, 'u204', '2026-05-25', '2026-05-27', 'Bez casu', 'active', 'host', 1, NULL, '2026-01-01', '2026-01-01')`,
		`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, summary, status, source, declared_guests, archived_at, created_at, updated_at) VALUES (205, 7, 'u205', '2026-05-30', '2026-05-31', 'Zrusena', 'cancelled', 'host', 1, NULL, '2026-01-01', '2026-01-01')`,
		`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, summary, status, source, declared_guests, archived_at, created_at, updated_at) VALUES (206, 10, 'u206', '2026-05-30', '2026-05-31', 'Cizi', 'active', 'host', 1, NULL, '2026-01-01', '2026-01-01')`,
		`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, summary, status, source, declared_guests, archived_at, created_at, updated_at) VALUES (207, 7, 'u207', '2026-06-01', '2026-06-02', 'Archiv', 'active', 'host', 1, '2026-01-02', '2026-01-01', '2026-01-01')`,
		`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, summary, status, source, declared_guests, archived_at, created_at, updated_at) VALUES (208, 8, 'u208', '2026-06-05', '2026-06-06', 'Byt archiv', 'active', 'host', 1, NULL, '2026-01-01', '2026-01-01')`,
		`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, summary, status, source, declared_guests, archived_at, created_at, updated_at) VALUES (209, 9, 'u209', '2026-06-08', '2026-06-09', 'Vypnuty', 'active', 'host', 1, NULL, '2026-01-01', '2026-01-01')`,
		`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, summary, status, source, declared_guests, archived_at, created_at, updated_at) VALUES (210, 7, 'u210', '2026-04-01', '2026-04-10', 'Konec', 'active', 'host', 1, NULL, '2026-01-01', '2026-01-01')`,
		`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, summary, status, source, declared_guests, archived_at, created_at, updated_at) VALUES (211, 7, 'u211', '2026-04-20', '2026-04-25', 'Zacatek', 'active', 'host', 1, NULL, '2026-01-01', '2026-01-01')`,
		// Guests. 201 foreign, complete, verified, not sent. 202 the same guest on a demo stay.
		// 203 sent by the host with a submitted_at stamp. The document number is encrypted.
		fmt.Sprintf(`INSERT INTO guest (id, reservation_id, surname, first_name, birth_date, nationality, res_country, res_street_enc, res_city_enc, doc_number_enc, purpose, signature_png, identity_verified_at, submit_state, submitted_at, is_lead, created_at, updated_at) VALUES (1, 201, 'Mustermann', 'Erika', '02011990', 'DEU', 'DEU', '%s', '%s', '%s', '10', 'imported', '2026-04-01T08:00:00Z', 'pending', NULL, 1, '2026-01-01', '2026-01-01')`, street, city, doc),
		fmt.Sprintf(`INSERT INTO guest (id, reservation_id, surname, first_name, birth_date, nationality, res_country, res_street_enc, res_city_enc, doc_number_enc, purpose, signature_png, identity_verified_at, submit_state, submitted_at, is_lead, created_at, updated_at) VALUES (2, 202, 'Mustermann', 'Erika', '02011990', 'DEU', 'DEU', '%s', '%s', '%s', '10', 'imported', '2026-04-01T08:00:00Z', 'pending', NULL, 1, '2026-01-01', '2026-01-01')`, street, city, doc),
		fmt.Sprintf(`INSERT INTO guest (id, reservation_id, surname, first_name, birth_date, nationality, res_country, res_street_enc, res_city_enc, doc_number_enc, purpose, signature_png, identity_verified_at, submit_state, submitted_at, is_lead, created_at, updated_at) VALUES (3, 203, 'Mustermann', 'Erika', '02011990', 'DEU', 'DEU', '%s', '%s', '%s', '10', 'imported', '2026-04-01T08:00:00Z', 'sent', '2026-05-19T10:00:00Z', 1, '2026-01-01', '2026-01-01')`, street, city, doc),
	}
	for _, s := range stmts {
		if _, err := pool.Exec(ctx, s); err != nil {
			t.Fatalf("seed: %v\n%s", err, s)
		}
	}
}

// dbCookie is a signed-in session cookie for account uid.
func dbCookie(uid int64) *http.Cookie {
	return &http.Cookie{Name: session.CookieName, Value: session.Sign(dbSecret, map[string]any{"uid": uid, "sv": 1}, dbNow)}
}

// dbServe runs GET /dashboard/calendar?rawQuery through the real handler.
func dbServe(t *testing.T, pool *pgxpool.Pool, rawQuery string, cookie *http.Cookie) *httptest.ResponseRecorder {
	t.Helper()
	h := Handler(pool, dbGetenv, func() time.Time { return dbNow })
	req := httptest.NewRequest(http.MethodGet, "/dashboard/calendar?"+rawQuery, nil)
	if cookie != nil {
		req.AddCookie(cookie)
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

// dbBody decodes a 200 answer.
type dbBody struct {
	Properties []propertyItem `json:"properties"`
	Events     []eventOut     `json:"events"`
}

func dbDecode(t *testing.T, rec *httptest.ResponseRecorder) dbBody {
	t.Helper()
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d, want 200: %s", rec.Code, rec.Body.String())
	}
	var b dbBody
	if err := json.Unmarshal(rec.Body.Bytes(), &b); err != nil {
		t.Fatal(err)
	}
	return b
}

func dbEvent(b dbBody, id int64) (eventOut, bool) {
	for _, e := range b.Events {
		if e.ID == id {
			return e, true
		}
	}
	return eventOut{}, false
}

const dbDefaultRange = "from=2026-05-01&to=2026-06-30"

func TestDashboardCalendarSignedOutRedirects(t *testing.T) {
	pool := dbPool(t)
	dbSeed(t, pool)
	rec := dbServe(t, pool, dbDefaultRange, nil)
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("status %d, want 303", rec.Code)
	}
	if loc := rec.Header().Get("Location"); loc != "/login?next=/dashboard/calendar" {
		t.Fatalf("location %q", loc)
	}
	if rec.Header().Get("Cache-Control") != "no-store" {
		t.Fatalf("cache-control %q", rec.Header().Get("Cache-Control"))
	}
}

func TestDashboardCalendarOwnerScope(t *testing.T) {
	pool := dbPool(t)
	dbSeed(t, pool)
	rec := dbServe(t, pool, dbDefaultRange, dbCookie(1))
	b := dbDecode(t, rec)
	if rec.Header().Get("Cache-Control") != "no-store" {
		t.Fatalf("cache-control %q", rec.Header().Get("Cache-Control"))
	}
	for _, id := range []int64{201, 202, 203, 204} {
		if _, ok := dbEvent(b, id); !ok {
			t.Errorf("stay %d should be listed", id)
		}
	}
	for _, id := range []int64{205, 206, 207, 208, 209} {
		if _, ok := dbEvent(b, id); ok {
			t.Errorf("stay %d should be absent", id)
		}
	}
	// Inactive apartment 9 and archived apartment 8 are absent from properties too.
	names := map[int64]string{}
	for _, p := range b.Properties {
		names[p.ID] = p.Name
	}
	if names[7] != "Byt Dole" || names[11] != "Byt Bez Casu" || len(names) != 2 {
		t.Fatalf("properties %v", names)
	}
}

func TestDashboardCalendarPropertyFilter(t *testing.T) {
	pool := dbPool(t)
	dbSeed(t, pool)
	b := dbDecode(t, dbServe(t, pool, dbDefaultRange+"&property=11", dbCookie(1)))
	if len(b.Events) != 1 {
		t.Fatalf("property 11 should list only stay 204, got %d events", len(b.Events))
	}
	if _, ok := dbEvent(b, 204); !ok {
		t.Fatal("stay 204 missing")
	}
	b = dbDecode(t, dbServe(t, pool, dbDefaultRange+"&property=7", dbCookie(1)))
	if _, ok := dbEvent(b, 204); ok {
		t.Fatal("property 7 must not list stay 204")
	}
	if _, ok := dbEvent(b, 201); !ok {
		t.Fatal("property 7 must list stay 201")
	}
}

func TestDashboardCalendarForeignAndBadInput(t *testing.T) {
	pool := dbPool(t)
	dbSeed(t, pool)
	cases := []struct {
		name, query string
		status      int
		body        string
	}{
		{"property of another owner", dbDefaultRange + "&property=10", http.StatusNotFound, `{"error":"not_found"}`},
		{"inactive property", dbDefaultRange + "&property=9", http.StatusNotFound, `{"error":"not_found"}`},
		{"bad range format", "from=2026/05/01&to=2026-06-30", http.StatusUnprocessableEntity, `{"error":"invalid_range"}`},
		{"end before start", "from=2026-06-30&to=2026-05-01", http.StatusUnprocessableEntity, `{"error":"invalid_range"}`},
		{"over 370 days", "from=2026-01-01&to=2027-01-07", http.StatusUnprocessableEntity, `{"error":"invalid_range"}`},
		{"bad property", dbDefaultRange + "&property=abc", http.StatusUnprocessableEntity, `{"error":"invalid_range"}`},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			rec := dbServe(t, pool, c.query, dbCookie(1))
			if rec.Code != c.status {
				t.Fatalf("status %d, want %d: %s", rec.Code, c.status, rec.Body.String())
			}
			if got := rec.Header().Get("Cache-Control"); got != "no-store" {
				t.Fatalf("cache-control %q", got)
			}
			if got := strings.TrimSpace(rec.Body.String()); got != c.body {
				t.Fatalf("body %s, want %s", got, c.body)
			}
		})
	}
}

func TestDashboardCalendarProgressAndTone(t *testing.T) {
	pool := dbPool(t)
	dbSeed(t, pool)
	b := dbDecode(t, dbServe(t, pool, dbDefaultRange, dbCookie(1)))

	ready, ok := dbEvent(b, 201)
	if !ok {
		t.Fatal("stay 201 missing")
	}
	if ready.Status != "ready" || ready.Tone != "ready" || ready.Preview {
		t.Errorf("foreign complete verified unsent: status %s tone %s preview %v", ready.Status, ready.Tone, ready.Preview)
	}
	if ready.Guests != 1 || ready.Complete != 1 {
		t.Errorf("guests %d complete %d", ready.Guests, ready.Complete)
	}

	demo, ok := dbEvent(b, 202)
	if !ok {
		t.Fatal("stay 202 missing")
	}
	if demo.Status != "ready" || !demo.Preview || demo.Tone != "neutral" {
		t.Errorf("demo stay: status %s tone %s preview %v", demo.Status, demo.Tone, demo.Preview)
	}
	if demo.Source == nil || *demo.Source != "demo" {
		t.Errorf("demo source %v", demo.Source)
	}

	reported, ok := dbEvent(b, 203)
	if !ok {
		t.Fatal("stay 203 missing")
	}
	if reported.Status != "reported" || reported.Tone != "done" {
		t.Errorf("sent stay: status %s tone %s", reported.Status, reported.Tone)
	}
}

func TestDashboardCalendarRangeBoundaries(t *testing.T) {
	pool := dbPool(t)
	dbSeed(t, pool)
	b := dbDecode(t, dbServe(t, pool, "from=2026-04-10&to=2026-04-20", dbCookie(1)))
	if _, ok := dbEvent(b, 210); !ok {
		t.Error("stay ending exactly on from must be included")
	}
	if _, ok := dbEvent(b, 211); ok {
		t.Error("stay starting on to must be excluded")
	}
}

func TestDashboardCalendarTimingFallback(t *testing.T) {
	pool := dbPool(t)
	dbSeed(t, pool)
	b := dbDecode(t, dbServe(t, pool, dbDefaultRange, dbCookie(1)))
	noHours, ok := dbEvent(b, 204)
	if !ok {
		t.Fatal("stay 204 missing")
	}
	if noHours.DisplayStart != "2026-05-25T12:00" || noHours.DisplayEnd != "2026-05-27T12:00" {
		t.Errorf("display %s / %s", noHours.DisplayStart, noHours.DisplayEnd)
	}
	if !noHours.TimingFallback {
		t.Error("timingFallback must be true without check-in hour")
	}
	withHours, ok := dbEvent(b, 201)
	if !ok {
		t.Fatal("stay 201 missing")
	}
	if withHours.DisplayStart != "2026-05-10T14:00" || withHours.DisplayEnd != "2026-05-12T10:00" || withHours.TimingFallback {
		t.Errorf("hours: %s / %s fallback %v", withHours.DisplayStart, withHours.DisplayEnd, withHours.TimingFallback)
	}
}

// TestDashboardCalendarExactBytes pins the wire format of one small answer.
func TestDashboardCalendarExactBytes(t *testing.T) {
	pool := dbPool(t)
	dbSeed(t, pool)
	rec := dbServe(t, pool, "from=2026-05-25&to=2026-05-28&property=11", dbCookie(1))
	want := `{"properties":[{"id":11,"name":"Byt Bez Casu"},{"id":7,"name":"Byt Dole"}],"events":[{"id":204,"propertyId":11,"property":"Byt Bez Casu","label":"Bez casu","start":"2026-05-25","end":"2026-05-27","displayStart":"2026-05-25T12:00","displayEnd":"2026-05-27T12:00","timingFallback":true,"guests":0,"complete":0,"expected":1,"status":"incomplete","tone":"action","preview":false,"source":"host","url":"/reservations/204?return_to=/"}]}`
	if got := strings.TrimSpace(rec.Body.String()); got != want {
		t.Fatalf("body\n got %s\nwant %s", got, want)
	}
}
