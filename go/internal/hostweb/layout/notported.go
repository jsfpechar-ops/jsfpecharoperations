package layout

import (
	"embed"
	"log"
	"net/http"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed notported.tmpl
var notPortedFiles embed.FS

var notPortedTpl = MustParse(Strings, notPortedFiles, "notported.tmpl")

// NotPortedView is the body of the not-ported page (host language).
type NotPortedView struct {
	Title    string
	Body     string
	Settings string
}

// NotPortedPage writes a host HTML page inside the light-mode layout (501) when
// the client wants HTML; otherwise an empty 501. The what argument is logged
// for operators and is not shown to hosts.
func NotPortedPage(w http.ResponseWriter, r *http.Request, env Env, host *session.Host, nav, what string) {
	w.Header().Set("X-Ubyhost-Not-Ported", "1")
	w.Header().Set("Cache-Control", "no-store, private")
	if what != "" {
		log.Printf("layout: not ported: %s", what)
	}
	if !hostweb.WantsHTML(r) {
		w.WriteHeader(http.StatusNotImplemented)
		return
	}
	v := notPortedCopy(hostweb.Lang(r))
	title := v.Title
	navKey := nav
	if navKey == "" {
		navKey = "settings"
	}
	p := Page{
		Title: title, Nav: navKey, BodyKind: "detail", V2: true,
		Status: http.StatusNotImplemented, BackURL: "/settings",
	}
	if err := Render(w, r, env, host, p, notPortedTpl, "not_ported", v); err != nil {
		log.Printf("layout: render not ported: %v", err)
		http.Error(w, http.StatusText(http.StatusNotImplemented), http.StatusNotImplemented)
	}
}

func notPortedCopy(lang string) NotPortedView {
	switch lang {
	case "cs":
		return NotPortedView{
			Title:    "Akce zatím není k dispozici",
			Body:     "Tato akce v této verzi UbyHostu zatím nejde dokončit. Obnovte stránku nebo se obraťte na podporu na support@ubyhost.com.",
			Settings: "Nastavení a podpora",
		}
	case "vi":
		return NotPortedView{
			Title:    "Thao tác chưa khả dụng",
			Body:     "Thao tác này chưa thể hoàn tất trên phiên bản UbyHost này. Hãy tải lại trang hoặc liên hệ hỗ trợ tại support@ubyhost.com.",
			Settings: "Cài đặt và hỗ trợ",
		}
	default:
		return NotPortedView{
			Title:    "This action is not available yet",
			Body:     "This action cannot be completed on this version of UbyHost. Reload the page, or contact support at support@ubyhost.com.",
			Settings: "Settings and support",
		}
	}
}
