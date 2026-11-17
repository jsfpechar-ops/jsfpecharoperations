package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestApartmentDetailRouteRegistered checks that GET /apartments/{id} reaches
// its own pattern and that the neighbouring routes keep theirs (brief 1701).
func TestApartmentDetailRouteRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/apartments/130201", "GET /apartments/{id}"},
		{http.MethodGet, "/apartments/new", "GET /apartments/new"},
		{http.MethodGet, "/apartments", "GET /apartments"},
		{http.MethodGet, "/apartments/130201/leon/setup", "GET /apartments/{id}/leon/setup"},
		{http.MethodPost, "/apartments/130201/archive", "POST /apartments/{id}/archive"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
