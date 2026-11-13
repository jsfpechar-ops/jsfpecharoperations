package invoices

// Test environment: a throwaway PostgreSQL database with the migrations
// applied, two hosts, and a mux with the routes of this package. Tests that
// need it skip when UBYHOST_TEST_DATABASE_URL is not set.

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
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

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL and
// applies the PostgreSQL migrations, as go/internal/web/stayfees does.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_invoices_%d", time.Now().UnixNano())
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
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("migration %s: %v", f, err)
		}
	}
	return pool
}

// testSeed holds the ids of the rows seedHosts makes.
type testSeed struct {
	Entity, PayerEntity, ForeignEntity      int64
	Apartment, ForeignApartment             int64
	Stay, StayB, ForeignStay, CancelledStay int64
}

// seedHosts makes host1 (id 1) and host2 (id 2), each with a business, a
// property and a stay; host1 also has a second (VAT payer) business, a
// second stay and a cancelled stay.
func seedHosts(t *testing.T, pool *pgxpool.Pool) testSeed {
	t.Helper()
	ctx := context.Background()
	exec := func(sql string, args ...any) {
		t.Helper()
		if _, err := pool.Exec(ctx, sql, args...); err != nil {
			t.Fatalf("seed: %v\n%s", err, sql)
		}
	}
	for _, u := range []struct {
		id   int
		name string
	}{{1, "host1"}, {2, "host2"}} {
		exec(`INSERT INTO user_account (id, username, password_hash, created_at, role, active, must_change_password, session_version)
		      VALUES ($1, $2, 'x', '2026-01-01', 'host', 1, 0, 1)`, u.id, u.name)
		for _, doc := range []string{"terms", "privacy", "dpa"} {
			exec(`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method)
			      VALUES ($1, $2, $3, '2026-01-01', 'clickwrap')`, u.id, doc, acceptedVersion)
		}
	}
	s := testSeed{Entity: 1, PayerEntity: 2, ForeignEntity: 3, Apartment: 1, ForeignApartment: 2,
		Stay: 11, StayB: 12, ForeignStay: 13, CancelledStay: 14}
	entity := func(id int64, owner int, name, vat, ico, dic string) {
		exec(`INSERT INTO legal_entity (id, name, seat, ico, dic, contact_email, bank_account, iban, vat_status,
		        registry_entry, invoice_prefix, invoice_due_days, owner_user_id, created_at)
		      VALUES ($1, $2, 'Ulice 1, 110 00 Praha', $3, $4, 'op@example.test', '19-2000145399/0800',
		        'CZ6508000000192000145399', $5, 'C 1 vedená u Městského soudu v Praze', '', 14, $6, '2026-01-01')`,
			id, name, ico, dic, vat, owner)
	}
	entity(1, 1, "Provoz Jedna s.r.o.", "non_payer", "27082440", "")
	entity(2, 1, "Provoz Dva a.s.", "payer", "27082440", "CZ27082440")
	entity(3, 2, "Cizí Provoz s.r.o.", "non_payer", "27082440", "")
	exec(`INSERT INTO apartment (id, internal_name, uby_name, legal_entity_id, owner_user_id, created_at)
	      VALUES (1, 'Chata U Lesa', 'UBY1', 1, 1, '2026-01-01'), (2, 'Cizí byt', 'UBY2', 3, 2, '2026-01-01')`)
	stay := func(id, apartment int64, from, to, status, source string) {
		exec(`INSERT INTO reservation (id, apartment_id, source, uid, date_from, date_to, status, guest_email, created_at, updated_at)
		      VALUES ($1, $2, $3, $4, $5, $6, $7, 'guest@example.test', '2026-01-01', '2026-01-01')`,
			id, apartment, source, fmt.Sprintf("uid-%d", id), from, to, status)
	}
	stay(11, 1, "2026-11-10", "2026-11-13", "active", "ical")
	stay(12, 1, "2026-10-01", "2026-10-04", "active", "ical")
	stay(13, 2, "2026-11-10", "2026-11-13", "active", "ical")
	stay(14, 1, "2026-09-01", "2026-09-04", "cancelled", "ical")
	return s
}

// testCaller is who a request is made as.
type testCaller struct {
	UserID int64
	Lang   string
}

var (
	host1 = testCaller{UserID: 1, Lang: "cs"}
	host2 = testCaller{UserID: 2, Lang: "cs"}
)

type testApp struct {
	t    *testing.T
	pool *pgxpool.Pool
	mux  *http.ServeMux
}

func newTestApp(t *testing.T) (*testApp, testSeed) {
	t.Helper()
	pool := testPool(t)
	seed := seedHosts(t, pool)
	mux := http.NewServeMux()
	for _, r := range Routes(pool, testEnv(), func() time.Time { return testNow }) {
		mux.Handle(r.Pattern, r.Handler)
	}
	return &testApp{t: t, pool: pool, mux: mux}, seed
}

func csrfPair(t *testing.T) (*http.Cookie, string) {
	t.Helper()
	cookie := "invoices-csrf-cookie"
	sum := sha256.Sum256([]byte(cookie))
	token, err := secure.NewTimedSerializer(testSecret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, testNow)
	if err != nil {
		t.Fatal(err)
	}
	return &http.Cookie{Name: "ubyhost_csrf", Value: cookie}, token
}

// do sends one request. who nil is a signed-out visitor; a POST carries a
// valid CSRF token unless noCSRF.
func (a *testApp) do(method, path string, form url.Values, who *testCaller, noCSRF ...bool) *httptest.ResponseRecorder {
	a.t.Helper()
	var req *http.Request
	if method == http.MethodPost {
		req = httptest.NewRequest(method, path, strings.NewReader(form.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		if len(noCSRF) == 0 || !noCSRF[0] {
			ck, token := csrfPair(a.t)
			req.AddCookie(ck)
			req.Header.Set("X-CSRF-Token", token)
		}
	} else {
		req = httptest.NewRequest(method, path, nil)
	}
	if who != nil {
		payload := map[string]any{"sv": 1, "iat": testNow.Unix(), "uid": who.UserID}
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, testNow)})
		if who.Lang != "" {
			req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: who.Lang})
		}
	}
	rec := httptest.NewRecorder()
	a.mux.ServeHTTP(rec, req)
	return rec
}

func (a *testApp) get(path string, who *testCaller) *httptest.ResponseRecorder {
	return a.do(http.MethodGet, path, nil, who)
}

// issueFor issues a real invoice for a stay through the package's own writer
// and returns its id and number.
func (a *testApp) issueFor(e entity, stayID int64, extra url.Values, owner int64) (int64, string) {
	a.t.Helper()
	ctx := context.Background()
	var st *stay
	for _, id := range []int64{stayID} {
		var err error
		st, err = stayFor(ctx, a.pool, owner, itoa(id))
		if err != nil || st == nil {
			a.t.Fatalf("stayFor %d: %v %v", id, st, err)
		}
	}
	form := url.Values{"stay_price": {"1500"}, "buyer_name": {"Jana Testová"}, "buyer_email": {"jana@example.test"},
		"lang": {"cs"}, "already_paid": {"0"}}
	for k, v := range extra {
		form[k] = v
	}
	d := buildDraft(e, form, pragueDay(testNow), st)
	d.OwnerUserID = &owner
	actor := owner
	id, number, err := writeIssued(ctx, a.pool, d, &actor, testNow)
	if err != nil {
		a.t.Fatalf("writeIssued: %v", err)
	}
	return id, number
}

func (a *testApp) entityRow(id int64) entity {
	a.t.Helper()
	e, err := scanEntity(a.pool.QueryRow(context.Background(), `SELECT `+entityColumns+` FROM legal_entity WHERE id = $1`, id))
	if err != nil {
		a.t.Fatal(err)
	}
	return e
}

func (a *testApp) count(sql string, args ...any) int64 {
	a.t.Helper()
	var n int64
	if err := a.pool.QueryRow(context.Background(), sql, args...).Scan(&n); err != nil {
		a.t.Fatal(err)
	}
	return n
}

// httptestPost is a POST request whose form is already parsed.
func httptestPost(form url.Values) *http.Request {
	req := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	_ = req.ParseForm()
	return req
}
