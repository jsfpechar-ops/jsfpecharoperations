package staydetail

import (
	"context"
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/scheduler"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// enqueueJob adds a due job row unless one of that kind is open; tests replace it.
var enqueueJob = scheduler.Enqueue

// submitStayIfComplete is reporting.submit_stay_if_complete (reporting.py
// 1151-1196) up to the send. Python then files inside the request; Go enqueues
// the existing "submit" job (the INSERT of jobqueue.enqueue), whose sweep files
// the stay: DueForAutomaticSend is true at once for an immediate apartment with
// a completion stamp. Filing stays in the sweep, the one Go filing path. It
// returns true when the job row was requested.
func submitStayIfComplete(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, apartmentID, reservationID int64) (bool, error) {
	var mode, name string
	err := pool.QueryRow(ctx,
		`SELECT COALESCE(automation_mode, ''), COALESCE(internal_name, '') FROM apartment WHERE id = $1`,
		apartmentID).Scan(&mode, &name)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	completed, err := ubyport.RefreshRegistrationCompletedAt(ctx, pool, reservationID, saveDecrypter(getenv), now)
	if err != nil {
		return false, err
	}
	if completed == nil || mode != "immediate" {
		return false, nil
	}
	// Same pause as the sweep: retrying a refused login on every save risks
	// locking the police account.
	paused, err := ubyport.OpenAlert(ctx, pool, fmt.Sprintf("ubyport_auth_failed:%d", apartmentID))
	if err != nil || paused {
		return false, err
	}
	var status string
	err = pool.QueryRow(ctx, `SELECT COALESCE(status, '') FROM reservation WHERE id = $1`, reservationID).Scan(&status)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if status != "active" {
		return false, nil
	}
	if _, err := enqueueJob(ctx, pool, "submit"); err != nil {
		log.Printf("stay save: submit enqueue apartment_id=%d: %v", apartmentID, err)
		return false, ubyport.RaiseAlert(ctx, pool, "warning", "submission_immediate",
			name+": automatic send failed after registration completed.", err.Error(),
			fmt.Sprintf("submission_immediate:%d", apartmentID), &apartmentID, nil, nil,
			ubyport.AlertParams{"property": name, "error": err.Error()})
	}
	return true, nil
}

// saveDecrypter opens stored guest fields with the data keys, loaded on first use.
func saveDecrypter(getenv func(string) string) ubyport.FieldDecrypter {
	var keys *secure.MultiFernet
	return func(token string) (string, error) {
		if keys == nil {
			k, err := secure.LoadDataKeys(getenv)
			if err != nil {
				return "", err
			}
			keys = k
		}
		b, err := keys.Decrypt(token, 0, time.Now())
		return string(b), err
	}
}
