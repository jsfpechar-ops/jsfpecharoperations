package guest

// protect_guest_post mirrors security.protect_guest_post + csrf_expired_page.

import (
	"net/http"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

// ProtectGuestPOST enforces CSRF before guest POST handlers run (Python router dependency).
func ProtectGuestPOST(w http.ResponseWriter, r *http.Request, getenv func(string) string, at time.Time) bool {
	if r.Method != http.MethodPost {
		return true
	}
	ok, crossSite := hostweb.PostCSRF(w, r, getenv, at)
	if ok {
		return true
	}
	if crossSite {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusForbidden)
		_, _ = w.Write([]byte(`{"detail":"Cross-site request rejected."}`))
		return false
	}
	lang := Language(r)
	token := r.PathValue("token")
	WriteUnavailable(w, r, lang, "form_expired", http.StatusForbidden, token, nil)
	return false
}

// WithPOSTCSRF wraps a guest POST handler to match Python's router CSRF dependency.
func WithPOSTCSRF(getenv func(string) string, now func() time.Time, h http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !ProtectGuestPOST(w, r, getenv, now()) {
			return
		}
		h(w, r)
	}
}