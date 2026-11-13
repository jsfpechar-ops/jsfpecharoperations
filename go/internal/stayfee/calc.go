// Package stayfee is the Go port of the stay-fee calculation in
// App/app/stay_fee.py, stay_fee_rate.py, stay_fee_adjustment.py and the read
// side of stay_fee_filing.py (brief 1240). It reproduces, from database rows,
// everything stay_fee_auto.check and stay_fee_filing.save need except the PDF.
//
// The package is split in two layers. The pure layer (this file, report.go and
// the key functions of filing.go) takes plain structs and does no I/O. The thin
// loader (loader.go and the Load* functions of filing.go) reads rows through a
// Querier (a *pgxpool.Pool or a pgx.Tx) and decrypts guest fields through a
// Decrypter; nothing runs at package init and no constructor touches the
// database. testdata/stay_fee_golden.json, written by App/scripts/stay_fee_golden.py
// from the real Python, pins both layers.
//
// Known differences, all outside the golden cases: Python's str.isdigit() also
// accepts digits outside 0-9 (superscripts, full-width) where this port is
// ASCII-only (ParseMonth, ParseCZKInt, VSOf, birth-date digits); str.upper()
// special cases other than the German sharp s are not ported; the combining
// mark test uses the canonical combining class like unicodedata.combining but
// \s in the municipality folding is ASCII after the whitespace collapse.
// Python's schedule_for defaults "today" to date.today() (the server's local
// date); here the caller passes it (ScheduleToday).
package stayfee

import (
	"fmt"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode"

	"golang.org/x/text/unicode/norm"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// Constants of stay_fee.py. Decisions, ExemptCategories, ScopeRules and
// Cadences are read-only: do not modify them.
// nbsp and bom are built from code points so no invisible character sits in the source.
var (
	nbsp = string(rune(0xA0))
	bom  = string(rune(0xFEFF))
)

const (
	MaxRateCZK      = 50 // §3d
	AdultAge        = 18 // §3b(1)(b)
	ReasonMax       = 120
	ThresholdNights = 60
	czechCode       = "CZE"
)

var (
	Cadences         = []string{"monthly", "quarterly"}
	Decisions        = []string{"exempt", "charge"}
	ExemptCategories = []string{"disability", "diplomat", "local_rule", "other_statutory"}
	ScopeRules       = []string{"calendar_days", "nights"}
	MonthsCS         = []string{"Leden", "Únor", "Březen", "Duben", "Květen", "Červen", "Červenec",
		"Srpen", "Září", "Říjen", "Listopad", "Prosinec"}
	// DocTypes is validation.DOC_TYPES.
	DocTypes = []string{"op", "pas", "prechodny_pobyt", "pobytova_karta_eu", "povoleni_pobyt",
		"povoleni_pobyt_cizinec", "trvaly_pobyt", "zadatel_mezinarodni_ochrana", "zadatel_docasna_ochrana"}
	DocTypeLabelsCS = map[string]string{
		"op":                          "Občanský průkaz",
		"pas":                         "Cestovní pas",
		"prechodny_pobyt":             "Potvrzení o přechodném pobytu",
		"pobytova_karta_eu":           "Pobytová karta rodinného příslušníka občana EU",
		"povoleni_pobyt":              "Průkaz o povolení k pobytu",
		"povoleni_pobyt_cizinec":      "Průkaz o povolení k pobytu pro cizince",
		"trvaly_pobyt":                "Průkaz o povolení k trvalému pobytu",
		"zadatel_mezinarodni_ochrana": "Průkaz žadatele o mezinárodní ochranu",
		"zadatel_docasna_ochrana":     "Průkaz žadatele o dočasnou ochranu",
	}
)

func inList(list []string, v string) bool {
	for _, item := range list {
		if item == v {
			return true
		}
	}
	return false
}

// Apartment holds the apartment columns the stay-fee code reads. An empty
// string stands for SQL NULL, as everywhere in the Go ports.
type Apartment struct {
	ID               int64
	LegalEntityID    int64 // 0 = none
	InternalName     string
	StayFeeRateCZK   int
	StayFeeCadence   string
	StayFeeVS        string
	AuthorityName    string
	AuthorityAddress string
	AuthorityContact string
	Payee            string
	Instruction      string
	CouncilAccount   string
	CouncilIBAN      string
	ScopeRule        string
	ScopeReference   string
	Collect          bool
	GuestRails       string
	GuestDefaultRail string
	RevolutLink      string
	CashNote         string
	AddrObec         string
	CityEN           string
	AddrStreet       string
	AddrHouseNo      string
	AddrOrientNo     string
	AddrZip          string
	ArchivedAt       string
}

// Entity is a legal_entity row (the payer). SignaturePNG is already decrypted.
type Entity struct {
	ID            int64
	Name          string
	Seat          string
	ICO           string
	ContactEmail  string
	IBAN          string
	BankAccount   string
	SignaturePNG  string
	SignatureName string
}

// GuestRow is one guest joined to its reservation, every field already
// decrypted (db.decrypt_field with the plaintext column as the fallback).
type GuestRow struct {
	ID              int64
	ReservationID   int64
	Surname         string
	FirstName       string
	BirthDate       string
	Nationality     string
	DocType         string
	DocNumber       string
	ResStreet       string
	ResCity         string
	ResCountry      string
	StayFrom        string
	StayTo          string
	FeeHostDecision string
	FeeHostReason   string
	SignaturePNG    string
	Restricted      bool
	ResFrom         string // reservation.date_from
	ResTo           string // reservation.date_to
}

// RateRow is a stay_fee_rate row.
type RateRow struct {
	EffectiveFrom string
	RateCZK       int
}

// RateStep is one entry of a rate schedule: the rate from a day on.
type RateStep struct {
	From time.Time
	Rate int
}

// Adjustment is an open stay_fee_adjustment row with its signed delta and
// decrypted reason.
type Adjustment struct {
	ID        int64  `json:"id"`
	Direction string `json:"direction"`
	Mode      string `json:"mode"`
	BedDays   int    `json:"bed_days"`
	Delta     int    `json:"delta"`
	Reason    string `json:"reason"`
}

// Line is one guest's share of one period (guest_period plus the extra keys
// property_period adds). The JSON tags are the Python dict keys, so a sealed
// payload decodes straight into it.
type Line struct {
	GuestID          int64    `json:"guest_id"`
	StayFrom         string   `json:"stay_from"`
	StayTo           string   `json:"stay_to"`
	Nights           int      `json:"nights"`
	LiableNights     int      `json:"liable_nights"`
	ExemptNights     int      `json:"exempt_nights"`
	Status           string   `json:"status"`
	AutoMinor        bool     `json:"auto_minor"`
	Decision         *string  `json:"decision"`
	Reason           string   `json:"reason"`
	ThresholdNights  bool     `json:"threshold_nights"`
	AmountCZK        int      `json:"amount_czk"`
	RateNights       [][2]int `json:"rate_nights"`
	AutoObecResident bool     `json:"auto_obec_resident"`
	ReservationID    int64    `json:"reservation_id"`
	Name             string   `json:"name"`
	Restricted       bool     `json:"restricted"`
	ResCountry       string   `json:"res_country"`
	ResCity          string   `json:"res_city"`
}

// Period is property_period's dict: the figures for one property and period.
// A frozen period (Frozen true) is a sealed filing; the fields that only a
// live period has (GuestLiableNights, AdjustmentBedDays, Adjustments,
// UnsignedGuests) are then zero.
type Period struct {
	Apartment         *Apartment
	Cadence           string
	First, Last       time.Time
	Label             string
	RateCZK           int
	Lines             []Line
	GuestLiableNights int
	LiableNights      int
	ExemptNights      int
	TotalCZK          int
	AdjustmentBedDays int
	Adjustments       []Adjustment
	UnsignedGuests    int
	RateSegments      [][2]int
	PeriodKey         string

	Frozen            bool
	FilingID          int64
	Version           int
	TotalCollectedCZK int
	SentAt            string
	PaidAt            string
	SentMessageID     string
}

// PeriodInput is everything BuildPeriod needs from the database for one
// apartment and period. Guests are in the order of the SQL (stay start, id);
// Adjustments are the open rows for PeriodKey(cadence, month).
type PeriodInput struct {
	RateRows      []RateRow
	ScheduleToday time.Time
	Guests        []GuestRow
	Adjustments   []Adjustment
}

// --- dates -------------------------------------------------------------------

// Day is a calendar day as a UTC midnight time.Time, the only form the package uses.
func Day(y int, m time.Month, d int) time.Time {
	return time.Date(y, m, d, 0, 0, 0, 0, time.UTC)
}

// ISO is date.isoformat().
func ISO(t time.Time) string { return t.Format("2006-01-02") }

func dayStart(t time.Time) time.Time { return Day(t.Year(), t.Month(), t.Day()) }

func daysBetween(a, b time.Time) int { return int(dayStart(b).Sub(dayStart(a)) / (24 * time.Hour)) }

func floorDiv(a, b int) int {
	q := a / b
	if (a%b != 0) && ((a < 0) != (b < 0)) {
		q--
	}
	return q
}

// ShiftMonth is stay_fee.shift_month: the first day of the month delta months away.
func ShiftMonth(month time.Time, delta int) time.Time {
	index := month.Year()*12 + int(month.Month()) - 1 + delta
	return Day(floorDiv(index, 12), time.Month(index-floorDiv(index, 12)*12+1), 1)
}

// PreviousMonth is stay_fee.previous_month.
func PreviousMonth(today time.Time) time.Time {
	return ShiftMonth(Day(today.Year(), today.Month(), 1), -1)
}

// MonthKey is stay_fee.month_key: YYYY-MM.
func MonthKey(day time.Time) string { return fmt.Sprintf("%04d-%02d", day.Year(), int(day.Month())) }

// PeriodBounds is stay_fee.period_bounds: first and last day, inclusive, of the
// monthly or quarterly period containing month.
func PeriodBounds(cadence string, month time.Time) (time.Time, time.Time) {
	var first, after time.Time
	if cadence == "quarterly" {
		first = Day(month.Year(), time.Month((int(month.Month())-1)/3*3+1), 1)
		after = ShiftMonth(first, 3)
	} else {
		first = Day(month.Year(), month.Month(), 1)
		after = ShiftMonth(first, 1)
	}
	return first, after.AddDate(0, 0, -1)
}

// PeriodLabelCS is stay_fee.period_label_cs: "Srpen 2026" or "3. čtvrtletí 2026".
func PeriodLabelCS(cadence string, month time.Time) string {
	if cadence == "quarterly" {
		return fmt.Sprintf("%d. čtvrtletí %d", (int(month.Month())-1)/3+1, month.Year())
	}
	return fmt.Sprintf("%s %d", MonthsCS[int(month.Month())-1], month.Year())
}

// PeriodComplete is stay_fee.period_complete.
func PeriodComplete(cadence string, month, today time.Time) bool {
	_, last := PeriodBounds(cadence, month)
	return last.Before(dayStart(today))
}

// ParseMonth is stay_fee.parse_month: "2026-08" is the first of August 2026;
// anything else, and any year before 2000, is not ok.
func ParseMonth(value string) (time.Time, bool) {
	text := []rune(strings.TrimSpace(value))
	if len(text) != 7 || text[4] != '-' {
		return time.Time{}, false
	}
	for i, r := range text {
		if i != 4 && (r < '0' || r > '9') {
			return time.Time{}, false
		}
	}
	year, _ := strconv.Atoi(string(text[:4]))
	month, _ := strconv.Atoi(string(text[5:]))
	if month < 1 || month > 12 || year < 2000 {
		return time.Time{}, false
	}
	return Day(year, time.Month(month), 1), true
}

// CountedDaysIn is stay_fee.counted_days_in: days in (arrival, departure]
// inside first..last inclusive.
func CountedDaysIn(start, end, first, last time.Time) int {
	firstDay := start.AddDate(0, 0, 1)
	if end.Before(firstDay) {
		return 0
	}
	lo := firstDay
	if first.After(lo) {
		lo = first
	}
	hi := end
	if last.Before(hi) {
		hi = last
	}
	if n := daysBetween(lo, hi) + 1; n > 0 {
		return n
	}
	return 0
}

// FormatCZK is stay_fee.format_czk: "1 234 Kč" with no-break spaces, also before Kč.
func FormatCZK(amount int) string {
	digits := strconv.Itoa(amount)
	sign := ""
	if amount < 0 {
		sign, digits = "-", digits[1:]
	}
	var b strings.Builder
	for i, r := range digits {
		if i > 0 && (len(digits)-i)%3 == 0 {
			b.WriteString(nbsp)
		}
		b.WriteRune(r)
	}
	return sign + b.String() + nbsp + "Kč"
}

// ParseCZKInt is stay_fee.parse_czk_int: a non-negative integer from ASCII
// digits only. A number too large for int64 is returned as MaxInt64.
func ParseCZKInt(raw string) (int, bool) {
	text := strings.TrimSpace(raw)
	if text == "" {
		return 0, false
	}
	for _, r := range text {
		if r < '0' || r > '9' {
			return 0, false
		}
	}
	n, err := strconv.ParseInt(text, 10, 64)
	if err != nil {
		return int(^uint(0) >> 1), true
	}
	return int(n), true
}

// ClampRate is stay_fee.clamp_rate: 0 for unparseable input, at most MaxRateCZK.
func ClampRate(raw string) int {
	n, ok := ParseCZKInt(raw)
	if !ok {
		return 0
	}
	return max(0, min(n, MaxRateCZK))
}

// IsActive is stay_fee.is_active: the property has a stay-fee rate.
func IsActive(ap *Apartment) bool { return ap != nil && ap.StayFeeRateCZK > 0 }

// CadenceOf is stay_fee.cadence_of.
func CadenceOf(ap *Apartment) string {
	if inList(Cadences, ap.StayFeeCadence) {
		return ap.StayFeeCadence
	}
	return "monthly"
}

// VSOf is stay_fee.vs_of: the digits of the variable symbol.
func VSOf(ap *Apartment) string {
	var b strings.Builder
	for _, r := range ap.StayFeeVS {
		if unicode.IsDigit(r) {
			b.WriteRune(r)
		}
	}
	return b.String()
}

// DefaultDocType is stay_fee.default_doc_type.
func DefaultDocType(nationality string) string {
	if strings.ToUpper(nationality) == czechCode {
		return "op"
	}
	return "pas"
}

// DocTypeOf is stay_fee.doc_type_of.
func DocTypeOf(g GuestRow) string {
	if inList(DocTypes, g.DocType) {
		return g.DocType
	}
	return DefaultDocType(g.Nationality)
}

// --- birth dates -------------------------------------------------------------

// AgeOn is validation.age_on: whole years between birth and when.
func AgeOn(birth, when time.Time) int {
	years := when.Year() - birth.Year()
	if when.Month() < birth.Month() || (when.Month() == birth.Month() && when.Day() < birth.Day()) {
		years--
	}
	return years
}

func stripForbidden(v string) string {
	var b strings.Builder
	for _, r := range v {
		switch {
		case r == '\r' || r == '\n' || r == '|':
			b.WriteByte(' ')
		case r <= 0x08 || r == 0x0b || r == 0x0c || (r >= 0x0e && r <= 0x1f) || r == 0x7f:
			b.WriteByte(' ')
		default:
			b.WriteRune(r)
		}
	}
	return b.String()
}

func asciiDecimals(v string, keep string) string {
	var b strings.Builder
	for _, r := range v {
		if strings.ContainsRune(keep, r) || (r >= '0' && r <= '9') {
			b.WriteRune(r)
		}
	}
	return b.String()
}

func expandTwoDigitYear(two string) string {
	n, _ := strconv.Atoi(two)
	current := time.Now().Year()
	lo, hi := 1900+n, 2000+n
	switch {
	case hi <= current:
		return strconv.Itoa(hi)
	case lo <= current:
		return strconv.Itoa(lo)
	}
	return strconv.Itoa(lo)
}

func padInt(s string, width int) string {
	n, err := strconv.Atoi(s)
	if err != nil {
		return s
	}
	return fmt.Sprintf("%0*d", width, n)
}

// NormaliseBirthDate is validation.normalise_birth_date: DDMMYYYY.
func NormaliseBirthDate(value string) string {
	raw := strings.TrimSpace(stripForbidden(value))
	if raw == "" {
		return ""
	}
	separated := strings.ReplaceAll(strings.ReplaceAll(raw, "/", "."), "-", ".")
	dd := asciiDecimals(separated, ".")
	if strings.Contains(dd, ".") {
		var parts []string
		for _, p := range strings.Split(dd, ".") {
			if p != "" {
				parts = append(parts, p)
			}
		}
		if len(parts) == 3 {
			year := parts[2]
			if len(year) == 2 {
				year = expandTwoDigitYear(year)
			}
			return padInt(parts[0], 2) + padInt(parts[1], 2) + strings.Repeat("0", max(0, 4-len(year))) + year
		}
	}
	digits := asciiDecimals(raw, "")
	switch len(digits) {
	case 8:
		return digits
	case 6:
		return digits[:4] + expandTwoDigitYear(digits[4:])
	}
	return digits
}

// ConservativeBirth is stay_fee.conservative_birth: the earliest possible
// birthday, so an unknown day or month never makes an adult look like a minor.
func ConservativeBirth(raw string) (time.Time, bool) {
	digits := NormaliseBirthDate(raw)
	if len(digits) != 8 {
		return time.Time{}, false
	}
	day, _ := strconv.Atoi(digits[:2])
	month, _ := strconv.Atoi(digits[2:4])
	year, _ := strconv.Atoi(digits[4:])
	if year == 0 {
		return time.Time{}, false
	}
	if month == 0 {
		month = 1
	}
	if day == 0 {
		day = 1
	}
	t := Day(year, time.Month(month), day)
	if t.Year() != year || int(t.Month()) != month || t.Day() != day {
		return time.Time{}, false
	}
	return t, true
}

func certainlyUnderAge(raw string, when *time.Time, years int) bool {
	if when == nil {
		return false
	}
	birth, ok := ConservativeBirth(raw)
	return ok && AgeOn(birth, *when) < years
}

// guestSignatureSettled is reporting.guest_signature_settled: signed, or under
// 15 on arrival and so not asked to sign (brief 1089).
func guestSignatureSettled(g GuestRow) bool {
	sig := strings.TrimSpace(g.SignaturePNG)
	if sig == "imported" || strings.HasPrefix(sig, "data:image/") {
		return true
	}
	var start *time.Time
	if t, ok := validation.ParseISODate(g.StayFrom); ok {
		start = &t
	} else if t, ok := validation.ParseISODate(g.ResFrom); ok {
		start = &t
	}
	return certainlyUnderAge(g.BirthDate, start, 15)
}

// --- same-obec residence (0898) ---------------------------------------------

var (
	statutoryDistrictBases = []string{"PRAHA", "BRNO", "CESKE BUDEJOVICE", "DECIN", "FRYDEK-MISTEK", "HAVIROV",
		"HRADEC KRALOVE", "CHOMUTOV", "JABLONEC NAD NISOU", "JIHLAVA", "KARLOVY VARY",
		"KARVINA", "KLADNO", "LIBEREC", "MLADA BOLESLAV", "MOST", "OLOMOUC", "OPAVA",
		"OSTRAVA", "PARDUBICE", "PLZEN", "PROSTEJOV", "PREROV", "TEPLICE", "TRINEC",
		"USTI NAD LABEM", "ZLIN"}
	obecAliases = map[string]string{
		"PRAGUE": "PRAHA", "PRAG": "PRAHA",
		"BRUNN": "BRNO", "PILSEN": "PLZEN", "BUDWEIS": "CESKE BUDEJOVICE",
		"OSTRAU": "OSTRAVA", "MAHRISCH OSTRAU": "OSTRAVA", "MAHRISCH-OSTRAU": "OSTRAVA",
		"MORAVIAN OSTRAVA": "OSTRAVA", "MORAVSKA OSTRAVA": "OSTRAVA",
		"KARLSBAD": "KARLOVY VARY", "CARLSBAD": "KARLOVY VARY",
		"MARIENBAD": "MARIANSKE LAZNE", "FRANZENSBAD": "FRANTISKOVY LAZNE",
		"OLMUTZ": "OLOMOUC", "REICHENBERG": "LIBEREC", "AUSSIG": "USTI NAD LABEM",
		"KONIGGRATZ": "HRADEC KRALOVE", "PARDUBITZ": "PARDUBICE", "IGLAU": "JIHLAVA",
		"TROPPAU": "OPAVA", "TEPLITZ": "TEPLICE", "KOMOTAU": "CHOMUTOV", "TETSCHEN": "DECIN",
		"JUNGBUNZLAU": "MLADA BOLESLAV", "GABLONZ": "JABLONEC NAD NISOU",
		"PROSSNITZ": "PROSTEJOV", "PRERAU": "PREROV", "BRUX": "MOST",
		"KRUMAU": "CESKY KRUMLOV", "KUTTENBERG": "KUTNA HORA", "ZNAIM": "ZNOJMO",
	}
	officialPrefixes = []string{"HLAVNI MESTO ", "HL. M. ", "HL.M. ", "HL M ", "STATUTARNI MESTO "}
	okresNotObec     = []string{"PRAHA-VYCHOD", "PRAHA-ZAPAD", "BRNO-VENKOV", "PLZEN-JIH", "PLZEN-SEVER"}
	obecSuffixBases  = buildSuffixBases()
	dashRE           = regexp.MustCompile(`\s*[-\x{2010}-\x{2015}\x{2212}]\s*`)
)

func buildSuffixBases() []string {
	set := map[string]bool{}
	for _, b := range statutoryDistrictBases {
		set[b] = true
	}
	for name, target := range obecAliases {
		if inList(statutoryDistrictBases, target) {
			set[name] = true
		}
	}
	out := make([]string, 0, len(set))
	for b := range set {
		out = append(out, b)
	}
	sort.Slice(out, func(i, j int) bool {
		if len(out[i]) != len(out[j]) {
			return len(out[i]) > len(out[j])
		}
		return out[i] < out[j]
	})
	return out
}

// pyUpper is Python str.upper() for the cases that matter here (sharp s).
func pyUpper(s string) string {
	var b strings.Builder
	for _, r := range s {
		if r == 'ß' {
			b.WriteString("SS")
			continue
		}
		b.WriteRune(unicode.ToUpper(r))
	}
	return b.String()
}

// FoldText is stay_fee.fold_text: diacritics, case and spacing folded.
func FoldText(value string) string {
	var b strings.Builder
	for _, r := range norm.NFKD.String(value) {
		if norm.NFC.PropertiesString(string(r)).CCC() != 0 {
			continue
		}
		b.WriteRune(r)
	}
	return strings.Join(strings.Fields(pyUpper(b.String())), " ")
}

// afterBase is _AFTER_BASE.match(text, len(base)): what may follow a city name
// in a city-part form (signature.js uses the same rule).
func afterBase(rest string) bool {
	if rest == "" || strings.HasPrefix(rest, "-") {
		return true
	}
	trimmed := strings.TrimLeft(rest, " \t\n\r\f\v")
	if trimmed != "" {
		first := []rune(trimmed)[0]
		if unicode.IsDigit(first) || first == ',' || first == '(' {
			return true
		}
	}
	if strings.HasPrefix(rest, " ") {
		s2 := rest[1:]
		for _, w := range []string{"NAD", "POD", "U", "NA", "PRI"} {
			if strings.HasPrefix(s2, w) && (len(s2) == len(w) || s2[len(w)] == ' ') {
				return false
			}
		}
		return s2 != "" && s2[0] >= 'A' && s2[0] <= 'Z'
	}
	return false
}

func suffixBase(text string) (string, bool) {
	for _, base := range obecSuffixBases {
		if strings.HasPrefix(text, base) && afterBase(text[len(base):]) {
			return base, true
		}
	}
	return "", false
}

// ObecKey is stay_fee._obec_key: the town a typed name means, folded (1031 rules).
func ObecKey(value string) string {
	text := dashRE.ReplaceAllString(FoldText(value), "-")
	for _, prefix := range officialPrefixes {
		if strings.HasPrefix(text, prefix) {
			rest := strings.TrimSpace(text[len(prefix):])
			if _, ok := suffixBase(rest); ok {
				text = rest
				break
			}
		}
	}
	for _, name := range okresNotObec {
		if strings.HasPrefix(text, name) {
			next := text[len(name):]
			if next == "" || next[0] < 'A' || next[0] > 'Z' {
				return text
			}
		}
	}
	if base, ok := suffixBase(text); ok {
		text = base
	}
	if alias, ok := obecAliases[text]; ok {
		return alias
	}
	return text
}

// PropertyObec is stay_fee.property_obec: addr_obec, else the town in city_en.
func PropertyObec(ap *Apartment) string {
	for _, v := range []string{ap.AddrObec, ap.CityEN} {
		if strings.TrimSpace(v) != "" {
			return v
		}
	}
	return ""
}

// SameObecResident is stay_fee.same_obec_resident: true only for a CZ resident
// whose city is the property's town.
func SameObecResident(g GuestRow, ap *Apartment) bool {
	if g.ResCountry != czechCode {
		return false
	}
	obec := ObecKey(PropertyObec(ap))
	return obec != "" && ObecKey(g.ResCity) == obec
}

// --- dated rates (brief 1027) --------------------------------------------------

// FlatSchedule is stay_fee_rate.flat: one rate for every night.
func FlatSchedule(rate int) []RateStep { return []RateStep{{From: time.Time{}, Rate: rate}} }

// ScheduleFor is stay_fee_rate.schedule_for over loaded rows. today is Python's
// date.today() default, used only when the column moved without a history row.
func ScheduleFor(column int, rows []RateRow, today time.Time) ([]RateStep, error) {
	if len(rows) == 0 {
		return FlatSchedule(column), nil
	}
	schedule := make([]RateStep, 0, len(rows)+1)
	for _, row := range rows {
		from, err := time.Parse("2006-01-02", row.EffectiveFrom)
		if err != nil {
			return nil, fmt.Errorf("stay_fee_rate.effective_from %q: %w", row.EffectiveFrom, err)
		}
		schedule = append(schedule, RateStep{From: from, Rate: row.RateCZK})
	}
	if schedule[len(schedule)-1].Rate != column {
		schedule = append(schedule, RateStep{From: dayStart(today), Rate: column})
		sort.SliceStable(schedule, func(i, j int) bool { return schedule[i].From.Before(schedule[j].From) })
	}
	return schedule, nil
}

// RateOn is stay_fee_rate.rate_on: the last entry dated on or before day.
func RateOn(schedule []RateStep, day time.Time) int {
	rate := schedule[0].Rate
	for _, step := range schedule {
		if !step.From.After(day) {
			rate = step.Rate
		} else {
			break
		}
	}
	return rate
}

// IsUniform is stay_fee_rate.is_uniform: one rate for every night first..last.
func IsUniform(schedule []RateStep, first, last time.Time) bool {
	rates := map[int]bool{RateOn(schedule, first): true, RateOn(schedule, last): true}
	for _, step := range schedule {
		if first.Before(step.From) && !step.From.After(last) {
			rates[RateOn(schedule, step.From)] = true
		}
	}
	return len(rates) == 1
}

// --- per guest and per property ------------------------------------------------

// GuestPeriod is stay_fee.guest_period with the apartment and schedule given:
// one guest's share of one period, or ok false when no counted day falls in it.
func GuestPeriod(g GuestRow, first, last time.Time, ap *Apartment, schedule []RateStep) (Line, bool) {
	fromText, toText := g.StayFrom, g.StayTo
	if fromText == "" {
		fromText = g.ResFrom
	}
	if toText == "" {
		toText = g.ResTo
	}
	start, okStart := validation.ParseISODate(fromText)
	end, okEnd := validation.ParseISODate(toText)
	if !okStart || !okEnd || !end.After(start) {
		return Line{}, false
	}
	stayNights := daysBetween(start, end)
	var decision *string
	if inList(Decisions, g.FeeHostDecision) {
		d := g.FeeHostDecision
		decision = &d
	}
	status := "liable"
	if stayNights > ThresholdNights {
		status = "not_subject"
	}
	liable, exempt, amount := 0, 0, 0
	byRate := map[int]int{}
	autoMinor := false
	var birth time.Time
	haveBirth := false
	if decision == nil {
		birth, haveBirth = ConservativeBirth(g.BirthDate)
	}
	obecAuto := decision == nil && SameObecResident(g, ap)
	d := start.AddDate(0, 0, 1)
	if first.After(d) {
		d = first
	}
	endInPeriod := end
	if last.Before(endInPeriod) {
		endInPeriod = last
	}
	for ; !d.After(endInPeriod); d = d.AddDate(0, 0, 1) {
		if status == "not_subject" {
			continue
		}
		dayStatus := "exempt"
		if !obecAuto {
			switch {
			case decision != nil && *decision == "exempt":
				dayStatus = "exempt"
			default:
				if !haveBirth {
					birth, haveBirth = ConservativeBirth(g.BirthDate)
				}
				if haveBirth && AgeOn(birth, d) < AdultAge {
					dayStatus = "exempt"
				} else {
					dayStatus = "liable"
				}
			}
		}
		if dayStatus == "liable" {
			liable++
			rate := RateOn(schedule, d)
			amount += rate
			byRate[rate]++
		} else {
			exempt++
			if decision == nil && haveBirth && AgeOn(birth, d) < AdultAge {
				autoMinor = true
			}
		}
	}
	days := liable + exempt
	if days <= 0 && status != "not_subject" {
		return Line{}, false
	}
	switch {
	case status == "not_subject":
		days = CountedDaysIn(start, end, first, last)
		liable, exempt = 0, 0
	case exempt > 0 && liable == 0:
		status = "exempt"
	case liable > 0:
		status = "liable"
	}
	rateNights := [][2]int{}
	for r, n := range byRate {
		rateNights = append(rateNights, [2]int{r, n})
	}
	sort.Slice(rateNights, func(i, j int) bool {
		if rateNights[i][0] != rateNights[j][0] {
			return rateNights[i][0] < rateNights[j][0]
		}
		return rateNights[i][1] < rateNights[j][1]
	})
	return Line{
		GuestID:          g.ID,
		StayFrom:         ISO(start),
		StayTo:           ISO(end),
		Nights:           days,
		LiableNights:     liable,
		ExemptNights:     exempt,
		Status:           status,
		AutoMinor:        autoMinor && status == "exempt",
		Decision:         decision,
		Reason:           g.FeeHostReason,
		ThresholdNights:  stayNights == ThresholdNights,
		AmountCZK:        amount,
		RateNights:       rateNights,
		AutoObecResident: obecAuto && status == "exempt",
	}, true
}

// applyScopeBoundary is stay_fee._apply_scope_boundary: a recorded 60-night
// ruling. Exactly 60 nights is 61 calendar days.
func applyScopeBoundary(line *Line, ap *Apartment) {
	if !line.ThresholdNights || strings.TrimSpace(ap.ScopeRule) != "calendar_days" {
		return
	}
	line.Status = "not_subject"
	line.LiableNights = 0
	line.ExemptNights = 0
	line.AutoMinor = false
	line.AmountCZK = 0
	line.RateNights = [][2]int{}
	line.AutoObecResident = false
}

// ChooseCadence is the first line of property_period: cadence if valid, else the apartment's.
func ChooseCadence(ap *Apartment, cadence string) string {
	if inList(Cadences, cadence) {
		return cadence
	}
	return CadenceOf(ap)
}

// BuildPeriod is stay_fee.property_period for a live period (live_only=True):
// the figures for ap and the period of cadence containing month. rate, when
// not nil, overrides the dated schedule with one flat rate. It returns nil when
// the property has no stay fee. The guests, rates and adjustments come in as in.
func BuildPeriod(ap *Apartment, month time.Time, cadence string, rate *int, in PeriodInput) (*Period, error) {
	chosen := ChooseCadence(ap, cadence)
	if !IsActive(ap) {
		return nil, nil
	}
	first, last := PeriodBounds(chosen, month)
	var schedule []RateStep
	if rate != nil {
		schedule = FlatSchedule(*rate)
	} else {
		var err error
		if schedule, err = ScheduleFor(ap.StayFeeRateCZK, in.RateRows, in.ScheduleToday); err != nil {
			return nil, err
		}
	}
	lastRate := RateOn(schedule, last)
	lines := []Line{}
	unsigned := 0
	for _, g := range in.Guests {
		if !guestSignatureSettled(g) {
			unsigned++
		}
		line, ok := GuestPeriod(g, first, last, ap, schedule)
		if !ok {
			continue
		}
		applyScopeBoundary(&line, ap)
		line.ReservationID = g.ReservationID
		line.Name = strings.TrimSpace(g.FirstName + " " + g.Surname)
		line.Restricted = g.Restricted
		line.ResCountry = g.ResCountry
		line.ResCity = g.ResCity
		lines = append(lines, line)
	}
	liable, exempt := 0, 0
	for _, l := range lines {
		liable += l.LiableNights
		exempt += l.ExemptNights
	}
	period := &Period{
		Apartment:         ap,
		Cadence:           chosen,
		First:             first,
		Last:              last,
		Label:             PeriodLabelCS(chosen, first),
		RateCZK:           lastRate,
		Lines:             lines,
		GuestLiableNights: liable,
		LiableNights:      liable,
		ExemptNights:      exempt,
		TotalCZK:          liable * lastRate,
		Adjustments:       []Adjustment{},
		UnsignedGuests:    unsigned,
	}
	applyAdjustments(period, month, in.Adjustments)
	return period, nil
}

// rateSegments is stay_fee._rate_segments: nights per rate, guest nights plus
// bed-days at the last-day rate, as [rate, nights] pairs.
func rateSegments(p *Period) [][2]int {
	nights := map[int]int{}
	for _, line := range p.Lines {
		for _, rn := range line.RateNights {
			nights[rn[0]] += rn[1]
		}
	}
	base := p.RateCZK
	nights[base] += p.AdjustmentBedDays
	deficit := 0
	if nights[base] < 0 {
		deficit = -nights[base]
	}
	if deficit > 0 {
		nights[base] = 0
		rates := make([]int, 0, len(nights))
		for r := range nights {
			rates = append(rates, r)
		}
		sort.Sort(sort.Reverse(sort.IntSlice(rates)))
		for _, r := range rates {
			take := min(deficit, nights[r])
			nights[r] -= take
			deficit -= take
		}
	}
	out := [][2]int{}
	for r, n := range nights {
		if n > 0 {
			out = append(out, [2]int{r, n})
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i][0] < out[j][0] })
	if len(out) == 0 {
		return [][2]int{{base, 0}}
	}
	return out
}

// applyAdjustments is stay_fee._apply_adjustments: fold open aggregate
// corrections into the live liable total.
func applyAdjustments(p *Period, month time.Time, rows []Adjustment) {
	delta := 0
	for _, r := range rows {
		delta += r.Delta
	}
	guestNights := p.GuestLiableNights
	liable := max(guestNights+delta, 0)
	p.AdjustmentBedDays = liable - guestNights
	p.Adjustments = rows
	if p.Adjustments == nil {
		p.Adjustments = []Adjustment{}
	}
	p.LiableNights = liable
	p.RateSegments = rateSegments(p)
	total := 0
	for _, seg := range p.RateSegments {
		total += seg[0] * seg[1]
	}
	p.TotalCZK = total
	p.PeriodKey = PeriodKey(p.Cadence, month)
}
