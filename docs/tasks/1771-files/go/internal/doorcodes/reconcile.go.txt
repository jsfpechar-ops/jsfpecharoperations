package doorcodes

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// Ports reconcile, _phase, _issue_due, _revive_unissued_expired, _expire_ended_stays,
// _resolve_unverified_cards and on_registration_complete from App/app/door_codes.py (lines 1511-1699).
// The phase-2 functions (_handle_cancellations, _handle_moves) and check_lock_clocks,
// _budget_alerts, _alert_delayed live in lifecycle_clock.go and reconcile_alerts.go.

// lifecycleOps is the phase-2 part of the reconcile tick. The phase-2 Lifecycle type (lifecycle_revoke.go,
// lifecycle_cancel.go) is wired here by the integrator. Each method is one _handle_* function.
type lifecycleOps interface {
	HandleCancellations(ctx context.Context, nowISO string) error
	HandleMoves(ctx context.Context, nowISO string) error
}

// BudgetCounter is the part of ttlock.PGBudget that _budget_alerts reads (calls_this_month).
type BudgetCounter interface {
	CallsThisMonth(ctx context.Context) (int64, error)
}

// LockClock is the TTLock clock calls of check_lock_clocks. *ttlock.Client satisfies it.
type LockClock interface {
	QueryLockTime(ctx context.Context, accountID int64, lockID string) (int64, error)
	AdjustLockTime(ctx context.Context, accountID int64, lockID string) (int64, error)
}

// DelayedNotifier is the notice side of _alert_delayed: the host mail (support in copy, never the
// guest) and the push. The mail drain is Service.Mailer.Drain.
type DelayedNotifier interface {
	// DoorCodeDelayedNotice is mail_notify.door_code_delayed_notice(reservation_id, reason).
	DoorCodeDelayedNotice(ctx context.Context, reservationID int64, reason string) error
	// DoorCodeMissing is push.door_code_missing(reservation_id).
	DoorCodeMissing(ctx context.Context, reservationID int64) error
}

// Reconciler is the reconcile tick (door_codes.reconcile) with the collaborators that
// reconcile needs beyond Service. The integrator fills every field; a nil one makes its phase fail
// (logged), the other phases still run.
type Reconciler struct {
	Svc         *Service
	Lifecycle   lifecycleOps
	Budget      BudgetCounter
	BudgetLimit int64 // TTLOCK_MONTHLY_CALLS; zero or less turns the budget alerts off
	Locks       LockClock
	Delayed     DelayedNotifier
}

// ReconcileCounts is the summary reconcile returns (the Python dict; clock keys included).
type ReconcileCounts struct {
	Created       int
	Issued        int
	Failed        int
	Expired       int
	Delayed       int
	ClockChecked  int
	ClockAdjusted int
}

// Total is the sum of all counts. The job returns it as its count (Python logs the dict when any value is set).
func (c ReconcileCounts) Total() int {
	return c.Created + c.Issued + c.Failed + c.Expired + c.Delayed + c.ClockChecked + c.ClockAdjusted
}

// releaseReasons is RELEASE_REASONS in Python order (the keys of RELEASE_RETRY_MINUTES).
var releaseReasons = []string{"not_eligible", "no_account", "bad_window"}

// errNoLifecycle is returned by the phases that need the phase-2 Lifecycle when it is not wired.
var errNoLifecycle = errors.New("door_codes: lifecycle operations are not wired")

// issueCounts is what _issue_due returns.
type issueCounts struct {
	created int
	issued  int
}

// reviveRow is one row of _revive_unissued_expired's candidate query.
type reviveRow struct {
	ID           int64
	DateFrom     string
	DateTo       string
	CheckinHour  *int64
	CheckoutHour *int64
	OwnerUserID  int64
}

// Reconcile is door_codes.reconcile: the periodic tick. Phases run in Python's order. A phase that
// fails is logged and the rest run; the returned error is only from the steps Python does not wrap
// (the unsent-mail query and the lease, expiry and failed-count statements).
func (r *Reconciler) Reconcile(ctx context.Context) (ReconcileCounts, error) {
	var c ReconcileCounts
	s := r.Svc
	if !s.Settings.Enabled {
		return c, nil
	}
	nowISO := iso(s.Clock.Now())

	_ = r.runPhase("expire_ended", func() error {
		n, err := r.expireEndedStays(ctx, nowISO)
		c.Expired += n
		return err
	})
	_ = r.runPhase("revive_expired", func() error {
		_, err := r.reviveUnissuedExpired(ctx)
		return err
	})

	// Issuing comes first: a guest is waiting on it, and cancellations or moves
	// (which call the gateway, up to 35 s each) must never hold it up.
	var due issueCounts
	if r.runPhase("issue_due", func() (err error) {
		due, err = r.issueDue(ctx, nowISO)
		return err
	}) == nil {
		c.Created += due.created
		c.Issued += due.issued
	}

	unsent, err := r.queryIDs(ctx,
		"SELECT id FROM door_code WHERE state = $1 AND notified_at IS NULL "+
			"AND issued_at IS NOT NULL ORDER BY issued_at LIMIT $2",
		StateIssued, Batch)
	if err != nil {
		return c, err
	}
	for _, id := range unsent {
		s.SendCodeMail(ctx, id)
	}

	r.lifecyclePhase("cancellations", func(l lifecycleOps) error { return l.HandleCancellations(ctx, nowISO) })
	r.lifecyclePhase("moves", func(l lifecycleOps) error { return l.HandleMoves(ctx, nowISO) })

	leaseCutoff := iso(s.Clock.Now().Add(-LeaseMinutes * time.Minute))
	if _, err := s.exec(ctx,
		"UPDATE door_code SET state = $1, claimed_at = NULL, next_attempt_at = $2, updated_at = $2 "+
			"WHERE state = $3 AND claimed_at IS NOT NULL AND claimed_at < $4",
		StateRetrying, nowISO, StateIssuing, leaseCutoff); err != nil {
		return c, err
	}

	expired, err := s.exec(ctx,
		"UPDATE door_code SET state = $1, updated_at = $2 WHERE state = $3 AND valid_to IS NOT NULL AND valid_to < $2",
		StateExpired, nowISO, StateIssued)
	if err != nil {
		return c, err
	}
	c.Expired += int(expired)

	_ = r.runPhase("unverified_cards", func() error { return r.resolveUnverifiedCards(ctx) })

	var failed int64
	if err := s.Pool.QueryRow(ctx, "SELECT COUNT(*) FROM door_code WHERE state = $1", StateFailed).Scan(&failed); err != nil {
		return c, err
	}
	c.Failed = int(failed)

	var delayed int
	if r.runPhase("delayed_alerts", func() (err error) {
		delayed, err = r.alertDelayed(ctx)
		return err
	}) == nil {
		c.Delayed = delayed
	}

	var clock clockCounts
	if r.runPhase("lock_clocks", func() (err error) {
		clock, err = r.checkLockClocks(ctx)
		return err
	}) == nil {
		c.ClockChecked = clock.checked
		c.ClockAdjusted = clock.adjusted
	}

	_ = r.runPhase("budget_alerts", func() error { return r.budgetAlerts(ctx) })
	_ = r.runPhase("held_confirmations", func() error {
		_, err := s.ReleaseHeldConfirmations(ctx)
		return err
	})
	return c, nil
}

// runPhase is _phase: a failure is logged and returned, and the caller carries on.
func (r *Reconciler) runPhase(name string, fn func() error) error {
	err := fn()
	if err != nil {
		r.Svc.log().Error("door_codes reconcile phase failed", "phase", name, "error", err)
	}
	return err
}

// lifecyclePhase runs one phase-2 step through the wired Lifecycle, as a phase.
func (r *Reconciler) lifecyclePhase(name string, fn func(lifecycleOps) error) {
	_ = r.runPhase(name, func() error {
		if r.Lifecycle == nil {
			return errNoLifecycle
		}
		return fn(r.Lifecycle)
	})
}

// queryIDs runs a query whose rows are one bigint id each.
func (r *Reconciler) queryIDs(ctx context.Context, sql string, args ...any) ([]int64, error) {
	rows, err := r.Svc.Pool.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, pgx.RowTo[int64])
}

// audit writes one system audit row (db.audit with actor "system"). owner nil is NULL.
func (r *Reconciler) audit(ctx context.Context, action, detail string, owner *int64) error {
	_, err := r.Svc.exec(ctx,
		"INSERT INTO audit (at, actor, action, detail, owner_user_id) VALUES ($1, 'system', $2, $3, $4)",
		iso(r.Svc.Clock.Now()), action, detail, owner)
	return err
}

// issueDue is _issue_due: create missing rows for eligible stays, then issue the due rows in batches.
func (r *Reconciler) issueDue(ctx context.Context, nowISO string) (issueCounts, error) {
	var out issueCounts
	s := r.Svc
	missing, err := r.queryIDs(ctx,
		"SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id "+
			"WHERE "+eligibleSQL(s.Settings.Live, "$1")+
			" AND NOT EXISTS (SELECT 1 FROM door_code dc WHERE dc.reservation_id = r.id)",
		s.today())
	if err != nil {
		return out, err
	}
	for _, id := range missing {
		_, ok, err := s.EnsureRow(ctx, id)
		if err != nil {
			return out, err
		}
		if ok {
			out.created++
		}
	}

	args := []any{StatePending, StateRetrying, nowISO}
	marks := make([]string, 0, len(releaseReasons))
	for _, reason := range releaseReasons {
		args = append(args, reason)
		marks = append(marks, fmt.Sprintf("$%d", len(args)))
	}
	args = append(args, Batch)
	due, err := r.queryIDs(ctx,
		"SELECT id FROM door_code WHERE state IN ($1, $2) "+
			"AND (next_attempt_at IS NULL OR next_attempt_at <= $3) "+
			"ORDER BY CASE WHEN last_error IN ("+joinComma(marks)+") THEN 2 "+
			"WHEN attempts > 0 THEN 1 ELSE 0 END, "+
			"(next_attempt_at IS NOT NULL), next_attempt_at, id LIMIT $"+fmt.Sprint(len(args)),
		args...)
	if err != nil {
		return out, err
	}
	for _, id := range due {
		var ok bool
		if r.runPhase("issue", func() (err error) {
			ok, err = s.Issue(ctx, id, true)
			return err
		}) == nil && ok {
			out.issued++
		}
	}
	return out, nil
}

// joinComma joins placeholders with ", ".
func joinComma(parts []string) string {
	out := ""
	for i, p := range parts {
		if i > 0 {
			out += ", "
		}
		out += p
	}
	return out
}

// reviveUnissuedExpired is _revive_unissued_expired (1173c): an expired row with no lock code is
// deleted when its stay is live again, so _issue_due makes a new one in the same tick.
func (r *Reconciler) reviveUnissuedExpired(ctx context.Context) (int, error) {
	s := r.Svc
	rows, err := s.Pool.Query(ctx,
		"SELECT dc.id, r.date_from, r.date_to, a.checkin_hour, a.checkout_hour, COALESCE(a.owner_user_id, 0) "+
			"FROM door_code dc JOIN reservation r ON r.id = dc.reservation_id "+
			"JOIN apartment a ON a.id = r.apartment_id "+
			"WHERE dc.state = $1 AND dc.provider_code_id IS NULL AND "+eligibleSQL(s.Settings.Live, "$2"),
		StateExpired, s.today())
	if err != nil {
		return 0, err
	}
	cands, err := pgx.CollectRows(rows, pgx.RowToStructByPos[reviveRow])
	if err != nil {
		return 0, err
	}
	nowMS := s.Clock.Now().UnixMilli()
	revived := 0
	for _, cand := range cands {
		_, endMS, err := ttlock.StayWindow(cand.DateFrom, cand.DateTo, hourOf(cand.CheckinHour), hourOf(cand.CheckoutHour),
			s.Settings.BufferHours)
		if err != nil {
			continue
		}
		if endMS < nowMS {
			continue
		}
		ok, err := s.allowed(ctx, cand.OwnerUserID)
		if err != nil {
			return revived, err
		}
		if !ok {
			// Plan without TTLock: ensure_row would never make a new row, keep the expired one (1173d).
			continue
		}
		// Guarded: only a row that is still expired is deleted.
		removed, err := s.exec(ctx, "DELETE FROM door_code WHERE id = $1 AND state = $2", cand.ID, StateExpired)
		if err != nil {
			return revived, err
		}
		if removed > 0 {
			revived++
			if err := r.audit(ctx, "door_code_reset", fmt.Sprintf("door_code=%d", cand.ID), nil); err != nil {
				return revived, err
			}
		}
	}
	return revived, nil
}

// expireEndedStays is _expire_ended_stays (1173): pending or retrying rows of a stay whose last day
// is past become expired. Cancelled or archived stays are left to the lifecycle (revoked).
func (r *Reconciler) expireEndedStays(ctx context.Context, nowISO string) (int, error) {
	n, err := r.Svc.exec(ctx,
		"UPDATE door_code SET state = $1, claimed_at = NULL, updated_at = $2 "+
			"WHERE state IN ($3, $4) AND claimed_at IS NULL AND reservation_id IN "+
			"(SELECT id FROM reservation WHERE status = 'active' AND archived_at IS NULL AND date_to < $5)",
		StateExpired, nowISO, StatePending, StateRetrying, r.Svc.today())
	return int(n), err
}

// resolveUnverifiedCards is _resolve_unverified_cards (1173b, 1173c): closes the host cards of a stay
// whose code row has ended.
func (r *Reconciler) resolveUnverifiedCards(ctx context.Context) error {
	now := iso(r.Svc.Clock.Now())
	if _, err := r.Svc.exec(ctx,
		"UPDATE alert SET resolved_at = $1 WHERE kind = $2 AND resolved_at IS NULL "+
			"AND NOT EXISTS (SELECT 1 FROM door_code dc "+
			"WHERE dc.reservation_id = alert.reservation_id AND dc.state = $3)",
		now, "door_code_pin_unverified", StateIssued); err != nil {
		return err
	}
	_, err := r.Svc.exec(ctx,
		"UPDATE alert SET resolved_at = $1 WHERE kind = $2 AND resolved_at IS NULL "+
			"AND EXISTS (SELECT 1 FROM door_code dc "+
			"WHERE dc.reservation_id = alert.reservation_id AND dc.state IN ($3, $4))",
		now, "door_code_delayed", StateExpired, StateRevoked)
	return err
}

// OnRegistrationComplete is on_registration_complete: a guest who finished registering gets a code
// now, not at the next tick. Failures are logged, never raised.
func (s *Service) OnRegistrationComplete(ctx context.Context, reservationID int64) {
	if !s.Settings.Enabled {
		return
	}
	rowID, ok, err := s.EnsureRow(ctx, reservationID)
	if err == nil && ok {
		_, err = s.Issue(ctx, rowID, false)
	}
	if err != nil {
		s.log().Error("door code hook failed", "reservation", reservationID, "error", err)
	}
}
