package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// The stay page and its settings save are Go routes; every other
// /reservations/{id}/... path (filing above all) falls to the catch-all and
// stays on Python, which only the 1864 selector keeps away from Go.
func TestStayDetailRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct {
		method, path, pattern string
	}{
		{http.MethodGet, "/reservations/7", "GET /reservations/{reservation_id}"},
		{http.MethodPost, "/reservations/7", "POST /reservations/{reservation_id}"},
		{http.MethodPost, "/reservations/7/submit", "/"},
		{http.MethodPost, "/reservations/7/filed-by-hand", "/"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
