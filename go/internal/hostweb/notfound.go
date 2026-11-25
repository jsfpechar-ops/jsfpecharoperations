package hostweb

import (
	"fmt"
	"io"
	"net/http"
	"strings"
)

// WantsHTML matches App/app/main.py _wants_html for host middleware 404s.
func WantsHTML(r *http.Request) bool {
	if strings.HasPrefix(r.URL.Path, "/api/") {
		return false
	}
	return strings.Contains(r.Header.Get("Accept"), "text/html")
}

// GuestPath reports /l and /l/...: Python renders their 404s with the guest
// lane's own page (App/app/main.py 255-258), which the Go guest lane does not
// have yet, so those paths keep net/http's plain 404 instead of borrowing the
// host page's styling.
func GuestPath(r *http.Request) bool {
	p := r.URL.Path
	return p == "/l" || strings.HasPrefix(p, "/l/")
}

// NotFoundPage writes the branded 404 of a host page: templating.render(
// "error.html", {"error_kind": "not_found"}) in Python (App/app/main.py
// 261-289), which is HTML when the client wants HTML and an empty
// Response(status_code=404) body otherwise. The payments-hidden middleware
// (BlockedPage) and the mux catch-all both land here.
func NotFoundPage(w http.ResponseWriter, r *http.Request) {
	if !WantsHTML(r) {
		w.WriteHeader(http.StatusNotFound)
		return
	}
	NotFoundHTML(w, r, http.StatusNotFound)
}

// NotFoundHTML writes the branded error page of the host lane with the given
// status (404 or 405). The copy is the same for both: the page says the link is
// wrong, and the Allow header is set by the caller.
func NotFoundHTML(w http.ResponseWriter, r *http.Request, status int) {
	lang := Lang(r)
	title, body, home := notFoundCopy(lang)
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(status)
	_, _ = io.WriteString(w, fmt.Sprintf(`<!doctype html><html lang="%s"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>%s · UbyHost</title><link rel="stylesheet" href="/static/tokens.css"><link rel="stylesheet" href="/static/app.css"></head><body class="layout-host"><main class="ui-body ui-body-detail" style="max-width:560px;margin:2rem auto;padding:0 1rem"><h1 class="big">%s</h1><p>%s</p><p><a class="ui-btn ui-btn-primary" href="/">%s</a></p></main></body></html>`,
		lang, title, title, body, home))
}

// BlockedPage is the payments-hidden middleware's 404; NotFoundPage serves
// every other host-page 404. One implementation, two names.
func BlockedPage(w http.ResponseWriter, r *http.Request) { NotFoundPage(w, r) }

func notFoundCopy(lang string) (title, body, home string) {
	switch lang {
	case "cs":
		return "Stránka nenalezena",
			"Odkaz je chybný, nebo stránka už neexistuje.",
			"Na úvod"
	case "vi":
		return "Không tìm thấy trang",
			"Liên kết không đúng hoặc trang không còn tồn tại.",
			"Về trang chủ"
	default:
		return "Page not found",
			"The link is wrong or the page no longer exists.",
			"Home"
	}
}
