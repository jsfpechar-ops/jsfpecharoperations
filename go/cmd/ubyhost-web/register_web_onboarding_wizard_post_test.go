package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestWizardPostRouteRegistered checks that POST /apartments/{id}/setup of
// brief 1602 reaches its own pattern.
func TestWizardPostRouteRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	_, pattern := mux.Handler(httptest.NewRequest(http.MethodPost, "/apartments/7/setup", nil))
	if pattern != "POST /apartments/{id}/setup" {
		t.Errorf("pattern %q", pattern)
	}
}
