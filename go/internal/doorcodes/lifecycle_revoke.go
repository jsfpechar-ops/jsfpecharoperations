package doorcodes

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// stayIsLive is _stay_is_live: an active, unarchived reservation.
func stayIsLive(r *Reservation) bool {
	return r != nil && r.Status == "active" && r.ArchivedAt == nil
}

// deleteResultUnknown is _delete_result_unknown: last_error leaves a delete's result open.
func deleteResultUnknown(lastError *string) bool {
	text := derefOr(lastError, "")
	for _, v := range ambiguousDeleteErrors {
		if text == v {
			return true
		}
	}
	return strings.HasPrefix(text, LookupFailed)
}

// lcCodeText prints an errcode as Python does: None when TTLock sent none.
func lcCodeText(code int) string {
	if code == 0 {
		return "None"
	}
	return strconv.Itoa(code)
}

// leaseCutoff is now minus LEASE_MINUTES, as stored text.
func (l *Lifecycle) leaseCutoff() string {
	return iso(l.Clock.Now().Add(-time.Duration(LeaseMinutes) * time.Minute))
}

// audit is db.audit with actor "system". ownerUserID 0 is Python's None.
func (l *Lifecycle) audit(ctx context.Context, action, detail string, ownerUserID int64) error {
	var owner any
	if ownerUserID != 0 {
		owner = ownerUserID
	}
	_, err := l.exec(ctx,
		"INSERT INTO audit (at, actor, action, detail, owner_user_id) VALUES ($1, 'system', $2, $3, $4)",
		iso(l.Clock.Now()), action, detail, owner)
	return err
}

// doorCodeNotice is mail_notify.door_code_notice(row_id, stage) without a key suffix.
func (l *Lifecycle) doorCodeNotice(ctx context.Context, rowID int64, stage string) error {
	return l.Notices.DoorCodeNotice(ctx, rowID, stage, "")
}

// apartmentOwner is the owner_user_id of an apartment (0 when none or the row is gone).
func (l *Lifecycle) apartmentOwner(ctx context.Context, apartmentID int64) (int64, error) {
	var owner int64
	err := l.Pool.QueryRow(ctx, "SELECT COALESCE(owner_user_id, 0) FROM apartment WHERE id = $1", apartmentID).Scan(&owner)
	if isNoRows(err) {
		return 0, nil
	}
	return owner, err
}

// keepIssued is _keep_issued: the stay is back, so the PIN is shown again. True if a row changed.
// Guarded: a row that _revoke_one holds (heldClaim) or that is leased (claimed_at inside
// LEASE_MINUTES) is taken only when the claim is the caller's own. The revived loop passes ""
// and so skips a leased row.
func (l *Lifecycle) keepIssued(ctx context.Context, rowID int64, nowISO, heldClaim string) (bool, error) {
	var held any
	if heldClaim != "" {
		held = heldClaim
	}
	n, err := l.exec(ctx,
		"UPDATE door_code SET state = $1, claimed_at = NULL, attempts = 0, next_attempt_at = NULL, "+
			"last_error = NULL, updated_at = $2 WHERE id = $3 AND state IN ($4, $5) "+
			"AND (claimed_at IS NULL OR claimed_at < $6 OR claimed_at = $7)",
		StateIssued, nowISO, rowID, StateRevokeFailed, StateRevokePending, l.leaseCutoff(), held)
	return n == 1, err
}

// lockCodeState is _lock_code_state: does the lock still hold the row's PIN? PinGone only when
// the whole listing was read and the code id is not in it. PinUnknown when the answer cannot be
// had or is incomplete. The code id decides, not the name or the window.
func (l *Lifecycle) lockCodeState(ctx context.Context, row *doorCode, ownerUserID int64) (string, error) {
	acc, err := l.Accounts.ForOwner(ctx, ownerUserID)
	if err != nil {
		return "", err
	}
	codeID := derefOr(row.ProviderCodeID, "")
	if acc == nil || acc.Status != ttlock.AccountStatusOK || codeID == "" {
		return PinUnknown, nil
	}
	listed, err := l.Locks.CodeIsListed(ctx, acc.ID, row.LockID, fmt.Sprintf("UH-%d", row.ID), codeID)
	if err != nil {
		if _, isTT := ttlock.AsError(err); isTT {
			return PinUnknown, nil
		}
		return "", err
	}
	switch listed {
	case ttlock.TriYes:
		return PinPresent, nil
	case ttlock.TriNo:
		return PinGone, nil
	}
	return PinUnknown, nil
}

// noteFailedLookup is _note_failed_lookup: count a failed lookup in last_error as
// "lookup_failed:<n>" and return n. attempts is the delete counter, so when the caller's claim
// raised it (claimed) the raise is taken back here.
func (l *Lifecycle) noteFailedLookup(ctx context.Context, rowID int64, claim string, claimed bool) (int, error) {
	var lastError *string
	err := l.Pool.QueryRow(ctx, "SELECT last_error FROM door_code WHERE id = $1", rowID).Scan(&lastError)
	if err != nil && !isNoRows(err) {
		return 0, err
	}
	previous := derefOr(lastError, "")
	count := 1
	prefix := LookupFailed + ":"
	if strings.HasPrefix(previous, prefix) {
		if n, perr := strconv.Atoi(strings.TrimSpace(previous[len(prefix):])); perr == nil {
			count = n + 1
		}
	}
	var taken int64
	if claimed {
		taken = 1
	}
	if _, err := l.exec(ctx,
		"UPDATE door_code SET attempts = attempts - $1, last_error = $2, updated_at = $3 "+
			"WHERE id = $4 AND claimed_at = $5",
		taken, fmt.Sprintf("%s:%d", LookupFailed, count), claim, rowID, claim); err != nil {
		return 0, err
	}
	return count, nil
}

// reviveOne is _revive_one: the stay is back, so show the PIN again, but first confirm it still
// exists when the delete may have run. True if the row is issued again.
func (l *Lifecycle) reviveOne(ctx context.Context, item *doorCode, nowISO, heldClaim string) (bool, error) {
	rowID := item.ID
	var floor int64
	if heldClaim != "" {
		floor = 1
	}
	if !(item.Attempts > floor && deleteResultUnknown(item.LastError)) {
		return l.keepIssued(ctx, rowID, nowISO, heldClaim)
	}
	claim := heldClaim
	if claim == "" {
		claim = iso(l.Clock.Now())
		n, err := l.exec(ctx,
			"UPDATE door_code SET claimed_at = $1, updated_at = $2 WHERE id = $3 AND state IN ($4, $5) "+
				"AND (claimed_at IS NULL OR claimed_at < $6)",
			claim, nowISO, rowID, StateRevokePending, StateRevokeFailed, l.leaseCutoff())
		if err != nil || n != 1 {
			return false, err
		}
	}
	ownerID, err := l.apartmentOwner(ctx, item.ApartmentID)
	if err != nil {
		return false, err
	}
	verdict, err := l.lockCodeState(ctx, item, ownerID)
	if err != nil {
		return false, err
	}
	unverified := false
	if verdict == PinUnknown {
		count, err := l.noteFailedLookup(ctx, rowID, claim, heldClaim != "")
		if err != nil {
			return false, err
		}
		if count < LookupMaxTries {
			return false, nil
		}
		unverified = true
	}
	kept, err := l.keepIssued(ctx, rowID, nowISO, claim)
	if err != nil || !kept {
		return false, err
	}
	switch {
	case unverified:
		if err := l.audit(ctx, "door_code_pin_unverified", fmt.Sprintf("door_code=%d", rowID), ownerID); err != nil {
			return false, err
		}
		l.tellHostUnverified(ctx, rowID, ownerID)
	case verdict == PinGone:
		if err := l.reissueLostPin(ctx, rowID, derefOr(item.ProviderCodeID, ""), ownerID); err != nil {
			return false, err
		}
	}
	return true, nil
}

// alreadyGone is _already_gone: a refused delete that may only mean the code no longer exists.
// Only an unmapped errcode or code_missing costs a listing; the code counts as deleted only when
// the lock confirms it is gone.
func (l *Lifecycle) alreadyGone(ctx context.Context, te *ttlock.TTLockError, row *doorCode, ownerUserID int64) (bool, error) {
	if te.Code == 0 {
		return false, nil
	}
	if mapped, ok := lcErrcodeKinds[te.Code]; ok && mapped != ttlock.KindCodeMissing {
		return false, nil
	}
	state, err := l.lockCodeState(ctx, row, ownerUserID)
	return state == PinGone, err
}

// tellHostReissued is _tell_host_reissued: one info card and one mail per replaced code. A failure
// is logged and never stops the re-issue. The PIN is not carried.
func (l *Lifecycle) tellHostReissued(ctx context.Context, rowID, ownerUserID int64) {
	if err := l.hostReissuedNotice(ctx, rowID); err != nil {
		l.log().Error(fmt.Sprintf("door code %d: host notice after a re-issue failed: %v", rowID, err))
	}
}

func (l *Lifecycle) hostReissuedNotice(ctx context.Context, rowID int64) error {
	var apartmentID, reservationID int64
	var property, email *string
	var dateFrom string
	err := l.Pool.QueryRow(ctx,
		"SELECT a.id, a.internal_name, r.id, r.date_from, c.email FROM door_code dc "+
			"JOIN apartment a ON a.id = dc.apartment_id JOIN reservation r ON r.id = dc.reservation_id "+
			"LEFT JOIN reservation_claim c ON c.reservation_id = r.id WHERE dc.id = $1", rowID).
		Scan(&apartmentID, &property, &reservationID, &dateFrom, &email)
	if isNoRows(err) {
		return nil
	}
	if err != nil {
		return err
	}
	suffix := ""
	if strings.TrimSpace(derefOr(email, "")) == "" {
		suffix = "_no_email"
	}
	if err := l.Alerts.Raise(ctx, Alert{
		Level:         "info",
		Kind:          "door_code_reissued" + suffix,
		Message:       "Door code was replaced",
		DedupeKey:     fmt.Sprintf("door_code_reissued%s:%d", suffix, reservationID),
		ApartmentID:   apartmentID,
		ReservationID: reservationID,
		Params:        map[string]any{"property": derefOr(property, ""), "date": dateFrom},
	}); err != nil {
		return err
	}
	return l.doorCodeNotice(ctx, rowID, "reissued"+suffix)
}

// tellHostUnverified is _tell_host_unverified: one warning card per stay and one mail per row
// when a revived code could not be confirmed on the lock. A failure is logged and never stops
// the revival.
func (l *Lifecycle) tellHostUnverified(ctx context.Context, rowID, ownerUserID int64) {
	if err := l.hostUnverifiedNotice(ctx, rowID); err != nil {
		l.log().Error(fmt.Sprintf("door code %d: host notice about an unverified code failed: %v", rowID, err))
	}
}

func (l *Lifecycle) hostUnverifiedNotice(ctx context.Context, rowID int64) error {
	var apartmentID, reservationID int64
	var property *string
	var dateFrom string
	err := l.Pool.QueryRow(ctx,
		"SELECT a.id, a.internal_name, r.id, r.date_from FROM door_code dc "+
			"JOIN apartment a ON a.id = dc.apartment_id JOIN reservation r ON r.id = dc.reservation_id "+
			"WHERE dc.id = $1", rowID).Scan(&apartmentID, &property, &reservationID, &dateFrom)
	if isNoRows(err) {
		return nil
	}
	if err != nil {
		return err
	}
	if err := l.Alerts.Raise(ctx, Alert{
		Level:         "warning",
		Kind:          "door_code_pin_unverified",
		Message:       "Door code could not be confirmed on the lock",
		DedupeKey:     fmt.Sprintf("door_code_pin_unverified:%d", reservationID),
		ApartmentID:   apartmentID,
		ReservationID: reservationID,
		Params:        map[string]any{"property": derefOr(property, ""), "date": dateFrom},
	}); err != nil {
		return err
	}
	return l.doorCodeNotice(ctx, rowID, "pin_unverified")
}

// reissueLostPin is _reissue_lost_pin: a revoke deleted the lock code but lost the row to a
// revival, so make a new code. One guarded UPDATE decides; a failure of issue() is logged.
func (l *Lifecycle) reissueLostPin(ctx context.Context, rowID int64, deletedCodeID string, ownerUserID int64) error {
	n, err := l.exec(ctx,
		"UPDATE door_code SET state = $1, pin_enc = NULL, provider_code_id = NULL, issued_at = NULL, "+
			"notified_at = NULL, claimed_at = NULL, attempts = 0, next_attempt_at = NULL, last_error = $2, "+
			"updated_at = $3 WHERE id = $4 AND state = $5 AND provider_code_id = $6 "+
			"AND EXISTS (SELECT 1 FROM reservation r WHERE r.id = door_code.reservation_id "+
			"AND r.status = 'active' AND r.archived_at IS NULL)",
		StatePending, "pin_lost", iso(l.Clock.Now()), rowID, StateIssued, deletedCodeID)
	if err != nil || n != 1 {
		return err
	}
	if err := l.audit(ctx, "door_code_pin_reissued", fmt.Sprintf("door_code=%d", rowID), ownerUserID); err != nil {
		return err
	}
	issued, err := l.Issue(ctx, rowID, true)
	if err != nil {
		l.log().Error(fmt.Sprintf("door code %d: re-issue after a lost revoke failed: %v", rowID, err))
		return nil
	}
	if issued {
		l.tellHostReissued(ctx, rowID, ownerUserID)
	}
	return nil
}

// setRevokeFailed moves a revoke_pending row to revoke_failed with last_error kind[:40] and
// reports whether it did. The caller decides on the audit and the notice.
func (l *Lifecycle) setRevokeFailed(ctx context.Context, rowID int64, lastError, nowISO string) (bool, error) {
	n, err := l.exec(ctx,
		"UPDATE door_code SET state = $1, claimed_at = NULL, last_error = $2, updated_at = $3 "+
			"WHERE id = $4 AND state = $5",
		StateRevokeFailed, truncateRunes(lastError, 40), nowISO, rowID, StateRevokePending)
	return n == 1, err
}

// revokeOne is _revoke_one: claim one due revoke_pending row, delete its lock code and record
// the outcome. A stay that is live again goes to reviveOne instead.
func (l *Lifecycle) revokeOne(ctx context.Context, rowID int64) error {
	now := l.Clock.Now()
	nowISO := iso(now)
	claimed, err := l.exec(ctx,
		"UPDATE door_code SET claimed_at = $1, attempts = attempts + 1, updated_at = $2 "+
			"WHERE id = $3 AND state = $4 AND (next_attempt_at IS NULL OR next_attempt_at <= $5) "+
			"AND (claimed_at IS NULL OR claimed_at < $6)",
		nowISO, nowISO, rowID, StateRevokePending, nowISO, l.leaseCutoff())
	if err != nil || claimed != 1 {
		return err
	}
	row, err := l.loadDoorCode(ctx, "id = $1", rowID)
	if err != nil || row == nil {
		return err
	}
	apt, err := l.loadApartment(ctx, row.ApartmentID)
	if err != nil {
		return err
	}
	res, err := l.loadReservation(ctx, row.ReservationID)
	if err != nil {
		return err
	}
	if apt == nil || res == nil {
		return nil
	}
	if stayIsLive(res) {
		_, err := l.reviveOne(ctx, row, nowISO, nowISO)
		return err
	}
	owner := apt.OwnerUserID
	account, err := l.Accounts.ForOwner(ctx, owner)
	if err != nil {
		return err
	}
	if account == nil || account.Status != ttlock.AccountStatusOK {
		n, err := l.exec(ctx,
			"UPDATE door_code SET state = $1, claimed_at = NULL, last_error = $2, updated_at = $3 "+
				"WHERE id = $4 AND state = $5",
			StateRevokeFailed, "no_account", nowISO, rowID, StateRevokePending)
		if err != nil || n != 1 {
			return err
		}
		return l.doorCodeNotice(ctx, rowID, "cancelled_not_deleted")
	}
	attempts := row.Attempts
	via := ""
	if derr := l.Locks.DeleteCode(ctx, account.ID, row.LockID, derefOr(row.ProviderCodeID, ""), ttlock.PriorityCritical); derr != nil {
		te, isTT := ttlock.AsError(derr)
		if !isTT {
			return derr
		}
		gone, err := l.alreadyGone(ctx, te, row, owner)
		if err != nil {
			return err
		}
		if !gone {
			return l.revokeRefused(ctx, rowID, row, te, attempts, now, nowISO, owner)
		}
		via = " via=gone:" + lcCodeText(te.Code)
		l.log().Warn(fmt.Sprintf("DOOR_CODE_PROBLEM stage=delete_gone door_code=%d errcode=%s", rowID, lcCodeText(te.Code)))
	}
	n, err := l.exec(ctx,
		"UPDATE door_code SET state = $1, revoked_at = $2, pin_enc = NULL, claimed_at = NULL, "+
			"updated_at = $3 WHERE id = $4 AND state = $5",
		StateRevoked, nowISO, nowISO, rowID, StateRevokePending)
	if err != nil {
		return err
	}
	if n != 1 {
		// The lock code is gone but the row moved on (the stay came back during the delete).
		// No audit "revoked", no mail; flag it and make the PIN again.
		if err := l.audit(ctx, "door_code_revoke_lost_race", fmt.Sprintf("door_code=%d", rowID), owner); err != nil {
			return err
		}
		return l.reissueLostPin(ctx, rowID, derefOr(row.ProviderCodeID, ""), owner)
	}
	if err := l.audit(ctx, "door_code_revoked", fmt.Sprintf("door_code=%d%s", rowID, via), owner); err != nil {
		return err
	}
	return l.doorCodeNotice(ctx, rowID, "cancelled_deleted")
}

// revokeRefused is the TTLock-error branch of _revoke_one: a gateway kind retries on the
// 1, 15, 60 minute schedule (and notifies on the third try), and a past-end code is given up,
// while any other kind goes to revoke_failed with a host notice.
func (l *Lifecycle) revokeRefused(ctx context.Context, rowID int64, row *doorCode, te *ttlock.TTLockError,
	attempts int64, now time.Time, nowISO string, owner int64) error {
	kind := te.Kind
	if kind == "" {
		kind = ttlock.KindTransient
	}
	if !isOneOf(kind, gatewayRetryKinds...) {
		ok, err := l.setRevokeFailed(ctx, rowID, kind, nowISO)
		if err != nil || !ok {
			return err
		}
		if err := l.audit(ctx, "door_code_revoke_failed", fmt.Sprintf("door_code=%d", rowID), owner); err != nil {
			return err
		}
		return l.doorCodeNotice(ctx, rowID, "cancelled_not_deleted")
	}
	pastEnd := false
	if validTo := derefOr(row.ValidTo, ""); validTo != "" {
		endMS, err := isoToMS(validTo)
		if err != nil {
			return err
		}
		pastEnd = endMS <= now.UnixMilli()
	}
	if pastEnd {
		ok, err := l.setRevokeFailed(ctx, rowID, kind, nowISO)
		if err != nil || !ok {
			return err
		}
		return l.audit(ctx, "door_code_revoke_failed", fmt.Sprintf("door_code=%d", rowID), owner)
	}
	delays := []int{1, 15, 60}
	idx := int(attempts - 1)
	if idx > 2 {
		idx = 2
	}
	if idx < 0 {
		idx += len(delays) // Python delays[-1] when attempts is 0
	}
	next := iso(now.Add(time.Duration(delays[idx]) * time.Minute))
	n, err := l.exec(ctx,
		"UPDATE door_code SET claimed_at = NULL, next_attempt_at = $1, last_error = $2, updated_at = $3 "+
			"WHERE id = $4 AND state = $5",
		next, truncateRunes(kind, 40), nowISO, rowID, StateRevokePending)
	if err != nil {
		return err
	}
	if n == 1 && attempts == 3 {
		return l.doorCodeNotice(ctx, rowID, "cancelled_not_deleted")
	}
	return nil
}
