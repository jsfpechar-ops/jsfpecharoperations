package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestHavelRoutesRegistered checks that the four Havel routes and the Leon setup routes reach their own
// patterns, that other methods on those paths get the 405 patterns, and that
// paths next to them are not taken over.
func TestHavelRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/havel", "GET /havel"},
		{http.MethodPost, "/havel", "POST /havel"},
		{http.MethodPost, "/havel/support", "POST /havel/support"},
		{http.MethodPost, "/havel/not-helped", "POST /havel/not-helped"},
		{http.MethodHead, "/havel", "HEAD /havel"},
		{http.MethodPut, "/havel", "PUT /havel"},
		{http.MethodGet, "/havel/support", "GET /havel/support"},
		{http.MethodGet, "/havel/not-helped", "GET /havel/not-helped"},
		{http.MethodGet, "/havelx", "/"},
		{http.MethodGet, "/apartments/5/leon/setup", "GET /apartments/{id}/leon/setup"},
		{http.MethodPost, "/apartments/5/leon/setup", "POST /apartments/{id}/leon/setup"},
		{http.MethodGet, "/apartments/5/leon/setup/cards", "GET /apartments/{id}/leon/setup/{step}"},
		{http.MethodGet, "/apartments/5/leon/setup/try", "GET /apartments/{id}/leon/setup/{step}"},
		{http.MethodPost, "/apartments/5/leon/setup/try", "POST /apartments/{id}/leon/setup/try"},
		{http.MethodPost, "/apartments/5/leon/setup/cards", "/apartments/{id}/leon/setup/{step}"},
		{http.MethodPut, "/apartments/5/leon/setup", "/apartments/{id}/leon/setup"},
		{http.MethodGet, "/havel/other", "/"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}

// A request on these routes needs the pool only after the CSRF check and the
// login: a signed-out GET must answer from the session alone.
func TestHavelRegistrationNeedsNoPool(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodPut, "/havel", nil))
	if rec.Code != http.StatusMethodNotAllowed || rec.Header().Get("Allow") != "GET, POST" {
		t.Errorf("PUT /havel: %d %q", rec.Code, rec.Header().Get("Allow"))
	}
}
