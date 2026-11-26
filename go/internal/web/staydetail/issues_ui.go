package staydetail

import (
	"embed"
	"fmt"
	"html/template"
	"strings"

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

var issueFieldLabels = map[string][3]string{
	// field: {en, cs, vi}
	"birth_date":  {"Birth date", "Datum narození", "Ngày sinh"},
	"res_street":  {"Street", "Ulice", "Đường"},
	"res_city":    {"City", "Město", "Thành phố"},
	"res_country": {"Country", "Stát", "Quốc gia"},
	"surname":     {"Surname", "Příjmení", "Họ"},
	"first_name":  {"Given name", "Jméno", "Tên"},
	"nationality": {"Nationality", "Občanství", "Quốc tịch"},
	"doc_number":  {"Document no.", "Číslo dokladu", "Số giấy tờ"},
	"visa_number": {"Visa", "Vízum", "Thị thực"},
	"purpose":     {"Purpose", "Účel pobytu", "Mục đích"},
	"signature":   {"Signature", "Podpis", "Chữ ký"},
	"stay_from":   {"Stay dates", "Termín", "Ngày lưu trú"},
	"stay_to":     {"Stay dates", "Termín", "Ngày lưu trú"},
	"note":        {"Note", "Poznámka", "Ghi chú"},
}

func fieldShortLabel(lang, field string) string {
	idx := 0
	switch lang {
	case "cs":
		idx = 1
	case "vi":
		idx = 2
	}
	if labels, ok := issueFieldLabels[field]; ok {
		return labels[idx]
	}
	return ""
}

// missingDetailsSummary builds a concise, scannable field-name summary for the
// guest-issues disclosure pill, e.g. "Missing: Birth date, Street, City +3 more".
func missingDetailsSummary(lang string, issues []validation.Issue) string {
	seen := map[string]bool{}
	var names []string
	for _, iss := range issues {
		lbl := fieldShortLabel(lang, iss.Field)
		if lbl == "" || seen[lbl] {
			continue
		}
		seen[lbl] = true
		names = append(names, lbl)
	}
	if len(names) == 0 {
		return missingDetailsLabel(lang, len(issues))
	}
	prefix := "Missing: "
	switch lang {
	case "cs":
		prefix = "Chybí: "
	case "vi":
		prefix = "Thiếu: "
	}
	const maxInline = 3
	if len(names) <= maxInline {
		return prefix + strings.Join(names, ", ")
	}
	extra := len(names) - maxInline
	more := fmt.Sprintf(" +%d more", extra)
	switch lang {
	case "cs":
		more = fmt.Sprintf(" +%d další", extra)
	case "vi":
		more = fmt.Sprintf(" +%d mục nữa", extra)
	}
	return prefix + strings.Join(names[:maxInline], ", ") + more
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
	funcs := make(template.FuncMap, len(tplFuncs)+3)
	for k, v := range tplFuncs {
		funcs[k] = v
	}
	funcs["guest_issues_tone"] = guestIssuesTone
	funcs["missing_details_label"] = missingDetailsLabel
	funcs["missing_details_summary"] = missingDetailsSummary
	return layout.MustParseFuncs(catalog, funcs, comfyTemplateFS, "templates/*.tmpl", "templates/comfy/*.tmpl")
}()
