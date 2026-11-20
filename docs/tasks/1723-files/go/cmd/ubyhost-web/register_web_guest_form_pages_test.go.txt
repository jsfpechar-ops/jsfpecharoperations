package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGuestFormPagesRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct{ method, path, pattern string }{
		{http.MethodGet, "/l/tok/1/new", "GET /l/{token}/{reservation_id}/new"},
		{http.MethodGet, "/l/tok/1/edit/2", "GET /l/{token}/{reservation_id}/edit/{guest_id}"},
		{http.MethodGet, "/l/tok/1/remove/2", "GET /l/{token}/{reservation_id}/remove/{guest_id}"},
		{http.MethodPost, "/l/tok/1/remove/2", "POST /l/{token}/{reservation_id}/remove/{guest_id}"},
		{http.MethodPost, "/l/tok/1/relang", "POST /l/{token}/{reservation_id}/relang"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
