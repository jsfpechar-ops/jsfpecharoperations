package ubyport

import (
	"context"
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

const completionImmediateMode = "completion_immediate"

// SubmitCompletedStayOptions lets tests inject a fake Sender, a prebuilt
// SweepDeps, or a submit hook while keeping the production gate logic intact.
// Production callers pass nil.
type SubmitCompletedStayOptions struct {
	NewSender func(*ApartmentRow) Sender
	SweepDeps *SweepDeps
	Submit    func(ctx context.Context, d SweepDeps, aptID int64, o CollectOptions, mode string) ([]BatchResult, error)
}

// SubmitCompletedStay is reporting.submit_stay_if_complete
// (App/app/reporting.py 1152-1197): refresh completion for reservationID and,
// when the apartment is in immediate mode and not auth-paused, file only the
// non-archived guests of that active reservation via SubmitForApartment with
// mode "completion_immediate" and IgnoreSchedule=true.
//
// It returns true when stay-scoped filing was invoked without an unexpected
// error. A filing exception raises the submission_immediate warning alert and
// returns (false, nil) so a committed guest/host write keeps its success flow.
func SubmitCompletedStay(
	ctx context.Context,
	pool *pgxpool.Pool,
	getenv func(string) string,
	now func() time.Time,
	apartmentID, reservationID int64,
	opts *SubmitCompletedStayOptions,
) (bool, error) {
	if now == nil {
		now = time.Now
	}
	if getenv == nil {
		getenv = func(string) string { return "" }
	}

	apt, err := LoadApartment(ctx, pool, apartmentID)
	if err != nil || apt == nil {
		return false, err
	}

	var dec FieldDecrypter
	if opts != nil && opts.SweepDeps != nil && opts.SweepDeps.Decrypt != nil {
		dec = opts.SweepDeps.Decrypt
	} else {
		dec = lazyDataDecrypter(getenv, now)
	}
	completed, err := RefreshRegistrationCompletedAt(ctx, pool, reservationID, dec, now)
	if err != nil {
		return false, err
	}
	if completed == nil || apt.AutomationMode != "immediate" {
		return false, nil
	}

	// Same pause as the sweep: retrying a refused login on every guest save
	// risks locking the police account.
	paused, err := OpenAlert(ctx, pool, fmt.Sprintf("ubyport_auth_failed:%d", apartmentID))
	if err != nil || paused {
		return false, err
	}

	var status, completedAt string
	var archived bool
	err = pool.QueryRow(ctx,
		`SELECT COALESCE(status, ''), archived_at IS NOT NULL, COALESCE(registration_completed_at, '')
		   FROM reservation WHERE id = $1 AND apartment_id = $2`,
		reservationID, apartmentID).Scan(&status, &archived, &completedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if status != "active" || archived || completedAt == "" {
		return false, nil
	}

	rows, err := pool.Query(ctx,
		`SELECT id FROM guest WHERE reservation_id = $1 AND archived_at IS NULL ORDER BY id`,
		reservationID)
	if err != nil {
		return false, err
	}
	var guestIDs []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return false, err
		}
		guestIDs = append(guestIDs, id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return false, err
	}
	// Never pass an empty OnlyGuestIDs to SubmitForApartment: LoadGuests treats
	// an empty slice as apartment-wide scope.
	if len(guestIDs) == 0 {
		return false, nil
	}

	if err := runImmediateStaySubmit(ctx, pool, getenv, now, apartmentID, guestIDs, opts); err != nil {
		name := apt.Ref.InternalName
		log.Printf("ubyport: immediate submit failed apartment_id=%d reservation_id=%d: %v", apartmentID, reservationID, err)
		if alertErr := RaiseAlert(ctx, pool, "warning", "submission_immediate",
			fmt.Sprintf("%s: automatic send failed after registration completed.", name),
			err.Error(),
			fmt.Sprintf("submission_immediate:%d", apartmentID),
			&apartmentID, nil, nil,
			AlertParams{"property": name, "error": err.Error()},
		); alertErr != nil {
			log.Printf("ubyport: immediate submit alert failed apartment_id=%d reservation_id=%d: %v", apartmentID, reservationID, alertErr)
		}
		return false, nil
	}
	return true, nil
}

func runImmediateStaySubmit(
	ctx context.Context,
	pool *pgxpool.Pool,
	getenv func(string) string,
	now func() time.Time,
	apartmentID int64,
	guestIDs []int64,
	opts *SubmitCompletedStayOptions,
) error {
	var d SweepDeps
	if opts != nil && opts.SweepDeps != nil {
		d = *opts.SweepDeps
	} else {
		keys, err := secure.LoadDataKeys(getenv)
		if err != nil {
			return err
		}
		d, err = NewSweepDeps(ctx, pool, keys, getenv)
		if err != nil {
			return err
		}
	}
	if d.Batch.Now == nil {
		d.Batch.Now = now
	}
	if opts != nil && opts.NewSender != nil {
		d.NewSender = opts.NewSender
	}
	yes := true
	collectOpts := CollectOptions{
		OnlyGuestIDs:   guestIDs,
		IgnoreSchedule: &yes,
		Now:            now,
	}
	submitFn := SubmitForApartment
	if opts != nil && opts.Submit != nil {
		submitFn = opts.Submit
	}
	_, err := submitFn(ctx, d, apartmentID, collectOpts, completionImmediateMode)
	return err
}

func lazyDataDecrypter(getenv func(string) string, now func() time.Time) FieldDecrypter {
	var keys *secure.MultiFernet
	return func(token string) (string, error) {
		if token == "" {
			return "", nil
		}
		if keys == nil {
			k, err := secure.LoadDataKeys(getenv)
			if err != nil {
				return "", err
			}
			keys = k
		}
		b, err := keys.Decrypt(token, 0, now())
		return string(b), err
	}
}
