package stays

import (
	"fmt"
	"net/url"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/appconfig"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

var tplFuncs = map[string]any{
	"date_cz":         dateCZ,
	"stay_range":      stayRange,
	"nights":          nights,
	"source_label":    sourceLabel,
	"journey_step":    journeyStep,
	"journey_strip":   RenderJourneyStrip,
	"journey_summary": RenderJourneySummary,
	"journey_legend":  RenderJourneyLegend,
	"lead_name":       leadName,
	"shown_name":      shownName,
	"stay_label":      stayLabel,
	"stay_group":      stayGroup,
	"payments_hide":   paymentsHidden,
	"public_base":     publicBaseURL,
	"min_int":         minInt,
	"page_from":       pageFrom,
	"page_to":         pageTo,
	"layout_progress": layoutProgress,
	"is_demo":         isDemo,
	"slug_or":         slugOr,
	"not_registered":  notRegistered,
	"in_house":        inHouse,
	"initial_rune":    initialRune,
	"encode_return":   encodeReturn,
	"day_of_month":    dayOfMonth,
	"is_nil_int":      isNilInt,
	"bad":             guestBad,
	"errFor":          guestErrFor,
	"guestVal":        guestVal,
}

func inHouse(checkIn time.Time, hasCheckIn bool, dateTo string, today time.Time) bool {
	if !hasCheckIn {
		return false
	}
	checkOut, ok := validation.ParseISODate(dateTo)
	if !ok {
		return false
	}
	now := pragueToday(today)
	return !checkIn.After(now) && !checkOut.Before(now)
}

func initialRune(s string) string {
	if s == "" {
		return ""
	}
	return strings.ToUpper(s[:1])
}

var prague = func() *time.Location {
	loc, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		panic("stays: Prague zone: " + err.Error())
	}
	return loc
}()

func pragueToday(at time.Time) time.Time {
	y, m, d := at.In(prague).Date()
	return time.Date(y, m, d, 0, 0, 0, 0, time.UTC)
}

func dateCZ(v string) string {
	if t, ok := validation.ParseISODate(v); ok {
		return t.Format("02.01.2006")
	}
	return v
}

// stayRange matches templating.stay_range (0766 phone cards).
var passWeekdays = map[string][7]string{
	"en": {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"},
	"cs": {"po", "út", "st", "čt", "pá", "so", "ne"},
	"vi": {"T2", "T3", "T4", "T5", "T6", "T7", "CN"},
}

var passMonths = map[string][12]string{
	"en": {"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"},
	"cs": {"led", "úno", "bře", "dub", "kvě", "čvn", "čvc", "srp", "zář", "říj", "lis", "pro"},
	"vi": {"thg 1", "thg 2", "thg 3", "thg 4", "thg 5", "thg 6", "thg 7", "thg 8", "thg 9", "thg 10", "thg 11", "thg 12"},
}

func stayRange(lang, from, to string) string {
	start, ok1 := validation.ParseISODate(from)
	end, ok2 := validation.ParseISODate(to)
	if !ok1 || !ok2 {
		return ""
	}
	if _, ok := passWeekdays[lang]; !ok {
		lang = "en"
	}
	wd := passWeekdays[lang]
	mo := passMonths[lang]
	pyWd := func(t time.Time) string { return wd[(int(t.Weekday())+6)%7] }
	if lang == "vi" {
		return pyWd(start) + " " + fmtDayMonthVI(start) + " – " + pyWd(end) + " " + fmtDayMonthVI(end)
	}
	sameMonth := start.Year() == end.Year() && start.Month() == end.Month()
	if lang == "cs" {
		if sameMonth {
			return fmt.Sprintf("%s %d. – %s %d. %d.", pyWd(start), start.Day(), pyWd(end), end.Day(), int(end.Month()))
		}
		return fmt.Sprintf("%s %d. %d. – %s %d. %d.", pyWd(start), start.Day(), int(start.Month()), pyWd(end), end.Day(), int(end.Month()))
	}
	if sameMonth {
		return fmt.Sprintf("%s %d – %s %d %s", pyWd(start), start.Day(), pyWd(end), end.Day(), mo[end.Month()-1])
	}
	return fmt.Sprintf("%s %d %s – %s %d %s", pyWd(start), start.Day(), mo[start.Month()-1], pyWd(end), end.Day(), mo[end.Month()-1])
}

func fmtDayMonthVI(t time.Time) string {
	return fmt.Sprintf("%d/%d", t.Day(), int(t.Month()))
}

func nights(from, to string) int {
	a, ok1 := validation.ParseISODate(from)
	b, ok2 := validation.ParseISODate(to)
	if !ok1 || !ok2 || !b.After(a) {
		return 0
	}
	return int(b.Sub(a).Hours() / 24)
}

// portalSourceLabels matches App/app/templating.py _PORTAL_LABELS (proper nouns, not i18n).
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

// sourceLabel matches templating._source_label: portal names as literals,
// UbyHost-written sources via host_i18n, unknown slugs title-cased.
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

// journeyStep matches App/app/workflow.py step_number (status → step 2–5).
func journeyStep(status string) int {
	switch status {
	case "awaiting_guest", "incomplete":
		return 2
	case "ready", "awaiting_verification", "failed":
		return 4
	case "reported":
		return 5
	}
	return 0
}

func leadName(guests []Guest) string {
	var lead *Guest
	for i := range guests {
		if guests[i].IsLead {
			lead = &guests[i]
			break
		}
	}
	if lead == nil && len(guests) > 0 {
		lead = &guests[0]
	}
	if lead == nil {
		return ""
	}
	return strings.TrimSpace(lead.FirstName + " " + lead.Surname)
}

func shownName(res Reservation, guests []Guest) string {
	if n := leadName(guests); n != "" {
		return n
	}
	if res.Source == "manual" {
		s := strings.TrimSpace(res.Summary)
		if s != "" {
			return s
		}
	}
	return ""
}

func stayLabel(res Reservation) string {
	if res.Source == "manual" {
		s := strings.TrimSpace(res.Summary)
		if s != "" {
			return s
		}
	}
	return res.InternalName
}

func stayGroup(res Reservation, today time.Time) string {
	dFrom, ok1 := validation.ParseISODate(res.DateFrom)
	dTo, ok2 := validation.ParseISODate(res.DateTo)
	now := pragueToday(today)
	if ok2 && dTo.Before(now) {
		return "earlier"
	}
	if ok1 && !dFrom.After(now) {
		return "today"
	}
	if ok1 && dFrom.Sub(now).Hours() <= 7*24 {
		return "week"
	}
	return "later"
}

func paymentsHidden(getenv func(string) string) bool {
	return appconfig.PaymentsHidden(getenv)
}

func publicBaseURL(getenv func(string) string) string {
	if u := getenv("UBYHOST_PUBLIC_BASE_URL"); u != "" {
		return strings.TrimRight(u, "/")
	}
	return ""
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func pageFrom(page, pageSize int) int {
	return (page-1)*pageSize + 1
}

func pageTo(page, pageSize, total int) int {
	n := page * pageSize
	if n > total {
		return total
	}
	return n
}

func layoutProgress(p Progress) layout.Progress {
	return layout.Progress{Expected: p.Expected, Filled: p.Filled, Guests: len(p.Guests)}
}

func isDemo(name, source string) bool {
	return strings.Contains(name, "(demo)") || source == "demo"
}

func slugOr(slug *string, token string) string {
	if slug != nil && *slug != "" {
		return *slug
	}
	return token
}

func notRegistered(p Progress) int {
	if p.NotRegistered == nil {
		return 0
	}
	return *p.NotRegistered
}

func encodeReturn(s string) string {
	return url.QueryEscape(s)
}

func dayOfMonth(iso string) int {
	t, ok := validation.ParseISODate(iso)
	if !ok {
		return 0
	}
	return t.Day()
}

func isNilInt(p *int) bool {
	return p == nil
}

var pages = layout.MustParseFuncs(catalog, tplFuncs, templateFS, "templates/*.tmpl")
