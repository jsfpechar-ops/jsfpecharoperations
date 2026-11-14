package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestStayFeesFinalizeRouteRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	_, pattern := mux.Handler(httptest.NewRequest(http.MethodPost, "/stay-fees/5/finalize", nil))
	if want := "POST /stay-fees/{apartment_id}/finalize"; pattern != want {
		t.Errorf("pattern %q, want %q", pattern, want)
	}
}
