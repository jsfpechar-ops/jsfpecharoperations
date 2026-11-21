package guest

// Route wiring for briefs 1721–1725 and 1629 on main before full handler ports land.
// Handlers answer 501 with X-Ubyhost-Not-Ported so Caddy can fall back to Python.

import (
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

func waveNotPorted(w http.ResponseWriter, what string) {
	w.Header().Set("X-Ubyhost-Not-Ported", "1")
	http.Error(w, "not served by Go yet: "+what, http.StatusNotImplemented)
}

func waveStub(_ string) http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) {
		waveNotPorted(w, "guest")
	}
}

// RegisterParty wires party size POST routes (brief 1722).
func RegisterParty(mux *http.ServeMux, _ *pgxpool.Pool, _ func(string) string, _ func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	for _, label := range []string{
		"POST /l/{token}/{reservation_id}/party",
		"POST /l/{token}/{reservation_id}/count",
		"POST /l/{token}/{reservation_id}/another",
	} {
		mux.Handle(label, wrap(label, waveStub("party")))
	}
}

// RegisterFormSave wires the registration save POST (brief 1724).
func RegisterFormSave(mux *http.ServeMux, _ *pgxpool.Pool, _ func(string) string, _ func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	const label = "POST /l/{token}/{reservation_id}/save"
	mux.Handle(label, wrap(label, waveStub("form_save")))
}

// RegisterGuideView wires QR and stay guide GET routes (brief 1629).
func RegisterGuideView(mux *http.ServeMux, _ *pgxpool.Pool, _ func(string) string, _ func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	for _, label := range []string{
		"GET /g/{token}",
		"GET /g/{token}/photos/{item_id}/{photo_id}",
		"GET /l/{token}/{reservation_id}/guide",
		"GET /l/{token}/{reservation_id}/guide/photos/{item_id}/{photo_id}",
	} {
		mux.Handle(label, wrap(label, waveStub("guide_view")))
	}
}
