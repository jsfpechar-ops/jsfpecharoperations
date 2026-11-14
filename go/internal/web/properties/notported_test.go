package properties

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// Brief 1630: every "not served by Go yet" answer is a 501 with the header
// Caddy matches on, so a real 501 from elsewhere is never re-sent to Python.
func TestNotPortedHeader(t *testing.T) {
	for _, what := range []string{
		"the property list",
		"host alerts on this page",
		"the business editor (?edit= with a non-ASCII number)",
		"the ARES lookup (Fill from register)",
	} {
		rec := httptest.NewRecorder()
		notPorted(rec, what)
		if rec.Code != http.StatusNotImplemented {
			t.Errorf("%s: code %d, want 501", what, rec.Code)
		}
		if got := rec.Header().Get("X-Ubyhost-Not-Ported"); got != "1" {
			t.Errorf("%s: header %q, want 1", what, got)
		}
	}
}
