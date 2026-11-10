package payments

import (
	"bytes"
	"image/png"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// Expected values were computed with App/app/payments.py (spayd, normalise_account,
// ascii_upper, qr_png_bytes) under App/.venv.

func TestQRSPAYDIBAN(t *testing.T) {
	got := qrSPAYD("CZ6508000000192000145399", 1250, "2026110201", "UbyHost payment request")
	want := "SPD*1.0*ACC:CZ6508000000192000145399*AM:1250.00*CC:CZK*X-VS:2026110201*MSG:UBYHOST PAYMENT REQUEST"
	if got != want {
		t.Fatalf("spayd = %q, want %q", got, want)
	}
}

func TestQRNormaliseAccount(t *testing.T) {
	display, iban, err := qrNormaliseAccount("19-2000145399/0800")
	if err != nil || display != "19-2000145399/0800" || iban != "CZ6508000000192000145399" {
		t.Fatalf("prefix account = %q %q %v", display, iban, err)
	}
	display, iban, err = qrNormaliseAccount("2000145399/0800")
	if err != nil || display != "2000145399/0800" || iban != "CZ7908000000002000145399" {
		t.Fatalf("plain account = %q %q %v", display, iban, err)
	}
	display, iban, err = qrNormaliseAccount("cz65 0800 0000 1920 0014 5399")
	if err != nil || display != "CZ6508000000192000145399" || iban != "CZ6508000000192000145399" {
		t.Fatalf("iban = %q %q %v", display, iban, err)
	}
	if _, _, err := qrNormaliseAccount("CZ6508000000192000145398"); err == nil {
		t.Fatal("bad IBAN checksum accepted")
	}
	if _, _, err := qrNormaliseAccount("2000145398/0800"); err == nil {
		t.Fatal("bad account checksum accepted")
	}
}

func TestQRSPAYDMessageFromAccount(t *testing.T) {
	_, iban, err := qrNormaliseAccount("19-2000145399/0800")
	if err != nil {
		t.Fatal(err)
	}
	got := qrSPAYD(iban, 99, "42", "Úhrada za oprava: ß straße  ﬁ ŉ, Ěšč ąę")
	want := "SPD*1.0*ACC:CZ6508000000192000145399*AM:99.00*CC:CZK*X-VS:42*MSG:UHRADA ZA OPRAVA: SS STRASSE FI N ESC AE"
	if got != want {
		t.Fatalf("spayd = %q, want %q", got, want)
	}
}

func TestQRASCIIUpper(t *testing.T) {
	cases := []struct {
		in    string
		limit int
		want  string
	}{
		{"Úhrada za žlutý kůň, opravu střechy a ještě delší text, který má přesahovat šedesát znaků rozhodně", 60,
			"UHRADA ZA ZLUTY KUN OPRAVU STRECHY A JESTE DELSI TEXT KTERY"},
		{"a", 60, "A"},
		{"   x  y   ", 60, "X Y"},
		{"ét́ A_B", 60, "ET A B"},
		{"ab cd ef gh", 5, "AB CD"},
		{"Ab-c/d:e+f$g.h", 60, "AB-C/D:E+F$G.H"},
	}
	for _, c := range cases {
		if got := qrASCIIUpper(c.in, c.limit); got != c.want {
			t.Errorf("qrASCIIUpper(%q, %d) = %q, want %q", c.in, c.limit, got, c.want)
		}
	}
	if got := qrASCIIUpper(string(bytes.Repeat([]byte("a"), 70)), 60); len(got) != 60 {
		t.Errorf("limit: got %d characters, want 60", len(got))
	}
}

func TestQRPNGSize(t *testing.T) {
	payload := qrSPAYD("CZ6508000000192000145399", 1250, "2026110201", "UbyHost payment request")
	raw, err := qrPNGBytes(payload)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.HasPrefix(raw, []byte("\x89PNG\r\n\x1a\n")) {
		t.Fatal("not a PNG")
	}
	img, err := png.Decode(bytes.NewReader(raw))
	if err != nil {
		t.Fatal(err)
	}
	if b := img.Bounds(); b.Dx() != 270 || b.Dy() != 270 {
		t.Fatalf("size %dx%d, want 270x270", b.Dx(), b.Dy())
	}
}

func TestQRPNGID(t *testing.T) {
	for file, want := range map[string]int64{"10.png": 10, "007.png": 7} {
		if id, ok := qrPNGID(file); !ok || id != want {
			t.Errorf("qrPNGID(%q) = %d, %v", file, id, ok)
		}
	}
	for _, file := range []string{"10", "10.jpg", "x.png", "-1.png", ".png", "1.5.png", "99999999999999999999.png"} {
		if _, ok := qrPNGID(file); ok {
			t.Errorf("qrPNGID(%q) accepted", file)
		}
	}
}

func qrGet(t *testing.T, h http.Handler, path string, uid int64) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, path, nil)
	if uid != 0 {
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: connectSession(uid, nil)})
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func TestQRPNGDatabase(t *testing.T) {
	pool := testPool(t)
	requestSeed(t, pool)
	mux := http.NewServeMux()
	mux.Handle("GET /payments/qr/{file}", QRPNGHandler(pool, connectEnv("test", nil), connectNow))
	if _, err := pool.Exec(t.Context(), `UPDATE legal_entity SET iban = 'CZ6508000000192000145399' WHERE owner_user_id = 1`); err != nil {
		t.Fatal(err)
	}

	if rec := qrGet(t, mux, "/payments/qr/10.png", 0); rec.Code != http.StatusSeeOther {
		t.Errorf("signed out: %d, want 303", rec.Code)
	}
	rec := qrGet(t, mux, "/payments/qr/10.png", 1)
	if rec.Code != http.StatusOK || rec.Header().Get("Content-Type") != "image/png" {
		t.Fatalf("good row: %d %q", rec.Code, rec.Header().Get("Content-Type"))
	}
	if !bytes.HasPrefix(rec.Body.Bytes(), []byte("\x89PNG\r\n\x1a\n")) {
		t.Error("good row: body is not a PNG")
	}
	for _, c := range []struct{ name, path string }{
		{"rail card", "/payments/qr/11.png"},
		{"other owner", "/payments/qr/16.png"},
		{"missing row", "/payments/qr/999.png"},
		{"html route", "/payments/qr/10"},
	} {
		if rec := qrGet(t, mux, c.path, 1); rec.Code != http.StatusNotFound || rec.Body.Len() != 0 {
			t.Errorf("%s: %d with body %d bytes, want empty 404", c.name, rec.Code, rec.Body.Len())
		}
	}
	if _, err := pool.Exec(t.Context(), `UPDATE legal_entity SET iban = NULL, bank_account = NULL WHERE owner_user_id = 1`); err != nil {
		t.Fatal(err)
	}
	rec = qrGet(t, mux, "/payments/qr/10.png", 1)
	if rec.Code != http.StatusNotFound || rec.Header().Get("Content-Type") != "text/plain; charset=utf-8" || rec.Body.String() != qrNoAccountBody {
		t.Errorf("no bank account: %d %q %q, want the plain 404 body", rec.Code, rec.Header().Get("Content-Type"), rec.Body.String())
	}
}

func TestQRNormaliseAccountFormat(t *testing.T) {
	if _, _, err := qrNormaliseAccount("2000145399/08"); err == nil {
		t.Fatal("short bank code accepted")
	}
}
