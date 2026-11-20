package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestSmartLocksPostRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodPost, "/smart-locks/setup", "POST /smart-locks/setup"},
		{http.MethodPost, "/smart-locks/refresh", "POST /smart-locks/refresh"},
		{http.MethodPost, "/smart-locks/remove", "POST /smart-locks/remove"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
