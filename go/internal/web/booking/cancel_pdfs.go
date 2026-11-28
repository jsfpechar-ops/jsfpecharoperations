// Guest cancel POST and invoice PDFs: property_page.py booking_manage_cancel,
// booking_invoice_pdf, booking_correction_pdf and booking_manage_calendar.

package booking

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/invoices"
)

const (
	scopeCancel  = "booking_cancel"
	scopeInvoice = "booking_invoice"
)

var siteTransitions = map[string]map[string]bool{
	"pending":        {"paid": true, "expired": true, "clash_refunded": true},
	"requested":      {"paid": true, "expired": true, "cancelled": true},
	"paid":           {"cancelled": true, "refunded": true, "clash_refunded": true},
	"cancelled":      {"refunded": true},
	"expired":        {"paid": true, "clash_refunded": true, "cancelled": true},
	"refunded":       {},
	"clash_refunded": {},
}

func intentKey(bookingID int64) string {
	return fmt.Sprintf("site_booking_refund_intent:%d", bookingID)
}

func getSetting(ctx context.Context, db DB, key string) (string, error) {
	var v *string
	err := db.QueryRow(ctx, `SELECT value FROM settings WHERE key = $1`, key).Scan(&v)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	if v == nil {
		return "", err
	}
	return *v, nil
}

func stampUTC(now time.Time) string {
	return now.UTC().Format("2006-01-02T15:04:05+00:00")
}

// cancelRow is the site_booking fields booking_cancel.cancel reads.
type cancelRow struct {
	SiteBooking
	OwnerUserID         int64
	ReservationID       *int64
	StripePaymentIntent *string
}

func loadCancelRow(ctx context.Context, db DB, id int64) (cancelRow, bool, error) {
	var c cancelRow
	c.ID = id
	var email, paid, intent *string
	err := db.QueryRow(ctx, `SELECT apartment_id, owner_user_id, status, pay_method, date_from, date_to, guests, nights,
		total_czk, refunded_czk, cleaning_fee_czk, cancellation_policy, guest_email, lang, paid_at, invoice_id,
		reservation_id, stripe_payment_intent_id
		FROM site_booking WHERE id = $1`, id).Scan(
		&c.ApartmentID, &c.OwnerUserID, &c.Status, &c.PayMethod, &c.DateFrom, &c.DateTo, &c.Guests, &c.Nights,
		&c.TotalCZK, &c.RefundedCZK, &c.CleaningFeeCZK, &c.Policy, &email, &c.Lang, &paid, &c.InvoiceID,
		&c.ReservationID, &intent)
	if errors.Is(err, pgx.ErrNoRows) {
		return c, false, nil
	}
	if email != nil {
		c.GuestEmail = *email
	}
	c.PaidAt = paid != nil && *paid != ""
	if intent != nil {
		c.StripePaymentIntent = intent
	}
	return c, err == nil, err
}

type cancelResult struct {
	Error     string
	RefundCZK int
}

// StripeRefunder posts a connected-account refund. nil means skip the call (tests).
type StripeRefunder func(ctx context.Context, ownerUserID int64, paymentIntent string, amountCZK, bookingID int64) error

// GuestCancel is booking_cancel.cancel(by_host=false). Safe to call twice.
func GuestCancel(ctx context.Context, db DB, bookingID int64, now time.Time, refund StripeRefunder) (cancelResult, error) {
	b, ok, err := loadCancelRow(ctx, db, bookingID)
	if err != nil {
		return cancelResult{}, err
	}
	if !ok {
		return cancelResult{Error: "not_found"}, nil
	}
	if b.PayMethod == "direct" {
		return cancelResult{Error: "not_cancellable"}, nil
	}
	amount := 0
	byHost := false
	if b.Status == "paid" {
		settings, err := LoadSettings(ctx, db, b.ApartmentID)
		if err != nil {
			return cancelResult{}, err
		}
		if started, err := Started(b.SiteBooking, settings.CheckinHour, now); err != nil {
			return cancelResult{}, err
		} else if started {
			return cancelResult{Error: "started"}, nil
		}
		amount, err = RefundCZK(RefundBooking{TotalCZK: b.TotalCZK, RefundedCZK: b.RefundedCZK, CleaningFeeCZK: b.CleaningFeeCZK,
			DateFrom: b.DateFrom, CancellationPolicy: b.Policy}, settings.CheckinHour, now, false)
		if err != nil {
			return cancelResult{}, err
		}
		if err := setSetting(ctx, db, intentKey(bookingID), fmt.Sprintf("%d:g", amount)); err != nil {
			return cancelResult{}, err
		}
		moved, err := setBookingStatus(ctx, db, bookingID, "cancelled", now, nil)
		if err != nil {
			return cancelResult{}, err
		}
		if !moved {
			return cancelResult{Error: "busy"}, nil
		}
		if err := freeReservationOnCancel(ctx, db, b, now); err != nil {
			return cancelResult{}, err
		}
		if _, err := db.Exec(ctx, `INSERT INTO audit (at, actor, action, detail, owner_user_id) VALUES ($1, '', $2, $3, $4)`,
			stampUTC(now), "site_booking_cancelled", fmt.Sprintf("id=%d by=guest refund=%d", bookingID, amount), b.OwnerUserID); err != nil {
			return cancelResult{}, err
		}
	} else if b.Status == "cancelled" && b.RefundedCZK == 0 {
		raw, err := getSetting(ctx, db, intentKey(bookingID))
		if err != nil {
			return cancelResult{}, err
		}
		num, who, _ := strings.Cut(raw, ":")
		if num == "" || who == "" || who != "g" {
			return cancelResult{Error: "not_cancellable"}, nil
		}
		var parseErr error
		amount, parseErr = strconv.Atoi(num)
		if parseErr != nil {
			return cancelResult{Error: "not_cancellable"}, nil
		}
		byHost = who == "h"
		if byHost {
			return cancelResult{Error: "not_cancellable"}, nil
		}
	} else {
		return cancelResult{Error: "not_cancellable"}, nil
	}
	if amount > 0 {
		if refund != nil && b.StripePaymentIntent != nil && *b.StripePaymentIntent != "" {
			if err := refund(ctx, b.OwnerUserID, *b.StripePaymentIntent, int64(amount), bookingID); err != nil {
				log.Printf("site booking %d: refund failed: %v", bookingID, err)
				return cancelResult{Error: "refund_failed", RefundCZK: amount}, nil
			}
		}
		fields := []statusField{{"refunded_czk", amount}}
		if _, err := setBookingStatus(ctx, db, bookingID, "refunded", now, fields); err != nil {
			return cancelResult{}, err
		}
		if _, err := db.Exec(ctx, `INSERT INTO audit (at, actor, action, detail, owner_user_id) VALUES ($1, '', $2, $3, $4)`,
			stampUTC(now), "site_booking_refunded", fmt.Sprintf("id=%d amount=%d", bookingID, amount), b.OwnerUserID); err != nil {
			return cancelResult{}, err
		}
		if pool, ok := db.(*pgxpool.Pool); ok {
			invoices.AdjustAfterRefund(ctx, pool, bookingID, amount, now)
		}
	}
	_ = byHost
	return cancelResult{RefundCZK: amount}, nil
}

type statusField struct {
	name  string
	value any
}

func setBookingStatus(ctx context.Context, db DB, id int64, to string, now time.Time, fields []statusField) (bool, error) {
	var cur string
	err := db.QueryRow(ctx, `SELECT status FROM site_booking WHERE id = $1`, id).Scan(&cur)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, errors.New("no such booking")
	}
	if err != nil {
		return false, err
	}
	if cur == to {
		return false, nil
	}
	if !siteTransitions[cur][to] {
		return false, fmt.Errorf("site_booking %d: %s -> %s", id, cur, to)
	}
	args := []any{to, stampUTC(now)}
	sql := "UPDATE site_booking SET status = $1, updated_at = $2"
	for _, f := range fields {
		args = append(args, f.value)
		sql += fmt.Sprintf(", %s = $%d", f.name, len(args))
	}
	args = append(args, id, cur)
	sql += fmt.Sprintf(" WHERE id = $%d AND status = $%d", len(args)-1, len(args))
	tag, err := db.Exec(ctx, sql, args...)
	if err != nil {
		return false, err
	}
	return tag.RowsAffected() == 1, nil
}

func freeReservationOnCancel(ctx context.Context, db DB, b cancelRow, now time.Time) error {
	if b.ReservationID == nil || *b.ReservationID == 0 {
		return nil
	}
	var status string
	err := db.QueryRow(ctx, `SELECT status FROM reservation WHERE id = $1`, *b.ReservationID).Scan(&status)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil
	}
	if err != nil || status != "active" {
		return err
	}
	_, err = db.Exec(ctx, `UPDATE reservation SET status = 'cancelled', updated_at = $1 WHERE id = $2 AND status = 'active'`,
		stampUTC(now), *b.ReservationID)
	return err
}

func invoicePDFBytes(ctx context.Context, db DB, id int64) ([]byte, string, error) {
	var blob []byte
	var sum *string
	var number string
	err := db.QueryRow(ctx, `SELECT pdf_blob, pdf_sha256, number FROM invoice WHERE id = $1`, id).Scan(&blob, &sum, &number)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, "", err
	}
	if err != nil {
		return nil, "", err
	}
	if len(blob) == 0 {
		return nil, "", errors.New("invoice_pdf_missing")
	}
	digest := sha256.Sum256(blob)
	if sum != nil && *sum != "" && hex.EncodeToString(digest[:]) != *sum {
		return nil, "", errors.New("invoice_pdf_mismatch")
	}
	return blob, number, nil
}

func ensureGuestInvoiceID(ctx context.Context, pool *pgxpool.Pool, b SiteBooking, at time.Time) (int64, bool, error) {
	if b.InvoiceID != nil && *b.InvoiceID != 0 {
		return *b.InvoiceID, true, nil
	}
	return invoices.EnsureSiteBooking(ctx, pool, b.ID, at)
}

func writePDF(w http.ResponseWriter, blob []byte, disp string) {
	h := w.Header()
	h.Set("Content-Type", "application/pdf")
	h.Set("Content-Disposition", disp)
	h.Set("Cache-Control", "no-store")
	h.Set("X-Robots-Tag", "noindex")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(blob)
}

// RegisterCancelPDFs wires the four guest routes (dormant until UBYHOST_GO_PATHS).
func RegisterCancelPDFs(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time,
	wrap func(string, http.HandlerFunc) http.Handler) {
	mux.Handle("POST /p/{slug}/b/{booking_id}/{token}/cancel",
		wrap("/p/{slug}/b/{booking_id}/{token}/cancel", manageCancelHandler(pool, getenv, now, nil)))
	mux.Handle("GET /p/{slug}/b/{booking_id}/{token}/invoice.pdf",
		wrap("/p/{slug}/b/{booking_id}/{token}/invoice.pdf", invoicePDFHandler(pool, getenv, now)))
	mux.Handle("GET /p/{slug}/b/{booking_id}/{token}/correction.pdf",
		wrap("/p/{slug}/b/{booking_id}/{token}/correction.pdf", correctionPDFHandler(pool, getenv, now)))
}

func manageCancelHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, refund StripeRefunder) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method", http.StatusMethodNotAllowed)
			return
		}
		at := now()
		if limited(w, r, pool, scopeCancel, at) {
			return
		}
		id, err := strconv.ParseInt(r.PathValue("booking_id"), 10, 64)
		if err != nil {
			http.NotFound(w, r)
			return
		}
		secret, err := secure.LoadSecret(getenv)
		if err != nil {
			serverError(w, "cancel secret", err)
			return
		}
		ctx := r.Context()
		b, err := BookingForToken(ctx, pool, secret, id, r.PathValue("token"), false)
		if err != nil {
			serverError(w, "cancel booking", err)
			return
		}
		if b == nil {
			http.NotFound(w, r)
			return
		}
		res, err := GuestCancel(ctx, pool, id, at, refund)
		if err != nil {
			serverError(w, "cancel", err)
			return
		}
		if res.Error == "not_found" {
			http.NotFound(w, r)
			return
		}
		q := url.Values{"lang": {manageLang(r, *b)}}
		if res.Error == "started" || res.Error == "busy" || res.Error == "refund_failed" {
			q.Set("e", res.Error)
		}
		slug, token := r.PathValue("slug"), r.PathValue("token")
		loc := fmt.Sprintf("/p/%s/b/%d/%s?%s", slug, id, token, q.Encode())
		http.Redirect(w, r, loc, http.StatusSeeOther)
	}
}

func invoicePDFHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		if limited(w, r, pool, scopeInvoice, at) {
			return
		}
		id, err := strconv.ParseInt(r.PathValue("booking_id"), 10, 64)
		if err != nil {
			http.NotFound(w, r)
			return
		}
		secret, err := secure.LoadSecret(getenv)
		if err != nil {
			serverError(w, "invoice secret", err)
			return
		}
		if !ManageTokenOK(secret, id, r.PathValue("token")) {
			http.NotFound(w, r)
			return
		}
		ctx := r.Context()
		b, ok, err := LoadSiteBooking(ctx, pool, id)
		if err != nil {
			serverError(w, "invoice booking", err)
			return
		}
		if !ok {
			http.NotFound(w, r)
			return
		}
		invID, have, err := ensureGuestInvoiceID(ctx, pool, b, at)
		if err != nil {
			serverError(w, "ensure invoice", err)
			return
		}
		if !have {
			http.NotFound(w, r)
			return
		}
		blob, number, err := invoicePDFBytes(ctx, pool, invID)
		if err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				http.NotFound(w, r)
				return
			}
			serverError(w, "invoice pdf", err)
			return
		}
		writePDF(w, blob, `attachment; filename="faktura-`+number+`.pdf"`)
	}
}

func correctionPDFHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		if limited(w, r, pool, scopeInvoice, at) {
			return
		}
		id, err := strconv.ParseInt(r.PathValue("booking_id"), 10, 64)
		if err != nil {
			http.NotFound(w, r)
			return
		}
		secret, err := secure.LoadSecret(getenv)
		if err != nil {
			serverError(w, "correction secret", err)
			return
		}
		if !ManageTokenOK(secret, id, r.PathValue("token")) {
			http.NotFound(w, r)
			return
		}
		ctx := r.Context()
		b, ok, err := LoadSiteBooking(ctx, pool, id)
		if err != nil || !ok || b.InvoiceID == nil {
			http.NotFound(w, r)
			return
		}
		var corrID int64
		var number string
		err = pool.QueryRow(ctx, `SELECT id, number FROM invoice WHERE corrects_invoice_id = $1 ORDER BY id DESC LIMIT 1`,
			*b.InvoiceID).Scan(&corrID, &number)
		if errors.Is(err, pgx.ErrNoRows) {
			http.NotFound(w, r)
			return
		}
		if err != nil {
			serverError(w, "correction lookup", err)
			return
		}
		blob, _, err := invoicePDFBytes(ctx, pool, corrID)
		if err != nil {
			serverError(w, "correction pdf", err)
			return
		}
		writePDF(w, blob, `attachment; filename="opravny-doklad-`+number+`.pdf"`)
	}
}
