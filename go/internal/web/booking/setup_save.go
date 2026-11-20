package booking

// Host booking-site settings save (booking_site.save_settings, booking_setup.parse_form).

import (
	"context"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

const (
	maxPriceCZK = 1_000_000
	maxNights   = 30
	maxGuests   = 60
)

// NoticeOptions is booking_setup.NOTICE_OPTIONS.
var NoticeOptions = []string{"0:12", "0:15", "0:18", "0:21", "1", "2", "3", "7"}

var setupErrFields = map[string]string{
	"same_day_cutoff_hour": "advance_notice_days",
}

// SetupFormError maps ValueError to the i18n field suffix.
func SetupFormError(field string) string {
	if alt, ok := setupErrFields[field]; ok {
		field = alt
	}
	switch field {
	case "nightly_price_czk", "cleaning_fee_czk", "min_nights", "max_guests",
		"cancellation_policy", "advance_notice_days":
		return field
	default:
		return "nightly_price_czk"
	}
}

// ParseSetupForm is booking_setup.parse_form.
func ParseSetupForm(form map[string][]string) (map[string]any, error) {
	get := func(name string) string {
		if v := form[name]; len(v) > 0 {
			return strings.TrimSpace(v[0])
		}
		return ""
	}
	whole := func(name string, emptyZero bool) (int, error) {
		text := strings.ReplaceAll(get(name), " ", "")
		if text == "" && emptyZero {
			return 0, nil
		}
		if !isDigits(text) {
			return 0, fmt.Errorf("%s", name)
		}
		n, _ := strconv.Atoi(text)
		return n, nil
	}
	nightly, err := whole("nightly_price_czk", false)
	if err != nil {
		return nil, err
	}
	cleaning, err := whole("cleaning_fee_czk", true)
	if err != nil {
		return nil, err
	}
	minN, err := whole("min_nights", false)
	if err != nil {
		return nil, err
	}
	maxG, err := whole("max_guests", true)
	if err != nil {
		return nil, err
	}
	notice := get("notice")
	if !containsStr(NoticeOptions, notice) {
		return nil, errors.New("advance_notice_days")
	}
	days, hour, _ := strings.Cut(notice, ":")
	d, _ := strconv.Atoi(days)
	out := map[string]any{
		"nightly_price_czk":   nightly,
		"cleaning_fee_czk":    cleaning,
		"min_nights":          minN,
		"max_guests":          maxG,
		"cancellation_policy": get("cancellation_policy"),
		"advance_notice_days": d,
	}
	if hour != "" {
		h, err := strconv.Atoi(hour)
		if err != nil {
			return nil, errors.New("advance_notice_days")
		}
		out["same_day_cutoff_hour"] = h
	}
	return out, nil
}

func isDigits(s string) bool {
	if s == "" {
		return false
	}
	for _, r := range s {
		if r < '0' || r > '9' {
			return false
		}
	}
	return true
}

func containsStr(list []string, v string) bool {
	for _, s := range list {
		if s == v {
			return true
		}
	}
	return false
}

func wholeInt(v any, low, high int, field string) (int, error) {
	n, ok := v.(int)
	if !ok {
		switch t := v.(type) {
		case float64:
			n = int(t)
		default:
			return 0, fmt.Errorf("%s", field)
		}
	}
	if n < low || n > high {
		return 0, fmt.Errorf("%s", field)
	}
	return n, nil
}

// SaveSettings is booking_site.save_settings.
func SaveSettings(ctx context.Context, db DB, apartmentID int64, values map[string]any, now time.Time) (Settings, error) {
	current, err := LoadSettings(ctx, db, apartmentID)
	if err != nil {
		return Settings{}, err
	}
	new := current
	fields := []string{"nightly_price_czk", "cleaning_fee_czk", "min_nights", "max_guests",
		"cancellation_policy", "advance_notice_days", "same_day_cutoff_hour"}
	for _, f := range fields {
		if v, ok := values[f]; ok {
			switch f {
			case "nightly_price_czk":
				n, err := wholeInt(v, 1, maxPriceCZK, f)
				if err != nil {
					return Settings{}, err
				}
				new.NightlyPriceCZK = n
			case "cleaning_fee_czk":
				n, err := wholeInt(v, 0, maxPriceCZK, f)
				if err != nil {
					return Settings{}, err
				}
				new.CleaningFeeCZK = n
			case "min_nights":
				n, err := wholeInt(v, 1, maxNights, f)
				if err != nil {
					return Settings{}, err
				}
				new.MinNights = n
			case "max_guests":
				n, err := wholeInt(v, 0, maxGuests, f)
				if err != nil {
					return Settings{}, err
				}
				new.MaxGuests = n
			case "same_day_cutoff_hour":
				n, err := wholeInt(v, 0, 23, f)
				if err != nil {
					return Settings{}, err
				}
				new.SameDayCutoffHour = n
			case "cancellation_policy":
				p := fmt.Sprint(v)
				if !containsStr(Policies, p) {
					return Settings{}, errors.New("cancellation_policy")
				}
				new.CancellationPolicy = p
			case "advance_notice_days":
				n, err := wholeInt(v, 0, 7, f)
				if err != nil {
					return Settings{}, err
				}
				if !pyEqualIntList(n, NoticeDays) {
					return Settings{}, errors.New("advance_notice_days")
				}
				new.AdvanceNoticeDays = n
			}
		}
	}
	if err := setSetting(ctx, db, settingKey(apartmentID), storedJSON(new)); err != nil {
		return Settings{}, err
	}
	if err := ensurePageRow(ctx, db, apartmentID, now); err != nil {
		return Settings{}, err
	}
	_, err = db.Exec(ctx, `UPDATE property_page SET nightly_price_czk = $1, updated_at = $2 WHERE apartment_id = $3`,
		new.NightlyPriceCZK, StampAt(now), apartmentID)
	if err != nil {
		return Settings{}, err
	}
	return LoadSettings(ctx, db, apartmentID)
}

func pyEqualIntList(n int, list []int) bool {
	for _, v := range list {
		if v == n {
			return true
		}
	}
	return false
}

func icalDoneKey(apartmentID int64) string {
	return fmt.Sprintf("booking_site_ical_done:%d", apartmentID)
}

// MarkICalDone is booking_setup.mark_calendar_done.
func MarkICalDone(ctx context.Context, db DB, apartmentID int64) error {
	return setSetting(ctx, db, icalDoneKey(apartmentID), "1")
}

func icalDone(ctx context.Context, db DB, apartmentID int64) (bool, error) {
	var v *string
	err := db.QueryRow(ctx, `SELECT value FROM settings WHERE key = $1`, icalDoneKey(apartmentID)).Scan(&v)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return v != nil && *v == "1", nil
}

// NoticeValue is booking_setup.notice_value.
func NoticeValue(s Settings) string {
	if s.AdvanceNoticeDays == 0 {
		v := fmt.Sprintf("0:%d", s.SameDayCutoffHour)
		if containsStr(NoticeOptions, v) {
			return v
		}
		return "0:18"
	}
	return strconv.Itoa(s.AdvanceNoticeDays)
}
