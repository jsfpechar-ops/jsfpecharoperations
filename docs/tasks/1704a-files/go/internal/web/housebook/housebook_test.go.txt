package housebook

// Tests of GET /housebook (brief 1704a). The expected strings are written by
// hand from the seed below; there is no Python golden file.

import (
	"context"
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

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const testSecret = "housebook-test-secret-key-0123456789abcdef"

var testNow = time.Date(2026, 11, 17, 12, 0, 0, 0, time.UTC)

func testGetenv(k string) string {
	return map[string]string{"UBYHOST_SECRET_KEY": testSecret}[k]
}

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL and
// applies the Postgres migrations. The tests are never skipped silently: a
// missing URL fails them.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Fatal("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_housebook_%d", time.Now().UnixNano())
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

// seed writes admin 1 and hosts 2 and 3 (current legal acceptances, so
// require_login does not send them to /account/accept), the properties,
// stays and guests the tests read. Host 3 owns the rows that must never show
// up for host 2.
func seed(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	ctx := context.Background()
	exec := func(sql string, args ...any) {
		t.Helper()
		if _, err := pool.Exec(ctx, sql, args...); err != nil {
			t.Fatalf("%s: %v", sql, err)
		}
	}
	for _, a := range []struct {
		id         int64
		name, role string
	}{{1, "admin_one", "admin"}, {2, "host_two", "host"}, {3, "host_three", "host"}} {
		exec(`INSERT INTO user_account (id, username, password_hash, created_at, role, active, session_version) VALUES ($1, $2, 'x', '2026-01-01T00:00:00+00:00', $3, 1, 1)`, a.id, a.name, a.role)
		for doc, ver := range map[string]string{"terms": "1.7", "privacy": "1.8", "dpa": "1.8"} {
			exec(`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES ($1, $2, $3, '2026-01-01T00:00:00+00:00', 'clickwrap')`, a.id, doc, ver)
		}
	}
	for _, a := range []struct {
		id    int64
		name  string
		owner int64
	}{{10, "Alpha Flat", 2}, {11, "Bravo House", 2}, {20, "Zulu Villa", 3}} {
		exec(`INSERT INTO apartment (id, internal_name, owner_user_id, created_at) VALUES ($1, $2, $3, '2026-01-01T00:00:00+00:00')`, a.id, a.name, a.owner)
	}
	for _, r := range []struct {
		id, apartment    int64
		source, from, to string
	}{
		{100, 10, "manual", "2026-11-05", "2026-11-08"},
		{101, 11, "manual", "2026-10-10", "2026-10-12"},
		{102, 10, "demo", "2026-11-05", "2026-11-08"},
		{200, 20, "manual", "2026-11-05", "2026-11-08"},
	} {
		exec(`INSERT INTO reservation (id, apartment_id, source, uid, date_from, date_to, created_at, updated_at) VALUES ($1, $2, $3, $4, $5, $6, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')`,
			r.id, r.apartment, r.source, fmt.Sprintf("uid-%d", r.id), r.from, r.to)
	}
	guest := func(id, res int64, surname, first, state string, extra string, args ...any) {
		t.Helper()
		sql := `INSERT INTO guest (id, reservation_id, surname, first_name, submit_state, created_at, updated_at` + extra + `) VALUES ($1, $2, $3, $4, $5, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'`
		for i := range args {
			sql += fmt.Sprintf(", $%d", i+6)
		}
		exec(sql+")", append([]any{id, res, surname, first, state}, args...)...)
	}
	// 1001: stay of reservation 100, filed and accepted, German, full facts.
	guest(1001, 100, "Novak", "Jana", "sent",
		", nationality, doc_number, visa_number, birth_date, purpose, signature_png, submitted_at, res_street, res_city, res_country",
		"DEU", "AB123456", "V99887", "01021990", "10", "imported", "2026-11-06T10:00:00", "Hauptstr 1", "Berlin", "deu")
	// 1002: stay of reservation 101 (property 11), not sent.
	guest(1002, 101, "Svoboda", "Petr", "pending", ", nationality, purpose, stay_from", "CZE", "01", "2026-10-10")
	// 1003: stay of the demo reservation: never listed.
	guest(1003, 102, "Demoguest", "Dee", "pending", "")
	// 1004: archived guest of reservation 100.
	guest(1004, 100, "Archivedperson", "Ann", "pending", ", archived_at", "2026-11-09T08:00:00")
	// 1005 and 1006: host 3's guests, live and archived.
	guest(1005, 200, "Foreignlive", "Fay", "pending", "")
	guest(1006, 200, "Foreignarchived", "Fay", "pending", ", archived_at", "2026-11-09T08:00:00")
	// 1007: filed by hand in the UbyPort web application.
	guest(1007, 100, "Handfiled", "Hana", "sent", ", manual_filed_at, manual_reference", "2026-11-07T09:00:00", "REF-1")
	// 1008: rejected and cannot be corrected.
	guest(1008, 100, "Blockedone", "Bob", "blocked", "")
}

// get sends GET target as user (0: signed out) with the language cookie lang;
// as is the workspace an admin previews (0: none).
func get(t *testing.T, pool *pgxpool.Pool, target string, user, as int64, lang string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, target, nil)
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: lang})
	if user != 0 {
		payload := map[string]any{"uid": user, "sv": 1}
		if as != 0 {
			payload["as"] = as
			payload["ast"] = testNow.Unix()
		}
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, testNow)})
	}
	rec := httptest.NewRecorder()
	Handler(pool, testGetenv, func() time.Time { return testNow }).ServeHTTP(rec, req)
	return rec
}

func mustContain(t *testing.T, name, body string, want ...string) {
	t.Helper()
	for _, w := range want {
		if !strings.Contains(body, w) {
			t.Errorf("%s: missing %q", name, w)
		}
	}
}

func mustNotContain(t *testing.T, name, body string, banned ...string) {
	t.Helper()
	for _, b := range banned {
		if strings.Contains(body, b) {
			t.Errorf("%s: must not contain %q", name, b)
		}
	}
}

func TestPeriodPresets(t *testing.T) {
	cases := []struct {
		today time.Time
		want  [3][2]string
	}{
		{time.Date(2026, 11, 17, 0, 0, 0, 0, time.UTC), [3][2]string{{"2026-11-01", "2026-11-30"}, {"2026-10-01", "2026-10-31"}, {"2026-01-01", "2026-12-31"}}},
		{time.Date(2026, 1, 31, 0, 0, 0, 0, time.UTC), [3][2]string{{"2026-01-01", "2026-01-31"}, {"2025-12-01", "2025-12-31"}, {"2026-01-01", "2026-12-31"}}},
		{time.Date(2028, 3, 1, 0, 0, 0, 0, time.UTC), [3][2]string{{"2028-03-01", "2028-03-31"}, {"2028-02-01", "2028-02-29"}, {"2028-01-01", "2028-12-31"}}},
	}
	for _, c := range cases {
		got := periodPresets(c.today)
		for i, k := range []string{"housebook.preset.this_month", "housebook.preset.last_month", "housebook.preset.this_year"} {
			if got[i][0] != k || got[i][1] != c.want[i][0] || got[i][2] != c.want[i][1] {
				t.Errorf("%s preset %d = %v, want %s %v", c.today.Format("2006-01-02"), i, got[i], k, c.want[i])
			}
		}
	}
}

func TestReportedPill(t *testing.T) {
	for in, want := range map[string]string{
		"yes": "ok", "not required (Czech national)": "not_required", "NO - rejected": "rejected",
		"NO - rejected, cannot be corrected": "final", "not yet": "not_sent",
		"yes - filed by hand in UbyPort": "not_sent", "": "not_sent",
	} {
		if got := reportedPill(in); got != want {
			t.Errorf("reportedPill(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestPurposeLabel(t *testing.T) {
	for _, c := range []struct{ code, lang, want string }{
		{"10", "cs", "Turistika"}, {"10", "en", "Tourism"}, {"10", "vi", "Du lịch"}, {"99", "en", "Other"},
		{"zz", "en", "zz"}, {"", "cs", ""},
	} {
		if got := purposeLabel(c.code, c.lang); got != c.want {
			t.Errorf("purposeLabel(%q, %q) = %q, want %q", c.code, c.lang, got, c.want)
		}
	}
}

func TestHousebookPageSignedOut(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	rec := get(t, pool, "/housebook", 0, 0, "en")
	if rec.Code != http.StatusSeeOther && rec.Code != http.StatusFound {
		t.Fatalf("status %d, want a redirect", rec.Code)
	}
	if loc := rec.Header().Get("Location"); !strings.HasPrefix(loc, "/login?next=") {
		t.Errorf("Location %q, want /login?next=...", loc)
	}
}

// TestHousebookPageEnglish reads host 2's page: the stays of properties 10
// and 11 in house-book order, the archived guest and the filter form.
func TestHousebookPageEnglish(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	rec := get(t, pool, "/housebook", 2, 0, "en")
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d", rec.Code)
	}
	body := rec.Body.String()
	if got := rec.Header().Get("Cache-Control"); got != "no-store, private" {
		t.Errorf("Cache-Control %q", got)
	}
	mustContain(t, "en", body,
		`<h1 class="big">House book</h1>`,
		`data-csv-export="/housebook.csv" data-csv-params="apartment="`,
		`data-csv-scope-label="All properties"`,
		`<a class="btn ghost" href="/submissions">`,
		`<option value="10" >`, `<option value="11" >`,
		`Alpha Flat</option>`, `Bravo House</option>`,
		`<strong>Svoboda</strong>`, `<strong>Novak</strong>`, `<strong>Handfiled</strong>`, `<strong>Blockedone</strong>`,
		`<span class="pill p-ok">Reported</span><small>06.11.2026</small>`,
		`<span class="pill p-bad">Rejected, final</span>`,
		`<span class="pill p-n">Not yet sent</span>`,
		`Citizenship:</span> Germany (DEU)`,
		`Document:</span> <span class="mono">AB123456, visa V99887</span>`,
		`Residence abroad:</span> Hauptstr 1, Berlin, Germany (DEU)`,
		`Date of birth:</span> 01.02.1990`,
		`Purpose:</span> Tourism`,
		`<span class="sav">N</span>`,
		`data-href="/guests/1001?return_to=/housebook"`,
		`href="/guests/1001/form.pdf"`,
		`<form method="post" action="/guests/1001/archive"`,
		`<form method="post" action="/guests/1004/unarchive" class="inline">`,
		`<strong>Archivedperson</strong> Ann`,
		`<form id="housebook-pdf-form" method="get" action="/housebook/pdfs.zip">`,
		`Up to 100 forms per download.`,
		`<a class="btn ghost sm" href="/housebook?from=2026-11-01&amp;to=2026-11-30">This month</a>`,
		`<a class="btn ghost sm" href="/housebook?from=2026-10-01&amp;to=2026-10-31">Last month</a>`,
		`<a class="btn ghost sm" href="/housebook?from=2026-01-01&amp;to=2026-12-31">This year</a>`,
	)
	// Owner scoping: host 3's guests, the demo stay and the other host's property never show.
	mustNotContain(t, "en", body, "Foreignlive", "Foreignarchived", "Zulu Villa", "Demoguest", "/guests/1003", "/guests/1005", "/guests/1006")
	// House-book order: stay_from (the guest's, else the stay's), then guest id.
	last := -1
	for _, name := range []string{"<strong>Svoboda</strong>", "<strong>Novak</strong>", "<strong>Handfiled</strong>", "<strong>Blockedone</strong>"} {
		i := strings.Index(body, name)
		if i < last {
			t.Errorf("%s is out of order", name)
		}
		last = i
	}
	// Python shows only the exact "yes" as reported: a guest filed by hand reads "Not yet sent".
	if i := strings.Index(body, `<strong>Handfiled</strong>`); !strings.Contains(body[i:i+700], `<span class="pill p-n">Not yet sent</span>`) {
		t.Errorf("a guest filed by hand must show the not-sent pill, as Python does")
	}
	// Every form that posts carries the CSRF field, so it works without JavaScript.
	page := body[strings.Index(body, `<div class="housebook-page">`):]
	page = page[:strings.Index(page, `</dialog>`)]
	if posts, csrf := strings.Count(page, `method="post"`), strings.Count(page, `name="_csrf"`); posts == 0 || csrf < posts {
		t.Errorf("%d post forms but %d _csrf inputs", posts, csrf)
	}
}

func TestHousebookPageFilters(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	body := get(t, pool, "/housebook?apartment=11&from=2026-10-01&to=2026-10-31", 2, 0, "en").Body.String()
	mustContain(t, "filtered", body,
		`<strong>Svoboda</strong>`, `01.10.2026 – 31.10.2026`,
		`data-csv-params="apartment=11"`, `data-csv-scope-label="Bravo House"`,
		`<option value="11" selected>`,
		`<input type="date" id="housebook-from" name="from" value="2026-10-01" data-range-from>`,
		`<input type="date" id="housebook-until" name="to" value="2026-10-31" data-range-until>`,
		`<a class="btn ghost sm is-on" href="/housebook?apartment=11&amp;from=2026-10-01&amp;to=2026-10-31" aria-current="true">Last month</a>`,
		`<a class="btn ghost sm" href="/housebook?apartment=11&amp;from=2026-11-01&amp;to=2026-11-30">This month</a>`,
	)
	// Property 11 has no archived guest, and the other guests are filtered out.
	mustNotContain(t, "filtered", body, "<strong>Novak</strong>", "Archivedperson", "Handfiled", "Foreign")
	// A date range with no guest shows the empty text, a bad filter value is ignored.
	empty := get(t, pool, "/housebook?from=2030-01-01&apartment=abc&to=nonsense", 2, 0, "en").Body.String()
	mustContain(t, "empty", empty, `<div class="panel empty">`, `<option value="">`)
	mustNotContain(t, "empty", empty, "<strong>Novak</strong>", "<strong>Svoboda</strong>")
	mustContain(t, "empty", empty, `value="2030-01-01" data-range-from`, `name="to" value="" data-range-until`)
}

// TestHousebookPageOtherHost: host 3 sees only host 3's rows.
func TestHousebookPageOtherHost(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	body := get(t, pool, "/housebook", 3, 0, "en").Body.String()
	mustContain(t, "host 3", body, `<strong>Foreignlive</strong>`, `<strong>Foreignarchived</strong>`, `Zulu Villa`)
	mustNotContain(t, "host 3", body, "Novak", "Svoboda", "Archivedperson", "Alpha Flat", "Bravo House")
	// A property of host 2 asked for by id returns no row for host 3.
	other := get(t, pool, "/housebook?apartment=10", 3, 0, "en").Body.String()
	mustNotContain(t, "host 3 asks for 10", other, "Novak", "Foreignlive", "Archivedperson")
}

// TestHousebookPageAdminPreview: an admin who previews host 2's workspace sees host 2's rows.
func TestHousebookPageAdminPreview(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	body := get(t, pool, "/housebook", 1, 2, "en").Body.String()
	mustContain(t, "admin", body, `<strong>Novak</strong>`, `AB123456, visa V99887`)
	mustNotContain(t, "admin", body, "Foreignlive")
}

func TestHousebookPageLanguages(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	cs := get(t, pool, "/housebook", 2, 0, "cs").Body.String()
	mustContain(t, "cs", cs, `<h1 class="big">Domovní kniha</h1>`, `Státní občanství:</span> Německo (DEU)`,
		`Účel:</span> Turistika`, `<a class="btn ghost sm" href="/housebook?from=2026-11-01&amp;to=2026-11-30">Tento měsíc</a>`)
	vi := get(t, pool, "/housebook", 2, 0, "vi").Body.String()
	mustContain(t, "vi", vi, `<h1 class="big">Sổ khách lưu trú</h1>`, `Mục đích:</span> Du lịch`,
		`<a class="btn ghost sm" href="/housebook?from=2026-11-01&amp;to=2026-11-30">Tháng này</a>`)
}
