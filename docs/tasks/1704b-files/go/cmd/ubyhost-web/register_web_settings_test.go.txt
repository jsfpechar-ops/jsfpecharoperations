package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestSettingsPageRoutesRegistered checks that the index and four groups of
// brief 1704b reach their own patterns and the existing /settings routes keep
// theirs. /settings/security and /settings/phone are brief 1704c.
func TestSettingsPageRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/settings", "GET /settings"},
		{http.MethodGet, "/settings/account", "GET /settings/account"},
		{http.MethodGet, "/settings/data", "GET /settings/data"},
		{http.MethodGet, "/settings/technical", "GET /settings/technical"},
		{http.MethodGet, "/settings/help", "GET /settings/help"},
		{http.MethodGet, "/settings/archived", "GET /settings/archived"},
		{http.MethodPost, "/settings/purge-expired", "POST /settings/purge-expired"},
		{http.MethodPost, "/settings/privacy/ad-consent", "POST /settings/privacy/ad-consent"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
