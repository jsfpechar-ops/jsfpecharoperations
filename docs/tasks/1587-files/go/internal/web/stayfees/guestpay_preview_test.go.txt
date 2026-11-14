package stayfees

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"image/png"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"
)

const (
	gpCZIBAN = "CZ6508000000192000145399" // 19-2000145399/0800
	gpGBIBAN = "GB82WEST12345698765432"
)

// gpEnv is goldenEnv with the guest-pay switch on or off.
func gpEnv(on string) func(string) string {
	base := goldenEnv()
	return func(k string) string {
		if k == "UBYHOST_STAY_FEE_GUEST_PAY" {
			return on
		}
		return base(k)
	}
}

type gpAnswer struct {
	OK      bool   `json:"ok"`
	Invalid bool   `json:"invalid"`
	Account string `json:"account"`
	QR      string `json:"qr"`
}

type gpResult struct {
	code int
	body string
	loc  string
	gp   gpAnswer
}

func TestGuestPayPreview(t *testing.T) {
	pool := testPool(t)
	g := loadGolden(t)
	seed(t, pool, g)
	ctx := context.Background()
	// Made-up operators: A has a Czech account only, B has an IBAN and a
	// different Czech account. Property 11: A, 14: B, 18: none.
	for _, q := range []string{
		`INSERT INTO legal_entity (id, name, owner_user_id, created_at, bank_account) OVERRIDING SYSTEM VALUE VALUES (901, 'Operator A', 1, '2026-09-01T00:00:00+00:00', '19-2000145399/0800')`,
		`INSERT INTO legal_entity (id, name, owner_user_id, created_at, bank_account, iban) OVERRIDING SYSTEM VALUE VALUES (902, 'Operator B', 1, '2026-09-01T00:00:00+00:00', '123/0300', '` + gpGBIBAN + `')`,
		`UPDATE apartment SET legal_entity_id = 901 WHERE id = 11`,
		`UPDATE apartment SET legal_entity_id = 902 WHERE id = 14`,
	} {
		if _, err := pool.Exec(ctx, q); err != nil {
			t.Fatal(err)
		}
	}
	at, err := time.Parse(time.RFC3339, g.Now)
	if err != nil {
		t.Fatal(err)
	}
	mux := func(on string) *http.ServeMux {
		m := http.NewServeMux()
		m.Handle("POST /stay-fees/{apartment_id}/guest-pay-preview", GuestPayPreviewHandler(pool, gpEnv(on), func() time.Time { return at }))
		return m
	}
	post := func(on, path string, who *string, token bool, form map[string]string) gpResult {
		v := url.Values{}
		for k, val := range form {
			v.Set(k, val)
		}
		req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(v.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		if token {
			ck, tok := csrfPair(t, at)
			req.AddCookie(ck)
			req.Header.Set("X-CSRF-Token", tok)
		}
		if who != nil {
			req.AddCookie(&http.Cookie{Name: "ubyhost_session", Value: sessionFor(*who, at)})
		}
		rec := httptest.NewRecorder()
		mux(on).ServeHTTP(rec, req)
		r := gpResult{code: rec.Code, body: rec.Body.String(), loc: rec.Header().Get("Location")}
		if rec.Code == http.StatusOK {
			if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
				t.Errorf("content type %q", ct)
			}
			if err := json.Unmarshal(rec.Body.Bytes(), &r.gp); err != nil {
				t.Fatalf("body %q: %v", r.body, err)
			}
		}
		return r
	}
	host1 := "host1"
	preview := func(apt string, form map[string]string) gpResult {
		return post("on", "/stay-fees/"+apt+"/guest-pay-preview", &host1, true, form)
	}
	// qrOK checks the data URI is a 6 px, 4-module-border PNG of a version 4 code
	// (the size Python's qrcode makes for these payloads: 41 modules).
	qrOK := func(name, uri string) {
		t.Helper()
		raw, ok := strings.CutPrefix(uri, "data:image/png;base64,")
		if !ok {
			t.Errorf("%s: qr %.30q", name, uri)
			return
		}
		b, err := base64.StdEncoding.DecodeString(raw)
		if err != nil {
			t.Fatal(err)
		}
		img, err := png.Decode(bytes.NewReader(b))
		if err != nil {
			t.Fatalf("%s: png: %v", name, err)
		}
		if sz := img.Bounds().Size(); sz.X != 246 || sz.Y != 246 {
			t.Errorf("%s: image %v, want 246x246", name, sz)
		}
	}

	// Valid Czech account typed; exact JSON shape (no spaces, key order).
	r := preview("12", map[string]string{"account": " 19-2000145399/0800 ", "rate": "20"})
	if r.code != 200 || !r.gp.OK || r.gp.Invalid || r.gp.Account != "CZ65 0800 0000 1920 0014 5399" {
		t.Fatalf("czech account: %+v", r)
	}
	if !strings.HasPrefix(r.body, `{"ok":true,"invalid":false,"account":"CZ65 0800 0000 1920 0014 5399","qr":"data:image/png;base64,`) {
		t.Errorf("body shape %.120q", r.body)
	}
	qrOK("czech", r.gp.QR)
	rate20 := r.gp.QR

	// Valid IBAN typed (spaces and lower case are fine).
	r = preview("12", map[string]string{"account": "gb82 west 1234 5698 7654 32"})
	if r.code != 200 || !r.gp.OK || r.gp.Account != "GB82 WEST 1234 5698 7654 32" {
		t.Fatalf("iban: %+v", r)
	}
	qrOK("iban", r.gp.QR)

	// Invalid typed account: not ok, invalid, nothing shown, even when an account is on file.
	for _, apt := range []string{"12", "11"} {
		r = preview(apt, map[string]string{"account": "12345/0100"})
		if r.code != 200 || r.gp.OK || !r.gp.Invalid || r.gp.Account != "" || r.gp.QR != "" {
			t.Errorf("invalid typed, property %s: %+v", apt, r)
		}
	}
	// Bad checksum IBAN is invalid too.
	r = preview("12", map[string]string{"account": "GB82WEST12345698765433"})
	if r.gp.OK || !r.gp.Invalid {
		t.Errorf("bad iban: %+v", r)
	}

	// Nothing typed, operator Czech account on file (property 11).
	r = preview("11", map[string]string{"account": ""})
	if r.code != 200 || !r.gp.OK || r.gp.Invalid || r.gp.Account != "CZ65 0800 0000 1920 0014 5399" {
		t.Fatalf("entity czech account: %+v", r)
	}
	qrOK("entity czech", r.gp.QR)
	// Nothing typed, operator with an IBAN (property 14): the IBAN wins over its Czech account.
	r = preview("14", nil)
	if r.code != 200 || !r.gp.OK || r.gp.Account != "GB82 WEST 1234 5698 7654 32" {
		t.Fatalf("entity iban: %+v", r)
	}
	// Nothing typed and no operator (property 18): not ok, not invalid.
	r = preview("18", map[string]string{"account": "   "})
	if r.code != 200 || r.gp.OK || r.gp.Invalid || r.gp.Account != "" || r.gp.QR != "" {
		t.Errorf("no operator: %+v", r)
	}
	if r.body != `{"ok":false,"invalid":false,"account":"","qr":""}` {
		t.Errorf("empty body %q", r.body)
	}

	// The rate only changes the sample amount: same as no rate for text, zero, and
	// out-of-range values; "1_0" is 10 as in Python; "-3" is clamped to 1.
	same := func(a, b map[string]string, wantSame bool) {
		t.Helper()
		x, y := preview("11", a), preview("11", b)
		if x.code != 200 || y.code != 200 || (x.gp.QR == y.gp.QR) != wantSame {
			t.Errorf("rate %v vs %v: same=%v, want %v", a, b, x.gp.QR == y.gp.QR, wantSame)
		}
	}
	none := map[string]string{}
	same(map[string]string{"rate": "abc"}, none, true)
	same(map[string]string{"rate": "12.5"}, none, true)
	same(map[string]string{"rate": "0"}, none, true)
	same(map[string]string{"rate": "50"}, none, true)
	same(map[string]string{"rate": "999999999999999999999999"}, none, true)
	same(map[string]string{"rate": "1_0"}, map[string]string{"rate": "10"}, true)
	same(map[string]string{"rate": "+10"}, map[string]string{"rate": "10"}, true)
	same(map[string]string{"rate": "-3"}, map[string]string{"rate": "1"}, true)
	same(map[string]string{"rate": "10"}, none, false)
	if x := preview("12", map[string]string{"account": "19-2000145399/0800", "rate": "20"}); x.gp.QR != rate20 {
		t.Error("the same input does not give the same image")
	}
	// Property 12 has its own rate of 50; property 14 (rate 0) falls back to 50;
	// a typed rate beats the property's own.
	a, b := preview("12", map[string]string{"account": gpGBIBAN}), preview("12", map[string]string{"account": gpGBIBAN, "rate": "7"})
	if a.gp.QR == b.gp.QR {
		t.Error("typed rate ignored")
	}

	// Refusals: foreign property, missing property, switch off.
	for _, apt := range []string{"20", "9999", "99999999999999999999999"} {
		r = preview(apt, map[string]string{"account": gpGBIBAN})
		if r.code != 404 || r.body != `{"ok":false}` {
			t.Errorf("property %s: %+v", apt, r)
		}
	}
	r = post("off", "/stay-fees/12/guest-pay-preview", &host1, true, map[string]string{"account": gpGBIBAN})
	if r.code != 404 || r.body != `{"ok":false}` {
		t.Errorf("switch off: %+v", r)
	}
	r = post("", "/stay-fees/12/guest-pay-preview", &host1, true, nil)
	if r.code != 404 {
		t.Errorf("switch unset: %+v", r)
	}
	r = post(" ON ", "/stay-fees/12/guest-pay-preview", &host1, true, nil)
	if r.code != 200 {
		t.Errorf("switch ' ON ': %+v", r)
	}
	// Host 2 cannot see host 1's property, and host 1 cannot see host 2's.
	host2 := "host2"
	r = post("on", "/stay-fees/12/guest-pay-preview", &host2, true, nil)
	if r.code != 404 {
		t.Errorf("foreign owner: %+v", r)
	}

	// Signed out: the login redirect, no answer body. No CSRF token: refused, nothing computed.
	r = post("on", "/stay-fees/12/guest-pay-preview", nil, true, map[string]string{"account": gpGBIBAN})
	if r.code != http.StatusSeeOther || !strings.HasPrefix(r.loc, "/login") {
		t.Errorf("signed out: %+v", r)
	}
	r = post("on", "/stay-fees/12/guest-pay-preview", &host1, false, map[string]string{"account": gpGBIBAN})
	if r.code == 200 || strings.Contains(r.body, "data:image") {
		t.Errorf("no csrf token: %+v", r)
	}
	// A path id that is not an integer is 422 as in FastAPI.
	r = post("on", "/stay-fees/abc/guest-pay-preview", &host1, true, nil)
	if r.code != http.StatusUnprocessableEntity {
		t.Errorf("text id: %+v", r)
	}
	// GET is not allowed on this path.
	req := httptest.NewRequest(http.MethodGet, "/stay-fees/12/guest-pay-preview", nil)
	rec := httptest.NewRecorder()
	mux("on").ServeHTTP(rec, req)
	if rec.Code != http.StatusMethodNotAllowed && rec.Code != http.StatusNotFound {
		t.Errorf("GET: %d", rec.Code)
	}
}

func TestGuestPayParseRate(t *testing.T) {
	for in, want := range map[string]string{
		"": "", "0": "", "abc": "", "12": "12", "-5": "-5", "+7": "7", "1_0": "10", "1__0": "", "_1": "",
		"1_": "", "1.5": "", "-": "", "007": "7",
	} {
		got := ""
		if n := guestpayParseRate(in); n != nil {
			got = n.String()
		}
		if got != want {
			t.Errorf("guestpayParseRate(%q) = %q, want %q", in, got, want)
		}
	}
}
