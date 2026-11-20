package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGuestEditRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct {
		method, path, pattern string
	}{
		{http.MethodGet, "/reservations/7/guests/new", "GET /reservations/{reservation_id}/guests/new"},
		{http.MethodPost, "/reservations/7/guests", "POST /reservations/{reservation_id}/guests"},
		{http.MethodGet, "/guests/42", "GET /guests/{guest_id}"},
		{http.MethodPost, "/guests/42", "POST /guests/{guest_id}"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
