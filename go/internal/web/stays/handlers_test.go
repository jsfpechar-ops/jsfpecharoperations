package stays

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestRegisterRoutesGET(t *testing.T) {
	mux := http.NewServeMux()
	Register(mux, nil, func(string) string { return "" }, func() time.Time { return fixedToday() },
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	req := httptest.NewRequest(http.MethodGet, "/reservations", nil)
	if h, p := mux.Handler(req); h == nil || p == "" {
		t.Fatalf("no handler pattern=%q", p)
	}
}