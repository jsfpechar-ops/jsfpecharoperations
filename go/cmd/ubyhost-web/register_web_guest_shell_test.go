package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGuestShellRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	req := httptest.NewRequest(http.MethodPost, "/l/example-token/pin", nil)
	_, pattern := mux.Handler(req)
	if pattern != "POST /l/{token}/pin" {
		t.Fatalf("pin route %q", pattern)
	}
	req = httptest.NewRequest(http.MethodGet, "/l/example-token", nil)
	_, pattern = mux.Handler(req)
	if pattern != "GET /l/{token}" {
		t.Fatalf("pick route %q", pattern)
	}
}
