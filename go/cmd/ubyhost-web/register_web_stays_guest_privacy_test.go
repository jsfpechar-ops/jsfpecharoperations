package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGuestPrivacyRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct{ method, path, pattern string }{
		{http.MethodPost, "/guests/7/restrict", "POST /guests/{guest_id}/restrict"},
		{http.MethodPost, "/guests/7/unrestrict", "POST /guests/{guest_id}/unrestrict"},
		{http.MethodPost, "/guests/7/verify-identity", "POST /guests/{guest_id}/verify-identity"},
		{http.MethodGet, "/guests/7/passport-photo", "GET /guests/{guest_id}/passport-photo"},
		{http.MethodPost, "/guests/7/reveal-identity", "POST /guests/{guest_id}/reveal-identity"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
