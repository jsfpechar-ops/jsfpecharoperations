package invoices

// Site-booking stay invoices: Go port of App/app/booking_invoice.py (ensure,
// _form, _skipped) plus storno / partial credit-note helpers for cancellations.

import (
	"context"
	"errors"
	"fmt"
	"log"
	"math/big"
	"net/url"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type siteBookingRow struct {
	ID, ApartmentID, OwnerUserID int64
	ReservationID                *int64
	InvoiceID                    *int64
	Status                       string
	TotalCZK, CleaningFeeCZK     int
	GuestName, GuestEmail, Lang  string
}

// BookingIssueForm is booking_invoice._form: values the host invoice draft
// builder reads for a paid site booking.
func BookingIssueForm(totalCZK, cleaningCZK int, guestName, guestEmail, lang string) url.Values {
	if lang != "en" {
		lang = "cs"
	}
	note := ""
	if cleaningCZK > 0 {
		note = siteBookingT(lang, "site_booking.invoice.note", cleaningCZK)
	}
	v := url.Values{}
	v.Set("lang", lang)
	v.Set("stay_price", fmt.Sprintf("%d", totalCZK))
	v.Set("stay_vat_rate", "12")
	v.Set("buyer_name", guestName)
	v.Set("buyer_email", guestEmail)
	v.Set("already_paid", "1")
	v.Set("paid_via", "custom")
	v.Set("paid_via_custom", siteBookingT(lang, "site_booking.invoice.paid_via", 0))
	v.Set("note", note)
	return v
}

// EnsureSiteBooking is booking_invoice.ensure: returns the invoice id of a paid
// booking, issuing it (with stored PDF) when needed. ok is false when no invoice
// can be issued (best-effort; booking stays valid and guest download retries).
func EnsureSiteBooking(ctx context.Context, pool *pgxpool.Pool, bookingID int64, now time.Time) (int64, bool, error) {
	b, ok, err := loadSiteBooking(ctx, pool, bookingID)
	if err != nil || !ok {
		return 0, false, err
	}
	if b.Status != "paid" && b.Status != "cancelled" && b.Status != "refunded" {
		return 0, false, nil
	}
	if b.InvoiceID != nil {
		return *b.InvoiceID, true, nil
	}
	if b.ReservationID == nil {
		return 0, false, nil
	}
	apartment, err := loadApartment(ctx, pool, b.ApartmentID)
	if err != nil {
		return 0, false, err
	}
	reservation, err := loadReservation(ctx, pool, *b.ReservationID)
	if err != nil {
		return 0, false, err
	}
	var ent *entity
	if apartment.LegalEntityID != nil {
		e, err := scanEntity(pool.QueryRow(ctx, `SELECT `+entityColumns+` FROM legal_entity WHERE id = $1`, *apartment.LegalEntityID))
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return 0, false, err
		}
		if err == nil {
			ent = &e
		}
	}
	if apartment.ID == 0 || reservation.ReservationID == 0 || ent == nil {
		skipSiteBookingInvoice(ctx, pool, b, "no_entity", now)
		return 0, false, nil
	}
	lang := b.Lang
	if lang != "cs" && lang != "en" {
		lang = "cs"
	}
	st := &stay{
		ReservationID: reservation.ReservationID,
		ApartmentID:   reservation.ApartmentID,
		DateFrom:      reservation.DateFrom,
		DateTo:        reservation.DateTo,
		Status:        reservation.Status,
		Source:        reservation.Source,
		GuestEmail:    reservation.GuestEmail,
		PropertyName:  apartment.InternalName,
		EntityID:      apartment.LegalEntityID,
	}
	form := BookingIssueForm(b.TotalCZK, b.CleaningFeeCZK, b.GuestName, b.GuestEmail, lang)
	dr := buildDraft(*ent, form, pragueDay(now), st)
	dr.LegalEntityID = ent.ID
	dr.OwnerUserID = &b.OwnerUserID
	if issues := validateForIssue(dr); len(issues) > 0 {
		skipSiteBookingInvoice(ctx, pool, b, issues[0].Message, now)
		return 0, false, nil
	}
	id, _, err := writeIssued(ctx, pool, dr, nil, now)
	if err != nil {
		var lim *stayLimit
		if errors.As(err, &lim) {
			if lim.InvoiceID == 0 {
				skipSiteBookingInvoice(ctx, pool, b, lim.Key, now)
				return 0, false, nil
			}
			id = lim.InvoiceID
		} else {
			skipSiteBookingInvoice(ctx, pool, b, err.Error(), now)
			return 0, false, nil
		}
	}
	tag, err := pool.Exec(ctx,
		`UPDATE site_booking SET invoice_id = $1, updated_at = $2 WHERE id = $3 AND invoice_id IS NULL`,
		id, stamp(now), bookingID)
	if err != nil {
		return 0, false, err
	}
	if tag.RowsAffected() == 0 {
		var existing *int64
		if err := pool.QueryRow(ctx, `SELECT invoice_id FROM site_booking WHERE id = $1`, bookingID).Scan(&existing); err != nil {
			return 0, false, err
		}
		if existing != nil {
			return *existing, true, nil
		}
	}
	return id, true, nil
}

// StornoSiteBooking is invoices.cancel after a full refund (booking_cancel).
func StornoSiteBooking(ctx context.Context, pool *pgxpool.Pool, invoiceID int64, reason string, now time.Time) (int64, error) {
	return cancelIssuedInvoice(ctx, pool, invoiceID, reason, "", now, false, 0)
}

// CorrectSiteBookingPartial is invoices.correct_partial after a partial refund.
func CorrectSiteBookingPartial(ctx context.Context, pool *pgxpool.Pool, invoiceID int64, refundCZK int, reason string, now time.Time) (int64, error) {
	return cancelIssuedInvoice(ctx, pool, invoiceID, reason, "", now, true, refundCZK)
}

func cancelIssuedInvoice(ctx context.Context, pool *pgxpool.Pool, id int64, reason, correctionDate string, now time.Time, partial bool, refundCZK int) (int64, error) {
	original, err := scanInvoice(pool.QueryRow(ctx, `SELECT `+invoiceColumns+` FROM invoice WHERE id = $1`, id))
	if errors.Is(err, pgx.ErrNoRows) || (err == nil && original.Kind != "invoice") {
		return 0, errCancel("not_cancellable")
	}
	if err != nil {
		return 0, err
	}
	if utf8.RuneCountInString(strings.TrimSpace(reason)) < 5 {
		return 0, errCancel("reason_required")
	}
	var other int64
	err = pool.QueryRow(ctx, `SELECT id FROM invoice WHERE corrects_invoice_id = $1 LIMIT 1`, id).Scan(&other)
	if err == nil {
		return 0, errCancel("already_corrected")
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return 0, err
	}
	items, err := loadItems(ctx, pool, id)
	if err != nil {
		return 0, err
	}
	kind := "storno"
	if original.VATStatus == "payer" {
		kind = "corrective"
	}
	today := pragueDay(now).Format("2006-01-02")
	dateText := correctionDate
	if dateText == "" {
		dateText = today
	}
	if partial {
		haler := int64(refundCZK) * 100
		if haler <= 0 || haler >= original.TotalHaler || len(items) == 0 {
			return 0, fmt.Errorf("bad_amount")
		}
		stayIt := items[0]
		d, err := draftFromOriginal(ctx, pool, original, nil, kind, strings.TrimSpace(reason), dateText, today)
		if err != nil {
			return 0, err
		}
		it := item{
			Kind: stayIt.Kind, Description: siteBookingT(original.Lang, "site_booking.invoice.partial_item", 0),
			Quantity: 1, Unit: stayIt.Unit, Gross: -haler,
		}
		if original.VATStatus == "payer" && stayIt.VATRate != nil {
			rate := *stayIt.VATRate
			den := big.NewRat(100+rate, 100)
			gross := big.NewRat(haler, 1)
			base := roundHalfUp(new(big.Rat).Quo(gross, den)).Int64()
			vat := haler - base
			it.VATRate = stayIt.VATRate
			nb, nv := -base, -vat
			it.Base, it.VAT = &nb, &nv
			d.TotalBase, d.TotalVAT = &nb, &nv
		}
		d.Items = []item{it}
		d.TotalHaler = -haler
		newID, _, err := writeIssued(ctx, pool, d, nil, now)
		return newID, err
	}
	d, err := draftFromOriginal(ctx, pool, original, items, kind, strings.TrimSpace(reason), dateText, today)
	if err != nil {
		return 0, err
	}
	newID, _, err := writeIssued(ctx, pool, d, nil, now)
	return newID, err
}

func skipSiteBookingInvoice(ctx context.Context, pool *pgxpool.Pool, b siteBookingRow, reason string, now time.Time) {
	log.Printf("site booking %d: no invoice (%s)", b.ID, reason)
	_, _ = pool.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail, owner_user_id) VALUES ($1, 'system', 'site_invoice_skipped', $2, $3)`,
		stamp(now), fmt.Sprintf("id=%d reason=%s", b.ID, reason), b.OwnerUserID)
}

func loadSiteBooking(ctx context.Context, pool *pgxpool.Pool, id int64) (siteBookingRow, bool, error) {
	var b siteBookingRow
	b.ID = id
	var res, inv *int64
	var name, email, lang *string
	err := pool.QueryRow(ctx, `SELECT apartment_id, owner_user_id, reservation_id, invoice_id, status, total_czk,
		cleaning_fee_czk, guest_name, guest_email, lang FROM site_booking WHERE id = $1`, id).
		Scan(&b.ApartmentID, &b.OwnerUserID, &res, &inv, &b.Status, &b.TotalCZK, &b.CleaningFeeCZK, &name, &email, &lang)
	if errors.Is(err, pgx.ErrNoRows) {
		return b, false, nil
	}
	if err != nil {
		return b, false, err
	}
	b.ReservationID = res
	b.InvoiceID = inv
	if name != nil {
		b.GuestName = *name
	}
	if email != nil {
		b.GuestEmail = *email
	}
	if lang != nil {
		b.Lang = *lang
	}
	return b, true, nil
}

type apartmentRow struct {
	ID            int64
	InternalName  string
	LegalEntityID *int64
}

func loadApartment(ctx context.Context, pool *pgxpool.Pool, id int64) (apartmentRow, error) {
	var a apartmentRow
	var name *string
	var le *int64
	err := pool.QueryRow(ctx, `SELECT internal_name, legal_entity_id FROM apartment WHERE id = $1`, id).Scan(&name, &le)
	if errors.Is(err, pgx.ErrNoRows) {
		return a, nil
	}
	if err != nil {
		return a, err
	}
	a.ID = id
	if name != nil {
		a.InternalName = *name
	}
	a.LegalEntityID = le
	return a, nil
}

func loadReservation(ctx context.Context, pool *pgxpool.Pool, id int64) (stay, error) {
	var st stay
	err := pool.QueryRow(ctx, `SELECT apartment_id, date_from::text, date_to::text,
		COALESCE(status, ''), COALESCE(source, ''), COALESCE(guest_email, '')
		FROM reservation WHERE id = $1`, id).
		Scan(&st.ApartmentID, &st.DateFrom, &st.DateTo, &st.Status, &st.Source, &st.GuestEmail)
	if errors.Is(err, pgx.ErrNoRows) {
		return st, nil
	}
	if err != nil {
		return st, err
	}
	st.ReservationID = id
	return st, nil
}

// SiteBookingCancelReason is host_i18n site_booking.invoice.cancel_reason.
func SiteBookingCancelReason(lang string) string {
	return siteBookingT(lang, "site_booking.invoice.cancel_reason", 0)
}

func siteBookingT(lang, key string, cleaning int) string {
	if lang != "en" {
		lang = "cs"
	}
	switch key {
	case "site_booking.invoice.paid_via":
		if lang == "en" {
			return "Card via Stripe"
		}
		return "Kartou přes Stripe"
	case "site_booking.invoice.note":
		if cleaning <= 0 {
			return ""
		}
		if lang == "en" {
			return fmt.Sprintf("The price includes the cleaning fee of %d CZK.", cleaning)
		}
		return fmt.Sprintf("V ceně je úklid %d Kč.", cleaning)
	case "site_booking.invoice.partial_item":
		if lang == "en" {
			return "Partial refund of accommodation under the cancellation policy"
		}
		return "Vrácení části ubytování podle storno podmínek"
	case "site_booking.invoice.cancel_reason":
		if lang == "en" {
			return "Booking cancelled, payment refunded"
		}
		return "Zrušení rezervace, vrácení platby"
	default:
		return key
	}
}
