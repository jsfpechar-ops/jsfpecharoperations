package invoices

import (
	"context"
	"net/http"
	"net/url"
	"os"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// seedGuest adds a complete adult guest to a stay. The address is stored the
// way the guest form stores it: encrypted, the plain columns empty.
func (a *testApp) seedGuest(stayID int64, first, surname, street, city, country string, complete bool) {
	a.t.Helper()
	keys, err := secure.LoadDataKeys(testEnv())
	if err != nil {
		a.t.Fatal(err)
	}
	enc := func(s string) string {
		out, err := keys.EncryptString(s)
		if err != nil {
			a.t.Fatal(err)
		}
		return out
	}
	doc, birth := "C01X00T47", "05051980"
	if !complete {
		doc, birth = "", ""
	}
	_, err = a.pool.Exec(context.Background(),
		`INSERT INTO guest (reservation_id, surname, first_name, nationality, res_country, purpose, signature_png,
		   doc_number_enc, birth_date_enc, res_street_enc, res_city_enc, created_at, updated_at)
		 VALUES ($1, $2, $3, 'DEU', $4, '10', 'imported', $5, $6, $7, $8, '2026-11-01', '2026-11-01')`,
		stayID, surname, first, country, enc(doc), enc(birth), enc(street), enc(city))
	if err != nil {
		a.t.Fatal(err)
	}
}

func TestPickerListsStaysAndQuickLinks(t *testing.T) {
	app, seed := newTestApp(t)
	body := app.get("/invoices/new", &host1).Body.String()
	for _, want := range []string{`<option value="11">Chata U Lesa, 10.11.2026 – 13.11.2026</option>`, `<option value="12">`, "Nedávné pobyty bez faktury",
		`href="/invoices/new?reservation_id=11"`, `href="/entities"`} {
		if !strings.Contains(body, want) {
			t.Errorf("picker lacks %q", want)
		}
	}
	for _, id := range []int64{seed.ForeignStay, seed.CancelledStay} {
		if strings.Contains(body, `<option value="`+itoa(id)+`">`) {
			t.Errorf("stay %d must not be offered", id)
		}
	}
	// a stay with a live invoice drops out of the quick links but stays in the list
	app.issueFor(app.entityRow(seed.Entity), seed.Stay, nil, 1)
	body = app.get("/invoices/new", &host1).Body.String()
	if strings.Contains(body, `href="/invoices/new?reservation_id=11"`) || !strings.Contains(body, `<option value="11">`) {
		t.Error("quick links skip stays that have an invoice")
	}
	if body := app.get("/invoices/new", &host2).Body.String(); strings.Contains(body, "Chata U Lesa") || !strings.Contains(body, "Cizí byt") {
		t.Error("only the host's own stays")
	}
	if rec := app.get("/invoices/new?reservation_id=", &host1); rec.Code != 200 || !strings.Contains(rec.Body.String(), `name="reservation_id" required`) {
		t.Error("an empty reservation_id shows the picker")
	}
}

func TestFormRedirectsAndRefusals(t *testing.T) {
	app, seed := newTestApp(t)
	loc := func(path string, who *testCaller) (int, string) {
		rec := app.get(path, who)
		return rec.Code, rec.Header().Get("Location")
	}
	if code, l := loc("/invoices/new?reservation_id=11", &host1); code != 303 || l != "/invoices/new?reservation_id=11&entity=1" {
		t.Errorf("the property's operator is pinned in the URL: %d %q", code, l)
	}
	for _, c := range []struct {
		path, prefix string
		who          *testCaller
	}{
		{"/invoices/new?reservation_id=13", "/invoices/new?err=", &host1}, // another host's stay
		{"/invoices/new?reservation_id=abc", "/invoices/new?err=", &host1},
		{"/invoices/new?reservation_id=14", "/invoices/new?err=", &host1}, // cancelled
		{"/invoices/new?reservation_id=99", "/invoices/new?err=", &host1},
	} {
		if code, l := loc(c.path, c.who); code != 303 || !strings.HasPrefix(l, c.prefix) {
			t.Errorf("%s: %d %q", c.path, code, l)
		}
	}
	app.issueFor(app.entityRow(seed.Entity), seed.Stay, nil, 1)
	if code, l := loc("/invoices/new?reservation_id=11&entity=1", &host1); code != 303 || !strings.HasPrefix(l, "/invoices/1?err=") {
		t.Errorf("a stay with an invoice goes to that invoice: %d %q", code, l)
	}
	if code, l := loc("/invoices/new", nil); code != 303 || l != "/login?next=/invoices/new" {
		t.Errorf("signed out: %d %q", code, l)
	}
}

func TestFormPage(t *testing.T) {
	app, seed := newTestApp(t)
	rec := app.get("/invoices/new?reservation_id=12&entity=1", &host1)
	body := rec.Body.String()
	if rec.Code != 200 {
		t.Fatalf("form: %d", rec.Code)
	}
	for _, want := range []string{
		`action="/invoices" class="invoice-form" data-reservation-id="12"`, `name="reservation_id" value="12"`, "Chata U Lesa, 01.10.2026 – 04.10.2026 (3 noci)",
		`name="_csrf"`, `<span class="invoice-supplier-name">Provoz Jedna s.r.o.</span>`, "IČO 27082440", `name="stay_price"`, `required`,
		`2026-0001`, `data-vat-payer="0"`, `value="guest@example.test"`, `id="already_paid" name="already_paid" value="1"
               checked`, `<option value="CZE" selected>`, `value="2026-11-13"`, `data-has-iban="1"`,
		`/entities?edit=1&amp;next=/invoices/new%3Freservation_id%3D12%26entity%3D1#entity-invoice`, `formaction="/invoices/preview"`,
	} {
		if !strings.Contains(body, want) {
			t.Errorf("form lacks %q", want)
		}
	}
	// the operator picker holds only the property's operator, hidden
	if strings.Count(body, `<option value="1"`)+strings.Count(body, `<option value="2"`) < 1 || strings.Contains(body, "Provoz Dva") {
		t.Error("the property names its operator: no other choice")
	}
	// a property without an operator lets the host pick between both
	if _, err := app.pool.Exec(context.Background(), `UPDATE apartment SET legal_entity_id = NULL WHERE id = 1`); err != nil {
		t.Fatal(err)
	}
	body = app.get("/invoices/new?reservation_id=12", &host1).Body.String()
	if rec := app.get("/invoices/new?reservation_id=12", &host1); rec.Code != 303 || rec.Header().Get("Location") != "/invoices/new?reservation_id=12&entity=2" {
		t.Errorf("first operator by name is pinned: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	body = app.get("/invoices/new?reservation_id=12&entity=2", &host1).Body.String()
	if !strings.Contains(body, "Provoz Jedna") || !strings.Contains(body, `data-vat-payer="1"`) || strings.Contains(body, `invoice-supplier-picker" hidden`) ||
		!strings.Contains(body, `name="stay_vat_rate" class="input-vat" >`) {
		t.Error("two operators: a picker, the payer's VAT column on")
	}
	_ = seed
}

func TestFormWithoutOperatorShowsTheError(t *testing.T) {
	app, _ := newTestApp(t)
	if _, err := app.pool.Exec(context.Background(), `UPDATE legal_entity SET archived_at = '2026-01-02' WHERE owner_user_id = 1`); err != nil {
		t.Fatal(err)
	}
	rec := app.get("/invoices/new?reservation_id=11", &host1)
	body := rec.Body.String()
	if rec.Code != 200 || !strings.Contains(body, "ui-banner-attention") || strings.Contains(body, `class="invoice-form"`) {
		t.Fatalf("no operator: %d", rec.Code)
	}
}

func TestFormSuggestsTheLeadGuestAsBuyer(t *testing.T) {
	app, _ := newTestApp(t)
	app.seedGuest(12, "Hans", "Mueller", "Hauptstrasse 1", "Berlin", "DEU", true)
	body := app.get("/invoices/new?reservation_id=12&entity=1", &host1).Body.String()
	for _, want := range []string{`value="Hans Mueller"`, `value="Hauptstrasse 1"`, `value="Berlin"`, `<option value="DEU" selected>`,
		`name="fill_from_guest"`, `data-buyer-only="guest"`, "invoice-lookup-guest"} {
		if !strings.Contains(body, want) {
			t.Errorf("form lacks %q", want)
		}
	}
	if !strings.Contains(body, `role="status" data-buyer-only="guest"`) {
		t.Error("the prefilled hint")
	}
	// an incomplete guest is never suggested
	app2, _ := newTestApp(t)
	app2.seedGuest(12, "Anna", "Incomplete", "Ulice 1", "Praha", "CZE", false)
	body = app2.get("/invoices/new?reservation_id=12&entity=1", &host1).Body.String()
	if strings.Contains(body, "Incomplete") || strings.Contains(body, `name="fill_from_guest"`) {
		t.Error("only a complete guest is offered")
	}
}

func TestFormPriceHintAndRememberedPayment(t *testing.T) {
	app, seed := newTestApp(t)
	app.issueFor(app.entityRow(seed.Entity), seed.Stay, url.Values{"stay_price": {"2400"}, "already_paid": {"1"}, "paid_via": {"cash"}}, 1)
	body := app.get("/invoices/new?reservation_id=12&entity=1", &host1).Body.String()
	for _, want := range []string{`placeholder="2400"`, `data-use-price="2400"`, `<option value="cash" selected>`} {
		if !strings.Contains(body, want) {
			t.Errorf("form lacks %q", want)
		}
	}
	if code := app.get("/invoices/new?reservation_id=12&entity=1", &host2).Code; code != http.StatusSeeOther {
		t.Errorf("another host's stay: %d", code)
	}
}

func TestBundledCountriesMatchTheSharedList(t *testing.T) {
	shared, err := os.ReadFile("../../countries/countries.json")
	if err != nil {
		t.Fatal(err)
	}
	if string(shared) != string(countriesJSON) {
		t.Error("countries.json differs from go/internal/countries/countries.json: copy it again")
	}
}
