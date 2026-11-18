package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestApartmentCreateRouteRegistered checks that POST /apartments reaches its
// own pattern and that the list and the new form keep theirs (brief 1700b2).
func TestApartmentCreateRouteRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodPost, "/apartments", "POST /apartments"},
		{http.MethodGet, "/apartments", "GET /apartments"},
		{http.MethodGet, "/apartments/new", "GET /apartments/new"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
