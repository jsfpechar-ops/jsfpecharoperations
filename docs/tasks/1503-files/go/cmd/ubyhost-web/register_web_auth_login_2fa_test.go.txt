package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestAuthLogin2FARoutesRegistered checks POST /login/2fa of brief 1503 next
// to the GET of brief 1282.
func TestAuthLogin2FARoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/login/2fa", "GET /login/2fa"},
		{http.MethodPost, "/login/2fa", "POST /login/2fa"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
