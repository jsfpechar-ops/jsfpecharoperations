package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGuestShellRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	// Foundation brief 1720a registers no /l handlers yet; ensure the mux still builds.
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	if _, pattern := mux.Handler(req); pattern == "" {
		t.Fatal("mux has no handler")
	}
}
