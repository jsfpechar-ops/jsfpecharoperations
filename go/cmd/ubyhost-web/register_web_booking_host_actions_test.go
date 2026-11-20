package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestBookingSiteActionsRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct {
		method, path, pattern string
	}{
		{http.MethodPost, "/apartments/3/booking-site/pay", "POST /apartments/{apartment_id}/booking-site/pay"},
		{http.MethodPost, "/apartments/3/booking-site/confirm", "POST /apartments/{apartment_id}/booking-site/confirm"},
		{http.MethodPost, "/apartments/3/booking-site/decline", "POST /apartments/{apartment_id}/booking-site/decline"},
		{http.MethodPost, "/apartments/3/booking-site/cancel", "POST /apartments/{apartment_id}/booking-site/cancel"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}