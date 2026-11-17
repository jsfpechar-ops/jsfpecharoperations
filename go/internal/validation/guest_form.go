package validation

// Guest form normalisation and the stay-date checks, ported from
// App/app/validation.py (normalise_guest with clamp=False and its helpers,
// note_for_parent_document, validate_stay_dates, validate_stay_date_text) and
// the guest-path signature check of App/app/reporting.py
// (guest_signature_issue with allow_imported=False and the English catalog).
// Brief 1835. go/internal/guestcontract/testdata/guest_form_golden.json,
// written by App/scripts/guest_form_golden.py from the real Python, pins it.
//
// Known differences, outside the golden cases: Python str.upper() also expands
// ligatures and a few other letters (pyUpper here handles only ß, like
// ubyport.pyUpper); the Unicode tables of Go and Python may differ for letters
// added in newer Unicode versions.

import (
	"strings"
	"time"
	"unicode"

	"golang.org/x/text/unicode/norm"
)

const (
	inpassNotePrefix             = "Dítě zapsané v pasu rodiče, číslo dokladu rodiče: "
	defaultPurpose               = "99"
	stayOutsideBookingMessage    = "These dates do not match your booking. Reload this page, or ask your host."
	stayDateUnreadableMessage    = "The stay dates on this page are not readable. Reload the page and try again."
	guestSignatureMissingMessage = "Please sign in the box before you continue."
	nameLetters                  = "abcdefghijklmnopqrstuvwxyz" +
		"ABCDEFGHIJKLMNOPQRSTUVWXYZ" +
		"ĄŁĽŚŠŞŤŹŽŻąłľśšşťźžżŔÁÂĂÄĹĆÇČÉĘËĚÍÎĎĐŃŇÓÔŐÖŘŮÚŰÜÝŢ" +
		"ŕáâăäĺćçčéęëěíîďđńňóôőöřůúűüýţß"
)

// GuestTextFields is validation.GUEST_TEXT_FIELDS, in order.
var GuestTextFields = []string{
	"surname", "first_name", "birth_date", "nationality", "doc_number", "visa_number",
	"res_street", "res_city", "res_country", "purpose", "note",
}

var (
	nameAllowed      = runeSet(nameLetters + " '-")
	residenceAllowed = runeSet(nameLetters + " '-" + "0123456789/.,;:()&#@")
	docAllowed       = runeSet("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
	// mrzFold is validation._MRZ_FOLD.
	mrzFold = map[rune]string{
		'Đ': "D", 'đ': "d", 'Ð': "D", 'ð': "d",
		'Ø': "O", 'ø': "o", 'Œ': "OE", 'œ': "oe",
		'Æ': "AE", 'æ': "ae", 'Þ': "TH", 'þ': "th",
		'İ': "I", 'ı': "i", 'Ħ': "H", 'ħ': "h",
		'Ŧ': "T", 'ŧ': "t", 'Ə': "E", 'ə': "e",
		'Ŀ': "L", 'ŀ': "l", 'Ŋ': "N", 'ŋ': "n",
		'Ƶ': "Z", 'ƶ': "z", 'Ɖ': "D", 'ɖ': "d",
	}
)

func runeSet(s string) map[rune]bool {
	m := make(map[rune]bool)
	for _, r := range s {
		m[r] = true
	}
	return m
}

// isPySpace is Python str.isspace() for one character (the pyStrip rule).
func isPySpace(r rune) bool {
	return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f)
}

// Strip is Python str.strip() with no arguments.
func Strip(s string) string { return pyStrip(s) }

// firstRunes is Python s[:n] on a str.
func firstRunes(s string, n int) string {
	i := 0
	for pos := range s {
		if i == n {
			return s[:pos]
		}
		i++
	}
	return s
}

// stripForbidden is validation.strip_forbidden.
func stripForbidden(v string) string {
	return strings.Map(func(r rune) rune {
		switch {
		case r == '\r' || r == '\n' || r == '|':
			return ' '
		case r <= 0x08 || r == 0x0b || r == 0x0c || (r >= 0x0e && r <= 0x1f) || r == 0x7f:
			return ' '
		}
		return r
	}, v)
}

// collapseSpaces is validation.collapse_spaces: re.sub(r"\s+", " ", v).strip().
func collapseSpaces(v string) string {
	return strings.Join(strings.FieldsFunc(v, isPySpace), " ")
}

// foldToAllowed is validation.fold_to_allowed.
func foldToAllowed(text string, allowed map[rune]bool) string {
	var b strings.Builder
	for _, ch := range text {
		if allowed[ch] {
			b.WriteRune(ch)
			continue
		}
		mapped, ok := mrzFold[ch]
		if !ok {
			var m strings.Builder
			for _, c := range norm.NFKD.String(string(ch)) {
				if norm.NFKD.PropertiesString(string(c)).CCC() == 0 {
					m.WriteRune(c)
				}
			}
			mapped = m.String()
		}
		for _, c := range mapped {
			if allowed[c] {
				b.WriteRune(c)
			}
		}
	}
	return b.String()
}

func normaliseName(v string) string {
	text := pyUpper(collapseSpaces(stripForbidden(v)))
	return collapseSpaces(foldToAllowed(text, nameAllowed))
}

func normaliseResidencePart(v string) string {
	text := collapseSpaces(stripForbidden(v))
	text = strings.Map(func(r rune) rune {
		if (r >= 0x2010 && r <= 0x2015) || r == 0x2212 {
			return '-'
		}
		return r
	}, text)
	return collapseSpaces(foldToAllowed(text, residenceAllowed))
}

func normaliseDocument(v string) string {
	return foldToAllowed(pyUpper(stripForbidden(v)), docAllowed)
}

func normaliseNote(v string) string {
	return firstRunes(collapseSpaces(stripForbidden(v)), maxNote)
}

// decimalValue is unicodedata.decimal for a character in category Nd. Decimal
// digits are encoded in runs that start at zero, so the value is the distance
// from the start of the run, modulo 10.
func decimalValue(r rune) (int, bool) {
	if !unicode.Is(unicode.Nd, r) {
		return 0, false
	}
	start := r
	for start > 0 && unicode.Is(unicode.Nd, start-1) {
		start--
	}
	return int(r-start) % 10, true
}

// asciiDecimals is validation._ascii_decimals.
func asciiDecimals(v, keep string) string {
	var b strings.Builder
	for _, ch := range v {
		switch {
		case strings.ContainsRune(keep, ch):
			b.WriteRune(ch)
		case ch >= '0' && ch <= '9':
			b.WriteRune(ch)
		default:
			if d, ok := decimalValue(ch); ok {
				b.WriteByte(byte('0' + d))
			}
		}
	}
	return b.String()
}

// expandTwoDigitYear is validation._expand_two_digit_year with today injected.
func expandTwoDigitYear(two string, today time.Time) string {
	n := 0
	for _, c := range two {
		n = n*10 + int(c-'0')
	}
	current := today.Year()
	a, b := 1900+n, 2000+n
	best := 0
	for _, c := range []int{a, b} {
		if c <= current && c > best {
			best = c
		}
	}
	if best == 0 {
		best = a
	}
	return itoa(best)
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var d []byte
	for n > 0 {
		d = append([]byte{byte('0' + n%10)}, d...)
		n /= 10
	}
	return string(d)
}

// pad2 is f"{int(s):02d}" for a string of ASCII digits of any length.
func pad2(s string) string {
	t := strings.TrimLeft(s, "0")
	if t == "" {
		t = "0"
	}
	for len(t) < 2 {
		t = "0" + t
	}
	return t
}

// zfill4 is str.zfill(4) for a string of ASCII digits.
func zfill4(s string) string {
	for len(s) < 4 {
		s = "0" + s
	}
	return s
}

// normaliseBirthDate is validation.normalise_birth_date with today injected.
func normaliseBirthDate(v string, today time.Time) string {
	raw := pyStrip(stripForbidden(v))
	if raw == "" {
		return ""
	}
	separated := strings.NewReplacer("/", ".", "-", ".").Replace(raw)
	digitsAndDots := asciiDecimals(separated, ".")
	if strings.Contains(digitsAndDots, ".") {
		var parts []string
		for _, p := range strings.Split(digitsAndDots, ".") {
			if p != "" {
				parts = append(parts, p)
			}
		}
		if len(parts) == 3 {
			day, month, year := parts[0], parts[1], parts[2]
			if len(year) == 2 {
				year = expandTwoDigitYear(year, today)
			}
			return pad2(day) + pad2(month) + zfill4(year)
		}
	}
	digits := asciiDecimals(raw, "")
	if len(digits) == 8 {
		return digits
	}
	if len(digits) == 6 {
		return digits[:4] + expandTwoDigitYear(digits[4:], today)
	}
	return digits
}

// NormaliseGuest is validation.normalise_guest(raw, clamp=False). raw holds the
// GuestTextFields as GuestFormRaw builds them. today is the clock of
// _expand_two_digit_year. Stay dates and signature stay empty.
func NormaliseGuest(raw map[string]string, today time.Time) GuestRow {
	return GuestRow{
		Surname:     normaliseName(raw["surname"]),
		FirstName:   normaliseName(raw["first_name"]),
		BirthDate:   normaliseBirthDate(raw["birth_date"], today),
		Nationality: firstRunes(pyUpper(pyStrip(raw["nationality"])), 3),
		DocNumber:   normaliseDocument(raw["doc_number"]),
		VisaNumber:  normaliseDocument(raw["visa_number"]),
		ResStreet:   normaliseResidencePart(raw["res_street"]),
		ResCity:     normaliseResidencePart(raw["res_city"]),
		ResCountry:  firstRunes(pyUpper(pyStrip(raw["res_country"])), 3),
		Purpose:     firstRunes(pyStrip(raw["purpose"]), 2),
		Note:        normaliseNote(raw["note"]),
	}
}

// NoteForParentDocument is validation.note_for_parent_document.
func NoteForParentDocument(parentDocument, note string) string {
	parent := normaliseDocument(parentDocument)
	if parent == "" {
		return note
	}
	text := inpassNotePrefix + parent
	if note != "" {
		text += " " + note
	}
	return firstRunes(text, maxNote)
}

// GuestFormRaw is admin_helpers.guest_form_raw for the guest link: form holds
// the posted values by field name (missing means empty), defaultPurpose is the
// apartment's default_purpose column.
func GuestFormRaw(form map[string]string, defaultPurposeOfApartment string) map[string]string {
	raw := make(map[string]string, len(GuestTextFields))
	for _, f := range GuestTextFields {
		raw[f] = pyStrip(form[f])
	}
	if raw["purpose"] == "" {
		if defaultPurposeOfApartment != "" {
			raw["purpose"] = defaultPurposeOfApartment
		} else {
			raw["purpose"] = defaultPurpose
		}
	}
	if raw["doc_number"] == inpassDoc {
		raw["note"] = NoteForParentDocument(pyStrip(form["parent_doc_number"]), raw["note"])
	}
	return raw
}

// ValidateGuestForm is validation.validate_guest(values, stay_from, stay_to, raw=raw).
func ValidateGuestForm(g GuestRow, stayFrom, stayTo *time.Time, today time.Time, raw map[string]string) []Issue {
	return validateGuest(g, stayFrom, stayTo, today, raw)
}

// CertainlyUnderAge is validation.certainly_under_age; a nil date is false.
func CertainlyUnderAge(birth string, when *time.Time, years int) bool {
	if when == nil {
		return false
	}
	return certainlyUnderAge(birth, *when, years)
}

// ValidateStayDates is validation.validate_stay_dates (tolerance 0 days).
func ValidateStayDates(stayFrom, stayTo, allowedFrom, allowedTo *time.Time) []Issue {
	var issues []Issue
	if stayFrom != nil && allowedFrom != nil && stayFrom.Before(*allowedFrom) {
		issues = append(issues, Issue{"stay_from", stayOutsideBookingMessage, severityError})
	}
	if stayTo != nil && allowedTo != nil && stayTo.After(*allowedTo) {
		issues = append(issues, Issue{"stay_to", stayOutsideBookingMessage, severityError})
	}
	return issues
}

// ValidateStayDateText is validation.validate_stay_date_text.
func ValidateStayDateText(stayFrom, stayTo string) []Issue {
	var issues []Issue
	for _, p := range [][2]string{{"stay_from", stayFrom}, {"stay_to", stayTo}} {
		if p[1] == "" {
			continue
		}
		if _, ok := ParseISODate(p[1]); !ok {
			issues = append(issues, Issue{p[0], stayDateUnreadableMessage, severityError})
		}
	}
	return issues
}

// GuestFormSignatureIssue is reporting.guest_signature_issue(value,
// translate=English catalog, allow_imported=False, under_15=under15).
func GuestFormSignatureIssue(value string, under15 bool) *Issue {
	text := pyStrip(value)
	if under15 && text == "" {
		return nil
	}
	if text == importedSignature || text == "" {
		return &Issue{"signature", guestSignatureMissingMessage, severityError}
	}
	if _, err := parseSignatureDataURL(value); err != nil {
		return &Issue{"signature", signatureInvalidMessage, severityError}
	}
	return nil
}
