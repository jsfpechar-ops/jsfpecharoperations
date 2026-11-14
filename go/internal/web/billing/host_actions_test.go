package billingweb

import (
	"html"
	"io"
	"net/http"
	"net/url"
	"strings"
	"testing"
	"time"
)

// Parity: routes/billing.py plan_order, _ares_fill and plan_change (lines 84-146),
// billing_order.place (100-134) and change (137-154).

// stubAres is a transport that never leaves the process: it answers every ARES
// request with one status and body and counts them.
type stubAres struct {
	status int
	body   string
	calls  int
	lastUA string
	lastTo string
}

func (s *stubAres) RoundTrip(r *http.Request) (*http.Response, error) {
	s.calls++
	s.lastUA, s.lastTo = r.Header.Get("User-Agent"), r.URL.String()
	return &http.Response{StatusCode: s.status, Body: io.NopCloser(strings.NewReader(s.body)),
		Header: http.Header{"Content-Type": {"application/json"}}, Request: r}, nil
}

// aresBody is a register answer for IC 27082440, a made-up seat with a short postcode.
const aresBody = `{"obchodniJmeno": " Example Seller s.r.o. ", "dic": "CZ27082440",
 "sidlo": {"nazevUlice": "Hlavní", "cisloDomovni": 12, "cisloOrientacni": 3, "cisloOrientacniPismeno": "a",
           "nazevObce": "Praha", "psc": 11000, "textovaAdresa": "unused"}}`

func orderForm(extra map[string]string) url.Values {
	f := url.Values{"plan": {"standard"}, "billing_interval": {"year"}, "buyer_name": {"Buyer s.r.o."},
		"buyer_street": {"Hlavní 1"}, "buyer_city": {"Praha"}, "buyer_zip": {"110 00"}, "buyer_email": {"Buyer@Example.test"}}
	for k, v := range extra {
		f.Set(k, v)
	}
	return f
}

func TestMapAresPayload(t *testing.T) {
	d := mapAresPayload([]byte(aresBody))
	if d == nil || d.Name != "Example Seller s.r.o." || d.Street != "Hlavní 12/3a" || d.City != "Praha" || d.Zip != "11000" || d.DIC != "CZ27082440" {
		t.Fatalf("%+v", d)
	}
	// A short postcode is zero-padded; a street without numbers; a street with a house number only; no DIC is "".
	d = mapAresPayload([]byte(`{"obchodniJmeno": "X", "sidlo": {"nazevUlice": "Dlouhá", "cisloDomovni": 7, "psc": 1000}}`))
	if d == nil || d.Street != "Dlouhá 7" || d.Zip != "01000" || d.DIC != "" {
		t.Fatalf("%+v", d)
	}
	if d = mapAresPayload([]byte(`{"obchodniJmeno": "X", "sidlo": {"nazevUlice": "", "cisloDomovni": 7}}`)); d == nil || d.Street != "" {
		t.Fatalf("no street name: %+v", d)
	}
	for _, bad := range []string{`[]`, `null`, `not json`, `{"obchodniJmeno": 5}`} {
		if mapAresPayload([]byte(bad)) != nil {
			t.Errorf("%q should give no data", bad)
		}
	}
}

func TestAresClient(t *testing.T) {
	stub := &stubAres{status: 200, body: aresBody}
	c := &AresClient{HTTP: &http.Client{Transport: stub}, URL: "https://ares.test/x/"}
	now := testNow
	if d := c.Lookup("27082440", now); d == nil || d.Name != "Example Seller s.r.o." {
		t.Fatalf("lookup: %+v", d)
	}
	if stub.lastTo != "https://ares.test/x/27082440" || stub.lastUA != "UbyHost" {
		t.Errorf("request: %q %q", stub.lastTo, stub.lastUA)
	}
	c.Lookup("27082440", now.Add(23*time.Hour)) // cached
	if stub.calls != 1 {
		t.Errorf("cache missed: %d calls", stub.calls)
	}
	c.Lookup("27082440", now.Add(25*time.Hour)) // expired
	if stub.calls != 2 {
		t.Errorf("expiry: %d calls", stub.calls)
	}
	// A bad IC never reaches the network.
	if c.Lookup("12345678", now) != nil || c.Lookup("", now) != nil || stub.calls != 2 {
		t.Error("bad IC reached the network or answered")
	}
	// 404 is cached as "unknown"; 500 is not cached; a nameless answer is not cached.
	stub.status, stub.body = 404, ""
	c2 := &AresClient{HTTP: &http.Client{Transport: stub}}
	calls := stub.calls
	c2.Lookup("25596641", now)
	c2.Lookup("25596641", now)
	if stub.calls != calls+1 {
		t.Errorf("404 not cached: %d calls", stub.calls-calls)
	}
	stub.status = 500
	c3 := &AresClient{HTTP: &http.Client{Transport: stub}}
	calls = stub.calls
	c3.Lookup("25596641", now)
	c3.Lookup("25596641", now)
	if stub.calls != calls+2 {
		t.Errorf("500 was cached: %d calls", stub.calls-calls)
	}
	stub.status, stub.body = 200, `{"obchodniJmeno": ""}`
	if c3.Lookup("25596641", now) != nil {
		t.Error("a nameless answer gave data")
	}
}

func TestOrderValidation(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	seedAccount(t, pool, 1, "trialing", "", "")
	mux := testMux(pool, testEnvMap(nil))
	rec := do(t, mux, "POST", "/predplatne", url.Values{"plan": {"gold"}, "buyer_zip": {"12"}, "buyer_email": {"nope"}}, "host1", false)
	body := rec.Body.String()
	if rec.Code != 400 {
		t.Fatalf("status %d", rec.Code)
	}
	for _, key := range []string{"billing.order.error.plan", "billing.order.error.required", "billing.order.error.zip", "billing.order.error.email"} {
		if !strings.Contains(body, catalog.T("en", key, nil)) {
			t.Errorf("no error text for %s", key)
		}
	}
	if got := queryString(t, pool, `SELECT COALESCE(plan, '<null>') FROM billing_account WHERE owner_user_id = 1`); got != "<null>" {
		t.Errorf("a refused order was saved: %s", got)
	}
	off := testMux(pool, testEnvMap(map[string]string{"UBYHOST_BILLING_ENABLED": ""}))
	if rec = do(t, off, "POST", "/predplatne", orderForm(nil), "host1", false); rec.Code != 303 || rec.Header().Get("Location") != "/settings" {
		t.Errorf("billing off: %d %q", rec.Code, rec.Header().Get("Location"))
	}
}

func TestOrderInTrial(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	seedAccount(t, pool, 1, "trialing", "", "")
	mustExec(t, pool, `UPDATE billing_account SET trial_ends_at = '2026-11-20T10:00:00+00:00' WHERE owner_user_id = 1`)
	mux := testMux(pool, testEnvMap(nil))
	rec := do(t, mux, "POST", "/predplatne", orderForm(map[string]string{"addon_ttlock": "1"}), "host1", false)
	loc := location(t, rec)
	want := catalog.T("en", "billing.order.done_trial", map[string]any{"date": "20.11.2026"})
	if rec.Code != 303 || loc.Path != "/predplatne" || loc.Query().Get("msg") != want {
		t.Fatalf("order: %d %s (want msg %q)", rec.Code, rec.Header().Get("Location"), want)
	}
	if got := queryString(t, pool, `SELECT status || ' ' || plan || ' ' || billing_interval || ' ' || addon_ttlock || ' ' || apartments_billed || ' ' ||
		buyer_name || '|' || buyer_zip || '|' || buyer_email || '|' || COALESCE(buyer_ico, '-') FROM billing_account WHERE owner_user_id = 1`); got != "trialing standard year 1 1 Buyer s.r.o.|11000|buyer@example.test|-" {
		t.Errorf("account: %s", got)
	}
	if got := queryString(t, pool, `SELECT actor || ' ' || detail || ' ' || actor_user_id FROM audit WHERE action = 'billing_order'`); got != "host1 standard year 1" {
		t.Errorf("audit: %s", got)
	}
	if got := queryString(t, pool, `SELECT COUNT(*)::text FROM platform_invoice`); got != "0" {
		t.Errorf("a trial order issued %s invoices", got)
	}
	// An account that is already running cannot order again.
	mustExec(t, pool, `UPDATE billing_account SET status = 'active' WHERE owner_user_id = 1`)
	rec = do(t, mux, "POST", "/predplatne", orderForm(nil), "host1", false)
	if loc = location(t, rec); loc.Query().Get("err") != catalog.T("en", "billing.order.error.state", nil) {
		t.Errorf("active order: %s", rec.Header().Get("Location"))
	}
	// No billing row at all: the same refusal.
	rec = do(t, mux, "POST", "/predplatne", orderForm(nil), "host2", false)
	if loc = location(t, rec); loc.Query().Get("err") != catalog.T("en", "billing.order.error.state", nil) {
		t.Errorf("no account: %s", rec.Header().Get("Location"))
	}
}

func TestOrderWhenPausedStartsNow(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	seedAccount(t, pool, 1, "paused", "", "")
	t.Setenv("UBYHOST_OPERATOR_NAME", "Operator s.r.o.")
	t.Setenv("UBYHOST_OPERATOR_ADDRESS", "Seat 1, Praha")
	t.Setenv("UBYHOST_OPERATOR_ICO", "27082440")
	t.Setenv("UBYHOST_BILLING_IBAN", "CZ6508000000192000145399")
	t.Setenv("UBYHOST_BILLING_BANK_ACCOUNT", "19-2000145399/0800")
	mux := testMux(pool, testEnvMap(nil))
	// A paused host may post to /predplatne: that is how it comes back.
	rec := do(t, mux, "POST", "/predplatne", orderForm(nil), "host1", false)
	loc := location(t, rec)
	want := catalog.T("en", "billing.order.done_now", map[string]any{"date": "13.11.2026"})
	if rec.Code != 303 || loc.Query().Get("msg") != want {
		t.Fatalf("order: %d %s", rec.Code, rec.Header().Get("Location"))
	}
	// 1 apartment (the minimum), standard, year: 1 190 Kc = 119000 haler; the period runs 2026-11-13 to 2027-11-12.
	if got := queryString(t, pool, `SELECT status || ' ' || period_start || ' ' || period_end FROM billing_account WHERE owner_user_id = 1`); got != "active 2026-11-13 2027-11-12" {
		t.Errorf("account: %s", got)
	}
	if got := queryString(t, pool, `SELECT number || ' ' || kind || ' ' || total_haler || ' ' || issue_date || ' ' || due_date || ' ' || period_from || ' ' || period_to
		FROM platform_invoice WHERE owner_user_id = 1`); got != "UBY-2026-0001 invoice 119000 2026-11-13 2026-11-27 2026-11-13 2027-11-12" {
		t.Errorf("invoice: %s", got)
	}
}

func TestOrderAresFill(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	seedAccount(t, pool, 1, "trialing", "", "")
	stub := &stubAres{status: 200, body: aresBody}
	mux := testMuxWith(deps{pool: pool, getenv: testEnvMap(nil), now: func() time.Time { return testNow },
		ares: &AresClient{HTTP: &http.Client{Transport: stub}}})
	form := url.Values{"do": {"ares"}, "plan": {"max"}, "billing_interval": {"month"}, "buyer_ico": {"27082440"},
		"buyer_name": {"Typed Name"}, "buyer_email": {"x@example.test"}}
	rec := do(t, mux, "POST", "/predplatne", form, "host1", false)
	body := rec.Body.String()
	if rec.Code != 200 || stub.calls != 1 {
		t.Fatalf("status %d, %d lookups", rec.Code, stub.calls)
	}
	// Blank fields are filled; the typed name stays; the note says what happened; no error is shown.
	for _, want := range []string{`value="Hlavní 12/3a"`, `value="Praha"`, `value="11000"`, `value="CZ27082440"`, `value="Typed Name"`,
		html.EscapeString(catalog.T("en", "billing.order.ares_done", nil)), `value="max" checked`} {
		if !strings.Contains(body, want) {
			t.Errorf("page lacks %q", want)
		}
	}
	if strings.Contains(body, "ui-field-err") {
		t.Error("the ARES fill shows field errors")
	}
	if got := queryString(t, pool, `SELECT COUNT(*)::text FROM rate_limit_event WHERE scope = 'ares' AND key = '1'`); got != "1" {
		t.Errorf("rate rows: %s", got)
	}
	if got := queryString(t, pool, `SELECT COALESCE(plan, '<null>') FROM billing_account WHERE owner_user_id = 1`); got != "<null>" {
		t.Errorf("the fill saved the order: %s", got)
	}
	// A bad IC: failure note, no lookup, no rate row.
	form.Set("buyer_ico", "12345678")
	body = do(t, mux, "POST", "/predplatne", form, "host1", false).Body.String()
	if !strings.Contains(body, html.EscapeString(catalog.T("en", "ares.failure", nil))) || stub.calls != 1 {
		t.Errorf("bad IC: %d lookups", stub.calls)
	}
	// An unknown IC: failure note (a rate row is recorded before the lookup).
	stub.status = 404
	form.Set("buyer_ico", "25596641")
	body = do(t, mux, "POST", "/predplatne", form, "host1", false).Body.String()
	if !strings.Contains(body, html.EscapeString(catalog.T("en", "ares.failure", nil))) || stub.calls != 2 {
		t.Errorf("unknown IC: %d lookups", stub.calls)
	}
	// The 20th lookup in an hour is the last: the next is refused without a lookup.
	for i := 0; i < 18; i++ {
		mustExec(t, pool, `INSERT INTO rate_limit_event (scope, key, at) VALUES ('ares', '1', $1)`, float64(testNow.Unix())-10)
	}
	body = do(t, mux, "POST", "/predplatne", form, "host1", false).Body.String()
	if !strings.Contains(body, catalog.T("en", "ares.rate_limited", nil)) || stub.calls != 2 {
		t.Errorf("rate limit: %d lookups", stub.calls)
	}
}

func TestPlanChange(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	seedAccount(t, pool, 1, "active", "standard", "year")
	mustExec(t, pool, `UPDATE billing_account SET period_start = '2026-04-01', period_end = '2027-03-31',
		buyer_name = 'Buyer s.r.o.', buyer_street = 'Hlavní 1', buyer_city = 'Praha', buyer_zip = '11000', buyer_email = 'b@example.test'
		WHERE owner_user_id = 1`)
	t.Setenv("UBYHOST_OPERATOR_NAME", "Operator s.r.o.")
	t.Setenv("UBYHOST_BILLING_IBAN", "CZ6508000000192000145399")
	t.Setenv("UBYHOST_BILLING_BANK_ACCOUNT", "19-2000145399/0800")
	mux := testMux(pool, testEnvMap(nil))
	state := catalog.T("en", "billing.order.error.state", nil)

	// Preview: Standard to Max on an annual plan, 1 apartment: 1 190 -> 1 760 Kc, 4 whole months left
	// (2026-11-13 to 2027-03-31), round(570 * 4 / 12) = 190 Kc to pay now.
	rec := do(t, mux, "POST", "/predplatne/zmena", url.Values{"field": {"plan"}, "value": {"max"}}, "host1", false)
	body := rec.Body.String()
	wantLine := catalog.T("en", "billing.change.when_now_extra", map[string]any{"before": "1 190", "after": "1 760", "extra": "190"})
	if rec.Code != 200 || !strings.Contains(body, `data-billing-preview="now"`) || !strings.Contains(body, wantLine) ||
		!strings.Contains(body, `name="confirm" value="1"`) {
		t.Fatalf("preview: %d, want line %q", rec.Code, wantLine)
	}
	if got := queryString(t, pool, `SELECT plan FROM billing_account WHERE owner_user_id = 1`); got != "standard" {
		t.Errorf("a preview changed the plan: %s", got)
	}
	// Confirm: the plan changes, a supplementary invoice of 190 Kc is issued.
	rec = do(t, mux, "POST", "/predplatne/zmena", url.Values{"field": {"plan"}, "value": {"max"}, "confirm": {"1"}}, "host1", false)
	if loc := location(t, rec); rec.Code != 303 || loc.Query().Get("msg") != catalog.T("en", "billing.change.saved_now", nil) {
		t.Fatalf("confirm: %d %s", rec.Code, rec.Header().Get("Location"))
	}
	if got := queryString(t, pool, `SELECT plan FROM billing_account WHERE owner_user_id = 1`); got != "max" {
		t.Errorf("plan: %s", got)
	}
	if got := queryString(t, pool, `SELECT kind || ' ' || total_haler || ' ' || period_from || ' ' || period_to FROM platform_invoice WHERE owner_user_id = 1`); got != "supplementary 19000 2026-11-13 2027-03-31" {
		t.Errorf("supplementary: %s", got)
	}
	if got := queryString(t, pool, `SELECT actor || ' ' || detail FROM audit WHERE action = 'billing_change'`); got != "host1 plan now" {
		t.Errorf("audit: %s", got)
	}
	// A value outside the form's choices, an unknown field and a locked add-on are refused.
	for _, f := range []url.Values{{"field": {"plan"}, "value": {"gold"}}, {"field": {"apartments"}, "value": {"3"}},
		{"field": {"addon_whitelabel"}, "value": {"1"}}, {"field": {""}, "value": {""}}} {
		rec = do(t, mux, "POST", "/predplatne/zmena", f, "host1", false)
		if loc := location(t, rec); loc.Query().Get("err") != state {
			t.Errorf("%v: %s", f, rec.Header().Get("Location"))
		}
	}
	// A trial or no account: refused.
	if loc := location(t, do(t, mux, "POST", "/predplatne/zmena", url.Values{"field": {"plan"}, "value": {"max"}}, "host2", false)); loc.Query().Get("err") != state {
		t.Errorf("no account: %s", loc)
	}
	mustExec(t, pool, `UPDATE billing_account SET status = 'canceling'`)
	if loc := location(t, do(t, mux, "POST", "/predplatne/zmena", url.Values{"field": {"plan"}, "value": {"standard"}}, "host1", false)); loc.Query().Get("err") != state {
		t.Errorf("canceling: %s", loc)
	}
}
