package billingweb

import (
	"strings"
	"testing"
)

// Parity: routes/admin_billing.py billing_admin_page (lines 33-69) and the template
// admin_billing.html. The data itself is pinned against Python by brief 1341's golden test.

func TestPosthogURL(t *testing.T) {
	env := func(m map[string]string) func(string) string { return func(k string) string { return m[k] } }
	for name, c := range map[string]struct {
		env  map[string]string
		want string
	}{
		"no key":      {map[string]string{}, ""},
		"defaults":    {map[string]string{"POSTHOG_PROJECT_API_KEY": "phc_x"}, "https://eu.posthog.com"},
		"own app url": {map[string]string{"POSTHOG_PROJECT_API_KEY": " phc_x ", "POSTHOG_APP_URL": "https://app.example.test/"}, "https://app.example.test"},
		"us host":     {map[string]string{"POSTHOG_PROJECT_API_KEY": "phc_x", "POSTHOG_HOST": "https://us.i.posthog.com"}, ""},
		"us assets":   {map[string]string{"POSTHOG_PROJECT_API_KEY": "phc_x", "POSTHOG_ASSETS_HOST": "https://us-assets.i.posthog.com"}, ""},
		"http host":   {map[string]string{"POSTHOG_PROJECT_API_KEY": "phc_x", "POSTHOG_HOST": "http://eu.i.posthog.com"}, ""},
	} {
		if got := posthogURL(env(c.env)); got != c.want {
			t.Errorf("%s: %q, want %q", name, got, c.want)
		}
	}
}

func TestMinusFormats(t *testing.T) {
	for in, want := range map[int64]string{119000: "1 190", 0: "0", -119000: "−1 190", -99: "−0"} {
		if got := minusKc(in); got != want {
			t.Errorf("minusKc(%d) = %q, want %q", in, got, want)
		}
	}
	for in, want := range map[int64]string{5: "5 Kč", 0: "0 Kč", -7: "−7 Kč"} {
		if got := minusWhole(in); got != want {
			t.Errorf("minusWhole(%d) = %q, want %q", in, got, want)
		}
	}
}

func TestAdminPage(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	// Host 1: 3 apartments billed, Standard, year: 3 * 1190 = 3570 a year, 297.5 a month rounds to 298 (half to even).
	seedAccount(t, pool, 1, "active", "standard", "year")
	mustExec(t, pool, `UPDATE billing_account SET apartments_billed = 3, period_start = '2026-10-01', period_end = '2027-09-30' WHERE owner_user_id = 1`)
	seedInvoice(t, pool, 31, 1, "UBY-2026-0031", "invoice", 119000)
	mustExec(t, pool, `UPDATE platform_invoice SET due_date = '2026-11-05' WHERE id = 31`)
	seedInvoice(t, pool, 32, 1, "UBY-2026-0032", "storno", -119000)
	mustExec(t, pool, `INSERT INTO bank_payment (bank_tx_id, received_on, amount_haler, vs, message, status)
		VALUES ('csv-x', '2026-11-12', 5000, '20269999', 'who knows', 'unmatched')`)
	mux := testMux(pool, testEnvMap(map[string]string{"UBYHOST_SIGNUP_ENABLED": "1", "POSTHOG_PROJECT_API_KEY": "phc_x"}))

	rec := do(t, mux, "GET", "/admin/fakturace", nil, "admin1", false)
	body := rec.Body.String()
	if rec.Code != 200 {
		t.Fatalf("status %d", rec.Code)
	}
	for _, want := range []string{
		`<title>` + catalog.T("en", "billing.admin.title", nil) + `</title>`,
		`data-billing-admin-unpaid="UBY-2026-0031"`, ` VS 20260031`, `ui-badge-overdue`, `05.11.2026`, // overdue badge with the date
		`action="/admin/fakturace/31/zaplaceno"`, `action="/admin/fakturace/31/storno"`, `name="paid_on"`, `value="2026-11-13"`,
		`href="/admin/fakturace/export?mesic=2026-11"`, `value="2026-11"`,
		"−1 190 Kč", // the storno row's amount
		`data-billing-admin-portfolio="1"`, `3570 Kč`, `298 Kč`,
		`data-billing-admin-statement`, `enctype="multipart/form-data"`, `who knows`, `50 Kč`,
		`id="funnel-ads-export"`, `href="https://eu.posthog.com"`, `/admin/customers/1`,
	} {
		if !strings.Contains(body, want) {
			t.Errorf("page lacks %q", want)
		}
	}
	// With an overdue invoice the watch card sits above the reports; with none, below the accounts.
	if w, r := strings.Index(body, `id="watch"`), strings.Index(body, `id="reports"`); w < 0 || r < 0 || w > r {
		t.Errorf("watch card position: %d, reports %d", w, r)
	}
	if !strings.Contains(body, `UBY-2026-0031 · 1 190 Kč · 8`) { // 2026-11-13 minus 2026-11-05 is 8 days late
		t.Error("overdue line lacks the invoice, amount and days late")
	}
	// Filters: a search that matches nobody, a state that matches nobody, and one that matches host 1.
	for q, shown := range map[string]bool{"?q=zzz": false, "?state=paused": false, "?state=active": true, "?q=HOST1": true} {
		b := do(t, mux, "GET", "/admin/fakturace"+q, nil, "admin1", false).Body.String()
		if got := strings.Contains(b, `data-billing-admin-portfolio="1"`); got != shown {
			t.Errorf("%s: portfolio row shown = %v, want %v", q, got, shown)
		}
	}
	// A month with nothing in it.
	b := do(t, mux, "GET", "/admin/fakturace?mesic=2020-01", nil, "admin1", false).Body.String()
	if !strings.Contains(b, catalog.T("en", "billing.admin.month.none", nil)) {
		t.Error("empty month shows no empty text")
	}
	// Nothing overdue: the watch card moves below the accounts.
	mustExec(t, pool, `UPDATE platform_invoice SET paid_on = '2026-11-06' WHERE id = 31`)
	b = do(t, mux, "GET", "/admin/fakturace", nil, "admin1", false).Body.String()
	if a, w := strings.Index(b, `id="accounts"`), strings.Index(b, `id="watch"`); a < 0 || w < a {
		t.Errorf("watch card below accounts: %d %d", a, w)
	}
	if !strings.Contains(b, `data-billing-admin-watch="none"`) {
		t.Error("no empty watch text")
	}
	// Access.
	if rec = do(t, mux, "GET", "/admin/fakturace", nil, "host1", false); rec.Code != 403 {
		t.Errorf("host: %d", rec.Code)
	}
	if rec = do(t, mux, "GET", "/admin/fakturace", nil, "", false); rec.Code != 303 || rec.Header().Get("Location") != "/login?next=/admin/fakturace" {
		t.Errorf("visitor: %d %q", rec.Code, rec.Header().Get("Location"))
	}
}
