package billingweb

import (
	"net/http"
	"net/url"
	"testing"
)

// Parity: routes/billing.py plan_invoice_pdf, plan_cancel, plan_resume (lines
// 149-189) and routes/admin_billing.py billing_admin_pdf (108-117).

func TestHostInvoicePDF(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	blob := seedInvoice(t, pool, 11, 1, "UBY-2026-0011", "invoice", 119000)
	seedInvoice(t, pool, 12, 2, "UBY-2026-0012", "invoice", 119000)
	seedInvoice(t, pool, 13, nil, "UBY-2026-0013", "invoice", 119000)
	mux := testMux(pool, testEnvMap(nil))

	rec := do(t, mux, "GET", "/predplatne/faktury/11.pdf", nil, "host1", false)
	if rec.Code != 200 || rec.Body.String() != string(blob) {
		t.Fatalf("own invoice: %d %q", rec.Code, rec.Body.String())
	}
	if got := rec.Header().Get("Content-Type"); got != "application/pdf" {
		t.Errorf("content type %q", got)
	}
	if got := rec.Header().Get("Content-Disposition"); got != `inline; filename="UBY-2026-0011.pdf"` {
		t.Errorf("content disposition %q", got)
	}
	for _, p := range []string{"/predplatne/faktury/12.pdf", "/predplatne/faktury/13.pdf", "/predplatne/faktury/99.pdf"} {
		rec = do(t, mux, "GET", p, nil, "host1", false)
		if rec.Code != 303 || rec.Header().Get("Location") != "/predplatne" {
			t.Errorf("%s: %d %q", p, rec.Code, rec.Header().Get("Location"))
		}
	}
	// An admin previewing host1's workspace sees host1's invoice, as Python's workspace owner does.
	if rec = do(t, mux, "GET", "/predplatne/faktury/11.pdf", nil, "admin_imp", false); rec.Code != 200 {
		t.Errorf("impersonating admin: %d", rec.Code)
	}
	if rec = do(t, mux, "GET", "/predplatne/faktury/11.pdf", nil, "", false); rec.Code != 303 ||
		rec.Header().Get("Location") != "/login?next=/predplatne/faktury/11.pdf" {
		t.Errorf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	if rec = do(t, mux, "GET", "/predplatne/faktury/11", nil, "host1", false); rec.Code != 404 {
		t.Errorf("no .pdf: %d", rec.Code)
	}
	if rec = do(t, mux, "GET", "/predplatne/faktury/abc.pdf", nil, "host1", false); rec.Code != 422 {
		t.Errorf("not a number: %d", rec.Code)
	}
	mustExec(t, pool, `UPDATE platform_invoice SET pdf_sha256 = 'bad' WHERE id = 11`)
	if rec = do(t, mux, "GET", "/predplatne/faktury/11.pdf", nil, "host1", false); rec.Code != 500 {
		t.Errorf("changed bytes: %d", rec.Code)
	}
	mustExec(t, pool, `UPDATE platform_invoice SET pdf_blob = NULL WHERE id = 11`)
	if rec = do(t, mux, "GET", "/predplatne/faktury/11.pdf", nil, "host1", false); rec.Code != 500 {
		t.Errorf("missing bytes: %d", rec.Code)
	}
}

func TestAdminInvoicePDF(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	blob := seedInvoice(t, pool, 12, 2, "UBY-2026-0012", "invoice", 119000)
	mux := testMux(pool, testEnvMap(nil))

	rec := do(t, mux, "GET", "/admin/fakturace/12.pdf", nil, "admin1", false)
	if rec.Code != 200 || rec.Body.String() != string(blob) {
		t.Fatalf("admin: %d", rec.Code)
	}
	if rec = do(t, mux, "GET", "/admin/fakturace/99.pdf", nil, "admin1", false); rec.Code != 303 ||
		rec.Header().Get("Location") != "/admin/fakturace" {
		t.Errorf("missing invoice: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	rec = do(t, mux, "GET", "/admin/fakturace/12.pdf", nil, "host1", false)
	if rec.Code != 403 || rec.Body.String() != "Administrators only." || rec.Header().Get("Content-Type") != "" {
		t.Errorf("host: %d %q %q", rec.Code, rec.Body.String(), rec.Header().Get("Content-Type"))
	}
	if rec = do(t, mux, "GET", "/admin/fakturace/12.pdf", nil, "", false); rec.Code != 303 {
		t.Errorf("signed out: %d", rec.Code)
	}
}

func TestCancelResume(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	seedAccount(t, pool, 1, "active", "standard", "year")
	mux := testMux(pool, testEnvMap(nil))
	state := catalog.T("en", "billing.order.error.state", nil)

	rec := do(t, mux, "POST", "/predplatne/zrusit", nil, "host1", false)
	loc := location(t, rec)
	if rec.Code != 303 || loc.Path != "/predplatne" || loc.Query().Get("msg") != catalog.T("en", "billing.cancel.done", nil) {
		t.Fatalf("cancel: %d %s", rec.Code, rec.Header().Get("Location"))
	}
	if got := queryString(t, pool, `SELECT status || ' ' || cancel_at_period_end FROM billing_account WHERE owner_user_id = 1`); got != "canceling 1" {
		t.Errorf("after cancel: %s", got)
	}
	if got := queryString(t, pool, `SELECT actor || ' ' || detail || ' ' || actor_user_id FROM audit WHERE action = 'billing_status'`); got != "host1 active->canceling 1" {
		t.Errorf("audit: %s", got)
	}
	// Cancelling twice is refused with the state error.
	rec = do(t, mux, "POST", "/predplatne/zrusit", nil, "host1", false)
	if loc = location(t, rec); loc.Query().Get("err") != state {
		t.Errorf("second cancel: %s", rec.Header().Get("Location"))
	}
	rec = do(t, mux, "POST", "/predplatne/obnovit", nil, "host1", false)
	if loc = location(t, rec); loc.Query().Get("msg") != catalog.T("en", "billing.resume.done", nil) {
		t.Errorf("resume: %s", rec.Header().Get("Location"))
	}
	if got := queryString(t, pool, `SELECT status || ' ' || cancel_at_period_end FROM billing_account WHERE owner_user_id = 1`); got != "active 0" {
		t.Errorf("after resume: %s", got)
	}
	rec = do(t, mux, "POST", "/predplatne/obnovit", nil, "host1", false)
	if loc = location(t, rec); loc.Query().Get("err") != state {
		t.Errorf("second resume: %s", rec.Header().Get("Location"))
	}
	// No billing row: refused. Billing off: refused, nothing written.
	if loc = location(t, do(t, mux, "POST", "/predplatne/zrusit", nil, "host2", false)); loc.Query().Get("err") != state {
		t.Errorf("no account: %s", loc)
	}
	off := testMux(pool, testEnvMap(map[string]string{"UBYHOST_BILLING_ENABLED": ""}))
	if loc = location(t, do(t, off, "POST", "/predplatne/zrusit", nil, "host1", false)); loc.Query().Get("err") != state {
		t.Errorf("billing off: %s", loc)
	}
	if got := queryString(t, pool, `SELECT status FROM billing_account WHERE owner_user_id = 1`); got != "active" {
		t.Errorf("billing off changed the account: %s", got)
	}
}

func TestPausedHostStillPostsToPlanPage(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	seedAccount(t, pool, 1, "paused", "standard", "month")
	mux := testMux(pool, testEnvMap(nil))
	rec := do(t, mux, "POST", "/predplatne/zrusit", nil, "host1", false)
	loc := location(t, rec)
	// Python's _READ_ONLY_OPEN_PREFIXES lets /predplatne through; hostweb.Login alone would send ?paused=1.
	if rec.Code != 303 || loc.Query().Get("paused") != "" || loc.Query().Get("err") == "" {
		t.Errorf("paused POST: %d %s", rec.Code, rec.Header().Get("Location"))
	}
}

func TestCSRFRequired(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	seedAccount(t, pool, 1, "active", "standard", "year")
	mux := testMux(pool, testEnvMap(nil))
	for _, p := range []string{"/predplatne/zrusit", "/predplatne/obnovit"} {
		rec := do(t, mux, "POST", p, url.Values{}, "host1", true)
		if rec.Code == http.StatusOK || rec.Code != 303 {
			t.Errorf("%s without CSRF: %d", p, rec.Code)
		}
	}
	if got := queryString(t, pool, `SELECT status FROM billing_account WHERE owner_user_id = 1`); got != "active" {
		t.Errorf("a request without a token changed the account: %s", got)
	}
}
