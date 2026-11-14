package invoices

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// testCall is a signed-in call for the transaction helpers.
func (a *testApp) testCall(owner int64, username string) *call {
	return &call{
		deps: deps{pool: a.pool, getenv: testEnv(), now: func() time.Time { return testNow }},
		r:    httptest.NewRequest("POST", "/", nil), at: testNow, lang: "cs", owner: owner,
		h: &session.Host{Account: session.Account{ID: owner, Username: username}, Workspace: session.Account{ID: owner}},
	}
}

func TestIssueNumbersAndStoredPDF(t *testing.T) {
	app, seed := newTestApp(t)
	e := app.entityRow(seed.Entity)
	id1, n1 := app.issueFor(e, seed.Stay, nil, 1)
	_, n2 := app.issueFor(e, seed.StayB, nil, 1)
	if n1 != "2026-0001" || n2 != "2026-0002" {
		t.Fatalf("numbers %q %q", n1, n2)
	}
	var vs, kind, issuedAt, sum string
	var blob []byte
	var issuedBy *int64
	var total int64
	if err := app.pool.QueryRow(context.Background(),
		`SELECT vs, kind, issued_at, pdf_blob, pdf_sha256, issued_by, total_haler FROM invoice WHERE id = $1`, id1).
		Scan(&vs, &kind, &issuedAt, &blob, &sum, &issuedBy, &total); err != nil {
		t.Fatal(err)
	}
	digest := sha256.Sum256(blob)
	if vs != "20260001" || kind != "invoice" || total != 150000 || hex.EncodeToString(digest[:]) != sum ||
		!strings.HasPrefix(string(blob), "%PDF") || issuedBy == nil || *issuedBy != 1 || issuedAt != "2026-11-13T10:00:00+00:00" {
		t.Fatalf("stored row: vs=%s kind=%s total=%d issuedBy=%v issuedAt=%s", vs, kind, total, issuedBy, issuedAt)
	}
	if got := app.count(`SELECT COUNT(*) FROM invoice_item WHERE invoice_id = $1 AND position = 1 AND kind = 'accommodation'`, id1); got != 1 {
		t.Fatalf("items: %d", got)
	}
	if got := app.count(`SELECT last_no FROM invoice_sequence WHERE legal_entity_id = $1 AND year = 2026`, seed.Entity); got != 2 {
		t.Fatalf("last_no %d", got)
	}
	again, err := downloadPDF(context.Background(), app.pool, id1)
	if err != nil || string(again) != string(blob) {
		t.Fatalf("download: %v", err)
	}
}

func TestIssuedInvoiceIsImmutable(t *testing.T) {
	app, seed := newTestApp(t)
	id, _ := app.issueFor(app.entityRow(seed.Entity), seed.Stay, nil, 1)
	if _, err := app.pool.Exec(context.Background(), `UPDATE invoice SET total_haler = 1 WHERE id = $1`, id); err == nil {
		t.Fatal("an issued invoice must not change")
	}
}

func TestDownloadRefusesMissingOrChangedPDF(t *testing.T) {
	app, seed := newTestApp(t)
	ctx := context.Background()
	if _, err := downloadPDF(ctx, app.pool, 999); err == nil {
		t.Error("no such invoice")
	}
	// A row without a stored PDF (not issued through this code) is an error.
	if _, err := app.pool.Exec(ctx,
		`INSERT INTO invoice (id, legal_entity_id, kind, seq_year, seq_no, number, vs, lang, vat_status, issue_date, seller_name, seller_seat, buyer_name, total_haler, created_at)
		 VALUES (900, $1, 'invoice', 2026, 900, 'X-900', '900', 'cs', 'non_payer', '2026-11-01', 's', 's', 'b', 100, '2026-11-01')`, seed.Entity); err != nil {
		t.Fatal(err)
	}
	if _, err := downloadPDF(ctx, app.pool, 900); err == nil || err.Error() != "invoice_pdf_missing" {
		t.Errorf("missing pdf: %v", err)
	}
	if _, err := app.pool.Exec(ctx, `UPDATE invoice SET pdf_blob = '\x25504446', pdf_sha256 = 'deadbeef' WHERE id = 900`); err != nil {
		t.Fatal(err)
	}
	if _, err := downloadPDF(ctx, app.pool, 900); err == nil || err.Error() != "invoice_pdf_mismatch" {
		t.Errorf("changed pdf: %v", err)
	}
}

func TestNumberingPrefixAndNextNumber(t *testing.T) {
	app, seed := newTestApp(t)
	ctx := context.Background()
	if _, err := app.pool.Exec(ctx, `UPDATE legal_entity SET invoice_prefix = 'RB', invoice_next_number = 41, invoice_next_number_year = 2026 WHERE id = $1`, seed.Entity); err != nil {
		t.Fatal(err)
	}
	if n, err := previewNumber(ctx, app.pool, app.entityRow(seed.Entity), 2026); err != nil || n != "RB2026-0001" {
		t.Fatalf("preview %q %v (the preview ignores the next-number override, as Python does)", n, err)
	}
	_, n := app.issueFor(app.entityRow(seed.Entity), seed.Stay, nil, 1)
	if n != "RB2026-0041" {
		t.Fatalf("number %q", n)
	}
	var next *int64
	if err := app.pool.QueryRow(ctx, `SELECT invoice_next_number FROM legal_entity WHERE id = $1`, seed.Entity).Scan(&next); err != nil || next != nil {
		t.Fatalf("next number must be consumed: %v %v", next, err)
	}
	if _, n = app.issueFor(app.entityRow(seed.Entity), seed.StayB, nil, 1); n != "RB2026-0042" {
		t.Fatalf("number %q", n)
	}
	// A next number meant for another year is neither used nor cleared.
	if _, err := app.pool.Exec(ctx, `UPDATE legal_entity SET invoice_next_number = 500, invoice_next_number_year = 2025 WHERE id = $1`, seed.PayerEntity); err != nil {
		t.Fatal(err)
	}
	if _, n = app.issueFor(app.entityRow(seed.PayerEntity), seed.CancelledStay, nil, 1); n != "2026-0001" {
		t.Fatalf("number %q", n)
	}
	if app.count(`SELECT invoice_next_number FROM legal_entity WHERE id = $1`, seed.PayerEntity) != 500 {
		t.Fatal("a next number of another year stays")
	}
	if got := formatNumber("", 2026, 12345); got != "2026-12345" {
		t.Fatal(got)
	}
}

func TestStayLimitAndCancelCycle(t *testing.T) {
	app, seed := newTestApp(t)
	ctx := context.Background()
	e := app.entityRow(seed.Entity)
	c := app.testCall(1, "host1")
	var first int64
	for round := 1; round <= 3; round++ {
		id, _ := app.issueFor(e, seed.Stay, nil, 1)
		if round == 1 {
			first = id
			// A second live invoice for the stay is refused and names the first.
			st, _ := stayFor(ctx, app.pool, 1, itoa(seed.Stay))
			d := buildDraft(e, url.Values{"stay_price": {"1"}, "buyer_name": {"A"}}, pragueDay(testNow), st)
			d.OwnerUserID = ptrOwner(1)
			_, _, err := writeIssued(ctx, app.pool, d, ptrOwner(1), testNow)
			var limit *stayLimit
			if !errors.As(err, &limit) || limit.Key != "invoice.err.stay_has_invoice" || limit.InvoiceID != id {
				t.Fatalf("second live invoice: %v", err)
			}
		}
		if _, err := c.cancelInvoice(id, "Hostovi se změnily plány", ""); err != nil {
			t.Fatalf("cancel %d: %v", round, err)
		}
	}
	// Three invoices have been issued for the stay: the fourth is over the limit.
	st, _ := stayFor(ctx, app.pool, 1, itoa(seed.Stay))
	d := buildDraft(e, url.Values{"stay_price": {"1"}, "buyer_name": {"A"}}, pragueDay(testNow), st)
	d.OwnerUserID = ptrOwner(1)
	_, _, err := writeIssued(ctx, app.pool, d, ptrOwner(1), testNow)
	var limit *stayLimit
	if !errors.As(err, &limit) || limit.Key != "invoice.err.stay_limit" || limit.InvoiceID != 0 {
		t.Fatalf("fourth invoice: %v", err)
	}
	// The first invoice has its storno: negative lines, a pointer back, its own number.
	var kind, number, reason string
	var total, itemGross int64
	var corrects int64
	var correctionDate *string
	if err := app.pool.QueryRow(ctx,
		`SELECT kind, number, total_haler, corrects_invoice_id, correction_reason, correction_date FROM invoice WHERE corrects_invoice_id = $1`, first).
		Scan(&kind, &number, &total, &corrects, &reason, &correctionDate); err != nil {
		t.Fatal(err)
	}
	if kind != "storno" || total != -150000 || corrects != first || reason != "Hostovi se změnily plány" || correctionDate != nil || number != "2026-0002" {
		t.Fatalf("storno: %s %s %d %d %q %v", kind, number, total, corrects, reason, correctionDate)
	}
	if err := app.pool.QueryRow(ctx, `SELECT gross_haler FROM invoice_item WHERE invoice_id = (SELECT id FROM invoice WHERE corrects_invoice_id = $1)`, first).Scan(&itemGross); err != nil || itemGross != -150000 {
		t.Fatalf("storno item: %d %v", itemGross, err)
	}
	if app.count(`SELECT COUNT(*) FROM audit WHERE action = 'invoice_corrected' AND actor = 'host1' AND owner_user_id = 1 AND detail LIKE $1`, "orig="+itoa(first)+" new=%kind=storno reason=Hostovi%") != 1 {
		t.Fatal("audit line of the correction")
	}
}

func TestCancelRefusals(t *testing.T) {
	app, seed := newTestApp(t)
	c := app.testCall(1, "host1")
	id, _ := app.issueFor(app.entityRow(seed.Entity), seed.Stay, nil, 1)
	for _, tc := range []struct {
		name   string
		id     int64
		reason string
		want   string
	}{
		{"short reason", id, "ab c", "reason_required"},
		{"blank reason", id, "   ", "reason_required"},
		{"no such invoice", 999, "dlouhý důvod", "not_cancellable"},
	} {
		if _, err := c.cancelInvoice(tc.id, tc.reason, ""); err == nil || err.Error() != tc.want {
			t.Errorf("%s: %v, want %s", tc.name, err, tc.want)
		}
	}
	newID, err := c.cancelInvoice(id, "dlouhý důvod", "")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := c.cancelInvoice(id, "dlouhý důvod", ""); err == nil || err.Error() != "already_corrected" {
		t.Errorf("twice: %v", err)
	}
	if _, err := c.cancelInvoice(newID, "dlouhý důvod", ""); err == nil || err.Error() != "not_cancellable" {
		t.Errorf("a storno cannot be cancelled: %v", err)
	}
}

func TestCancelPayerGivesCorrectiveWithDate(t *testing.T) {
	app, seed := newTestApp(t)
	ctx := context.Background()
	c := app.testCall(1, "host1")
	id, _ := app.issueFor(app.entityRow(seed.PayerEntity), seed.Stay, url.Values{"stay_vat_rate": {"12"}, "already_paid": {"1"}, "paid_via": {"cash"}}, 1)
	newID, err := c.cancelInvoice(id, "Chybná částka", "2026-11-12")
	if err != nil {
		t.Fatal(err)
	}
	var kind, date, paidOn string
	var base, vat, total int64
	if err := app.pool.QueryRow(ctx, `SELECT kind, correction_date, COALESCE(paid_on,''), total_base_haler, total_vat_haler, total_haler FROM invoice WHERE id = $1`, newID).
		Scan(&kind, &date, &paidOn, &base, &vat, &total); err != nil {
		t.Fatal(err)
	}
	if kind != "corrective" || date != "2026-11-12" || paidOn != "2026-11-13" || base != -150000 || vat != -18000 || total != -168000 {
		t.Fatalf("corrective: %s %s %s %d %d %d", kind, date, paidOn, base, vat, total)
	}
}

func TestHelpersReadOnlyTheHostsOwnRows(t *testing.T) {
	app, seed := newTestApp(t)
	ctx := context.Background()
	if st, err := stayFor(ctx, app.pool, 1, itoa(seed.ForeignStay)); err != nil || st != nil {
		t.Errorf("foreign stay: %v %v", st, err)
	}
	if st, err := stayFor(ctx, app.pool, 1, "99999999999999999999"); err != nil || st != nil {
		t.Errorf("huge id: %v %v", st, err)
	}
	st, err := stayFor(ctx, app.pool, 1, " "+itoa(seed.Stay)+" ")
	if err != nil || st == nil || st.PropertyName != "Chata U Lesa" || st.EntityID == nil || *st.EntityID != seed.Entity {
		t.Fatalf("own stay: %+v %v", st, err)
	}
	list, _ := entities(ctx, app.pool, 1)
	if len(list) != 2 || list[0].Name != "Provoz Dva a.s." || list[1].Name != "Provoz Jedna s.r.o." {
		t.Fatalf("entities ordered by name: %+v", list)
	}
	if e := chosenEntity(list, "3", ""); e == nil || e.ID != list[0].ID {
		t.Error("an entity of another host is never chosen (the first stays)")
	}
	if e := chosenEntity(list, "", "1"); e == nil || e.ID != 1 {
		t.Error("?entity=")
	}
	if e := entityForStay(list, st, "2", ""); e == nil || e.ID != 1 {
		t.Error("the property's operator wins over the form")
	}
	opts, _ := stayOptions(ctx, app.pool, 1, pragueDay(testNow))
	if len(opts) != 2 || opts[0].ID != seed.Stay {
		t.Fatalf("options: %+v", opts)
	}
	for _, o := range opts {
		if o.ID == seed.CancelledStay || o.ID == seed.ForeignStay {
			t.Errorf("option %d must not be offered", o.ID)
		}
	}
	// price hint and remembered payment method come from the last invoice.
	app.issueFor(app.entityRow(seed.Entity), seed.Stay, url.Values{"stay_price": {"1234.5"}, "already_paid": {"1"}, "paid_via": {"booking"}}, 1)
	if h, _ := lastStayPriceHint(ctx, app.pool, 1, seed.Apartment); h != "1234.5" {
		t.Errorf("hint %q", h)
	}
	if h, _ := lastStayPriceHint(ctx, app.pool, 2, seed.Apartment); h != "" {
		t.Errorf("another owner's price must not leak: %q", h)
	}
	if m, _ := rememberedPaidVia(ctx, app.pool, 1, seed.Entity); m["paid_via"] != "booking" {
		t.Errorf("paid via %v", m)
	}
}

func TestHintAmount(t *testing.T) {
	// _last_stay_price_hint: whole amounts print as integers, others with
	// two decimals and the trailing zeros cut.
	for _, c := range []struct {
		gross, qty int64
		want       string
	}{{150000, 1, "1500"}, {150050, 1, "1500.5"}, {150000, 3, "500"}, {100000, 3, "333.33"}, {155, 1, "1.55"}} {
		if got := hintAmount(c.gross, c.qty); got != c.want {
			t.Errorf("%d/%d: got %q want %q", c.gross, c.qty, got, c.want)
		}
	}
}

func TestFormatNumber(t *testing.T) {
	for _, c := range []struct {
		prefix string
		year   int
		seq    int64
		want   string
	}{{"", 2026, 1, "2026-0001"}, {"RB", 2026, 12, "RB2026-0012"}, {"", 2026, 10000, "2026-10000"}, {"X", 2027, 99999, "X2027-99999"}} {
		if got := formatNumber(c.prefix, c.year, c.seq); got != c.want {
			t.Errorf("%v: got %q want %q", c, got, c.want)
		}
	}
}
