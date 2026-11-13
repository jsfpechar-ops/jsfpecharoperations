package billingweb

import (
	"strconv"
	"strings"
	"time"
	"unicode"
)

// isPySpace is Python's str.isspace for the characters statements and names can hold.
func isPySpace(r rune) bool { return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f) }

// pyStrip is str.strip().
func pyStrip(s string) string { return strings.TrimFunc(s, isPySpace) }

// pyLStrip is str.lstrip().
func pyLStrip(s string) string { return strings.TrimLeftFunc(s, isPySpace) }

// pyLines is str.splitlines(): it splits after \n, \r, \r\n, \v, \f, \x1c-\x1e,
// \x85, U+2028 and U+2029 and drops the break.
func pyLines(s string) []string {
	var out []string
	var cur strings.Builder
	rs := []rune(s)
	for i := 0; i < len(rs); i++ {
		switch r := rs[i]; r {
		case '\n', '\v', '\f', 0x1c, 0x1d, 0x1e, 0x85, 0x2028, 0x2029:
		case '\r':
			if i+1 < len(rs) && rs[i+1] == '\n' {
				i++
			}
		default:
			cur.WriteRune(r)
			continue
		}
		out = append(out, cur.String())
		cur.Reset()
	}
	if cur.Len() > 0 {
		out = append(out, cur.String())
	}
	return out
}

// cut is s[:n] where n counts characters, as a Python slice does.
func cut(s string, n int) string {
	i := 0
	for idx := range s {
		if i == n {
			return s[:idx]
		}
		i++
	}
	return s
}

// floorDiv is Python's a // b for b > 0.
func floorDiv(a, b int64) int64 {
	q := a / b
	if a%b != 0 && a < 0 {
		q--
	}
	return q
}

func deref(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

func itoa(n int64) string { return strconv.FormatInt(n, 10) }

// csvField quotes a field the way csv.writer does with QUOTE_MINIMAL.
func csvField(f string) string {
	if strings.ContainsAny(f, ";\"\r\n") {
		return "\"" + strings.ReplaceAll(f, "\"", "\"\"") + "\""
	}
	return f
}

// csvBytes is the shared writer of the accountant's files: a BOM, semicolons
// and \r\n, so Czech Excel opens it straight away (billing_admin.export_csv,
// billing_analytics._csv_bytes).
func csvBytes(header []string, rows [][]string) []byte {
	var b strings.Builder
	b.WriteString(bom)
	for _, row := range append([][]string{header}, rows...) {
		for i, f := range row {
			if i > 0 {
				b.WriteString(";")
			}
			b.WriteString(csvField(f))
		}
		b.WriteString("\r\n")
	}
	return []byte(b.String())
}

// dayOf keeps only the year, month and day of t (zero means now), in UTC.
func dayOf(t time.Time) time.Time {
	if t.IsZero() {
		t = time.Now()
	}
	return time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, time.UTC)
}

func isoDay(t time.Time) string { return t.Format("2006-01-02") }

// parseDay is date.fromisoformat(s[:10]).
func parseDay(s string) (time.Time, error) { return time.Parse("2006-01-02", cut(s, 10)) }

// daysBetween is (a - b).days for two midnight UTC days.
func daysBetween(a, b time.Time) int { return int(a.Sub(b) / (24 * time.Hour)) }

// bom is the UTF-8 byte order mark, written as bytes so no source line holds it.
const bom = "\xef\xbb\xbf"
