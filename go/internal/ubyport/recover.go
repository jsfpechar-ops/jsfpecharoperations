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
	"fmt"
	"log"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
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
