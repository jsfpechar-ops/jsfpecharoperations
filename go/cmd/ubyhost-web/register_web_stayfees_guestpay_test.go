package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestStayFeesGuestPayRouteRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	const want = "POST /stay-fees/{apartment_id}/guest-pay-preview"
	_, pattern := mux.Handler(httptest.NewRequest(http.MethodPost, "/stay-fees/5/guest-pay-preview", nil))
	if pattern != want {
		t.Errorf("pattern %q, want %q", pattern, want)
	}
}
