package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestBookingHostBookingSitesRouteRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	path := "/booking-sites"
	pattern := "GET /booking-sites"
	_, got := mux.Handler(httptest.NewRequest(http.MethodGet, path, nil))
	if got != pattern {
		t.Errorf("GET %s: pattern %q, want %q", path, got, pattern)
	}
}
