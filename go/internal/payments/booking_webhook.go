package payments

// Go port of the booking-site Stripe webhook: App/app/booking_webhook.py
// (handle, _expire, _confirm, _refund_clash, _mail_confirmed, _mail_clash and
// their helpers), with the parts it calls: booking_site.py by_session, get,
// set_status, manage_url and manage_token; stripe_connect.py process_event (the
// dedupe around booking events), account_for_owner and _api; mail.enqueue;
// mail_notify._entity_contact_email; guest_slug.link_key. It writes the same
// rows, audit lines and outbox mails as Python (golden test:
// booking_webhook_test.go, fixture from App/scripts/booking_webhook_golden.py).
//
// It runs only when UBYHOST_GO_BOOKING_WEBHOOK=1. Otherwise webhook.go
// forwards booking events to Python exactly as before.
//
// Known gaps, deliberately not ported:
//   - booking_invoice.ensure (best effort in Python after the mails; needs the
//     invoice PDF code Go does not have). The invoice is then issued when the
//     guest first opens /p/{slug}/b/{id}/{token}/invoice.pdf (Python route),
//     with that day as its issue date.
//   - guest_slug.ensure minting a slug: when the apartment has a permalink
//     token but no current slug, Go links /l/<token>/<reservation> (the token
//     keeps working); Python would create the slug first.
//   - No Stripe network retries (see onboarder.go); Stripe redelivers the event.
//   - The secret key is loaded before any write, so a missing key answers 500
//     before the booking is confirmed (Python would fail after, in the mail).

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	_ "embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

//go:embed booking_i18n.json
var bookingJSON []byte

// bookingStrings holds the site_booking.mail.* and pp.book.policy.* keys (cs,
// en) of App/app/host_i18n.py, written by App/scripts/booking_webhook_golden.py.
var bookingStrings = hostweb.Load(bookingJSON)

const (
	// BookingSwitchEnv turns the Go handler on with the value "1".
	BookingSwitchEnv = "UBYHOST_GO_BOOKING_WEBHOOK"
	bookingLockName  = "booking_site_dates" // db.lock_key name, shared with Python
	bookingBaseURL   = "http://127.0.0.1:8080"
)

const (
	eventSeenSQL   = `SELECT 1 FROM stripe_webhook_event WHERE event_id = $1`
	bookingColumns = `id, apartment_id, owner_user_id, hold_id, status, date_from, date_to, guests,
		guest_name, guest_email, total_czk, lang, cancellation_policy, pay_method`
	bookingBySessionSQL = `SELECT ` + bookingColumns + ` FROM site_booking WHERE stripe_session_id = $1`
	bookingByIDSQL      = `SELECT ` + bookingColumns + ` FROM site_booking WHERE id = $1`
	bookingStatusSQL    = `SELECT status FROM site_booking WHERE id = $1`
	bookingLockSQL      = `SELECT pg_advisory_xact_lock(hashtext($1), $2)`
	bookingClashSQL     = `SELECT id FROM reservation WHERE apartment_id = $1 AND status = 'active'
		AND date_from < $2 AND date_to > $3 LIMIT 1`
	bookingReservationSQL = `INSERT INTO reservation (apartment_id, source, uid, date_from, date_to,
		summary, expected_guests_override, guest_email, status, created_at, updated_at)
		VALUES ($1, 'site', $2, $3, $4, $5, $6, $7, 'active', $8, $8) RETURNING id`
	bookingPaidSQL = `UPDATE site_booking SET status = 'paid', reservation_id = $1,
		stripe_payment_intent_id = $2, paid_at = $3, updated_at = $3
		WHERE id = $4 AND status IN ('pending', 'expired')`
	bookingHoldDeleteSQL = `DELETE FROM booking_hold WHERE id = $1`
	bookingApartmentSQL  = `SELECT internal_name, legal_entity_id, permalink_token FROM apartment WHERE id = $1`
	bookingEntityMailSQL = `SELECT contact_email FROM legal_entity WHERE id = $1`
	bookingSlugSQL       = `SELECT slug FROM apartment_slug WHERE apartment_id = $1 AND is_current = 1`
	bookingPageSlugSQL   = `SELECT slug FROM property_slug WHERE apartment_id = $1`
)

// bookingTransitions is booking_site._TRANSITIONS.
var bookingTransitions = map[string]map[string]bool{
	"pending":        {"paid": true, "expired": true, "clash_refunded": true},
	"requested":      {"paid": true, "expired": true, "cancelled": true},
	"paid":           {"cancelled": true, "refunded": true, "clash_refunded": true},
	"cancelled":      {"refunded": true},
	"expired":        {"paid": true, "clash_refunded": true, "cancelled": true},
	"refunded":       {},
	"clash_refunded": {},
}

// siteBooking is the part of a site_booking row the handler reads.
type siteBooking struct {
	id, apartmentID, ownerUserID int64
	holdID                       *int64
	status, dateFrom, dateTo     string
	guests, totalCZK             int64
	guestName, guestEmail        *string
	lang, policy, payMethod      string
}

type bookingApartment struct {
	found          bool
	internalName   string
	legalEntityID  *int64
	permalinkToken *string
}

// bookingField is one extra column set_status writes, in Python's order.
type bookingField struct {
	name  string
	value any
}

// BookingWebhook handles booking events. Stripe is used for the clash refund
// only; tests point Stripe.APIBase at httptest. Building it touches nothing.
type BookingWebhook struct {
	Pool   *pgxpool.Pool
	Getenv func(string) string
	Now    func() time.Time
	Stripe *StripeOnboarder
}

// bookingSwitchOn is UBYHOST_GO_BOOKING_WEBHOOK == "1" (trimmed).
func bookingSwitchOn(getenv func(string) string) bool {
	return strings.TrimSpace(getenv(BookingSwitchEnv)) == "1"
}

// NewBookingWebhook returns the production handler. It does not use the pool.
func NewBookingWebhook(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) *BookingWebhook {
	return &BookingWebhook{Pool: pool, Getenv: getenv, Now: now, Stripe: NewStripeOnboarder(pool, getenv, now)}
}

// Process is stripe_connect.process_event for a booking event: a seen event id
// is a no-op; the id is recorded only after the handler returned, so an error
// leaves it unrecorded and Stripe's retry runs it again.
func (b *BookingWebhook) Process(ctx context.Context, ev stripeEvent, mode string) error {
	if ev.ID == "" {
		return errors.New("event without id")
	}
	var one int
	err := b.Pool.QueryRow(ctx, eventSeenSQL, ev.ID).Scan(&one)
	if err == nil {
		return nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	if err := b.handle(ctx, ev); err != nil {
		return err
	}
	_, err = b.Pool.Exec(ctx, insertEventSQL, ev.ID, ev.Type, mode, stampAt(b.Now()))
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) && pgErr.Code == "23505" {
		return nil
	}
	return err
}

// handle is booking_webhook.handle.
func (b *BookingWebhook) handle(ctx context.Context, ev stripeEvent) error {
	obj := ev.Data.Object
	session, _ := obj["id"].(string)
	bk, err := b.booking(ctx, bookingBySessionSQL, session)
	if err != nil {
		return err
	}
	if bk == nil {
		log.Printf("booking webhook: no booking for session %s", session)
		return nil
	}
	if ev.Type == "checkout.session.expired" || ev.Type == "checkout.session.async_payment_failed" {
		return b.expire(ctx, bk)
	}
	if ps, _ := obj["payment_status"].(string); ps != "paid" {
		return nil // async method still pending; async_payment_succeeded follows
	}
	if bk.status != "pending" && bk.status != "expired" {
		return nil // already handled
	}
	intent, _ := obj["payment_intent"].(string)
	return b.confirm(ctx, bk, intent)
}

// booking reads one row; nil when there is none.
func (b *BookingWebhook) booking(ctx context.Context, sql string, arg any) (*siteBooking, error) {
	var bk siteBooking
	err := b.Pool.QueryRow(ctx, sql, arg).Scan(&bk.id, &bk.apartmentID, &bk.ownerUserID, &bk.holdID,
		&bk.status, &bk.dateFrom, &bk.dateTo, &bk.guests, &bk.guestName, &bk.guestEmail, &bk.totalCZK,
		&bk.lang, &bk.policy, &bk.payMethod)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &bk, nil
}

// expire is _expire.
func (b *BookingWebhook) expire(ctx context.Context, bk *siteBooking) error {
	if bk.status != "pending" {
		return nil
	}
	if _, err := b.setStatus(ctx, bk.id, "expired", nil); err != nil {
		return err
	}
	if bk.holdID != nil && *bk.holdID != 0 {
		if _, err := b.Pool.Exec(ctx, bookingHoldDeleteSQL, *bk.holdID); err != nil {
			return err
		}
	}
	return nil
}

// setStatus is booking_site.set_status: false when the row is already there,
// an error for a missing row or an illegal move.
func (b *BookingWebhook) setStatus(ctx context.Context, id int64, to string, fields []bookingField) (bool, error) {
	var cur string
	err := b.Pool.QueryRow(ctx, bookingStatusSQL, id).Scan(&cur)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, errors.New("no such booking")
	}
	if err != nil {
		return false, err
	}
	if cur == to {
		return false, nil
	}
	if !bookingTransitions[cur][to] {
		return false, fmt.Errorf("site_booking %d: %s -> %s", id, cur, to)
	}
	args := []any{to, stampAt(b.Now())}
	sql := "UPDATE site_booking SET status = $1, updated_at = $2"
	for _, f := range fields {
		args = append(args, f.value)
		sql += fmt.Sprintf(", %s = $%d", f.name, len(args))
	}
	args = append(args, id, cur)
	sql += fmt.Sprintf(" WHERE id = $%d AND status = $%d", len(args)-1, len(args))
	tag, err := b.Pool.Exec(ctx, sql, args...)
	if err != nil {
		return false, err
	}
	return tag.RowsAffected() == 1, nil
}

// confirm is _confirm: under the per-apartment lock, re-read the status, check
// for a clash, write the stay and mark the booking paid, release the hold.
func (b *BookingWebhook) confirm(ctx context.Context, bk *siteBooking, intent string) error {
	secret, err := secure.LoadSecret(b.Getenv)
	if err != nil {
		return err
	}
	stamp := stampAt(b.Now())
	tx, err := b.Pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	if _, err := tx.Exec(ctx, bookingLockSQL, bookingLockName, int32(bk.apartmentID)); err != nil {
		return err
	}
	// Stripe often delivers completed and async_payment_succeeded together;
	// without this re-read the stay just written looks like a double booking.
	var live string
	err = tx.QueryRow(ctx, bookingStatusSQL, bk.id).Scan(&live)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil
	}
	if err != nil {
		return err
	}
	if live != "pending" && live != "expired" {
		return nil
	}
	var other int64
	err = tx.QueryRow(ctx, bookingClashSQL, bk.apartmentID, bk.dateTo, bk.dateFrom).Scan(&other)
	clash := err == nil
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	var reservationID int64
	if !clash {
		err = tx.QueryRow(ctx, bookingReservationSQL, bk.apartmentID, fmt.Sprintf("site-%d", bk.id),
			bk.dateFrom, bk.dateTo, bk.guestName, bk.guests, bk.guestEmail, stamp).Scan(&reservationID)
		if err != nil {
			return err
		}
		var pi *string
		if intent != "" {
			pi = &intent
		}
		if _, err := tx.Exec(ctx, bookingPaidSQL, reservationID, pi, stamp, bk.id); err != nil {
			return err
		}
	}
	if bk.holdID != nil && *bk.holdID != 0 {
		if _, err := tx.Exec(ctx, bookingHoldDeleteSQL, *bk.holdID); err != nil {
			return err
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return err
	}
	if clash {
		return b.refundClash(ctx, bk, intent)
	}
	if err := audit(ctx, b.Pool, stampAt(b.Now()), "site_booking_paid",
		fmt.Sprintf("id=%d reservation=%d", bk.id, reservationID), bk.ownerUserID); err != nil {
		return err
	}
	fresh, err := b.booking(ctx, bookingByIDSQL, bk.id)
	if err != nil {
		return err
	}
	if fresh == nil {
		fresh = bk
	}
	// booking_invoice.ensure is not ported (known gap, see the file comment).
	return b.mailConfirmed(ctx, fresh, reservationID, secret)
}

// refundClash is _refund_clash: a full refund on the host's connected account.
// Any failure is returned, so the webhook answers 500 and Stripe retries.
func (b *BookingWebhook) refundClash(ctx context.Context, bk *siteBooking, intent string) error {
	account, err := b.Stripe.existingAccount(ctx, bk.ownerUserID)
	if err != nil {
		return err
	}
	if account == "" || intent == "" {
		return fmt.Errorf("site booking %d: cannot refund (no account or intent)", bk.id)
	}
	key, _, err := b.Stripe.guard(ctx)
	if err != nil {
		return err
	}
	form := url.Values{}
	form.Set("payment_intent", intent)
	form.Set("metadata[site_booking_id]", strconv.FormatInt(bk.id, 10))
	if err := b.refund(ctx, key, account, fmt.Sprintf("site_booking_clash_refund_%d", bk.id), form); err != nil {
		return err
	}
	if _, err := b.setStatus(ctx, bk.id, "clash_refunded", []bookingField{
		{"refunded_czk", bk.totalCZK}, {"stripe_payment_intent_id", intent},
	}); err != nil {
		return err
	}
	if err := audit(ctx, b.Pool, stampAt(b.Now()), "site_booking_clash_refunded",
		fmt.Sprintf("id=%d amount=%d", bk.id, bk.totalCZK), bk.ownerUserID); err != nil {
		return err
	}
	return b.mailClash(ctx, bk)
}

// refund posts /v1/refunds on the connected account with an idempotency key.
// A non-2xx reply is an error naming the status and Stripe's message and code.
func (b *BookingWebhook) refund(ctx context.Context, key, account, idem string, form url.Values) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, b.Stripe.base()+"/v1/refunds",
		strings.NewReader(form.Encode()))
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Bearer "+key)
	req.Header.Set("Stripe-Version", stripeVersion)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Stripe-Account", account)
	req.Header.Set("Idempotency-Key", idem)
	resp, err := b.Stripe.client().Do(req)
	if err != nil {
		return fmt.Errorf("stripe: POST /v1/refunds: %w", err)
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, stripeMaxResponse))
	if err != nil {
		return err
	}
	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		var se struct {
			Error struct {
				Message string `json:"message"`
				Code    string `json:"code"`
			} `json:"error"`
		}
		_ = json.Unmarshal(raw, &se)
		return fmt.Errorf("stripe: POST /v1/refunds: HTTP %d: %s (%s)", resp.StatusCode,
			se.Error.Message, se.Error.Code)
	}
	return nil
}

// --- mails -------------------------------------------------------------------

func (b *BookingWebhook) apartment(ctx context.Context, id int64) (bookingApartment, error) {
	var a bookingApartment
	err := b.Pool.QueryRow(ctx, bookingApartmentSQL, id).Scan(&a.internalName, &a.legalEntityID, &a.permalinkToken)
	if errors.Is(err, pgx.ErrNoRows) {
		return bookingApartment{}, nil
	}
	if err != nil {
		return bookingApartment{}, err
	}
	a.found = true
	return a, nil
}

// hostEmail is _host_email via mail_notify._entity_contact_email.
func (b *BookingWebhook) hostEmail(ctx context.Context, a bookingApartment) (string, error) {
	if !a.found || a.legalEntityID == nil || *a.legalEntityID == 0 {
		return "", nil
	}
	var contact *string
	err := b.Pool.QueryRow(ctx, bookingEntityMailSQL, *a.legalEntityID).Scan(&contact)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	if contact == nil {
		return "", nil
	}
	return ubyport.NormaliseEmail(*contact), nil
}

// linkKey is guest_slug.link_key without the minting (known gap).
func (b *BookingWebhook) linkKey(ctx context.Context, apartmentID int64, a bookingApartment) (string, error) {
	if !a.found || a.permalinkToken == nil || *a.permalinkToken == "" {
		return "", nil
	}
	var slug string
	err := b.Pool.QueryRow(ctx, bookingSlugSQL, apartmentID).Scan(&slug)
	if errors.Is(err, pgx.ErrNoRows) {
		return *a.permalinkToken, nil
	}
	if err != nil {
		return "", err
	}
	if slug == "" {
		return *a.permalinkToken, nil
	}
	return slug, nil
}

// baseURL is config.PUBLIC_BASE_URL with trailing slashes removed.
func (b *BookingWebhook) baseURL() string {
	v := b.Getenv("UBYHOST_PUBLIC_BASE_URL")
	if v == "" {
		v = bookingBaseURL
	}
	return strings.TrimRight(v, "/")
}

// manageURL is booking_site.manage_url with manage_token.
func (b *BookingWebhook) manageURL(ctx context.Context, bk *siteBooking, secret string) (string, error) {
	slug := "x"
	var s string
	err := b.Pool.QueryRow(ctx, bookingPageSlugSQL, bk.apartmentID).Scan(&s)
	if err == nil {
		slug = s
	} else if !errors.Is(err, pgx.ErrNoRows) {
		return "", err
	}
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(fmt.Sprintf("site_booking:%d", bk.id)))
	token := hex.EncodeToString(mac.Sum(nil))[:40]
	return fmt.Sprintf("%s/p/%s/b/%d/%s", b.baseURL(), slug, bk.id, token), nil
}

// bookingDates is _dates: "1. 2. 2027 – 3. 2. 2027" in cs, ISO otherwise.
func bookingDates(bk *siteBooking, lang string) (string, error) {
	one := func(iso string) (string, error) {
		d, err := time.Parse("2006-01-02", iso)
		if err != nil {
			return "", err
		}
		if lang == "cs" {
			return fmt.Sprintf("%d. %d. %d", d.Day(), int(d.Month()), d.Year()), nil
		}
		return iso, nil
	}
	from, err := one(bk.dateFrom)
	if err != nil {
		return "", err
	}
	to, err := one(bk.dateTo)
	if err != nil {
		return "", err
	}
	return from + " – " + to, nil
}

// facts is _facts.
func bookingFacts(bk *siteBooking, a bookingApartment, lang string) (map[string]any, error) {
	dates, err := bookingDates(bk, lang)
	if err != nil {
		return nil, err
	}
	return map[string]any{
		"property": a.internalName,
		"dates":    dates,
		"guests":   bk.guests,
		"total":    bk.totalCZK,
		"name":     deref0(bk.guestName),
		"email":    deref0(bk.guestEmail),
		"policy":   bookingStrings.T(lang, "pp.book.policy."+bk.policy, nil),
	}, nil
}

func deref0(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

func bookingLang(bk *siteBooking) string {
	if bk.lang == "cs" || bk.lang == "en" {
		return bk.lang
	}
	return "cs"
}

// mailConfirmed is _mail_confirmed.
func (b *BookingWebhook) mailConfirmed(ctx context.Context, bk *siteBooking, reservationID int64, secret string) error {
	a, err := b.apartment(ctx, bk.apartmentID)
	if err != nil {
		return err
	}
	host, err := b.hostEmail(ctx, a)
	if err != nil {
		return err
	}
	lang := bookingLang(bk)
	facts, err := bookingFacts(bk, a, lang)
	if err != nil {
		return err
	}
	key, err := b.linkKey(ctx, bk.apartmentID, a)
	if err != nil {
		return err
	}
	direct := bk.payMethod == "direct"
	textKey, manageKey, hostKey := "site_booking.mail.guest_text", "site_booking.mail.guest_manage", "site_booking.mail.host_text"
	if direct {
		textKey, manageKey, hostKey = textKey+"_direct", manageKey+"_direct", hostKey+"_direct"
	}
	body := bookingStrings.T(lang, textKey, facts)
	if key != "" {
		link := fmt.Sprintf("%s/l/%s/%d", b.baseURL(), key, reservationID)
		body += "\n\n" + bookingStrings.T(lang, "site_booking.mail.guest_register", map[string]any{"link": link})
	}
	manage, err := b.manageURL(ctx, bk, secret)
	if err != nil {
		return err
	}
	body += "\n\n" + bookingStrings.T(lang, manageKey, map[string]any{"link": manage})
	if deref0(bk.guestEmail) != "" {
		b.enqueue(ctx, "site_booking_confirmed", fmt.Sprintf("site_booking:%d:confirmed", bk.id), *bk.guestEmail,
			bookingStrings.T(lang, "site_booking.mail.guest_subject", facts),
			`{"text": `+ubyport.PyString(body)+`, "lang": `+ubyport.PyString(lang)+`, "reply_to": `+ubyport.PyString(host)+`}`,
			host, true, &reservationID, bk)
	}
	if host != "" {
		hostFacts, err := bookingFacts(bk, a, "cs")
		if err != nil {
			return err
		}
		b.enqueue(ctx, "site_booking_host", fmt.Sprintf("site_booking:%d:host_new", bk.id), host,
			bookingStrings.T("cs", "site_booking.mail.host_subject", hostFacts),
			`{"text": `+ubyport.PyString(bookingStrings.T("cs", hostKey, hostFacts))+`, "lang": "cs"}`,
			"", false, &reservationID, bk)
	}
	return nil
}

// mailClash is _mail_clash.
func (b *BookingWebhook) mailClash(ctx context.Context, bk *siteBooking) error {
	a, err := b.apartment(ctx, bk.apartmentID)
	if err != nil {
		return err
	}
	host, err := b.hostEmail(ctx, a)
	if err != nil {
		return err
	}
	lang := bookingLang(bk)
	facts, err := bookingFacts(bk, a, lang)
	if err != nil {
		return err
	}
	if deref0(bk.guestEmail) != "" {
		b.enqueue(ctx, "site_booking_refunded", fmt.Sprintf("site_booking:%d:clash_refund", bk.id), *bk.guestEmail,
			bookingStrings.T(lang, "site_booking.mail.clash_subject", facts),
			`{"text": `+ubyport.PyString(bookingStrings.T(lang, "site_booking.mail.clash_text", facts))+
				`, "lang": `+ubyport.PyString(lang)+`, "reply_to": `+ubyport.PyString(host)+`}`,
			host, true, nil, bk)
	}
	if host != "" {
		hostFacts, err := bookingFacts(bk, a, "cs")
		if err != nil {
			return err
		}
		b.enqueue(ctx, "site_booking_host", fmt.Sprintf("site_booking:%d:host_clash", bk.id), host,
			bookingStrings.T("cs", "site_booking.mail.host_clash_subject", hostFacts),
			`{"text": `+ubyport.PyString(bookingStrings.T("cs", "site_booking.mail.host_clash_text", hostFacts))+`, "lang": "cs"}`,
			"", false, nil, bk)
	}
	return nil
}

// enqueue is mail.enqueue for these kinds. Mail off or an address that does not
// normalise queue nothing. The demo-stay guard is not needed: the stay is
// source 'site'. A failure is logged, not returned, as Python's enqueue does.
func (b *BookingWebhook) enqueue(ctx context.Context, kind, key, to, subject, payload, replyTo string,
	guestKind bool, reservationID *int64, bk *siteBooking) {
	if !mailOn(b.Getenv) {
		log.Printf("mail disabled; skip enqueue kind=%s key=%s", kind, key)
		return
	}
	to = ubyport.NormaliseEmail(to)
	if to == "" {
		return
	}
	if guestKind && ubyport.NormaliseEmail(replyTo) == "" {
		log.Printf("guest mail has no reply_to kind=%s key=%s", kind, key)
	}
	apartment, owner := bk.apartmentID, bk.ownerUserID
	if _, err := ubyport.EnqueueMail(ctx, b.Pool, ubyport.OutboxMail{
		Kind:          kind,
		Key:           key,
		ReservationID: reservationID,
		ApartmentID:   &apartment,
		OwnerUserID:   &owner,
		To:            to,
		Subject:       subject,
		Payload:       payload,
	}); err != nil {
		log.Printf("mail enqueue failed kind=%s key=%s", kind, key)
	}
}
