package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestSubmissionsRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct {
		method, path, pattern string
	}{
		{http.MethodGet, "/submissions", "GET /submissions"},
		{http.MethodGet, "/submissions/42", "GET /submissions/{submission_id}"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
