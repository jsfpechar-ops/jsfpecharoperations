package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGuestPartyRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct {
		method, path, pattern string
	}{
		{http.MethodPost, "/l/tok/7/party", "POST /l/{token}/{reservation_id}/party"},
		{http.MethodPost, "/l/tok/7/count", "POST /l/{token}/{reservation_id}/count"},
		{http.MethodPost, "/l/tok/7/another", "POST /l/{token}/{reservation_id}/another"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
