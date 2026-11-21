package public

import (
	"bytes"
	"net/http"
	"strings"
	"text/template"
)

var landingTmpl = template.Must(template.New("landing.tmpl").ParseFS(pagesFS,
	append(append([]string{}, pageShared...), "templates/pages/landing.tmpl")...))

type landingData struct {
	*pg
	SignupHref string
	Weekdays   []string
}

// ServeLanding renders the public landing page (landing.html) at GET /.
func ServeLanding(w http.ResponseWriter, r *http.Request, d Deps) {
	cfg := loadConfig(d.Getenv)
	lang := resolveLang(r, d.SignedIn)
	p := newPG("/", lang, cfg)
	p.Active, p.SwitchPath = "home", "/"
	p.canonical = cfg.PublicBase + "/"
	if lang != "" {
		p.canonical += "?lang=" + lang
	}
	for _, code := range []string{"en", "cs"} {
		p.Alternates = append(p.Alternates, link{code, p.URL("/", code)})
	}
	p.Alternates = append(p.Alternates, link{"x-default", p.URL("/", "")})
	data := landingData{pg: p}
	if cfg.SignupEnabled {
		data.SignupHref = "/signup?lang=" + lang
	}
	data.Weekdays = strings.Split(pcat.Strings.T(lang, "landing.demo.weekdays", nil), ",")
	var buf bytes.Buffer
	if err := landingTmpl.ExecuteTemplate(&buf, "landing.tmpl", data); err != nil {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	pageFinish(w, r, cfg, buf.Bytes())
}
