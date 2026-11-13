package public

import (
	"net/http"
	"os"
	"testing"
)

// TestServeForScreenshots serves the five pages and App/app/static on
// PUBLIC_LEGAL_SHOTS_ADDR until the process is stopped, for the rule 7/10
// screenshots (brief 1270 phase 5). Skipped when the variable is unset.
func TestServeForScreenshots(t *testing.T) {
	addr := os.Getenv("PUBLIC_LEGAL_SHOTS_ADDR")
	if addr == "" {
		t.Skip("PUBLIC_LEGAL_SHOTS_ADDR not set")
	}
	env := map[string]string{
		"UBYHOST_PUBLIC_BASE_URL": "http://" + addr, "UBYHOST_OPERATOR_NAME": "Demo Operator s.r.o.",
		"UBYHOST_OPERATOR_ICO": "12345678", "UBYHOST_OPERATOR_ADDRESS": "Václavské náměstí 1, 110 00 Praha 1",
		"UBYHOST_OPERATOR_REGISTRY_URL": "https://or.justice.cz/ias/ui/rejstrik",
	}
	deps := Deps{Getenv: func(k string) string { return env[k] }}
	mux := http.NewServeMux()
	for _, path := range Paths {
		mux.Handle("GET "+path, Handler(path, deps))
	}
	mux.Handle("GET /static/", http.StripPrefix("/static/", http.FileServer(http.Dir("../../../../App/app/static"))))
	t.Fatal(http.ListenAndServe(addr, mux))
}
