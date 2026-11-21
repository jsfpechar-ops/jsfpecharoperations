// Package staticfiles serves App/app/static under /static/ when Caddy does not
// (Go-only stack, brief 1782). Mirrors Python StaticFiles + cache rules.
package staticfiles

import (
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

const (
	cacheVersioned = "public, max-age=31536000, immutable"
	cacheDefault   = "public, max-age=86400"
)

// Root returns the directory that holds fingerprinted CSS, JS and images.
func Root(getenv func(string) string) string {
	if getenv == nil {
		getenv = os.Getenv
	}
	if root := strings.TrimSpace(getenv("UBYHOST_APP_ROOT")); root != "" {
		p := filepath.Join(root, "static")
		if ok, _ := dirOK(p); ok {
			return p
		}
	}
	for _, p := range []string{
		"/app/static",
		"App/app/static",
		"../../../App/app/static",
		"../../../../App/app/static",
	} {
		if ok, _ := dirOK(p); ok {
			return p
		}
	}
	return ""
}

func dirOK(p string) (bool, error) {
	st, err := os.Stat(p)
	if err != nil {
		return false, err
	}
	return st.IsDir(), nil
}

// Register mounts GET/HEAD /static/ when a static tree is present.
func Register(mux *http.ServeMux, getenv func(string) string, wrap func(string, http.HandlerFunc) http.Handler) {
	root := Root(getenv)
	if root == "" {
		return
	}
	inner := http.FileServer(http.Dir(root))
	serve := func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasPrefix(r.URL.Path, "/static/") {
			http.NotFound(w, r)
			return
		}
		h := w.Header()
		h.Set("X-Content-Type-Options", "nosniff")
		if strings.TrimSpace(r.URL.Query().Get("v")) != "" {
			h.Set("Cache-Control", cacheVersioned)
		} else {
			h.Set("Cache-Control", cacheDefault)
		}
		http.StripPrefix("/static/", inner).ServeHTTP(w, r)
	}
	if wrap != nil {
		mux.Handle("GET /static/", wrap("/static/", serve))
		mux.Handle("HEAD /static/", wrap("/static/", serve))
		return
	}
	mux.Handle("GET /static/", http.HandlerFunc(serve))
	mux.Handle("HEAD /static/", http.HandlerFunc(serve))
}