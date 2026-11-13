package stayfee

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"
)

// PeriodKey is stay_fee_filing.period_key: "2026-Q3" or "2026-08".
func PeriodKey(cadence string, month time.Time) string {
	if cadence == "quarterly" {
		return fmt.Sprintf("%04d-Q%d", month.Year(), (int(month.Month())-1)/3+1)
	}
	return MonthKey(month)
}

// OverlapKeys is stay_fee_filing.overlap_keys: the period keys whose dates
// intersect the period of cadence containing month.
func OverlapKeys(cadence string, month time.Time) []string {
	if cadence == "quarterly" {
		first, _ := PeriodBounds("quarterly", month)
		keys := []string{PeriodKey("quarterly", first)}
		for offset := 0; offset < 3; offset++ {
			keys = append(keys, MonthKey(ShiftMonth(first, offset)))
		}
		return keys
	}
	return []string{PeriodKey("monthly", month), PeriodKey("quarterly", month)}
}

// PeriodAnchor is stay_fee_filing.period_anchor: the first day of the period a
// filing row was sealed for. A malformed key is an error (Python ValueError).
func PeriodAnchor(key string) (time.Time, error) {
	if strings.Contains(key, "-Q") {
		parts := strings.Split(key, "-Q")
		if len(parts) != 2 {
			return time.Time{}, fmt.Errorf("bad period key %s", key)
		}
		year, err1 := strconv.Atoi(parts[0])
		quarter, err2 := strconv.Atoi(parts[1])
		if err1 != nil || err2 != nil || year < 1 || quarter < 1 || quarter > 4 {
			return time.Time{}, fmt.Errorf("bad period key %s", key)
		}
		return Day(year, time.Month((quarter-1)*3+1), 1), nil
	}
	parsed, ok := ParseMonth(key)
	if !ok {
		return time.Time{}, fmt.Errorf("bad period key %s", key)
	}
	return parsed, nil
}

// FilingRow is a stay_fee_filing row without the encrypted PDF and CSV blobs.
// PayloadEnc is the Fernet token of the sealed payload. Empty string is NULL.
type FilingRow struct {
	ID                int64
	ApartmentID       int64
	PeriodKey         string
	Version           int
	Cadence           string
	RateCZK           int
	LiableDays        int
	ExemptDays        int
	TotalDueCZK       int
	TotalCollectedCZK int
	PayloadEnc        string
	CreatedAt         string
	SupersededAt      string
	SentAt            string
	SentMessageID     string
	PaidAt            string
}

const filingColumns = `id, apartment_id, period_key, version, cadence, rate_czk, liable_days, exempt_days,
	total_due_czk, total_collected_czk, COALESCE(payload_enc, ''), created_at, COALESCE(superseded_at, ''),
	COALESCE(sent_at, ''), COALESCE(sent_message_id, ''), COALESCE(paid_at, '')`

func queryFiling(ctx context.Context, q Querier, sql string, args ...any) (*FilingRow, error) {
	rows, err := q.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	if !rows.Next() {
		return nil, rows.Err()
	}
	var f FilingRow
	if err := rows.Scan(&f.ID, &f.ApartmentID, &f.PeriodKey, &f.Version, &f.Cadence, &f.RateCZK, &f.LiableDays,
		&f.ExemptDays, &f.TotalDueCZK, &f.TotalCollectedCZK, &f.PayloadEnc, &f.CreatedAt, &f.SupersededAt,
		&f.SentAt, &f.SentMessageID, &f.PaidAt); err != nil {
		return nil, err
	}
	return &f, nil
}

// activeFiling is stay_fee_filing._active: the newest live filing among keys.
func activeFiling(ctx context.Context, q Querier, apartmentID int64, keys []string) (*FilingRow, error) {
	if len(keys) == 0 {
		return nil, nil
	}
	return queryFiling(ctx, q, `SELECT `+filingColumns+` FROM stay_fee_filing
		WHERE apartment_id = $1 AND superseded_at IS NULL AND period_key = ANY($2)
		ORDER BY created_at DESC, id DESC LIMIT 1`, apartmentID, keys)
}

// Covering is stay_fee_filing.covering: the newest sealed filing whose period
// contains month, either cadence. nil, nil when there is none.
func Covering(ctx context.Context, q Querier, apartmentID int64, month time.Time) (*FilingRow, error) {
	return activeFiling(ctx, q, apartmentID, OverlapKeys("monthly", month))
}

// ForeignOverlap is stay_fee_filing.foreign_overlap: a sealed filing that
// intersects this period but is not this period itself.
func ForeignOverlap(ctx context.Context, q Querier, apartmentID int64, cadence string, month time.Time) (*FilingRow, error) {
	own := PeriodKey(cadence, month)
	var keys []string
	for _, k := range OverlapKeys(cadence, month) {
		if k != own {
			keys = append(keys, k)
		}
	}
	return activeFiling(ctx, q, apartmentID, keys)
}

// Latest is stay_fee_filing.latest: the live filing of one period key, newest version.
func Latest(ctx context.Context, q Querier, apartmentID int64, key string) (*FilingRow, error) {
	return queryFiling(ctx, q, `SELECT `+filingColumns+` FROM stay_fee_filing
		WHERE apartment_id = $1 AND period_key = $2 AND superseded_at IS NULL
		ORDER BY version DESC LIMIT 1`, apartmentID, key)
}

// CorrectionRateFor is stay_fee_filing.correction_rate over a loaded schedule:
// the sealed flat rate when every night of the sealed period had one rate, nil
// (priced per night again) when the period spans a rate change.
func CorrectionRateFor(schedule []RateStep, row *FilingRow) (*int, error) {
	anchor, err := PeriodAnchor(row.PeriodKey)
	if err != nil {
		return nil, err
	}
	first, last := PeriodBounds(row.Cadence, anchor)
	if !IsUniform(schedule, first, last) {
		return nil, nil
	}
	rate := row.RateCZK
	return &rate, nil
}

// CorrectionRate loads the apartment's schedule and calls CorrectionRateFor.
// scheduleToday is Python's date.today() default of schedule_for.
func CorrectionRate(ctx context.Context, q Querier, ap *Apartment, row *FilingRow, scheduleToday time.Time) (*int, error) {
	schedule, err := LoadSchedule(ctx, q, ap, scheduleToday)
	if err != nil {
		return nil, err
	}
	return CorrectionRateFor(schedule, row)
}

type sealedPayload struct {
	Lines        []Line   `json:"lines"`
	RateSegments [][2]int `json:"rate_segments"`
}

// FrozenSummary is stay_fee_filing.frozen_summary: the Period shape for a
// sealed row. dec decrypts the sealed payload; the lines and rate segments come
// from it, the totals from the row.
func FrozenSummary(row *FilingRow, ap *Apartment, dec Decrypter) (*Period, error) {
	anchor, err := PeriodAnchor(row.PeriodKey)
	if err != nil {
		return nil, err
	}
	first, last := PeriodBounds(row.Cadence, anchor)
	var sealed sealedPayload
	if row.PayloadEnc != "" {
		plain, err := dec(row.PayloadEnc)
		if err != nil {
			return nil, err
		}
		if plain != "" {
			if err := json.Unmarshal([]byte(plain), &sealed); err != nil {
				return nil, fmt.Errorf("stayfee: filing %d payload: %w", row.ID, err)
			}
		}
	}
	if sealed.Lines == nil {
		sealed.Lines = []Line{}
	}
	if len(sealed.RateSegments) == 0 {
		sealed.RateSegments = [][2]int{{row.RateCZK, row.LiableDays}}
	}
	return &Period{
		Apartment: ap, Cadence: row.Cadence, First: first, Last: last,
		Label: PeriodLabelCS(row.Cadence, anchor), PeriodKey: row.PeriodKey, RateCZK: row.RateCZK,
		Lines: sealed.Lines, RateSegments: sealed.RateSegments, LiableNights: row.LiableDays,
		ExemptNights: row.ExemptDays, TotalCZK: row.TotalDueCZK, Frozen: true, FilingID: row.ID,
		Version: row.Version, TotalCollectedCZK: row.TotalCollectedCZK, SentAt: row.SentAt, PaidAt: row.PaidAt,
		SentMessageID: row.SentMessageID,
	}, nil
}
