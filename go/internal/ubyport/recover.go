package ubyport

// recover.go is reporting.recover_stale_submissions (App/app/reporting.py
// 1851-1912) and the completion step of reporting.refresh_registration_completed_at
// (923-972). A batch left running after a crash is judged stale by its send
// claim, not by row age; a stale batch becomes outcome_unknown and its guests
// point at it. Each stale batch is its own transaction, all under the
// submit_apartment advisory lock, as in Python.

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// staleSubmissionReason is STALE_SUBMISSION_REASON (reporting.py 64).
const staleSubmissionReason = "The send stopped before UbyPort answered."

// lockSubmitApartment takes the submit_apartment advisory lock, as db.lock_key does.
func lockSubmitApartment(ctx context.Context, tx pgx.Tx, aptID int64) error {
	_, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "submit_apartment", int32(aptID))
	return err
}

// parseGuestIDs reads a guest_ids JSON text array; empty or NULL means none.
func parseGuestIDs(raw *string) ([]int64, error) {
	if raw == nil || *raw == "" {
		return []int64{}, nil
	}
	var ids []int64
	if err := json.Unmarshal([]byte(*raw), &ids); err != nil {
		return nil, err
	}
	if ids == nil {
		ids = []int64{}
	}
	return ids, nil
}

// RecoverStaleSubmissions marks the running batches of one apartment whose
// guests hold no live claim (claimed_at within the last 300 s) as
// outcome_unknown, points their guests at them, and raises one critical alert
// when anything was stale. It returns the number of stale batches. now is a
// parameter so tests can pin it.
func RecoverStaleSubmissions(ctx context.Context, pool *pgxpool.Pool, aptID int64, now func() time.Time) (int, error) {
	liveAfter := float64(now().UnixNano())/1e9 - SubmissionClaimTTL.Seconds()

	type candidate struct {
		id       int64
		guestIDs []int64
	}
	var candidates []candidate

	// One transaction for the scan.
	err := withTx(ctx, pool, func(tx pgx.Tx) error {
		if err := lockSubmitApartment(ctx, tx, aptID); err != nil {
			return err
		}
		rows, err := tx.Query(ctx,
			`SELECT id, guest_ids FROM submission WHERE apartment_id = $1 AND state = 'running' ORDER BY id`,
			aptID)
		if err != nil {
			return err
		}
		type running struct {
			id  int64
			raw *string
		}
		var list []running
		for rows.Next() {
			var r running
			if err := rows.Scan(&r.id, &r.raw); err != nil {
				rows.Close()
				return err
			}
			list = append(list, r)
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return err
		}
		for _, r := range list {
			guestIDs, err := parseGuestIDs(r.raw)
			if err != nil {
				return err
			}
			if len(guestIDs) > 0 {
				var live int
				err := tx.QueryRow(ctx,
					`SELECT 1 FROM submission_claim WHERE guest_id = ANY($1) AND claimed_at >= $2 LIMIT 1`,
					guestIDs, liveAfter).Scan(&live)
				if err == nil {
					continue
				}
				if err != pgx.ErrNoRows {
					return err
				}
			}
			candidates = append(candidates, candidate{id: r.id, guestIDs: guestIDs})
		}
		return nil
	})
	if err != nil {
		return 0, err
	}

	var stale []int64
	for _, c := range candidates {
		err := withTx(ctx, pool, func(tx pgx.Tx) error {
			if err := lockSubmitApartment(ctx, tx, aptID); err != nil {
				return err
			}
			if _, err := tx.Exec(ctx,
				`UPDATE submission SET state = 'outcome_unknown', finished_at = $1, error_text = $2 WHERE id = $3`,
				UTCNow(), staleSubmissionReason, c.id); err != nil {
				return err
			}
			for _, guestID := range c.guestIDs {
				if _, err := tx.Exec(ctx,
					`UPDATE guest SET submission_id = $1 WHERE id = $2 AND submit_state != 'sent'
					 AND (submission_id IS NULL OR submission_id < $1)`,
					c.id, guestID); err != nil {
					return err
				}
			}
			return nil
		})
		if err != nil {
			return 0, err
		}
		stale = append(stale, c.id)
	}

	if len(stale) == 0 {
		return 0, nil
	}
	var name string
	if err := pool.QueryRow(ctx, `SELECT internal_name FROM apartment WHERE id = $1`, aptID).Scan(&name); err != nil {
		return 0, err
	}
	message := fmt.Sprintf("%s: UbyPort may or may not have received the report.", name)
	apt := aptID
	if err := RaiseAlert(ctx, pool, "critical", "submission_outcome_unknown", message, staleSubmissionReason,
		fmt.Sprintf("submission_outcome_unknown:%d", aptID), &apt, nil, nil,
		AlertParams{"property": name, "error": staleSubmissionReason}); err != nil {
		return 0, err
	}
	log.Printf("ubyport_submission_stale apartment_id=%d submissions=%v", aptID, stale)
	return len(stale), nil
}

// RefreshRegistrationCompletedAt is reporting.refresh_registration_completed_at
// (reporting.py 923-972). A stay is complete when its declared headcount is
// filled, or when every form on file is complete and no form was touched for
// 12 hours. The first such instant is stored; a stay with an incomplete form
// loses a stored stamp. A guest filed by hand counts as complete. It returns the
// stored stamp, nil for none.
func RefreshRegistrationCompletedAt(ctx context.Context, pool *pgxpool.Pool, reservationID int64, decrypt FieldDecrypter, now func() time.Time) (*string, error) {
	var dateFrom, dateTo string
	var existing *string
	var override, declared *int64
	err := pool.QueryRow(ctx,
		`SELECT COALESCE(date_from,''), COALESCE(date_to,''), registration_completed_at,
		        expected_guests_override, declared_guests
		   FROM reservation WHERE id = $1`, reservationID,
	).Scan(&dateFrom, &dateTo, &existing, &override, &declared)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if existing != nil && *existing == "" {
		existing = nil
	}
	// expected_guest_count: the host override wins when it is truthy.
	expected := declared
	if override != nil && *override != 0 {
		expected = override
	}

	guests, err := LoadGuests(ctx, pool, GuestScope{ReservationID: reservationID}, decrypt)
	if err != nil {
		return nil, err
	}
	today := reportingToday(now())
	filled := 0
	allComplete := true
	for _, c := range guests {
		if (c.submitState == collectGuestSent && c.manualFiled != "") ||
			validation.GuestIsComplete(c.row, dateFrom, dateTo, today) {
			filled++
		} else {
			allComplete = false
		}
	}
	declaredFilled := expected != nil && int64(filled) >= *expected && allComplete

	// _forms_quiet_for: the newest guest stamp (updated_at, else created_at),
	// compared as stored text, then read as UTC; quiet for 12 hours.
	quiet := false
	if len(guests) > 0 && allComplete {
		rows, err := pool.Query(ctx,
			`SELECT COALESCE(NULLIF(updated_at,''), NULLIF(created_at,''))
			   FROM guest WHERE reservation_id = $1 AND archived_at IS NULL`, reservationID)
		if err != nil {
			return nil, err
		}
		var newest string
		for rows.Next() {
			var stamp *string
			if err := rows.Scan(&stamp); err != nil {
				rows.Close()
				return nil, err
			}
			if stamp != nil && *stamp > newest {
				newest = *stamp
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return nil, err
		}
		if newest != "" {
			if t, ok := parseStoredUTC(newest); ok {
				quiet = now().Sub(t) >= 12*time.Hour
			}
		}
	}
	formsSettled := len(guests) > 0 && allComplete && quiet
	complete := declaredFilled || formsSettled

	if complete && existing == nil {
		if _, err := pool.Exec(ctx,
			`UPDATE reservation SET registration_completed_at = $1, updated_at = $2
			  WHERE id = $3 AND registration_completed_at IS NULL`,
			UTCNow(), UTCNow(), reservationID); err != nil {
			return nil, err
		}
		if err := pool.QueryRow(ctx,
			`SELECT registration_completed_at FROM reservation WHERE id = $1`, reservationID,
		).Scan(&existing); err != nil {
			return nil, err
		}
	} else if !complete && existing != nil && !allComplete {
		// Only a form that is actually missing un-completes a stay.
		if _, err := pool.Exec(ctx,
			`UPDATE reservation SET registration_completed_at = NULL, updated_at = $1 WHERE id = $2`,
			UTCNow(), reservationID); err != nil {
			return nil, err
		}
		existing = nil
	}
	return existing, nil
}
