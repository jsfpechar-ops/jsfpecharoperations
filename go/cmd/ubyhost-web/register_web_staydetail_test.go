package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// Stay detail GET/POST and manual submit (brief 1741) register on Go; other
// /reservations/{id}/... filing posts still fall through until ported.
func TestStayDetailRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct {
		method, path, pattern string
	}{
		{http.MethodGet, "/reservations/7", "GET /reservations/{reservation_id}"},
		{http.MethodPost, "/reservations/7", "POST /reservations/{reservation_id}"},
		{http.MethodPost, "/reservations/7/submit", "POST /reservations/{reservation_id}/submit"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
