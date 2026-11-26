package staydetail

import (
	"embed"
	"fmt"
	"html/template"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

//go:embed templates/*.tmpl templates/comfy/*.tmpl
var comfyTemplateFS embed.FS

func guestIssuesTone(issues []validation.Issue) string {
	for _, iss := range issues {
		if iss.Severity == "error" {
			return "bad"
		}
	}
	return "warn"
}

func missingDetailsLabel(lang string, n int) string {
	switch lang {
	case "cs":
		switch {
		case n == 1:
			return "Chybí 1 údaj"
		case n >= 2 && n <= 4:
			return fmt.Sprintf("Chybí %d údaje", n)
		default:
			return fmt.Sprintf("Chybí %d údajů", n)
		}
	case "vi":
		return fmt.Sprintf("Thiếu %d thông tin", n)
	default:
		if n == 1 {
			return "1 detail missing"
		}
		return fmt.Sprintf("%d details missing", n)
	}
}

var comfyPages = func() *layout.Templates {
	funcs := make(template.FuncMap, len(tplFuncs)+2)
	for k, v := range tplFuncs {
		funcs[k] = v
	}
	funcs["guest_issues_tone"] = guestIssuesTone
	funcs["missing_details_label"] = missingDetailsLabel
	return layout.MustParseFuncs(catalog, funcs, comfyTemplateFS, "templates/*.tmpl", "templates/comfy/*.tmpl")
}()
