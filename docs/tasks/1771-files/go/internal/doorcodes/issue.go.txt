package doorcodes

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// EnsureRow is ensure_row: it makes the pending door_code row of an eligible stay. ok is
// false when the stay is not eligible or the owner cannot hold a code.
func (s *Service) EnsureRow(ctx context.Context, reservationID int64) (int64, bool, error) {
	var rid, aid, owner int64
	var lockID *string
	err := s.Pool.QueryRow(ctx,
		"SELECT r.id, a.id, a.lock_id, COALESCE(a.owner_user_id, 0) FROM reservation r "+
			"JOIN apartment a ON a.id = r.apartment_id WHERE r.id = $1 AND "+eligibleSQL(s.Settings.Live, "$2"),
		reservationID, s.today()).Scan(&rid, &aid, &lockID, &owner)
	if isNoRows(err) {
		return 0, false, nil
	}
	if err != nil {
		return 0, false, err
	}
	can, err := s.ownerCanHoldCode(ctx, owner)
	if err != nil || !can {
		return 0, false, err
	}
	now := iso(s.Clock.Now())
	if _, err := s.exec(ctx,
		"INSERT INTO door_code (reservation_id, apartment_id, lock_id, code_kind, state, "+
			"attempts, next_attempt_at, created_at, updated_at) "+
			"VALUES ($1, $2, $3, 'random', $4, 0, $5, $6, $6) ON CONFLICT (reservation_id) DO NOTHING",
		rid, aid, derefOr(lockID, ""), StatePending, now, now); err != nil {
		return 0, false, err
	}
	existing, err := s.loadDoorCode(ctx, "reservation_id = $1", rid)
	if err != nil || existing == nil {
		return 0, false, err
	}
	return existing.ID, true, nil
}

// allowed is ttlock.allowed_for: the TTLock client is enabled and the plan allows it.
func (s *Service) allowed(ctx context.Context, ownerUserID int64) (bool, error) {
	if ownerUserID == 0 || !s.Settings.Enabled || !s.TTLock.Enabled() {
		return false, nil
	}
	return s.Plans.TTLockAllowed(ctx, ownerUserID)
}

// ownerCanHoldCode is _owner_can_hold_code.
func (s *Service) ownerCanHoldCode(ctx context.Context, ownerUserID int64) (bool, error) {
	ok, err := s.allowed(ctx, ownerUserID)
	if err != nil || !ok {
		return false, err
	}
	acc, err := s.Accounts.ForOwner(ctx, ownerUserID)
	if err != nil {
		return false, err
	}
	return acc != nil && acc.Status == ttlock.AccountStatusOK, nil
}

// SendCodeMail is send_code_mail: it queues the code mail and logs any failure instead of raising.
func (s *Service) SendCodeMail(ctx context.Context, doorCodeID int64) {
	if err := s.sendCodeMail(ctx, doorCodeID); err != nil {
		s.log().Error(fmt.Sprintf("door_code_mail_failed door_code=%d err=%v", doorCodeID, err))
	}
}

// sendCodeMail is _send_code_mail.
func (s *Service) sendCodeMail(ctx context.Context, doorCodeID int64) error {
	row, err := s.loadDoorCode(ctx, "id = $1", doorCodeID)
	if err != nil || row == nil || row.State != StateIssued || row.NotifiedAt != nil {
		return err
	}
	res, err := s.loadReservation(ctx, row.ReservationID)
	if err != nil || res == nil {
		return err
	}
	apt, err := s.loadApartment(ctx, row.ApartmentID)
	if err != nil || apt == nil {
		return err
	}
	var email string
	var lang, completedAt *string
	err = s.Pool.QueryRow(ctx,
		"SELECT COALESCE(email, ''), lang, completion_notified_at FROM reservation_claim WHERE reservation_id = $1",
		res.ID).Scan(&email, &lang, &completedAt)
	if isNoRows(err) {
		return nil
	}
	if err != nil {
		return err
	}
	if strings.TrimSpace(email) == "" {
		return nil
	}
	if completedAt == nil {
		// The confirmation has not gone yet: the code travels inside it.
		if err := s.releaseConfirmation(ctx, res.ID, false); err != nil {
			return err
		}
		again, err := s.loadDoorCode(ctx, "id = $1", doorCodeID)
		if err != nil {
			return err
		}
		if again != nil && again.NotifiedAt != nil {
			return nil
		}
	}
	shown, err := s.View(ctx, *res, *apt)
	if err != nil || shown == nil || shown.State != "issued" {
		return err
	}
	language := derefOr(lang, "")
	if language == "" {
		language = "en"
	}
	in := DoorCodeMail{
		Lang:         language,
		PropertyName: apt.InternalName,
		Checkin:      shown.Checkin,
		Checkout:     shown.Checkout,
		FirstUseBy:   shown.FirstUseBy,
	}
	// The fee block rides along only when the completion mail (the bill) has gone and the
	// group is still whole. Any failure drops the fee block, never the code mail.
	content, ok := s.contentWithFee(ctx, in, *res, *apt, completedAt != nil)
	if !ok {
		if content, err = s.Mailer.BuildDoorCode(ctx, in); err != nil {
			return err
		}
	}
	payload, err := s.Mailer.GuestPayload(ctx, apt.ID, content, language)
	if err != nil {
		return err
	}
	if payload == nil {
		payload = map[string]any{}
	}
	if content.QRSpayd != "" {
		payload[qrSpaydPayloadKey] = content.QRSpayd
	}
	payload[doorCodePayloadKey] = derefOr(row.PinEnc, "")
	cc, _ := payload["reply_to"].(string)
	outboxID, queued, err := s.Mailer.Enqueue(ctx, OutboxMail{
		Kind:           "door_code",
		IdempotencyKey: mailIdempotencyKey(res.ID, row),
		ToEmail:        email,
		CcEmail:        cc,
		Subject:        content.Subject,
		Payload:        payload,
		ReservationID:  res.ID,
		ApartmentID:    apt.ID,
		OwnerUserID:    apt.OwnerUserID,
	})
	if err != nil || !queued {
		return err
	}
	_ = outboxID
	now := iso(s.Clock.Now())
	if _, err := s.exec(ctx, "UPDATE door_code SET notified_at = $1, updated_at = $1 WHERE id = $2", now, doorCodeID); err != nil {
		return err
	}
	return s.Mailer.Drain(ctx, 4)
}

// contentWithFee builds the code mail with the fee block when the group is whole and the
// completion mail has gone. ok is false when there is no fee block or it failed.
func (s *Service) contentWithFee(ctx context.Context, in DoorCodeMail, res Reservation, apt Apartment, completed bool) (DoorCodeContent, bool) {
	if !completed {
		return DoorCodeContent{}, false
	}
	filled, expected, err := s.Billing.ReservationProgress(ctx, res.ID)
	if err != nil {
		s.log().Error(fmt.Sprintf("door code %d: fee block dropped from the code mail", res.ID))
		return DoorCodeContent{}, false
	}
	if expected == nil || filled < *expected {
		return DoorCodeContent{}, false
	}
	fee, err := s.Billing.CompletionFee(ctx, apt.ID, res.ID)
	if err != nil || fee == nil {
		return DoorCodeContent{}, false
	}
	in.Fee = fee
	content, err := s.Mailer.BuildDoorCode(ctx, in)
	if err != nil {
		s.log().Error(fmt.Sprintf("door code %d: fee block dropped from the code mail", res.ID))
		return DoorCodeContent{}, false
	}
	return content, true
}

// CompletionResult is what CompletionDoorCode says about the door code in the confirmation.
type CompletionResult struct {
	Action     string // CompletionHold, CompletionWith or CompletionWithout
	DoorCodeID int64  // set for CompletionWith
	Fields     *Shown // checkin, checkout and first_use_by, set for CompletionWith
}

// CompletionDoorCode is completion_door_code.
func (s *Service) CompletionDoorCode(ctx context.Context, res Reservation, apt Apartment) (CompletionResult, error) {
	without := CompletionResult{Action: CompletionWithout}
	if !s.Settings.Enabled {
		return without, nil
	}
	row, err := s.loadDoorCode(ctx, "reservation_id = $1", res.ID)
	if err != nil || row == nil {
		return without, err
	}
	switch row.State {
	case StatePending, StateIssuing, StateRetrying:
		return CompletionResult{Action: CompletionHold}, nil
	}
	if row.State == StateIssued && derefOr(row.PinEnc, "") != "" && row.NotifiedAt == nil {
		shown, err := s.View(ctx, res, apt)
		if err != nil {
			return without, err
		}
		if shown != nil && shown.State == "issued" {
			return CompletionResult{
				Action:     CompletionWith,
				DoorCodeID: row.ID,
				Fields:     &Shown{Checkin: shown.Checkin, Checkout: shown.Checkout, FirstUseBy: shown.FirstUseBy},
			}, nil
		}
	}
	return without, nil
}

// releaseConfirmation is _release_confirmation: send a held confirmation.
func (s *Service) releaseConfirmation(ctx context.Context, reservationID int64, force bool) error {
	res, err := s.loadReservation(ctx, reservationID)
	if err != nil || res == nil {
		return err
	}
	apt, err := s.loadApartment(ctx, res.ApartmentID)
	if err != nil || apt == nil {
		return err
	}
	return s.Confirm.MaybeNotifyCompletion(ctx, res.ID, apt.ID, force)
}

// ReleaseHeldConfirmations is _release_held_confirmations: the safety net that sends any
// confirmation held longer than HoldConfirmationMinutes. It returns how many it found.
func (s *Service) ReleaseHeldConfirmations(ctx context.Context) (int, error) {
	now := s.Clock.Now()
	cutoff := iso(now.Add(-HoldConfirmationMinutes * time.Minute))
	// Only stays this brief can have held: they have a door_code row and registered in the
	// last day. Older stays must never get a late confirmation.
	oldest := iso(now.Add(-24 * time.Hour))
	rows, err := s.Pool.Query(ctx,
		"SELECT r.id FROM reservation r JOIN reservation_claim c ON c.reservation_id = r.id "+
			"JOIN door_code dc ON dc.reservation_id = r.id "+
			"WHERE c.state = 'claimed' AND c.email IS NOT NULL AND c.email <> '' "+
			"AND c.completion_notified_at IS NULL AND r.status = 'active' "+
			"AND r.registration_completed_at < $1 AND r.registration_completed_at > $2 LIMIT $3",
		cutoff, oldest, Batch)
	if err != nil {
		return 0, err
	}
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return 0, err
		}
		ids = append(ids, id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}
	for _, id := range ids {
		s.log().Error(fmt.Sprintf("DOOR_CODE_PROBLEM stage=confirmation_without_code reservation=%d", id))
		if err := s.releaseConfirmation(ctx, id, true); err != nil {
			return 0, err
		}
	}
	return len(ids), nil
}

// periodHeldByOther is _period_code_held_by_other: another stay already stores this period code.
func (s *Service) periodHeldByOther(ctx context.Context, lockID, codeID string, startMS, endMS, doorCodeID int64) (bool, error) {
	return s.exists(ctx,
		"SELECT 1 FROM door_code WHERE lock_id = $1 AND provider_code_id = $2 "+
			"AND valid_from = $3 AND valid_to = $4 AND id != $5",
		lockID, codeID, msToISO(startMS), msToISO(endMS), doorCodeID)
}

// createRandom is _create_random: a period code that another stay already holds is an error.
func (s *Service) createRandom(ctx context.Context, accountID int64, lockID string, startMS, endMS int64,
	name, priority string, doorCodeID int64) (string, string, error) {
	pin, codeID, err := s.TTLock.CreatePeriodCode(ctx, accountID, lockID, startMS, endMS, name, priority)
	if err != nil {
		return "", "", err
	}
	held, err := s.periodHeldByOther(ctx, lockID, codeID, startMS, endMS, doorCodeID)
	if err != nil {
		return "", "", err
	}
	if held {
		return "", "", &ttlock.TTLockError{Kind: PeriodShared, Message: "period already has an undeleted code"}
	}
	return pin, codeID, nil
}

// handOver is the FAILED side effect shared by every failure branch of issue.
func (s *Service) handOver(ctx context.Context, doorCodeID int64, res Reservation, apt Apartment) error {
	if err := s.Alerts.Raise(ctx, Alert{
		Level:         "warning",
		Kind:          alertDoorCodeFailed,
		Message:       alertFailedMessage,
		DedupeKey:     fmt.Sprintf("door_code_failed:%d", res.ID),
		ApartmentID:   apt.ID,
		ReservationID: res.ID,
		Params:        map[string]any{"property": apt.InternalName, "date": res.DateFrom},
	}); err != nil {
		return err
	}
	if err := s.Mailer.DoorCodeNotice(ctx, doorCodeID, "failed"); err != nil {
		return err
	}
	if err := s.releaseConfirmation(ctx, res.ID, false); err != nil {
		return err
	}
	return s.Mailer.Drain(ctx, 4)
}

// problem logs a DOOR_CODE_PROBLEM line in the format the host dashboards grep for.
func (s *Service) problem(stage string, res Reservation, doorCodeID int64, attempts int64, reason string) {
	s.log().Error(fmt.Sprintf("DOOR_CODE_PROBLEM stage=%s reservation=%d door_code=%d attempt=%d reason=%s",
		stage, res.ID, doorCodeID, attempts, reason))
}

// Issue is issue(door_code_id, allow_gateway): claim the row, create the code on the lock and
// store it. It reports whether the code was issued. An error is a database fault.
func (s *Service) Issue(ctx context.Context, doorCodeID int64, allowGateway bool) (bool, error) {
	now := s.Clock.Now()
	nowISO := iso(now)
	leaseCutoff := iso(now.Add(-LeaseMinutes * time.Minute))
	claimed, err := s.exec(ctx,
		"UPDATE door_code SET state = $1, claimed_at = $2, attempts = attempts + 1, updated_at = $2 "+
			"WHERE id = $3 AND state IN ($4, $5) AND (next_attempt_at IS NULL OR next_attempt_at <= $2) "+
			"AND (claimed_at IS NULL OR claimed_at < $6)",
		StateIssuing, nowISO, doorCodeID, StatePending, StateRetrying, leaseCutoff)
	if err != nil {
		return false, err
	}
	if claimed != 1 {
		return false, nil
	}

	row, err := s.loadDoorCode(ctx, "id = $1", doorCodeID)
	if err != nil || row == nil {
		return false, err
	}
	res, err := s.loadReservation(ctx, row.ReservationID)
	if err != nil || res == nil {
		return false, err
	}
	apt, err := s.loadApartment(ctx, row.ApartmentID)
	if err != nil || apt == nil {
		return false, err
	}

	still, err := s.exists(ctx,
		"SELECT 1 FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE r.id = $1 AND "+
			eligibleSQL(s.Settings.Live, "$2"),
		res.ID, s.today())
	if err != nil {
		return false, err
	}
	allowedNow := false
	if still {
		if allowedNow, err = s.allowed(ctx, apt.OwnerUserID); err != nil {
			return false, err
		}
	}
	if !still || !allowedNow {
		return false, s.releaseIssueClaim(ctx, doorCodeID, true, "not_eligible")
	}

	account, err := s.Accounts.ForOwner(ctx, apt.OwnerUserID)
	if err != nil {
		return false, err
	}
	if account == nil || account.Status != ttlock.AccountStatusOK {
		return false, s.releaseIssueClaim(ctx, doorCodeID, true, "no_account")
	}

	start, end, werr := ttlock.StayWindow(res.DateFrom, res.DateTo, hourOf(apt.CheckinHour), hourOf(apt.CheckoutHour),
		s.Settings.BufferHours)
	if werr != nil {
		return false, s.releaseIssueClaim(ctx, doorCodeID, true, "bad_window")
	}

	if end < now.UnixMilli() {
		_, err := s.exec(ctx,
			"UPDATE door_code SET state = $1, claimed_at = NULL, attempts = attempts - 1, updated_at = $2 "+
				"WHERE id = $3 AND attempts > 0",
			StateExpired, iso(s.Clock.Now()), doorCodeID)
		return false, err
	}

	name := fmt.Sprintf("UH-%d", doorCodeID)
	priority := ttlock.PriorityNormal
	if start < now.Add(24*time.Hour).UnixMilli() {
		priority = ttlock.PriorityCritical
	}
	attempts := row.Attempts
	taken := strings.HasPrefix(derefOr(row.LastError, ""), PeriodTaken)
	viaAdd := false
	lockID := row.LockID
	accountID := account.ID

	// attempt is the try on the lock and the success write. Its errors are classified below.
	attempt := func() (bool, error) {
		var pin, codeID string
		havePin := false
		kind := "random"
		if attempts > 1 {
			foundPin, foundID, found, err := s.TTLock.FindCodeByName(ctx, accountID, lockID, name, start, end)
			if err != nil {
				return false, err
			}
			if found {
				held, err := s.periodHeldByOther(ctx, lockID, foundID, start, end, doorCodeID)
				if err != nil {
					return false, err
				}
				if held {
					// get names the returned period code UH-<id>; a retry would hand the cancelled
					// stay's PIN to the new guest. Skip it; the custom-code path issues this stay's own.
					s.problem(PeriodShared, *res, doorCodeID, attempts, "")
					if err := s.Mailer.DoorCodeNotice(ctx, doorCodeID, PeriodShared); err != nil {
						return false, err
					}
					if err := s.Mailer.Drain(ctx, 4); err != nil {
						return false, err
					}
					if !taken {
						taken = true
						if _, err := s.exec(ctx, "UPDATE door_code SET last_error = $1 WHERE id = $2",
							"period_taken:shared", doorCodeID); err != nil {
							return false, err
						}
					}
				} else {
					pin, codeID, havePin = foundPin, foundID, true
					if taken {
						kind = "custom"
					}
				}
			}
		}
		if !havePin {
			switch {
			case taken && allowGateway:
				viaAdd = true
				p, c, err := s.TTLock.AddCustomCode(ctx, accountID, lockID, start, end, name, priority)
				if err != nil {
					return false, err
				}
				pin, codeID, kind = p, c, "custom"
			case taken:
				if err := s.releaseIssueClaim(ctx, doorCodeID, true, ""); err != nil {
					return false, err
				}
				return false, nil
			default:
				p, c, err := s.createRandom(ctx, accountID, lockID, start, end, name, priority, doorCodeID)
				if err == nil {
					pin, codeID = p, c
					break
				}
				te, ok := ttlock.AsError(err)
				if !ok || (te.Kind != PeriodTaken && te.Kind != PeriodShared) {
					return false, err
				}
				s.problem(te.Kind, *res, doorCodeID, attempts, "")
				if err := s.Mailer.DoorCodeNotice(ctx, doorCodeID, te.Kind); err != nil {
					return false, err
				}
				if err := s.Mailer.Drain(ctx, 4); err != nil {
					return false, err
				}
				if !allowGateway {
					lastErr := "period_taken:shared"
					if te.Kind == PeriodTaken {
						lastErr = "period_taken:-1026"
					}
					if _, err := s.exec(ctx,
						"UPDATE door_code SET state = $1, claimed_at = NULL, last_error = $2, "+
							"next_attempt_at = $3, updated_at = $3 WHERE id = $4",
						StateRetrying, lastErr, nowISO, doorCodeID); err != nil {
						return false, err
					}
					return false, nil
				}
				viaAdd = true
				p, c, addErr := s.TTLock.AddCustomCode(ctx, accountID, lockID, start, end, name, priority)
				if addErr != nil {
					return false, addErr
				}
				pin, codeID, kind = p, c, "custom"
			}
		}

		pinEnc, err := s.encryptField(pin)
		if err != nil {
			return false, err
		}
		if _, err := s.exec(ctx,
			"UPDATE door_code SET state = $1, pin_enc = $2, provider_code_id = $3, code_kind = $4, "+
				"valid_from = $5, valid_to = $6, issued_at = $7, claimed_at = NULL, last_error = NULL, "+
				"updated_at = $7 WHERE id = $8",
			StateIssued, pinEnc, codeID, kind, msToISO(start), msToISO(end), nowISO, doorCodeID); err != nil {
			return false, err
		}
		for _, key := range []string{
			fmt.Sprintf("door_code_failed:%d", res.ID),
			fmt.Sprintf("door_code_delayed:%d", res.ID),
			fmt.Sprintf("door_code_pin_unverified:%d", res.ID),
		} {
			if err := s.Alerts.Resolve(ctx, key); err != nil {
				return false, err
			}
		}
		if _, err := s.exec(ctx,
			"INSERT INTO audit (at, actor, action, detail, owner_user_id) VALUES ($1, 'system', 'door_code_issued', $2, $3)",
			iso(s.Clock.Now()), fmt.Sprintf("door_code=%d reservation=%d", doorCodeID, res.ID), apt.OwnerUserID); err != nil {
			return false, err
		}
		fresh, err := s.loadReservation(ctx, res.ID)
		if err != nil {
			return false, err
		}
		if fresh != nil && fresh.Status == "active" && fresh.ArchivedAt == nil {
			s.SendCodeMail(ctx, doorCodeID)
		}
		return true, nil
	}

	ok, err := attempt()
	if err == nil {
		return ok, nil
	}
	if te, isTTLock := ttlock.AsError(err); isTTLock {
		return false, s.failedTTLock(ctx, doorCodeID, *res, *apt, attempts, taken, viaAdd, te)
	}
	return false, s.failedGeneric(ctx, doorCodeID, *res, *apt, attempts)
}

// failedTTLock is the TTLockError branch of issue.
func (s *Service) failedTTLock(ctx context.Context, doorCodeID int64, res Reservation, apt Apartment,
	attempts int64, taken, viaAdd bool, te *ttlock.TTLockError) error {
	now := s.Clock.Now()
	nowISO := iso(now)
	kindErr := te.Kind
	if kindErr == "" {
		kindErr = "transient"
	}
	kindErr = truncateRunes(kindErr, 40)
	reason := kindErr
	if te.Code != 0 {
		reason = fmt.Sprintf("%s:%d", kindErr, te.Code)
	}

	var newState string
	var nextAt any
	if taken || viaAdd {
		lastErr := truncateRunes("period_taken:"+reason, 40)
		switch {
		case te.Code == -2012:
			newState = StateFailed
		case isOneOf(kindErr, "permission", "reauth", "config", "disabled", "storage", "duplicate"):
			newState = StateFailed
		case kindErr == "budget":
			newState = StateRetrying
			nextAt = iso(now.Add(60 * time.Minute))
			if _, err := s.exec(ctx, "UPDATE door_code SET attempts = attempts - 1 WHERE id = $1", doorCodeID); err != nil {
				return err
			}
		case attempts >= PeriodTakenMaxAttempts:
			newState = StateFailed
		default:
			newState = StateRetrying
			idx := min(max(int(attempts)-2, 0), 1)
			nextAt = iso(now.Add(time.Duration(periodTakenRetryMinutes[idx]) * time.Minute))
		}
		if _, err := s.exec(ctx,
			"UPDATE door_code SET state = $1, claimed_at = NULL, last_error = $2, next_attempt_at = $3, updated_at = $4 WHERE id = $5",
			newState, lastErr, nextAt, nowISO, doorCodeID); err != nil {
			return err
		}
		return s.afterFailure(ctx, doorCodeID, res, apt, attempts, newState, lastErr)
	}

	switch {
	case isOneOf(te.Kind, "reauth", "permission", "config", "disabled"):
		newState = StateFailed
	case te.Kind == "budget":
		newState = StateRetrying
		nextAt = iso(now.Add(60 * time.Minute))
		if _, err := s.exec(ctx, "UPDATE door_code SET attempts = attempts - 1 WHERE id = $1", doorCodeID); err != nil {
			return err
		}
	case attempts >= IssueMaxAttempts:
		newState = StateFailed
	default:
		newState = StateRetrying
		nextAt = iso(now.Add(time.Duration(backoffMinutes[backoffIndex(attempts)]) * time.Minute))
	}
	if _, err := s.exec(ctx,
		"UPDATE door_code SET state = $1, claimed_at = NULL, last_error = $2, next_attempt_at = $3, updated_at = $4 WHERE id = $5",
		newState, truncateRunes(reason, 40), nextAt, nowISO, doorCodeID); err != nil {
		return err
	}
	return s.afterFailure(ctx, doorCodeID, res, apt, attempts, newState, reason)
}

// failedGeneric is the catch-all branch of issue: any other error is a transient failure.
func (s *Service) failedGeneric(ctx context.Context, doorCodeID int64, res Reservation, apt Apartment, attempts int64) error {
	s.log().Error(fmt.Sprintf("door_code_issue_failed door_code=%d", doorCodeID))
	now := s.Clock.Now()
	var newState string
	var nextAt any
	if attempts >= IssueMaxAttempts {
		newState = StateFailed
	} else {
		newState = StateRetrying
		nextAt = iso(now.Add(time.Duration(backoffMinutes[backoffIndex(attempts)]) * time.Minute))
	}
	if _, err := s.exec(ctx,
		"UPDATE door_code SET state = $1, claimed_at = NULL, last_error = $2, next_attempt_at = $3, updated_at = $4 WHERE id = $5",
		newState, "transient", nextAt, iso(now), doorCodeID); err != nil {
		return err
	}
	return s.afterFailure(ctx, doorCodeID, res, apt, attempts, newState, "transient")
}

// afterFailure logs the failed try and, when the row was handed over, raises the host alert.
func (s *Service) afterFailure(ctx context.Context, doorCodeID int64, res Reservation, apt Apartment,
	attempts int64, newState, reason string) error {
	stage := "attempt_failed"
	if newState == StateFailed {
		stage = "handed_over"
	}
	s.problem(stage, res, doorCodeID, attempts, reason)
	if newState != StateFailed {
		return nil
	}
	return s.handOver(ctx, doorCodeID, res, apt)
}

// backoffIndex is the BACKOFF_MINUTES index for the n-th try (n >= 1), kept inside the table.
func backoffIndex(attempts int64) int {
	return min(max(int(attempts)-1, 0), len(backoffMinutes)-1)
}

func isOneOf(v string, options ...string) bool {
	for _, o := range options {
		if v == o {
			return true
		}
	}
	return false
}
