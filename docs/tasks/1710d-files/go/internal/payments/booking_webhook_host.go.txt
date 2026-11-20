package payments

// Host-side booking-site actions (brief 1710d): Python booking_direct.confirm/decline
// and booking_cancel.cancel(by_host=True), wired from booking_site_actions.go.

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

const (
	hostDirectErrNotFound       = "not_found"
	hostDirectErrNotConfirmable = "not_confirmable"
	hostDirectErrTaken          = "taken"
	hostCancelErrNotFound       = "not_found"
	hostCancelErrNotCancellable = "not_cancellable"
	hostCancelErrRefundFailed   = "refund_failed"
	hostCancelErrBusy           = "busy"
)

var directConfirmSQL = `UPDATE site_booking SET status = 'paid', reservation_id = $1,
	paid_at = $2, updated_at = $2 WHERE id = $3 AND status IN ('requested', 'expired')`

var directDeclineSQL = `UPDATE site_booking SET status = 'cancelled', cancelled_at = $1, updated_at = $1
	WHERE id = $2 AND status IN ('requested', 'expired')`

var holdClashSQL = `SELECT id FROM booking_hold WHERE apartment_id = $1 AND expires_at > $2
	AND date_from < $3 AND date_to > $4 AND id != $5 LIMIT 1`

// HostConfirmDirect marks a direct request paid and creates the reservation.
func (b *BookingWebhook) HostConfirmDirect(ctx context.Context, bookingID, ownerUserID int64) string {
	bk, err := b.booking(ctx, b.Pool, bookingByIDSQL, bookingID)
	if err != nil || bk == nil || bk.ownerUserID != ownerUserID || bk.payMethod != "direct" {
		return hostDirectErrNotFound
	}
	secret, err := secure.LoadSecret(b.Getenv)
	if err != nil {
		log.Printf("host confirm direct %d: secret: %v", bookingID, err)
		return hostDirectErrNotConfirmable
	}
	stamp := stampAt(b.Now())
	tx, err := b.Pool.Begin(ctx)
	if err != nil {
		log.Printf("host confirm direct %d: begin: %v", bookingID, err)
		return hostDirectErrNotConfirmable
	}
	defer tx.Rollback(ctx)
	if _, err := tx.Exec(ctx, bookingLockSQL, bookingLockName, int32(bk.apartmentID)); err != nil {
		return hostDirectErrNotConfirmable
	}
	var live string
	if err := tx.QueryRow(ctx, bookingStatusSQL, bookingID).Scan(&live); errors.Is(err, pgx.ErrNoRows) {
		return hostDirectErrNotFound
	} else if err != nil {
		return hostDirectErrNotConfirmable
	}
	if live != "requested" && live != "expired" {
		return hostDirectErrNotConfirmable
	}
	var other int64
	err = tx.QueryRow(ctx, bookingClashSQL, bk.apartmentID, bk.dateTo, bk.dateFrom).Scan(&other)
	if err == nil {
		return hostDirectErrTaken
	}
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return hostDirectErrNotConfirmable
	}
	holdSkip := int64(0)
	if bk.holdID != nil {
		holdSkip = *bk.holdID
	}
	err = tx.QueryRow(ctx, holdClashSQL, bk.apartmentID, stamp, bk.dateTo, bk.dateFrom, holdSkip).Scan(&other)
	if err == nil {
		return hostDirectErrTaken
	}
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return hostDirectErrNotConfirmable
	}
	var reservationID int64
	err = tx.QueryRow(ctx, bookingReservationSQL, bk.apartmentID, fmt.Sprintf("site-%d", bk.id),
		bk.dateFrom, bk.dateTo, deref0(bk.guestName), bk.guests, deref0(bk.guestEmail), stamp).Scan(&reservationID)
	if err != nil {
		return hostDirectErrNotConfirmable
	}
	tag, err := tx.Exec(ctx, directConfirmSQL, reservationID, stamp, bookingID)
	if err != nil || tag.RowsAffected() != 1 {
		return hostDirectErrNotConfirmable
	}
	if bk.holdID != nil && *bk.holdID != 0 {
		if _, err := tx.Exec(ctx, bookingHoldDeleteSQL, *bk.holdID); err != nil {
			return hostDirectErrNotConfirmable
		}
	}
	if err := audit(ctx, tx, stampAt(b.Now()), "site_booking_paid",
		fmt.Sprintf("id=%d reservation=%d direct", bookingID, reservationID), ownerUserID); err != nil {
		return hostDirectErrNotConfirmable
	}
	fresh, err := b.booking(ctx, tx, bookingByIDSQL, bookingID)
	if err != nil || fresh == nil {
		fresh = bk
	}
	if err := b.mailConfirmed(ctx, tx, fresh, reservationID, secret); err != nil {
		log.Printf("host confirm direct %d: mail: %v", bookingID, err)
	}
	if err := tx.Commit(ctx); err != nil {
		return hostDirectErrNotConfirmable
	}
	return ""
}

// HostDeclineDirect cancels a direct request and mails the guest.
func (b *BookingWebhook) HostDeclineDirect(ctx context.Context, bookingID, ownerUserID int64) string {
	bk, err := b.booking(ctx, b.Pool, bookingByIDSQL, bookingID)
	if err != nil || bk == nil || bk.ownerUserID != ownerUserID || bk.payMethod != "direct" {
		return hostDirectErrNotFound
	}
	stamp := stampAt(b.Now())
	tx, err := b.Pool.Begin(ctx)
	if err != nil {
		return hostDirectErrNotConfirmable
	}
	defer tx.Rollback(ctx)
	if _, err := tx.Exec(ctx, bookingLockSQL, bookingLockName, int32(bk.apartmentID)); err != nil {
		return hostDirectErrNotConfirmable
	}
	tag, err := tx.Exec(ctx, directDeclineSQL, stamp, bookingID)
	if err != nil || tag.RowsAffected() != 1 {
		return hostDirectErrNotConfirmable
	}
	if bk.holdID != nil && *bk.holdID != 0 {
		if _, err := tx.Exec(ctx, bookingHoldDeleteSQL, *bk.holdID); err != nil {
			return hostDirectErrNotConfirmable
		}
	}
	if err := audit(ctx, tx, stamp, "site_booking_declined", fmt.Sprintf("id=%d", bookingID), ownerUserID); err != nil {
		return hostDirectErrNotConfirmable
	}
	if err := b.mailDeclined(ctx, tx, bk); err != nil {
		log.Printf("host decline direct %d: mail: %v", bookingID, err)
	}
	if err := tx.Commit(ctx); err != nil {
		return hostDirectErrNotConfirmable
	}
	return ""
}

func (b *BookingWebhook) mailDeclined(ctx context.Context, q dbtx, bk *siteBooking) error {
	if deref0(bk.guestEmail) == "" {
		return nil
	}
	a, err := b.apartment(ctx, q, bk.apartmentID)
	if err != nil {
		return err
	}
	host, err := b.hostEmail(ctx, q, a)
	if err != nil {
		return err
	}
	lang := bookingLang(bk)
	facts, err := bookingFacts(bk, a, lang)
	if err != nil {
		return err
	}
	return b.enqueue(ctx, q, "site_booking_refunded", fmt.Sprintf("site_booking:%d:declined", bk.id), *bk.guestEmail,
		bookingStrings.T(lang, "site_booking.mail.declined_subject", facts),
		`{"text": `+ubyport.PyString(bookingStrings.T(lang, "site_booking.mail.declined_text", facts))+
			`, "lang": `+ubyport.PyString(lang)+`, "reply_to": `+ubyport.PyString(host)+`}`,
		host, true, nil, bk)
}

// HostCancelByHost is booking_cancel.cancel(..., by_host=True).
func (b *BookingWebhook) HostCancelByHost(ctx context.Context, bookingID, ownerUserID int64) (code string, refundCZK int) {
	bk, err := b.booking(ctx, b.Pool, bookingByIDSQL, bookingID)
	if err != nil || bk == nil || bk.ownerUserID != ownerUserID {
		return hostCancelErrNotFound, 0
	}
	return b.hostCancel(ctx, bk, true)
}

func (b *BookingWebhook) hostCancel(ctx context.Context, bk *siteBooking, byHost bool) (string, int) {
	owner := bk.ownerUserID
	amount := 0
	if bk.status == "paid" {
		var total, refunded int
		if err := b.Pool.QueryRow(ctx, `SELECT total_czk, COALESCE(refunded_czk, 0) FROM site_booking WHERE id = $1`, bk.id).
			Scan(&total, &refunded); err != nil {
			return hostCancelErrNotCancellable, 0
		}
		amount = total - refunded
		if amount < 0 {
			amount = 0
		}
		if bk.payMethod == "direct" {
			amount = 0
		}
		if err := b.setRefundIntent(ctx, bk.id, amount, byHost); err != nil {
			return hostCancelErrNotCancellable, 0
		}
		ok, err := b.setStatus(ctx, bk.id, "cancelled", []bookingField{{"cancelled_at", stampAt(b.Now())}})
		if err != nil {
			return hostCancelErrNotCancellable, 0
		}
		if !ok {
			return hostCancelErrBusy, 0
		}
		if err := b.freeReservation(ctx, bk); err != nil {
			log.Printf("host cancel %d: free reservation: %v", bk.id, err)
		}
		if err := audit(ctx, b.Pool, stampAt(b.Now()), "site_booking_cancelled",
			fmt.Sprintf("id=%d by=host refund=%d", bk.id, amount), owner); err != nil {
			log.Printf("host cancel %d: audit: %v", bk.id, err)
		}
	} else if bk.status == "cancelled" {
		raw, who, ok := b.readRefundIntent(ctx, bk.id)
		if !ok {
			return hostCancelErrNotCancellable, 0
		}
		amount, byHost = raw, who == "h"
	} else {
		return hostCancelErrNotCancellable, 0
	}
	if amount > 0 {
		if err := b.stripeCancelRefund(ctx, bk, amount); err != nil {
			log.Printf("host cancel %d: stripe refund: %v", bk.id, err)
			_ = b.mailRefundFailed(ctx, bk)
			return hostCancelErrRefundFailed, amount
		}
		if _, err := b.setStatus(ctx, bk.id, "refunded", []bookingField{{"refunded_czk", amount}}); err != nil {
			log.Printf("host cancel %d: refunded status: %v", bk.id, err)
		}
		if err := audit(ctx, b.Pool, stampAt(b.Now()), "site_booking_refunded",
			fmt.Sprintf("id=%d amount=%d", bk.id, amount), owner); err != nil {
			log.Printf("host cancel %d: refund audit: %v", bk.id, err)
		}
	}
	if err := b.mailCancelled(ctx, bk, amount, byHost); err != nil {
		log.Printf("host cancel %d: mail: %v", bk.id, err)
	}
	return "", amount
}

func (b *BookingWebhook) setRefundIntent(ctx context.Context, bookingID int64, amount int, byHost bool) error {
	who := "g"
	if byHost {
		who = "h"
	}
	key := fmt.Sprintf("site_booking_refund_intent:%d", bookingID)
	val := fmt.Sprintf("%d:%s", amount, who)
	_, err := b.Pool.Exec(ctx, `INSERT INTO settings (key, value) VALUES ($1, $2)
		ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value`, key, val)
	return err
}

func (b *BookingWebhook) readRefundIntent(ctx context.Context, bookingID int64) (amount int, who string, ok bool) {
	key := fmt.Sprintf("site_booking_refund_intent:%d", bookingID)
	var raw string
	err := b.Pool.QueryRow(ctx, `SELECT value FROM settings WHERE key = $1`, key).Scan(&raw)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, "", false
	}
	if err != nil {
		return 0, "", false
	}
	num, rest, _ := strings.Cut(raw, ":")
	if !isDigits(num) || (rest != "h" && rest != "g") {
		return 0, "", false
	}
	amount, _ = strconv.Atoi(num)
	return amount, rest, true
}

func isDigits(s string) bool {
	if s == "" {
		return false
	}
	for _, c := range s {
		if c < '0' || c > '9' {
			return false
		}
	}
	return true
}

func (b *BookingWebhook) freeReservation(ctx context.Context, bk *siteBooking) error {
	var resID *int64
	err := b.Pool.QueryRow(ctx, `SELECT reservation_id FROM site_booking WHERE id = $1`, bk.id).Scan(&resID)
	if errors.Is(err, pgx.ErrNoRows) || resID == nil || *resID == 0 {
		return nil
	}
	if err != nil {
		return err
	}
	var status string
	if err := b.Pool.QueryRow(ctx, `SELECT status FROM reservation WHERE id = $1`, *resID).Scan(&status); err != nil {
		return err
	}
	if status != "active" {
		return nil
	}
	_, err = b.Pool.Exec(ctx, `UPDATE reservation SET status = 'cancelled', updated_at = $1 WHERE id = $2`,
		stampAt(b.Now()), *resID)
	return err
}

func (b *BookingWebhook) stripeCancelRefund(ctx context.Context, bk *siteBooking, amountCZK int) error {
	var intent *string
	if err := b.Pool.QueryRow(ctx, `SELECT stripe_payment_intent_id FROM site_booking WHERE id = $1`, bk.id).Scan(&intent); err != nil {
		return err
	}
	account, err := b.Stripe.existingAccount(ctx, bk.ownerUserID)
	if err != nil {
		return err
	}
	if account == "" || intent == nil || *intent == "" {
		return fmt.Errorf("site booking %d: cannot refund", bk.id)
	}
	key, _, err := b.Stripe.guard(ctx)
	if err != nil {
		return err
	}
	form := url.Values{}
	form.Set("payment_intent", *intent)
	form.Set("amount", strconv.Itoa(amountCZK*100))
	form.Set("metadata[site_booking_id]", strconv.FormatInt(bk.id, 10))
	return b.refund(ctx, key, account, fmt.Sprintf("site_booking_cancel_refund_%d", bk.id), form)
}

func (b *BookingWebhook) mailCancelled(ctx context.Context, bk *siteBooking, amount int, byHost bool) error {
	a, err := b.apartment(ctx, b.Pool, bk.apartmentID)
	if err != nil {
		return err
	}
	host, err := b.hostEmail(ctx, b.Pool, a)
	if err != nil {
		return err
	}
	lang := bookingLang(bk)
	facts, err := bookingFacts(bk, a, lang)
	if err != nil {
		return err
	}
	facts["refund"] = amount
	direct := bk.payMethod == "direct"
	guestKey := "site_booking.mail.cancel_guest_none"
	if byHost && direct {
		guestKey = "site_booking.mail.cancel_guest_direct"
	} else if byHost {
		guestKey = "site_booking.mail.cancel_guest_by_host"
	} else if amount > 0 {
		guestKey = "site_booking.mail.cancel_guest_refund"
	}
	if deref0(bk.guestEmail) != "" {
		if err := b.enqueue(ctx, b.Pool, "site_booking_refunded", fmt.Sprintf("site_booking:%d:cancelled", bk.id), *bk.guestEmail,
			bookingStrings.T(lang, "site_booking.mail.cancel_subject", facts),
			`{"text": `+ubyport.PyString(bookingStrings.T(lang, guestKey, facts))+`, "lang": `+ubyport.PyString(lang)+
				`, "reply_to": `+ubyport.PyString(host)+`}`,
			host, true, nil, bk); err != nil {
			return err
		}
	}
	if host != "" {
		hostFacts, err := bookingFacts(bk, a, "cs")
		if err != nil {
			return err
		}
		hostFacts["refund"] = amount
		hostKey := "site_booking.mail.cancel_host_by_guest"
		if byHost && direct {
			hostKey = "site_booking.mail.cancel_host_direct"
		} else if byHost {
			hostKey = "site_booking.mail.cancel_host_by_host"
		}
		return b.enqueue(ctx, b.Pool, "site_booking_host", fmt.Sprintf("site_booking:%d:host_cancelled", bk.id), host,
			bookingStrings.T("cs", "site_booking.mail.host_cancel_subject", hostFacts),
			`{"text": `+ubyport.PyString(bookingStrings.T("cs", hostKey, hostFacts))+`, "lang": "cs"}`,
			"", false, nil, bk)
	}
	return nil
}

func (b *BookingWebhook) mailRefundFailed(ctx context.Context, bk *siteBooking) error {
	a, err := b.apartment(ctx, b.Pool, bk.apartmentID)
	if err != nil {
		return err
	}
	host, err := b.hostEmail(ctx, b.Pool, a)
	if err != nil || host == "" {
		return err
	}
	facts, err := bookingFacts(bk, a, "cs")
	if err != nil {
		return err
	}
	return b.enqueue(ctx, b.Pool, "site_booking_host", fmt.Sprintf("site_booking:%d:refund_failed", bk.id), host,
		bookingStrings.T("cs", "site_booking.mail.refund_failed_subject", facts),
		`{"text": `+ubyport.PyString(bookingStrings.T("cs", "site_booking.mail.refund_failed_text", facts))+`, "lang": "cs"}`,
		"", false, nil, bk)
}

// WebhookForHost returns a webhook helper for host booking-site POST routes.
func WebhookForHost(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) *BookingWebhook {
	return NewBookingWebhook(pool, getenv, now)
}
