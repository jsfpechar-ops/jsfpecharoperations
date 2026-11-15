package doorcodes

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// lcDCCols are the door_code columns, qualified with dc for queries that join reservation.
const lcDCCols = "dc.id, dc.reservation_id, dc.apartment_id, dc.lock_id, dc.code_kind, dc.state, dc.pin_enc, " +
	"dc.provider_code_id, dc.valid_from, dc.valid_to, dc.attempts, dc.next_attempt_at, dc.claimed_at, " +
	"dc.last_error, dc.notified_at, dc.issued_at"

// lcScanDC is the scan destinations for lcDCCols.
func lcScanDC(d *doorCode) []any {
	return []any{&d.ID, &d.ReservationID, &d.ApartmentID, &d.LockID, &d.CodeKind, &d.State, &d.PinEnc,
		&d.ProviderCodeID, &d.ValidFrom, &d.ValidTo, &d.Attempts, &d.NextAttemptAt, &d.ClaimedAt,
		&d.LastError, &d.NotifiedAt, &d.IssuedAt}
}

// doorCodeRows reads whole door_code rows; the rows are read to the end before the caller
// runs any other statement.
func (l *Lifecycle) doorCodeRows(ctx context.Context, sql string, args ...any) ([]*doorCode, error) {
	rows, err := l.Pool.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*doorCode
	for rows.Next() {
		d := &doorCode{}
		if err := rows.Scan(lcScanDC(d)...); err != nil {
			return nil, err
		}
		out = append(out, d)
	}
	return out, rows.Err()
}

// idRows reads a list of door_code ids.
func (l *Lifecycle) idRows(ctx context.Context, sql string, args ...any) ([]int64, error) {
	rows, err := l.Pool.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		out = append(out, id)
	}
	return out, rows.Err()
}

// handleCancellations is _handle_cancellations: the cancelled stays are revoked, a revived stay
// gets its PIN back, the due revokes run and a reactivated revoked row is reset.
func (l *Lifecycle) handleCancellations(ctx context.Context, nowISO string) error {
	rows, err := l.doorCodeRows(ctx,
		"SELECT "+lcDCCols+" FROM door_code dc JOIN reservation r ON r.id = dc.reservation_id "+
			"WHERE (r.status != 'active' OR r.archived_at IS NOT NULL)")
	if err != nil {
		return err
	}
	for _, row := range rows {
		switch {
		case row.State == StatePending || row.State == StateRetrying:
			// Guarded: issue() may have claimed the row since the SELECT.
			if _, err := l.exec(ctx,
				"UPDATE door_code SET state = $1, claimed_at = NULL, updated_at = $2 "+
					"WHERE id = $3 AND state IN ($4, $5)",
				StateRevoked, nowISO, row.ID, StatePending, StateRetrying); err != nil {
				return err
			}
		case row.State == StateIssued && derefOr(row.ValidTo, "") != "":
			endMS, err := isoToMS(*row.ValidTo)
			if err != nil {
				return err
			}
			if endMS > l.Clock.Now().UnixMilli() {
				if _, err := l.exec(ctx,
					"UPDATE door_code SET state = $1, attempts = 0, next_attempt_at = $2, claimed_at = NULL, "+
						"last_error = NULL, updated_at = $3 WHERE id = $4 AND state = $5",
					StateRevokePending, nowISO, nowISO, row.ID, StateIssued); err != nil {
					return err
				}
			}
		}
	}

	// A calendar revival or archive undo can bring the stay back while a delete is still
	// queued. Restore the PIN before the due query so the stay page shows it.
	revived, err := l.doorCodeRows(ctx,
		"SELECT "+lcDCCols+" FROM door_code dc JOIN reservation r ON r.id = dc.reservation_id "+
			"WHERE dc.state IN ($1, $2) AND r.status = 'active' AND r.archived_at IS NULL "+
			"AND dc.pin_enc IS NOT NULL",
		StateRevokePending, StateRevokeFailed)
	if err != nil {
		return err
	}
	for _, item := range revived {
		ok, err := l.reviveOne(ctx, item, nowISO, "")
		if err != nil {
			return err
		}
		if ok {
			if err := l.audit(ctx, "door_code_revoke_aborted", fmt.Sprintf("door_code=%d", item.ID), 0); err != nil {
				return err
			}
		}
	}

	due, err := l.idRows(ctx,
		"SELECT dc.id FROM door_code dc JOIN reservation r ON r.id = dc.reservation_id "+
			"WHERE dc.state = $1 AND (r.status != 'active' OR r.archived_at IS NOT NULL) "+
			"AND (dc.next_attempt_at IS NULL OR dc.next_attempt_at <= $2) "+
			"ORDER BY (dc.next_attempt_at IS NOT NULL), dc.next_attempt_at LIMIT $3",
		StateRevokePending, nowISO, Batch)
	if err != nil {
		return err
	}
	for _, id := range due {
		if err := l.revokeOne(ctx, id); err != nil {
			return err
		}
	}

	reactivated, err := l.idRows(ctx,
		"SELECT dc.id FROM door_code dc JOIN reservation r ON r.id = dc.reservation_id "+
			"WHERE dc.state = $1 AND r.status = 'active' AND r.archived_at IS NULL",
		StateRevoked)
	if err != nil {
		return err
	}
	for _, id := range reactivated {
		// Guarded: only a row that is still revoked is reset.
		removed, err := l.exec(ctx, "DELETE FROM door_code WHERE id = $1 AND state = $2", id, StateRevoked)
		if err != nil {
			return err
		}
		if removed > 0 {
			if err := l.audit(ctx, "door_code_reset", fmt.Sprintf("door_code=%d", id), 0); err != nil {
				return err
			}
		}
	}
	return nil
}

// lcMoveRow is a door_code row with the stay and apartment fields that _handle_moves reads.
type lcMoveRow struct {
	doorCode
	DateFrom, DateTo string
	CheckinHour      *int64
	CheckoutHour     *int64
	OwnerUserID      int64
}

// handleMoves is _handle_moves: an issued code whose stay window moved gets a new code, and the
// old one is deleted once the new one is in place.
func (l *Lifecycle) handleMoves(ctx context.Context, nowISO string) error {
	rows, err := l.Pool.Query(ctx,
		"SELECT "+lcDCCols+", r.date_from, r.date_to, a.checkin_hour, a.checkout_hour, "+
			"COALESCE(a.owner_user_id, 0) FROM door_code dc "+
			"JOIN reservation r ON r.id = dc.reservation_id JOIN apartment a ON a.id = dc.apartment_id "+
			"WHERE dc.state = $1 AND r.status = 'active' AND r.archived_at IS NULL",
		StateIssued)
	if err != nil {
		return err
	}
	var moves []lcMoveRow
	for rows.Next() {
		var m lcMoveRow
		dst := append(lcScanDC(&m.doorCode), &m.DateFrom, &m.DateTo, &m.CheckinHour, &m.CheckoutHour, &m.OwnerUserID)
		if err := rows.Scan(dst...); err != nil {
			rows.Close()
			return err
		}
		moves = append(moves, m)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	for _, m := range moves {
		if err := l.moveRow(ctx, m, nowISO); err != nil {
			return err
		}
	}
	return nil
}

// moveRow is one row of _handle_moves, up to and including the replace.
func (l *Lifecycle) moveRow(ctx context.Context, row lcMoveRow, nowISO string) error {
	nowMS := l.Clock.Now().UnixMilli()
	if derefOr(row.NextAttemptAt, "") != "" && *row.NextAttemptAt > nowISO {
		return nil
	}
	startMS, endMS, err := ttlock.StayWindow(row.DateFrom, row.DateTo, hourOf(row.CheckinHour),
		hourOf(row.CheckoutHour), l.Settings.BufferHours)
	if err != nil {
		return nil
	}
	if endMS < nowMS {
		return nil
	}
	validFrom, validTo := derefOr(row.ValidFrom, ""), derefOr(row.ValidTo, "")
	if validFrom != "" && validTo != "" {
		fromMS, err := isoToMS(validFrom)
		if err != nil {
			return err
		}
		toMS, err := isoToMS(validTo)
		if err != nil {
			return err
		}
		if fromMS == startMS && toMS == endMS {
			// The stay is back on the code's own window: an old move failure is stale.
			lastErr := derefOr(row.LastError, "")
			if strings.HasPrefix(lastErr, "lock_setup") || strings.HasPrefix(lastErr, "config") {
				if _, err := l.exec(ctx,
					"UPDATE door_code SET last_error = NULL, next_attempt_at = NULL, updated_at = $1 "+
						"WHERE id = $2 AND state = $3",
					nowISO, row.ID, StateIssued); err != nil {
					return err
				}
			}
			return nil
		}
	}
	movedDuring := startMS <= nowMS
	if validFrom != "" {
		fromMS, err := isoToMS(validFrom)
		if err != nil {
			return err
		}
		if fromMS <= nowMS {
			movedDuring = true
		}
	}
	if movedDuring {
		return l.doorCodeNotice(ctx, row.ID, "moved_during_stay")
	}
	// Brief 0037: a move that failed with permission (etc.) is not retried until the host fixes
	// TTLock access; the guest keeps the old code until then.
	lastErr := derefOr(row.LastError, "")
	for _, p := range []string{"permission", "reauth", "config", "disabled"} {
		if strings.HasPrefix(lastErr, p) {
			return nil
		}
	}
	account, err := l.Accounts.ForOwner(ctx, row.OwnerUserID)
	if err != nil {
		return err
	}
	if account == nil || account.Status != ttlock.AccountStatusOK {
		return nil
	}
	priority := ttlock.PriorityNormal
	if startMS < l.Clock.Now().Add(24*time.Hour).UnixMilli() {
		priority = ttlock.PriorityCritical
	}
	name := fmt.Sprintf("UH-%d", row.ID)
	viaAdd, err := l.replaceCode(ctx, row, account, startMS, endMS, name, priority, nowISO)
	if err == nil {
		return nil
	}
	te, isTT := ttlock.AsError(err)
	if !isTT {
		return err
	}
	return l.moveRefused(ctx, row, te, viaAdd, startMS, endMS, nowISO)
}

// replaceCode is the try body of _handle_moves: create the new code (a taken period falls back
// to a custom code), store it, audit, send the code mail and delete the old code. viaAdd reports
// that the custom-code fallback ran.
func (l *Lifecycle) replaceCode(ctx context.Context, row lcMoveRow, account *ttlock.Account,
	startMS, endMS int64, name, priority, nowISO string) (bool, error) {
	viaAdd := false
	pin, codeID, err := l.createRandom(ctx, account.ID, row.LockID, startMS, endMS, name, priority, row.ID)
	codeKind := "random"
	if err != nil {
		te, isTT := ttlock.AsError(err)
		if !isTT || (te.Kind != PeriodTaken && te.Kind != PeriodShared) {
			return false, err
		}
		if err := l.doorCodeNotice(ctx, row.ID, te.Kind); err != nil {
			return false, err
		}
		if err := l.Mailer.Drain(ctx, 4); err != nil {
			return false, err
		}
		viaAdd = true
		pin, codeID, err = l.TTLock.AddCustomCode(ctx, account.ID, row.LockID, startMS, endMS, name, priority)
		if err != nil {
			return viaAdd, err
		}
		codeKind = "custom"
	}
	enc, err := l.encryptField(pin)
	if err != nil {
		return viaAdd, err
	}
	if _, err := l.exec(ctx,
		"UPDATE door_code SET pin_enc = $1, provider_code_id = $2, code_kind = $3, valid_from = $4, "+
			"valid_to = $5, notified_at = NULL, next_attempt_at = NULL, last_error = NULL, updated_at = $6 "+
			"WHERE id = $7",
		enc, codeID, codeKind, msToISO(startMS), msToISO(endMS), nowISO, row.ID); err != nil {
		return viaAdd, err
	}
	if err := l.audit(ctx, "door_code_replaced", fmt.Sprintf("door_code=%d", row.ID), row.OwnerUserID); err != nil {
		return viaAdd, err
	}
	if err := l.Alerts.Resolve(ctx, fmt.Sprintf("door_code_pin_unverified:%d", row.ReservationID)); err != nil {
		return viaAdd, err
	}
	l.SendCodeMail(ctx, row.ID)
	oldCodeID := derefOr(row.ProviderCodeID, "")
	if oldCodeID != "" && oldCodeID != codeID {
		if derr := l.Locks.DeleteCode(ctx, account.ID, row.LockID, oldCodeID, ttlock.PriorityCritical); derr != nil {
			if _, isTT := ttlock.AsError(derr); !isTT {
				return viaAdd, derr
			}
			if err := l.audit(ctx, "door_code_move_old_not_deleted", fmt.Sprintf("door_code=%d", row.ID), row.OwnerUserID); err != nil {
				return viaAdd, err
			}
			if err := l.doorCodeNotice(ctx, row.ID, "moved_not_deleted"); err != nil {
				return viaAdd, err
			}
			if err := l.Mailer.Drain(ctx, 4); err != nil {
				return viaAdd, err
			}
		}
	}
	return viaAdd, nil
}

// moveRefused is the TTLock-error branch of _handle_moves. Permission-type kinds stop retrying and
// tell the host once. Other kinds wait 60 minutes for budget and lock_setup, 15 for the rest, and
// a lock_setup failure is noticed once per target window. The guest keeps the old code.
func (l *Lifecycle) moveRefused(ctx context.Context, row lcMoveRow, te *ttlock.TTLockError, viaAdd bool,
	startMS, endMS int64, nowISO string) error {
	kind := te.Kind
	if kind == "" {
		kind = ttlock.KindTransient
	}
	reason := kind
	if te.Code != 0 {
		reason = fmt.Sprintf("%s:%d", kind, te.Code)
	}
	lastError := reason
	if viaAdd {
		lastError = "period_taken:" + reason
	}
	lastError = truncateRunes(lastError, 40)
	if isOneOf(kind, ttlock.KindPermission, ttlock.KindReauth, ttlock.KindConfig, ttlock.KindDisabled) {
		if _, err := l.exec(ctx,
			"UPDATE door_code SET last_error = $1, updated_at = $2 WHERE id = $3",
			truncateRunes(reason, 40), nowISO, row.ID); err != nil {
			return err
		}
		if err := l.doorCodeNotice(ctx, row.ID, "failed"); err != nil {
			return err
		}
		return l.Mailer.Drain(ctx, 4)
	}
	delay := 15
	if isOneOf(kind, ttlock.KindBudget, ttlock.KindLockSetup) {
		delay = 60
	}
	if _, err := l.exec(ctx,
		"UPDATE door_code SET next_attempt_at = $1, last_error = $2, updated_at = $3 WHERE id = $4",
		iso(l.Clock.Now().Add(time.Duration(delay)*time.Minute)), lastError, nowISO, row.ID); err != nil {
		return err
	}
	if kind != ttlock.KindLockSetup {
		return nil
	}
	// The guest keeps the old code while the retry runs: tell the host once per target window.
	if err := l.Notices.DoorCodeNotice(ctx, row.ID, "moved_failed", fmt.Sprintf("%d-%d", startMS, endMS)); err != nil {
		return err
	}
	return l.Mailer.Drain(ctx, 4)
}
