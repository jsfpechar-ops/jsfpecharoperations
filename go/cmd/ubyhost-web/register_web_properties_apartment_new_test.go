package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestApartmentNewRouteRegistered checks that GET /apartments/new reaches its
// own pattern and that the neighbouring list route keeps its pattern (brief 1700a).
func TestApartmentNewRouteRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/apartments/new", "GET /apartments/new"},
		{http.MethodGet, "/apartments", "GET /apartments"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
