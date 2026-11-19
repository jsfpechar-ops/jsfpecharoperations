package staydetail

import (
	"embed"
	"fmt"
	"net/url"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/countries"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

//go:embed i18n.json
var catalogJSON []byte

//go:embed templates/*.tmpl
var templateFS embed.FS

var catalog = hostweb.Load(catalogJSON)

var tplFuncs = map[string]any{
	"weekday":            weekday,
	"date_short":         dateShort,
	"date_cz":            dateCZ,
	"nights":             nights,
	"source_label":       sourceLabel,
	"deadline_cell":      deadlineCell,
	"link_window":        linkWindow,
	"identity_visible":   identityVisible,
	"display_birth_date": displayBirthDate,
	"country_name":       countryName,
	"entered_by_label":   enteredByLabel,
	"validation_message": validationMessage,
	"payments_hidden":    paymentsHidden,
	"havel_on":           havelOn,
	"urlencode":          urlencode,
	"leadName":           leadName,
	"is_demo":            isDemo,
	"is_nil_int":         isNilInt,
	"format_time_iso":    formatTimeISO,
	"seq_range":          seqRange,
	"append":             appendSlice,
	"join":               joinStrings,
	"max":                maxInt,
	"first":              firstWhere,
	"where":              filterWhere,
	"in":                 inSlice,
	"list":               makeList,
}

var weekdays = map[string][7]string{
	"en": {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"},
	"cs": {"po", "út", "st", "čt", "pá", "so", "ne"},
	"vi": {"T2", "T3", "T4", "T5", "T6", "T7", "CN"},
}

var prague = func() *time.Location {
	loc, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		panic("staydetail: Prague zone: " + err.Error())
	}
	return loc
}()

func pragueToday(at time.Time) time.Time {
	y, m, d := at.In(prague).Date()
	return time.Date(y, m, d, 0, 0, 0, 0, time.UTC)
}

func weekday(v string) string {
	if t, ok := validation.ParseISODate(v); ok {
		lang := "en"
		if ws, ok := weekdays[lang]; ok {
			idx := (int(t.Weekday()) + 6) % 7
			return ws[idx]
		}
	}
	return v
}

func dateShort(v string) string {
	if t, ok := validation.ParseISODate(v); ok {
		return fmt.Sprintf("%d.%d.", t.Day(), t.Month())
	}
	return v
}

func dateCZ(v string) string {
	if t, ok := validation.ParseISODate(v); ok {
		return t.Format("02.01.2006")
	}
	return v
}

func nights(from, to string) int {
	a, ok1 := validation.ParseISODate(from)
	b, ok2 := validation.ParseISODate(to)
	if !ok1 || !ok2 || !b.After(a) {
		return 0
	}
	return int(b.Sub(a).Hours() / 24)
}

var portalSourceLabels = map[string]string{
	"airbnb": "Airbnb", "booking": "Booking.com", "agoda": "Agoda",
	"vrbo": "Vrbo", "expedia": "Expedia", "tripadvisor": "Tripadvisor",
	"trip": "Trip.com", "google": "Google Calendar", "apple": "Apple Calendar",
}

var staySourceI18nKeys = map[string]string{
	"manual": "stays.source.manual",
	"ical":   "stays.source.ical",
	"demo":   "stays.source.demo",
}

func sourceLabel(lang, source string) string {
	source = strings.TrimSpace(strings.ToLower(source))
	if label, ok := portalSourceLabels[source]; ok {
		return label
	}
	if key, ok := staySourceI18nKeys[source]; ok {
		return catalog.T(lang, key, nil)
	}
	if source == "" {
		return ""
	}
	s := strings.ReplaceAll(source, "_", " ")
	if s == "" {
		return ""
	}
	return strings.ToUpper(s[:1]) + s[1:]
}

func deadlineCell(p stays.Progress, checkIn *time.Time) layout.DeadlineCell {
	if p.HasCell {
		return p.Cell
	}
	return layout.DeadlineCell{}
}

type linkWindowView struct {
	State string
	Opens string
}

func linkWindow(res Stay) *linkWindowView {
	return nil
}

func identityVisible(guestID int64) bool {
	return false
}

func displayBirthDate(v string) string {
	if t, ok := validation.ParseISODate(v); ok {
		return t.Format("02.01.2006")
	}
	return v
}

func countryName(nationality, lang string) string {
	return countries.Name(nationality, lang)
}

func enteredByLabel(value string) string {
	value = strings.TrimSpace(value)
	switch value {
	case "host":
		return "Host"
	case "guest":
		return "Guest"
	case "api_mobile":
		return "Mobile API"
	}
	return value
}

func validationMessage(message string) string {
	if strings.HasPrefix(message, "validation.") {
		return message
	}
	return message
}

func paymentsHidden(getenv func(string) string) bool {
	switch strings.ToLower(getenv("UBYHOST_PAYMENTS_HIDDEN")) {
	case "1", "true", "yes":
		return true
	}
	return false
}

func havelOn() bool {
	return false
}

func urlencode(s string) string {
	return url.QueryEscape(s)
}

func leadName(guestRows []GuestRow) string {
	for _, row := range guestRows {
		if row.Guest.IsLead {
			return strings.TrimSpace(row.Guest.Row.FirstName + " " + row.Guest.Row.Surname)
		}
	}
	if len(guestRows) > 0 {
		return strings.TrimSpace(guestRows[0].Guest.Row.FirstName + " " + guestRows[0].Guest.Row.Surname)
	}
	return ""
}

func isDemo(name, source string) bool {
	return strings.Contains(name, "(demo)") || source == "demo"
}

func formatTimeISO(t *time.Time, format string) string {
	if t == nil {
		return ""
	}
	return t.Format(format)
}

func seqRange(from, to int) []int {
	if from > to {
		return []int{}
	}
	result := make([]int, 0, to-from+1)
	for i := from; i < to; i++ {
		result = append(result, i)
	}
	return result
}

func appendSlice(slice []string, item string) []string {
	return append(slice, item)
}

func joinStrings(items []string, sep string) string {
	return strings.Join(items, sep)
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func isNilInt(p *int) bool {
	return p == nil
}

func firstWhere(items interface{}, key string, values interface{}) interface{} {
	return nil
}

func filterWhere(items interface{}, key string, values interface{}) interface{} {
	return items
}

func inSlice(item interface{}, slice interface{}) bool {
	return false
}

func makeList(items ...interface{}) []interface{} {
	return items
}

var pages = layout.MustParseFuncs(catalog, tplFuncs, templateFS, "templates/*.tmpl")
