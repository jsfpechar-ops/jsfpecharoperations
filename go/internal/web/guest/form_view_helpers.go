package guest

import (
	"fmt"
	"html/template"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

type formChildEntry struct {
	ID   int64
	Name string
}

func (v formView) Val(name string) string {
	if s, ok := v.Values[name]; ok && s != "" {
		return s
	}
	if v.GuestFields != nil {
		return v.GuestFields[name]
	}
	return ""
}

func (v formView) ResCountrySel() string {
	if s := v.Val("res_country"); s != "" {
		return s
	}
	if n := v.Val("nationality"); n != "" {
		return n
	}
	return ""
}

func (v formView) FieldClass(field string) string {
	for _, iss := range v.Issues {
		if iss.Field == field && iss.Severity == "error" {
			return "bad"
		}
	}
	return ""
}

func (v formView) FieldIsInvalid(field string) bool {
	for _, iss := range v.Issues {
		if iss.Field == field && iss.Severity == "error" {
			return true
		}
	}
	return false
}

func (v formView) ErrHTML(field string) template.HTML {
	var b strings.Builder
	for _, iss := range v.Issues {
		if iss.Field != field {
			continue
		}
		cls := "hint"
		id := ""
		if iss.Severity == "error" {
			cls = "err"
			id = fmt.Sprintf(` id="%s-error"`, field)
		}
		b.WriteString(fmt.Sprintf(`<div class="%s"%s>%s</div>`, cls, id, template.HTMLEscapeString(iss.Message)))
	}
	return template.HTML(b.String())
}

func (v formView) HasErrors() bool {
	for _, iss := range v.Issues {
		if iss.Severity == "error" {
			return true
		}
	}
	return false
}

func (v formView) ErrorIssues() []validation.Issue {
	var out []validation.Issue
	for _, iss := range v.Issues {
		if iss.Severity == "error" {
			out = append(out, iss)
		}
	}
	return out
}

// DisplayBirth formats YYYY-MM-DD or DDMMYYYY as dd.mm.yyyy for the guest birth field.
func (v formView) DisplayBirth(raw string) string {
	raw = strings.TrimSpace(raw)
	if len(raw) == 8 {
		for _, c := range raw {
			if c < '0' || c > '9' {
				return raw
			}
		}
		return raw[:2] + "." + raw[2:4] + "." + raw[4:]
	}
	if len(raw) >= 10 && raw[4] == '-' {
		return raw[8:10] + "." + raw[5:7] + "." + raw[0:4]
	}
	return raw
}
