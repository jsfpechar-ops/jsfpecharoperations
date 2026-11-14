package billingweb

import (
	"context"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
)

// Parity: routes/billing.py plan_page and _page (lines 33-81), billing_order.form_values
// (25-59), billing_invoices.for_owner (248-257).

// TestSavePct pins routes/billing.py line 56 with fixed numbers: Python's round() is half to even.
func TestSavePct(t *testing.T) {
	for _, c := range []struct{ month, year, want int }{
		{447, 3570, 33}, // 3 apartments: 100 * (5364 - 3570) / 5364 = 33.4
		{149, 1190, 33}, // 1 apartment: 100 * (1788 - 1190) / 1788 = 33.4
		{2, 21, 12},     // 12.5 rounds to 12 (half to even); half up would say 13
		{2, 15, 38},     // 37.5 rounds to 38
		{0, 0, 0},       // no month price: 0
	} {
		if got := savePct(c.month, c.year); got != c.want {
			t.Errorf("savePct(%d, %d) = %d, want %d", c.month, c.year, got, c.want)
		}
	}
}

func TestKcWhole(t *testing.T) {
	for in, want := range map[int]string{0: "0", 999: "999", 1190: "1 190", 12345: "12 345", 1234567: "1 234 567", -1234: "-1 234"} {
		if got := kcWhole(in); got != want {
			t.Errorf("kcWhole(%d) = %q, want %q", in, got, want)
		}
	}
}

func TestFmtDate(t *testing.T) {
	for in, want := range map[string]string{
		"2026-11-20": "20.11.2026", "2026-11-20T10:00:00+00:00": "20.11.2026", "": "", "soon": "soon", "2026-13-40": "2026-13-40",
	} {
		if got := fmtDate(in); got != want {
			t.Errorf("fmtDate(%q) = %q, want %q", in, got, want)
		}
	}
}

// TestUpgradeFor pins the upgrade card prices with fixed numbers and the add-on price to the engine's table.
func TestUpgradeFor(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	ctx := context.Background()
	if q, err := billing.Quote(1, "standard", "month", true, false, 0); err != nil || q.TTLock != ttlockMonthly {
		t.Fatalf("ttlockMonthly is %d, the engine says %+v (%v)", ttlockMonthly, q, err)
	}
	for i := 1; i <= 3; i++ {
		mustExec(t, pool, `INSERT INTO apartment (owner_user_id, internal_name, active, created_at) VALUES (1, 'A' || $1::int::text, 1, '2026-01-01')`, i)
	}
	seedAccount(t, pool, 1, "active", "standard", "month")
	acc, err := billing.Account(ctx, pool, 1)
	if err != nil {
		t.Fatal(err)
	}
	// 3 apartments, standard, month: Max costs 3 * (149 + 59) = 624 a month; a year saves 33 %.
	u, err := UpgradeFor(ctx, pool, 1, acc)
	if err != nil || u == nil || u.Price != "624" || u.SavePct != 33 || u.TTLockPrice != 49 {
		t.Fatalf("month: %+v %v", u, err)
	}
	// Annual: Max for a year is 3 * (1190 + 570) = 5 280.
	acc.BillingInterval = "year"
	if u, err = UpgradeFor(ctx, pool, 1, acc); err != nil || u.Price != "5 280" {
		t.Fatalf("year: %+v %v", u, err)
	}
	// On Max the other plan is Standard with the lock add-on kept (it is free on Max, paid on
	// Standard): 3 * 149 + 3 * 49 = 594 a month.
	acc.Plan, acc.BillingInterval, acc.AddonTTLock = "max", "month", true
	if u, err = UpgradeFor(ctx, pool, 1, acc); err != nil || u.Price != "594" {
		t.Fatalf("max: %+v %v", u, err)
	}
	acc.Plan = ""
	if u, err = UpgradeFor(ctx, pool, 1, acc); err != nil || u != nil {
		t.Errorf("no plan: %+v %v", u, err)
	}
}

func TestFormValues(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	ctx := context.Background()
	// No billing row: defaults, the first legal entity, then the login address.
	v, err := FormValues(ctx, pool, 1, map[string]string{"plan": "", "interval": ""})
	if err != nil || v.Plan != "standard" || v.BillingInterval != "year" || v.BuyerEmail != "host1@example.test" || v.BuyerName != "" {
		t.Fatalf("defaults: %+v %v", v, err)
	}
	mustExec(t, pool, `INSERT INTO legal_entity (owner_user_id, name, ico, dic, contact_email, created_at)
		VALUES (1, 'Entity Two s.r.o.', '27082440', 'CZ27082440', 'billing@example.test', '2026-01-01'),
		       (1, 'Entity Later', '', '', '', '2026-01-02')`)
	if v, err = FormValues(ctx, pool, 1, nil); err != nil || v.BuyerName != "Entity Two s.r.o." || v.BuyerICO != "27082440" ||
		v.BuyerDIC != "CZ27082440" || v.BuyerEmail != "billing@example.test" {
		t.Fatalf("entity: %+v %v", v, err)
	}
	// Signup preferences prefill an unordered account; a non-empty query value beats them,
	// even a bad one, which then falls back to the default (year), as Python's dict merge does.
	mustExec(t, pool, `UPDATE user_account SET signup_selection_json = '{"plan": "max", "interval": "month", "ttlock": "1", "apartments": 5}' WHERE id = 1`)
	seedAccount(t, pool, 1, "trialing", "", "")
	if v, err = FormValues(ctx, pool, 1, map[string]string{"plan": "standard", "interval": "weekly"}); err != nil ||
		v.Plan != "standard" || v.BillingInterval != "year" || !v.AddonTTLock {
		t.Fatalf("selection: %+v %v", v, err)
	}
	// An ordered account keeps its order; preferences no longer apply.
	mustExec(t, pool, `UPDATE billing_account SET plan = 'max', billing_interval = 'year', addon_whitelabel = 1,
		buyer_name = 'Saved Buyer', buyer_email = 'saved@example.test' WHERE owner_user_id = 1`)
	if v, err = FormValues(ctx, pool, 1, nil); err != nil || v.Plan != "max" || v.BillingInterval != "year" || v.AddonTTLock ||
		!v.AddonWhitelabel || v.BuyerName != "Saved Buyer" || v.BuyerEmail != "saved@example.test" || v.BuyerICO != "" {
		t.Fatalf("ordered: %+v %v", v, err)
	}
}

func TestPlanPage(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	mux := testMux(pool, testEnvMap(nil))

	// Billing off, and signed out.
	off := testMux(pool, testEnvMap(map[string]string{"UBYHOST_BILLING_ENABLED": ""}))
	if rec := do(t, off, "GET", "/predplatne", nil, "host1", false); rec.Code != 303 || rec.Header().Get("Location") != "/settings" {
		t.Errorf("billing off: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	if rec := do(t, mux, "GET", "/predplatne", nil, "", false); rec.Code != 303 || rec.Header().Get("Location") != "/login?next=/predplatne" {
		t.Errorf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	// No billing row (an OG host): the explanation only.
	rec := do(t, mux, "GET", "/predplatne", nil, "host1", false)
	if rec.Code != 200 || !strings.Contains(rec.Body.String(), "tip-billing-og") || strings.Contains(rec.Body.String(), "data-billing-order") {
		t.Errorf("no account: %d", rec.Code)
	}
	// A trial: the order form with the quote of the chosen plan (1 apartment: Max a month is 149 + 59).
	seedAccount(t, pool, 1, "trialing", "", "")
	rec = do(t, mux, "GET", "/predplatne?plan=max&interval=month", nil, "host1", false)
	body := rec.Body.String()
	for _, want := range []string{"data-billing-order", `data-billing-total>208 Kč</strong>`, `name="_csrf"`, `name="do" value="ares"`,
		`<title>` + catalog.T("en", "billing.plan.title", nil) + ` · UbyHost</title>`} {
		if rec.Code != 200 || !strings.Contains(body, want) {
			t.Errorf("trial page lacks %q (status %d)", want, rec.Code)
		}
	}
	if !strings.Contains(body, `value="max" checked`) || !strings.Contains(body, `value="month" checked`) {
		t.Error("trial page does not check max and month")
	}
	// An active plan: facts, the change forms, the cancel form and the invoice list.
	mustExec(t, pool, `DELETE FROM billing_account`)
	seedAccount(t, pool, 1, "active", "standard", "month")
	mustExec(t, pool, `UPDATE billing_account SET period_end = '2026-12-31' WHERE owner_user_id = 1`)
	seedInvoice(t, pool, 21, 1, "UBY-2026-0021", "invoice", 119000)
	seedInvoice(t, pool, 22, 1, "UBY-2026-0022", "storno", -119000)
	rec = do(t, mux, "GET", "/predplatne", nil, "host1", false)
	body = rec.Body.String()
	for _, want := range []string{"31.12.2026", `action="/predplatne/zrusit"`, `name="field" value="plan"><input type="hidden" name="value" value="max"`,
		`href="/predplatne/faktury/21.pdf"`, `1 190 Kč`, `-1 190 Kč`, "ui-badge-neutral", "ui-badge-action", "ui-badge-done"} {
		if rec.Code != 200 || !strings.Contains(body, want) {
			t.Errorf("active page lacks %q (status %d)", want, rec.Code)
		}
	}
	if strings.Contains(body, `action="/predplatne/obnovit"`) {
		t.Error("active page offers resume")
	}
	// Canceling offers resume, not cancel.
	mustExec(t, pool, `UPDATE billing_account SET status = 'canceling', cancel_at_period_end = 1 WHERE owner_user_id = 1`)
	body = do(t, mux, "GET", "/predplatne", nil, "host1", false).Body.String()
	if !strings.Contains(body, `action="/predplatne/obnovit"`) || strings.Contains(body, `action="/predplatne/zrusit"`) ||
		strings.Contains(body, `/predplatne/zmena`) {
		t.Error("canceling page offers the wrong forms")
	}
	// Another host's invoices never appear.
	if strings.Contains(do(t, mux, "GET", "/predplatne", nil, "host2", false).Body.String(), "UBY-2026-0021") {
		t.Error("host2 sees host1's invoice")
	}
}
