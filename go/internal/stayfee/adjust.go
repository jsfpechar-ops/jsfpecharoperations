package stayfee

// The write side of App/app/stay_fee_adjustment.py (brief 1242): add and
// reverse. Python writes no audit row in either; the routes do.

import (
	"context"
	"time"
)

// AdjustmentInput is stay_fee_adjustment.add's keyword arguments. Direction is
// "add" or "remove", Mode "people" or "bed_days" (CHECK constraints in the
// schema). PeopleCount and Nights 0 are stored as NULL, as Python's "or None".
type AdjustmentInput struct {
	ApartmentID int64
	PeriodKey   string
	Direction   string
	Mode        string
	PeopleCount int
	Nights      int
	BedDays     int
	Reason      string
	CreatedBy   int64
}

func zeroNull(v int) any {
	if v == 0 {
		return nil
	}
	return v
}

// AddAdjustment is stay_fee_adjustment.add: insert one correction and return
// its id. The reason is encrypted like db.encrypt_field: an empty reason is
// NULL, which the NOT NULL column refuses, as in Python.
func AddAdjustment(ctx context.Context, db DB, enc Encrypter, in AdjustmentInput, now time.Time) (int64, error) {
	var reason any
	if in.Reason != "" {
		token, err := enc([]byte(in.Reason))
		if err != nil {
			return 0, err
		}
		reason = token
	}
	var id int64
	err := db.QueryRow(ctx, `INSERT INTO stay_fee_adjustment (apartment_id, period_key, direction, mode,
		people_count, nights, bed_days, reason_enc, created_by, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING id`,
		in.ApartmentID, in.PeriodKey, in.Direction, in.Mode, zeroNull(in.PeopleCount), zeroNull(in.Nights),
		in.BedDays, reason, in.CreatedBy, UTCStamp(now)).Scan(&id)
	return id, err
}

// ReverseAdjustment is stay_fee_adjustment.reverse: mark one correction
// reversed. Like db.update it does not check that a row matched.
func ReverseAdjustment(ctx context.Context, db DB, adjustmentID, actorID int64, now time.Time) error {
	_, err := db.Exec(ctx, `UPDATE stay_fee_adjustment SET reversed_at = $1, reversed_by = $2 WHERE id = $3`,
		UTCStamp(now), actorID, adjustmentID)
	return err
}
