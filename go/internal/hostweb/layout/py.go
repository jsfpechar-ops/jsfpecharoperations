package layout

import (
	"fmt"
	"html/template"
	"reflect"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode"
)

// esc is markupsafe.escape: & < > " ' become &amp; &lt; &gt; &#34; &#39;.
// A template.HTML value is already markup and passes through, as Markup does.
func esc(v any) string {
	if h, ok := v.(template.HTML); ok {
		return string(h)
	}
	return escText(pyStr(v))
}

var escReplacer = strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;", `"`, "&#34;", "'", "&#39;")

func escText(s string) string { return escReplacer.Replace(s) }

// safe is a "| safe" parameter (attrs, actions, a facts value): a
// template.HTML value is written as it is, any other value is escaped, so a
// Go page marks raw markup on purpose with the safe func.
func safe(v any) string { return esc(v) }

// pyStr is Python's str() for the values templates print.
func pyStr(v any) string {
	switch x := v.(type) {
	case nil:
		return "None"
	case string:
		return x
	case template.HTML:
		return string(x)
	case bool:
		if x {
			return "True"
		}
		return "False"
	case *int:
		if x == nil {
			return "None"
		}
		return strconv.Itoa(*x)
	case fmt.Stringer:
		return x.String()
	}
	return fmt.Sprint(v)
}

// truthy is Python truth: None, False, 0, "" and empty collections are false.
func truthy(v any) bool {
	switch x := v.(type) {
	case nil:
		return false
	case bool:
		return x
	case string:
		return x != ""
	case template.HTML:
		return x != ""
	case int:
		return x != 0
	case int64:
		return x != 0
	case float64:
		return x != 0
	case *int:
		return x != nil && *x != 0
	}
	rv := reflect.ValueOf(v)
	switch rv.Kind() {
	case reflect.Slice, reflect.Map, reflect.Array, reflect.String:
		return rv.Len() > 0
	case reflect.Ptr, reflect.Interface:
		return !rv.IsNil()
	}
	return true
}

// toInt reads an integer argument; anything else is 0.
func toInt(v any) int {
	switch x := v.(type) {
	case int:
		return x
	case int64:
		return int(x)
	case int32:
		return int(x)
	case float64:
		return int(x)
	case *int:
		if x != nil {
			return *x
		}
	case string:
		n, _ := strconv.Atoi(strings.TrimSpace(x))
		return n
	}
	return 0
}

// pyMod is Python's %: the result has the sign of the divisor.
func pyMod(a, b int) int { return ((a % b) + b) % b }

// rsplit1 is Python's s.rsplit(' ', 1).
func rsplit1(s string) []string {
	i := strings.LastIndex(s, " ")
	if i < 0 {
		return []string{s}
	}
	return []string{s[:i], s[i+1:]}
}

// firstUpper is Jinja's name[:1] | upper.
func firstUpper(s string) string {
	for _, r := range s {
		return strings.ToUpper(string(r))
	}
	return ""
}

var (
	commentRe = regexp.MustCompile(`(?s)<!--.*?-->`)
	tagRe     = regexp.MustCompile(`(?s)<.*?>`)
	entityRep = strings.NewReplacer("&amp;", "&", "&lt;", "<", "&gt;", ">", "&#34;", `"`, "&#39;", "'", "&quot;", `"`)
)

// striptags is Jinja's striptags: comments and tags go, whitespace collapses,
// entities are unescaped.
func striptags(s string) string {
	s = commentRe.ReplaceAllString(s, "")
	s = tagRe.ReplaceAllString(s, "")
	s = strings.Join(strings.Fields(s), " ")
	return entityRep.Replace(s)
}

// truncate is Jinja's truncate(s, length, killwords=False, end='...', leeway=5).
func truncate(s string, length int) string {
	r := []rune(s)
	if len(r) <= length+5 {
		return s
	}
	cut := string(r[:length-3])
	if i := strings.LastIndex(cut, " "); i >= 0 {
		cut = cut[:i]
	}
	return cut + "..."
}

// items reads a list argument of tuples (a [][]any, [][2]string, [][3]any...)
// as rows of values.
func items(v any) [][]any {
	if v == nil {
		return nil
	}
	rv := reflect.ValueOf(v)
	if rv.Kind() != reflect.Slice && rv.Kind() != reflect.Array {
		return nil
	}
	out := make([][]any, 0, rv.Len())
	for i := 0; i < rv.Len(); i++ {
		row := rv.Index(i)
		for row.Kind() == reflect.Interface {
			row = row.Elem()
		}
		var cells []any
		if row.Kind() == reflect.Slice || row.Kind() == reflect.Array {
			for j := 0; j < row.Len(); j++ {
				cells = append(cells, row.Index(j).Interface())
			}
		} else {
			cells = []any{row.Interface()}
		}
		out = append(out, cells)
	}
	return out
}

func cell(row []any, i int) any {
	if i < len(row) {
		return row[i]
	}
	return nil
}

// isDigits is Python's str.isdigit on a non-empty string.
func isDigits(s string) bool {
	if s == "" {
		return false
	}
	for _, r := range s {
		if !unicode.IsDigit(r) {
			return false
		}
	}
	return true
}

// isAlpha is Python's str.isalpha.
func isAlpha(s string) bool {
	if s == "" {
		return false
	}
	for _, r := range s {
		if !unicode.IsLetter(r) {
			return false
		}
	}
	return true
}

// isoLayouts are the forms datetime.fromisoformat reads that the app writes.
var isoLayouts = []string{
	"2006-01-02T15:04:05.999999999Z07:00",
	"2006-01-02 15:04:05.999999999Z07:00",
	"2006-01-02T15:04:05.999999999",
	"2006-01-02 15:04:05.999999999",
	"2006-01-02T15:04Z07:00",
	"2006-01-02 15:04Z07:00",
	"2006-01-02T15:04",
	"2006-01-02 15:04",
	"2006-01-02",
}

// datetimeLocal is templating._datetime_local: a stored UTC timestamp in
// Prague time, "YYYY-MM-DD HH:MM" (with seconds when asked); text that does
// not parse is shown as stored.
func datetimeLocal(value any, seconds ...bool) string {
	text := ""
	if value != nil {
		text = strings.TrimSpace(pyStr(value))
	}
	if text == "" || text == "None" {
		return ""
	}
	width := 16
	if len(seconds) > 0 && seconds[0] {
		width = 19
	}
	for _, layout := range isoLayouts {
		parsed, err := time.Parse(layout, text)
		if err != nil {
			continue
		}
		local := parsed.In(prague).Format("2006-01-02 15:04:05")
		return local[:width]
	}
	r := []rune(text)
	if len(r) > width {
		r = r[:width]
	}
	return strings.ReplaceAll(string(r), "T", " ")
}
