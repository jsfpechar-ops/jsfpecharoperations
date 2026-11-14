package properties

import (
	"bytes"
	"context"
	"encoding/base64"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const (
	goodICO     = "12345679"
	goodAccount = "19-2000145399/0800"
	goodIBAN    = "CZ6508000000192000145399"
)

func entityMux(pool *pgxpool.Pool) *http.ServeMux {
	mux := http.NewServeMux()
	Register(mux, noWrap, pool, testEnv, testClock) // the archive routes next to the new ones
	RegisterEntities(mux, noWrap, pool, testEnv, testClock)
	return mux
}

// multipartPost sends fields and files as multipart/form-data, as the editor does.
func multipartPost(t *testing.T, mux http.Handler, path string, uid int64, fields map[string]string, files map[string][]byte) *httptest.ResponseRecorder {
	t.Helper()
	var buf bytes.Buffer
	mw := multipart.NewWriter(&buf)
	_ = mw.WriteField("_csrf", csrfToken(t, csrfCookie))
	for k, v := range fields {
		_ = mw.WriteField(k, v)
	}
	for k, v := range files {
		fw, _ := mw.CreateFormFile(k, "sig.bin")
		_, _ = fw.Write(v)
	}
	_ = mw.Close()
	req := httptest.NewRequest(http.MethodPost, path, &buf)
	req.Header.Set("Content-Type", mw.FormDataContentType())
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: csrfCookie})
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: "en"})
	payload := map[string]any{"uid": uid, "sv": int64(1), "iat": testNow.Unix()}
	req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, testNow)})
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

type entityRowT struct {
	name, seat, ico, dic, email, phone, bank, iban, bic, vat, registry, prefix string
	next, year, due                                                            *int64
	sig, sigName                                                               *string
	owner                                                                      int64
}

func readEntity(t *testing.T, pool *pgxpool.Pool, id int64) entityRowT {
	t.Helper()
	var e entityRowT
	err := pool.QueryRow(context.Background(), `SELECT name, COALESCE(seat,'~'), COALESCE(ico,'~'), COALESCE(dic,'~'), COALESCE(contact_email,'~'),
		COALESCE(contact_phone,'~'), COALESCE(bank_account,'~'), COALESCE(iban,'~'), COALESCE(bic,'~'), vat_status, COALESCE(registry_entry,'~'),
		COALESCE(invoice_prefix,'~'), invoice_next_number, invoice_next_number_year, invoice_due_days, signature_png_enc, signature_name, owner_user_id
		FROM legal_entity WHERE id = $1`, id).Scan(&e.name, &e.seat, &e.ico, &e.dic, &e.email, &e.phone, &e.bank, &e.iban, &e.bic, &e.vat, &e.registry,
		&e.prefix, &e.next, &e.year, &e.due, &e.sig, &e.sigName, &e.owner)
	if err != nil {
		t.Fatal(err)
	}
	return e
}

func TestNormaliseAccount(t *testing.T) {
	for _, c := range []struct {
		in, display, iban string
		ok                bool
	}{
		{" 19-2000145399 / 0800 ", "19-2000145399/0800", goodIBAN, true},
		{"cz65 0800 0000 1920 0014 5399", goodIBAN, goodIBAN, true},
		{"19-2000145398/0800", "", "", false},
		{"CZ6508000000192000145398", "", "", false},
		{"abc", "", "", false},
	} {
		d, i, ok := normaliseAccount(c.in)
		if ok != c.ok {
			t.Errorf("%q: ok=%v", c.in, ok)
		}
		if c.ok && (d != c.display || i != c.iban) {
			t.Errorf("%q: %q %q", c.in, d, i)
		}
	}
}

func TestInvoiceDetailPayload(t *testing.T) {
	req := func(form url.Values) *http.Request {
		r := httptest.NewRequest(http.MethodPost, "/x", strings.NewReader(form.Encode()))
		r.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		_ = r.ParseForm()
		return r
	}
	d := invoiceDetailPayload(req(url.Values{"bic": {" gib acz px "}, "vat_status": {"weird"}, "registry_entry": {""}, "invoice_prefix": {"ab-12 cd34567"},
		"invoice_next_number": {"0"}, "invoice_due_days": {"9999999999999999999999"}}), 2026)
	want := map[string]any{"bic": "GIBACZPX", "vat_status": "non_payer", "registry_entry": nil, "invoice_prefix": "AB12CD",
		"invoice_next_number": nil, "invoice_next_number_year": nil, "invoice_due_days": int64(365)}
	for k, v := range want {
		if d[k] != v {
			t.Errorf("%s: %#v want %#v", k, d[k], v)
		}
	}
	d = invoiceDetailPayload(req(url.Values{"invoice_next_number": {"7"}, "invoice_due_days": {"x"}}), 2026)
	if d["invoice_next_number"] != int64(7) || d["invoice_next_number_year"] != int64(2026) || d["invoice_due_days"] != int64(14) {
		t.Errorf("%#v", d)
	}
	if len(invoiceDetailPayload(req(url.Values{}), 2026)) != 0 {
		t.Error("absent fields must stay absent")
	}
}

func TestWithCountryCode(t *testing.T) {
	for _, c := range [][3]string{
		{"420", "777 123 456", "+420777123456"}, {"+420", "777123456", "+420777123456"}, {"420", "+49 30 1234", "+49301234"},
		{"420", "00 49 30 1", "+49301"}, {"4200", "777", "777"}, {"", "777123456", "777123456"}, {"420", "", ""}, {"420", "ext 5", "ext 5"},
	} {
		if got := withCountryCode(c[0], c[1]); got != c[2] {
			t.Errorf("%v: %q", c, got)
		}
	}
}

func TestDrawnSignature(t *testing.T) {
	png := "data:image/png;base64," + base64.StdEncoding.EncodeToString([]byte("\x89PNGxxxx"))
	jpg := "data:image/jpeg;base64," + base64.StdEncoding.EncodeToString([]byte("\xff\xd8\xffxxxx"))
	big := "data:image/png;base64," + base64.StdEncoding.EncodeToString(append([]byte("\x89PNG"), make([]byte, maxSignatureBytes)...))
	for in, ok := range map[string]bool{png: true, jpg: true, big: false, "data:image/png;base64," + base64.StdEncoding.EncodeToString([]byte("GIF89a")): false,
		"data:image/gif;base64,AAAA": false, "data:image/png;base64,!!!": false, "": false, "data:image/png;base64,iVBO\nRw==": false} {
		if got := drawnSignature(in) != ""; got != ok {
			t.Errorf("%.40q: %v", in, got)
		}
	}
}

func TestEntitySave(t *testing.T) {
	pool := testPool(t)
	seedHosts(t, pool)
	mux := entityMux(pool)
	form := func(extra map[string]string) url.Values {
		v := url.Values{"name": {"  New Co "}, "seat": {"Praha 1"}, "ico": {goodICO}, "dic": {"CZ12345679"}, "contact_email": {"a@example.com"},
			"contact_phone_country_code": {"420"}, "contact_phone": {"777 123 456"}, "bank_account": {goodAccount}, "bic": {"gib acz px"},
			"vat_status": {"payer"}, "registry_entry": {"C 1"}, "invoice_prefix": {"ab-12 cd34567"}, "invoice_next_number": {"5"}, "invoice_due_days": {"400"}}
		for k, x := range extra {
			v.Set(k, x)
		}
		return v
	}
	// create_entity, first business of a host with no property: continue to the first property.
	rec := post(t, mux, "/entities", 130001, 0, "en", form(nil))
	id := oneInt(t, pool, `SELECT id FROM legal_entity WHERE name = 'New Co'`)
	if loc := rec.Header().Get("Location"); rec.Code != http.StatusSeeOther || !strings.HasPrefix(loc, "/apartments/new?legal_entity_id="+intString(id)+"&msg=Added%20New%20Co.%20Next") {
		t.Errorf("first entity: %d %q", rec.Code, loc)
	}
	e := readEntity(t, pool, id)
	if e.owner != 130001 || e.seat != "Praha 1" || e.ico != goodICO || e.phone != "+420777123456" || e.bank != goodAccount || e.iban != goodIBAN ||
		e.bic != "GIBACZPX" || e.vat != "payer" || e.prefix != "AB12CD" || e.next == nil || *e.next != 5 || *e.year != 2026 || *e.due != 365 || e.sig != nil {
		t.Errorf("row %+v", e)
	}
	if n := oneInt(t, pool, `SELECT COUNT(*) FROM legal_entity WHERE name = 'New Co' AND created_at = '2026-11-13T10:00:00+00:00'`); n != 1 {
		t.Error("created_at is the request clock")
	}

	// With a property: back to the list; with next: back there.
	mustExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, legal_entity_id, created_at) VALUES (130201, 130001, 'Flat', $1, $2)`, id, stamp0)
	rec = post(t, mux, "/entities", 130001, 0, "en", form(map[string]string{"name": "Second"}))
	if loc := rec.Header().Get("Location"); loc != "/entities?msg=Added%20Second." && !strings.HasPrefix(loc, "/entities?msg=Added%20Second.&toast_kind=success") {
		t.Errorf("second entity: %q", loc)
	}
	rec = post(t, mux, "/entities", 130001, 0, "en", form(map[string]string{"name": "Third", "next": "/apartments/130201?view=settings"}))
	if loc := rec.Header().Get("Location"); !strings.HasPrefix(loc, "/apartments/130201?view=settings&msg=Added%20Third.") {
		t.Errorf("with next: %q", loc)
	}
	rec = post(t, mux, "/entities", 130001, 0, "en", form(map[string]string{"name": "Fourth", "next": "https://evil.example/"}))
	if loc := rec.Header().Get("Location"); !strings.HasPrefix(loc, "/entities?msg=Added%20Fourth.") {
		t.Errorf("unsafe next: %q", loc)
	}

	// Refusals write nothing.
	before := oneInt(t, pool, `SELECT COUNT(*) FROM legal_entity`)
	for _, c := range []struct {
		name  string
		extra map[string]string
		err   string
	}{
		{"blank name", map[string]string{"name": "   "}, "Please%20enter%20a%20name."},
		{"bad ico", map[string]string{"ico": "12345678"}, "That%20company%20ID"},
		{"bad account", map[string]string{"bank_account": "19-2000145398/0800"}, "That%20account%20number%20is%20not%20valid"},
		{"bad signature", map[string]string{"signature_drawn": "data:image/png;base64,AAAA"}, "The%20signature%20must%20be"},
	} {
		rec = post(t, mux, "/entities", 130001, 0, "en", form(c.extra))
		if loc := rec.Header().Get("Location"); !strings.HasPrefix(loc, "/entities?err="+c.err) {
			t.Errorf("%s: %q", c.name, loc)
		}
	}
	if oneInt(t, pool, `SELECT COUNT(*) FROM legal_entity`) != before {
		t.Error("a refused save wrote a row")
	}
	// Signed out; and the register button is not served yet.
	if rec = post(t, mux, "/entities", 0, 0, "en", form(nil)); !strings.HasPrefix(rec.Header().Get("Location"), "/login") {
		t.Errorf("signed out: %q", rec.Header().Get("Location"))
	}
}

func intString(n int64) string {
	if n == 0 {
		return "0"
	}
	var b []byte
	for ; n > 0; n /= 10 {
		b = append([]byte{byte('0' + n%10)}, b...)
	}
	return string(b)
}

func TestEntitySignature(t *testing.T) {
	pool := testPool(t)
	seedHosts(t, pool)
	mux := entityMux(pool)
	keys, err := secure.LoadDataKeys(testEnv)
	if err != nil {
		t.Fatal(err)
	}
	png := "data:image/png;base64," + base64.StdEncoding.EncodeToString([]byte("\x89PNGdrawn"))
	base := url.Values{"name": {"Signer"}, "signature_drawn": {png}, "signature_name": {"  " + strings.Repeat("x", 90) + "  "}}
	post(t, mux, "/entities", 130001, 0, "en", base)
	id := oneInt(t, pool, `SELECT id FROM legal_entity WHERE name = 'Signer'`)
	e := readEntity(t, pool, id)
	if e.sig == nil || *e.sigName == "" || len(*e.sigName) != 80 {
		t.Fatalf("signature row %+v", e)
	}
	plain, err := keys.Decrypt(*e.sig, 0, testNow)
	if err != nil || string(plain) != png {
		t.Errorf("decrypt: %q %v", plain, err)
	}
	// An upload wins over the drawing; its bytes are stored as a data URL.
	rec := multipartPost(t, mux, "/entities/"+intString(id), 130001, map[string]string{"name": "Signer", "signature_drawn": png},
		map[string][]byte{"signature_file": []byte("\xff\xd8\xffjpegbytes")})
	if rec.Code != http.StatusSeeOther || !strings.HasPrefix(rec.Header().Get("Location"), "/entities?msg=Saved.") {
		t.Fatalf("upload: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	e = readEntity(t, pool, id)
	plain, _ = keys.Decrypt(*e.sig, 0, testNow)
	if string(plain) != "data:image/jpeg;base64,"+base64.StdEncoding.EncodeToString([]byte("\xff\xd8\xffjpegbytes")) {
		t.Errorf("stored %q", plain)
	}
	// An upload that is not an image is refused and nothing changes.
	rec = multipartPost(t, mux, "/entities/"+intString(id), 130001, map[string]string{"name": "Changed"}, map[string][]byte{"signature_file": []byte("GIF89a")})
	if !strings.Contains(rec.Header().Get("Location"), "err=The%20signature%20must%20be") || readEntity(t, pool, id).name != "Signer" {
		t.Errorf("bad upload: %q", rec.Header().Get("Location"))
	}
	// signature_remove clears it.
	post(t, mux, "/entities/"+intString(id), 130001, 0, "en", url.Values{"name": {"Signer"}, "signature_remove": {"1"}})
	if readEntity(t, pool, id).sig != nil {
		t.Error("signature_remove did not clear the signature")
	}
}

func TestEntityUpdate(t *testing.T) {
	pool := testPool(t)
	seedHosts(t, pool)
	mux := entityMux(pool)
	mustExec(t, pool, `INSERT INTO legal_entity (id, owner_user_id, name, seat, bank_account, iban, vat_status, created_at, archived_at) VALUES
		(130101, 130001, 'Mine', 'Old seat', '123/0100', 'KEEP', 'payer', $1, NULL),
		(130102, 130002, 'Theirs', NULL, NULL, NULL, 'non_payer', $1, NULL),
		(130103, 130001, 'Archived', NULL, NULL, NULL, 'non_payer', $1, $1)`, stamp0)
	mustExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, legal_entity_id, created_at) VALUES (130201, 130001, 'Flat', 130101, $1)`, stamp0)
	mustExec(t, pool, `INSERT INTO alert (id, level, kind, apartment_id, owner_user_id, dedupe_key, message, created_at) VALUES
		(901, 'critical', 'controller_missing', 130201, 130001, 'controller_missing:130201', 'm', $1)`, stamp0)

	// Another host's business, and an unknown one.
	for _, id := range []string{"130102", "999999"} {
		rec := post(t, mux, "/entities/"+id, 130001, 0, "en", url.Values{"name": {"Hijack"}})
		if loc := rec.Header().Get("Location"); !strings.HasPrefix(loc, "/entities?err=") {
			t.Errorf("%s: %q", id, loc)
		}
	}
	if readEntity(t, pool, 130102).name != "Theirs" {
		t.Error("another host's business was changed")
	}
	if rec := post(t, mux, "/entities/abc", 130001, 0, "en", url.Values{"name": {"x"}}); rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("bad id: %d", rec.Code)
	}
	// A short form only touches what it carries; the controller card clears once the identity is complete.
	post(t, mux, "/entities/130101", 130001, 0, "en", url.Values{"name": {"Mine 2"}, "seat": {"New seat"}})
	e := readEntity(t, pool, 130101)
	if e.name != "Mine 2" || e.seat != "New seat" || e.bank != "123/0100" || e.iban != "KEEP" || e.vat != "payer" {
		t.Errorf("partial update %+v", e)
	}
	if n := oneInt(t, pool, `SELECT COUNT(*) FROM alert WHERE id = 901 AND resolved_at IS NULL`); n != 1 {
		t.Error("controller_missing cleared without a contact e-mail")
	}
	rec := post(t, mux, "/entities/130101", 130001, 0, "en", url.Values{"name": {"Mine 2"}, "contact_email": {"m@example.com"}, "next": {"/apartments/130201?view=settings"}})
	if loc := rec.Header().Get("Location"); !strings.HasPrefix(loc, "/apartments/130201?view=settings&msg=Saved.") {
		t.Errorf("next: %q", loc)
	}
	if n := oneInt(t, pool, `SELECT COUNT(*) FROM alert WHERE id = 901 AND resolved_at IS NOT NULL`); n != 1 {
		t.Error("controller_missing not cleared")
	}
	// Sent blank clears, and an archived business can still be edited.
	post(t, mux, "/entities/130101", 130001, 0, "en", url.Values{"name": {"Mine 2"}, "bank_account": {""}, "bic": {""}})
	if e = readEntity(t, pool, 130101); e.bank != "~" || e.iban != "~" || e.bic != "~" {
		t.Errorf("blank should clear: %+v", e)
	}
	post(t, mux, "/entities/130103", 130001, 0, "en", url.Values{"name": {"Archived 2"}})
	if readEntity(t, pool, 130103).name != "Archived 2" {
		t.Error("archived entity not updated")
	}
}
