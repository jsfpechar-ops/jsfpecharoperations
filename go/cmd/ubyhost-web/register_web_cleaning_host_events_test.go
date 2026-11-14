package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestCleaningHostEventRoutesRegistered checks the two event writes of brief 1571.
func TestCleaningHostEventRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodPost, "/cleaning/events", "POST /cleaning/events"},
		{http.MethodPost, "/cleaning/events/7", "POST /cleaning/events/{id}"},
		{http.MethodPost, "/cleaning/events/7/delete", "POST /cleaning/events/{id}/delete"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
