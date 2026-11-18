package policyletter

import (
	"strconv"
	"strings"
)

const maxFormLine = 100000

// ConfirmedFields returns (listed, unconfirmed) from hidden letter_fields.
// The second list is always empty (1097). Never panics.
func ConfirmedFields(form any) ([]string, []string) {
	raw := formGet(form, "letter_fields")
	var names map[string]struct{}
	if s, ok := raw.(string); ok {
		names = make(map[string]struct{})
		for _, part := range strings.Split(s, ",") {
			part = strings.TrimSpace(part)
			if part != "" {
				names[part] = struct{}{}
			}
		}
	}
	var listed []string
	for _, name := range Fields {
		if names != nil {
			if _, ok := names[name]; ok {
				listed = append(listed, name)
			}
		}
	}
	return listed, nil
}

// LineFromForm reads letter_line_<name> as 1..maxFormLine, else nil. Never panics.
func LineFromForm(form any, name string) *int {
	raw := formGet(form, "letter_line_"+name)
	s, ok := raw.(string)
	if !ok || s == "" || len(s) > 6 {
		return nil
	}
	if !isASCII(s) || !isDigits(s) {
		return nil
	}
	n, err := strconv.Atoi(s)
	if err != nil || n < 1 || n > maxFormLine {
		return nil
	}
	return &n
}

func formGet(form any, key string) any {
	if form == nil {
		return nil
	}
	defer func() { _ = recover() }()
	switch f := form.(type) {
	case map[string]string:
		return f[key]
	case map[string]any:
		return f[key]
	default:
		type getter interface {
			Get(string) any
		}
		if g, ok := form.(getter); ok {
			return g.Get(key)
		}
	}
	return nil
}

func isASCII(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] >= 0x80 {
			return false
		}
	}
	return true
}

func isDigits(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}
