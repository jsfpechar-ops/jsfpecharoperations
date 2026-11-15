package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestAuthPasskeyRoutesRegistered checks the six passkey routes of brief 1760.
func TestAuthPasskeyRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ path, pattern string }{
		{"/account/passkeys/options", "POST /account/passkeys/options"},
		{"/account/passkeys", "POST /account/passkeys"},
		{"/account/passkeys/7/rename", "POST /account/passkeys/{id}/rename"},
		{"/account/passkeys/7/delete", "POST /account/passkeys/{id}/delete"},
		{"/login/passkey/options", "POST /login/passkey/options"},
		{"/login/passkey", "POST /login/passkey"},
		{"/account/security-prompt/seen", "POST /account/security-prompt/seen"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(http.MethodPost, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("POST %s: pattern %q, want %q", c.path, pattern, c.pattern)
		}
	}
}
