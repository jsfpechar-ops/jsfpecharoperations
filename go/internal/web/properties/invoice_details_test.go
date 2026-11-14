package properties

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

const vatBody = `<?xml version="1.0"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>
<r:StatusNespolehlivySubjektRozsirenyV2Response xmlns:r="http://adis.mfcr.cz/rozhraniCRPDPH/"><r:status statusCode="0" statusText="OK"/>
<r:statusPlatceDPH dic="99999999"/>
<r:statusSubjektu dic="12345679" nespolehlivyPlatce="ANO" typSubjektu="PLATCE_DPH"><r:zverejneneUcty>
<r:ucet datumZverejneni="2020-01-01"><r:standardniUcet predcisli="19" cislo="2000145399" kodBanky="0800"/></r:ucet>
<r:ucet datumZverejneni="2020-01-01"><r:standardniUcet cislo="123" kodBanky="0100"/></r:ucet>
<r:ucet datumZverejneni="2020-01-01"><r:standardniUcet cislo="123" kodBanky="0100"/></r:ucet>
<r:ucet datumZverejneni="2020-01-01" datumZverejneniUkonceni="2021-01-01"><r:standardniUcet cislo="999" kodBanky="0300"/></r:ucet>
<r:ucet datumZverejneni="2020-01-01"><r:nestandardniUcet cislo="CZ00"/></r:ucet>
</r:zverejneneUcty></r:statusSubjektu></r:Body></r:Envelope>`

func fakeVAT(t *testing.T, body string, status int) *int32 {
	t.Helper()
	var hits int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&hits, 1)
		if r.Header.Get("SOAPAction") != `"`+vatAction+`"` || r.Header.Get("User-Agent") != "UbyHost" {
			t.Errorf("headers %v", r.Header)
		}
		w.WriteHeader(status)
		_, _ = w.Write([]byte(body))
	}))
	old := vatURL
	vatURL = srv.URL
	vatMu.Lock()
	vatCache = map[string]vatCacheEntry{}
	vatMu.Unlock()
	t.Cleanup(func() { srv.Close(); vatURL = old; vatClock = time.Now })
	return &hits
}

func TestParseVAT(t *testing.T) {
	// The envelope in the fixture is malformed on purpose at the end; fix it for the parse test.
	body := strings.Replace(vatBody, "</r:Body></r:Envelope>", "</r:StatusNespolehlivySubjektRozsirenyV2Response></soap:Body></soap:Envelope>", 1)
	d, err := parseVAT([]byte(body), "12345679")
	if err != nil || d == nil || d.Status != "payer" || !d.Unreliable {
		t.Fatalf("%+v %v", d, err)
	}
	if strings.Join(d.Accounts, "|") != "19-2000145399/0800|123/0100" {
		t.Errorf("accounts %v (an ended one, a duplicate and a non-standard account are left out)", d.Accounts)
	}
	if d, err := parseVAT([]byte(body), "11111111"); d != nil || err != nil {
		t.Errorf("unknown DIČ: %+v %v", d, err)
	}
	if _, err := parseVAT([]byte(strings.Replace(body, `statusCode="0"`, `statusCode="1"`, 1)), "12345679"); err == nil {
		t.Error("a register error is an error")
	}
	if d, _ := parseVAT([]byte(strings.Replace(body, "PLATCE_DPH", "NEPLATCE", 1)), "12345679"); d != nil {
		t.Error("a non-payer type is unknown")
	}
	for in, want := range map[string]string{"CZ12345679": "12345679", " cz 1234 5679 ": "12345679", "12345679": "12345679", "CZ123": "", "": "", "SK12345679": ""} {
		if got := dicDigits(in); got != want {
			t.Errorf("%q: %q", in, got)
		}
	}
	if composeCzechAccount("a1", "2-3", "x4") != "1-23/4" || composeCzechAccount("", "", "") != "" || composeCzechAccount("", "5", "100") != "5/100" {
		t.Error("composeCzechAccount")
	}
}

func TestInvoiceDetailsSave(t *testing.T) {
	pool := testPool(t)
	seedHosts(t, pool)
	mux := http.NewServeMux()
	RegisterLists(mux, noWrap, pool, testEnv, testClock)
	RegisterInvoiceDetails(mux, noWrap, pool, testEnv, testClock)
	mustExec(t, pool, `INSERT INTO legal_entity (id, owner_user_id, name, ico, bank_account, iban, vat_status, created_at, archived_at) VALUES
		(130101, 130001, 'Mine', '12345679', NULL, NULL, 'non_payer', $1, NULL),
		(130102, 130001, 'IBAN only', NULL, 'CZ6508000000192000145399', 'CZ6508000000192000145399', 'non_payer', $1, NULL),
		(130103, 130002, 'Theirs', NULL, NULL, NULL, 'non_payer', $1, NULL),
		(130104, 130001, 'Archived', NULL, NULL, NULL, 'non_payer', $1, $1)`, stamp0)

	// Three-part account: composed, validated, IBAN stored, BIC derived from the bank code; audit row written.
	rec := post(t, mux, "/entities/130101/invoice", 130001, 0, "en", url.Values{"account_prefix": {"19"}, "account_number": {"2000145399"}, "account_bank": {"0800"},
		"vat_status": {"payer"}, "registry_entry": {"C 1"}, "invoice_prefix": {"x-1"}, "invoice_next_number": {"12"}, "invoice_due_days": {"30"}})
	if loc := rec.Header().Get("Location"); rec.Code != http.StatusSeeOther || !strings.HasPrefix(loc, "/entities?edit=130101&msg=Saved.") || !strings.HasSuffix(loc, "#entity-invoice") {
		t.Fatalf("save: %d %q", rec.Code, loc)
	}
	e := readEntity(t, pool, 130101)
	if e.bank != goodAccount || e.iban != goodIBAN || e.bic != "GIBACZPX" || e.vat != "payer" || e.registry != "C 1" || e.prefix != "X1" || *e.next != 12 || *e.due != 30 || e.name != "Mine" {
		t.Errorf("row %+v", e)
	}
	if n := oneInt(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'entity_invoice_details_saved' AND detail = 'id=130101' AND owner_user_id = 130001 AND actor_user_id = 130001`); n != 1 {
		t.Errorf("audit rows %d", n)
	}
	// next is honoured; a posted blank BIC is not derived; blank parts clear the domestic account.
	rec = post(t, mux, "/entities/130101/invoice", 130001, 0, "en", url.Values{"account_prefix": {""}, "account_number": {""}, "account_bank": {""}, "bic": {""}, "next": {"/apartments/5"}})
	if loc := rec.Header().Get("Location"); !strings.HasPrefix(loc, "/apartments/5?msg=Saved.") {
		t.Errorf("next: %q", loc)
	}
	if e = readEntity(t, pool, 130101); e.bank != "~" || e.iban != "~" || e.bic != "~" {
		t.Errorf("cleared %+v", e)
	}
	// An IBAN-only account survives empty parts, and a BIC is derived for it when none is stored and none posted.
	post(t, mux, "/entities/130102/invoice", 130001, 0, "en", url.Values{"account_prefix": {""}, "account_number": {""}, "account_bank": {""}, "vat_status": {"identified"}})
	if e = readEntity(t, pool, 130102); e.iban != goodIBAN || e.bank != goodIBAN || e.bic != "GIBACZPX" || e.vat != "identified" {
		t.Errorf("iban only %+v", e)
	}
	// An invalid account: 422, the typed values come back, nothing is written.
	rec = post(t, mux, "/entities/130101/invoice", 130001, 0, "en", url.Values{"account_prefix": {"19"}, "account_number": {"2000145398"}, "account_bank": {"0800"}, "registry_entry": {"typed registry"}})
	body := rec.Body.String()
	if rec.Code != http.StatusUnprocessableEntity || !strings.Contains(body, "That account number is not valid. Please check it.") || !strings.Contains(body, `value="2000145398"`) || !strings.Contains(body, `value="typed registry"`) {
		t.Errorf("422: %d", rec.Code)
	}
	if readEntity(t, pool, 130101).registry != "C 1" {
		t.Error("a refused save wrote a row")
	}
	// Another host's business, an archived one, a bad id, signed out.
	for _, id := range []string{"130103", "130104", "999"} {
		if loc := post(t, mux, "/entities/"+id+"/invoice", 130001, 0, "en", url.Values{"vat_status": {"payer"}}).Header().Get("Location"); !strings.HasPrefix(loc, "/entities?err=") {
			t.Errorf("%s: %q", id, loc)
		}
	}
	if readEntity(t, pool, 130103).vat != "non_payer" {
		t.Error("another host's business changed")
	}
	if rec = post(t, mux, "/entities/abc/invoice", 130001, 0, "en", url.Values{}); rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("bad id %d", rec.Code)
	}
	if rec = post(t, mux, "/entities/130101/invoice", 0, 0, "en", url.Values{"vat_status": {"payer"}}); !strings.HasPrefix(rec.Header().Get("Location"), "/login") {
		t.Errorf("signed out: %q", rec.Header().Get("Location"))
	}
}

func TestInvoiceDetailsLookup(t *testing.T) {
	pool := testPool(t)
	seedHosts(t, pool)
	fakeARES(t, func(w http.ResponseWriter, r *http.Request) { _, _ = w.Write([]byte(aresBody)) })
	body := strings.Replace(vatBody, "</r:Body></r:Envelope>", "</r:StatusNespolehlivySubjektRozsirenyV2Response></soap:Body></soap:Envelope>", 1)
	vatHits := fakeVAT(t, body, 200)
	mux := http.NewServeMux()
	RegisterLists(mux, noWrap, pool, testEnv, testClock)
	RegisterInvoiceDetails(mux, noWrap, pool, testEnv, testClock)
	mustExec(t, pool, `INSERT INTO legal_entity (id, owner_user_id, name, ico, vat_status, created_at) VALUES (130101, 130001, 'Mine', '12345679', 'non_payer', $1)`, stamp0)

	rec := post(t, mux, "/entities/130101/invoice", 130001, 0, "en", url.Values{"fill_from_register": {"1"}, "ico": {goodICO}, "vat_status": {"non_payer"}, "registry_entry": {""}})
	got := rec.Body.String()
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d", rec.Code)
	}
	for _, want := range []string{
		`We filled: registry entry, VAT status, bank account, BIC.`, `Filled from the business register (ARES) and the VAT register. Check and save.`,
		`value="spisová značka C 123 vedená u Městského soudu v Praze"`, `<option value="payer" selected>`, `name="account_number" inputmode="numeric" maxlength="10" value="2000145399"`,
		`value="GIBACZPX"`, `class="alert">`, `value="123/0100" formnovalidate>Use 123/0100</button>`,
	} {
		if !strings.Contains(got, want) {
			t.Errorf("lookup page lacks %q", want)
		}
	}
	if atomic.LoadInt32(vatHits) != 1 {
		t.Errorf("VAT register requests %d", *vatHits)
	}
	if e := readEntity(t, pool, 130101); e.vat != "non_payer" || e.bank != "~" {
		t.Errorf("the lookup saved something: %+v", e)
	}
	// Picking another published account replaces the filled one; a typed account is kept.
	got = post(t, mux, "/entities/130101/invoice", 130001, 0, "en", url.Values{"use_register_account": {"123/0100"}, "ico": {goodICO}}).Body.String()
	if !strings.Contains(got, `name="account_number" inputmode="numeric" maxlength="10" value="123"`) || !strings.Contains(got, `Use 19-2000145399/0800`) {
		t.Error("use_register_account")
	}
	got = post(t, mux, "/entities/130101/invoice", 130001, 0, "en", url.Values{"fill_from_register": {"1"}, "account_number": {"555"}, "account_bank": {"0100"}, "account_prefix": {""}}).Body.String()
	if !strings.Contains(got, `value="555"`) || !strings.Contains(got, `Use 19-2000145399/0800`) || !strings.Contains(got, `Use 123/0100`) {
		t.Error("a typed account is kept and both published accounts are offered")
	}
}
