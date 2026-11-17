package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestSettingsSecurityPhoneRoutesRegistered checks that the two groups of
// brief 1704c reach their own patterns, and that the passkey and push routes
// the pages post to keep theirs.
func TestSettingsSecurityPhoneRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/settings/security", "GET /settings/security"},
		{http.MethodGet, "/settings/phone", "GET /settings/phone"},
		{http.MethodPost, "/account/passkeys/7/delete", "POST /account/passkeys/{id}/delete"},
		{http.MethodPost, "/account/passkeys/7/rename", "POST /account/passkeys/{id}/rename"},
		{http.MethodPost, "/account/push/devices/7/delete", "POST /account/push/devices/{id}/delete"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
