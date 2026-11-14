package customers

import (
	"context"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	billingweb "github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/billing"
)

// Tests of GET /admin (brief 1593), over the golden seed (today 2026-11-13). The
// counts behind its "System problems" list are tested in ops_test.go.

// homeMux serves GET /admin over the golden seed.
func homeMux(t *testing.T, billing bool) (*http.ServeMux, *pgxpool.Pool) {
	t.Helper()
	g := loadGolden(t)
	pool := dbPool(t)
	seed(t, pool, g)
	base := testGetenv(g.Versions)
	getenv := func(k string) string {
		if k == "UBYHOST_BILLING_ENABLED" && billing {
			return "1"
		}
		return base(k)
	}
	mux := http.NewServeMux()
	mux.Handle("GET /admin", HomeHandler(pool, getenv, func() time.Time { return testNow }))
	return mux, pool
}

func homeLines(t *testing.T, mux *http.ServeMux, lang string) string {
	t.Helper()
	rec := serve(t, mux, call{method: "GET", path: "/admin", lang: lang, payload: map[string]any{"uid": 1, "sv": 1}})
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d: %.200s", rec.Code, rec.Body.String())
	}
	return strings.Join(visibleLines(rec.Body.String()), "\n")
}

func wantLines(t *testing.T, page string, lines ...string) {
	t.Helper()
	for _, l := range lines {
		if !strings.Contains(page, l) {
			t.Errorf("page lacks %q", l)
		}
	}
}

// TestHomePage: the console home over the golden seed (today 2026-11-13).
func TestHomePage(t *testing.T) {
	mux, pool := homeMux(t, true)
	page := homeLines(t, mux, "en")
	wantLines(t, page,
		"Operator", "console", "What needs attention today (2026-11-13).",
		// The four stats: MRR and ARR through money_czk, then the overdue and trialing counts of summary().
		"MRR", "ARR", "Overdue", "On trial",
		"<a href=/admin/customers?state=overdue>", "<a href=/admin/customers?state=trialing>",
		// System problems: no job has a success on record (14 late jobs) and the seeded mail was never sent.
		"System problems", "Background jobs", "E-mail problems",
		"<a href=/admin/operations#ops-jobs>", "<a href=/admin/operations#ops-mail>",
		"Overdue invoices", "Trials ending within 7 days", "Unverified signups", "Ending at renewal",
		// Trials ending 13 to 20 November: customers 14, 6 (Eve), 4 and 15 (Milan); 14 and 4 have no name,
		// so the page prints their id. Unverified sign-ups: customer 4, whose Python row has no username.
		"Eve Ending", "16.11.2026", "Milan Ending Edge", "20.11.2026", "<a href=/admin/customers/14>", "14.11.2026",
		// Hugo cancels at the end of his period.
		"Hugo Canceling", "01.12.2026",
		// An overdue invoice of Gina.
		"Gina Overdue", "<a href=/admin/fakturace/",
	)
	// The MRR and ARR lines are money_czk of the portfolio's whole-crowns figures, as admin_home.html
	// prints them (Python shows them one hundredth of the value; see the brief).
	p, err := billingweb.GetPortfolio(context.Background(), pool, time.Date(2026, 11, 13, 0, 0, 0, 0, time.UTC))
	if err != nil {
		t.Fatal(err)
	}
	wantLines(t, page, moneyCZK(p.MRRCZK), moneyCZK(p.ARRCZK))
	if strings.Contains(page, "All clear") {
		t.Error("the page claims all is clear")
	}
	// Czech.
	cs := homeLines(t, mux, "cs")
	wantLines(t, cs, "Konzole", "operátora", "Co dnes potřebuje pozornost (2026-11-13).", "Problémy systému", "Faktury po splatnosti")
	// Billing off: no stats, and the neutral banner of customers.billing_off.
	mux, _ = homeMux(t, false)
	off := homeLines(t, mux, "en")
	if strings.Contains(off, "MRR") || !strings.Contains(off, "Billing is switched off.") {
		t.Errorf("billing off page: %s", off)
	}
}

// TestHomePageNeedsAdmin: Python's _require_admin on GET /admin.
func TestHomePageNeedsAdmin(t *testing.T) {
	mux, _ := homeMux(t, true)
	rec := serve(t, mux, call{method: "GET", path: "/admin", lang: "en"})
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?next=/admin" {
		t.Fatalf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	rec = serve(t, mux, call{method: "GET", path: "/admin", lang: "en", payload: map[string]any{"uid": 7, "sv": 1}})
	if rec.Code != http.StatusForbidden || rec.Body.String() != "Administrators only." {
		t.Fatalf("host: %d %q", rec.Code, rec.Body.String())
	}
}
