package main

import (
	"net/http"
	"testing"
)

func TestHostwebDashboardRouteRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct {
		method  string
		path    string
		pattern string
	}{
		{http.MethodGet, "/", "GET /{$}"},
	}
	for _, c := range cases {
		req, _ := http.NewRequest(c.method, c.path, nil)
		_, pattern := mux.Handler(req)
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
