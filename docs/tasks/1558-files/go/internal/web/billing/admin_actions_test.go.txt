package billingweb

import (
	"bytes"
	"context"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// Parity: routes/admin_billing.py billing_admin_statement and billing_admin_mark_paid
// (lines 72-101), bank_import.record, import_statement, mark_paid_manually (187-236),
// billing_invoices.mark_paid (220-240), billing_jobs.settle (141-163), mail_notify.billing_paid.

func TestPyISODate(t *testing.T) {
	for s, want := range map[string]bool{
		"2026-11-13": true, "20261113": true, "2026-02-29": false, "2024-02-29": true, "2026-W46": true, "2026W46": true,
		"2026W465": true, "2026-W46-5": true, "2026-W53": true, "2026-W54": false, "2025-W53": false, "2026-W00": false,
		"2026-W46-8": false, "2026-W46-0": false, "0001-01-01": true, "0000-01-01": false, "2026-13-01": false,
		"2026/11/13": false, "2026-11-1": false, "": false, "202611": false, "2026-W4": false, "2026W5": false, "20261301": false,
	} {
		if got := pyISODate(s); got != want {
			t.Errorf("pyISODate(%q) = %v, want %v (date.fromisoformat on Python 3.12)", s, got, want)
		}
	}
}

// doUpload sends a multipart POST with one file part (name "statement" unless field is set).
func doUpload(t *testing.T, mux http.Handler, path, field, filename string, content []byte, who string) *httptest.ResponseRecorder {
	t.Helper()
	var body bytes.Buffer
	mw := multipart.NewWriter(&body)
	if filename != "" || content != nil {
		fw, err := mw.CreateFormFile(field, filename)
		if err != nil {
			t.Fatal(err)
		}
		_, _ = fw.Write(content)
	}
	_ = mw.Close()
	req := httptest.NewRequest("POST", path, &body)
	req.Header.Set("Content-Type", mw.FormDataContentType())
	ck, token := csrfPair(t, testNow)
	req.AddCookie(ck)
	req.Header.Set("X-CSRF-Token", token)
	req.AddCookie(&http.Cookie{Name: session.CookieName, Value: sessionFor(who, testNow)})
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

const statementCSV = "id;date;amount;vs;message\n" +
	"t1;2026-11-12;1190,00;20260031;paid in full\n" +
	"t2;2026-11-12;1500,00;20260032;paid too much\n" +
	"t3;2026-11-12;100,00;20260033;paid too little\n" +
	"t4;2026-11-12;5,00;20269999;nobody's\n" +
	"t5;2026-11-12;7,00;abc;not ours\n"

func TestStatementUpload(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	seedAccount(t, pool, 1, "overdue", "standard", "year")
	seedInvoice(t, pool, 31, 1, "UBY-2026-0031", "invoice", 119000)
	mustExec(t, pool, `UPDATE platform_invoice SET due_date = '2026-11-05' WHERE id = 31`)
	seedInvoice(t, pool, 32, 2, "UBY-2026-0032", "invoice", 119000)
	seedInvoice(t, pool, 33, 1, "UBY-2026-0033", "supplementary", 50000)
	mustExec(t, pool, `UPDATE platform_invoice SET period_from = '2026-11-02', due_date = '2026-12-01' WHERE id = 33`)
	mux := testMux(pool, testEnvMap(nil))

	rec := doUpload(t, mux, "/admin/fakturace/vypis", "statement", "statement.csv", []byte(statementCSV), "admin1")
	loc := location(t, rec)
	want := catalog.T("en", "billing.admin.statement.done", map[string]any{"matched": 1, "unmatched": 1, "partial": 1, "overpaid": 1, "seen": 0, "ignored": 1})
	if rec.Code != 303 || loc.Path != "/admin/fakturace" || loc.Query().Get("msg") != want {
		t.Fatalf("upload: %d %s (want %q)", rec.Code, rec.Header().Get("Location"), want)
	}
	for sql, want := range map[string]string{
		// Invoice 31 matched exactly, 32 overpaid: both paid on the statement's date, by the bank.
		`SELECT paid_on || ' ' || paid_via FROM platform_invoice WHERE id = 31`:  "2026-11-12 bank_auto",
		`SELECT paid_on || ' ' || paid_via FROM platform_invoice WHERE id = 32`:  "2026-11-12 bank_auto",
		`SELECT COALESCE(paid_on, '<null>') FROM platform_invoice WHERE id = 33`: "<null>",
		// The payments: status and matched invoice (a partial payment is linked to its invoice, which stays open).
		`SELECT string_agg(bank_tx_id || '=' || status || ':' || COALESCE(matched_invoice_id::text, '-'), ' ' ORDER BY bank_tx_id) FROM bank_payment`: "csv-t1=matched:31 csv-t2=overpaid:32 csv-t3=partial:33 csv-t4=unmatched:-",
		// Host 1 had nothing else overdue, so the account settles back to active, audited as system with the operator's id.
		`SELECT status FROM billing_account WHERE owner_user_id = 1`:                                                                                                   "active",
		`SELECT actor || ' ' || detail || ' ' || actor_user_id FROM audit WHERE action = 'billing_status'`:                                                             "system overdue->active 3",
		`SELECT string_agg(actor || ' ' || detail || ' ' || owner_user_id || ' ' || actor_user_id, '|' ORDER BY id) FROM audit WHERE action = 'platform_invoice_paid'`: "admin1 UBY-2026-0031 bank_auto 1 3|admin1 UBY-2026-0032 bank_auto 2 3",
		// The import line belongs to the operator's own workspace (id 3).
		`SELECT actor || ' ' || detail || ' ' || owner_user_id FROM audit WHERE action = 'bank_statement_import'`: "admin1 matched=1 unmatched=1 partial=1 overpaid=1 seen=0 ignored=1 3",
		// One confirmation per invoice, to the one address of each host, with a copy to the operator.
		`SELECT string_agg(idempotency_key || ' ' || to_email || ' ' || cc_email, '|' ORDER BY idempotency_key) FROM email_outbox WHERE kind = 'billing_paid'`: "billing-paid-31-buyer host1@example.test support@ubyhost.com|billing-paid-32-buyer host2@example.test support@ubyhost.com",
		`SELECT subject FROM email_outbox WHERE idempotency_key = 'billing-paid-31-buyer'`:                                                                     "Faktura UBY-2026-0031 je zaplacena",
	} {
		if got := queryString(t, pool, sql); got != want {
			t.Errorf("%s\n got: %s\nwant: %s", sql, got, want)
		}
	}
	// The same statement again: every credit is "seen", nothing is paid twice, no second mail.
	rec = doUpload(t, mux, "/admin/fakturace/vypis", "statement", "statement.csv", []byte(statementCSV), "admin1")
	want = catalog.T("en", "billing.admin.statement.done", map[string]any{"matched": 0, "unmatched": 0, "partial": 0, "overpaid": 0, "seen": 4, "ignored": 1})
	if loc = location(t, rec); loc.Query().Get("msg") != want {
		t.Errorf("second upload: %s", rec.Header().Get("Location"))
	}
	if got := queryString(t, pool, `SELECT COUNT(*)::text FROM email_outbox WHERE kind = 'billing_paid'`); got != "2" {
		t.Errorf("mails after the second upload: %s", got)
	}
}

func TestStatementUploadRefusals(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	mux := testMux(pool, testEnvMap(nil))
	missing := catalog.T("en", "billing.admin.statement.missing", nil)
	unreadable := catalog.T("en", "billing.admin.statement.unreadable", nil)
	// No file part, an empty file name, a wrong field name, and a url-encoded post: all "missing".
	for name, rec := range map[string]*httptest.ResponseRecorder{
		"no part":    doUpload(t, mux, "/admin/fakturace/vypis", "", "", nil, "admin1"),
		"empty name": doUpload(t, mux, "/admin/fakturace/vypis", "statement", "", []byte("x"), "admin1"),
		"wrong name": doUpload(t, mux, "/admin/fakturace/vypis", "other", "a.csv", []byte("x"), "admin1"),
		"urlencoded": do(t, mux, "POST", "/admin/fakturace/vypis", url.Values{"statement": {"a.csv"}}, "admin1", false),
	} {
		if loc := location(t, rec); rec.Code != 303 || loc.Query().Get("err") != missing {
			t.Errorf("%s: %d %s", name, rec.Code, rec.Header().Get("Location"))
		}
	}
	// Over 5 MiB, and bytes the parser refuses (no header row): "unreadable".
	big := bytes.Repeat([]byte("a"), statementMaxBytes+1)
	for name, content := range map[string][]byte{"too big": big, "no header": []byte("hello\nworld\n"), "cp1250 hole": {0x81, 0x41}} {
		rec := doUpload(t, mux, "/admin/fakturace/vypis", "statement", "s.csv", content, "admin1")
		if loc := location(t, rec); rec.Code != 303 || loc.Query().Get("err") != unreadable {
			t.Errorf("%s: %d %s", name, rec.Code, rec.Header().Get("Location"))
		}
	}
	// Exactly 5 MiB is read (here it has no header row, so it is unreadable as a statement, not as a size).
	if got := queryString(t, pool, `SELECT COUNT(*)::text FROM bank_payment`); got != "0" {
		t.Errorf("payments: %s", got)
	}
	// A host is refused before anything is read; a visitor goes to the login page; no token is a CSRF refusal.
	if rec := doUpload(t, mux, "/admin/fakturace/vypis", "statement", "s.csv", []byte(statementCSV), "host1"); rec.Code != 403 {
		t.Errorf("host: %d", rec.Code)
	}
	if rec := do(t, mux, "POST", "/admin/fakturace/vypis", url.Values{}, "admin1", true); rec.Code != 303 {
		t.Errorf("no token: %d", rec.Code)
	}
}

func TestMarkPaid(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	seedAccount(t, pool, 1, "paused", "standard", "month")
	seedInvoice(t, pool, 41, 1, "UBY-2026-0041", "invoice", 14900)
	mustExec(t, pool, `UPDATE platform_invoice SET period_from = '2026-11-01', period_to = '2026-11-30' WHERE id = 41`)
	seedInvoice(t, pool, 42, 1, "UBY-2026-0042", "storno", -14900)
	mux := testMux(pool, testEnvMap(nil))
	post := func(path, who string, form url.Values) *httptest.ResponseRecorder {
		return do(t, mux, "POST", path, form, who, false)
	}

	for _, bad := range []string{"", "13.11.2026", "2026-02-30", "2026-11-13 x"} {
		rec := post("/admin/fakturace/41/zaplaceno", "admin1", url.Values{"paid_on": {bad}})
		if loc := location(t, rec); loc.Query().Get("err") != catalog.T("en", "billing.admin.paid.bad_date", nil) {
			t.Errorf("paid_on %q: %s", bad, rec.Header().Get("Location"))
		}
	}
	// A storno and a missing invoice are not open.
	for _, id := range []string{"42", "99"} {
		rec := post("/admin/fakturace/"+id+"/zaplaceno", "admin1", url.Values{"paid_on": {"2026-11-13"}})
		if loc := location(t, rec); loc.Query().Get("err") != catalog.T("en", "billing.admin.paid.not_open", nil) {
			t.Errorf("invoice %s: %s", id, rec.Header().Get("Location"))
		}
	}
	// A paused account with its current period invoiced and now paid comes back (billing_jobs.settle).
	rec := post("/admin/fakturace/41/zaplaceno", "admin1", url.Values{"paid_on": {" 2026-11-13 "}})
	if loc := location(t, rec); rec.Code != 303 || loc.Query().Get("msg") != catalog.T("en", "billing.admin.paid.done", nil) {
		t.Fatalf("mark paid: %d %s", rec.Code, rec.Header().Get("Location"))
	}
	for sql, want := range map[string]string{
		`SELECT paid_on || ' ' || paid_via FROM platform_invoice WHERE id = 41`:             "2026-11-13 bank_manual",
		`SELECT status FROM billing_account WHERE owner_user_id = 1`:                        "active",
		`SELECT actor || ' ' || detail FROM audit WHERE action = 'platform_invoice_paid'`:   "admin1 UBY-2026-0041 bank_manual",
		`SELECT subject || ' | ' || to_email FROM email_outbox WHERE kind = 'billing_paid'`: "Faktura UBY-2026-0041 je zaplacena | host1@example.test",
	} {
		if got := queryString(t, pool, sql); got != want {
			t.Errorf("%s\n got: %s\nwant: %s", sql, got, want)
		}
	}
	// Paid twice: not open any more, and nothing is mailed again.
	rec = post("/admin/fakturace/41/zaplaceno", "admin1", url.Values{"paid_on": {"2026-11-14"}})
	if loc := location(t, rec); loc.Query().Get("err") != catalog.T("en", "billing.admin.paid.not_open", nil) {
		t.Errorf("second payment: %s", rec.Header().Get("Location"))
	}
	// A compact date is accepted, as date.fromisoformat does, and stored as typed.
	seedInvoice(t, pool, 43, 2, "UBY-2026-0043", "invoice", 14900)
	post("/admin/fakturace/43/zaplaceno", "admin1", url.Values{"paid_on": {"20261113"}})
	if got := queryString(t, pool, `SELECT paid_on FROM platform_invoice WHERE id = 43`); got != "20261113" {
		t.Errorf("compact date: %s", got)
	}
	// Not an integer: 422 before the login check; a host: 403; no token: refused.
	if rec = post("/admin/fakturace/abc/zaplaceno", "", url.Values{}); rec.Code != 422 {
		t.Errorf("abc: %d", rec.Code)
	}
	if rec = post("/admin/fakturace/41/zaplaceno", "host1", url.Values{"paid_on": {"2026-11-13"}}); rec.Code != 403 {
		t.Errorf("host: %d", rec.Code)
	}
	if rec = do(t, mux, "POST", "/admin/fakturace/41/zaplaceno", url.Values{}, "admin1", true); rec.Code != 303 {
		t.Errorf("no token: %d", rec.Code)
	}
}

func TestSettle(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	ctx := context.Background()
	p := payer{pool: pool, username: "admin1", userID: 3, workspace: 3, today: testNow}
	// A paused account with no paid current-period invoice stays paused; one without a plan is never touched.
	seedAccount(t, pool, 1, "paused", "standard", "month")
	if moved, err := p.settle(ctx, 1); err != nil || moved {
		t.Fatalf("paused, nothing paid: %v %v", moved, err)
	}
	seedInvoice(t, pool, 51, 1, "UBY-2026-0051", "invoice", 14900)
	mustExec(t, pool, `UPDATE platform_invoice SET paid_on = '2026-11-01', period_to = '2026-11-30' WHERE id = 51`)
	// An unpaid invoice past its due date (2026-11-12 < today 2026-11-13) blocks it.
	seedInvoice(t, pool, 52, 1, "UBY-2026-0052", "supplementary", 5000)
	mustExec(t, pool, `UPDATE platform_invoice SET due_date = '2026-11-12' WHERE id = 52`)
	if moved, err := p.settle(ctx, 1); err != nil || moved {
		t.Fatalf("still overdue: %v %v", moved, err)
	}
	// Due today is not overdue (the comparison is due_date < today).
	mustExec(t, pool, `UPDATE platform_invoice SET due_date = '2026-11-13' WHERE id = 52`)
	if moved, err := p.settle(ctx, 1); err != nil || !moved {
		t.Fatalf("due today: %v %v", moved, err)
	}
	// An overdue account needs no paid invoice, only nothing overdue.
	mustExec(t, pool, `UPDATE billing_account SET status = 'overdue' WHERE owner_user_id = 1`)
	mustExec(t, pool, `UPDATE platform_invoice SET paid_on = '2026-11-13' WHERE id = 52`)
	if moved, err := p.settle(ctx, 1); err != nil || !moved {
		t.Fatalf("overdue: %v %v", moved, err)
	}
	if moved, err := p.settle(ctx, 1); err != nil || moved {
		t.Fatalf("already active: %v %v", moved, err)
	}
	if moved, err := p.settle(ctx, 2); err != nil || moved {
		t.Fatalf("no account: %v %v", moved, err)
	}
	if !strings.Contains(queryString(t, pool, `SELECT string_agg(detail, ',' ORDER BY id) FROM audit WHERE action = 'billing_status'`), "paused->active,overdue->active") {
		t.Error("audit rows missing")
	}
}
