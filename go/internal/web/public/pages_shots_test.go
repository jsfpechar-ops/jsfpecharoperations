package public

import (
	"net/http"
	"os"
	"testing"
)

// TestServePagesForScreenshots serves /jak-to-funguje, /cenik, /pruvodce/{slug}
// and App/app/static on PUBLIC_PAGES_SHOTS_ADDR until the process is stopped,
// for the rule 7/10 screenshots (brief 1622). Skipped when the variable is unset.
func TestServePagesForScreenshots(t *testing.T) {
	addr := os.Getenv("PUBLIC_PAGES_SHOTS_ADDR")
	if addr == "" {
		t.Skip("PUBLIC_PAGES_SHOTS_ADDR not set")
	}
	env := map[string]string{"UBYHOST_PUBLIC_BASE_URL": "http://" + addr, "UBYHOST_SECRET_KEY": "public-legal-golden-secret-not-real-0123"}
	mux := pagesMux(Deps{Getenv: func(k string) string { return env[k] }})
	mux.Handle("GET /static/", http.StripPrefix("/static/", http.FileServer(http.Dir("../../../../App/app/static"))))
	t.Fatal(http.ListenAndServe(addr, mux))
}
