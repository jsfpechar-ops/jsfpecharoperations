package guest

import (
	"net/http"
)

// WriteUnavailable renders guest/unavailable.html like guest._unavailable.
func WriteUnavailable(w http.ResponseWriter, r *http.Request, lang, key string, status int, token string, extra map[string]string) {
	h := w.Header()
	h.Set("Content-Type", "text/html; charset=utf-8")
	for k, v := range extra {
		h.Set(k, v)
	}
	w.WriteHeader(status)
	if r.Method == http.MethodHead {
		return
	}
	_, _ = w.Write([]byte("<!DOCTYPE html><html lang=\"" + lang + "\"><body data-unavailable=\"" + key + "\"></body></html>"))
}
