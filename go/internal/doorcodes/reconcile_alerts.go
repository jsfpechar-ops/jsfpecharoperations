package doorcodes

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

// Ports _budget_alerts and _alert_delayed from App/app/door_codes.py (lines 1441-1510).

// delayedRow is one row of _alert_delayed's query.
type delayedRow struct {
	ReservationID int64
	DateFrom      string
	ApartmentID   int64
	InternalName  *string
	OwnerUserID   int64
	LastError     *string
	HasRow        bool
}

// budgetAlerts is _budget_alerts: a host alert at 80 % and 95 % of the monthly TTLock calls.
func (r *Reconciler) budgetAlerts(ctx context.Context) error {
	if r.Budget == nil {
		return errors.New("door_codes: TTLock budget is not wired")
	}
	used, err := r.Budget.CallsThisMonth(ctx)
	if err != nil {
		return err
	}
	limit := r.BudgetLimit
	if limit <= 0 {
		return nil
	}
	month := r.Svc.Clock.Now().UTC().Format("2006-01")
	params := func(percent int64) map[string]any {
		return map[string]any{"percent": percent, "used": used, "limit": limit}
	}
	switch {
	case float64(used) >= 0.95*float64(limit):
		return r.Svc.Alerts.Raise(ctx, Alert{
			Level:     "critical",
			Kind:      "ttlock_budget",
			Message:   "TTLock calls 95 %",
			DedupeKey: fmt.Sprintf("ttlock_budget:%s:95", month),
			Params:    params(95),
		})
	case float64(used) >= 0.8*float64(limit):
		return r.Svc.Alerts.Raise(ctx, Alert{
			Level:     "warning",
			Kind:      "ttlock_budget",
			Message:   "TTLock calls 80 %",
			DedupeKey: fmt.Sprintf("ttlock_budget:%s:80", month),
			Params:    params(80),
		})
	}
	return nil
}

// alertDelayed is _alert_delayed: every registered stay still without a code (past DelayMinutes)
// raises a host alert, one host mail and one push. It returns how many stays matched, whether or not
// the owner may hold a code, as the Python len(rows) does.
func (r *Reconciler) alertDelayed(ctx context.Context) (int, error) {
	s := r.Svc
	if r.Delayed == nil {
		return 0, errors.New("door_codes: delayed notifier is not wired")
	}
	cutoff := iso(s.Clock.Now().Add(-time.Duration(DelayMinutes) * time.Minute))
	today := s.today()
	sql := "SELECT r.id AS reservation_id, r.date_from, a.id AS apartment_id, " +
		"a.internal_name, COALESCE(a.owner_user_id, 0) AS owner_user_id, dc.last_error, (dc.id IS NOT NULL) AS has_row " +
		"FROM reservation r JOIN apartment a ON a.id = r.apartment_id " +
		"LEFT JOIN door_code dc ON dc.reservation_id = r.id " +
		"WHERE a.lock_provider = 'ttlock' AND r.status = 'active' " +
		"AND r.archived_at IS NULL AND r.registration_completed_at IS NOT NULL " +
		"AND r.registration_completed_at < $1 AND r.date_to >= $2 " +
		"AND COALESCE(r.source, '') != 'demo' " +
		"AND (dc.id IS NULL OR dc.state IN ($3, $4, $5))"
	if !s.Settings.Live {
		sql += " AND r.source = 'manual'"
	}
	rows, err := s.Pool.Query(ctx, sql, cutoff, today, StatePending, StateIssuing, StateRetrying)
	if err != nil {
		return 0, err
	}
	list, err := pgx.CollectRows(rows, pgx.RowToStructByPos[delayedRow])
	if err != nil {
		return 0, err
	}
	for _, row := range list {
		ok, err := s.allowed(ctx, row.OwnerUserID)
		if err != nil {
			return 0, err
		}
		if !ok {
			continue
		}
		reason := strings.TrimSpace(derefOr(row.LastError, ""))
		if reason == "" {
			reason = "not_set_up"
			if row.HasRow {
				reason = "waiting"
			}
		}
		// The Alert type has no detail column yet, so the reason travels in params (see the port notes).
		if err := s.Alerts.Raise(ctx, Alert{
			Level:         "warning",
			Kind:          "door_code_delayed",
			Message:       "Door code is taking too long",
			DedupeKey:     fmt.Sprintf("door_code_delayed:%d", row.ReservationID),
			ApartmentID:   row.ApartmentID,
			ReservationID: row.ReservationID,
			Params: map[string]any{
				"property": derefOr(row.InternalName, ""),
				"date":     row.DateFrom,
				"detail":   "reason=" + reason,
			},
		}); err != nil {
			return 0, err
		}
		s.log().Error(fmt.Sprintf("DOOR_CODE_PROBLEM stage=delayed reservation=%d reason=%s", row.ReservationID, reason))
		// One mail to the host (support in copy), once per stay. Never to the guest.
		if err := r.Delayed.DoorCodeDelayedNotice(ctx, row.ReservationID, reason); err != nil {
			return 0, err
		}
		if err := r.Delayed.DoorCodeMissing(ctx, row.ReservationID); err != nil {
			return 0, err
		}
		if err := s.Mailer.Drain(ctx, 4); err != nil {
			return 0, err
		}
	}
	return len(list), nil
}
