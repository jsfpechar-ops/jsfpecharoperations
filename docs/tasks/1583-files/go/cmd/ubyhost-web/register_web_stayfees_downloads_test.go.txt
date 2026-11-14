package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestStayFeesDownloadRoutesRegistered checks the PDF routes of brief 1583.
func TestStayFeesDownloadRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/stay-fees/12/pdf", "GET /stay-fees/{apartment_id}/pdf"},
		{http.MethodGet, "/stay-fees/pdfs.zip", "GET /stay-fees/pdfs.zip"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
