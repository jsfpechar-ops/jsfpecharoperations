package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestPaymentsQRPageRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	_, hostPat := mux.Handler(httptest.NewRequest(http.MethodGet, "/payments/qr/42.png", nil))
	if hostPat != "GET /payments/qr/{file}" {
		t.Errorf("host pattern %q, want GET /payments/qr/{file}", hostPat)
	}
	_, guestPat := mux.Handler(httptest.NewRequest(http.MethodGet, "/pay/1/abcd", nil))
	if guestPat != "GET /pay/{id}/{file}" {
		t.Errorf("guest pattern %q, want GET /pay/{id}/{file}", guestPat)
	}
}
