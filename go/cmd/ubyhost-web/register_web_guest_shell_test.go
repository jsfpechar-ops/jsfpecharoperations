package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGuestShellRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	checks := [][2]string{
		{http.MethodPost, "/l/example-token/pin"},
		{http.MethodGet, "/l/example-token/privacy"},
		{http.MethodGet, "/l/example-token/ruian-suggest"},
	}
	want := []string{
		"POST /l/{token}/pin",
		"GET /l/{token}/privacy",
		"GET /l/{token}/ruian-suggest",
	}
	for i, c := range checks {
		req := httptest.NewRequest(c[0], c[1], nil)
		_, pattern := mux.Handler(req)
		if pattern != want[i] {
			t.Fatalf("%s %s route %q want %q", c[0], c[1], pattern, want[i])
		}
	}
	req := httptest.NewRequest(http.MethodGet, "/l/example-token", nil)
	_, pattern := mux.Handler(req)
	if pattern != "GET /l/{token}" {
		t.Fatalf("pick route %q", pattern)
	}
}
