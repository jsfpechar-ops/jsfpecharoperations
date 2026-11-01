// Package validation is the Go port of the guest and apartment checks in
// App/app/validation.py (Issue, validate_guest, validate_birth_date,
// validate_residence, parse_signature_data_url, validate_apartment,
// errors_only, parse_iso_date) and of App/app/reporting.py (guest_issues and
// guest_is_complete on the translate=None, allow_imported=True path).
//
// Messages, field names, severities and issue order are copied byte for byte.
// Python reads date.today() in validate_birth_date; here the clock is the
// today parameter. testdata/golden.json, written by
// App/scripts/validation_golden.py from the real Python functions, pins the
// behaviour; validation_test.go compares every case.
//
// Known differences, all outside the golden cases: Python's str.isdigit()
// also accepts digits outside Nd (superscripts), so the birth-date check here
// is ASCII-only; the Python dead branch "Home address is too long" (compose
// truncates to 255 first) is not ported; the NFKD folding in the normalisers
// is not ported because validate_guest takes stored, already normalised values.
package validation

import (
	"bytes"
	"encoding/base64"
	"fmt"
	"image"
	_ "image/jpeg" // registers the JPEG decoder for DecodeConfig
	_ "image/png"  // registers the PNG decoder for DecodeConfig
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/countries"
)

// Issue is validation.Issue: Severity is "error" (blocks submission) or "warning".
type Issue struct {
	Field    string
	Message  string
	Severity string
}

const (
	severityError   = "error"
	severityWarning = "warning"
)

// GuestRow holds the fields reporting.guest_dict reads, plus the stored stay
// dates and signature. Empty string stands for SQL NULL.
type GuestRow struct {
	Surname      string
	FirstName    string
	BirthDate    string
	Nationality  string
	DocNumber    string
	VisaNumber   string
	ResStreet    string
	ResCity      string
	ResCountry   string
	Purpose      string
	Note         string
	StayFrom     string
	StayTo       string
	SignaturePNG string
}

const (
	maxSurname         = 50
	maxFirstName       = 24
	maxDoc             = 30
	minDoc             = 6
	maxVisa            = 15
	maxResidencePart   = 42
	maxNote            = 255
	inpassDoc          = "INPASS"
	importedSignature  = "imported"
	czechCode          = "CZE"
	maxSignatureBytes  = 256 * 1024
	maxSignatureSide   = 6000
	maxSignaturePixels = 12000000
	// 4 base64 characters carry 3 bytes, so this is the longest payload that
	// can still decode to an allowed number of bytes.
	maxSignaturePayloadChars = 4*(maxSignatureBytes/3) + 4
)

const (
	nonLatinMessage = "Type this using Latin letters (A-Z), exactly as printed in the two " +
		"machine-readable lines at the bottom of your passport."
	inpassNoteMessage = "For a child recorded in a parent's passport the note must contain " +
		"the parent's document number."
	forbiddenCharMessage       = "Remove the | character and any line breaks."
	signatureInvalidMessage    = "That signature could not be saved. Sign again on the signature pad."
	hostSignatureRequiredMsg   = "A guest signature is required. Use the guest link or sign on the host form."
	webServiceLoginWarningText = "Web-service logins look like UBY-WS123abc (production) or uby-tws1ab45 (test). " +
		"The ub1234567 login is for the web form and will not work here."
	noPropertyManagerMessage = "No property manager is attached, so guests have no named contact " +
		"for questions about their stay."
	noControllerMessage = " The privacy notice also cannot name who controls their data."
)

// purposeCodes is validation.PURPOSE_CODES.
var purposeCodes = map[string]bool{
	"00": true, "01": true, "02": true, "03": true, "04": true, "05": true, "06": true,
	"07": true, "10": true, "11": true, "12": true, "13": true, "27": true, "93": true, "99": true,
}

var sigMagic = map[string][]byte{
	"image/png":  []byte("\x89PNG\r\n\x1a\n"),
	"image/jpeg": []byte("\xff\xd8\xff"),
}

var (
	sigDataURLRE = regexp.MustCompile(`^data:(image/[a-z0-9.+-]+);base64,([A-Za-z0-9+/=]*)$`)
	idubRE       = regexp.MustCompile(`^[A-Za-z0-9]{12,14}$`)
	markRE       = regexp.MustCompile(`^[A-Za-z0-9]{5,6}$`)
	// Python \d is Unicode (Nd), so \p{Nd} here; the patterns are IGNORECASE in Python.
	houseRE   = regexp.MustCompile(`(?i)^(?:\p{Nd}{1,4}|E\p{Nd}{1,4}|\p{Nd}{1,4}E)$`)
	orientRE  = regexp.MustCompile(`^\p{Nd}{1,3}[A-Za-z]?$`)
	wsUserRE  = regexp.MustCompile(`(?i)^(?:uby-ws[A-Za-z0-9]{6}|uby-ws_[A-Za-z0-9]{5,6}|uby-tws[A-Za-z0-9]{5})$`)
	isoDateRE = regexp.MustCompile(`^([0-9]{4})-(1[0-2]|0[1-9]|[1-9])-(3[01]|[12][0-9]|0[1-9]|[1-9]| [1-9])$`)
)

// pyLen is Python len() on a str: code points, not bytes.
func pyLen(s string) int { return utf8.RuneCountInString(s) }

// pyStrip is Python str.strip() with no arguments.
func pyStrip(s string) string {
	return strings.TrimFunc(s, func(r rune) bool {
		return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f)
	})
}

// pyUpper mirrors Python str.upper() for the cases that reach here. Same rule
// as ubyport.pyUpper; copied because this package must not import ubyport for
// its helpers.
func pyUpper(s string) string {
	return strings.ToUpper(strings.ReplaceAll(s, "ß", "SS"))
}

// pyIsDigit is Python str.isdigit() for non-empty strings (Nd only here).
func pyIsDigit(s string) bool {
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

// knownCountry reports whether code is in countries.json. The list is
// internal/countries, read through Name, which returns the code unchanged when it is unknown.
func knownCountry(code string) bool {
	return code != "" && countries.Name(code, "en") != code
}

// roundTrip builds a UTC date and reports whether it is a real calendar date.
func roundTrip(y, m, d int) (time.Time, bool) {
	t := time.Date(y, time.Month(m), d, 0, 0, 0, 0, time.UTC)
	return t, t.Year() == y && int(t.Month()) == m && t.Day() == d
}

// ParseISODate is validation.parse_iso_date: the first ten characters as
// %Y-%m-%d, strptime-style (one-digit month and day allowed). ok is false
// where Python returns None.
func ParseISODate(s string) (time.Time, bool) {
	if s == "" {
		return time.Time{}, false
	}
	if pyLen(s) > 10 {
		s = string([]rune(s)[:10])
	}
	m := isoDateRE.FindStringSubmatch(s)
	if m == nil {
		return time.Time{}, false
	}
	y, _ := strconv.Atoi(m[1])
	mon, _ := strconv.Atoi(m[2])
	day, _ := strconv.Atoi(strings.TrimSpace(m[3]))
	if y < 1 {
		return time.Time{}, false
	}
	t, ok := roundTrip(y, mon, day)
	return t, ok
}

// stayDates is reporting._stay_dates: the guest's own date, else the reservation's.
func stayDates(g GuestRow, dateFrom, dateTo string) (from, to *time.Time) {
	if t, ok := ParseISODate(g.StayFrom); ok {
		from = &t
	} else if t, ok := ParseISODate(dateFrom); ok {
		from = &t
	}
	if t, ok := ParseISODate(g.StayTo); ok {
		to = &t
	} else if t, ok := ParseISODate(dateTo); ok {
		to = &t
	}
	return from, to
}

// parseBirthDate is validation.parse_birth_date on a DDMMYYYY string.
func parseBirthDate(s string) (time.Time, bool) {
	if len(s) != 8 {
		return time.Time{}, false
	}
	day, err1 := strconv.Atoi(s[0:2])
	month, err2 := strconv.Atoi(s[2:4])
	year, err3 := strconv.Atoi(s[4:8])
	if err1 != nil || err2 != nil || err3 != nil {
		return time.Time{}, false
	}
	if day == 0 || month == 0 || year == 0 {
		return time.Time{}, false
	}
	t, ok := roundTrip(year, month, day)
	return t, ok
}

// validateBirthDate is validation.validate_birth_date. today is Python date.today().
func validateBirthDate(s string, stayFrom *time.Time, today time.Time) []Issue {
	const field = "birth_date"
	if s == "" {
		return []Issue{{field, "Date of birth is required.", severityError}}
	}
	if len(s) != 8 || !isASCIIDigits(s) {
		return []Issue{{field, "Enter the full date as DD.MM.YYYY.", severityError}}
	}
	day, _ := strconv.Atoi(s[0:2])
	month, _ := strconv.Atoi(s[2:4])
	year, _ := strconv.Atoi(s[4:8])
	if year != 0 && year < 1900 {
		return []Issue{{field, "Year must be 1900 or later.", severityError}}
	}
	if month > 12 {
		return []Issue{{field, "Month must be between 01 and 12.", severityError}}
	}
	if day > 31 {
		return []Issue{{field, "Day must be between 01 and 31.", severityError}}
	}
	exact, ok := parseBirthDate(s)
	if day != 0 && month != 0 && year != 0 && !ok {
		return []Issue{{field, "That date does not exist - please check day and month.", severityError}}
	}
	if ok && stayFrom != nil && exact.After(*stayFrom) {
		return []Issue{{field, "Date of birth cannot be after your arrival date.", severityError}}
	}
	if ok && exact.After(today) {
		return []Issue{{field, "Date of birth cannot be in the future.", severityError}}
	}
	return nil
}

func isASCIIDigits(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return len(s) > 0
}

// validateResidence is validation.validate_residence.
func validateResidence(street, city, countryCode string) []Issue {
	var issues []Issue
	if street == "" {
		issues = append(issues, Issue{"res_street", "Street and number are required.", severityError})
	}
	if city == "" {
		issues = append(issues, Issue{"res_city", "City is required.", severityError})
	}
	if countryCode == "" {
		issues = append(issues, Issue{"res_country", "Country is required.", severityError})
	}
	for _, part := range []struct{ field, value, label string }{
		{"res_street", street, "Street"},
		{"res_city", city, "City"},
	} {
		if part.value == "" {
			continue
		}
		if pyLen(part.value) > maxResidencePart {
			issues = append(issues, Issue{part.field, fmt.Sprintf("%s must be at most %d characters.", part.label, maxResidencePart), severityError})
		}
		if pyIsDigit(part.value) {
			issues = append(issues, Issue{part.field, part.label + " cannot consist of digits only.", severityError})
		}
	}
	if countryCode != "" && !knownCountry(countryCode) {
		issues = append(issues, Issue{"res_country", "Unknown country code.", severityError})
	}
	return issues
}

// validateGuest is validation.validate_guest. raw is the untouched form input
// (nil on the reporting path, where it is never passed).
func validateGuest(g GuestRow, stayFrom, stayTo *time.Time, today time.Time, raw map[string]string) []Issue {
	var issues []Issue
	typed := func(field string) bool {
		return raw != nil && pyStrip(raw[field]) != ""
	}

	if g.Surname == "" {
		if typed("surname") {
			issues = append(issues, Issue{"surname", nonLatinMessage, severityError})
		} else {
			issues = append(issues, Issue{"surname", "Surname is required.", severityError})
		}
	} else if pyLen(g.Surname) > maxSurname {
		issues = append(issues, Issue{"surname", fmt.Sprintf("Surname must be at most %d characters.", maxSurname), severityError})
	}

	if g.FirstName == "" {
		if typed("first_name") {
			issues = append(issues, Issue{"first_name", nonLatinMessage, severityError})
		} else {
			issues = append(issues, Issue{"first_name", "Given name looks missing - please check the passport.", severityWarning})
		}
	} else if pyLen(g.FirstName) > maxFirstName {
		issues = append(issues, Issue{"first_name", fmt.Sprintf("Given name must be at most %d characters.", maxFirstName), severityError})
	}

	issues = append(issues, validateBirthDate(g.BirthDate, stayFrom, today)...)

	nationality := pyUpper(g.Nationality)
	if nationality == "" {
		issues = append(issues, Issue{"nationality", "Nationality is required.", severityError})
	} else if !knownCountry(nationality) {
		issues = append(issues, Issue{"nationality", fmt.Sprintf("'%s' is not a valid three-letter country code.", nationality), severityError})
	}

	doc := g.DocNumber
	note := g.Note
	if doc == "" {
		issues = append(issues, Issue{"doc_number", "Travel document number is required.", severityError})
	} else if doc == inpassDoc {
		if note == "" {
			issues = append(issues, Issue{"note", inpassNoteMessage, severityError})
		}
	} else if pyLen(doc) < minDoc {
		issues = append(issues, Issue{"doc_number", fmt.Sprintf("Document number must be at least %d characters.", minDoc), severityError})
	} else if pyLen(doc) > maxDoc {
		issues = append(issues, Issue{"doc_number", fmt.Sprintf("Document number must be at most %d characters.", maxDoc), severityError})
	}

	if g.VisaNumber != "" && pyLen(g.VisaNumber) > maxVisa {
		issues = append(issues, Issue{"visa_number", fmt.Sprintf("Visa number must be at most %d characters.", maxVisa), severityError})
	}

	issues = append(issues, validateResidence(g.ResStreet, g.ResCity, pyUpper(g.ResCountry))...)

	if g.Purpose == "" {
		issues = append(issues, Issue{"purpose", "Purpose of stay is required.", severityError})
	} else if !purposeCodes[g.Purpose] {
		issues = append(issues, Issue{"purpose", "Unknown purpose-of-stay code.", severityError})
	}

	for _, f := range []struct{ field, value string }{
		{"surname", g.Surname},
		{"first_name", g.FirstName},
		{"doc_number", g.DocNumber},
		{"visa_number", g.VisaNumber},
		{"res_street", g.ResStreet},
		{"res_city", g.ResCity},
		{"note", g.Note},
	} {
		if strings.ContainsAny(f.value, "\r\n|") {
			issues = append(issues, Issue{f.field, forbiddenCharMessage, severityError})
		}
	}

	if pyLen(note) > maxNote {
		issues = append(issues, Issue{"note", fmt.Sprintf("Note must be at most %d characters.", maxNote), severityError})
	}

	if stayFrom != nil && stayTo != nil && !stayTo.After(*stayFrom) {
		issues = append(issues, Issue{"stay_to", "Departure date must be later than the arrival date.", severityError})
	}
	return issues
}

// parseSignatureDataURL is validation.parse_signature_data_url. It returns the
// image bytes, or an error where Python raises ValueError.
func parseSignatureDataURL(value string) ([]byte, error) {
	m := sigDataURLRE.FindStringSubmatch(pyStrip(value))
	if m == nil {
		return nil, fmt.Errorf("signature")
	}
	magic, ok := sigMagic[m[1]]
	if !ok {
		return nil, fmt.Errorf("signature")
	}
	payload := m[2]
	if payload == "" || pyLen(payload) > maxSignaturePayloadChars {
		return nil, fmt.Errorf("signature")
	}
	content, err := base64.StdEncoding.DecodeString(payload)
	if err != nil {
		return nil, fmt.Errorf("signature")
	}
	if len(content) == 0 || len(content) > maxSignatureBytes {
		return nil, fmt.Errorf("signature")
	}
	if !bytes.HasPrefix(content, magic) {
		return nil, fmt.Errorf("signature")
	}
	cfg, _, err := image.DecodeConfig(bytes.NewReader(content))
	if err != nil {
		return nil, fmt.Errorf("signature")
	}
	if cfg.Width > maxSignatureSide || cfg.Height > maxSignatureSide ||
		cfg.Width*cfg.Height > maxSignaturePixels {
		return nil, fmt.Errorf("signature")
	}
	return content, nil
}

// guestSignatureIssue is reporting.guest_signature_issue with translate=None
// and allow_imported=True.
func guestSignatureIssue(value string) *Issue {
	text := pyStrip(value)
	if text == importedSignature {
		return nil
	}
	if text == "" {
		return &Issue{"signature", hostSignatureRequiredMsg, severityError}
	}
	if _, err := parseSignatureDataURL(value); err != nil {
		return &Issue{"signature", signatureInvalidMessage, severityError}
	}
	return nil
}

// GuestIssues is reporting.guest_issues: every reason the stored guest would
// be refused. dateFrom and dateTo are the reservation dates; today is the
// clock (Python date.today()).
func GuestIssues(g GuestRow, dateFrom, dateTo string, today time.Time) []Issue {
	from, to := stayDates(g, dateFrom, dateTo)
	issues := validateGuest(g, from, to, today, nil)
	if sig := guestSignatureIssue(g.SignaturePNG); sig != nil {
		issues = append(issues, *sig)
	}
	return issues
}

// GuestIsComplete is reporting.guest_is_complete: no error-severity issue.
func GuestIsComplete(g GuestRow, dateFrom, dateTo string, today time.Time) bool {
	return len(ErrorsOnly(GuestIssues(g, dateFrom, dateTo, today))) == 0
}

// GuestIsReportable is validation.guest_is_reportable: non-Czech nationals.
func GuestIsReportable(nationality string) bool {
	return nationality != "" && pyUpper(nationality) != czechCode
}

// ErrorsOnly is validation.errors_only.
func ErrorsOnly(issues []Issue) []Issue {
	var out []Issue
	for _, i := range issues {
		if i.Severity == severityError {
			out = append(out, i)
		}
	}
	return out
}

// digitsOnly keeps the Nd characters, as validation.normalise_zip does.
func digitsOnly(s string) string {
	var b strings.Builder
	for _, r := range s {
		if unicode.IsDigit(r) {
			b.WriteRune(r)
		}
	}
	return b.String()
}

// ValidateApartment is validation.validate_apartment. Values are the stored
// strings; a missing key is an empty value.
func ValidateApartment(ap map[string]string) []Issue {
	var issues []Issue
	get := func(k string) string { return pyStrip(ap[k]) }

	idub := get("uby_idub")
	if idub == "" {
		issues = append(issues, Issue{"uby_idub", "IDUB is required before anything can be reported.", severityError})
	} else if !idubRE.MatchString(idub) {
		issues = append(issues, Issue{"uby_idub", "IDUB must be 12-14 letters or digits.", severityError})
	}

	mark := get("uby_mark")
	if mark == "" {
		issues = append(issues, Issue{"uby_mark", "The facility abbreviation (zkratka) is required.", severityError})
	} else if !markRE.MatchString(mark) {
		issues = append(issues, Issue{"uby_mark", "The abbreviation is the 5 or 6 letters or digits the police assigned, e.g. AAKLI.", severityError})
	}

	name := get("uby_name")
	if name == "" {
		issues = append(issues, Issue{"uby_name", "Accommodation facility name is required.", severityError})
	} else if pyLen(name) > 35 {
		issues = append(issues, Issue{"uby_name", "Facility name must be at most 35 characters.", severityError})
	}

	for _, lim := range []struct {
		field string
		limit int
	}{
		{"uby_name", 35},
		{"uby_contact", 50},
		{"addr_okres", 32},
		{"addr_obec", 48},
		{"addr_obec_cast", 48},
		{"addr_street", 48},
	} {
		if pyLen(get(lim.field)) > lim.limit {
			issues = append(issues, Issue{lim.field, fmt.Sprintf("Must be at most %d characters.", lim.limit), severityError})
		}
	}

	house := get("addr_house_no")
	if house == "" {
		issues = append(issues, Issue{"addr_house_no", "House number is required.", severityError})
	} else if !houseRE.MatchString(house) {
		issues = append(issues, Issue{"addr_house_no", "House number is up to 4 digits, optionally with E for an evidence number.", severityError})
	}

	orient := get("addr_orient_no")
	if orient != "" && !orientRE.MatchString(orient) {
		issues = append(issues, Issue{"addr_orient_no", "Orientation number is up to 3 digits plus one optional letter.", severityError})
	}

	zipcode := digitsOnly(ap["addr_zip"])
	if zipcode == "" {
		issues = append(issues, Issue{"addr_zip", "Postcode is required.", severityError})
	} else if pyLen(zipcode) != 5 {
		issues = append(issues, Issue{"addr_zip", "Postcode must be exactly 5 digits.", severityError})
	}

	if get("addr_obec") == "" {
		issues = append(issues, Issue{"addr_obec", "Municipality is required.", severityError})
	}

	user := get("uby_ws_user")
	if user == "" {
		issues = append(issues, Issue{"uby_ws_user", "UbyPort web-service login is required for automatic reporting.", severityError})
	} else if !wsUserRE.MatchString(user) {
		issues = append(issues, Issue{"uby_ws_user", webServiceLoginWarningText, severityWarning})
	}

	if ap["uby_ws_password"] == "" {
		issues = append(issues, Issue{"uby_ws_password", "UbyPort web-service password is required.", severityError})
	}

	if ap["legal_entity_id"] == "" {
		message := noPropertyManagerMessage
		if ap["data_controller_entity_id"] == "" {
			message += noControllerMessage
		}
		issues = append(issues, Issue{"legal_entity_id", message, severityWarning})
	}
	return issues
}
