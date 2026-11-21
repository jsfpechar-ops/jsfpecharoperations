package hostweb

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestDashboardHandlerNotImplemented(t *testing.T) {
	h := DashboardHandler(nil, func(string) string { return "" }, nil, time.Now)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusNotImplemented {
		t.Fatalf("status %d, want 501", rec.Code)
	}
}
