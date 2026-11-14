package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// billingRoutes is each method and path of routes/billing.py and routes/admin_billing.py
// that the briefs 1555 to 1559 have ported, with the pattern that must answer it.
var billingRoutes = []struct{ method, path, pattern string }{
	{http.MethodGet, "/predplatne/faktury/5.pdf", "GET /predplatne/faktury/{file}"},
	{http.MethodPost, "/predplatne/zrusit", "POST /predplatne/zrusit"},
	{http.MethodPost, "/predplatne/obnovit", "POST /predplatne/obnovit"},
	{http.MethodGet, "/admin/fakturace/5.pdf", "GET /admin/fakturace/{file}"},
	{http.MethodGet, "/predplatne", "GET /predplatne"},
	{http.MethodPost, "/predplatne", "POST /predplatne"},
	{http.MethodPost, "/predplatne/zmena", "POST /predplatne/zmena"},
	{http.MethodPost, "/admin/fakturace/vypis", "POST /admin/fakturace/vypis"},
	{http.MethodPost, "/admin/fakturace/5/zaplaceno", "POST /admin/fakturace/{invoice_id}/zaplaceno"},
	{http.MethodPost, "/admin/fakturace/5/storno", "POST /admin/fakturace/{invoice_id}/storno"},
	{http.MethodGet, "/admin/fakturace/export-vse", "GET /admin/fakturace/export-vse"},
	{http.MethodGet, "/admin/fakturace/export", "GET /admin/fakturace/export"},
}

// TestBillingRoutesRegistered checks that each ported billing route reaches
// its own pattern and that no route falls into the catch-all.
func TestBillingRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range billingRoutes {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
