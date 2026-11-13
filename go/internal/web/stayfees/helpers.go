package stayfees

// Pure helpers the stay-fee routes need. Each one is a copy of a Python
// function and names it; go/internal/stayfee is built by another thread, so
// these stay unexported until it lands.

import (
	"strconv"
	"strings"
	"time"

	"golang.org/x/text/cases"
	"golang.org/x/text/unicode/norm"
)

// copy of App/app/stay_fee.py DECISIONS; replace with go/internal/stayfee when it lands.
var decisions = []string{"exempt", "charge"}

// copy of App/app/stay_fee.py REASON_MAX; replace with go/internal/stayfee when it lands.
const reasonMax = 120

// copy of App/app/stay_fee.py EXEMPT_CATEGORIES; replace with go/internal/stayfee when it lands.
var exemptCategories = []string{"disability", "diplomat", "local_rule", "other_statutory"}

// copy of App/app/stay_fee.py SCOPE_RULES; replace with go/internal/stayfee when it lands.
var scopeRules = []string{"calendar_days", "nights"}

// referenceMax is the [:200] the decision and scope routes cut a reference to.
const referenceMax = 200

// copy of App/app/routes/stay_fees.py FEE_COPY_FIELDS; replace with go/internal/stayfee when it lands.
var feeCopyFields = []string{
	"stay_fee_rate_czk", "stay_fee_cadence", "stay_fee_vs",
	"stay_fee_council_account", "stay_fee_council_iban",
	"stay_fee_authority_name", "stay_fee_authority_address",
	"stay_fee_authority_contact", "stay_fee_authority_databox",
	"stay_fee_payee", "stay_fee_instruction",
	"stay_fee_scope_rule", "stay_fee_scope_reference",
}

func contains(list []string, v string) bool {
	for _, item := range list {
		if item == v {
			return true
		}
	}
	return false
}

// truncRunes is Python's s[:n]: the first n characters.
func truncRunes(s string, n int) string {
	if r := []rune(s); len(r) > n {
		return string(r[:n])
	}
	return s
}

// copy of App/app/stay_fee.py parse_month; replace with go/internal/stayfee when it lands.
// Only ASCII digits count: Python's isdigit also accepts other scripts' digits.
func parseMonth(value string) (time.Time, bool) {
	text := strings.TrimSpace(value)
	if len(text) != 7 || text[4] != '-' {
		return time.Time{}, false
	}
	digits := text[:4] + text[5:]
	for i := 0; i < len(digits); i++ {
		if digits[i] < '0' || digits[i] > '9' {
			return time.Time{}, false
		}
	}
	year := int(digits[0]-'0')*1000 + int(digits[1]-'0')*100 + int(digits[2]-'0')*10 + int(digits[3]-'0')
	month := int(digits[4]-'0')*10 + int(digits[5]-'0')
	if month < 1 || month > 12 || year < 2000 {
		return time.Time{}, false
	}
	return monthStart(year, month), true
}

func monthStart(year, month int) time.Time {
	return time.Date(year, time.Month(month), 1, 0, 0, 0, 0, time.UTC)
}

// copy of App/app/stay_fee.py month_key; replace with go/internal/stayfee when it lands.
func monthKey(day time.Time) string {
	return day.Format("2006-01")
}

// copy of App/app/stay_fee.py shift_month; replace with go/internal/stayfee when it lands.
func shiftMonth(month time.Time, delta int) time.Time {
	index := month.Year()*12 + int(month.Month()) - 1 + delta
	return monthStart(index/12, index%12+1)
}

// copy of App/app/stay_fee.py period_bounds; replace with go/internal/stayfee when it lands.
func periodBounds(cadence string, month time.Time) (time.Time, time.Time) {
	var first, after time.Time
	if cadence == "quarterly" {
		first = monthStart(month.Year(), (int(month.Month())-1)/3*3+1)
		after = shiftMonth(first, 3)
	} else {
		first = monthStart(month.Year(), int(month.Month()))
		after = shiftMonth(first, 1)
	}
	return first, after.AddDate(0, 0, -1)
}

// copy of App/app/stay_fee_filing.py period_key; replace with go/internal/stayfee when it lands.
func periodKey(cadence string, month time.Time) string {
	if cadence == "quarterly" {
		return month.Format("2006") + "-Q" + string(rune('0'+(int(month.Month())-1)/3+1))
	}
	return monthKey(month)
}

// copy of App/app/stay_fee_filing.py overlap_keys; replace with go/internal/stayfee when it lands.
func overlapKeys(cadence string, month time.Time) []string {
	if cadence == "quarterly" {
		first, _ := periodBounds("quarterly", month)
		keys := []string{periodKey("quarterly", first)}
		for offset := 0; offset < 3; offset++ {
			keys = append(keys, monthKey(shiftMonth(first, offset)))
		}
		return keys
	}
	return []string{periodKey("monthly", month), periodKey("quarterly", month)}
}

// copy of App/app/stay_fee.py is_active; replace with go/internal/stayfee when it lands.
// rate is the apartment's stay_fee_rate_czk.
func isActive(rate int64) bool {
	return rate > 0
}

// copy of App/app/routes/stay_fees.py _default_month; replace with go/internal/stayfee when it lands.
func defaultMonth(today time.Time) time.Time {
	return monthStart(today.Year(), int(today.Month()))
}

// foldPlace is _fold_place in App/app/routes/stay_fees.py: strip, NFKD, drop
// combining marks, casefold. Copy; replace with go/internal/stayfee when it lands.
func foldPlace(value string) string {
	plain := norm.NFKD.String(strings.TrimSpace(value))
	var b strings.Builder
	for _, r := range plain {
		if norm.NFD.PropertiesString(string(r)).CCC() != 0 {
			continue
		}
		b.WriteRune(r)
	}
	return cases.Fold().String(b.String())
}

// apartment is the part of an apartment row the routes read.
type apartment struct {
	ID       int64
	Name     string
	Obec     string
	Archived bool
	Rate     int64
}

// copy of App/app/routes/stay_fees.py fee_copy_source for one candidate: true
// when candidate is an active fee in the same municipality as target, and not
// target itself. Replace with go/internal/stayfee when it lands.
func feeCopySource(target, candidate apartment) bool {
	place := foldPlace(target.Obec)
	if place == "" {
		return false
	}
	return candidate.ID != target.ID && isActive(candidate.Rate) && foldPlace(candidate.Obec) == place
}

// copy of App/app/routes/stay_fees.py fee_return_path; replace with go/internal/stayfee when it lands.
func feeReturnPath(raw string, apartmentID int64) string {
	if raw == "" {
		return ""
	}
	path := safeLocalPath(raw, "")
	if path == "" {
		return ""
	}
	base, _, _ := strings.Cut(path, "?")
	if base == "/stay-fees" || base == "/stay-fees/"+strconv.FormatInt(apartmentID, 10) {
		return path
	}
	return ""
}

// safeLocalPath is App/app/security.py safe_local_path: a normalised same-site
// path with its query, or def. Copy; it has no Go twin yet.
func safeLocalPath(value, def string) string {
	raw := strings.TrimSpace(value)
	if raw == "" || strings.Contains(raw, "\\") {
		return def
	}
	for i := 0; i < len(raw); i++ {
		if raw[i] < 0x20 {
			return def
		}
	}
	rest := raw
	// urlsplit: a scheme is letters first, then letters, digits and "+-." up to ":".
	if i := strings.IndexByte(rest, ':'); i > 0 && isLetter(rest[0]) {
		scheme := true
		for j := 0; j < i; j++ {
			c := rest[j]
			if !isLetter(c) && !(c >= '0' && c <= '9') && c != '+' && c != '-' && c != '.' {
				scheme = false
				break
			}
		}
		if scheme {
			return def
		}
	}
	if strings.HasPrefix(rest, "//") {
		end := strings.IndexAny(rest[2:], "/?#")
		if end < 0 {
			end = len(rest) - 2
		}
		if end > 0 {
			return def
		}
		rest = rest[2+end:]
	}
	rest, _, _ = strings.Cut(rest, "#")
	path, query, _ := strings.Cut(rest, "?")
	if !strings.HasPrefix(path, "/") || strings.HasPrefix(path, "//") {
		return def
	}
	decoded := percentDecode(path)
	if strings.HasPrefix(decoded, "//") || strings.Contains(decoded, "\\") {
		return def
	}
	for i := 0; i < len(decoded); i++ {
		if decoded[i] < 0x20 {
			return def
		}
	}
	clean := posixNormpath(path)
	if !strings.HasPrefix(clean, "/") || strings.HasPrefix(clean, "//") {
		return def
	}
	if query != "" {
		return clean + "?" + query
	}
	return clean
}

func isLetter(c byte) bool {
	return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')
}

// percentDecode is urllib.parse.unquote: valid %XX pairs become bytes, the rest stays.
func percentDecode(s string) string {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		if s[i] == '%' && i+2 < len(s) && hexVal(s[i+1]) >= 0 && hexVal(s[i+2]) >= 0 {
			b.WriteByte(byte(hexVal(s[i+1])<<4 | hexVal(s[i+2])))
			i += 2
			continue
		}
		b.WriteByte(s[i])
	}
	return b.String()
}

func hexVal(c byte) int {
	switch {
	case c >= '0' && c <= '9':
		return int(c - '0')
	case c >= 'a' && c <= 'f':
		return int(c-'a') + 10
	case c >= 'A' && c <= 'F':
		return int(c-'A') + 10
	}
	return -1
}

// posixNormpath is posixpath.normpath for a path that starts with one "/".
func posixNormpath(path string) string {
	var out []string
	for _, part := range strings.Split(path, "/") {
		switch part {
		case "", ".":
		case "..":
			if len(out) > 0 {
				out = out[:len(out)-1]
			}
		default:
			out = append(out, part)
		}
	}
	return "/" + strings.Join(out, "/")
}

// pragueDay is claim.prague_today for the instant at: the civil date in
// Europe/Prague, as a UTC midnight so it compares with monthStart values.
func pragueDay(at time.Time) time.Time {
	local := at.In(prague)
	return time.Date(local.Year(), local.Month(), local.Day(), 0, 0, 0, 0, time.UTC)
}

// stamp is db.utcnow: seconds, UTC, "+00:00".
func stamp(at time.Time) string {
	return at.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}
