package stayfees

// Route tests of the stay fee list page (brief 1581; the fixtures here also serve brief 1582) on PostgreSQL. The
// fixtures are made up (@example.test, test keys). There is no Python golden
// for these pages (the Python app cannot be started where this was written),
// so the tests check the texts, forms and links the Jinja templates produce.

import (
	"context"
	"fmt"
	"html"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// pageNow is 11:00 in Prague on 2026-11-13: the default month is November,
// October is over and the third quarter is sealed.
var pageNow = time.Date(2026, 11, 13, 10, 0, 0, 0, time.UTC)

type pageEnv struct {
	t    *testing.T
	pool *pgxpool.Pool
	mux  *http.ServeMux
	keys *secure.MultiFernet
}

func (e *pageEnv) exec(sql string, args ...any) {
	e.t.Helper()
	if _, err := e.pool.Exec(context.Background(), sql, args...); err != nil {
		e.t.Fatalf("%v\n%s", err, sql)
	}
}

func (e *pageEnv) enc(plain string) string {
	e.t.Helper()
	token, err := e.keys.Encrypt([]byte(plain))
	if err != nil {
		e.t.Fatal(err)
	}
	return token
}

const pageStamp = "2026-09-01T00:00:00+00:00"

func (e *pageEnv) user(id int, name, role string) {
	e.exec(`INSERT INTO user_account (id, username, password_hash, role, created_at) VALUES ($1, $2, 'x', $3, $4)`,
		id, name, role, pageStamp)
	for _, doc := range []string{"terms", "privacy", "dpa"} {
		e.exec(`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES ($1, $2, $3, '2026-01-01', 'clickwrap')`,
			id, doc, acceptedVersion)
	}
}

type pgFeeApt struct {
	id, owner, entity           int
	name, obec                  string
	rate                        int
	cadence, vs, authority, box string
	account, iban               string
}

func (e *pageEnv) apartment(a pgFeeApt) {
	var entity any
	if a.entity != 0 {
		entity = a.entity
	}
	if a.cadence == "" {
		a.cadence = "monthly"
	}
	e.exec(`INSERT INTO apartment (id, owner_user_id, internal_name, created_at, addr_obec, stay_fee_rate_czk, stay_fee_cadence,
		stay_fee_vs, stay_fee_authority_name, stay_fee_authority_databox, stay_fee_council_account, stay_fee_council_iban,
		stay_fee_scope_rule, legal_entity_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7, NULLIF($8, ''), NULLIF($9, ''), NULLIF($10, ''), NULLIF($11, ''), NULLIF($12, ''), NULL, $13)`,
		a.id, a.owner, a.name, pageStamp, a.obec, a.rate, a.cadence, a.vs, a.authority, a.box, a.account, a.iban, entity)
}

type pgFeeGuest struct {
	id, res int
	first   string
	surname string
	birth   string
	nat     string
	country string
	city    string
	from    string
	to      string
	sig     string
	dec     string
}

func (e *pageEnv) reservation(id, apartmentID int, from, to string) {
	e.exec(`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, created_at, updated_at) VALUES ($1, $2, $3, $4, $5, $6, $6)`,
		id, apartmentID, fmt.Sprintf("uid-%d", id), from, to, pageStamp)
}

func (e *pageEnv) guest(g pgFeeGuest) {
	e.exec(`INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality,
		res_country, res_city, stay_from, stay_to, signature_png, fee_host_decision)
		VALUES ($1, $2, $3, $3, $4, $5, $6, $7, $8, $9, NULLIF($10, ''), NULLIF($11, ''), $12, NULLIF($13, ''))`,
		g.id, g.res, pageStamp, g.first, g.surname, g.birth, g.nat, g.country, g.city, g.from, g.to, g.sig, g.dec)
}

func (e *pageEnv) filing(id, apartmentID int, key, cadence string, total int, payload string, paid bool) {
	var paidAt any
	if paid {
		paidAt = "2026-10-05T08:00:00+00:00"
	}
	var enc any
	if payload != "" {
		enc = e.enc(payload)
	}
	e.exec(`INSERT INTO stay_fee_filing (id, apartment_id, period_key, version, cadence, rate_czk, liable_days, exempt_days,
		total_due_czk, total_collected_czk, payload_enc, created_at, paid_at)
		VALUES ($1, $2, $3, 1, $4, 50, $5, 0, $6, $6, $7, $8, $9)`,
		id, apartmentID, key, cadence, total/50, total, enc, pageStamp, paidAt)
}

// newPageEnv seeds two hosts, an admin, a host with nothing set up and the
// properties the tests read (see the comments).
func newPageEnv(t *testing.T) *pageEnv {
	t.Helper()
	pool := testPool(t)
	getenv := goldenEnv()
	keys, err := secure.LoadDataKeys(getenv)
	if err != nil {
		t.Fatal(err)
	}
	e := &pageEnv{t: t, pool: pool, keys: keys}
	e.mux = http.NewServeMux()
	for _, r := range PageRoutes(pool, getenv, func() time.Time { return pageNow }) {
		e.mux.Handle(r.Pattern, r.Handler)
	}
	e.user(1, "host1@example.test", "host")
	e.user(2, "host2@example.test", "host")
	e.user(3, "admin@example.test", "admin")
	e.user(4, "host4@example.test", "host")
	e.exec(`INSERT INTO legal_entity (id, name, ico, created_at, owner_user_id) VALUES (101, 'Provozovatel Test s.r.o.', ' 12345678 ', $1, 1)`, pageStamp)
	e.exec(`INSERT INTO legal_entity (id, name, created_at, owner_user_id) VALUES (102, 'Druha Firma', $1, 1)`, pageStamp)
	// 12: ready in October; 15: ready in October, sealed and paid in September;
	// 17: quarterly, sealed for Q3, still running in Q4; 11 and 14: no fee set up
	// (11 can copy from 12: same town); 18: fee on but nothing else; 20: another host.
	e.apartment(pgFeeApt{id: 12, owner: 1, entity: 101, name: "Byt B", obec: "Praha 3", rate: 50, vs: "12", authority: "Authority 12", box: "box12",
		account: "123456/0800", iban: "CZ6508000000192000145399"})
	e.apartment(pgFeeApt{id: 15, owner: 1, entity: 101, name: "Byt E", obec: "Kladno", rate: 50, vs: "15", authority: "Authority 15", box: "box15",
		account: "19-2000145399/0800", iban: "CZ6508000000192000145399"})
	e.apartment(pgFeeApt{id: 17, owner: 1, entity: 101, name: "Byt Q", obec: "Kladno", rate: 50, cadence: "quarterly", vs: "17", authority: "Authority 17",
		account: "123456/0800", iban: "CZ6508000000192000145399"})
	e.apartment(pgFeeApt{id: 11, owner: 1, name: "Byt A", obec: "praha 3"})
	e.apartment(pgFeeApt{id: 14, owner: 1, name: "Byt D", obec: "Brno"})
	e.apartment(pgFeeApt{id: 18, owner: 1, name: "Byt F", obec: "Plzen", rate: 50})
	e.apartment(pgFeeApt{id: 20, owner: 2, name: "Foreign", obec: "Praha 3", rate: 50, vs: "20", authority: "Authority 20"})
	e.apartment(pgFeeApt{id: 30, owner: 4, name: "Only Unset", obec: "Ostrava"})

	// Byt B, October: a foreign adult, an auto minor, a Czech resident of the
	// town with a host decision (the local hint), one without (auto resident).
	e.reservation(1, 12, "2026-10-01", "2026-10-05")
	e.guest(pgFeeGuest{id: 1, res: 1, first: "Jan", surname: "Novak", birth: "01011980", nat: "DEU", country: "DEU", city: "Berlin", sig: "imported"})
	e.guest(pgFeeGuest{id: 2, res: 1, first: "Kid", surname: "Novak", birth: "01012015", nat: "DEU", country: "DEU", city: "Berlin", sig: "imported"})
	e.guest(pgFeeGuest{id: 3, res: 1, first: "Petr", surname: "Dvorak", birth: "02022000", nat: "CZE", country: "CZE", city: "PRAHA 3", sig: "imported", dec: "charge"})
	e.guest(pgFeeGuest{id: 4, res: 1, first: "Obec", surname: "Local", birth: "03032000", nat: "CZE", country: "CZE", city: "Praha 3", sig: "imported"})
	// Byt F: exactly 60 nights (the scope ruling is missing) and no signature.
	e.reservation(2, 18, "2026-08-15", "2026-10-14")
	e.guest(pgFeeGuest{id: 5, res: 2, first: "Long", surname: "Stay", birth: "01011980", nat: "DEU", country: "DEU", city: "Berlin"})
	// Byt E, September: the sealed line's guest.
	e.reservation(501, 15, "2026-09-01", "2026-09-11")
	e.guest(pgFeeGuest{id: 9001, res: 501, first: "Eva", surname: "Frozen", birth: "05051975", nat: "AUT", country: "AUT", city: "Wien", sig: "imported"})

	e.filing(1, 15, "2026-09", "monthly", 500, `{"lines":[{"guest_id":9001,"stay_from":"2026-09-01","stay_to":"2026-09-11","nights":10,
		"liable_nights":10,"exempt_nights":0,"status":"liable","auto_minor":false,"decision":null,"reason":"","threshold_nights":false,
		"amount_czk":500,"rate_nights":[[50,10]],"auto_obec_resident":false,"reservation_id":501,"name":"Eva Frozen","restricted":false,
		"res_country":"AUT","res_city":"Wien"}],"rate_segments":[[50,10]]}`, true)
	e.filing(2, 17, "2026-Q3", "quarterly", 500, "", false)
	// Byt B: an open correction and one a filing took.
	e.filing(3, 12, "2026-08", "monthly", 500, "", false)
	e.exec(`INSERT INTO stay_fee_adjustment (id, apartment_id, period_key, direction, mode, bed_days, reason_enc, created_by, created_at, filing_id)
		VALUES (1, 12, '2026-10', 'add', 'bed_days', 3, $1, 1, $2, NULL), (2, 12, '2026-10', 'remove', 'bed_days', 1, $3, 1, $2, 3)`,
		e.enc("sample reason"), pageStamp, e.enc("sealed reason"))
	return e
}

func pageSession(uid int, at time.Time) string {
	return session.Sign(goldenSecret, map[string]any{"sv": 1, "iat": at.Unix(), "uid": uid}, at)
}

func (e *pageEnv) get(uid int, target string) *httptest.ResponseRecorder {
	e.t.Helper()
	req := httptest.NewRequest(http.MethodGet, target, nil)
	if uid != 0 {
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: pageSession(uid, pageNow)})
	}
	rec := httptest.NewRecorder()
	e.mux.ServeHTTP(rec, req)
	return rec
}

// text is a catalog text in English as it appears in the HTML.
func pgText(key string, kv ...any) string { return html.EscapeString(pageT("en", key, kv...)) }

func pgHas(t *testing.T, name, body string, want ...string) {
	t.Helper()
	for _, w := range want {
		if !strings.Contains(body, w) {
			t.Errorf("%s: body lacks %q", name, w)
		}
	}
}

func pgLacks(t *testing.T, name, body string, bad ...string) {
	t.Helper()
	for _, w := range bad {
		if strings.Contains(body, w) {
			t.Errorf("%s: body has %q", name, w)
		}
	}
}

func pgOk(t *testing.T, name string, rec *httptest.ResponseRecorder) string {
	t.Helper()
	if rec.Code != http.StatusOK {
		t.Fatalf("%s: status %d: %s", name, rec.Code, rec.Body.String())
	}
	if strings.Contains(rec.Body.String(), "ZgotmplZ") {
		t.Errorf("%s: html/template refused a value (ZgotmplZ)", name)
	}
	return rec.Body.String()
}

func TestPageListPage(t *testing.T) {
	e := newPageEnv(t)

	// October: 12 and 15 are ready, 17 is running, 18 has blockers, 11 can copy from 12.
	body := pgOk(t, "october", e.get(1, "/stay-fees?month=2026-10&lang=en"))
	pgHas(t, "october", body,
		pgText("stay_fees.title"),
		`id="fee-pay-12"`, `id="fee-pay-15"`, `id="fee-pay-17"`, `id="fee-pay-18"`,
		`data-fee-step="1"`,
		`action="/stay-fees/12/finalize"`, `name="return_to" value="/stay-fees?month=2026-10"`,
		// two ready properties: the bulk form with both ids
		`action="/stay-fees/confirm-ready"`, `name="apartment_id" value="12"`, `name="apartment_id" value="15"`,
		pgText("stay_fees.bulk.confirm", "count", 2),
		// waiting (the quarter is running) and blocked
		pgText("stay_fees.issue.period_running"), pgText("stay_fees.pay.fix_first"),
		pgText("stay_fees.issue.no_vs"), pgText("stay_fees.issue.no_authority"), pgText("stay_fees.issue.no_payer"),
		// the copy card of the unset 11 and the setup links of 11 and 14
		`id="fee-copy-11"`, `action="/stay-fees/11/copy-setup"`, `name="source_id" value="12"`,
		pgText("stay_fees.copy.title", "name", "Byt B"),
		`href="/apartments/14?view=settings&amp;section=reporting&amp;return_to=%2Fstay-fees%3Fmonth%3D2026-10#stay-fee-settings"`,
		pgText("stay_fees.status.not_setup"), pgText("stay_fees.setup.action"),
		// the compact month filter: the month, the way back and a next month
		`value="2026-10"`, `data-filter-compact`, `data-month-optional="false"`, `data-max-month="2026-11"`,
		`id="filter-apartment"`, `id="filter-status"`,
		// the head: tabs of the invoices section, the how-to, the e-mail line
		`href="/invoices"`, `href="/entities`, pgText("stay_fees.list.email_on"),
		`href="/stay-fees/12?month=2026-10"`, pgText("stay_fees.col.liable"),
	)
	pgLacks(t, "october", body, "Foreign", "Only Unset", `data-fee-step="2"`, `data-fee-step="3"`, "fee-periods-unset")
	// Byt B's four guests: three nights each are not counted twice (liable 8, exempt 4 or the like); the row shows the rate.
	pgHas(t, "october rate", body, pgText("stay_fees.rate_line", "rate", 50))

	// September: 15 is sealed and paid (step 3), 17's quarter is sealed (step 2, QR), two saved: the zip link.
	body = pgOk(t, "september", e.get(1, "/stay-fees?month=2026-09&lang=en"))
	pgHas(t, "september", body,
		`id="fee-pay-15" aria-labelledby="fee-pay-h-15" data-fee-step="3"`, pgText("stay_fees.pay.done_title"),
		`href="/stay-fees/15/pdf?month=2026-09"`,
		`id="fee-pay-17" aria-labelledby="fee-pay-h-17" data-fee-step="2"`, pgText("stay_fees.pay.step2"),
		`src="data:image/png;base64,`, `id="fee-acc-17"`, `id="fee-vs-17"`, `action="/stay-fees/17/paid"`,
		`href="/stay-fees/pdfs.zip?month=2026-09"`, pgText("stay_fees.bulk.pdfs", "count", 2),
		pgText("stay_fees.saved_version", "version", 1), pgText("stay_fees.quarter", "n", 3, "year", 2026),
		pgText("stay_fees.pay.open_databox"),
	)

	// Filters: one property, a status with no row, a future month, a stranger's id.
	body = pgOk(t, "apartment filter", e.get(1, "/stay-fees?month=2026-10&apartment=12&lang=en"))
	pgHas(t, "apartment filter", body, `id="fee-pay-12"`, `<option value="12" selected>`)
	pgLacks(t, "apartment filter", body, `id="fee-pay-15"`, `id="fee-copy-11"`)
	body = pgOk(t, "empty status", e.get(1, "/stay-fees?month=2026-10&status=saved&lang=en"))
	pgHas(t, "empty status", body, pgText("filter.no_results"), pgText("filter.reset"), `href="/stay-fees"`, `<option value="saved" selected>`)
	pgLacks(t, "empty status", body, `id="fee-pay-12"`)
	body = pgOk(t, "future month", e.get(1, "/stay-fees?month=2027-01&lang=en"))
	pgHas(t, "future month", body, `value="2026-11"`)
	body = pgOk(t, "foreign apartment id", e.get(1, "/stay-fees?month=2026-10&apartment=20&lang=en"))
	pgLacks(t, "foreign apartment id", body, "Foreign", `<option value="20"`)
	pgHas(t, "foreign apartment id", body, `id="fee-pay-12"`)

	// Another host sees only its own property; a host with nothing set up gets the setup list.
	body = pgOk(t, "host2", e.get(2, "/stay-fees?month=2026-10&lang=en"))
	pgHas(t, "host2", body, "Foreign")
	pgLacks(t, "host2", body, "Byt B")
	body = pgOk(t, "host4", e.get(4, "/stay-fees?month=2026-10&lang=en"))
	pgHas(t, "host4", body, "fee-periods-unset", "Only Unset", pgText("stay_fees.setup.action"))
	pgLacks(t, "host4", body, pgText("stay_fees.col.liable"))

	// Signed out: the login page; the language never reaches the way back.
	rec := e.get(0, "/stay-fees?month=2026-10")
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?next=/stay-fees" {
		t.Errorf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
}

func TestPageListReturnKeepsFilters(t *testing.T) {
	for in, want := range map[string]string{
		"":                               "/stay-fees",
		"lang=cs":                        "/stay-fees",
		"month=2026-10&lang=en&status=a": "/stay-fees?month=2026-10&status=a",
		"q=a+b%26c":                      "/stay-fees?q=a+b%26c",
	} {
		if got := pgListReturn(in); got != want {
			t.Errorf("pgListReturn(%q) = %q, want %q", in, got, want)
		}
	}
	if got := pgFeeSettingsURL(5, "/stay-fees?month=2026-10"); got != "/apartments/5?view=settings&section=reporting&return_to=%2Fstay-fees%3Fmonth%3D2026-10#stay-fee-settings" {
		t.Errorf("feeSettingsURL = %q", got)
	}
	if got := pgFeeOperatorURL(5, 0, ""); got != "/apartments/5?view=settings&section=property#settings-property" {
		t.Errorf("feeOperatorURL = %q", got)
	}
	if got := pgFeeOperatorURL(5, 9, "x"); got != "/entities?edit=9" {
		t.Errorf("feeOperatorURL entity = %q", got)
	}
}

func TestPageRowStatus(t *testing.T) {
	for _, c := range []struct {
		unset, frozen bool
		issues        []string
		want          string
	}{
		{true, false, nil, "attention"},
		{false, true, []string{"x"}, "saved"},
		{false, false, []string{pgIssuePeriodRunning}, "waiting"},
		{false, false, []string{pgIssuePeriodRunning, "x"}, "attention"},
		{false, false, []string{"x"}, "attention"},
		{false, false, nil, "ready"},
	} {
		if got := pgRowStatus(c.unset, c.frozen, c.issues); got != c.want {
			t.Errorf("pgRowStatus(%v) = %q, want %q", c, got, c.want)
		}
	}
}

func TestPageHelpers(t *testing.T) {
	for in, want := range map[string]string{"a b/c": "a%20b%2Fc", "x-_.~": "x-_.~", "č": "%C4%8D"} {
		if got := pgPyQuote(in); got != want {
			t.Errorf("pgPyQuote(%q) = %q, want %q", in, got, want)
		}
	}
	for in, want := range map[string]string{"": "?", "Byt": "B", "Čaj": "Č"} {
		if got := pgFirstLetter(in); got != want {
			t.Errorf("pgFirstLetter(%q) = %q, want %q", in, got, want)
		}
	}
}
