// Package cleaning ports the parts of the Python cleaning area that need no host
// page layout: the schedule JSON, the standalone shared cleaner page and its
// JSON, the delete of one cleaning and the revoke of a share. The Python files
// are the reference: App/app/routes/cleaning.py, App/app/cleaning.py,
// App/app/cleaning_i18n.py and the templates _cleaning_*.html and
// cleaning_shared.html. Nothing here is switched on (no Caddy path moves).
package cleaning

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode/utf16"
)

//go:embed i18n.json
var i18nJSON []byte

// catalog is i18n.json, written by App/scripts/go_cleaning_i18n.py.
type catalog struct {
	Words     map[string]map[string]string `json:"words"`
	Host      map[string]map[string]string `json:"host"`
	Weekdays  map[string][]string          `json:"weekdays"`
	CalLabels map[string]map[string]string `json:"calendar_labels"`
}

var texts = loadCatalog()

func loadCatalog() catalog {
	var c catalog
	if err := json.Unmarshal(i18nJSON, &c); err != nil {
		panic("cleaning: bad i18n.json: " + err.Error())
	}
	return c
}

// ct is cleaning_i18n.translator(lang)(key): a missing key is its own text.
func ct(lang, key string) string {
	if v, ok := texts.Words[lang][key]; ok {
		return v
	}
	return key
}

// t is host_i18n.translate(lang, key) for the keys in i18n.json.
func t(lang, key string) string {
	if v, ok := texts.Host[lang][key]; ok {
		return v
	}
	return key
}

// formatCount is Jinja's format(count=n) on a "%(count)s" text.
func formatCount(text string, n int) string {
	return strings.ReplaceAll(text, "%(count)s", strconv.Itoa(n))
}

var shortDays = map[string][]string{
	"en": {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"},
	"vi": {"T2", "T3", "T4", "T5", "T6", "T7", "CN"},
	"cs": {"Po", "Út", "St", "Čt", "Pá", "So", "Ne"},
}

var months = []string{"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"}

// weekdayIndex is Python's date.weekday(): Monday is 0.
func weekdayIndex(d time.Time) int { return (int(d.Weekday()) + 6) % 7 }

func parseDay(value string) (time.Time, bool) {
	d, err := time.Parse("2006-01-02", value)
	return d, err == nil
}

// cdate is _context.full_date.
func cdate(lang, value string) string {
	d, ok := parseDay(value)
	if !ok {
		return value
	}
	names := texts.Weekdays[lang]
	if len(names) != 7 {
		names = texts.Weekdays["cs"]
	}
	return fmt.Sprintf("%s %d.%d.%d", names[weekdayIndex(d)], d.Day(), int(d.Month()), d.Year())
}

// cday is _context.cleaning_day.
func cday(lang, value string) string {
	d, ok := parseDay(value)
	if !ok {
		return value
	}
	days := shortDays[lang]
	if days == nil {
		days = shortDays["cs"]
	}
	switch lang {
	case "en":
		return fmt.Sprintf("%s %d %s", days[weekdayIndex(d)], d.Day(), months[d.Month()-1])
	case "vi":
		return fmt.Sprintf("%s %d/%d", days[weekdayIndex(d)], d.Day(), int(d.Month()))
	}
	return fmt.Sprintf("%s %d. %d.", days[weekdayIndex(d)], d.Day(), int(d.Month()))
}

// cshort is _context.cleaning_short.
func cshort(lang, value string) string {
	d, ok := parseDay(value)
	if !ok {
		return value
	}
	switch lang {
	case "en":
		return fmt.Sprintf("%d %s", d.Day(), months[d.Month()-1])
	case "vi":
		return fmt.Sprintf("%d/%d", d.Day(), int(d.Month()))
	}
	return fmt.Sprintf("%d. %d.", d.Day(), int(d.Month()))
}

// pyString is one JSON string as Python's json.dumps writes it (ensure_ascii),
// after Jinja's tojson has turned < > & ' into \u escapes.
func pyString(s string) string {
	var out strings.Builder
	out.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"':
			out.WriteString(`\"`)
		case '\\':
			out.WriteString(`\\`)
		case '\n':
			out.WriteString(`\n`)
		case '\r':
			out.WriteString(`\r`)
		case '\t':
			out.WriteString(`\t`)
		case '\b':
			out.WriteString(`\b`)
		case '\f':
			out.WriteString(`\f`)
		case '<', '>', '&', '\'':
			fmt.Fprintf(&out, `\u%04x`, r)
		default:
			if r < 0x20 || r > 0x7e {
				for _, u := range utf16.Encode([]rune{r}) {
					fmt.Fprintf(&out, `\u%04x`, u)
				}
				continue
			}
			out.WriteRune(r)
		}
	}
	out.WriteByte('"')
	return out.String()
}

// tojsonMap is Jinja's tojson on a dict of strings: keys sorted, ", " and ": "
// between the items, as json.dumps(sort_keys=True) writes them.
func tojsonMap(m map[string]string) string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	parts := make([]string, 0, len(keys))
	for _, k := range keys {
		parts = append(parts, pyString(k)+": "+pyString(m[k]))
	}
	return "{" + strings.Join(parts, ", ") + "}"
}

// tojsonProperty is Jinja's tojson on {'id': id, 'name': name}.
func tojsonProperty(id int64, name string) string {
	return fmt.Sprintf(`{"id": %d, "name": %s}`, id, pyString(name))
}
