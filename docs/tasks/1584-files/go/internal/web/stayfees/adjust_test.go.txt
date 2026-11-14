package stayfees

// Brief 1584 route tests on PostgreSQL. The fixtures are the made-up rows of
// testdata/actions_golden.json (seed), so they are the same properties and
// accounts as TestActionsMatchPython. The seeded adjustments hold a
// placeholder reason that no key decrypts, so these tests clear them first.

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

type adjustEnv struct {
	t    *testing.T
	pool *pgxpool.Pool
	mux  *http.ServeMux
	at   time.Time
	keys *secure.MultiFernet
}

func newAdjustEnv(t *testing.T) *adjustEnv {
	t.Helper()
	g := loadGolden(t)
	pool := testPool(t)
	seed(t, pool, g)
	if _, err := pool.Exec(context.Background(), `DELETE FROM stay_fee_adjustment`); err != nil {
		t.Fatal(err)
	}
	at, err := time.Parse(time.RFC3339, g.Now)
	if err != nil {
		t.Fatal(err)
	}
	getenv := goldenEnv()
	keys, err := secure.LoadDataKeys(getenv)
	if err != nil {
		t.Fatal(err)
	}
	mux := http.NewServeMux()
	for _, r := range AdjustRoutes(pool, getenv, func() time.Time { return at }) {
		mux.Handle(r.Pattern, r.Handler)
	}
	return &adjustEnv{t: t, pool: pool, mux: mux, at: at, keys: keys}
}

// post sends a signed-in form POST with a valid CSRF token.
func (e *adjustEnv) post(who, path string, form map[string]string) *httptest.ResponseRecorder {
	e.t.Helper()
	c := goldenCase{Method: http.MethodPost, Path: path, Form: form}
	if who != "" {
		c.Who = &who
	}
	rec := httptest.NewRecorder()
	e.mux.ServeHTTP(rec, request(e.t, c, e.at))
	return rec
}

func (e *adjustEnv) count(table string) int {
	e.t.Helper()
	var n int
	if err := e.pool.QueryRow(context.Background(), `SELECT count(*) FROM `+table).Scan(&n); err != nil {
		e.t.Fatal(err)
	}
	return n
}

// liable is guest_liable_nights of the live period (what the handler compares with).
func (e *adjustEnv) liable(aptID int64, month time.Time, o stayfee.Opts) int {
	e.t.Helper()
	ctx := context.Background()
	ap, err := stayfee.LoadApartment(ctx, e.pool, aptID)
	if err != nil {
		e.t.Fatal(err)
	}
	o.LiveOnly = true
	u := e.at.UTC()
	o.ScheduleToday = stayfee.Day(u.Year(), u.Month(), u.Day())
	p, err := stayfee.PropertyPeriod(ctx, e.pool, stayfee.FernetDecrypter(e.keys), ap, month, o)
	if err != nil || p == nil {
		e.t.Fatalf("period: %v %v", p, err)
	}
	return p.GuestLiableNights
}

// location returns the redirect target, failing unless it is a 303.
func (e *adjustEnv) location(rec *httptest.ResponseRecorder) *url.URL {
	e.t.Helper()
	if rec.Code != http.StatusSeeOther {
		e.t.Fatalf("status %d, want 303 (%s)", rec.Code, rec.Body.String())
	}
	u, err := url.Parse(rec.Header().Get("Location"))
	if err != nil {
		e.t.Fatal(err)
	}
	return u
}

// refused checks a 303 to wantPath carrying the err text of key and no msg.
func (e *adjustEnv) refused(rec *httptest.ResponseRecorder, wantPath, lang, key string, fromMain bool) {
	e.t.Helper()
	u := e.location(rec)
	text := adjustCatalog.T(lang, key, nil)
	if fromMain {
		text = catalog.T(lang, key, nil)
	}
	got := u.Path
	if q := u.Query().Get("month"); q != "" {
		got += "?month=" + q
	}
	if c := u.Query().Get("correct"); c != "" {
		got += "&correct=" + c
	}
	if got != wantPath {
		e.t.Errorf("redirect %q, want %q", got, wantPath)
	}
	if u.Query().Get("err") != text || text == key {
		e.t.Errorf("err %q, want %q", u.Query().Get("err"), text)
	}
	if u.Query().Get("msg") != "" {
		e.t.Errorf("a refusal carries a msg: %q", u.RawQuery)
	}
}

type adjRow struct {
	id                   int64
	apartment            int64
	period, dir, mode    string
	people, nights, days *int
	reasonEnc, created   string
	createdBy            int64
}

func (e *adjustEnv) rows() []adjRow {
	e.t.Helper()
	rs, err := e.pool.Query(context.Background(),
		`SELECT id, apartment_id, period_key, direction, mode, people_count, nights, bed_days, reason_enc, created_at, created_by
		FROM stay_fee_adjustment ORDER BY id`)
	if err != nil {
		e.t.Fatal(err)
	}
	defer rs.Close()
	var out []adjRow
	for rs.Next() {
		var r adjRow
		var days int
		if err := rs.Scan(&r.id, &r.apartment, &r.period, &r.dir, &r.mode, &r.people, &r.nights, &days, &r.reasonEnc, &r.created, &r.createdBy); err != nil {
			e.t.Fatal(err)
		}
		r.days = &days
		out = append(out, r)
	}
	return out
}

func (e *adjustEnv) reason(r adjRow) string {
	e.t.Helper()
	plain, err := e.keys.Decrypt(r.reasonEnc, 0, e.at)
	if err != nil {
		e.t.Fatal("stored reason does not decrypt")
	}
	return string(plain)
}

type auditRow struct{ actor, action, detail string }

func (e *adjustEnv) audits() []auditRow {
	e.t.Helper()
	rs, err := e.pool.Query(context.Background(), `SELECT actor, action, detail FROM audit ORDER BY id`)
	if err != nil {
		e.t.Fatal(err)
	}
	defer rs.Close()
	var out []auditRow
	for rs.Next() {
		var a auditRow
		if err := rs.Scan(&a.actor, &a.action, &a.detail); err != nil {
			e.t.Fatal(err)
		}
		out = append(out, a)
	}
	return out
}

func intIs(p *int, want int) bool { return p != nil && *p == want }

func TestAdjustmentAddSaves(t *testing.T) {
	e := newAdjustEnv(t)
	base := map[string]string{"month": "2026-11", "direction": "add", "mode": "bed_days", "bed_days": "5", "reason": "  Oprava hostů  "}
	rec := e.post("host1", "/stay-fees/12/adjustment", base)
	u := e.location(rec)
	if u.Path != "/stay-fees/12" || u.Query().Get("month") != "2026-11" || u.Query().Get("msg") != catalog.T("en", "flash.stay_fees.saved", nil) || u.Query().Get("err") != "" {
		t.Fatalf("redirect %q", u.String())
	}
	rows := e.rows()
	if len(rows) != 1 {
		t.Fatalf("%d adjustment rows, want 1", len(rows))
	}
	r := rows[0]
	if r.apartment != 12 || r.period != "2026-11" || r.dir != "add" || r.mode != "bed_days" || !intIs(r.days, 5) ||
		r.people != nil || r.nights != nil || r.createdBy != 1 || r.created != "2026-11-13T10:00:00+00:00" {
		t.Errorf("row %+v", r)
	}
	if got := e.reason(r); got != "Oprava hostů" {
		t.Errorf("reason %q, want it stripped", got)
	}
	want := auditRow{"host1@example.test", "stay_fee_adjustment", "apartment_id=12 period=2026-11 direction=add days=5"}
	if a := e.audits(); len(a) != 1 || a[0] != want {
		t.Errorf("audit %v, want [%v]", a, want)
	}

	// People mode stores the counts; bed-days is people x nights.
	rec = e.post("host1", "/stay-fees/12/adjustment", map[string]string{
		"month": "2026-11", "direction": "add", "mode": "people", "people": "2", "nights": "3",
		"reason": strings.Repeat("x", 250)})
	e.location(rec)
	rows = e.rows()
	if len(rows) != 2 {
		t.Fatalf("%d rows, want 2", len(rows))
	}
	r = rows[1]
	if r.mode != "people" || !intIs(r.people, 2) || !intIs(r.nights, 3) || !intIs(r.days, 6) {
		t.Errorf("people row %+v", r)
	}
	if got := e.reason(r); len([]rune(got)) != 200 {
		t.Errorf("reason has %d characters, want 200", len([]rune(got)))
	}

	// Python's int() takes "1_0" and "+7"; both are accepted.
	for text, days := range map[string]int{"1_0": 10, "+7": 7, "9999": 9999} {
		b := map[string]string{"month": "2026-11", "direction": "add", "mode": "bed_days", "bed_days": text, "reason": "abc"}
		e.location(e.post("host1", "/stay-fees/12/adjustment", b))
		rows = e.rows()
		if last := rows[len(rows)-1]; !intIs(last.days, days) {
			t.Errorf("bed_days %q stored %v, want %d", text, last.days, days)
		}
	}
	if n := len(e.audits()); n != 5 {
		t.Errorf("%d audit rows, want 5", n)
	}

	// An admin inside the workspace: the audit row names the admin as impersonator.
	e.location(e.post("admin_imp", "/stay-fees/12/adjustment", base))
	var impersonator, owner, actor int64
	if err := e.pool.QueryRow(context.Background(),
		`SELECT impersonator_user_id, owner_user_id, actor_user_id FROM audit ORDER BY id DESC LIMIT 1`).Scan(&impersonator, &owner, &actor); err != nil {
		t.Fatal(err)
	}
	if impersonator != 3 || owner != 1 || actor != 3 {
		t.Errorf("impersonation audit %d %d %d", impersonator, owner, actor)
	}
	if last := e.rows(); last[len(last)-1].createdBy != 1 {
		t.Error("created_by must be the workspace owner")
	}
}

func TestAdjustmentAddNoMonthUsesCurrentMonth(t *testing.T) {
	e := newAdjustEnv(t)
	u := e.location(e.post("host1", "/stay-fees/12/adjustment",
		map[string]string{"direction": "add", "mode": "bed_days", "bed_days": "2", "reason": "abc"}))
	if u.Query().Get("month") != "2026-11" {
		t.Errorf("redirect %q, want month 2026-11", u.String())
	}
	if rows := e.rows(); len(rows) != 1 || rows[0].period != "2026-11" {
		t.Errorf("rows %+v", rows)
	}
}

func TestAdjustmentAddInvalid(t *testing.T) {
	e := newAdjustEnv(t)
	ok := func() map[string]string {
		return map[string]string{"month": "2026-11", "direction": "add", "mode": "bed_days", "bed_days": "3", "reason": "abc"}
	}
	for name, edit := range map[string]func(map[string]string){
		"bad direction":      func(f map[string]string) { f["direction"] = "up" },
		"no direction":       func(f map[string]string) { delete(f, "direction") },
		"bad mode":           func(f map[string]string) { f["mode"] = "nights" },
		"short reason":       func(f map[string]string) { f["reason"] = " ab " },
		"no reason":          func(f map[string]string) { delete(f, "reason") },
		"bed_days zero":      func(f map[string]string) { f["bed_days"] = "0" },
		"bed_days empty":     func(f map[string]string) { f["bed_days"] = "" },
		"bed_days too big":   func(f map[string]string) { f["bed_days"] = "10000" },
		"bed_days negative":  func(f map[string]string) { f["bed_days"] = "-3" },
		"bed_days text":      func(f map[string]string) { f["bed_days"] = "abc" },
		"bed_days decimal":   func(f map[string]string) { f["bed_days"] = "1.5" },
		"bed_days overflow":  func(f map[string]string) { f["bed_days"] = "99999999999999999999" },
		"bed_days underline": func(f map[string]string) { f["bed_days"] = "1__0" },
		"people zero":        func(f map[string]string) { f["mode"], f["people"], f["nights"] = "people", "0", "2" },
		"people 100":         func(f map[string]string) { f["mode"], f["people"], f["nights"] = "people", "100", "2" },
		"people text":        func(f map[string]string) { f["mode"], f["people"], f["nights"] = "people", "x", "2" },
		"people missing":     func(f map[string]string) { f["mode"], f["nights"] = "people", "2" },
		"nights zero":        func(f map[string]string) { f["mode"], f["people"], f["nights"] = "people", "2", "0" },
		"nights 367":         func(f map[string]string) { f["mode"], f["people"], f["nights"] = "people", "2", "367" },
		"nights missing":     func(f map[string]string) { f["mode"], f["people"] = "people", "2" },
	} {
		f := ok()
		edit(f)
		e.refused(e.post("host1", "/stay-fees/12/adjustment", f), "/stay-fees/12?month=2026-11", "en", "flash.stay_fees.adjust_invalid", false)
		if n := e.count("stay_fee_adjustment"); n != 0 {
			t.Fatalf("%s wrote %d adjustment rows", name, n)
		}
		if n := e.count("audit"); n != 0 {
			t.Fatalf("%s wrote %d audit rows", name, n)
		}
	}
	// Edge values that are valid.
	for _, f := range []map[string]string{
		{"mode": "people", "people": "99", "nights": "366", "bed_days": "0"},
		{"mode": "people", "people": "1", "nights": "1"},
	} {
		f["month"], f["direction"], f["reason"] = "2026-11", "add", "abc"
		e.location(e.post("host1", "/stay-fees/12/adjustment", f))
	}
	if n := e.count("stay_fee_adjustment"); n != 2 {
		t.Errorf("%d rows after the edge values, want 2", n)
	}

	// The Czech catalog is used when the host reads Czech.
	c := goldenCase{Method: http.MethodPost, Path: "/stay-fees/12/adjustment", Who: &[]string{"host1"}[0], Lang: &[]string{"cs"}[0],
		Form: map[string]string{"month": "2026-11", "direction": "x", "mode": "bed_days", "reason": "abc"}}
	rec := httptest.NewRecorder()
	e.mux.ServeHTTP(rec, request(t, c, e.at))
	e.refused(rec, "/stay-fees/12?month=2026-11", "cs", "flash.stay_fees.adjust_invalid", false)
}

func TestAdjustmentAddNegativeAndFrozen(t *testing.T) {
	e := newAdjustEnv(t)
	form := func(dir string, days string) map[string]string {
		return map[string]string{"month": "2026-11", "direction": dir, "mode": "bed_days", "bed_days": days, "reason": "abc"}
	}
	nov := stayfee.Day(2026, time.November, 1)
	if n := e.liable(12, nov, stayfee.Opts{}); n != 0 {
		t.Fatalf("fixture changed: %d liable nights in 2026-11, want 0", n)
	}
	// Nothing to remove from.
	e.refused(e.post("host1", "/stay-fees/12/adjustment", form("remove", "1")), "/stay-fees/12?month=2026-11", "en", "flash.stay_fees.adjust_negative", false)
	e.location(e.post("host1", "/stay-fees/12/adjustment", form("add", "4")))
	// Removing all of it is allowed (total zero); one more is not.
	e.location(e.post("host1", "/stay-fees/12/adjustment", form("remove", "4")))
	e.refused(e.post("host1", "/stay-fees/12/adjustment", form("remove", "1")), "/stay-fees/12?month=2026-11", "en", "flash.stay_fees.adjust_negative", false)
	if n := e.count("stay_fee_adjustment"); n != 2 {
		t.Errorf("%d rows, want 2", n)
	}
	// A reversed adjustment no longer counts.
	if _, err := e.pool.Exec(context.Background(), `UPDATE stay_fee_adjustment SET reversed_at = '2026-11-13T10:00:00+00:00', reversed_by = 1`); err != nil {
		t.Fatal(err)
	}
	e.refused(e.post("host1", "/stay-fees/12/adjustment", form("remove", "1")), "/stay-fees/12?month=2026-11", "en", "flash.stay_fees.adjust_negative", false)

	// A sealed period refuses a plain adjustment.
	before := e.count("stay_fee_adjustment")
	f := form("add", "1")
	f["month"] = "2026-10"
	e.refused(e.post("host1", "/stay-fees/12/adjustment", f), "/stay-fees/12?month=2026-10", "en", "flash.stay_fees.adjust_frozen", false)
	if e.count("stay_fee_adjustment") != before {
		t.Error("a frozen period took an adjustment")
	}
}

func TestAdjustmentAddCorrection(t *testing.T) {
	e := newAdjustEnv(t)
	form := func(month, dir, days string) map[string]string {
		return map[string]string{"month": month, "correct": "1", "direction": dir, "mode": "bed_days", "bed_days": days, "reason": "oprava"}
	}
	// No sealed filing covers 2026-11 on apartment 12.
	e.refused(e.post("host1", "/stay-fees/12/adjustment", form("2026-11", "add", "1")), "/stay-fees/12?month=2026-11", "en", "flash.stay_fees.report_blocked", true)

	// Sealed monthly period 2026-10: the row keeps the sealed key and the back link says correct=1.
	n := e.liable(12, stayfee.Day(2026, time.October, 1), stayfee.Opts{Cadence: "monthly", Rate: &[]int{50}[0]})
	u := e.location(e.post("host1", "/stay-fees/12/adjustment", form("2026-10", "add", "2")))
	if u.Path != "/stay-fees/12" || u.Query().Get("month") != "2026-10" || u.Query().Get("correct") != "1" || u.Query().Get("msg") == "" {
		t.Errorf("redirect %q", u.String())
	}
	if rows := e.rows(); len(rows) != 1 || rows[0].period != "2026-10" || rows[0].apartment != 12 {
		t.Errorf("rows %+v", rows)
	}
	// Removing more than guests plus corrections is refused, with correct=1 kept.
	e.refused(e.post("host1", "/stay-fees/12/adjustment", form("2026-10", "remove", strconv.Itoa(n+3))),
		"/stay-fees/12?month=2026-10&correct=1", "en", "flash.stay_fees.adjust_negative", false)
	e.location(e.post("host1", "/stay-fees/12/adjustment", form("2026-10", "remove", strconv.Itoa(n+2))))
	if got := len(e.rows()); got != 2 {
		t.Errorf("%d rows, want 2", got)
	}

	// A quarterly seal (Q3 on apartment 17): any month inside it files under the sealed quarter key.
	e.location(e.post("host1", "/stay-fees/17/adjustment", form("2026-08", "add", "1")))
	rows := e.rows()
	if last := rows[len(rows)-1]; last.apartment != 17 || last.period != "2026-Q3" {
		t.Errorf("quarterly correction row %+v, want period 2026-Q3", last)
	}
	if a := e.audits(); a[len(a)-1].detail != "apartment_id=17 period=2026-Q3 direction=add days=1" {
		t.Errorf("audit %v", a[len(a)-1])
	}
}

func TestAdjustmentAddRefusals(t *testing.T) {
	e := newAdjustEnv(t)
	good := map[string]string{"month": "2026-11", "direction": "add", "mode": "bed_days", "bed_days": "3", "reason": "abc"}
	noApartment := "/stay-fees"

	// Foreign, missing, out of range and rate-less properties.
	for _, id := range []string{"20", "999", "99999999999999999999", "11", "13"} {
		rec := e.post("host1", "/stay-fees/"+id+"/adjustment", good)
		u := e.location(rec)
		if u.Path != noApartment || u.Query().Get("err") != catalog.T("en", "flash.error.no_such_apartment", nil) {
			t.Errorf("apartment %s: %q", id, u.String())
		}
	}
	// A path id that is not an integer is a 422 before anything else.
	if rec := e.post("host1", "/stay-fees/1x/adjustment", good); rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("text id: status %d, want 422", rec.Code)
	}
	// Signed out: the login page, nothing written.
	rec := e.post("", "/stay-fees/12/adjustment", good)
	if u := e.location(rec); u.Path != "/login" || u.Query().Get("next") != "/stay-fees/12/adjustment" {
		t.Errorf("signed out: %q", u.String())
	}
	// The other host cannot reach property 12.
	if u := e.location(e.post("host2", "/stay-fees/12/adjustment", good)); u.Path != noApartment {
		t.Errorf("other host: %q", u.String())
	}
	// A missing or wrong CSRF token is a 403.
	req := httptest.NewRequest(http.MethodPost, "/stay-fees/12/adjustment", strings.NewReader("month=2026-11&direction=add&mode=bed_days&bed_days=3&reason=abc"))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Origin", "https://evil.example")
	req.AddCookie(&http.Cookie{Name: session.CookieName, Value: sessionFor("host1", e.at)})
	bad := httptest.NewRecorder()
	e.mux.ServeHTTP(bad, req)
	if bad.Code != http.StatusForbidden {
		t.Errorf("bad CSRF: status %d, want 403", bad.Code)
	}
	if e.count("stay_fee_adjustment") != 0 || e.count("audit") != 0 {
		t.Error("a refused request wrote a row")
	}
	// GET is not a route of this brief.
	get := httptest.NewRecorder()
	e.mux.ServeHTTP(get, httptest.NewRequest(http.MethodGet, "/stay-fees/12/adjustment", nil))
	if get.Code != http.StatusMethodNotAllowed {
		t.Errorf("GET: status %d, want 405", get.Code)
	}

	// Python checks only the rate, not archived_at: an archived property that
	// still has a rate takes the adjustment.
	e.location(e.post("host1", "/stay-fees/16/adjustment", good))
	if rows := e.rows(); len(rows) != 1 || rows[0].apartment != 16 {
		t.Errorf("archived property rows %+v", rows)
	}
}
