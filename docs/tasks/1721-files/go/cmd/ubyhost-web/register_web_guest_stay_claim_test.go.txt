package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGuestStayClaimRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct {
		method, path, pattern string
	}{
		{http.MethodGet, "/l/abc/demo/7", "GET /l/{token}/{rest...}"},
		{http.MethodGet, "/l/abc/7", "GET /l/{token}/{rest...}"},
		{http.MethodGet, "/l/abc/7/claim", "GET /l/{token}/{rest...}"},
		{http.MethodPost, "/l/abc/7/claim/confirm", "POST /l/{token}/{reservation_id}/claim/confirm"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
