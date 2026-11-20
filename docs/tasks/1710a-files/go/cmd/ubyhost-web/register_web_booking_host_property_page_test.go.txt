package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestBookingHostPropertyPageRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	id := "42"
	cases := []struct {
		method, path, pattern string
	}{
		{http.MethodGet, "/apartments/" + id + "/page", "GET /apartments/{apartment_id}/page"},
		{http.MethodPost, "/apartments/" + id + "/page", "POST /apartments/{apartment_id}/page"},
		{http.MethodPost, "/apartments/" + id + "/page/photo-move", "POST /apartments/{apartment_id}/page/photo-move"},
		{http.MethodPost, "/apartments/" + id + "/page/photo-delete", "POST /apartments/{apartment_id}/page/photo-delete"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
