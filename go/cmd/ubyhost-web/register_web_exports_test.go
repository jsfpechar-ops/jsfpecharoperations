package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// exportRoutes is each method and path of App/app/routes/exports.py that
// briefs 1320, 1321 and 1605 to 1609 have ported, with the pattern that must
// answer it (13 of 13).
var exportRoutes = []struct{ method, path, pattern string }{
	{http.MethodGet, "/reservations.csv", "GET /reservations.csv"},
	{http.MethodGet, "/submissions/receipts.zip", "GET /submissions/receipts.zip"},
	{http.MethodGet, "/submissions/5/receipt.pdf", "GET /submissions/{id}/receipt.pdf"},
	{http.MethodGet, "/submissions/5/errors.pdf", "GET /submissions/{id}/errors.pdf"},
	{http.MethodGet, "/submissions/5/request.xml", "GET /submissions/{id}/{file}"},
	{http.MethodGet, "/reservations/5/dorucenka.zip", "GET /reservations/{id}/dorucenka.zip"},
	{http.MethodGet, "/housebook.csv", "GET /housebook.csv"},
	{http.MethodGet, "/guests/5/export.json", "GET /guests/{id}/export.json"},
	{http.MethodGet, "/guests/5/form.pdf", "GET /guests/{id}/form.pdf"},
	{http.MethodGet, "/housebook/pdfs.zip", "GET /housebook/pdfs.zip"},
	{http.MethodPost, "/settings/workspace-export", "POST /settings/workspace-export"},
	{http.MethodGet, "/settings/archived", "GET /settings/archived"},
	{http.MethodPost, "/settings/purge-expired", "POST /settings/purge-expired"},
}

// TestExportRoutesRegistered checks that each ported export route reaches its
// own pattern on the service mux and that none falls into the catch-all.
func TestExportRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range exportRoutes {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
