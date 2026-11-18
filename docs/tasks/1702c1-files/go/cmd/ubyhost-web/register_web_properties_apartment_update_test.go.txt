package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestApartmentUpdateRouteRegistered checks that POST /apartments/{id}
// reaches its own pattern and that the property page, its other POSTs and the
// wizard keep theirs (brief 1702c1).
func TestApartmentUpdateRouteRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodPost, "/apartments/130201", "POST /apartments/{id}"},
		{http.MethodGet, "/apartments/130201", "GET /apartments/{id}"},
		{http.MethodPost, "/apartments/130201/door-codes", "POST /apartments/{id}/door-codes"},
		{http.MethodPost, "/apartments/130201/setup", "POST /apartments/{id}/setup"},
		{http.MethodPost, "/apartments", "POST /apartments"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
