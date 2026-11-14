package customers

import (
	"context"
	"net/http"
	"net/url"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
)

// Tests of the plan and price actions (brief 1591), over the same golden seed
// as actions_test.go. The invoice mail goes through billingjob.Invoicer, which
// reads the mail switch and base URLs from the process environment.

func billingMux(pool *pgxpool.Pool, getenv func(string) string) *http.ServeMux {
	now := testClock
	mux := http.NewServeMux()
	mux.Handle("POST /admin/customers/{user_id}/sleva", DiscountHandler(pool, getenv, now))
	mux.Handle("POST /admin/customers/{user_id}/plan", PlanChangeHandler(pool, getenv, now))
	mux.Handle("POST /admin/customers/{user_id}/priradit", AssignPlanHandler(pool, getenv, now))
	return mux
}

func billingWorld(t *testing.T) (*http.ServeMux, *pgxpool.Pool) {
	t.Helper()
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	t.Setenv("UBYHOST_PUBLIC_BASE_URL", "https://ubyhost.example")
	t.Setenv("UBYHOST_APP_BASE_URL", "https://app.ubyhost.example")
	g := loadGolden(t)
	pool := dbPool(t)
	seed(t, pool, g)
	// The seeded invoices use numbers up to 50; the invoicer must number after them.
	if _, err := pool.Exec(context.Background(), "INSERT INTO platform_invoice_sequence (year, last_no) VALUES (2026, 100)"); err != nil {
		t.Fatal(err)
	}
	return billingMux(pool, actEnv(g.Versions)), pool
}

// TestBillingActionGuards: the three routes that change an account refuse as Python does.
func TestBillingActionGuards(t *testing.T) {
	mux, pool := billingWorld(t)
	checkGuards(t, mux, pool, []guardCase{
		{"sleva", "/admin/customers/12/sleva", "percent=10&reason=x"},
		{"plan", "/admin/customers/12/plan", "field=apartments&value=5"},
		{"priradit", "/admin/customers/11/priradit", assignForm(nil)},
	}, "SELECT owner_user_id, status, plan, apartments_billed, discount_percent, discount_reason, pending_change_json FROM billing_account ORDER BY owner_user_id")
	if n := countRows(t, pool, "SELECT COUNT(*) FROM platform_invoice"); n != 13 {
		t.Errorf("refused requests changed the invoices: %d", n)
	}
}

// assignForm is a complete order form for customer_assign_plan; over replaces fields.
func assignForm(over map[string]string) string {
	f := map[string]string{
		"plan": "standard", "billing_interval": "month",
		"buyer_name": "Jana Pending s.r.o.", "buyer_street": "Hlavni 1", "buyer_city": "Brno",
		"buyer_zip": "602 00", "buyer_ico": "", "buyer_dic": "", "buyer_email": " Jana@Example.test ",
	}
	for k, v := range over {
		f[k] = v
	}
	q := url.Values{}
	for k, v := range f {
		q.Set(k, v)
	}
	return q.Encode()
}

// TestDiscountAction mirrors customer_discount (admin_customers.py 111-132) and
// billing.apply_discount (billing.py 311-374).
func TestDiscountAction(t *testing.T) {
	mux, pool := billingWorld(t)
	post := func(id, form, lang string) (string, string, int64) {
		top := maxAuditID(t, pool)
		_, _, m, e := flashOf(t, actServe(t, mux, actCall{path: "/admin/customers/" + id + "/sleva", form: form, uid: 1, sv: 1, lang: lang}))
		return m, e, top
	}
	acct := func(id string) string {
		return actRows(t, pool, "SELECT discount_percent, discount_reason FROM billing_account WHERE owner_user_id = "+id)
	}
	// Customer 12 (Max, active) has no unpaid invoice: the discount is saved, nothing reissued.
	m, e, top := post("12", "percent=20&reason=%20Partner%20", "en")
	if m != "Discount saved." || e != "" {
		t.Errorf("discount: %q %q", m, e)
	}
	actWant(t, "acct 12", acct("12"), `[{"discount_percent":20,"discount_reason":"Partner"}]`)
	actWant(t, "discount audit", actAudit(t, pool, top), `[{"action":"billing_discount","actor":"operator:admin","actor_user_id":1,
		"detail":"20 % Partner","impersonator_user_id":null,"owner_user_id":12}]`)
	// Percent 0 clears both columns; the reason is not needed then.
	m, _, _ = post("12", "percent=0&reason=", "en")
	actWant(t, "acct 12 cleared", acct("12"), `[{"discount_percent":0,"discount_reason":null}]`)
	if m != "Discount saved." {
		t.Errorf("clear: %q", m)
	}
	// An empty percent means 0 (the form value is "0" when absent).
	post("12", "", "en")
	// Refusals write nothing.
	for _, c := range []struct{ id, form, want string }{
		{"12", "percent=abc", "The discount must be 0 to 100."},
		{"12", "percent=1.5", "The discount must be 0 to 100."},
		{"12", "percent=%20", "The discount must be 0 to 100."},
		{"12", "percent=101&reason=x", "The discount must be 0 to 100."},
		{"12", "percent=-1&reason=x", "The discount must be 0 to 100."},
		{"12", "percent=99999999999999999999&reason=x", "The discount must be 0 to 100."},
		{"12", "percent=10", "Write why the discount applies."},
		{"12", "percent=10&reason=%20%20", "Write why the discount applies."},
		{"3", "percent=10&reason=x", "This customer has no plan to discount."},
		{"11", "percent=10&reason=x", "This customer has no plan to discount."},
		{"99999", "percent=10&reason=x", "This customer has no plan to discount."},
	} {
		m, e, top = post(c.id, c.form, "en")
		if m != "" || e != c.want {
			t.Errorf("%s %q: %q %q", c.id, c.form, m, e)
		}
		if got := actAudit(t, pool, top); got != "[]" {
			t.Errorf("%s %q wrote %s", c.id, c.form, got)
		}
	}
	actWant(t, "acct 12 untouched", acct("12"), `[{"discount_percent":0,"discount_reason":null}]`)
	// The reason is cut to 200 characters.
	long := make([]byte, 250)
	for i := range long {
		long[i] = 'r'
	}
	post("12", "percent=5&reason="+string(long), "en")
	if got := countRows(t, pool, "SELECT COUNT(*) FROM billing_account WHERE owner_user_id = 12 AND LENGTH(discount_reason) = 200"); got != 1 {
		t.Error("reason not cut to 200")
	}
	// Czech text.
	_, e, _ = post("12", "percent=abc", "cs")
	if e != "Sleva musí být 0 až 100." {
		t.Errorf("Czech: %q", e)
	}
}

// issueFor issues a real invoice for a customer the way the billing job would,
// so the discount has an unpaid invoice to cancel and reissue.
func issueFor(t *testing.T, pool *pgxpool.Pool, owner int64, from, to string) int64 {
	t.Helper()
	if _, err := pool.Exec(context.Background(), `UPDATE billing_account SET buyer_name = 'Gina s.r.o.', buyer_street = 'Ulice 1',
		buyer_city = 'Praha', buyer_zip = '11000', buyer_email = 'gina@example.test' WHERE owner_user_id = $1`, owner); err != nil {
		t.Fatal(err)
	}
	id, err := (&billingjob.Invoicer{Pool: pool}).IssueForPeriod(context.Background(), owner, from, to, testNow)
	if err != nil {
		t.Fatal(err)
	}
	return id
}

// TestDiscountReissuesUnpaidInvoice: the unpaid invoice is cancelled and issued again.
func TestDiscountReissuesUnpaidInvoice(t *testing.T) {
	mux, pool := billingWorld(t)
	id := issueFor(t, pool, 12, "2026-11-01", "2026-11-30")
	top := maxAuditID(t, pool)
	rec := actServe(t, mux, actCall{path: "/admin/customers/12/sleva", form: "percent=10&reason=Partner", uid: 1, sv: 1, lang: "en"})
	_, _, m, e := flashOf(t, rec)
	if m != "Discount saved; the unpaid invoice was cancelled and reissued with the discount." || e != "" {
		t.Errorf("reissue: %q %q", m, e)
	}
	// The old invoice is voided, a storno corrects it, a new invoice for the same period is open.
	actWant(t, "invoices of 12", actRows(t, pool, `SELECT kind, voided, period_from, period_to, paid_on IS NULL AS unpaid
		FROM platform_invoice WHERE owner_user_id = 12 ORDER BY id`),
		`[{"kind":"invoice","voided":1,"period_from":"2026-11-01","period_to":"2026-11-30","unpaid":true},
		  {"kind":"storno","voided":0,"period_from":"2026-11-01","period_to":"2026-11-30","unpaid":true},
		  {"kind":"invoice","voided":0,"period_from":"2026-11-01","period_to":"2026-11-30","unpaid":true}]`)
	if got := countRows(t, pool, "SELECT COUNT(*) FROM platform_invoice WHERE id = $1 AND voided = 1", id); got != 1 {
		t.Error("the first invoice is not voided")
	}
	audit := actAudit(t, pool, top)
	if !(strings.Contains(audit, `"action":"billing_discount"`) && strings.Contains(audit, `"detail":"10 % Partner"`)) {
		t.Errorf("audit: %s", audit)
	}
	// Python's db.audit gives every row of the request the signed-in account, the invoice rows too.
	if got := actRows(t, pool, `SELECT action, actor, actor_user_id, impersonator_user_id FROM audit
		WHERE id > $1 AND action = 'platform_invoice_issued' ORDER BY id`, top); got !=
		`[{"action":"platform_invoice_issued","actor":"system","actor_user_id":1,"impersonator_user_id":null},`+
			`{"action":"platform_invoice_issued","actor":"system","actor_user_id":1,"impersonator_user_id":null}]` {
		t.Errorf("issue rows: %s", got)
	}
	// Again as an impersonating admin: the rows name the admin as impersonator, and a row that
	// belongs to nobody's request (an invoice issued earlier) is not touched.
	top = maxAuditID(t, pool)
	actServe(t, mux, actCall{path: "/admin/customers/12/sleva", form: "percent=15&reason=Partner", uid: 1, sv: 1, lang: "en", impersonating: true})
	if got := actRows(t, pool, `SELECT actor_user_id, impersonator_user_id FROM audit
		WHERE id > $1 AND action = 'platform_invoice_issued' ORDER BY id`, top); got !=
		`[{"actor_user_id":1,"impersonator_user_id":1},{"actor_user_id":1,"impersonator_user_id":1}]` {
		t.Errorf("impersonating issue rows: %s", got)
	}
	if got := countRows(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'platform_invoice_issued' AND actor_user_id IS NULL`); got != 1 {
		t.Errorf("the invoice issued outside the request lost its NULL actor: %d rows with NULL", got)
	}
}

// TestPlanChangeAction mirrors customer_plan (admin_customers.py 135-162) and
// billing_order.change.
func TestPlanChangeAction(t *testing.T) {
	mux, pool := billingWorld(t)
	post := func(id, form, lang string) (string, string, int64) {
		top := maxAuditID(t, pool)
		_, _, m, e := flashOf(t, actServe(t, mux, actCall{path: "/admin/customers/" + id + "/plan", form: form, uid: 1, sv: 1, lang: lang}))
		return m, e, top
	}
	acct := func(id string) string {
		return actRows(t, pool, "SELECT apartments_billed, plan, billing_interval, addon_ttlock, addon_whitelabel, carry_czk, pending_change_json FROM billing_account WHERE owner_user_id = "+id)
	}
	// A rise on a monthly plan starts now and is saved; the audit names the username (Python's "host").
	m, e, top := post("2", "field=apartments&value=5", "en")
	if m != "The change is saved; the customer sees it on their plan page." || e != "" {
		t.Errorf("rise: %q %q", m, e)
	}
	actWant(t, "acct 2", acct("2"), `[{"apartments_billed":5,"plan":"standard","billing_interval":"month","addon_ttlock":0,"addon_whitelabel":0,"carry_czk":0,"pending_change_json":null}]`)
	actWant(t, "rise audit", actAudit(t, pool, top), `[{"action":"billing_change","actor":"admin","actor_user_id":1,
		"detail":"apartments now","impersonator_user_id":null,"owner_user_id":2}]`)
	if got := actRows(t, pool, "SELECT status FROM billing_month_snapshot WHERE month = '2026-11' AND owner_user_id = 2"); got != `[{"status":"active"}]` {
		t.Errorf("snapshot: %s", got)
	}
	// A drop waits for the next period: pending_change_json, audit "next_period".
	_, _, top = post("2", "field=apartments&value=3", "en")
	actWant(t, "acct 2 pending", acct("2"), `[{"apartments_billed":5,"plan":"standard","billing_interval":"month","addon_ttlock":0,"addon_whitelabel":0,"carry_czk":0,"pending_change_json":"{\"apartments\": 3}"}]`)
	actWant(t, "drop audit", actAudit(t, pool, top), `[{"action":"billing_change","actor":"admin","actor_user_id":1,
		"detail":"apartments next_period","impersonator_user_id":null,"owner_user_id":2}]`)
	// Plan and interval are text; an add-on value is int(bool(int)): 7 means on.
	_, _, top = post("102", "field=addon_ttlock&value=7", "en")
	actWant(t, "acct 102", acct("102"), `[{"apartments_billed":2,"plan":"standard","billing_interval":"month","addon_ttlock":1,"addon_whitelabel":0,"carry_czk":0,"pending_change_json":null}]`)
	actWant(t, "add-on audit", actAudit(t, pool, top), `[{"action":"billing_change","actor":"admin","actor_user_id":1,
		"detail":"addon_ttlock now","impersonator_user_id":null,"owner_user_id":102}]`)
	post("12", "field=billing_interval&value=year", "en")
	actWant(t, "acct 12", acct("12"), `[{"apartments_billed":2,"plan":"max","billing_interval":"month","addon_ttlock":0,"addon_whitelabel":0,"carry_czk":0,"pending_change_json":"{\"billing_interval\": \"year\"}"}]`)
	// Nothing to do when the price does not change: no audit row, still "saved".
	m, _, top = post("12", "field=plan&value=max", "en")
	if m == "" || actAudit(t, pool, top) != "[]" {
		t.Errorf("same plan: %q %s", m, actAudit(t, pool, top))
	}
	// Refusals and their texts; nothing is written.
	for _, c := range []struct{ id, form, want string }{
		{"2", "field=nothing&value=1", "Choose what to change."},
		{"2", "field=&value=1", "Choose what to change."},
		{"2", "field=discount_percent&value=5", "Choose what to change."},
		{"2", "field=apartments&value=abc", "That value does not fit."},
		{"2", "field=addon_ttlock&value=", "That value does not fit."},
		{"2", "field=plan&value=gold", "This change is not possible for this customer."},
		{"2", "field=addon_whitelabel&value=1", "This change is not possible for this customer."},
		{"3", "field=apartments&value=3", "This change is not possible for this customer."},
		{"11", "field=apartments&value=3", "This change is not possible for this customer."},
		{"99999", "field=apartments&value=3", "This change is not possible for this customer."},
	} {
		m, e, top = post(c.id, c.form, "en")
		if m != "" || e != c.want {
			t.Errorf("%s %q: %q %q", c.id, c.form, m, e)
		}
		if got := actAudit(t, pool, top); got != "[]" {
			t.Errorf("%s %q wrote %s", c.id, c.form, got)
		}
	}
	// Customer 8 has whitelabel switched on (yearly Max, 7 apartments): a rise issues a supplementary invoice
	// and queues its mail, a drop does not.
	issueFor(t, pool, 8, "2026-10-01", "2027-09-30")
	before := countRows(t, pool, "SELECT COUNT(*) FROM email_outbox WHERE kind = 'billing_invoice'")
	m, e, _ = post("8", "field=apartments&value=9", "en")
	if m == "" || e != "" {
		t.Fatalf("annual rise: %q %q", m, e)
	}
	if got := countRows(t, pool, "SELECT COUNT(*) FROM platform_invoice WHERE owner_user_id = 8 AND kind = 'supplementary'"); got != 1 {
		t.Errorf("supplementary invoices: %d", got)
	}
	if got := countRows(t, pool, "SELECT COUNT(*) FROM email_outbox WHERE kind = 'billing_invoice'"); got != before+1 {
		t.Errorf("invoice mails: %d, was %d", got, before)
	}
	// Czech text.
	_, e, _ = post("2", "field=nothing", "cs")
	if e != "Vyberte, co měnit." {
		t.Errorf("Czech: %q", e)
	}
}

// TestAssignPlanAction mirrors customer_assign_plan (admin_customers.py 165-181)
// and billing_order.place_for_operator (billing_order.py 175-203).
func TestAssignPlanAction(t *testing.T) {
	mux, pool := billingWorld(t)
	post := func(id, form, lang string) (string, string, int64) {
		top := maxAuditID(t, pool)
		_, _, m, e := flashOf(t, actServe(t, mux, actCall{path: "/admin/customers/" + id + "/priradit", form: form, uid: 1, sv: 1, lang: lang}))
		return m, e, top
	}
	// Incomplete or invalid forms are refused before anything is written.
	for _, over := range []map[string]string{
		{"plan": "gold"}, {"billing_interval": "week"}, {"buyer_name": " "}, {"buyer_street": ""},
		{"buyer_city": ""}, {"buyer_zip": "1234"}, {"buyer_ico": "12345678x"}, {"buyer_email": "nope"},
	} {
		m, e, top := post("11", assignForm(over), "en")
		if m != "" || e != "Fill the plan and the invoicing name, street, city, ZIP and e-mail." {
			t.Errorf("%v: %q %q", over, m, e)
		}
		if got := actAudit(t, pool, top); got != "[]" {
			t.Errorf("%v wrote %s", over, got)
		}
	}
	// Customer 11 (trial_pending, no plan): the plan runs from today, the first invoice is issued and mailed.
	m, e, top := post("11", assignForm(nil), "en")
	if m != "Plan assigned; it runs from today and the first invoice is issued." || e != "" {
		t.Fatalf("assign: %q %q", m, e)
	}
	actWant(t, "acct 11", actRows(t, pool, `SELECT status, plan, billing_interval, period_start, period_end, buyer_name, buyer_zip, buyer_email
		FROM billing_account WHERE owner_user_id = 11`),
		`[{"status":"active","plan":"standard","billing_interval":"month","period_start":"2026-11-13","period_end":"2026-12-12",
		  "buyer_name":"Jana Pending s.r.o.","buyer_zip":"60200","buyer_email":"jana@example.test"}]`)
	actWant(t, "assign audit", actAudit(t, pool, top), `[
	 {"action":"billing_status","actor":"operator:admin","actor_user_id":1,"detail":"trial_pending->paused","impersonator_user_id":null,"owner_user_id":11},
	 {"action":"billing_order","actor":"admin","actor_user_id":1,"detail":"standard month","impersonator_user_id":null,"owner_user_id":11},
	 {"action":"billing_status","actor":"admin","actor_user_id":1,"detail":"paused->active","impersonator_user_id":null,"owner_user_id":11},
	 {"action":"platform_invoice_issued","actor":"system","actor_user_id":1,"detail":"UBY-2026-0101 invoice","impersonator_user_id":null,"owner_user_id":11},
	 {"action":"billing_order","actor":"operator:admin","actor_user_id":1,"detail":"standard month (operator assign)","impersonator_user_id":null,"owner_user_id":11}]`)
	if got := actRows(t, pool, "SELECT kind, period_from, period_to, voided FROM platform_invoice WHERE owner_user_id = 11"); got != norm(t, []byte(`[{"kind":"invoice","period_from":"2026-11-13","period_to":"2026-12-12","voided":0}]`)) {
		t.Errorf("invoice: %s", got)
	}
	if got := actRows(t, pool, "SELECT kind, owner_user_id FROM email_outbox WHERE kind = 'billing_invoice' AND owner_user_id = 11"); got != `[{"kind":"billing_invoice","owner_user_id":11}]` {
		t.Errorf("invoice mail: %s", got)
	}
	// A customer who has a plan is refused (already ordered); so is a second assignment.
	for _, id := range []string{"11", "2", "12"} {
		m, e, top = post(id, assignForm(nil), "cs")
		if m != "" || e != "Tenhle zákazník už plán má." {
			t.Errorf("customer %s: %q %q", id, m, e)
		}
		if got := actAudit(t, pool, top); got != "[]" {
			t.Errorf("customer %s wrote %s", id, got)
		}
	}
	// Customer 3 has no billing row at all: it is created and assigned.
	m, e, _ = post("3", assignForm(map[string]string{"plan": "max", "billing_interval": "year"}), "en")
	if m == "" || e != "" {
		t.Fatalf("assign to 3: %q %q", m, e)
	}
	actWant(t, "acct 3", actRows(t, pool, "SELECT status, plan, billing_interval, period_end FROM billing_account WHERE owner_user_id = 3"),
		`[{"status":"active","plan":"max","billing_interval":"year","period_end":"2027-11-12"}]`)
}
