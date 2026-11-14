package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestCleaningAllRoutesRegistered: after brief 1573 Go serves every method of every
// /cleaning path that routes/cleaning.py serves (16 routes), so Caddy can move the
// whole /cleaning prefix without a gap.
func TestCleaningAllRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/cleaning", "GET /cleaning"},
		{http.MethodGet, "/cleaning/schedule", "GET /cleaning/schedule"},
		{http.MethodGet, "/cleaning/new", "GET /cleaning/new"},
		{http.MethodPost, "/cleaning/events", "POST /cleaning/events"},
		{http.MethodGet, "/cleaning/events/7/edit", "GET /cleaning/events/{id}/edit"},
		{http.MethodPost, "/cleaning/events/7", "POST /cleaning/events/{id}"},
		{http.MethodPost, "/cleaning/events/7/delete", "POST /cleaning/events/{id}/delete"},
		{http.MethodGet, "/cleaning/properties", "GET /cleaning/properties"},
		{http.MethodGet, "/cleaning/properties/3", "GET /cleaning/properties/{id}"},
		{http.MethodPost, "/cleaning/properties/3", "POST /cleaning/properties/{id}"},
		{http.MethodPost, "/cleaning/properties/3/code/manual", "POST /cleaning/properties/{id}/code/{action}"},
		{http.MethodPost, "/cleaning/properties/3/code/ttlock", "POST /cleaning/properties/{id}/code/{action}"},
		{http.MethodPost, "/cleaning/properties/3/code/remove", "POST /cleaning/properties/{id}/code/{action}"},
		{http.MethodGet, "/cleaning/shares", "GET /cleaning/shares"},
		{http.MethodPost, "/cleaning/shares", "POST /cleaning/shares"},
		{http.MethodPost, "/cleaning/shares/3/revoke", "POST /cleaning/shares/{id}/revoke"},
		{http.MethodGet, "/cleaning/shared/share1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "GET /cleaning/shared/{token}"},
		{http.MethodGet, "/cleaning/shared/share1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/schedule", "GET /cleaning/shared/{token}/schedule"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
