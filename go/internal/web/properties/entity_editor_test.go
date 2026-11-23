package properties

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

// fakeARES serves the ARES REST shape on a local port and points aresURL at it.
// No test reaches the real register.
func fakeARES(t *testing.T, handler http.HandlerFunc) *int32 {
	t.Helper()
	var hits int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&hits, 1)
		if r.Header.Get("User-Agent") != "UbyHost" {
			t.Errorf("User-Agent %q", r.Header.Get("User-Agent"))
		}
		handler(w, r)
	}))
	old := aresURL
	aresURL = srv.URL + "/ico/%s"
	aresMu.Lock()
	aresCache = map[string]aresCacheEntry{}
	aresMu.Unlock()
	t.Cleanup(func() { srv.Close(); aresURL = old; aresClock = time.Now })
	return &hits
}

const aresBody = `{"obchodniJmeno":" Alfa s.r.o. ","dic":"CZ12345679","sidlo":{"textovaAdresa":"Hlavní 12/3, 110 00 Praha 1","nazevUlice":"Hlavní","cisloDomovni":12,"cisloOrientacni":3,"cisloOrientacniPismeno":"a","nazevObce":"Praha","psc":11000},
 "seznamRegistraci":{"stavZdrojeDph":"aktivni"},"dalsiUdaje":[{"datovyZdroj":"rzp","spisovaZnacka":"zzz"},{"datovyZdroj":"VR","spisovaZnacka":"C 123/MSPH"}]}`

func TestMapAres(t *testing.T) {
	var payload map[string]any
	dec := json.NewDecoder(strings.NewReader(aresBody))
	dec.UseNumber()
	if err := dec.Decode(&payload); err != nil {
		t.Fatal(err)
	}
	got := mapAres(payload)
	want := aresData{Name: "Alfa s.r.o.", Seat: "Hlavní 12/3, 110 00 Praha 1", Street: "Hlavní 12/3a", City: "Praha", Zip: "11000", DIC: "CZ12345679",
		VATPayer: true, RegistryEntry: "spisová značka C 123 vedená u Městského soudu v Praze"}
	if got != want {
		t.Errorf("got %+v\nwant %+v", got, want)
	}
	if mapAres(map[string]any{"sidlo": map[string]any{"psc": json.Number("1100")}}).Zip != "01100" {
		t.Error("a short ZIP is padded to five digits")
	}
	for in, want := range map[string]string{"": "", "C 1": "C 1", "C 1/XXXX": "C 1/XXXX", " C 9 / KSBR ": "spisová značka C 9 vedená u Krajského soudu v Brně"} {
		if got := formatRegistryMark(in); got != want {
			t.Errorf("%q: %q", in, got)
		}
	}
}

func TestAresLookup(t *testing.T) {
	var status atomic.Int32
	status.Store(200)
	hits := fakeARES(t, func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/12345679") {
			t.Errorf("path %s", r.URL.Path)
		}
		w.WriteHeader(int(status.Load()))
		if status.Load() == 200 {
			_, _ = w.Write([]byte(aresBody))
		}
	})
	ctx := t.Context()
	if aresLookup(ctx, "12345678") != nil || atomic.LoadInt32(hits) != 0 {
		t.Fatal("an invalid IČO must not be sent")
	}
	d := aresLookup(ctx, " 12345679 ")
	if d == nil || d.Name != "Alfa s.r.o." {
		t.Fatalf("lookup %+v", d)
	}
	aresLookup(ctx, "12345679")
	if atomic.LoadInt32(hits) != 1 {
		t.Errorf("a second lookup within 24 h must come from the cache: %d requests", atomic.LoadInt32(hits))
	}
	// After the TTL it asks again; a 404 is cached as "unknown", other errors are not.
	now := time.Now()
	aresClock = func() time.Time { return now.Add(25 * time.Hour) }
	status.Store(404)
	if aresLookup(ctx, "12345679") != nil || atomic.LoadInt32(hits) != 2 {
		t.Fatal("404")
	}
	if aresLookup(ctx, "12345679") != nil || atomic.LoadInt32(hits) != 2 {
		t.Error("a 404 is cached")
	}
	aresClock = func() time.Time { return now.Add(60 * time.Hour) }
	status.Store(500)
	aresLookup(ctx, "12345679")
	aresLookup(ctx, "12345679")
	if atomic.LoadInt32(hits) != 4 {
		t.Errorf("a 500 is not cached: %d requests", atomic.LoadInt32(hits))
	}
}

func TestRegisterLookupLimit(t *testing.T) {
	pool := testPool(t)
	fakeARES(t, func(w http.ResponseWriter, r *http.Request) { _, _ = w.Write([]byte(aresBody)) })
	at := testNow
	// A bad IČO is refused before the limit is charged.
	if _, msg, err := registerLookup(t.Context(), pool, 7, "en", "12345678", at); err != nil || msg != "The register didn't answer or doesn't know this IČO. Please type the details." {
		t.Fatalf("%q %v", msg, err)
	}
	if oneInt(t, pool, `SELECT COUNT(*) FROM rate_limit_event`) != 0 {
		t.Error("an invalid IČO was charged")
	}
	for i := 0; i < 20; i++ {
		if d, msg, err := registerLookup(t.Context(), pool, 7, "en", goodICO, at); err != nil || d == nil || msg != "" {
			t.Fatalf("lookup %d: %v %q %v", i, d, msg, err)
		}
	}
	if d, msg, _ := registerLookup(t.Context(), pool, 7, "en", goodICO, at); d != nil || msg != "Too many lookups, try again later." {
		t.Errorf("21st lookup: %v %q", d, msg)
	}
	// Another owner, and the same owner an hour later, are free.
	if d, _, _ := registerLookup(t.Context(), pool, 8, "en", goodICO, at); d == nil {
		t.Error("another owner is limited")
	}
	if d, _, _ := registerLookup(t.Context(), pool, 7, "en", goodICO, at.Add(61*time.Minute)); d == nil {
		t.Error("the window did not slide")
	}
}

func TestBankAndPhoneParts(t *testing.T) {
	if p := czechAccountParts(" 19-2000145399 / 0800"); p != (accountParts{"19", "2000145399", "0800", ""}) {
		t.Errorf("%+v", p)
	}
	if p := czechAccountParts("cz65 0800 0000 1920 0014 5399"); p != (accountParts{IBAN: goodIBAN}) {
		t.Errorf("%+v", p)
	}
	if p := czechAccountParts("nonsense"); p != (accountParts{}) {
		t.Errorf("%+v", p)
	}
	for in, want := range map[string]string{"19-2000145399/0800": "GIBACZPX", goodIBAN: "GIBACZPX", "1/9999": "", "": "", "123/0100": "KOMBCZPP"} {
		if got := bicForAccount(in); got != want {
			t.Errorf("%q: %q want %q", in, got, want)
		}
	}
	for in, want := range map[string][2]string{"": {"", ""}, "777123456": {"+420", "777123456"}, "+420 777 123 456": {"+420", "777123456"}, "0049301234": {"+49", "301234"},
		"+1 212 555 0100": {"+1", "2125550100"}, "+7 495 1": {"+7", "4951"}, "+999": {"", "+999"}, "12345": {"", "12345"}} {
		if c, n := phoneFormParts(in); [2]string{c, n} != want {
			t.Errorf("%q: %q %q want %v", in, c, n, want)
		}
	}
}

func TestEntityEditorPage(t *testing.T) {
	pool := testPool(t)
	seedHosts(t, pool)
	mux := http.NewServeMux()
	RegisterLists(mux, noWrap, pool, testEnv, testClock)
	RegisterEntities(mux, noWrap, pool, testEnv, testClock)
	mustExec(t, pool, `INSERT INTO legal_entity (id, owner_user_id, name, seat, ico, contact_email, contact_phone, bank_account, iban, bic, vat_status, invoice_prefix, invoice_next_number, invoice_due_days, created_at, archived_at) VALUES
		(130101, 130001, 'Mine', 'Praha', '12345679', 'm@example.com', '+420777123456', '19-2000145399/0800', 'CZ6508000000192000145399', 'GIBACZPX', 'payer', 'AB', 7, 30, $1, NULL),
		(130102, 130002, 'Theirs', 'Brno', NULL, NULL, NULL, NULL, NULL, NULL, 'non_payer', NULL, NULL, 14, $1, NULL),
		(130103, 130001, 'Old one', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'non_payer', NULL, NULL, 14, $1, $1)`, stamp0)
	mustExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, legal_entity_id, data_controller_entity_id, created_at) VALUES
		(130201, 130001, 'Flat B', 130101, NULL, $1), (130202, 130001, 'Flat A', NULL, 130101, $1)`, stamp0)

	body := getAs(t, mux, "/entities?edit=130101&next=/apartments/130201", 130001, 0, nil).Body.String()
	for _, want := range []string{
		`id="entity-edit"`, `action="/entities/130101"`, `action="/entities/130101/invoice"`, `name="next" value="/apartments/130201"`,
		`value="12345679"`, `name="contact_phone_country_code" value="420"`, `name="contact_phone" autocomplete="tel-national" inputmode="tel" value="777123456"`,
		`<a href="/apartments/130202?view=settings&amp;section=property#operator-picker">Flat A</a>`,
		`name="account_number" inputmode="numeric" maxlength="10" value="2000145399"`, `value="GIBACZPX"`, `<option value="payer" selected>`,
		`name="invoice_next_number" min="1" inputmode="numeric" value="7"`, `name="invoice_due_days" min="0" max="365" inputmode="numeric" value="30"`,
		`name="_invoice_account_existing" value="19-2000145399/0800"`, `class="clickable-row row-selected"`, `class="ui-btn ui-btn-quiet ui-btn-compact" href="/apartments/130201"`,
	} {
		if !strings.Contains(body, want) {
			t.Errorf("editor lacks %q", want)
		}
	}
	if strings.Count(body, "row-selected") != 1 {
		t.Errorf("row-selected %d times", strings.Count(body, "row-selected"))
	}
	// Another host's business: the list, no editor. An archived one: the business form only.
	if b := getAs(t, mux, "/entities?edit=130102", 130001, 0, nil).Body.String(); strings.Contains(b, "entity-edit") || strings.Contains(b, "Theirs") {
		t.Error("another host's business opened")
	}
	b := getAs(t, mux, "/entities?edit=130103", 130001, 0, nil).Body.String()
	if !strings.Contains(b, `id="entity-edit"`) || strings.Contains(b, `id="entity-invoice"`) {
		t.Error("an archived business shows Business details only")
	}
	if b = getAs(t, mux, "/entities?edit=99999999999999999999999", 130001, 0, nil).Body.String(); strings.Contains(b, "entity-edit") {
		t.Error("an id past int64 opens nothing")
	}
	if rec := getAs(t, mux, "/entities?edit=%D9%A1", 130001, 0, nil); rec.Code != http.StatusNotImplemented {
		t.Errorf("non-ASCII digits: %d", rec.Code)
	}
}

// "Fill from register" on the add form and on the editor (admin.py _entities_ares_rerender).
func TestFillFromRegister(t *testing.T) {
	pool := testPool(t)
	seedHosts(t, pool)
	hits := fakeARES(t, func(w http.ResponseWriter, r *http.Request) { _, _ = w.Write([]byte(aresBody)) })
	mux := http.NewServeMux()
	RegisterLists(mux, noWrap, pool, testEnv, testClock)
	RegisterEntities(mux, noWrap, pool, testEnv, testClock)
	mustExec(t, pool, `UPDATE user_account SET email = 'host@example.com' WHERE id = 130001`)
	mustExec(t, pool, `INSERT INTO legal_entity (id, owner_user_id, name, seat, contact_email, created_at) VALUES (130101, 130001, 'Typed name', '', 'old@example.com', $1)`, stamp0)

	// Add form: blank name, seat and DIČ are filled; what the host typed stays; nothing is saved.
	rec := post(t, mux, "/entities", 130001, 0, "en", url.Values{"fill_from_register": {"1"}, "ico": {goodICO}, "name": {""}, "seat": {"My seat"}, "contact_email": {""}})
	body := rec.Body.String()
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d", rec.Code)
	}
	for _, want := range []string{
		`id="new_name" name="name" autocomplete="organization" autocapitalize="words" required value="Alfa s.r.o."`,
		`id="new_seat" name="seat" autocomplete="street-address" autocapitalize="words" required value="My seat"`,
		`value="CZ12345679"`,
		`value="host@example.com"`,
		`We filled: name, tax ID (DIČ).`, `Filled from the public business register (ARES). Check and save.`,
	} {
		if !strings.Contains(body, want) {
			t.Errorf("add form lacks %q", want)
		}
	}
	if oneInt(t, pool, `SELECT COUNT(*) FROM legal_entity`) != 1 {
		t.Error("the lookup saved a business")
	}
	if atomic.LoadInt32(hits) != 1 {
		t.Errorf("ARES requests: %d", *hits)
	}

	// Editor: typed values win, the stored e-mail stays, the editor opens on the right business; the form is multipart.
	rec = multipartPost(t, mux, "/entities/130101", 130001, map[string]string{"fill_from_register": "1", "ico": goodICO, "name": "Typed name", "seat": "", "dic": ""}, nil)
	body = rec.Body.String()
	for _, want := range []string{`id="entity-edit"`, `value="Typed name"`, `value="Hlavní 12/3, 110 00 Praha 1"`, `value="old@example.com"`, `We filled: registered seat, tax ID (DIČ).`} {
		if !strings.Contains(body, want) {
			t.Errorf("editor lacks %q", want)
		}
	}
	if readEntity(t, pool, 130101).seat != "~" && readEntity(t, pool, 130101).seat != "" {
		t.Error("the lookup changed the stored business")
	}

	// A bad IČO and another host's business.
	body = post(t, mux, "/entities", 130001, 0, "en", url.Values{"fill_from_register": {"1"}, "ico": {"12345678"}}).Body.String()
	if !strings.Contains(body, `<p class="alert">The register didn&#39;t answer or doesn&#39;t know this IČO. Please type the details.</p>`) {
		t.Error("no failure message")
	}
	mustExec(t, pool, `INSERT INTO legal_entity (id, owner_user_id, name, created_at) VALUES (130102, 130002, 'Theirs', $1)`, stamp0)
	rec = post(t, mux, "/entities/130102", 130001, 0, "en", url.Values{"fill_from_register": {"1"}, "ico": {goodICO}})
	if loc := rec.Header().Get("Location"); !strings.HasPrefix(loc, "/entities?err=") {
		t.Errorf("another host's business: %d %q", rec.Code, loc)
	}
}
