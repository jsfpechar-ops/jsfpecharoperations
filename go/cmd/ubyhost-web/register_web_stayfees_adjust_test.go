package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestStayFeesAdjustRouteRegistered checks the adjustment route of brief 1584.
func TestStayFeesAdjustRouteRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	_, pattern := mux.Handler(httptest.NewRequest(http.MethodPost, "/stay-fees/12/adjustment", nil))
	if want := "POST /stay-fees/{apartment_id}/adjustment"; pattern != want {
		t.Errorf("pattern %q, want %q", pattern, want)
	}
}
