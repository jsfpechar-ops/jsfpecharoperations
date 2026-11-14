package invoices

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"testing"
)

// insertInvoice writes a bare invoice row (no PDF, not issued) for list tests.
func (a *testApp) insertInvoice(id, entityID, owner int64, apartment any, kind, number, issueDate, buyer string, total int64, paidOn any, corrects any) {
	a.t.Helper()
	_, err := a.pool.Exec(context.Background(),
		`INSERT INTO invoice (id, legal_entity_id, apartment_id, kind, corrects_invoice_id, seq_year, seq_no, number, vs, lang, vat_status,
		   issue_date, paid_on, seller_name, seller_seat, buyer_name, total_haler, owner_user_id, created_at)
		 VALUES ($1::bigint, $2, $3, $4, $5, 2026, $1::bigint, $6, $1::text, 'cs', 'non_payer', $7, $8, 'Prodejce', 'Sídlo', $9, $10, $11, '2026-11-01')`,
		id, entityID, apartment, kind, corrects, number, issueDate, paidOn, buyer, total, owner)
	if err != nil {
		a.t.Fatalf("insertInvoice: %v", err)
	}
}

func TestListShowsOnlyOwnInvoicesWithStateAndFilters(t *testing.T) {
	app, seed := newTestApp(t)
	app.insertInvoice(1, seed.Entity, 1, seed.Apartment, "invoice", "2026-0001", "2026-11-02", "Jana Nováková", 150000, nil, nil)
	app.insertInvoice(2, seed.Entity, 1, seed.Apartment, "invoice", "2026-0002", "2026-10-02", "Petr Černý", 99000, "2026-10-03", nil)
	app.insertInvoice(3, seed.Entity, 1, seed.Apartment, "invoice", "2026-0003", "2026-10-05", "Zrušený Host", 5000, nil, nil)
	app.insertInvoice(4, seed.Entity, 1, seed.Apartment, "storno", "2026-0004", "2026-10-06", "Zrušený Host", -5000, nil, 3)
	app.insertInvoice(5, seed.ForeignEntity, 2, seed.ForeignApartment, "invoice", "F-0001", "2026-11-02", "Cizí Host", 1000, nil, nil)

	rec := app.get("/invoices", &host1)
	body := rec.Body.String()
	if rec.Code != 200 || !strings.Contains(body, "Jana Nováková") || !strings.Contains(body, "Petr Černý") || strings.Contains(body, "Cizí Host") {
		t.Fatalf("list: %d own and foreign rows wrong", rec.Code)
	}
	if !strings.Contains(body, "1 500,00 Kč") || !strings.Contains(body, "02.11.2026") || !strings.Contains(body, "/invoices/1.pdf") {
		t.Error("amount, date or pdf link missing")
	}
	// state pills: unpaid, paid, cancelled (a storno exists), correction
	for _, want := range []string{`p-warn`, `p-ok`, `p-n`} {
		if !strings.Contains(body, want) {
			t.Errorf("pill %s missing", want)
		}
	}
	count := func(q string) int {
		b := app.get("/invoices?"+q, &host1).Body.String()
		return strings.Count(b, `class="nowrap"`)
	}
	for _, tc := range []struct {
		q    string
		rows int
	}{
		{"", 4}, {"status=unpaid", 1}, {"status=paid", 1}, {"status=correction", 1}, {"status=bogus", 4},
		{"month=2026-10", 3}, {"month=2026-11", 1}, {"month=2027-01", 4}, {"month=1999-01", 4},
		// lower() of a column in the "C" collation lowercases ASCII only, and
		// Python lowers the query fully: "Černý" never matches "černý".
		{"q=nov%C3%A1kov%C3%A1", 1}, {"q=JANA", 1}, {"q=2026-0003", 1}, {"q=ZRU%C5%A0EN%C3%9D", 2},
		{"q=petr", 1}, {"q=%C4%8Dern%C3%BD", 0}, {"q=%25", 0},
		{"apartment=" + itoa(seed.Apartment), 4}, {"apartment=" + itoa(seed.ForeignApartment), 4},
	} {
		if got := count(tc.q); got != tc.rows {
			t.Errorf("?%s: %d rows, want %d", tc.q, got, tc.rows)
		}
	}
	if !strings.Contains(app.get("/invoices?status=unpaid&month=2026-11", &host1).Body.String(), `value="2026-11"`) {
		t.Error("the month input keeps its value")
	}
	if !strings.Contains(app.get("/invoices?q=zzz", &host1).Body.String(), "list-filter-reset") {
		t.Error("an empty filtered list offers the reset")
	}
}

func TestListPagination(t *testing.T) {
	app, seed := newTestApp(t)
	for i := 1; i <= 52; i++ {
		app.insertInvoice(int64(i), seed.Entity, 1, nil, "invoice", fmt.Sprintf("2026-%04d", i), "2026-11-02", "Host", 100, nil, nil)
	}
	first := app.get("/invoices?status=unpaid", &host1).Body.String()
	if strings.Count(first, `class="nowrap"`) != 50 || !strings.Contains(first, "/invoices?status=unpaid&amp;page=2") {
		t.Error("page 1: 50 rows and a next link that keeps the filter")
	}
	second := app.get("/invoices?status=unpaid&page=2", &host1).Body.String()
	if strings.Count(second, `class="nowrap"`) != 2 {
		t.Error("page 2 has the last two")
	}
	if strings.Count(app.get("/invoices?page=junk", &host1).Body.String(), `class="nowrap"`) != 50 {
		t.Error("a bad page number reads as 1")
	}
	if strings.Count(app.get("/invoices?page=0", &host1).Body.String(), `class="nowrap"`) != 50 {
		t.Error("page 0 reads as 1")
	}
}

func TestListNeedsSignIn(t *testing.T) {
	app, _ := newTestApp(t)
	rec := app.get("/invoices", nil)
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?next=/invoices" {
		t.Fatalf("%d %q", rec.Code, rec.Header().Get("Location"))
	}
}

func TestDetailPageNonPayerAndPayer(t *testing.T) {
	app, seed := newTestApp(t)
	idA, numA := app.issueFor(app.entityRow(seed.Entity), seed.Stay, nil, 1)
	idB, _ := app.issueFor(app.entityRow(seed.PayerEntity), seed.StayB, url.Values{"stay_vat_rate": {"21"}, "already_paid": {"1"}, "paid_via": {"cash"}}, 1)

	body := app.get("/invoices/"+itoa(idA), &host1).Body.String()
	for _, want := range []string{"Faktura " + numA, "1 500,00 Kč", "Zaznamenat platbu", "/invoices/" + itoa(idA) + "/send", `action="/invoices/` + itoa(idA) + `/cancel"`,
		"jana@example.test", "/reservations/11", "next=/invoices/" + itoa(idA) + "#entity-invoice"} {
		if !strings.Contains(body, want) {
			t.Errorf("non-payer detail lacks %q", want)
		}
	}
	if strings.Contains(body, "correction_date") {
		t.Error("only a VAT payer is asked for a correction date")
	}
	payer := app.get("/invoices/"+itoa(idB), &host1).Body.String()
	for _, want := range []string{"correction_date", "1 815,00 Kč", "315,00 Kč", "1 500,00 Kč", "21 %", "ui-badge-done"} {
		if !strings.Contains(payer, want) {
			t.Errorf("payer detail lacks %q", want)
		}
	}
	if strings.Contains(payer, `action="/invoices/`+itoa(idB)+`/paid"`) {
		t.Error("a paid invoice has no mark-paid button")
	}
	// After a storno the original has no cancel form and the storno shows its kind.
	c := app.testCall(1, "host1")
	stornoID, err := c.cancelInvoice(idA, "Chybný pobyt", "")
	if err != nil {
		t.Fatal(err)
	}
	storno := app.get("/invoices/"+itoa(stornoID), &host1).Body.String()
	if strings.Contains(storno, "/cancel") || strings.Contains(storno, "/paid") || !strings.Contains(storno, "-1 500,00 Kč") {
		t.Error("storno detail")
	}
}

func TestDetailRefusals(t *testing.T) {
	app, seed := newTestApp(t)
	id, _ := app.issueFor(app.entityRow(seed.Entity), seed.Stay, nil, 1)
	rec := app.get("/invoices/"+itoa(id), &host2)
	if rec.Code != 303 || !strings.HasPrefix(rec.Header().Get("Location"), "/invoices?err=") {
		t.Errorf("another host's invoice: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	if rec := app.get("/invoices/99999", &host1); rec.Code != 303 || !strings.HasPrefix(rec.Header().Get("Location"), "/invoices?err=") {
		t.Errorf("no such invoice: %d", rec.Code)
	}
	if rec := app.get("/invoices/99999999999999999999", &host1); rec.Code != 303 {
		t.Errorf("huge id: %d", rec.Code)
	}
	if rec := app.get("/invoices/abc", &host1); rec.Code != 404 || rec.Body.String() != `{"detail":"Not Found"}` {
		t.Errorf("non-number: %d %s", rec.Code, rec.Body.String())
	}
	if rec := app.get("/invoices/preview", &host1); rec.Code != 405 || rec.Header().Get("Allow") != "POST" {
		t.Errorf("preview by GET: %d", rec.Code)
	}
	if rec := app.get("/invoices/"+itoa(id), nil); rec.Code != 303 || rec.Header().Get("Location") != "/login?next=/invoices/"+itoa(id) {
		t.Errorf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
}

func TestPyQuoteAndJSONString(t *testing.T) {
	if got := pyQuote("/invoices/new?reservation_id=41&entity=7"); got != "/invoices/new%3Freservation_id%3D41%26entity%3D7" {
		t.Error(got)
	}
	if got := pyQuote("č x"); got != "%C4%8D%20x" {
		t.Error(got)
	}
	if got := jsonString("a\"b\\c\n"); got != `"a\"b\\c\u000a"` {
		t.Error(got)
	}
}
