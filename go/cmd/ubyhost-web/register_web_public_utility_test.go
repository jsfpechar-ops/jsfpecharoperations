package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestUtilityRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct {
		method, path, pattern string
	}{
		{http.MethodGet, "/robots.txt", "GET /robots.txt"},
		{http.MethodGet, "/.well-known/tdmrep.json", "GET /.well-known/tdmrep.json"},
		{http.MethodGet, "/manifest.webmanifest", "GET /manifest.webmanifest"},
		{http.MethodGet, "/sw.js", "GET /sw.js"},
		{http.MethodGet, "/offline", "GET /offline"},
		{http.MethodGet, "/sitemap.xml", "GET /sitemap.xml"},
		{http.MethodPost, "/language", "POST /language"},
		{http.MethodGet, "/favicon.ico", "GET /favicon.ico"},
		{http.MethodGet, "/sample-airbnb.ics", "GET /sample-airbnb.ics"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
