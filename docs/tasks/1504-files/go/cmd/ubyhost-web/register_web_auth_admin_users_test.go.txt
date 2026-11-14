package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestAuthAdminUsersRoutesRegistered checks the three admin account writes of
// brief 1504 next to the GET of brief 1282.
func TestAuthAdminUsersRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/admin/users", "GET /admin/users"},
		{http.MethodPost, "/admin/users", "POST /admin/users"},
		{http.MethodPost, "/admin/users/7/invite", "POST /admin/users/{id}/invite"},
		{http.MethodPost, "/admin/users/7/email", "POST /admin/users/{id}/email"},
		{http.MethodPost, "/admin/users/7/impersonate", "POST /admin/users/{id}/impersonate"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
