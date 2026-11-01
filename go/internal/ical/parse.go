// Package ical reads iCalendar feeds with the standard library only. It is a
// port of App/app/icalsync.py: the regexes and PLATFORM_HINTS (lines 40-128),
// and _as_date, _event_status, is_block, _guest_name_hint, the synthetic UID
// helpers, parse_events and platform_of (lines 194-370). The golden files in
// testdata/ are written by App/scripts/ical_golden.py from the Python code, so
// this package must match them byte for byte.
package ical

import (
	"crypto/sha1"
	"encoding/hex"
	"errors"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	_ "time/tzdata"
)

// Event is one stay, with the same keys as the dicts parse_events returns.
type Event struct {
	UID            string  `json:"uid"`
	DateFrom       string  `json:"date_from"`
	DateTo         string  `json:"date_to"`
	Summary        string  `json:"summary"`
	Description    string  `json:"description"`
	IsBlock        bool    `json:"is_block"`
	IsCancelled    bool    `json:"is_cancelled"`
	Recurring      bool    `json:"recurring"`
	ReservationURL *string `json:"reservation_url"`
	PhoneLast4     *string `json:"phone_last4"`
	GuestEmail     *string `json:"guest_email"`
	NameHint       string  `json:"name_hint"`
}

// wsClass is Python's str.isspace() set. Python's \s and \S mean this; RE2's
// \s is ASCII only.
const wsClass = `\t\n\v\f\r \x1c-\x1f\x85\p{Z}`

var (
	blockRE              = regexp.MustCompile(`(?i)not available|unavailable|blocked|nedostupn|blokov|^busy$|preparation|airbnb \(not available\)|owner block|host block|maintenance|^closed$`)
	closedNotAvailableRE = regexp.MustCompile(`(?i)^CLOSED[` + wsClass + `]*-[` + wsClass + `]*Not available$`)
	genericSummaryRE     = regexp.MustCompile(`(?i)^(?:reserved|closed|closed[` + wsClass + `]*-[` + wsClass + `]*not available|booking|busy|reservation|booked)$`)
	urlRE                = regexp.MustCompile(`(https?://[^` + wsClass + `]+)`)
	phoneRE              = regexp.MustCompile(`(?im)phone[^\n]*?(\p{Nd}{4})[` + wsClass + `]*$`)
	emailRE              = regexp.MustCompile(`[\p{L}\p{N}_.+-]+@[\p{L}\p{N}_-]+\.[\p{L}\p{N}_.]+`)
	dateOnlyRE           = regexp.MustCompile(`^[0-9]{8}$`)
	durationRE           = regexp.MustCompile(`^([+-]?)P(?:([0-9]+)W)?(?:([0-9]+)D)?(?:T(?:([0-9]+)H)?(?:([0-9]+)M)?(?:([0-9]+)S)?)?$`)
)

var prague = mustLoad("Europe/Prague")

var platformHints = []struct {
	name  string
	hints []string
}{
	{"airbnb", []string{"airbnb"}},
	{"booking", []string{"booking.com", "booking"}},
	{"agoda", []string{"agoda"}},
	{"vrbo", []string{"vrbo", "homeaway"}},
	{"expedia", []string{"expedia"}},
	{"tripadvisor", []string{"tripadvisor", "flipkey"}},
	{"trip", []string{"trip.com", "ctrip"}},
	{"google", []string{"google.com/calendar", "calendar.google"}},
	{"apple", []string{"icloud.com"}},
	{"echalupy", []string{"e-chalupy", "echalupy"}},
}

func mustLoad(name string) *time.Location {
	loc, err := time.LoadLocation(name)
	if err != nil {
		panic(err)
	}
	return loc
}

// ParseEvents returns the stays in an iCal document, as parse_events does.
// A document Python cannot parse returns an error and no events.
//
// Python keeps a leading UTF-8 BOM, and then fails on it, so this does too.
func ParseEvents(text string) ([]Event, error) {
	roots, err := parseTree(text)
	if err != nil {
		return nil, err
	}
	if len(roots) != 1 || roots[0].name != "VCALENDAR" {
		return nil, errors.New("ical: expected exactly one VCALENDAR")
	}
	calendar := roots[0]
	calendarCancelled := strings.ToUpper(strings.TrimSpace(calendar.textOf("METHOD"))) == "CANCEL"

	comps := walkVEvents(calendar, nil)
	ambiguous := ambiguousSynthetic(comps)
	events := []Event{}
	for _, c := range comps {
		startProp, hasStart := c.props["DTSTART"]
		start := ""
		if hasStart {
			start, err = dateOf(startProp)
			if err != nil {
				return nil, err
			}
		}
		end := ""
		if endProp, ok := c.props["DTEND"]; ok {
			end, err = dateOf(endProp)
			if err != nil {
				return nil, err
			}
		}
		if !hasStart {
			continue
		}
		if end == "" {
			if durProp, ok := c.props["DURATION"]; ok {
				secs, err := durationSeconds(durProp.value)
				if err != nil {
					return nil, err
				}
				if secs > 0 {
					end = addDays(start, secs/86400)
				} else {
					end = addDays(start, 1)
				}
			} else {
				end = addDays(start, 1)
			}
		}

		summary := strings.TrimSpace(c.textOf("SUMMARY"))
		description := descriptionOf(c)
		uid := strings.TrimSpace(c.textOf("UID"))
		if uid == "" {
			uid = syntheticUID(summary, description, sequenceOf(c))
			if ambiguous[uid] {
				uid = uid + "-" + start
			}
		}

		status := strings.ToUpper(strings.TrimSpace(c.textOf("STATUS")))
		var reservationURL *string
		if m := urlRE.FindStringSubmatch(description); m != nil {
			reservationURL = trimmed(m[1])
		} else if m := urlRE.FindStringSubmatch(c.textOf("URL")); m != nil {
			reservationURL = trimmed(m[1])
		}
		var phoneLast4 *string
		if m := phoneRE.FindStringSubmatch(description); m != nil {
			phoneLast4 = &m[1]
		}
		var guestEmail *string
		if e := emailRE.FindString(description); e != "" {
			guestEmail = &e
		}
		recurring := false
		for _, name := range []string{"RRULE", "RDATE", "EXDATE"} {
			if p, ok := c.props[name]; ok && strings.TrimSpace(p.value) != "" {
				recurring = true
			}
		}

		events = append(events, Event{
			UID:            uid,
			DateFrom:       start,
			DateTo:         end,
			Summary:        summary,
			Description:    description,
			IsBlock:        IsBlock(summary),
			IsCancelled:    calendarCancelled || status == "CANCELLED" || status == "CANCELED",
			Recurring:      recurring,
			ReservationURL: reservationURL,
			PhoneLast4:     phoneLast4,
			GuestEmail:     guestEmail,
			NameHint:       guestNameHint(summary),
		})
	}
	return events, nil
}

// PlatformOf returns the portal a calendar came from, as platform_of does.
func PlatformOf(url, text string) string {
	if utf8.RuneCountInString(text) > 800 {
		text = string([]rune(text)[:800])
	}
	haystack := strings.ToLower(url + " " + text)
	for _, p := range platformHints {
		for _, hint := range p.hints {
			if strings.Contains(haystack, hint) {
				return p.name
			}
		}
	}
	return "ical"
}

// IsBlock reports whether a summary means a block rather than a guest stay.
func IsBlock(summary string) bool {
	text := strings.TrimSpace(summary)
	// Booking.com's closures are imported as stays, like its reservations.
	if closedNotAvailableRE.MatchString(text) {
		return false
	}
	return blockRE.MatchString(text)
}

func guestNameHint(summary string) string {
	text := strings.TrimSpace(summary)
	if text == "" || genericSummaryRE.MatchString(text) || IsBlock(text) {
		return ""
	}
	runes := []rune(text)
	if len(runes) > 80 {
		runes = runes[:80]
	}
	return string(runes)
}

func trimmed(s string) *string {
	t := strings.TrimRight(s, ".,);")
	return &t
}

func descriptionOf(c *component) string {
	return strings.TrimSpace(strings.ReplaceAll(c.textOf("DESCRIPTION"), `\n`, "\n"))
}

// sequenceOf mirrors str(SEQUENCE or ""): an integer is printed back in
// decimal, 0 is falsy in Python so it becomes "", and text that is not an
// integer is kept as it is.
func sequenceOf(c *component) string {
	raw := strings.TrimSpace(c.textOf("SEQUENCE"))
	if raw == "" {
		return ""
	}
	n, err := strconv.Atoi(raw)
	if err != nil {
		return raw
	}
	if n == 0 {
		return ""
	}
	return strconv.Itoa(n)
}

func syntheticUID(summary, description, sequence string) string {
	sum := sha1.Sum([]byte(summary + "\x1f" + description + "\x1f" + sequence))
	return "synthetic-" + hex.EncodeToString(sum[:])[:16]
}

// ambiguousSynthetic counts the UID-less keys over the whole feed before any
// event is read, as _ambiguous_synthetic_keys does.
func ambiguousSynthetic(comps []*component) map[string]bool {
	counts := map[string]int{}
	for _, c := range comps {
		if _, ok := c.props["DTSTART"]; !ok {
			continue
		}
		if strings.TrimSpace(c.textOf("UID")) != "" {
			continue
		}
		counts[syntheticUID(strings.TrimSpace(c.textOf("SUMMARY")), descriptionOf(c), sequenceOf(c))]++
	}
	ambiguous := map[string]bool{}
	for key, n := range counts {
		if n > 1 {
			ambiguous[key] = true
		}
	}
	return ambiguous
}

// dateOf returns the local date (YYYY-MM-DD) an iCal value means, as
// _as_date does. An unknown TZID is read as written.
func dateOf(p property) (string, error) {
	value := p.value
	if strings.EqualFold(p.params["VALUE"], "DATE") || dateOnlyRE.MatchString(value) {
		t, err := time.Parse("20060102", value)
		if err != nil {
			return "", err
		}
		return t.Format("2006-01-02"), nil
	}
	t, err := time.Parse("20060102T150405", strings.TrimSuffix(value, "Z"))
	if err != nil {
		return "", err
	}
	if strings.HasSuffix(value, "Z") {
		return t.In(prague).Format("2006-01-02"), nil
	}
	if tzid, ok := p.params["TZID"]; ok {
		if loc, err := time.LoadLocation(tzid); err == nil {
			t = time.Date(t.Year(), t.Month(), t.Day(), t.Hour(), t.Minute(), t.Second(), 0, loc)
			return t.In(prague).Format("2006-01-02"), nil
		}
	}
	return t.Format("2006-01-02"), nil
}

// durationSeconds parses an RFC 5545 DURATION value.
func durationSeconds(value string) (int64, error) {
	m := durationRE.FindStringSubmatch(value)
	if m == nil || strings.Join(m[2:], "") == "" {
		return 0, errors.New("ical: bad DURATION")
	}
	num := func(s string) int64 {
		n, _ := strconv.ParseInt(s, 10, 64)
		return n
	}
	total := num(m[2])*7*86400 + num(m[3])*86400 + num(m[4])*3600 + num(m[5])*60 + num(m[6])
	if m[1] == "-" {
		total = -total
	}
	return total, nil
}

func addDays(date string, days int64) string {
	t, err := time.Parse("2006-01-02", date)
	if err != nil {
		panic(err)
	}
	return t.AddDate(0, 0, int(days)).Format("2006-01-02")
}

// unescapeText undoes the RFC 5545 TEXT escapes in one pass.
func unescapeText(s string) string {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		if s[i] == '\\' && i+1 < len(s) {
			switch s[i+1] {
			case 'n', 'N':
				b.WriteByte('\n')
				i++
				continue
			case ',', ';', '\\':
				b.WriteByte(s[i+1])
				i++
				continue
			}
		}
		b.WriteByte(s[i])
	}
	return b.String()
}

type property struct {
	params map[string]string
	value  string
}

type component struct {
	name     string
	props    map[string]property
	children []*component
}

func (c *component) textOf(name string) string {
	p, ok := c.props[name]
	if !ok {
		return ""
	}
	return unescapeText(p.value)
}

func walkVEvents(c *component, out []*component) []*component {
	if c.name == "VEVENT" {
		out = append(out, c)
	}
	for _, child := range c.children {
		out = walkVEvents(child, out)
	}
	return out
}

// unfold joins each continuation line (one leading space or tab) to the line
// before it. Empty lines are dropped.
func unfold(text string) []string {
	var lines []string
	for _, raw := range strings.Split(text, "\n") {
		raw = strings.TrimSuffix(raw, "\r")
		if raw == "" {
			continue
		}
		if (raw[0] == ' ' || raw[0] == '\t') && len(lines) > 0 {
			lines[len(lines)-1] += raw[1:]
			continue
		}
		lines = append(lines, raw)
	}
	return lines
}

func parseTree(text string) ([]*component, error) {
	var roots []*component
	var stack []*component
	for _, line := range unfold(text) {
		name, prop, ok, err := parseContentLine(line)
		if err != nil {
			return nil, err
		}
		if !ok {
			continue
		}
		switch name {
		case "BEGIN":
			c := &component{name: strings.ToUpper(strings.TrimSpace(prop.value)), props: map[string]property{}}
			if len(stack) == 0 {
				roots = append(roots, c)
			} else {
				top := stack[len(stack)-1]
				top.children = append(top.children, c)
			}
			stack = append(stack, c)
		case "END":
			if len(stack) == 0 || stack[len(stack)-1].name != strings.ToUpper(strings.TrimSpace(prop.value)) {
				return nil, errors.New("ical: END does not match BEGIN")
			}
			stack = stack[:len(stack)-1]
		default:
			if len(stack) == 0 {
				return nil, errors.New("ical: property outside a component")
			}
			top := stack[len(stack)-1]
			if _, dup := top.props[name]; !dup {
				top.props[name] = prop
			}
		}
	}
	if len(stack) != 0 {
		return nil, errors.New("ical: BEGIN without END")
	}
	return roots, nil
}

// parseContentLine splits NAME;PARAM=VALUE:VALUE. The bool is false for a line
// with no colon, which icalendar skips without error.
func parseContentLine(line string) (string, property, bool, error) {
	if !strings.Contains(line, ":") {
		return "", property{}, false, nil
	}
	i := 0
	for i < len(line) && line[i] != ';' && line[i] != ':' {
		i++
	}
	name := strings.ToUpper(line[:i])
	if !validName(name) {
		return "", property{}, false, errors.New("ical: bad property name")
	}
	params := map[string]string{}
	for i < len(line) && line[i] == ';' {
		i++
		start := i
		for i < len(line) && line[i] != '=' && line[i] != ':' && line[i] != ';' {
			i++
		}
		if i >= len(line) || line[i] != '=' {
			return "", property{}, false, errors.New("ical: bad parameter")
		}
		pname := strings.ToUpper(line[start:i])
		i++
		for {
			var val string
			if i < len(line) && line[i] == '"' {
				end := strings.IndexByte(line[i+1:], '"')
				if end < 0 {
					return "", property{}, false, errors.New("ical: unclosed quote")
				}
				val = line[i+1 : i+1+end]
				i += end + 2
			} else {
				start = i
				for i < len(line) && line[i] != ',' && line[i] != ';' && line[i] != ':' {
					i++
				}
				val = line[start:i]
			}
			if _, dup := params[pname]; !dup {
				params[pname] = val
			}
			if i < len(line) && line[i] == ',' {
				i++
				continue
			}
			break
		}
	}
	if i >= len(line) || line[i] != ':' {
		return "", property{}, false, errors.New("ical: missing colon")
	}
	return name, property{params: params, value: line[i+1:]}, true, nil
}

func validName(name string) bool {
	if name == "" {
		return false
	}
	for i := 0; i < len(name); i++ {
		c := name[i]
		if !(c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' || c == '-') {
			return false
		}
	}
	return true
}
