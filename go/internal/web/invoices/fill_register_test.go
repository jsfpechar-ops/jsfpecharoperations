package invoices

import (
	"net/http"
	"net/url"
	"strings"
	"testing"
)

func TestFillBuyerFromRegister(t *testing.T) {
	hits, stop := fakeAres(t)
	defer stop()
	app, _ := newTestApp(t)
	app.seedGuest(11, "Hans", "Mueller", "Hauptstrasse 1", "Berlin", "DEU", true)
	form := validForm(url.Values{"fill_buyer_from_register": {"1"}, "buyer_kind": {"company"}, "buyer_ico": {"27082440"},
		"buyer_name": {"Hans Mueller"}, "buyer_street": {"Hauptstrasse 1"}, "buyer_city": {"Berlin"}, "buyer_zip": {""}, "buyer_country": {"DEU"}, "buyer_dic": {""}})
	rec := app.do(http.MethodPost, "/invoices", form, &host1)
	body := rec.Body.String()
	// the guest's suggestion is dropped for a company, so the register fills name, street, city, zip and DIČ; the typed country stays
	for _, want := range []string{`value="Firma s.r.o."`, `value="Ulice 12"`, `value="Praha"`, `value="11000"`, `value="CZ27082440"`, `<option value="DEU" selected>`, "hint"} {
		if !strings.Contains(body, want) {
			t.Errorf("filled form lacks %q", want)
		}
	}
	if rec.Code != 200 || *hits != 1 || app.count(`SELECT COUNT(*) FROM invoice`) != 0 {
		t.Fatalf("status %d, %d requests", rec.Code, *hits)
	}
	if app.count(`SELECT COUNT(*) FROM rate_limit_event WHERE scope = 'ares' AND key = '1'`) != 1 {
		t.Error("the lookup counts against the owner")
	}
	// a typed name is never replaced
	form.Set("buyer_kind", "guest")
	form.Set("buyer_name", "Typed Name")
	body = app.do(http.MethodPost, "/invoices", form, &host1).Body.String()
	if !strings.Contains(body, `value="Typed Name"`) || strings.Contains(body, `value="Firma s.r.o."`) {
		t.Error("typed values win")
	}
	// bad IČO: the failure line, no request, no count
	form.Set("buyer_ico", "12345678")
	before := *hits
	body = app.do(http.MethodPost, "/invoices", form, &host1).Body.String()
	if !strings.Contains(body, `class="alert"`) || *hits != before {
		t.Error("invalid IČO")
	}
	// the 21st lookup of an hour is refused with the rate-limit line
	form.Set("buyer_ico", "27082440")
	for i := 0; i < 25; i++ {
		body = app.do(http.MethodPost, "/invoices", form, &host1).Body.String()
	}
	if app.count(`SELECT COUNT(*) FROM rate_limit_event WHERE scope = 'ares' AND key = '1'`) != 20 || !strings.Contains(body, `class="alert"`) {
		t.Errorf("limit: %d events", app.count(`SELECT COUNT(*) FROM rate_limit_event WHERE scope = 'ares'`))
	}
}
