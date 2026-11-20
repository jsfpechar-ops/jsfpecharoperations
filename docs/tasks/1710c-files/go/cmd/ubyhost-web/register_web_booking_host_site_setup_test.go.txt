package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestBookingHostSiteSetupRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	id := "42"
	cases := []struct {
		method, path, pattern string
	}{
		{http.MethodGet, "/apartments/" + id + "/booking-site", "GET /apartments/{apartment_id}/booking-site"},
		{http.MethodPost, "/apartments/" + id + "/booking-site", "POST /apartments/{apartment_id}/booking-site"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
