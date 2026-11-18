package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestRuianSuggestRouteRegistered checks that GET /apartments/ruian-suggest
// reaches its own pattern (brief 1700d) and that the neighbouring list route
// keeps its pattern.
func TestRuianSuggestRouteRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/apartments/ruian-suggest", "GET /apartments/ruian-suggest"},
		{http.MethodGet, "/apartments", "GET /apartments"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
