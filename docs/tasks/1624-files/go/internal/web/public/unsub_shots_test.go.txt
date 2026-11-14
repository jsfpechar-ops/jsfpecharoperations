package public

import (
	"net/http"
	"os"
	"testing"
)

// TestServeUnsubscribeForScreenshots serves the unsubscribe page on a
// throwaway database, with App/app/static, on PUBLIC_UNSUB_SHOTS_ADDR until
// the process is stopped, for the rule 7/10 screenshots (brief 1624). Skipped
// when the variable or UBYHOST_TEST_DATABASE_URL is unset.
func TestServeUnsubscribeForScreenshots(t *testing.T) {
	addr := os.Getenv("PUBLIC_UNSUB_SHOTS_ADDR")
	if addr == "" {
		t.Skip("PUBLIC_UNSUB_SHOTS_ADDR not set")
	}
	pool := unsubTestPool(t)
	reseed(t, pool, 0)
	f := loadUnsub(t)
	env := map[string]string{"UBYHOST_PUBLIC_BASE_URL": "http://" + addr, "UBYHOST_SECRET_KEY": f.Secret}
	mux := unsubMux(UnsubDeps{Pool: pool, Getenv: func(k string) string { return env[k] }})
	mux.Handle("GET /static/", http.StripPrefix("/static/", http.FileServer(http.Dir("../../../../App/app/static"))))
	t.Fatal(http.ListenAndServe(addr, mux))
}
