package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestApartmentSmallPostsRouteRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	routes := []struct{ method, path, pattern string }{
		{http.MethodPost, "/apartments/130201/automation-timing", "POST /apartments/{id}/automation-timing"},
		{http.MethodPost, "/apartments/130201/feeds", "POST /apartments/{id}/feeds"},
		{http.MethodPost, "/apartments/130201/test-connection", "POST /apartments/{id}/test-connection"},
		{http.MethodPost, "/apartments/130201/police-letter", "POST /apartments/{id}/police-letter"},
		{http.MethodPost, "/apartments/130201/refresh-codelists", "POST /apartments/{id}/refresh-codelists"},
		{http.MethodPost, "/apartments/130201/door-codes", "POST /apartments/{id}/door-codes"},
	}
	for _, c := range routes {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
