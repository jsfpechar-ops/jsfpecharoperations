package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestInvoiceRoutesRegistered checks that every ported invoice route reaches
// its own pattern, and that the one still on Python does not exist in Go.
func TestInvoiceRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/invoices", "GET /invoices"},
		{http.MethodPost, "/invoices", "POST /invoices"},
		{http.MethodGet, "/invoices/new", "GET /invoices/new"},
		{http.MethodPost, "/invoices/preview", "POST /invoices/preview"},
		{http.MethodGet, "/invoices/12", "GET /invoices/{id}"},
		{http.MethodGet, "/invoices/12.pdf", "GET /invoices/{id}"},
		{http.MethodPost, "/invoices/12/paid", "POST /invoices/{id}/paid"},
		{http.MethodPost, "/invoices/12/cancel", "POST /invoices/{id}/cancel"},
		{http.MethodGet, "/invoice/d/sometoken", "GET /invoice/d/{token}"},
		// Still Python: the send route waits for brief 1429.
		{http.MethodPost, "/invoices/12/send", "/"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
