package invoices

import (
	"context"
	"net/http"
	"net/url"
	"strings"
	"testing"
)

func validForm(extra url.Values) url.Values {
	form := url.Values{"reservation_id": {"11"}, "legal_entity_id": {"1"}, "stay_price": {"1500"}, "buyer_name": {"Jana Nováková"},
		"buyer_street": {"Ulice 1"}, "buyer_city": {"Brno"}, "buyer_zip": {"602 00"}, "buyer_country": {"CZE"}, "buyer_email": {"jana@example.test"},
		"already_paid": {"1"}, "paid_via": {"cash"}, "lang": {"cs"}}
	for k, v := range extra {
		form[k] = v
	}
	return form
}

func TestIssueCreatesTheInvoice(t *testing.T) {
	app, seed := newTestApp(t)
	rec := app.do(http.MethodPost, "/invoices", validForm(url.Values{
		"item_kind": {"cleaning"}, "item_description": {""}, "item_quantity": {"2"}, "item_unit": {"ks"}, "item_unit_price": {"100"}, "item_vat_rate": {"21"}}), &host1)
	loc := rec.Header().Get("Location")
	if rec.Code != 303 || !strings.HasPrefix(loc, "/invoices/1?msg=") {
		t.Fatalf("issue: %d %q %s", rec.Code, loc, rec.Body.String())
	}
	if msg, _ := url.QueryUnescape(loc); !strings.Contains(msg, "2026-0001") {
		t.Errorf("the flash names the number: %q", msg)
	}
	var number, kind, buyer, paidOn, paidVia, duzp, label string
	var total int64
	var owner, issuedBy int64
	if err := app.pool.QueryRow(context.Background(),
		`SELECT number, kind, buyer_name, COALESCE(paid_on,''), COALESCE(paid_via,''), COALESCE(duzp,''), COALESCE(stay_label,''), total_haler, owner_user_id, issued_by FROM invoice WHERE id = 1`).
		Scan(&number, &kind, &buyer, &paidOn, &paidVia, &duzp, &label, &total, &owner, &issuedBy); err != nil {
		t.Fatal(err)
	}
	if number != "2026-0001" || kind != "invoice" || buyer != "Jana Nováková" || paidOn != "2026-11-13" || paidVia != "cash" ||
		duzp != "2026-11-13" || total != 170000 || owner != 1 || issuedBy != 1 || label != "Chata U Lesa, 10.11.2026 – 13.11.2026 (3 noci)" {
		t.Fatalf("row: %s %s %s %s %s %s %d %d %d %q", number, kind, buyer, paidOn, paidVia, duzp, total, owner, issuedBy, label)
	}
	if app.count(`SELECT COUNT(*) FROM invoice_item WHERE invoice_id = 1`) != 2 || app.count(`SELECT COUNT(*) FROM audit WHERE action = 'invoice_issued' AND actor = 'host1' AND detail = 'id=1 number=2026-0001 entity=1 total=170000'`) != 1 {
		t.Error("items and the audit line")
	}
	_ = seed
	// the same stay again goes back to the live invoice
	again := app.do(http.MethodPost, "/invoices", validForm(nil), &host1)
	if again.Code != 303 || !strings.HasPrefix(again.Header().Get("Location"), "/invoices/1?err=") {
		t.Errorf("second invoice for the stay: %d %q", again.Code, again.Header().Get("Location"))
	}
	if app.count(`SELECT COUNT(*) FROM invoice`) != 1 {
		t.Error("nothing more was issued")
	}
}

func TestIssuePayerAmounts(t *testing.T) {
	app, _ := newTestApp(t)
	if _, err := app.pool.Exec(context.Background(), `UPDATE apartment SET legal_entity_id = 2 WHERE id = 1`); err != nil {
		t.Fatal(err)
	}
	rec := app.do(http.MethodPost, "/invoices", validForm(url.Values{"legal_entity_id": {"2"}, "stay_price": {"1234,57"}, "stay_vat_rate": {"21"},
		"item_kind": {"stay_fee"}, "item_description": {""}, "item_quantity": {"3"}, "item_unit": {""}, "item_unit_price": {"50"}, "item_vat_rate": {"21"}}), &host1)
	if rec.Code != 303 || !strings.HasPrefix(rec.Header().Get("Location"), "/invoices/1?msg=") {
		t.Fatalf("issue: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	var base, vat, total int64
	if err := app.pool.QueryRow(context.Background(), `SELECT total_base_haler, total_vat_haler, total_haler FROM invoice WHERE id = 1`).Scan(&base, &vat, &total); err != nil {
		t.Fatal(err)
	}
	// 1234.57 at 21 %: base 123457, vat 25926 (25925.97 rounded); the stay fee 3 x 50 is outside VAT.
	if base != 123457+15000 || vat != 25926 || total != 123457+25926+15000 {
		t.Fatalf("totals %d %d %d", base, vat, total)
	}
	if app.count(`SELECT COUNT(*) FROM invoice_item WHERE invoice_id = 1 AND kind = 'stay_fee' AND vat_rate = 0 AND vat_haler = 0`) != 1 {
		t.Error("the stay fee line has VAT 0")
	}
}

func TestIssueValidationErrorsRenderThe422Form(t *testing.T) {
	app, _ := newTestApp(t)
	rec := app.do(http.MethodPost, "/invoices", validForm(url.Values{"buyer_name": {""}, "stay_price": {"abc"}, "note": {"keep me"},
		"item_kind": {"pet"}, "item_description": {""}, "item_quantity": {"0"}, "item_unit": {""}, "item_unit_price": {"5"}, "item_vat_rate": {"21"}}), &host1)
	body := rec.Body.String()
	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("status %d", rec.Code)
	}
	for _, want := range []string{"ui-banner-attention", `value="keep me"`, `value="abc"`, `<option value="pet" selected>`, `value="0" inputmode="numeric"`, `value="Brno"`} {
		if !strings.Contains(body, want) {
			t.Errorf("422 form lacks %q", want)
		}
	}
	if strings.Count(body, "<li>") < 3 {
		t.Error("buyer, amount and quantity errors are listed")
	}
	if app.count(`SELECT COUNT(*) FROM invoice`) != 0 {
		t.Error("nothing was issued")
	}
	// a payer without a DIČ, and a seller without a registry entry
	if _, err := app.pool.Exec(context.Background(), `UPDATE legal_entity SET registry_entry = NULL WHERE id = 1`); err != nil {
		t.Fatal(err)
	}
	if rec := app.do(http.MethodPost, "/invoices", validForm(nil), &host1); rec.Code != 422 {
		t.Errorf("no registry entry: %d", rec.Code)
	}
}

func TestIssueRefusals(t *testing.T) {
	app, seed := newTestApp(t)
	for name, form := range map[string]url.Values{
		"foreign stay":   validForm(url.Values{"reservation_id": {itoa(seed.ForeignStay)}}),
		"cancelled stay": validForm(url.Values{"reservation_id": {itoa(seed.CancelledStay)}}),
		"no stay":        validForm(url.Values{"reservation_id": {""}}),
	} {
		rec := app.do(http.MethodPost, "/invoices", form, &host1)
		if rec.Code != 303 || !strings.HasPrefix(rec.Header().Get("Location"), "/invoices/new?err=") {
			t.Errorf("%s: %d %q", name, rec.Code, rec.Header().Get("Location"))
		}
	}
	if rec := app.do(http.MethodPost, "/invoices", validForm(nil), &host1, true); rec.Code == 303 && strings.HasPrefix(rec.Header().Get("Location"), "/invoices/1") {
		t.Error("no CSRF token, no invoice")
	}
	// a forged operator id of another host is ignored (the property's operator wins)
	if rec := app.do(http.MethodPost, "/invoices", validForm(url.Values{"legal_entity_id": {itoa(seed.ForeignEntity)}}), &host1); rec.Code != 303 {
		t.Errorf("forged operator: %d", rec.Code)
	}
	if app.count(`SELECT COUNT(*) FROM invoice WHERE legal_entity_id = $1`, seed.ForeignEntity) != 0 || app.count(`SELECT COUNT(*) FROM invoice WHERE owner_user_id = 1`) != 1 {
		t.Error("the invoice belongs to host1's operator")
	}
	// no operator at all
	if _, err := app.pool.Exec(context.Background(), `UPDATE legal_entity SET archived_at = '2026-01-02' WHERE owner_user_id = 1`); err != nil {
		t.Fatal(err)
	}
	if rec := app.do(http.MethodPost, "/invoices", validForm(nil), &host1); rec.Code != 303 || !strings.HasPrefix(rec.Header().Get("Location"), "/invoices/new?err=") {
		t.Errorf("no operator: %d %q", rec.Code, rec.Header().Get("Location"))
	}
}

func TestPreviewIsAWatermarkedPDFAndSavesNothing(t *testing.T) {
	app, _ := newTestApp(t)
	rec := app.do(http.MethodPost, "/invoices/preview", validForm(nil), &host1)
	if rec.Code != 200 || rec.Header().Get("Content-Type") != "application/pdf" || rec.Header().Get("Content-Disposition") != `inline; filename="nahled-faktura.pdf"` ||
		!strings.HasPrefix(rec.Body.String(), "%PDF") {
		t.Fatalf("preview: %d %v", rec.Code, rec.Header())
	}
	if app.count(`SELECT COUNT(*) FROM invoice`) != 0 || app.count(`SELECT COUNT(*) FROM invoice_sequence`) != 0 {
		t.Error("a preview issues nothing and takes no number")
	}
	// even an invalid draft previews (no validation, as in Python)
	if rec := app.do(http.MethodPost, "/invoices/preview", validForm(url.Values{"buyer_name": {""}, "stay_price": {"x"}}), &host1); rec.Code != 200 {
		t.Errorf("invalid draft: %d", rec.Code)
	}
	if rec := app.do(http.MethodPost, "/invoices/preview", validForm(url.Values{"reservation_id": {"13"}}), &host1); rec.Code != 303 || !strings.HasPrefix(rec.Header().Get("Location"), "/invoices/new?err=") {
		t.Errorf("foreign stay: %d", rec.Code)
	}
}

func TestFillFromGuestKeepsWhatWasTyped(t *testing.T) {
	app, _ := newTestApp(t)
	app.seedGuest(11, "Hans", "Mueller", "Hauptstrasse 1", "Berlin", "DEU", true)
	rec := app.do(http.MethodPost, "/invoices", validForm(url.Values{"buyer_name": {"Own Name"}, "buyer_street": {""}, "buyer_city": {""}, "buyer_country": {"DEU"},
		"fill_from_guest": {"1"}, "note": {"typed note"}}), &host1)
	body := rec.Body.String()
	if rec.Code != 200 || !strings.Contains(body, `value="Own Name"`) || !strings.Contains(body, `value="Hauptstrasse 1"`) || !strings.Contains(body, `value="Berlin"`) ||
		!strings.Contains(body, `value="typed note"`) || strings.Contains(body, `value="Hans Mueller"`) {
		t.Fatalf("fill from guest fills blanks only: %d", rec.Code)
	}
	if app.count(`SELECT COUNT(*) FROM invoice`) != 0 {
		t.Error("a fill button issues nothing")
	}
	// no guest: the error line
	app2, _ := newTestApp(t)
	rec = app2.do(http.MethodPost, "/invoices", validForm(url.Values{"fill_from_guest": {"1"}}), &host1)
	if rec.Code != 200 || !strings.Contains(rec.Body.String(), "ui-banner-attention") {
		t.Errorf("no guest: %d", rec.Code)
	}
	// any other fill_ key re-renders without issuing
	if rec := app2.do(http.MethodPost, "/invoices", validForm(url.Values{"fill_other": {"1"}}), &host1); rec.Code != 200 || app2.count(`SELECT COUNT(*) FROM invoice`) != 0 {
		t.Errorf("fill_other: %d", rec.Code)
	}
	// a radio value 0 survives the re-render
	rec = app2.do(http.MethodPost, "/invoices", validForm(url.Values{"fill_other": {"1"}, "already_paid": {"0"}, "due_date": {"2026-12-01"}}), &host1)
	if !strings.Contains(rec.Body.String(), `value="0"
               checked`) || !strings.Contains(rec.Body.String(), `value="2026-12-01"`) {
		t.Error("payment requested and its due date stay")
	}
}

func TestFormStateRowsAndFlags(t *testing.T) {
	c := &call{}
	c.r = httptestPost(url.Values{"item_kind": {"cleaning", "", ""}, "item_description": {"", "", "x"}, "item_quantity": {"2", "1", "1"},
		"item_unit_price": {"10", "", ""}, "already_paid": {"on"}, "lang": {""}})
	state, rows := formState(c)
	if state["already_paid"] != "1" || state["lang"] != "" || len(rows) != 2 || rows[0].Kind != "cleaning" || rows[0].VATRate != "21" || rows[1].Description != "x" {
		t.Fatalf("%v %+v", state, rows)
	}
}
