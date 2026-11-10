package payments

import (
	"bytes"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestGuestToken(t *testing.T) {
	// Value computed with Python payment_request.guest_token for the same input.
	secret := strings.Repeat("k", 32)
	if got := guestToken(secret, 10, "2600000010"); got != "4e32f618faa135220ad4fe38d14f1805" {
		t.Errorf("guestToken = %q", got)
	}
}

func TestPaylinkNameCustomNote(t *testing.T) {
	long := strings.Repeat("ž", 70)
	for _, c := range []struct {
		reason, note string
		want         string
	}{
		{"custom", "  Klíče   od  auta ", "Klíče od auta (žádost č. 7)"},
		{"custom", "", "Vlastní (žádost č. 7)"},
		{"repair", "ignored", "Příspěvek na opravu (žádost č. 7)"},
		{"custom", long, strings.Repeat("ž", 60) + " (žádost č. 7)"},
	} {
		if got := paylinkName(c.reason, c.note, 7); got != c.want {
			t.Errorf("paylinkName(%q, %q) = %q, want %q", c.reason, c.note, got, c.want)
		}
	}
}

func TestGuestQRPNGDatabase(t *testing.T) {
	pool := testPool(t)
	requestSeed(t, pool)
	env := connectEnv("test", nil)
	mux := http.NewServeMux()
	mux.Handle("GET /pay/{id}/{file}", GuestQRPNGHandler(pool, env))
	if _, err := pool.Exec(t.Context(), `UPDATE legal_entity SET iban = 'CZ6508000000192000145399' WHERE owner_user_id = 1`); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(t.Context(), `UPDATE payment_request SET variable_symbol = '2600000010' WHERE id = 10`); err != nil {
		t.Fatal(err)
	}
	good := guestToken(connectTestSecret, 10, "2600000010")
	get := func(path string) *httptest.ResponseRecorder {
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, path, nil))
		return rec
	}
	rec := get(fmt.Sprintf("/pay/10/%s.png", good))
	if rec.Code != http.StatusOK || rec.Header().Get("Content-Type") != "image/png" ||
		rec.Header().Get("Cache-Control") != "private, max-age=300" ||
		!bytes.HasPrefix(rec.Body.Bytes(), []byte("\x89PNG\r\n\x1a\n")) {
		t.Fatalf("good token: %d %v", rec.Code, rec.Header())
	}
	for name, path := range map[string]string{
		"wrong token":     "/pay/10/" + strings.Repeat("0", 32) + ".png",
		"no png suffix":   "/pay/10/" + good,
		"card rail":       "/pay/11/" + good + ".png",
		"missing request": "/pay/999/" + good + ".png",
		"non digit id":    "/pay/1x/" + good + ".png",
	} {
		if rec := get(path); rec.Code != http.StatusNotFound || rec.Body.Len() != 0 {
			t.Errorf("%s: %d with %d body bytes, want empty 404", name, rec.Code, rec.Body.Len())
		}
	}
	if _, err := pool.Exec(t.Context(), `UPDATE legal_entity SET iban = NULL, bank_account = NULL WHERE owner_user_id = 1`); err != nil {
		t.Fatal(err)
	}
	rec = get(fmt.Sprintf("/pay/10/%s.png", good))
	if rec.Code != http.StatusNotFound || rec.Header().Get("Content-Type") != "text/plain; charset=utf-8" || rec.Body.String() != qrNoAccountBody {
		t.Errorf("no bank account: %d %q %q, want the plain 404 body", rec.Code, rec.Header().Get("Content-Type"), rec.Body.String())
	}
	if rec := get("/pay/10/" + strings.Repeat("0", 32) + ".png"); rec.Code != http.StatusNotFound || rec.Body.Len() != 0 {
		t.Errorf("wrong token without account: %d with %d body bytes, want empty 404", rec.Code, rec.Body.Len())
	}
	if _, err := pool.Exec(t.Context(), `UPDATE legal_entity SET iban = 'CZ6508000000192000145399' WHERE owner_user_id = 1`); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(t.Context(), `UPDATE payment_request SET status = 'cancelled' WHERE id = 10`); err != nil {
		t.Fatal(err)
	}
	if rec := get(fmt.Sprintf("/pay/10/%s.png", good)); rec.Code != http.StatusNotFound {
		t.Errorf("cancelled: %d, want 404", rec.Code)
	}
}

func TestRequestLinkDatabase(t *testing.T) {
	pool := testPool(t)
	requestSeed(t, pool)
	env := connectEnv("test", nil)
	links := &fakeLinks{url: "https://pay.stripe.example/test_link"}
	mux := http.NewServeMux()
	mux.Handle("POST /payments/requests/{id}/link", RequestLinkHandler(pool, env, connectNow, links))
	post := func(path string, uid int64) *httptest.ResponseRecorder {
		return requestCall(t, mux, path, uid, nil)
	}

	if rec := post("/payments/requests/abc/link", 1); rec.Code != http.StatusNotFound {
		t.Errorf("non-integer id: %d, want 404", rec.Code)
	}
	for name, id := range map[string]int{"other owner": 16, "qr rail": 10, "paid": 12, "missing": 999} {
		rec := post(fmt.Sprintf("/payments/requests/%d/link", id), 1)
		if !strings.HasPrefix(rec.Header().Get("Location"), "/payments?err=") {
			t.Errorf("%s: Location %q", name, rec.Header().Get("Location"))
		}
	}
	if links.calls != 0 {
		t.Errorf("link made for an invalid request: %d calls", links.calls)
	}

	rec := post("/payments/requests/11/link", 1)
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/payments/requests/11/share" {
		t.Fatalf("draft card: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	if requestStatus(t, pool, 11) != "sent" {
		t.Error("draft did not move to sent")
	}
	if !containsDetail(auditDetails(t, pool, "payment_request_status"), "id=11 draft->sent") {
		t.Error("no draft->sent audit row")
	}

	links.url = ""
	rec = post("/payments/requests/11/link", 1)
	if loc := rec.Header().Get("Location"); !strings.HasPrefix(loc, "/payments?err=") || !strings.HasSuffix(loc, "&fix=stripe") {
		t.Errorf("not ready: %q", loc)
	}
}
