// Package booking is the logic layer of the public booking site (/p/<slug>),
// ported from App/app/booking_site.py, booking_calendar.py, booking_rails.py,
// booking_ical.py, booking_manage.calendar_ics and the URL helpers of
// property_page.py (brief 1351). It renders no HTML page.
//
// Times are Europe/Prague, dates are ISO strings like the reservation table,
// money is whole CZK. testdata/golden.json (App/scripts/booking_site_golden.py)
// pins every result to the Python one.
package booking

import (
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"sort"
	"strconv"
	"strings"
	"time"
	_ "time/tzdata" // the Prague zone must exist even on a bare container

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

// DB is the part of *pgxpool.Pool this package uses.
type DB interface {
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
}

// Constants from booking_site.py.
const (
	MaxNights          = 30
	MaxGuests          = 60
	DefaultCutoffHour  = 18
	DefaultCheckinHour = 15
	TermsVersion       = "2026-11-03"
)

// Policies, NoticeDays and Statuses are booking_site.POLICIES, NOTICE_DAYS, STATUSES.
var (
	Policies   = []string{"non_refundable", "flexible", "moderate"}
	NoticeDays = []int{0, 1, 2, 3, 7}
	Statuses   = []string{"pending", "requested", "paid", "expired", "cancelled", "refunded", "clash_refunded"}
)

var prague = mustZone("Europe/Prague")

func mustZone(name string) *time.Location {
	loc, err := time.LoadLocation(name)
	if err != nil {
		panic(err)
	}
	return loc
}

// Prague is the Europe/Prague zone.
func Prague() *time.Location { return prague }

// Settings is booking_site.settings(): stored values with defaults filled in.
type Settings struct {
	NightlyPriceCZK    int    `json:"nightly_price_czk"`
	CleaningFeeCZK     int    `json:"cleaning_fee_czk"`
	MinNights          int    `json:"min_nights"`
	MaxGuests          int    `json:"max_guests"`
	CancellationPolicy string `json:"cancellation_policy"`
	AdvanceNoticeDays  int    `json:"advance_notice_days"`
	SameDayCutoffHour  int    `json:"same_day_cutoff_hour"`
	ICalToken          string `json:"ical_token"`
	CheckinHour        int    `json:"checkin_hour"`
	CityTaxCZK         int    `json:"city_tax_czk"`
}

func settingKey(apartmentID int64) string {
	return "booking_site:" + strconv.FormatInt(apartmentID, 10)
}

func contains[T comparable](list []T, v T) bool {
	for _, x := range list {
		if x == v {
			return true
		}
	}
	return false
}

// pyNumber reads a JSON number the way the Python code uses it: ok is false
// for a non-number; integral is false for a float literal such as 18.0.
func pyNumber(v any) (n int, integral bool, ok bool) {
	num, isNum := v.(json.Number)
	if !isNum {
		return 0, false, false
	}
	if i, err := strconv.ParseInt(string(num), 10, 64); err == nil {
		return int(i), true, true
	}
	f, err := num.Float64()
	if err != nil {
		return 0, false, false
	}
	return int(f), false, true // int(float) truncates toward zero
}

// pyEqualInt is Python "value in list" for a JSON value (7.0 == 7 holds).
func pyEqualInt(v any, list []int) (int, bool) {
	num, isNum := v.(json.Number)
	if !isNum {
		return 0, false
	}
	f, err := num.Float64()
	if err != nil {
		return 0, false
	}
	for _, x := range list {
		if float64(x) == f {
			return x, true
		}
	}
	return 0, false
}

// LoadSettings is booking_site.settings(apartment_id). A stored value that
// is not a number is treated as absent (Python would fail later; save_settings
// only ever writes whole numbers).
func LoadSettings(ctx context.Context, db DB, apartmentID int64) (Settings, error) {
	s := Settings{MinNights: 1, CancellationPolicy: "non_refundable", SameDayCutoffHour: DefaultCutoffHour}
	var raw *string
	err := db.QueryRow(ctx, `SELECT value FROM settings WHERE key = $1`, settingKey(apartmentID)).Scan(&raw)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return s, err
	}
	text := "{}"
	if raw != nil && *raw != "" {
		text = *raw
	}
	stored := map[string]any{}
	dec := json.NewDecoder(strings.NewReader(text))
	dec.UseNumber()
	var parsed any
	if dec.Decode(&parsed) == nil && !dec.More() {
		if m, ok := parsed.(map[string]any); ok {
			stored = m
		}
	}
	for key, dst := range map[string]*int{
		"nightly_price_czk": &s.NightlyPriceCZK, "cleaning_fee_czk": &s.CleaningFeeCZK,
		"min_nights": &s.MinNights, "max_guests": &s.MaxGuests,
	} {
		if n, _, ok := pyNumber(stored[key]); ok {
			*dst = n
		}
	}
	if v, present := stored["cancellation_policy"]; present {
		str, _ := v.(string)
		s.CancellationPolicy = str
	}
	if _, present := stored["advance_notice_days"]; present {
		if n, ok := pyEqualInt(stored["advance_notice_days"], NoticeDays); ok {
			s.AdvanceNoticeDays = n
		}
	}
	if v, present := stored["same_day_cutoff_hour"]; present {
		s.SameDayCutoffHour = -1
		if n, integral, ok := pyNumber(v); ok && integral {
			s.SameDayCutoffHour = n
		}
	}
	if v, ok := stored["ical_token"].(string); ok {
		s.ICalToken = v
	}
	if _, present := stored["nightly_price_czk"]; !present {
		// Pages priced before 0814 kept the price only on property_page (0434).
		var price *int64
		err := db.QueryRow(ctx, `SELECT nightly_price_czk FROM property_page WHERE apartment_id = $1 LIMIT 1`, apartmentID).Scan(&price)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return s, err
		}
		if err == nil && price != nil && *price != 0 {
			s.NightlyPriceCZK = int(*price)
		}
	}
	if !contains(Policies, s.CancellationPolicy) {
		s.CancellationPolicy = "non_refundable"
	}
	if s.SameDayCutoffHour < 0 || s.SameDayCutoffHour > 23 {
		s.SameDayCutoffHour = DefaultCutoffHour
	}
	var hour *int64
	var cityTax *int64
	err = db.QueryRow(ctx, `SELECT checkin_hour, stay_fee_rate_czk FROM apartment WHERE id = $1`, apartmentID).Scan(&hour, &cityTax)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return s, err
	}
	s.CheckinHour = DefaultCheckinHour
	if err == nil {
		if hour != nil && *hour >= 0 && *hour <= 23 {
			s.CheckinHour = int(*hour)
		}
		if cityTax != nil {
			s.CityTaxCZK = int(*cityTax)
		}
	}
	return s, nil
}

// storedJSON is json.dumps({k: current[k] for k in DEFAULTS}, sort_keys=True).
func storedJSON(s Settings) string {
	fields := map[string]string{
		"nightly_price_czk":    strconv.Itoa(s.NightlyPriceCZK),
		"cleaning_fee_czk":     strconv.Itoa(s.CleaningFeeCZK),
		"min_nights":           strconv.Itoa(s.MinNights),
		"max_guests":           strconv.Itoa(s.MaxGuests),
		"cancellation_policy":  pyString(s.CancellationPolicy),
		"advance_notice_days":  strconv.Itoa(s.AdvanceNoticeDays),
		"same_day_cutoff_hour": strconv.Itoa(s.SameDayCutoffHour),
		"ical_token":           pyString(s.ICalToken),
	}
	keys := make([]string, 0, len(fields))
	for k := range fields {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	parts := make([]string, len(keys))
	for i, k := range keys {
		parts[i] = pyString(k) + ": " + fields[k]
	}
	return "{" + strings.Join(parts, ", ") + "}"
}

// pyString is json.dumps(str) with ensure_ascii.
func pyString(v string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range v {
		switch {
		case r == '"':
			b.WriteString(`\"`)
		case r == '\\':
			b.WriteString(`\\`)
		case r == '\n':
			b.WriteString(`\n`)
		case r == '\r':
			b.WriteString(`\r`)
		case r == '\t':
			b.WriteString(`\t`)
		case r < 0x20 || r > 0x7e:
			if r > 0xffff {
				r -= 0x10000
				b.WriteString(`\u` + hex4(0xd800+(r>>10)) + `\u` + hex4(0xdc00+(r&0x3ff)))
			} else {
				b.WriteString(`\u` + hex4(r))
			}
		default:
			b.WriteRune(r)
		}
	}
	b.WriteByte('"')
	return b.String()
}

func hex4(r rune) string {
	s := strconv.FormatInt(int64(r), 16)
	return strings.Repeat("0", 4-len(s)) + s
}

// ICalToken is booking_site.ical_token: the export URL secret, created on
// first use (secrets.token_urlsafe(18)) and stored with the other settings.
func ICalToken(ctx context.Context, db DB, apartmentID int64) (string, error) {
	s, err := LoadSettings(ctx, db, apartmentID)
	if err != nil {
		return "", err
	}
	if s.ICalToken != "" {
		return s.ICalToken, nil
	}
	buf := make([]byte, 18)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	s.ICalToken = base64.RawURLEncoding.EncodeToString(buf)
	if err := setSetting(ctx, db, settingKey(apartmentID), storedJSON(s)); err != nil {
		return "", err
	}
	return s.ICalToken, nil
}

// setSetting is db.set_setting: an upsert on settings.key.
func setSetting(ctx context.Context, db DB, key, value string) error {
	_, err := db.Exec(ctx, `INSERT INTO settings (key, value) VALUES ($1, $2)
		ON CONFLICT (key) DO UPDATE SET value = excluded.value`, key, value)
	return err
}

// --- dates --------------------------------------------------------------

// civil returns the calendar date of t as midnight UTC.
func civil(t time.Time) time.Time {
	y, m, d := t.Date()
	return time.Date(y, m, d, 0, 0, 0, 0, time.UTC)
}

func isoDay(t time.Time) string { return t.Format("2006-01-02") }

// wall is t's Prague wall clock read as UTC. Python subtracts two datetimes
// that share the PRAGUE tzinfo by wall clock, ignoring DST; so do we.
func wall(t time.Time) time.Time {
	l := t.In(prague)
	return time.Date(l.Year(), l.Month(), l.Day(), l.Hour(), l.Minute(), l.Second(), l.Nanosecond(), time.UTC)
}

// EarliestCheckIn is booking_site.earliest_check_in (a civil date).
func EarliestCheckIn(s Settings, now time.Time) time.Time {
	local := now.In(prague)
	day := civil(local)
	if s.AdvanceNoticeDays == 0 {
		if local.Hour() < s.SameDayCutoffHour {
			return day
		}
		return day.AddDate(0, 0, 1)
	}
	return day.AddDate(0, 0, s.AdvanceNoticeDays)
}

// --- quote --------------------------------------------------------------

// Quote is booking_site.quote(). Error is "" for a good quote, else one of
// bad_dates, min_nights, too_soon, guests, no_price, taken; MinNights is set
// only with min_nights.
type Quote struct {
	Error              string
	MinNights          int
	DateFrom           string
	DateTo             string
	Nights             int
	Guests             int
	NightlyCZK         int
	AccommodationCZK   int
	CleaningFeeCZK     int
	TotalCZK           int
	CityTaxOnSiteCZK   int
	CancellationPolicy string
}

// Map is the Python dict the quote returns.
func (q Quote) Map() map[string]any {
	if q.Error == "min_nights" {
		return map[string]any{"error": q.Error, "min_nights": q.MinNights}
	}
	if q.Error != "" {
		return map[string]any{"error": q.Error}
	}
	return map[string]any{
		"error": nil, "date_from": q.DateFrom, "date_to": q.DateTo, "nights": q.Nights,
		"guests": q.Guests, "nightly_czk": q.NightlyCZK, "accommodation_czk": q.AccommodationCZK,
		"cleaning_fee_czk": q.CleaningFeeCZK, "total_czk": q.TotalCZK,
		"city_tax_on_site_czk": q.CityTaxOnSiteCZK, "cancellation_policy": q.CancellationPolicy,
	}
}

// GetQuote is booking_site.quote(apartment_id, date_from, date_to, guests, now=now).
func GetQuote(ctx context.Context, db DB, apartmentID int64, dateFrom, dateTo string, guests int, now time.Time) (Quote, error) {
	s, err := LoadSettings(ctx, db, apartmentID)
	if err != nil {
		return Quote{}, err
	}
	dFrom, ok1 := ParseISODate(dateFrom)
	dTo, ok2 := ParseISODate(dateTo)
	if !ok1 || !ok2 {
		return Quote{Error: "bad_dates"}, nil
	}
	nights := int(dTo.Sub(dFrom).Hours() / 24)
	if nights < 1 || nights > MaxNights {
		return Quote{Error: "bad_dates"}, nil
	}
	if nights < s.MinNights {
		return Quote{Error: "min_nights", MinNights: s.MinNights}, nil
	}
	if dFrom.Before(EarliestCheckIn(s, now)) {
		return Quote{Error: "too_soon"}, nil
	}
	if guests < 1 {
		return Quote{Error: "guests"}, nil
	}
	limit := s.MaxGuests
	if limit == 0 {
		limit = MaxGuests
	}
	if guests > limit {
		return Quote{Error: "guests"}, nil
	}
	nightly := s.NightlyPriceCZK
	if nightly < 1 {
		return Quote{Error: "no_price"}, nil
	}
	free, err := DatesAvailable(ctx, db, apartmentID, isoDay(dFrom), isoDay(dTo), now)
	if err != nil {
		return Quote{}, err
	}
	if !free {
		return Quote{Error: "taken"}, nil
	}
	accommodation := nightly * nights
	return Quote{
		DateFrom: isoDay(dFrom), DateTo: isoDay(dTo), Nights: nights, Guests: guests,
		NightlyCZK: nightly, AccommodationCZK: accommodation, CleaningFeeCZK: s.CleaningFeeCZK,
		TotalCZK: accommodation + s.CleaningFeeCZK, CityTaxOnSiteCZK: s.CityTaxCZK * guests * nights,
		CancellationPolicy: s.CancellationPolicy,
	}, nil
}

// StampAt formats a time like Python db.utcnow().
func StampAt(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

// DatesAvailable is property_page.dates_available: no active reservation and
// no live hold overlaps [dateFrom, dateTo).
func DatesAvailable(ctx context.Context, db DB, apartmentID int64, dateFrom, dateTo string, now time.Time) (bool, error) {
	var id int64
	err := db.QueryRow(ctx, `SELECT id FROM reservation r
		WHERE r.apartment_id = $1 AND r.status = 'active'
		AND r.date_from < $2 AND r.date_to > $3 LIMIT 1`, apartmentID, dateTo, dateFrom).Scan(&id)
	if err == nil {
		return false, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return false, err
	}
	err = db.QueryRow(ctx, `SELECT id FROM booking_hold
		WHERE apartment_id = $1 AND expires_at > $2
		AND date_from < $3 AND date_to > $4 LIMIT 1`, apartmentID, StampAt(now), dateTo, dateFrom).Scan(&id)
	if err == nil {
		return false, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return false, err
	}
	return true, nil
}

// --- refunds ------------------------------------------------------------

// RefundBooking holds the site_booking columns refund_czk reads.
type RefundBooking struct {
	TotalCZK           int    `json:"total_czk"`
	RefundedCZK        int    `json:"refunded_czk"`
	CleaningFeeCZK     int    `json:"cleaning_fee_czk"`
	DateFrom           string `json:"date_from"`
	CancellationPolicy string `json:"cancellation_policy"`
}

// CheckInMoment is booking_site.check_in_moment, in Prague.
func CheckInMoment(checkIn string, checkinHour int) (time.Time, bool) {
	d, ok := ParseISODate(checkIn)
	if !ok {
		return time.Time{}, false
	}
	return time.Date(d.Year(), d.Month(), d.Day(), checkinHour, 0, 0, 0, prague), true
}

// RefundCZK is booking_site.refund_czk: what the guest gets back if the
// booking is cancelled now. Host cancellation always refunds in full.
func RefundCZK(b RefundBooking, checkinHour int, now time.Time, byHost bool) (int, error) {
	total := b.TotalCZK - b.RefundedCZK
	if total <= 0 {
		return 0, nil
	}
	if byHost {
		return total, nil
	}
	moment, ok := CheckInMoment(b.DateFrom, checkinHour)
	if !ok {
		return 0, errors.New("booking: bad date_from " + b.DateFrom)
	}
	left := wall(moment).Sub(wall(now))
	switch b.CancellationPolicy {
	case "flexible":
		if left >= 24*time.Hour {
			return total, nil
		}
		return 0, nil
	case "moderate":
		if left >= 5*24*time.Hour {
			return total, nil
		}
		if left > 0 {
			cleaning := b.CleaningFeeCZK
			return min(total, cleaning+floorDiv(b.TotalCZK-cleaning, 2)), nil
		}
		return 0, nil
	}
	return 0, nil
}

// floorDiv is Python //.
func floorDiv(a, b int) int {
	q := a / b
	if (a%b != 0) && ((a < 0) != (b < 0)) {
		q--
	}
	return q
}

// --- tokens and URLs ----------------------------------------------------

// TokenHash is booking_site.token_hash.
func TokenHash(token string) string {
	sum := sha256.Sum256([]byte(token))
	return hex.EncodeToString(sum[:])
}

// ManageToken is booking_site.manage_token: HMAC-SHA256 of
// "site_booking:<id>" under the server secret, first 40 hex characters.
func ManageToken(secret string, bookingID int64) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte("site_booking:" + strconv.FormatInt(bookingID, 10)))
	return hex.EncodeToString(mac.Sum(nil))[:40]
}

// ManageTokenOK is booking_site.token_ok.
func ManageTokenOK(secret string, bookingID int64, token string) bool {
	return hmac.Equal([]byte(ManageToken(secret, bookingID)), []byte(token))
}

// ManageURL is booking_site.manage_url; base is hostweb.PublicBase(getenv).
func ManageURL(ctx context.Context, db DB, base, secret string, apartmentID, bookingID int64) (string, error) {
	slug := "x"
	var live string
	err := db.QueryRow(ctx, `SELECT slug FROM property_slug WHERE apartment_id = $1 LIMIT 1`, apartmentID).Scan(&live)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return "", err
	}
	if err == nil {
		slug = live
	}
	return strings.TrimRight(base, "/") + "/p/" + slug + "/b/" + strconv.FormatInt(bookingID, 10) + "/" +
		ManageToken(secret, bookingID), nil
}

// Resolved is property_page.resolve(slug). Kind is "redirect" (Redirect is
// the live slug: answer 301 to RedirectPath), "missing" (unpublished: 404),
// "live" (published) or "none" (404).
type Resolved struct {
	Kind        string `json:"kind"`
	Redirect    string `json:"redirect,omitempty"`
	ApartmentID int64  `json:"apartment_id,omitempty"`
}

// Resolve is property_page.resolve: history 301 first, then the live slug.
func Resolve(ctx context.Context, db DB, slug string) (Resolved, error) {
	var aptID int64
	err := db.QueryRow(ctx, `SELECT apartment_id FROM property_slug_history WHERE old_slug = $1 LIMIT 1`, slug).Scan(&aptID)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return Resolved{}, err
	}
	if err == nil {
		var live string
		err = db.QueryRow(ctx, `SELECT slug FROM property_slug WHERE apartment_id = $1 LIMIT 1`, aptID).Scan(&live)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return Resolved{}, err
		}
		if err == nil {
			return Resolved{Kind: "redirect", Redirect: live}, nil
		}
	}
	var published int64
	err = db.QueryRow(ctx, `SELECT apartment_id, published FROM property_slug WHERE slug = $1 LIMIT 1`, slug).Scan(&aptID, &published)
	if errors.Is(err, pgx.ErrNoRows) {
		return Resolved{Kind: "none"}, nil
	}
	if err != nil {
		return Resolved{}, err
	}
	if published == 0 {
		return Resolved{Kind: "missing", ApartmentID: aptID}, nil
	}
	return Resolved{Kind: "live", ApartmentID: aptID}, nil
}

// RedirectPath is the 301 Location for a history slug ("/p/<live>"), "" for
// any other result. The page brief answers GET /p/{slug} with it.
func RedirectPath(r Resolved) string {
	if r.Kind != "redirect" {
		return ""
	}
	return "/p/" + r.Redirect
}
