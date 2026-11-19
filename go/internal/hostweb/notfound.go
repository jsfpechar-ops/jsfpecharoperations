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

// BlockedPage writes a 404 for payments-hidden middleware: branded HTML when
// WantsHTML, else an empty body like Python's Response(status_code=404).
func BlockedPage(w http.ResponseWriter, r *http.Request) {
	if !WantsHTML(r) {
		w.WriteHeader(http.StatusNotFound)
		return
	}
	lang := Lang(r)
	title, body, home := notFoundCopy(lang)
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusNotFound)
	_, _ = io.WriteString(w, fmt.Sprintf(`<!doctype html><html lang="%s"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>%s · UbyHost</title><link rel="stylesheet" href="/static/tokens.css"><link rel="stylesheet" href="/static/app.css"></head><body class="layout-host"><main class="ui-body ui-body-detail" style="max-width:560px;margin:2rem auto;padding:0 1rem"><h1 class="big">%s</h1><p>%s</p><p><a class="ui-btn ui-btn-primary" href="/">%s</a></p></main></body></html>`,
		lang, title, title, body, home))
}

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