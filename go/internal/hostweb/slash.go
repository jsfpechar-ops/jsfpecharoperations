package hostweb

import (
	"net/http"
	"strings"
)

// Router is the part of *http.ServeMux CanonicalSlash needs.
type Router interface {
	Handler(r *http.Request) (http.Handler, string)
}

// CanonicalSlash answers <path>/ with a 307 to <path> when a registered
// route serves <path>, as Starlette's redirect_slashes does for the Python
// app (305-style 307, method and body preserved, main.go:193). Routes registered as a
// subtree ("/static/") and unknown paths are left to the mux.
func CanonicalSlash(router Router, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p := r.URL.Path
		if len(p) > 1 && strings.HasSuffix(p, "/") {
			if trimmed := strings.TrimRight(p, "/"); trimmed != "" {
				probe := r.Clone(r.Context())
				u := *r.URL
				u.Path, u.RawPath = trimmed, ""
				probe.URL = &u
				if _, pattern := router.Handler(probe); pattern != "" && pattern != "/" && !strings.HasSuffix(pattern, "/") {
					target := trimmed
					if u.RawQuery != "" {
						target += "?" + u.RawQuery
					}
					http.Redirect(w, r, target, http.StatusTemporaryRedirect)
					return
				}
			}
		}
		next.ServeHTTP(w, r)
	})
}
