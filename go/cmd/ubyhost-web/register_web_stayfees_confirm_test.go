package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestStayFeesConfirmReadyRouteRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	_, pattern := mux.Handler(httptest.NewRequest(http.MethodPost, "/stay-fees/confirm-ready", nil))
	if want := "POST /stay-fees/confirm-ready"; pattern != want {
		t.Errorf("pattern %q, want %q", pattern, want)
	}
}
