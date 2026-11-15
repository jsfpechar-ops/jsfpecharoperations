package doorcodes

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// Ports check_lock_clocks from App/app/door_codes.py (lines 1374-1440). It checks at most one
// lock per tick, and each lock at most once in seven days.

// clockDriftMS is the drift that makes the clock adjusted (120 s).
const clockDriftMS = 120_000

// clockCounts is what check_lock_clocks returns.
type clockCounts struct {
	checked  int
	adjusted int
}

// clockLock is one distinct (owner, lock) pair of the apartments on TTLock.
type clockLock struct {
	OwnerUserID int64
	LockID      string
}

// clockSample is the first apartment on a lock, named in the warning when the clock cannot be checked.
type clockSample struct {
	ID           int64
	InternalName *string
}

// clockRetryKinds are the TTLock error kinds that only retry later (the row is checked again in 1 day).
var clockRetryKinds = []string{ttlock.KindOffline, ttlock.KindTransient, ttlock.KindNetwork, ttlock.KindRate, ttlock.KindBudget}

// checkLockClocks is check_lock_clocks. A TTLock error is handled per lock; any other error is
// returned and the phase logs it.
func (r *Reconciler) checkLockClocks(ctx context.Context) (clockCounts, error) {
	var out clockCounts
	s := r.Svc
	now := s.Clock.Now()
	nowISO := iso(now)
	nowMS := now.UnixMilli()

	rows, err := s.Pool.Query(ctx,
		"SELECT DISTINCT COALESCE(a.owner_user_id, 0) AS owner_user_id, a.lock_id FROM apartment a "+
			"WHERE a.lock_provider = 'ttlock' AND a.lock_id IS NOT NULL")
	if err != nil {
		return out, err
	}
	locks, err := pgx.CollectRows(rows, pgx.RowToStructByPos[clockLock])
	if err != nil {
		return out, err
	}

	for _, lk := range locks {
		allowed, err := s.allowed(ctx, lk.OwnerUserID)
		if err != nil {
			return out, err
		}
		if !allowed {
			continue
		}
		acc, err := s.Accounts.ForOwner(ctx, lk.OwnerUserID)
		if err != nil {
			return out, err
		}
		if acc == nil || acc.Status != ttlock.AccountStatusOK {
			continue
		}
		key := "ttlock_clock_checked:" + lk.LockID
		last, err := r.readSetting(ctx, key)
		if err != nil {
			return out, err
		}
		if last != "" {
			// An unreadable stored value is ignored, as the Python ValueError branch does.
			if seen, perr := parseISO(last); perr == nil && now.Sub(seen) < 7*24*time.Hour {
				continue
			}
		}
		if out.checked >= 1 {
			break
		}
		out.checked++

		sample, found, err := r.clockSampleFor(ctx, lk.LockID)
		if err != nil {
			return out, err
		}

		remote, err := r.Locks.QueryLockTime(ctx, acc.ID, lk.LockID)
		if err == nil {
			drift := remote - nowMS
			if drift > clockDriftMS || drift < -clockDriftMS {
				if _, err = r.Locks.AdjustLockTime(ctx, acc.ID, lk.LockID); err == nil {
					out.adjusted++
					owner := lk.OwnerUserID
					if err := r.audit(ctx, "lock_clock_adjusted",
						fmt.Sprintf("lock=%s drift_s=%d", lk.LockID, clockFloorDiv(drift, 1000)), &owner); err != nil {
						return out, err
					}
				}
			}
		}
		if err == nil {
			if err := r.writeSetting(ctx, key, nowISO); err != nil {
				return out, err
			}
			continue
		}

		te, isTTLock := ttlock.AsError(err)
		if !isTTLock {
			return out, err
		}
		kind := te.Kind
		if kind == "" {
			kind = "transient"
		}
		if clockRetryKind(kind) {
			// Retry in one day: the 7-day gate then passes on the next tick.
			if err := r.writeSetting(ctx, key, iso(now.Add(-6*24*time.Hour))); err != nil {
				return out, err
			}
			continue
		}
		if found {
			name := derefOr(sample.InternalName, "")
			if err := s.Alerts.Raise(ctx, Alert{
				Level:       "warning",
				Kind:        "door_code_clock",
				Message:     "Lock clock could not be checked",
				DedupeKey:   "door_code_clock:" + lk.LockID,
				ApartmentID: sample.ID,
				Params:      map[string]any{"property": name},
			}); err != nil {
				return out, err
			}
		}
		if err := r.writeSetting(ctx, key, nowISO); err != nil {
			return out, err
		}
	}
	return out, nil
}

// clockRetryKind reports whether a TTLock error kind only retries later.
func clockRetryKind(kind string) bool {
	for _, k := range clockRetryKinds {
		if k == kind {
			return true
		}
	}
	return false
}

// clockSampleFor is the first apartment on the lock (LIMIT 1); found is false when there is none.
func (r *Reconciler) clockSampleFor(ctx context.Context, lockID string) (clockSample, bool, error) {
	rows, err := r.Svc.Pool.Query(ctx,
		"SELECT id, internal_name FROM apartment WHERE lock_provider = 'ttlock' AND lock_id = $1 LIMIT 1", lockID)
	if err != nil {
		return clockSample{}, false, err
	}
	found, err := pgx.CollectRows(rows, pgx.RowToStructByPos[clockSample])
	if err != nil || len(found) == 0 {
		return clockSample{}, false, err
	}
	return found[0], true, nil
}

// readSetting is db.get_setting: "" when the key is missing or NULL.
func (r *Reconciler) readSetting(ctx context.Context, key string) (string, error) {
	var v *string
	err := r.Svc.Pool.QueryRow(ctx, "SELECT value FROM settings WHERE key = $1", key).Scan(&v)
	if isNoRows(err) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	return derefOr(v, ""), nil
}

// writeSetting is db.set_setting.
func (r *Reconciler) writeSetting(ctx context.Context, key, value string) error {
	_, err := r.Svc.exec(ctx,
		"INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
		key, value)
	return err
}

// clockFloorDiv is Python's // for integers (rounds toward negative infinity).
func clockFloorDiv(a, b int64) int64 {
	q := a / b
	if (a%b != 0) && ((a < 0) != (b < 0)) {
		q--
	}
	return q
}
