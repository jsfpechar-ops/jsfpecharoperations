package stays

// Brief 1597a: exported claim helpers for demo.seed (claim.start_claim, confirm,
// ensure_row, lock_guest_access). No HTTP routes.

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailnotify"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

const claimHoldTakeover = 60 * time.Second

// SeedReservation is the stay row demo.seed passes into the claim helpers.
type SeedReservation struct {
	ID          int64
	ApartmentID int64
	Status      string
}

// SeedApartment is the property row for claim mail and outbox metadata.
type SeedApartment struct {
	ID             int64
	OwnerUserID    int64
	Name           string
	PermalinkToken string
}

// ClaimSeedDeps wires database, env and clock (same roles as claimOpsDeps).
type ClaimSeedDeps struct {
	Pool   *pgxpool.Pool
	Getenv func(string) string
	Now    func() time.Time
}

func (d ClaimSeedDeps) ops() claimOpsDeps {
	return claimOpsDeps{pool: d.Pool, getenv: d.Getenv, now: d.Now}
}

// ClaimRowView is the reservation_claim fields callers need after EnsureClaimRow.
type ClaimRowView struct {
	State             string
	Email             string
	TokenVersion      int64
	GuestAccessLocked bool
}

// EnsureClaimRow is claim.ensure_row: insert an unclaimed row when missing.
func EnsureClaimRow(ctx context.Context, pool *pgxpool.Pool, reservationID int64, now time.Time) (ClaimRowView, error) {
	row, err := ensureClaimRow(ctx, pool, reservationID, isoStamp(now))
	if err != nil {
		return ClaimRowView{}, err
	}
	return claimRowView(row), nil
}

func claimRowView(row *claimRow) ClaimRowView {
	return ClaimRowView{
		State:             row.State,
		Email:             row.Email,
		TokenVersion:      row.TokenVersion,
		GuestAccessLocked: row.GuestAccessLocked,
	}
}

// StartClaim is claim.start_claim without the HTTP layer. It returns
// (ok, errorCode, secret). secret is only for tests and the staging console.
func StartClaim(ctx context.Context, d ClaimSeedDeps, res SeedReservation, apt SeedApartment, email string, partySize int, lang string, resend bool) (bool, string, string, error) {
	return startClaimSeed(ctx, d, res, apt, email, partySize, lang, resend, true)
}

func startClaimSeed(ctx context.Context, d ClaimSeedDeps, res SeedReservation, apt SeedApartment, email string, partySize int, lang string, resend, retry bool) (bool, string, string, error) {
	at := d.Now()
	_, _ = mailjob.ExpireHolds(ctx, d.Pool, at)
	addr := ubyport.NormaliseEmail(email)
	if addr == "" {
		return false, "bad_email", "", nil
	}
	if partySize < 1 || partySize > 60 {
		return false, "bad_party", "", nil
	}
	if res.Status != "active" {
		return false, "stay_gone", "", nil
	}
	stamp := isoStamp(at)
	row, err := ensureClaimRow(ctx, d.Pool, res.ID, stamp)
	if err != nil {
		return false, "", "", err
	}
	if !guestAccessOpen(res.Status, row.GuestAccessLocked) {
		_ = LockGuestAccess(ctx, d.Pool, res.ID, at)
		return false, "locked", "", nil
	}
	if row.State == claimStateClaimed && !resend {
		return false, "already_claimed", "", nil
	}
	if row.State == claimStateClaimed && resend {
		if ubyport.NormaliseEmail(row.Email) != addr {
			return false, "already_claimed", "", nil
		}
	}
	sameEmail := ubyport.NormaliseEmail(row.Email) == addr
	if row.State == claimStateProvisional && !resend {
		if holdStillActive(row.ProvisionalUntil, at) {
			if sameEmail {
				return false, "already_sent", "", nil
			}
			age := holdAgeSeconds(row.ProvisionalUntil, at)
			if age == nil || *age < claimHoldTakeover.Seconds() {
				return false, "held", "", nil
			}
		}
	}
	if resend || row.State == claimStateClaimed {
		if resendTooSoon(row.UpdatedAt, at) {
			return false, "cooldown", "", nil
		}
		st := &claimStay{id: res.ID, apartmentID: res.ApartmentID, status: res.Status}
		a := &claimApt{id: apt.ID, ownerID: apt.OwnerUserID, name: apt.Name, permalink: apt.PermalinkToken}
		ok, code, secret, err := startClaimResend(ctx, d.ops(), st, a, row, addr, partySize, lang, at)
		if err != nil {
			return false, "", "", err
		}
		if !ok {
			return false, code, "", nil
		}
		return true, "", secret, nil
	}

	if code, err := claimMailBlocked(ctx, d.Pool, res.ID, addr, at); err != nil {
		return false, "", "", err
	} else if code != "" {
		return false, code, "", nil
	}

	secret, err := newClaimSecret()
	if err != nil {
		return false, "", "", err
	}
	until := at.UTC().Add(claimHoldMinutes * time.Minute).Truncate(time.Second).Format("2006-01-02T15:04:05+00:00")
	version := row.TokenVersion + 1
	var declared any = partySize
	tag, err := d.Pool.Exec(ctx, `UPDATE reservation_claim SET state = $1, email = $2, email_masked = $3, lang = $4,
		token_hash = $5, token_version = $6, provisional_until = $7, declared_guests = $8, updated_at = $9
		WHERE reservation_id = $10 AND state = $11 AND token_version = $12`,
		claimStateProvisional, addr, mail.MaskEmail(addr), lang, claimTokenHash(secret), version, until, declared, stamp,
		res.ID, row.State, row.TokenVersion)
	if err != nil {
		return false, "", "", err
	}
	if tag.RowsAffected() != 1 {
		if retry {
			return startClaimSeed(ctx, d, res, apt, email, partySize, lang, resend, false)
		}
		return false, "held", "", nil
	}
	st := &claimStay{id: res.ID, apartmentID: res.ApartmentID, status: res.Status}
	a := &claimApt{id: apt.ID, ownerID: apt.OwnerUserID, name: apt.Name, permalink: apt.PermalinkToken}
	if err := enqueueClaimStart(ctx, d.ops(), st, a, addr, lang, secret, version, resend || row.State == claimStateClaimed, stamp); err != nil {
		return false, "", "", err
	}
	recKey := "claim_to:" + fmt.Sprintf("%x", sha256Sum([]byte(addr)))
	_ = rateRecord(ctx, d.Pool, "claim_mail_recipient", recKey, at)
	_ = rateRecord(ctx, d.Pool, "claim_mail_reservation", fmt.Sprintf("claim_res:%d", res.ID), at)
	if cfg, drainErr := mail.ConfigFromEnv(d.Getenv); drainErr == nil {
		_, _ = mail.Drain(ctx, d.Pool, cfg, 4)
	}
	return true, "", secret, nil
}

func readClaimSecretHash(ctx context.Context, pool *pgxpool.Pool, resID int64) (string, error) {
	var hash *string
	err := pool.QueryRow(ctx, `SELECT token_hash FROM reservation_claim WHERE reservation_id = $1`, resID).Scan(&hash)
	if err != nil {
		return "", err
	}
	if hash == nil || *hash == "" {
		return "", nil
	}
	return "", nil
}

// ConfirmClaim is claim.confirm for an active stay and matching secret.
func ConfirmClaim(ctx context.Context, d ClaimSeedDeps, res SeedReservation, secret string) (bool, error) {
	at := d.Now()
	_, _ = mailjob.ExpireHolds(ctx, d.Pool, at)
	stamp := isoStamp(at)
	row, err := ensureClaimRow(ctx, d.Pool, res.ID, stamp)
	if err != nil {
		return false, err
	}
	if secret == "" || row.State == claimStateUnclaimed {
		return false, nil
	}
	var hash string
	err = d.Pool.QueryRow(ctx, `SELECT COALESCE(token_hash,'') FROM reservation_claim WHERE reservation_id = $1`, res.ID).Scan(&hash)
	if err != nil || hash == "" {
		return false, err
	}
	if res.Status != "active" {
		return false, nil
	}
	if !guestAccessOpen(res.Status, row.GuestAccessLocked) {
		_ = LockGuestAccess(ctx, d.Pool, res.ID, at)
		return false, nil
	}
	if claimTokenHash(secret) != hash {
		return false, nil
	}
	if row.State == claimStateProvisional && row.ProvisionalUntil != nil {
		if deadline, err := parseClaimHoldDeadline(*row.ProvisionalUntil); err == nil && deadline.Before(at.UTC()) {
			return false, nil
		}
	}
	version := row.TokenVersion
	tx, err := d.Pool.Begin(ctx)
	if err != nil {
		return false, err
	}
	defer tx.Rollback(ctx)
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "reservation", int32(res.ID)); err != nil {
		return false, err
	}
	var heldState string
	var pending *int64
	err = tx.QueryRow(ctx, `SELECT state, declared_guests FROM reservation_claim WHERE reservation_id = $1`, res.ID).
		Scan(&heldState, &pending)
	if err != nil {
		return false, err
	}
	tag, err := tx.Exec(ctx, `UPDATE reservation_claim SET state = $1, claimed_at = $2, token_hash = NULL,
		provisional_until = NULL, updated_at = $2
		WHERE reservation_id = $3 AND token_hash = $4 AND token_version = $5 AND state IN ($6, $7)`,
		claimStateClaimed, stamp, res.ID, hash, version, claimStateProvisional, claimStateClaimed)
	if err != nil {
		return false, err
	}
	if tag.RowsAffected() != 1 {
		return false, nil
	}
	var ownerID *int64
	pendingCount := pending
	if heldState == claimStateProvisional && pendingCount != nil {
		code, old, err := applyDeclaredInTx(ctx, tx, res.ID, int(*pending), at)
		if err != nil {
			return false, err
		}
		_ = d.Pool.QueryRow(ctx, `SELECT owner_user_id FROM apartment WHERE id = $1`, res.ApartmentID).Scan(&ownerID)
		_ = recordDeclaredAudit(ctx, d.Pool, res.ID, code, old, int(*pendingCount), ownerID, stamp)
	}
	if _, err := tx.Exec(ctx, `UPDATE reservation_claim SET declared_guests = NULL WHERE reservation_id = $1`, res.ID); err != nil {
		return false, err
	}
	if err := tx.Commit(ctx); err != nil {
		return false, err
	}
	return true, nil
}

// LockGuestAccess is claim.lock_guest_access when access is not already locked.
func LockGuestAccess(ctx context.Context, pool *pgxpool.Pool, reservationID int64, now time.Time) error {
	stamp := isoStamp(now)
	_, err := pool.Exec(ctx, `UPDATE reservation_claim SET guest_access_locked_at = $1,
		guest_access_reopened_at = NULL, updated_at = $2
		WHERE reservation_id = $3 AND guest_access_locked_at IS NULL`,
		stamp, stamp, reservationID)
	return err
}

func holdStillActive(until *string, now time.Time) bool {
	if until == nil || strings.TrimSpace(*until) == "" {
		return false
	}
	deadline, err := parseClaimHoldDeadline(*until)
	if err != nil {
		return false
	}
	return deadline.After(now.UTC())
}

func holdAgeSeconds(until *string, now time.Time) *float64 {
	if until == nil || strings.TrimSpace(*until) == "" {
		return nil
	}
	deadline, err := parseClaimHoldDeadline(*until)
	if err != nil {
		return nil
	}
	started := deadline.Add(-claimHoldMinutes * time.Minute)
	age := now.UTC().Sub(started).Seconds()
	return &age
}

func parseClaimHoldDeadline(value string) (time.Time, error) {
	s := strings.ReplaceAll(value, "Z", "+00:00")
	if t, err := time.Parse(time.RFC3339Nano, s); err == nil {
		return t.UTC(), nil
	}
	loc, err := time.LoadLocation(pragueTZ)
	if err != nil {
		return time.Time{}, err
	}
	for _, layout := range []string{
		"2006-01-02T15:04:05.999999999",
		"2006-01-02 15:04:05.999999999",
		"2006-01-02T15:04:05",
	} {
		if t, err := time.ParseInLocation(layout, s, loc); err == nil {
			return t.UTC(), nil
		}
	}
	return time.Time{}, fmt.Errorf("unparseable provisional_until %q", value)
}

func enqueueClaimStart(ctx context.Context, d claimOpsDeps, st *claimStay, apt *claimApt, addr, lang, secret string, version int64, resend bool, stamp string) error {
	if !billingjob.MailEnabled() {
		return nil
	}
	base := strings.TrimRight(hostweb.PublicBase(d.getenv), "/")
	link := fmt.Sprintf("%s/l/%s/%d/claim#c=%s", base, apt.permalink, st.id, claimSecretMarker)
	return enqueueClaimMail(ctx, d, st, apt, addr, lang, secret, version, resend, link, stamp)
}

func enqueueClaimMail(ctx context.Context, d claimOpsDeps, st *claimStay, apt *claimApt, addr, lang, secret string, version int64, resend bool, link, stamp string) error {
	keys, err := secure.LoadDataKeys(d.getenv)
	if err != nil {
		return err
	}
	base := strings.TrimRight(hostweb.PublicBase(d.getenv), "/")
	enc, err := keys.EncryptString(secret)
	if err != nil {
		return err
	}
	var from, to string
	_ = d.pool.QueryRow(ctx, `SELECT COALESCE(date_from::text,''), COALESCE(date_to::text,'') FROM reservation WHERE id = $1`, st.id).Scan(&from, &to)
	var host *mailnotify.Host
	var contact string
	if apt.legalEntityID != nil {
		var h mailnotify.Host
		if err := d.pool.QueryRow(ctx, `SELECT COALESCE(name,''), COALESCE(seat,''), COALESCE(contact_email,''), COALESCE(contact_phone,'') FROM legal_entity WHERE id = $1`, *apt.legalEntityID).Scan(&h.Name, &h.Seat, &h.Email, &h.Phone); err == nil {
			host = &h
			contact = ubyport.NormaliseEmail(h.Email)
		}
	}
	content := mailnotify.BuildClaim(base, mailnotify.ClaimInput{Lang: lang, PropertyName: apt.name, Dates: mailnotify.CompletionDateRange(from, to), Link: link, Resend: resend, Host: host})
	kind, key := "claim", fmt.Sprintf("claim:%d:v%d", st.id, version)
	if resend {
		kind, key = "claim_resend", fmt.Sprintf("claim_resend:%d:v%d", st.id, version)
	}
	parts := map[string]any{"text": content.Text, "html": content.HTML, "lang": mailnotify.GuestLanguage(lang), mail.ClaimSecretPayloadKey: enc}
	if contact != "" {
		parts["reply_to"] = contact
	}
	payload, _ := json.Marshal(parts)
	owner := apt.ownerID
	res := st.id
	aptID := apt.id
	_, err = ubyport.EnqueueMail(ctx, d.pool, ubyport.OutboxMail{
		Kind: kind, Key: key,
		ReservationID: &res, ApartmentID: &aptID, OwnerUserID: &owner,
		To: addr, Subject: content.Subject, Payload: string(payload),
	})
	return err
}

// applyDeclaredInTx is headcount.apply_declared_in on an open transaction (demo paths).
func applyDeclaredInTx(ctx context.Context, tx pgx.Tx, reservationID int64, count int, now time.Time) (string, *int64, error) {
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "reservation", int32(reservationID)); err != nil {
		return "", nil, err
	}
	var status string
	var archived *string
	var override *int64
	var old *int64
	err := tx.QueryRow(ctx, `SELECT status, archived_at, expected_guests_override, declared_guests
		FROM reservation WHERE id = $1`, reservationID).Scan(&status, &archived, &override, &old)
	if errors.Is(err, pgx.ErrNoRows) {
		return "stay_gone", nil, nil
	}
	if err != nil {
		return "", nil, err
	}
	if status != "active" || archived != nil {
		return "stay_gone", old, nil
	}
	if override != nil && *override != 0 {
		return "host_set", old, nil
	}
	if count < 1 {
		return "out_of_range", old, nil
	}
	if count > 60 {
		return "above_ceiling", old, nil
	}
	if old != nil && int(*old) == count {
		return "unchanged", old, nil
	}
	var live int
	if err := tx.QueryRow(ctx, `SELECT COUNT(*) FROM guest WHERE reservation_id = $1 AND archived_at IS NULL`, reservationID).Scan(&live); err != nil {
		return "", nil, err
	}
	if count < max(1, live) {
		return "below_floor", old, nil
	}
	stamp := isoStamp(now)
	if _, err := tx.Exec(ctx, `UPDATE reservation SET declared_guests = $1, updated_at = $2 WHERE id = $3`, count, stamp, reservationID); err != nil {
		return "", nil, err
	}
	return "saved", old, nil
}

func recordDeclaredAudit(ctx context.Context, pool *pgxpool.Pool, resID int64, code string, old *int64, count int, ownerID *int64, stamp string) error {
	if code != "saved" && code != "below_floor" {
		return nil
	}
	action := "reservation_declared_guests_set"
	if code == "below_floor" {
		action = "reservation_declared_guests_refused"
	}
	detail := fmt.Sprintf("id=%d from=%v to=%d source=claim_confirm", resID, old, count)
	_, err := pool.Exec(ctx, auditSQL, stamp, "guest", action, detail, ownerID, nil, nil)
	return err
}
