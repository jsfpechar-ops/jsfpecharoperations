package staydetail

import (
	"embed"
	"fmt"
	"strconv"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/countries"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validationi18n"
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
	"identity_visible":   identityVisible,
	"guest_line":         newGuestLine,
	"display_birth_date": displayBirthDate,
	"country_name":       countryName,
	"entered_by_label":   enteredByLabel,
	"validation_message": validationMessage,
	"urlencode":          urlencode,
	"leadName":           leadName,
	"is_demo":            isDemo,
	"format_time_iso":    formatTimeISO,
	"seq_range":          seqRange,
	"max":                maxInt,
	"deref_int":          derefInt,
	"py_int":             pyInt,
	"fix_href":           fixHref,
	"any_receipt":        anyReceipt,
	"displayName":        displayName,
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

// weekdayAbbr is strftime("%a") in the server's C locale.
var weekdayAbbr = [7]string{"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}

// weekday is the weekday filter (templating._weekday).
func weekday(v string) string {
	t, ok := validation.ParseISODate(v)
	if !ok {
		return ""
	}
	return weekdayAbbr[(int(t.Weekday())+6)%7]
}

// dateShort is validation.fmt_date_short: "d. m." and the year when it is not
// the server's current year (date.today(), UTC on the server).
func dateShort(v string, at time.Time) string {
	t, ok := validation.ParseISODate(v)
	if !ok {
		return v
	}
	short := fmt.Sprintf("%d. %d.", t.Day(), int(t.Month()))
	if t.Year() == at.UTC().Year() {
		return short
	}
	return short + " " + strconv.Itoa(t.Year())
}

func dateCZ(v string) string {
	if t, ok := validation.ParseISODate(v); ok {
		return t.Format("02.01.2006")
	}
	return v
}

// nights is templating._nights: days from check-in to check-out, 0 when a
// date is missing.
func nights(from, to string) int {
	a, ok1 := validation.ParseISODate(from)
	b, ok2 := validation.ParseISODate(to)
	if !ok1 || !ok2 {
		return 0
	}
	return int(b.Sub(a) / (24 * time.Hour))
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

// sourceLabel is templating._source_label: a portal's own name, UbyHost's
// sources in the host's language, else the slug as str.capitalize shows it.
func sourceLabel(lang, source string) string {
	source = strings.TrimSpace(source)
	if label, ok := portalSourceLabels[source]; ok {
		return label
	}
	if key, ok := staySourceI18nKeys[source]; ok {
		return catalog.T(lang, key, nil)
	}
	return pyCapitalize(strings.ReplaceAll(source, "_", " "))
}

// pyCapitalize is str.capitalize: the first character title case, the rest lower.
func pyCapitalize(s string) string {
	r, size := utf8.DecodeRuneInString(s)
	if size == 0 {
		return ""
	}
	return string(unicode.ToTitle(r)) + strings.ToLower(s[size:])
}

func deadlineCell(p stays.Progress, checkIn *time.Time) layout.DeadlineCell {
	if p.HasCell {
		return p.Cell
	}
	return layout.DeadlineCell{State: "none"}
}

// linkWindowView is workflow.link_window's result: State "now" while the stay
// is listed on the property's guest link, "from" before; Opens is ISO.
type linkWindowView struct {
	State string
	Opens string
}

// linkWindow is workflow.link_window: nil for a past, inactive, archived or
// demo stay. windowDays is workflow._window_days, read only after those checks.
func linkWindow(res Stay, today time.Time, windowDays func() (int, error)) (*linkWindowView, error) {
	if res.Status != "active" || res.ArchivedAt != "" || res.Source == "demo" {
		return nil, nil
	}
	start, ok := validation.ParseISODate(res.DateFrom)
	if !ok || start.Before(today) {
		return nil, nil
	}
	days, err := windowDays()
	if err != nil {
		return nil, err
	}
	opens := start.AddDate(0, 0, -days)
	if !opens.After(today) {
		return &linkWindowView{State: "now", Opens: today.Format(time.DateOnly)}, nil
	}
	return &linkWindowView{State: "from", Opens: opens.Format(time.DateOnly)}, nil
}

// identityAccess is what access.identity_visible reads from the request: an
// admin, or a host in their own workspace, sees every guest in full; an
// impersonating admin only the guests revealed in the session ("rv").
type identityAccess struct {
	All      bool
	Revealed []int64
}

func newIdentityAccess(h *session.Host) identityAccess {
	if h.Account.Role == "admin" || !h.Impersonating {
		return identityAccess{All: true}
	}
	var a identityAccess
	list, _ := h.Payload["rv"].([]any)
	for _, v := range list {
		switch n := v.(type) {
		case int64:
			a.Revealed = append(a.Revealed, n)
		case float64:
			a.Revealed = append(a.Revealed, int64(n))
		case int:
			a.Revealed = append(a.Revealed, int64(n))
		}
	}
	return a
}

// identityVisible is access.identity_visible(request, guest_id).
func identityVisible(a identityAccess, guestID int64) bool {
	if a.All {
		return true
	}
	for _, id := range a.Revealed {
		if id == guestID {
			return true
		}
	}
	return false
}

// guestLine is a guest row with the request's identity access, the data of
// the staydetail.id_line template.
type guestLine struct {
	GuestRow
	Access identityAccess
}

func newGuestLine(row GuestRow, a identityAccess) guestLine {
	return guestLine{GuestRow: row, Access: a}
}

// displayBirthDate is validation.display_birth_date: DD.MM.YYYY when the value
// normalises to eight digits, else the value as typed.
func displayBirthDate(v string) string {
	n := stayfee.NormaliseBirthDate(v)
	if len(n) == 8 && strings.Trim(n, "0123456789") == "" {
		return n[:2] + "." + n[2:4] + "." + n[4:]
	}
	return strings.TrimSpace(v)
}

func countryName(nationality, lang string) string {
	return countries.Name(nationality, lang)
}

var enteredByKeys = map[string]string{
	"guest":  "stay.detail.guests.entered_by.guest",
	"host":   "stay.detail.guests.entered_by.host",
	"import": "stay.detail.guests.entered_by.import",
}

// enteredByLabel is templating._entered_by_label: who typed a guest record, as
// a word rather than the stored slug.
func enteredByLabel(lang, value string) string {
	if key, ok := enteredByKeys[strings.TrimSpace(value)]; ok {
		return catalog.T(lang, key, nil)
	}
	return value
}

// validationMessage is the validation_message global: a validation.py
// sentence in the host's language.
func validationMessage(message, lang string) string {
	return validationi18n.Localize(message, lang)
}

// paymentsHidden is config.PAYMENTS_HIDDEN.
func paymentsHidden(getenv func(string) string) bool {
	switch strings.ToLower(strings.TrimSpace(getenv("UBYHOST_PAYMENTS_HIDDEN"))) {
	case "1", "true", "yes":
		return true
	}
	return false
}

// urlencode is Jinja's urlencode filter for a string: urllib quote with "/"
// kept, so a return_to path stays readable.
func urlencode(s string) string {
	const hex = "0123456789ABCDEF"
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		if 'A' <= c && c <= 'Z' || 'a' <= c && c <= 'z' || '0' <= c && c <= '9' || strings.IndexByte("_.-~/", c) >= 0 {
			b.WriteByte(c)
			continue
		}
		b.WriteByte('%')
		b.WriteByte(hex[c>>4])
		b.WriteByte(hex[c&15])
	}
	return b.String()
}

func derefInt(p *int) int {
	if p == nil {
		return 0
	}
	return *p
}

// pyInt is an optional count as Python's str.format shows it.
func pyInt(p *int) any {
	if p == nil {
		return "None"
	}
	return *p
}

// fixHref is stay_cta's fix_href: the first refused guest's page, else #guests.
func fixHref(rows []GuestRow, reservationID int64) string {
	for _, row := range rows {
		if row.Guest.SubmitState == "error" || row.Guest.SubmitState == "blocked" {
			return fmt.Sprintf("/guests/%d?return_to=/reservations/%d", row.Guest.ID, reservationID)
		}
	}
	return "#guests"
}

func anyReceipt(subs []Submission) bool {
	for _, s := range subs {
		if s.HasReceipt {
			return true
		}
	}
	return false
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

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

var pages = layout.MustParseFuncs(catalog, tplFuncs, templateFS, "templates/*.tmpl")
